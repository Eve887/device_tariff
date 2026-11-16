"""
step2_india_trade_comtrade.py

WHAT IT DOES
    Downloads India's own trade figures for every code in hs6_codes.csv:
      - India's EXPORTS (flow X) to the World, the US and other key countries
        -> tells us what share of each product India sends to the US
           ("US dependence" in the exposure score, View A)
      - India's IMPORTS (flow M) from the World, the US, China and others
        -> tells us how much India buys from the US (View B)
    Source: UN Comtrade free public preview service (data India reports to
    the UN). https://comtradeapi.un.org/public/v1/preview/C/A/HS

WHAT YOU GET
    data/india_trade.csv            - one row per year x flow x code x partner
    raw/comtrade/<flow>_<year>_<n>.json - untouched server answers, saved as
        {"requested_codes": [...], "response": <the full server JSON>}
        so the raw file keeps the whole answer (not just the extracted rows)
        plus a record of which codes were actually asked for in that batch.

IMPORTANT: YEARS
    Comtrade shows India by CALENDAR year (Jan-Dec). India's own figures
    (TradeStat, EPCMD) use the FINANCIAL year (April-March). So Comtrade 2024
    will not exactly match FY 2024-25. Step 3 reminds you of this.

LIMIT OF THE FREE SERVICE
    Each answer can hold at most 500 rows. The script asks in small batches
    and, if an answer comes back full (500 rows), splits the batch in half
    and asks again, so nothing is silently cut off.

HOW TO RUN
    py step2_india_trade_comtrade.py      (Ctrl+C is safe; re-run to continue)
"""

import json
import time

from common import (DATA_DIR, RAW_DIR, fetch_json, log, progress, read_codes,
                    save_json_safely, write_csv)

URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
INDIA = "699"                     # UN country code for India
YEARS = [2022, 2023, 2024, 2025]
# Partner countries (UN codes): 0 = World total, 842 = USA, 156 = China,
# 276 = Germany, 392 = Japan, 484 = Mexico, 372 = Ireland
PARTNERS = {"0": "World", "842": "USA", "156": "China", "276": "Germany",
            "392": "Japan", "484": "Mexico", "372": "Ireland"}
FLOWS = {"X": "India exports", "M": "India imports"}
BATCH = 20                        # codes per question (20 x 7 partners = 140 rows)
ROW_LIMIT = 500
LOG = "step2_comtrade"
OUT_DIR = RAW_DIR / "comtrade"
OUT_DIR.mkdir(exist_ok=True)


def ask(flow, year, hs_list):
    params = {
        "reporterCode": INDIA,
        "period": str(year),
        "flowCode": flow,
        "cmdCode": ",".join(hs_list),
        "partnerCode": ",".join(PARTNERS),
        # Ask for totals only, not split by transport mode or customs regime,
        # otherwise the same trade would appear several times.
        "partner2Code": "0",
        "customsCode": "C00",
        "motCode": "0",
    }
    return fetch_json(URL, params, LOG)


def download_batch(flow, year, hs_list, label):
    """Download one batch; split it if the answer hits the 500-row limit."""
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
        # The server said there is nothing for this question. That is a
        # real possible answer (not an error), so record it as a response
        # with zero rows rather than treating it as a failure.
        data = {"data": [], "error": ""}
    # The real Comtrade response puts the rows under "data". Checking for
    # that key explicitly (instead of silently defaulting to an empty
    # list) is what catches a schema change or a wrong field name instead
    # of hiding it as a quiet zero-row "success".
    if not isinstance(data, dict) or "data" not in data:
        keys = sorted(data.keys()) if isinstance(data, dict) else type(data).__name__
        log(f"FAILED {flow} {year} batch {label}: response has no \"data\" "
            f"key (keys present: {keys})", LOG)
        return "failed"
    if data.get("error"):
        log(f"FAILED {flow} {year} batch {label}: server reported an "
            f"error: {data['error']}", LOG)
        return "failed"
    rows = data["data"]
    if len(rows) >= ROW_LIMIT and len(hs_list) > 1:
        half = len(hs_list) // 2
        log(f"  batch {label} hit {ROW_LIMIT} rows; splitting", LOG)
        r1 = download_batch(flow, year, hs_list[:half], label + "a")
        r2 = download_batch(flow, year, hs_list[half:], label + "b")
        return "failed" if "failed" in (r1, r2) else "ok"
    # Save the whole server answer (not just the rows we extracted), plus
    # which codes this batch actually asked for, so the raw file is real
    # evidence and the request can be audited later.
    save_json_safely(raw_file, {"requested_codes": hs_list, "response": data})
    time.sleep(1.5)               # the free service asks for gentle use

    max_possible = len(hs_list) * len(PARTNERS)
    codes_with_rows = {str(r.get("cmdCode", "")) for r in rows}
    codes_missing = [c for c in hs_list if c not in codes_with_rows]
    log(f"  batch {label}: {len(rows)} rows received (max possible = "
        f"{len(hs_list)} codes x {len(PARTNERS)} partners = {max_possible}); "
        f"{len(codes_with_rows)}/{len(hs_list)} of this batch's codes came "
        "back with at least one row"
        + (f"; no rows for: {', '.join(codes_missing)}" if codes_missing else ""),
        LOG)
    return "ok"


