"""
e3_build_monthly_imports.py

Phase 3, Part 2: build data/monthly_imports.csv from the raw monthly
Census files (raw/census_monthly/), for India, China, and all
countries, then analyze whether India's March-July 2025 looks
front-loaded (noticeably higher than the same months of 2024, beyond
normal growth), and show a side-by-side monthly India table.

READ-ONLY against raw/census_monthly/* and final_codes_grouped.csv.
Writes data/monthly_imports.csv (new file) only.
"""

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
MONTHLY_DIR = HERE / "raw" / "census_monthly"
INDIA, CHINA = "5330", "5700"


def load_codes():
    with open(DATA_DIR / "final_codes_grouped.csv", newline="", encoding="utf-8-sig") as f:
        return [(r["code"], r["level"]) for r in csv.DictReader(f)]


def build_months():
    months = [f"2024-{m:02d}" for m in range(1, 13)]
    months += [f"2025-{m:02d}" for m in range(1, 13)]
    months += [f"2026-{m:02d}" for m in range(1, 10)]
    return months


def month_values(code, period):
    raw_file = MONTHLY_DIR / f"{code}_{period}.json"
    if not raw_file.exists():
        return None
    saved = json.loads(raw_file.read_text(encoding="utf-8"))
    out = {"india": 0, "china": 0, "world": 0}
    if saved["status"] != "ok" or not saved["rows"]:
        return out
    header, *records = saved["rows"]
    for rec in records:
        r = dict(zip(header, rec))
        val = int(r.get("CON_VAL_MO") or 0)
        if "TOTAL FOR ALL" in (r.get("CTY_NAME") or "").upper():
            out["world"] = val
        elif r.get("CTY_CODE") == INDIA and r.get("SUMMARY_LVL") == "DET":
            out["india"] = val
        elif r.get("CTY_CODE") == CHINA and r.get("SUMMARY_LVL") == "DET":
            out["china"] = val
    return out


def main():
    codes = load_codes()
    months = build_months()

    rows = []
    monthly_totals = {m: {"india": 0, "china": 0, "world": 0} for m in months}
    for code, level in codes:
        for m in months:
            v = month_values(code, m)
            if v is None:
                continue
            rows.append({"code": code, "level": level, "month": m,
                         "india_usd": v["india"], "china_usd": v["china"], "world_usd": v["world"]})
            monthly_totals[m]["india"] += v["india"]
            monthly_totals[m]["china"] += v["china"]
            monthly_totals[m]["world"] += v["world"]

    with open(DATA_DIR / "monthly_imports.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["code", "level", "month", "india_usd", "china_usd", "world_usd"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote data/monthly_imports.csv ({len(rows)} rows)\n")

    # ---- side-by-side India monthly table ----
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    print(f"{'Month':<6}{'2024 India $':>16}{'2025 India $':>16}{'2026 India $':>16}")
    for i, mname in enumerate(month_names, start=1):
        v24 = monthly_totals.get(f"2024-{i:02d}", {}).get("india")
        v25 = monthly_totals.get(f"2025-{i:02d}", {}).get("india")
        v26 = monthly_totals.get(f"2026-{i:02d}", {}).get("india")
        c24 = f"{v24:,}" if v24 is not None else ""
        c25 = f"{v25:,}" if v25 is not None else ""
        c26 = f"{v26:,}" if v26 is not None else ""
        print(f"{mname:<6}{c24:>16}{c25:>16}{c26:>16}")

    # ---- front-loading check: March-July ----
    print("\n--- Front-loading check: March-July ---")
    mar_jul_24 = sum(monthly_totals[f"2024-{m:02d}"]["india"] for m in range(3, 8))
    mar_jul_25 = sum(monthly_totals[f"2025-{m:02d}"]["india"] for m in range(3, 8))
    yoy_mar_jul = round(100 * (mar_jul_25 - mar_jul_24) / mar_jul_24, 1) if mar_jul_24 else None
    print(f"India Mar-Jul 2024: ${mar_jul_24:,}")
    print(f"India Mar-Jul 2025: ${mar_jul_25:,}  (change: {yoy_mar_jul}%)")

    # "normal growth" baseline: full-year 2024 -> full-year-equivalent 2025 growth using Jan+Feb+Aug+Sep (months NOT in the suspected front-load window) as a control
    control_months_24 = sum(monthly_totals[f"2024-{m:02d}"]["india"] for m in (1, 2, 8, 9))
    control_months_25 = sum(monthly_totals[f"2025-{m:02d}"]["india"] for m in (1, 2, 8, 9))
    control_growth = round(100 * (control_months_25 - control_months_24) / control_months_24, 1) if control_months_24 else None
    print(f"Control (Jan+Feb+Aug+Sep, months outside the suspected window) 2024: ${control_months_24:,}")
    print(f"Control (Jan+Feb+Aug+Sep) 2025: ${control_months_25:,}  (change: {control_growth}%)")
    print(f"\n=> Mar-Jul grew {yoy_mar_jul}% vs the control months' {control_growth}% "
          f"({'ABOVE' if yoy_mar_jul is not None and control_growth is not None and yoy_mar_jul > control_growth else 'NOT above'} "
          "normal growth, suggesting "
          f"{'possible front-loading' if yoy_mar_jul is not None and control_growth is not None and yoy_mar_jul - control_growth > 10 else 'no strong front-loading signal'})")

    # per-month detail for the suspected window
    print("\nPer-month Mar-Jul detail:")
    for m in range(3, 8):
        v24 = monthly_totals[f"2024-{m:02d}"]["india"]
        v25 = monthly_totals[f"2025-{m:02d}"]["india"]
        chg = round(100 * (v25 - v24) / v24, 1) if v24 else None
        print(f"  {month_names[m-1]}: 2024=${v24:,}  2025=${v25:,}  change={chg}%")


if __name__ == "__main__":
    main()
