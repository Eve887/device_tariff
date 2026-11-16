"""
b1_census_ytd2025.py

Investigation B1: download US Census imports-for-consumption data for
period 2025-09 (January-September 2025 year-to-date) for every code in
hs6_codes.csv, the same way step1_us_imports_census.py downloads any
other period. This gives a like-for-like comparison against 2026-09
(January-September 2026), which step1 already downloaded as its
"latest 2026 month".

Does not modify or overwrite any existing raw file: this period
(2025-09) was never fetched by step1 (which only fetches full
calendar-year Decembers plus the latest 2026 YTD month), so every file
this writes is new.

OUTPUT: raw/census/<hs6>_2025-09.json (new files; same naming
convention as step1, so step1 could pick them up for free on a future
run, but step1 itself is untouched).
"""

import time

from common import HERE, RAW_DIR, fetch_json, log, progress, read_codes, save_json_safely

URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
PERIOD = "2025-09"
LOG = "b1_census_ytd2025"
FIELDS = ["CTY_CODE", "CTY_NAME", "SUMMARY_LVL",
          "CON_VAL_YR", "GEN_VAL_YR", "DUT_VAL_YR", "CAL_DUT_YR"]
OUT_DIR = RAW_DIR / "census"


def read_key():
    key_file = HERE / "census_key.txt"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    return ""


def ask(hs6, key):
    params = {
        "get": ",".join(FIELDS),
        "COMM_LVL": "HS6",
        "I_COMMODITY": hs6,
        "time": PERIOD,
    }
    if key:
        params["key"] = key
    return fetch_json(URL, params, LOG)


def main():
    key = read_key()
    codes = read_codes()
    log(f"B1 started: Census {PERIOD} for all {len(codes)} codes", LOG)

    started = time.time()
    failed = []
    for n, code in enumerate(codes, start=1):
        raw_file = OUT_DIR / f"{code['hs6']}_{PERIOD}.json"
        if raw_file.exists():
            continue
        status, data = ask(code["hs6"], key)
        if status == "key_error":
            raise SystemExit(f"STOP: {data}")
        if status == "failed":
            failed.append((code["hs6"], data))
            log(f"FAILED {code['hs6']} {PERIOD}: {data}", LOG)
            continue
        save_json_safely(raw_file, {"status": status, "rows": data})
        log(f"{code['hs6']} {PERIOD}: {status} | {progress(n, len(codes), started)}", LOG)
        time.sleep(0.5)

    if failed:
        log(f"{len(failed)} codes failed. Run the script again to retry them.", LOG)
    log("B1 finished", LOG)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by you (Ctrl+C). Everything finished so far is saved.")
        print("Run the same command again to continue.")