def main():
    codes = read_codes()
    hs_all = [c["hs6"] for c in codes]
    batches = [hs_all[i:i + BATCH] for i in range(0, len(hs_all), BATCH)]
    jobs = [(f, y, b, str(i)) for f in FLOWS for y in YEARS
            for i, b in enumerate(batches, start=1)]
    log("Step 2 started: India exports and imports (UN Comtrade)", LOG)
    started, failed = time.time(), 0
    for n, (flow, year, batch, label) in enumerate(jobs, start=1):
        result = download_batch(flow, year, batch, label)
        failed += result == "failed"
        if result != "skipped":
            log(f"{FLOWS[flow]} {year} batch {label}: {result} | "
                f"{progress(n, len(jobs), started)}", LOG)
    build_table(codes)
    if failed:
        log(f"{failed} batches failed. Run the script again to retry them.", LOG)
    log("Step 2 finished", LOG)


def build_table(codes):
    info = {c["hs6"]: c for c in codes}
    rows, seen = [], set()
    for raw_file in sorted(OUT_DIR.glob("*.json")):
        saved = json.loads(raw_file.read_text(encoding="utf-8"))
        for e in saved["response"]["data"]:
            hs6 = str(e.get("cmdCode", ""))
            partner = str(e.get("partnerCode", ""))
            key = (e.get("refYear"), e.get("flowCode"), hs6, partner)
            if key in seen:          # never count the same figure twice
                continue
            seen.add(key)
            rows.append({
                "year": e.get("refYear"),
                "flow": FLOWS.get(e.get("flowCode"), e.get("flowCode")),
                "hs6": hs6,
                "group": info.get(hs6, {}).get("group", ""),
                "description": info.get(hs6, {}).get("description", ""),
                "partner_code": partner,
                "partner": PARTNERS.get(partner, partner),
                # primaryValue = trade value in US$ (exports valued FOB,
                # imports valued CIF, i.e. including freight and insurance)
                "value_usd": e.get("primaryValue"),
                "net_weight_kg": e.get("netWgt"),
                "quantity": e.get("qty"),
                "quantity_unit_code": e.get("qtyUnitCode"),
            })
    rows.sort(key=lambda r: (r["flow"], r["hs6"], str(r["year"]), r["partner_code"]))
    columns = list(rows[0].keys()) if rows else ["year"]
    write_csv(DATA_DIR / "india_trade.csv", rows, columns)
    log(f"Wrote data/india_trade.csv with {len(rows)} rows", LOG)

    all_codes = {c["hs6"] for c in codes}
    for y in YEARS:
        have = {r["hs6"] for r in rows
                if r["flow"] == "India exports" and r["partner"] == "USA"
                and str(r["year"]) == str(y)}
        log(f"{y}: {len(have)}/{len(all_codes)} codes have an "
            "India-to-USA export figure", LOG)
    if not rows:
        log("Do NOT run step 3: india_trade.csv has 0 rows.", LOG)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by you (Ctrl+C). Everything finished so far is saved.")
        print("Run the same command again to continue.")
