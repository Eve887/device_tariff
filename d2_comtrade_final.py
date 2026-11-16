"""
d2_comtrade_final.py

Downloads UN Comtrade (India-reported) data for HS6 codes in
data/final_codes.csv and data/lab_instruments_codes.csv that are new
(not already covered by the earlier 61-code step2 run). Same batching,
same partners/flows/years as step2_india_trade_comtrade.py, same fixed
parsing (reads response["data"], checks for "error", saves the whole
server answer) - just a different, smaller code list.

Skip-if-exists via raw/comtrade/<flow>_<year>_<label>.json; does not
touch any existing batch file.
"""

import csv
import time

from common import DATA_DIR, RAW_DIR, fetch_json, log, progress, save_json_safely, write_csv

URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
INDIA = "699"
YEARS = [2022, 2023, 2024, 2025]
PARTNERS = {"0": "World", "842": "USA", "156": "China", "276": "Germany",
            "392": "Japan", "484": "Mexico", "372": "Ireland"}
FLOWS = {"X": "India exports", "M": "India imports"}
BATCH = 20
ROW_LIMIT = 500
LOG = "d2_comtrade_final"
OUT_DIR = RAW_DIR / "comtrade" / "final_new_codes"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HERE = RAW_DIR.parent


def read_new_hs6():
    with open(HERE / "hs6_codes.csv", newline="", encoding="utf-8") as f:
        our61 = set(r["hs6"] for r in csv.DictReader(f))
    all_hs6 = set()
    for fname in ("final_codes.csv", "lab_instruments_codes.csv"):
        with open(HERE / "data" / fname, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r["level"] == "HS6":
                    all_hs6.add(r["code"])
    return sorted(all_hs6 - our61)


def ask(flow, year, hs_list):
    params = {
        "reporterCode": INDIA, "period": str(year), "flowCode": flow,
        "cmdCode": ",".join(hs_list), "partnerCode": ",".join(PARTNERS),
        "partner2Code": "0", "customsCode": "C00", "motCode": "0",
    }
    return fetch_json(URL, params, LOG)


def download_batch(flow, year, hs_list, label):
    raw_file = OUT_DIR / f"{flow}_{year}_{label}.json"
    if raw_file.exists():
        return "skipped"
    status, data = ask(flow, year, hs_list)
    if status == "key_error":
        raise SystemExit(f"STOP: {data}")
    if status == "failed":
        log(f"FAILED {flow} {year} batch {label}: {data}", LOG)
        return "failed"
    if status == "no_data":
        data = {"data": [], "error": ""}
    if not isinstance(data, dict) or "data" not in data:
        keys = sorted(data.keys()) if isinstance(data, dict) else type(data).__name__
        log(f"FAILED {flow} {year} batch {label}: response has no \"data\" key (keys: {keys})", LOG)
        return "failed"
    if data.get("error"):
        log(f"FAILED {flow} {year} batch {label}: server error: {data['error']}", LOG)
        return "failed"
    rows = data["data"]
    if len(rows) >= ROW_LIMIT and len(hs_list) > 1:
        half = len(hs_list) // 2
        r1 = download_batch(flow, year, hs_list[:half], label + "a")
        r2 = download_batch(flow, year, hs_list[half:], label + "b")
        return "failed" if "failed" in (r1, r2) else "ok"
    save_json_safely(raw_file, {"requested_codes": hs_list, "response": data})
    time.sleep(1.5)
    log(f"  batch {label}: {len(rows)} rows received ({len(hs_list)} codes x {len(PARTNERS)} partners = {len(hs_list)*len(PARTNERS)} max)", LOG)
    return "ok"


def main():
    hs6_list = read_new_hs6()
    if not hs6_list:
        log("No new hs6 codes need Comtrade data. D2 finished.", LOG)
        return
    log(f"D2 started: Comtrade for {len(hs6_list)} new hs6 codes: {hs6_list}", LOG)
    batches = [hs6_list[i:i + BATCH] for i in range(0, len(hs6_list), BATCH)]
    jobs = [(f, y, b, str(i)) for f in FLOWS for y in YEARS for i, b in enumerate(batches, start=1)]
    started, failed = time.time(), 0
    for n, (flow, year, batch, label) in enumerate(jobs, start=1):
        result = download_batch(flow, year, batch, label)
        failed += result == "failed"
        if result != "skipped":
            log(f"{FLOWS[flow]} {year} batch {label}: {result} | {progress(n, len(jobs), started)}", LOG)
    build_table()
    if failed:
        log(f"{failed} batches failed. Run again to retry.", LOG)
    log("D2 finished", LOG)


def build_table():
    rows, seen = [], set()
    for raw_file in sorted(OUT_DIR.glob("*.json")):
        import json
        saved = json.loads(raw_file.read_text(encoding="utf-8"))
        for e in saved["response"]["data"]:
            hs6 = str(e.get("cmdCode", ""))
            partner = str(e.get("partnerCode", ""))
            key = (e.get("refYear"), e.get("flowCode"), hs6, partner)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "year": e.get("refYear"),
                "flow": FLOWS.get(e.get("flowCode"), e.get("flowCode")),
                "hs6": hs6, "partner_code": partner,
                "partner": PARTNERS.get(partner, partner),
                "value_usd": e.get("primaryValue"),
                "net_weight_kg": e.get("netWgt"),
            })
    rows.sort(key=lambda r: (r["flow"], r["hs6"], str(r["year"]), r["partner_code"]))
    if rows:
        columns = list(rows[0].keys())
        write_csv(DATA_DIR / "india_trade_final_new_codes.csv", rows, columns)
        log(f"Wrote data/india_trade_final_new_codes.csv ({len(rows)} rows)", LOG)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by you (Ctrl+C). Everything finished so far is saved.")
