"""
q3a_fetch_hts10_lines.py

Phase 4 fix 3, step 1: fetch the US 10-digit HTS lines under each of
the top 10 core codes (by 2025 India value), same HTS REST API
approach used throughout this project.

READ-ONLY against core_device_codes.csv and raw/census/* (to rank by
2025 India value). Writes raw/hts/top10_hs10_lines.json (new file).
"""

import csv
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
CENSUS_DIR = HERE / "raw" / "census"
RAW_HTS_DIR = HERE / "raw" / "hts"
INDIA = "5330"
URL = "https://hts.usitc.gov/reststop/exportList"


def india_2025_value(code):
    raw_file = CENSUS_DIR / f"{code}_2025-12.json"
    if not raw_file.exists():
        return 0
    saved = json.loads(raw_file.read_text(encoding="utf-8"))
    if saved["status"] != "ok" or not saved["rows"]:
        return 0
    header, *records = saved["rows"]
    for rec in records:
        r = dict(zip(header, rec))
        if r.get("CTY_CODE") == INDIA and r.get("SUMMARY_LVL") == "DET":
            return int(r.get("CON_VAL_YR") or 0)
    return 0


def dotted(hs6):
    return f"{hs6[:4]}.{hs6[4:6]}"


def fetch(from_code, to_code):
    params = {"from": from_code, "to": to_code, "format": "JSON", "styles": "true"}
    url = URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "medical-device-tariff-study/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body) if body.strip() else []


def hs10_lines_for(hs6):
    base = dotted(hs6)
    data = fetch(f"{base}.00", f"{base}.99")
    lines = []
    for r in data:
        code = r.get("htsno", "").replace(".", "")
        if len(code) == 10 and code.startswith(hs6):
            lines.append(code)
    return sorted(set(lines))


def main():
    with open(DATA_DIR / "core_device_codes.csv", newline="", encoding="utf-8-sig") as f:
        codes = [(r["code"], r["description"]) for r in csv.DictReader(f) if r["level"] == "HS6"]

    ranked = sorted(((india_2025_value(c), c, d) for c, d in codes), reverse=True)
    top10 = ranked[:10]

    result = {}
    for val, code, desc in top10:
        lines = hs10_lines_for(code)
        result[code] = {"description": desc, "india_2025_usd": val, "hs10_lines": lines}
        print(f"{code} ({desc[:40]}): ${val:,} - {len(lines)} ten-digit lines")
        time.sleep(0.4)

    RAW_HTS_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_HTS_DIR / "top10_hs10_lines.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    total_lines = sum(len(v["hs10_lines"]) for v in result.values())
    print(f"\nTotal 10-digit lines across top 10 codes: {total_lines}")
    print("Wrote raw/hts/top10_hs10_lines.json")


if __name__ == "__main__":
    main()
