"""
b1b_census_fy2425_periods.py

Part 2b: download the Census periods needed to build an exact
April-March FY2024-25 figure for every HS6 in EPCMD's 151-code list
(data/epcmd_151_codes.csv), the same way step1 does:
    FY2024-25 = (2024-12 YTD) - (2024-03 YTD) + (2025-03 YTD)

For each of the 68 unique hs6 values in that list, downloads whichever
of these three periods is not already present in raw/census/ (same
skip-if-exists logic as step1 - never re-downloads or overwrites an
existing raw file):
    2024-12  (full calendar year 2024, YTD through December)
    2024-03  (YTD through March 2024)
    2025-03  (YTD through March 2025)

52 of the 68 hs6 codes already have 2024-12 from earlier runs (they
overlap with hs6_codes.csv); 16 are new to Census entirely and need all
three periods. This script figures out what's missing itself - no need
to run it differently for the two cases.

OUTPUT: new raw/census/<hs6>_<period>.json files only. Does not touch
any existing raw file, hs6_codes.csv, or any data/ CSV.
"""

import time

from common import HERE, RAW_DIR, fetch_json, log, progress, save_json_safely

import csv

URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
PERIODS = ["2024-12", "2024-03", "2025-03"]
LOG = "b1b_census_fy2425"
FIELDS = ["CTY_CODE", "CTY_NAME", "SUMMARY_LVL",
          "CON_VAL_YR", "GEN_VAL_YR", "DUT_VAL_YR", "CAL_DUT_YR"]
OUT_DIR = RAW_DIR / "census"


def read_key():
    key_file = HERE / "census_key.txt"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    return ""


def read_epcmd_hs6():
    with open(HERE / "data" / "epcmd_151_codes.csv", newline="", encoding="utf-8-sig") as f:
        return sorted(set(r["hs6"] for r in csv.DictReader(f)))


def ask(hs6, period, key):
    params = {
        "get": ",".join(FIELDS),
        "COMM_LVL": "HS6",
        "I_COMMODITY": hs6,
        "time": period,
    }
    if key:
        params["key"] = key
    return fetch_json(URL, params, LOG)


def main():
    key = read_key()
    hs6_list = read_epcmd_hs6()
    log(f"B1b started: Census FY24-25 periods for {len(hs6_list)} EPCMD hs6 codes", LOG)

    jobs = [(h, p) for h in hs6_list for p in PERIODS]
    started = time.time()
    failed = []
    n_skipped = n_done = 0

    for n, (hs6, period) in enumerate(jobs, start=1):
        raw_file = OUT_DIR / f"{hs6}_{period}.json"
        if raw_file.exists():
            n_skipped += 1
            continue
        status, data = ask(hs6, period, key)
        if status == "key_error":
            raise SystemExit(f"STOP: {data}")
        if status == "failed":
            failed.append((hs6, period, data))
            log(f"FAILED {hs6} {period}: {data}", LOG)
            continue
        save_json_safely(raw_file, {"status": status, "rows": data})
        n_done += 1
        log(f"{hs6} {period}: {status} | {progress(n, len(jobs), started)}", LOG)
        time.sleep(0.5)

    log(f"Done: {n_done} newly downloaded, {n_skipped} already present, "
        f"{len(failed)} failed", LOG)
    if failed:
        log(f"{len(failed)} requests failed. Run the script again to retry them.", LOG)
    log("B1b finished", LOG)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by you (Ctrl+C). Everything finished so far is saved.")
        print("Run the same command again to continue.")
