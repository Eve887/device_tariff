"""
c2c_fy2425_reconciliation.py

Part 2c: build an exact April 2024-March 2025 US-imports-from-India
figure for every hs6 in EPCMD's list, using:
    FY2024-25 = (2024-12 YTD) - (2024-03 YTD) + (2025-03 YTD)
read directly from the raw Census files (2024-12 from earlier runs or
b1b, 2024-03/2025-03 from b1b). Then sum separately for CLEAN and MIXED
hs6 groups (per data/epcmd_hs6_classification.csv) and compare the CLEAN
total against EPCMD's $782.57 million.

READ-ONLY against raw/census/*.json and data/epcmd_hs6_classification.csv.
OUTPUT: data/fy2425_reconciliation.csv (new file, per-hs6 detail) and
prints the summary table.
"""

import json
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
OUT_DIR = HERE / "raw" / "census"
INDIA = "5330"
EPCMD_TARGET = 782_570_000


def load_india_value(hs6, period):
    raw_file = OUT_DIR / f"{hs6}_{period}.json"
    if not raw_file.exists():
        return None
    saved = json.loads(raw_file.read_text(encoding="utf-8"))
    if saved["status"] != "ok" or not saved["rows"]:
        return 0
    header, *records = saved["rows"]
    for rec in records:
        r = dict(zip(header, rec))
        if r.get("CTY_CODE") == INDIA and r.get("SUMMARY_LVL") == "DET":
            return int(r.get("CON_VAL_YR") or 0)
    return 0


def fy_value(hs6):
    v_dec24 = load_india_value(hs6, "2024-12")
    v_mar24 = load_india_value(hs6, "2024-03")
    v_mar25 = load_india_value(hs6, "2025-03")
    if None in (v_dec24, v_mar24, v_mar25):
        return None
    return v_dec24 - v_mar24 + v_mar25


def main():
    with open(DATA_DIR / "epcmd_hs6_classification.csv", newline="", encoding="utf-8-sig") as f:
        classes = list(csv.DictReader(f))

    rows = []
    totals = {"CLEAN": 0, "MIXED": 0, "UNKNOWN": 0}
    for c in classes:
        hs6 = c["hs6"]
        cls = c["classification"].split(" ")[0].split("(")[0].strip()
        fy = fy_value(hs6)
        rows.append({
            "hs6": hs6,
            "description": c["description"],
            "classification": cls,
            "fy2425_us_imports_from_india_usd": fy if fy is not None else "",
        })
        if fy is not None and cls in totals:
            totals[cls] += fy

    with open(DATA_DIR / "fy2425_reconciliation.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote data/fy2425_reconciliation.csv ({len(rows)} rows)\n")
    print(f"{'Group':<12}{'FY2024-25 US imports from India $':>36}")
    print(f"{'CLEAN':<12}{totals['CLEAN']:>36,}")
    print(f"{'MIXED':<12}{totals['MIXED']:>36,}  (shown separately - NOT added in, includes non-medical products)")
    print(f"{'UNKNOWN':<12}{totals['UNKNOWN']:>36,}  (shown separately - classification not confirmed either way)")
    print()
    print(f"{'EPCMD target (USA, FY2024-25)':<35}{EPCMD_TARGET:>20,}")
    print(f"{'Gap (target - CLEAN total)':<35}{EPCMD_TARGET - totals['CLEAN']:>20,}")
    print(f"{'Gap (target - CLEAN - MIXED)':<35}{EPCMD_TARGET - totals['CLEAN'] - totals['MIXED']:>20,}")
    print(f"{'Gap (target - CLEAN - MIXED - UNKNOWN)':<35}{EPCMD_TARGET - totals['CLEAN'] - totals['MIXED'] - totals['UNKNOWN']:>20,}")

    # Show the largest MIXED hs6 by value, for Part 2d
    print("\nMIXED hs6 groups sorted by FY2024-25 value (for Part 2d):")
    mixed = sorted((r for r in rows if r["classification"] == "MIXED"),
                   key=lambda r: r["fy2425_us_imports_from_india_usd"] if r["fy2425_us_imports_from_india_usd"] != "" else 0,
                   reverse=True)
    for r in mixed:
        print(f"  {r['hs6']}: {r['description'][:50]:<52} {r['fy2425_us_imports_from_india_usd']:>14,}")


if __name__ == "__main__":
    main()
