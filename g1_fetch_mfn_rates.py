"""
g1_fetch_mfn_rates.py

Phase 3, Part 3 prep: fetch the US MFN ("general") duty rate for every
code in data/final_codes_grouped.csv from hts.usitc.gov's own REST API
- one sequential Python process (not a flood of separate curl calls),
polite delay between requests, same spirit as every Census download in
this project even though this is a different server.

For an HS6 code, fetches the full heading's children and reports the
rate if uniform across all 10-digit children, or "varies" with the
range of distinct rates found if not.
For an HS10 code, fetches that exact line directly.

OUTPUT: raw/hts/mfn_rates.json (new file, evidence) and prints a table.
Read-only against everything else.
"""

import csv
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
RAW_DIR = HERE / "raw" / "hts"
RAW_DIR.mkdir(parents=True, exist_ok=True)
URL = "https://hts.usitc.gov/reststop/exportList"


def load_codes():
    with open(DATA_DIR / "final_codes_grouped.csv", newline="", encoding="utf-8-sig") as f:
        return [(r["code"], r["level"]) for r in csv.DictReader(f)]


def dotted(code):
    """Turn a plain digit string into dotted HTS notation, e.g.
    '300510' -> '3005.10', '9025198010' -> '9025.19.80.10'."""
    if len(code) == 6:
        return f"{code[:4]}.{code[4:6]}"
    if len(code) == 10:
        return f"{code[:4]}.{code[4:6]}.{code[6:8]}.{code[8:10]}"
    return code


def fetch(from_code, to_code):
    params = {"from": from_code, "to": to_code, "format": "JSON", "styles": "true"}
    url = URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "medical-device-tariff-study/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body) if body.strip() else []


def mfn_for_hs6(hs6):
    base = dotted(hs6)
    # widen the net to catch all children under this 6-digit heading -
    # MUST start at .00, not .01: a flat/undivided subheading's rate
    # often lives on an 8-digit "<base>.00" line (confirmed directly
    # against 9018.31 "Syringes": the real "Free" rate is on
    # "9018.31.00", which a ".01"-".99" range silently excludes).
    data = fetch(f"{base}.00", f"{base}.99")
    if not data:
        data = fetch(base, base)
    rates = set()
    for r in data:
        if r.get("htsno", "").replace(".", "").startswith(hs6) and r.get("general", "").strip():
            rates.add(r["general"].strip())
    if len(rates) == 1:
        return rates.pop(), "uniform"
    if len(rates) > 1:
        return "; ".join(sorted(rates)), "varies"
    return "", "not found"


def mfn_for_hs10(hs10):
    """The chargeable rate for a 10-digit statistical line often lives
    on a shorter ancestor code (8-digit or 6-digit), with the 10-digit
    line itself carrying a blank rate (pure statistical breakout) -
    confirmed directly against 9018.31 earlier. So: fetch the whole
    6-digit heading, then take the rate from the LONGEST matching
    ancestor code that has a non-empty rate (closest governing line)."""
    hs6 = hs10[:6]
    base6 = dotted(hs6)
    data = fetch(f"{base6}.00", f"{base6}.99")
    best = None  # (ancestor_length, rate)
    for r in data:
        code = r.get("htsno", "").replace(".", "")
        rate = r.get("general", "").strip()
        if code and rate and hs10.startswith(code):
            if best is None or len(code) > best[0]:
                best = (len(code), rate)
    if best:
        return best[1], f"inherited from {best[0]}-digit ancestor"
    return "", "not found"


def main():
    codes = load_codes()
    results = {}
    for code, level in codes:
        try:
            if level == "HS6":
                rate, status = mfn_for_hs6(code)
            else:
                rate, status = mfn_for_hs10(code)
        except Exception as e:
            rate, status = "", f"ERROR: {e}"
        results[code] = {"level": level, "general_rate": rate, "status": status}
        print(f"{code} ({level}): {rate!r} [{status}]")
        time.sleep(0.4)

    (RAW_DIR / "mfn_rates.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote raw/hts/mfn_rates.json ({len(results)} codes)")

    not_found = [c for c, r in results.items() if r["status"] == "not found" or not r["general_rate"]]
    if not_found:
        print(f"\nCodes with NO rate found ({len(not_found)}):", not_found)


if __name__ == "__main__":
    main()
