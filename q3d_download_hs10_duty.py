"""
q3d_download_hs10_duty.py

Phase 4 fix 3, step 2b (added after discovering the gap): the HS10
quantity records downloaded in q3b did not include CAL_DUT_MO, and
these 42 specific 10-digit lines were never separately pulled at
monthly granularity in Phase 3/4 (raw/census_monthly/ only has the
60 core HS6 codes + a handful of unrelated HS10 codes - none of our
42 lines are in it). Alpha needs India's OWN tariff-rate change
(calculated duty / value), so this fetches CON_VAL_MO + CAL_DUT_MO
for the same 42 lines x 12 months (baseline+shock), same API, same
checkpoint/skip-if-exists pattern as every other download script.

Saved into its own new directory, raw/census_hs10_duty/, to keep this
distinct data shape separate from raw/census_hs10_qty/ (evidence
layering - never mix shapes in one folder).
"""

import json
import time

from common import HERE, RAW_DIR, fetch_json, log, progress, save_json_safely

URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
LOG = "q3d_census_hs10_duty"
FIELDS = ["CTY_CODE", "CTY_NAME", "SUMMARY_LVL", "CON_VAL_MO", "CAL_DUT_MO"]
OUT_DIR = RAW_DIR / "census_hs10_duty"
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
    log(f"Q3d started: HS10 duty data for {len(lines)} lines x {len(MONTHS)} months = {len(jobs)} jobs", LOG)

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
    log("Q3d finished", LOG)


if __name__ == "__main__":
    main()
