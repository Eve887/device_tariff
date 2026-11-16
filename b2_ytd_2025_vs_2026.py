"""
b2_ytd_2025_vs_2026.py

Investigation B2: like-for-like YTD comparison, Jan-Sep 2025 vs Jan-Sep
2026, for India, China, Mexico, and all countries (world total),
per HS6 code and in total.

READ-ONLY: reads raw/census/<hs6>_2025-09.json (from b1_census_ytd2025.py)
and raw/census/<hs6>_2026-09.json (already downloaded by step1, since
2026-09 was its "latest 2026 month"). Does not modify any existing file.

OUTPUT: data/ytd_2025_vs_2026.csv (new file).
"""

import json
from pathlib import Path

from common import DATA_DIR, RAW_DIR, read_codes, write_csv

OUT_DIR = RAW_DIR / "census"
PERIOD_2025 = "2025-09"
PERIOD_2026 = "2026-09"
COUNTRIES = {"5330": "India", "5700": "China", "2010": "Mexico"}


def load_period(hs6, period):
    """Return dict: group_label -> (imports_for_consumption_usd, calculated_duty_usd)."""
    raw_file = OUT_DIR / f"{hs6}_{period}.json"
    out = {}
    if not raw_file.exists():
        return out
    saved = json.loads(raw_file.read_text(encoding="utf-8"))
    if saved["status"] != "ok" or not saved["rows"]:
        return out
    header, *records = saved["rows"]
    for rec in records:
        r = dict(zip(header, rec))
        con_val = int(r.get("CON_VAL_YR") or 0)
        duty = int(r.get("CAL_DUT_YR") or 0)
        if "TOTAL FOR ALL" in (r.get("CTY_NAME") or "").upper():
            out["All countries"] = (con_val, duty)
        elif r.get("CTY_CODE") in COUNTRIES and r.get("SUMMARY_LVL") == "DET":
            out[COUNTRIES[r["CTY_CODE"]]] = (con_val, duty)
    return out


def pct_change(old, new):
    return round(100 * (new - old) / old, 1) if old else ""


def duty_pct(duty, val):
    return round(100 * duty / val, 2) if val else ""


def main():
    codes = read_codes()
    rows = []
    totals = {g: [0, 0, 0, 0] for g in ("India", "China", "Mexico", "All countries")}
    # totals[g] = [val_2025, duty_2025, val_2026, duty_2026]

    for code in codes:
        hs6 = code["hs6"]
        p2025 = load_period(hs6, PERIOD_2025)
        p2026 = load_period(hs6, PERIOD_2026)
        for group in ("India", "China", "Mexico", "All countries"):
            v25, d25 = p2025.get(group, (0, 0))
            v26, d26 = p2026.get(group, (0, 0))
            totals[group][0] += v25
            totals[group][1] += d25
            totals[group][2] += v26
            totals[group][3] += d26
            rows.append({
                "hs6": hs6,
                "group": code["group"],
                "description": code["description"],
                "country_group": group,
                "jan_sep_2025_imports_usd": v25,
                "jan_sep_2025_duty_usd": d25,
                "jan_sep_2025_duty_pct": duty_pct(d25, v25),
                "jan_sep_2026_imports_usd": v26,
                "jan_sep_2026_duty_usd": d26,
                "jan_sep_2026_duty_pct": duty_pct(d26, v26),
                "pct_change_imports": pct_change(v25, v26),
            })

    # Add 4 grand-total rows (one per country group, across all 61 codes)
    for group in ("India", "China", "Mexico", "All countries"):
        v25, d25, v26, d26 = totals[group]
        rows.append({
            "hs6": "TOTAL", "group": "", "description": "All 61 codes combined",
            "country_group": group,
            "jan_sep_2025_imports_usd": v25,
            "jan_sep_2025_duty_usd": d25,
            "jan_sep_2025_duty_pct": duty_pct(d25, v25),
            "jan_sep_2026_imports_usd": v26,
            "jan_sep_2026_duty_usd": d26,
            "jan_sep_2026_duty_pct": duty_pct(d26, v26),
            "pct_change_imports": pct_change(v25, v26),
        })

    columns = list(rows[0].keys())
    write_csv(DATA_DIR / "ytd_2025_vs_2026.csv", rows, columns)
    print(f"Wrote data/ytd_2025_vs_2026.csv ({len(rows)} rows)")
    print()
    print(f"{'country_group':<14}{'2025 YTD $':>16}{'2026 YTD $':>16}{'% change':>10}{'2025 duty %':>13}{'2026 duty %':>13}")
    for group in ("India", "China", "Mexico", "All countries"):
        v25, d25, v26, d26 = totals[group]
        print(f"{group:<14}{v25:>16,}{v26:>16,}{pct_change(v25, v26):>10}"
              f"{duty_pct(d25, v25):>13}{duty_pct(d26, v26):>13}")


if __name__ == "__main__":
    main()
