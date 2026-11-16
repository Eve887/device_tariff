"""
q3b_download_hs10_quantity.py

Phase 4 fix 3, step 2: download Census monthly value+quantity data at
COMM_LVL=HS10 for all 42 ten-digit lines found under the top 10 core
codes, for the baseline and shock months (same 12 months as Fix 1/2's
baseline-shock window: Oct 2024-Mar 2025 and Oct 2025-Mar 2026 - the
alpha measurement here is specifically testing the same shock used to
estimate epsilon, per the user's instruction).

Saved into a new directory, raw/census_hs10_qty/, for the same
collision-avoidance reason as every other distinct-data-shape download.
"""

import json
import time

from common import HERE, RAW_DIR, fetch_json, log, progress, save_json_safely

URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
LOG = "q3b_census_hs10_qty"
FIELDS = ["CTY_CODE", "CTY_NAME", "SUMMARY_LVL",
          "CON_VAL_MO", "CON_QY1_MO", "UNIT_QY1", "CON_QY2_MO", "UNIT_QY2"]
OUT_DIR = RAW_DIR / "census_hs10_qty"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MONTHS = (["2024-10", "2024-11", "2024-12", "2025-01", "2025-02", "2025-03"] +
          ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03"])


def read_key():
    key_file = HERE / "census_key.txt"
    return key_file.read_text(encoding="utf-8").strip() if key_file.exists() else ""


def read_lines():
    data = json.loads((RAW_DIR / "hts" / "top10_hs10_lines.json").read_text(encoding="utf-8"))
    lines = []
    for hs6, info in data.items():
        lines.extend(info["hs10_lines"])
    return lines


def ask(code, period, key):
    params = {"get": ",".join(FIELDS), "COMM_LVL": "HS10", "I_COMMODITY": code, "time": period}
    if key:
        params["key"] = key
    return fetch_json(URL, params, LOG)


def main():
    key = read_key()
    lines = read_lines()
    jobs = [(c, p) for c in lines for p in MONTHS]
    log(f"Q3b started: HS10 quantity data for {len(lines)} lines x {len(MONTHS)} months = {len(jobs)} jobs", LOG)

    started = time.time()
    failed = n_done = n_skipped = 0
    for n, (code, period) in enumerate(jobs, start=1):
        raw_file = OUT_DIR / f"{code}_{period}.json"
        if raw_file.exists():
            n_skipped += 1
            continue
        status, data = ask(code, period, key)
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
    log("Q3b finished", LOG)


if __name__ == "__main__":
    main()
