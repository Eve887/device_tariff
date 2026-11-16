"""
d3_census_monthly.py

Phase 3, Part 2: download Census MONTHLY (not year-to-date) figures for
every code in data/final_codes_grouped.csv, for every month January
2024 through the latest published 2026 month. Uses the _MO field
suffixes (that month only), not _YR (cumulative year-to-date) - a
distinct data shape from everything downloaded so far in this project.

IMPORTANT: saved into a SEPARATE directory, raw/census_monthly/, using
the same <code>_<period>.json filename convention as raw/census/ - this
is deliberate, so a monthly file for e.g. "2024-12" can never collide
with or be mistaken for the existing YTD file of the same name in
raw/census/ (which holds _YR fields, a different shape entirely).

Skip-if-exists, same discipline as every other download script in this
project. This is a long run (63 codes x ~33 months = ~2000 requests);
safe to interrupt with Ctrl+C and re-run - already-downloaded months are
skipped.
"""

import csv
import time

from common import HERE, RAW_DIR, fetch_json, log, progress, save_json_safely

URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
LOG = "d3_census_monthly"
FIELDS = ["CTY_CODE", "CTY_NAME", "SUMMARY_LVL",
          "CON_VAL_MO", "GEN_VAL_MO", "DUT_VAL_MO", "CAL_DUT_MO"]
OUT_DIR = RAW_DIR / "census_monthly"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def read_key():
    key_file = HERE / "census_key.txt"
    return key_file.read_text(encoding="utf-8").strip() if key_file.exists() else ""


def read_codes():
    with open(HERE / "data" / "final_codes_grouped.csv", newline="", encoding="utf-8-sig") as f:
        return [(r["code"], r["level"]) for r in csv.DictReader(f)]


def build_months():
    months = [f"2024-{m:02d}" for m in range(1, 13)]
    months += [f"2025-{m:02d}" for m in range(1, 13)]
    months += [f"2026-{m:02d}" for m in range(1, 10)]  # through September, the latest published month
    return months


def ask(code, level, period, key):
    params = {"get": ",".join(FIELDS), "COMM_LVL": level, "I_COMMODITY": code, "time": period}
    if key:
        params["key"] = key
    return fetch_json(URL, params, LOG)


def main():
    key = read_key()
    codes = read_codes()
    months = build_months()
    jobs = [(c, lvl, p) for c, lvl in codes for p in months]
    log(f"D3 started: monthly Census data for {len(codes)} codes x {len(months)} months "
        f"= {len(jobs)} jobs", LOG)

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
    if failed:
        log(f"{failed} requests failed. Run the script again to retry them.", LOG)
    log("D3 finished", LOG)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by you (Ctrl+C). Everything finished so far is saved.")
        print("Run the same command again to continue.")
