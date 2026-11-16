"""
step1_us_imports_census.py

WHAT IT DOES
    Downloads what the US imported of each medical device code (hs6_codes.csv),
    from every country, for full years 2022-2025 and 2026 so far.
    Source: US Census Bureau International Trade API (official US trade data,
    the same numbers USITC DataWeb shows).
    https://api.census.gov/data/timeseries/intltrade/imports/hs

WHAT YOU GET
    data/us_imports_by_country.csv  - one row per year x code x country
    raw/census/<code>_<period>.json - the untouched server answers (evidence)

KEY FIELDS (explained in simple words)
    CON_VAL_YR : "imports for consumption" value in US$ for the year so far.
                 This is the value that actually entered the US market and on
                 which duty is charged. We use it as Exposure (E).
    GEN_VAL_YR : "general imports" - also counts goods put into bonded
                 warehouses. Kept for checking only.
    DUT_VAL_YR : the part of the value that was dutiable.
    CAL_DUT_YR : duty in US$ that Census calculated for those imports.
    _YR fields with time=YYYY-12 give the full calendar year (Jan-Dec).

HOW TO RUN (Windows Command Prompt, inside this folder)
    py step1_us_imports_census.py
    You can press Ctrl+C at any time. Run the same command again and it
    continues from where it stopped (finished downloads are skipped).

API KEY (REQUIRED)
    Census now refuses this service without a key (tested Nov 2026: every
    request without one is redirected to missing_key.html). Get a free key:
    https://api.census.gov/data/key_signup.html
    activate it from the email, then put the key alone in a file named
    census_key.txt in this folder. The script checks the key first and
    stops with a clear message if it is missing or wrong.
"""

import json
import time

from common import (DATA_DIR, HERE, RAW_DIR, fetch_json, log, progress,
                    read_codes, save_json_safely, write_csv)

URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
FULL_YEARS = [2022, 2023, 2024, 2025]
LOG = "step1_census"
FIELDS = ["CTY_CODE", "CTY_NAME", "SUMMARY_LVL",
          "CON_VAL_YR", "GEN_VAL_YR", "DUT_VAL_YR", "CAL_DUT_YR"]
OUT_DIR = RAW_DIR / "census"
OUT_DIR.mkdir(exist_ok=True)


def read_key():
    key_file = HERE / "census_key.txt"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    return ""


def ask(hs6, period, key):
    """One question to Census: all countries, one code, one period."""
    params = {
        "get": ",".join(FIELDS),
        "COMM_LVL": "HS6",
        "I_COMMODITY": hs6,
        "time": period,
    }
    if key:
        params["key"] = key
    return fetch_json(URL, params, LOG)


def latest_2026_month(key):
    """
    Find the newest month of 2026 that Census has published.
    Census publishes each month about 5 weeks after it ends, so we try
    from December backwards and stop at the first month that has data.
    """
    for month in range(12, 0, -1):
        period = f"2026-{month:02d}"
        status, _ = ask("901831", period, key)
        if status == "ok":
            return period
    return None


def check_key(key):
    """
    Ask one small question first. If the key is missing or wrong, stop now
    with a clear message instead of failing 240 times.
    """
    if not key:
        log("STOP: no API key. Census now requires one for this service.\n"
            "  1. Get a free key: https://api.census.gov/data/key_signup.html\n"
            "  2. Census emails it to you; click the activation link in that email.\n"
            "  3. Paste the key alone into census_key.txt in this folder.\n"
            "  4. Run this script again.", LOG)
        return False
    status, data = ask("901831", "2024-12", key)
    if status == "ok":
        log("API key works.", LOG)
        return True
    log(f"STOP: test question failed ({status}: {data}).\n"
        "  If it says the key is invalid: check you clicked the activation link\n"
        "  in the Census email, and that census_key.txt holds only the key\n"
        "  (no spaces, no quotes).", LOG)
    return False


def main():
    key = read_key()
    codes = read_codes()
    log("Step 1 started: US imports by country (Census)", LOG)
    if not check_key(key):
        return

    periods = [f"{y}-12" for y in FULL_YEARS]
    ytd = latest_2026_month(key)
    if ytd:
        periods.append(ytd)
        log(f"Latest 2026 month published: {ytd} (2026 figures are Jan to that month)", LOG)
    else:
        log("No 2026 month found yet; using full years only", LOG)

    jobs = [(c, p) for c in codes for p in periods]
    started = time.time()
    failed = []

    for n, (code, period) in enumerate(jobs, start=1):
        raw_file = OUT_DIR / f"{code['hs6']}_{period}.json"
        if raw_file.exists():          # already downloaded in an earlier run
            continue
        status, data = ask(code["hs6"], period, key)
        if status == "key_error":
            log(f"STOP: {data}. Fix census_key.txt and run again.", LOG)
            return
        if status == "failed":
            failed.append((code["hs6"], period, data))
            log(f"FAILED {code['hs6']} {period}: {data}", LOG)
            continue
        # Save even "no data" answers, so we do not ask again next time.
        save_json_safely(raw_file, {"status": status, "rows": data})
        log(f"{code['hs6']} {period}: {status} | {progress(n, len(jobs), started)}", LOG)
        time.sleep(0.5)                # be polite to the server

    build_table(codes, periods)
    if failed:
        log(f"{len(failed)} questions failed. Run the script again to retry them.", LOG)
    log("Step 1 finished", LOG)


def build_table(codes, periods):
    """Turn all raw answers into one clean CSV."""
    rows = []
    for code in codes:
        for period in periods:
            raw_file = OUT_DIR / f"{code['hs6']}_{period}.json"
            if not raw_file.exists():
                continue
            saved = json.loads(raw_file.read_text(encoding="utf-8"))
            if saved["status"] != "ok" or not saved["rows"]:
                continue
            header, *records = saved["rows"]   # first row = column names
            for rec in records:
                r = dict(zip(header, rec))
                con_val = int(r.get("CON_VAL_YR") or 0)
                duty = int(r.get("CAL_DUT_YR") or 0)
                rows.append({
                    "year": period[:4],
                    "period_end": period,
                    "months_covered": int(period[5:7]),
                    "hs6": code["hs6"],
                    "group": code["group"],
                    "description": code["description"],
                    "cty_code": r.get("CTY_CODE", ""),
                    "cty_name": r.get("CTY_NAME", ""),
                    # DET = a single country; CGP = a group such as
                    # "TOTAL FOR ALL COUNTRIES" or "EUROPEAN UNION".
                    "summary_lvl": r.get("SUMMARY_LVL", ""),
                    "imports_for_consumption_usd": con_val,
                    "general_imports_usd": int(r.get("GEN_VAL_YR") or 0),
                    "dutiable_value_usd": int(r.get("DUT_VAL_YR") or 0),
                    "calculated_duty_usd": duty,
                    # Duty paid as % of value. A typed number, not a formula.
                    "effective_duty_rate_pct": round(100 * duty / con_val, 2) if con_val else "",
                })
    columns = list(rows[0].keys()) if rows else ["year"]
    write_csv(DATA_DIR / "us_imports_by_country.csv", rows, columns)
    log(f"Wrote data/us_imports_by_country.csv with {len(rows)} rows", LOG)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by you (Ctrl+C). Everything finished so far is saved.")
        print("Run the same command again to continue.")
