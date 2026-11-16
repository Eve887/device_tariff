"""
h3_top15_suppliers.py

Phase 3 fix 3, part 1: find the top 15 core device codes by 2025 India
value, and for each, the top 3 NON-INDIA suppliers (by name), their
2025 import value, and their Jan-Sep 2026 actual duty paid as % of
value (from Census calculated duty, same method as every prior step).

READ-ONLY against core_device_codes.csv and raw/census/*.
"""

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
CENSUS_DIR = HERE / "raw" / "census"
INDIA = "5330"


def load_codes():
    with open(DATA_DIR / "core_device_codes.csv", newline="", encoding="utf-8-sig") as f:
        return [(r["code"], r["level"], r["description"]) for r in csv.DictReader(f)]


def census_detail(code, period):
    raw_file = CENSUS_DIR / f"{code}_{period}.json"
    if not raw_file.exists():
        return None
    saved = json.loads(raw_file.read_text(encoding="utf-8"))
    if saved["status"] != "ok" or not saved["rows"]:
        return {"india": 0, "world": 0, "suppliers": {}}
    header, *records = saved["rows"]
    india = world = 0
    suppliers = {}
    for rec in records:
        r = dict(zip(header, rec))
        val = int(r.get("CON_VAL_YR") or 0)
        duty = int(r.get("CAL_DUT_YR") or 0)
        if "TOTAL FOR ALL" in (r.get("CTY_NAME") or "").upper():
            world = val
        elif r.get("SUMMARY_LVL") == "DET":
            suppliers[r.get("CTY_CODE")] = {"name": (r.get("CTY_NAME") or "").title(),
                                             "value_2025": val}
            if r.get("CTY_CODE") == INDIA:
                india = val
    return {"india": india, "world": world, "suppliers": suppliers}


def main():
    codes = load_codes()
    india_2025 = {}
    for code, level, desc in codes:
        d = census_detail(code, "2025-12")
        india_2025[code] = (d["india"] if d else 0, desc, level)

    top15 = sorted(india_2025.items(), key=lambda x: x[1][0], reverse=True)[:15]

    all_countries_needed = set()
    results = []
    for code, (india_val, desc, level) in top15:
        d2025 = census_detail(code, "2025-12")
        d2026 = census_detail(code, "2026-09")
        suppliers_2025 = d2025["suppliers"] if d2025 else {}
        suppliers_2026 = d2026["suppliers"] if d2026 else {}
        non_india = sorted(
            ((cc, info) for cc, info in suppliers_2025.items() if cc != INDIA),
            key=lambda x: x[1]["value_2025"], reverse=True)[:3]
        row = {"code": code, "description": desc, "india_2025_usd": india_val, "suppliers": []}
        for cc, info in non_india:
            all_countries_needed.add((cc, info["name"]))
            v2026 = suppliers_2026.get(cc, {}).get("value_2025", 0)  # same key name, value at 2026-09 YTD
            d2026_duty = None
            raw_file = CENSUS_DIR / f"{code}_2026-09.json"
            if raw_file.exists():
                saved = json.loads(raw_file.read_text(encoding="utf-8"))
                if saved["status"] == "ok" and saved["rows"]:
                    header, *records = saved["rows"]
                    for rec in records:
                        r = dict(zip(header, rec))
                        if r.get("CTY_CODE") == cc and r.get("SUMMARY_LVL") == "DET":
                            v26 = int(r.get("CON_VAL_YR") or 0)
                            d26 = int(r.get("CAL_DUT_YR") or 0)
                            d2026_duty = round(100 * d26 / v26, 2) if v26 else None
                            v2026 = v26
            row["suppliers"].append({
                "country_code": cc, "country_name": info["name"],
                "value_2025_usd": info["value_2025"],
                "value_2026ytd_usd": v2026,
                "actual_duty_pct_2026ytd": d2026_duty,
            })
        results.append(row)

    print("Top 15 core codes by 2025 India value, with top 3 non-India suppliers:\n")
    for row in results:
        print(f"{row['code']} ({row['description'][:50]}) - India 2025: ${row['india_2025_usd']:,}")
        for s in row["suppliers"]:
            print(f"    {s['country_name']:<20} 2025: ${s['value_2025_usd']:>14,}  "
                  f"2026 YTD: ${s['value_2026ytd_usd']:>14,}  actual duty 2026 YTD: {s['actual_duty_pct_2026ytd']}%")
        print()

    print("\nDistinct countries appearing as top-3 non-India suppliers across these 15 codes:")
    for cc, name in sorted(all_countries_needed, key=lambda x: x[1]):
        print(f"  {cc}: {name}")

    # Save for the next script
    with open(DATA_DIR / "top15_competitor_check_raw.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote data/top15_competitor_check_raw.json")


if __name__ == "__main__":
    main()
