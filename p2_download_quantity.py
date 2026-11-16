"""
p2_download_quantity.py

Phase 4, Part 2: download Census monthly QUANTITY data (CON_QY1_MO,
UNIT_QY1, plus the secondary CON_QY2_MO/UNIT_QY2 in case a code
reports under the second quantity unit instead) for the baseline and
shock months, for core_device_codes.csv only (60 codes).

Field names confirmed directly against
https://api.census.gov/data/timeseries/intltrade/imports/hs/variables.json
(raw/census_variables.json) rather than guessed.

Saved into a SEPARATE directory, raw/census_monthly_qty/, using the
same <code>_<period>.json filename convention as raw/census_monthly/ -
deliberate, so this quantity-field response (a different shape) can
never be confused with or overwrite the value-only monthly files
already saved for the same periods.
"""

import csv
import time

from common import HERE, RAW_DIR, fetch_json, log, progress, save_json_safely

URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
LOG = "p2_census_quantity"
FIELDS = ["CTY_CODE", "CTY_NAME", "SUMMARY_LVL",
          "CON_VAL_MO", "CON_QY1_MO", "UNIT_QY1", "CON_QY2_MO", "UNIT_QY2"]
OUT_DIR = RAW_DIR / "census_monthly_qty"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MONTHS = (["2024-10", "2024-11", "2024-12", "2025-01", "2025-02", "2025-03"] +
          ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03"])


def read_key():
    key_file = HERE / "census_key.txt"
    return key_file.read_text(encoding="utf-8").strip() if key_file.exists() else ""


def read_codes():
    with open(HERE / "data" / "core_device_codes.csv", newline="", encoding="utf-8-sig") as f:
        return [(r["code"], r["level"]) for r in csv.DictReader(f)]


def ask(code, level, period, key):
    params = {"get": ",".join(FIELDS), "COMM_LVL": level, "I_COMMODITY": code, "time": period}
    if key:
        params["key"] = key
    return fetch_json(URL, params, LOG)


def main():
    key = read_key()
    codes = read_codes()
    jobs = [(c, lvl, p) for c, lvl in codes for p in MONTHS]
    log(f"P2 started: quantity data for {len(codes)} codes x {len(MONTHS)} months = {len(jobs)} jobs", LOG)

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
        if n_done % 25 == 0 or n == len(jobs):
            log(f"{code} {period}: {status} | {progress(n, len(jobs), started)}", LOG)
        time.sleep(0.5)

    log(f"Done: {n_done} newly downloaded, {n_skipped} already present, {failed} failed", LOG)
    log("P2 finished", LOG)


if __name__ == "__main__":
    main()
