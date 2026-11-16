"""
d1_census_final.py

Downloads every period needed for the final Phase 2 code list:
    2024-03, 2024-09, 2024-12, 2025-03, 2025-09, 2025-12,
    and the latest published 2026 month (determined the same way step1 does).

Covers every code in data/final_codes.csv and data/lab_instruments_codes.csv,
at whichever level (HS6 or HS10) that file specifies. HS10 codes use
COMM_LVL=HS10 with the code written without dots (e.g. "9025198010"),
confirmed working in the Part 2d test.

Skip-if-exists, same convention as step1: raw/census/<code>_<period>.json.
Never re-downloads or touches an existing raw file.
"""

import csv
import time

from common import HERE, RAW_DIR, fetch_json, log, progress, save_json_safely

URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
PERIODS = ["2024-03", "2024-09", "2024-12", "2025-03", "2025-09", "2025-12"]
LOG = "d1_census_final"
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
    params = {
        "get": ",".join(FIELDS),
        "COMM_LVL": level,
        "I_COMMODITY": code,
        "time": period,
    }
    if key:
        params["key"] = key
    return fetch_json(URL, params, LOG)


def latest_2026_month(key):
    for month in range(12, 0, -1):
        period = f"2026-{month:02d}"
        status, _ = ask("901831", "HS6", period, key)
        if status == "ok":
            return period
    return None


def main():
    key = read_key()
    codes = read_codes()
    log(f"D1 started: Census final periods for {len(codes)} codes (final_codes.csv + lab_instruments_codes.csv)", LOG)

    ytd = latest_2026_month(key)
    periods = PERIODS + ([ytd] if ytd else [])
    if ytd:
        log(f"Latest 2026 month published: {ytd}", LOG)
    else:
        log("No 2026 month found yet", LOG)

    jobs = [(c, lvl, p) for c, lvl in codes for p in periods]
    started = time.time()
    failed = []
    n_done = n_skipped = 0

    for n, (code, level, period) in enumerate(jobs, start=1):
        raw_file = OUT_DIR / f"{code}_{period}.json"
        if raw_file.exists():
            n_skipped += 1
            continue
        status, data = ask(code, level, period, key)
        if status == "key_error":
            raise SystemExit(f"STOP: {data}")
        if status == "failed":
            failed.append((code, period, data))
            log(f"FAILED {code} {period}: {data}", LOG)
            continue
        save_json_safely(raw_file, {"status": status, "rows": data})
        n_done += 1
        log(f"{code} {period}: {status} | {progress(n, len(jobs), started)}", LOG)
        time.sleep(0.5)

    log(f"Done: {n_done} newly downloaded, {n_skipped} already present, {len(failed)} failed", LOG)
    if failed:
        log(f"{len(failed)} requests failed. Run the script again to retry them.", LOG)
    log("D1 finished", LOG)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by you (Ctrl+C). Everything finished so far is saved.")
