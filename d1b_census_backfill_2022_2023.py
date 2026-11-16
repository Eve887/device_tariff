"""
d1b_census_backfill_2022_2023.py

phase2_final_summary.csv needs full years 2022-2025 for every code in
final_codes.csv and lab_instruments_codes.csv. Earlier downloads
(d1_census_final.py) covered 2024-03 through the latest 2026 month, but
never fetched 2022-12 or 2023-12 for codes that are new to this project
(beyond the original 61-code list). This fills exactly that gap.

Skip-if-exists, same convention as every other step.
"""

import csv
import time

from common import HERE, RAW_DIR, fetch_json, log, progress, save_json_safely

URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
PERIODS = ["2022-12", "2023-12"]
LOG = "d1b_backfill_2022_2023"
FIELDS = ["CTY_CODE", "CTY_NAME", "SUMMARY_LVL",
          "CON_VAL_YR", "GEN_VAL_YR", "DUT_VAL_YR", "CAL_DUT_YR"]
OUT_DIR = RAW_DIR / "census"


def read_key():
    key_file = HERE / "census_key.txt"
    return key_file.read_text(encoding="utf-8").strip() if key_file.exists() else ""


def read_codes():
    codes = []
    for fname in ("final_codes.csv", "lab_instruments_codes.csv"):
        with open(HERE / "data" / fname, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                codes.append((r["code"], r["level"]))
    return codes


def ask(code, level, period, key):
    params = {"get": ",".join(FIELDS), "COMM_LVL": level, "I_COMMODITY": code, "time": period}
    if key:
        params["key"] = key
    return fetch_json(URL, params, LOG)


def main():
    key = read_key()
    codes = read_codes()
    jobs = [(c, lvl, p) for c, lvl in codes for p in PERIODS]
    log(f"D1b started: backfilling 2022-12/2023-12 for {len(codes)} codes", LOG)
    started = time.time()
    failed = n_done = n_skipped = 0
    for n, (code, level, period) in enumerate(jobs, start=1):
        raw_file = OUT_DIR / f"{code}_{period}.json"
        if raw_file.exists():
            n_skipped += 1
            continue
        status, data = ask(code, level, period, key)
        if status == "key_error":
            raise SystemExit(f"STOP: {data}")
        if status == "failed":
            failed += 1
            log(f"FAILED {code} {period}: {data}", LOG)
            continue
        save_json_safely(raw_file, {"status": status, "rows": data})
        n_done += 1
        log(f"{code} {period}: {status} | {progress(n, len(jobs), started)}", LOG)
        time.sleep(0.5)
    log(f"Done: {n_done} newly downloaded, {n_skipped} already present, {failed} failed", LOG)
    log("D1b finished", LOG)


if __name__ == "__main__":
    main()
