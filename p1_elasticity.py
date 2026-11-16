"""
p1_elasticity.py

Phase 4, Part 1: measure elasticity (epsilon) of switching away from
India as India's tariff rises, per product group.

Baseline months: Oct 2024 - Mar 2025. Shock months: Oct 2025 - Mar 2026.
For each code:
    relative_change = india_pct_change - others_pct_change   (shock vs baseline)
    gap_change = (india_duty_pct - others_duty_pct) in shock
                 minus the same difference in baseline, in points
    epsilon = -relative_change / gap_change

Excludes codes where India sold under $1M in 2025, or |gap_change| < 2
points (reported separately as "too small a gap to use", not dropped
silently).

READ-ONLY against core_device_codes.csv, final_codes_grouped.csv,
raw/census_monthly/*, raw/census/* (for 2025 full-year India value).
Writes data/phase4_elasticity.csv (new file) and prints the per-group
summary.
"""

import csv
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
MONTHLY_DIR = HERE / "raw" / "census_monthly"
CENSUS_DIR = HERE / "raw" / "census"
INDIA = "5330"

BASELINE_MONTHS = ["2024-10", "2024-11", "2024-12", "2025-01", "2025-02", "2025-03"]
SHOCK_MONTHS = ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03"]


def load_codes():
    with open(DATA_DIR / "core_device_codes.csv", newline="", encoding="utf-8-sig") as f:
        return [(r["code"], r["level"], r["description"]) for r in csv.DictReader(f)]


def load_groups():
    with open(DATA_DIR / "final_codes_grouped.csv", newline="", encoding="utf-8-sig") as f:
        return {r["code"]: r["group"] for r in csv.DictReader(f)}


def india_2025_value(code):
    raw_file = CENSUS_DIR / f"{code}_2025-12.json"
    if not raw_file.exists():
        return 0
    saved = json.loads(raw_file.read_text(encoding="utf-8"))
    if saved["status"] != "ok" or not saved["rows"]:
        return 0
    header, *records = saved["rows"]
    for rec in records:
        r = dict(zip(header, rec))
        if r.get("CTY_CODE") == INDIA and r.get("SUMMARY_LVL") == "DET":
            return int(r.get("CON_VAL_YR") or 0)
    return 0


def monthly_india_world(code, months):
    india_val = india_duty = world_val = world_duty = 0
    for m in months:
        raw_file = MONTHLY_DIR / f"{code}_{m}.json"
        if not raw_file.exists():
            continue
        saved = json.loads(raw_file.read_text(encoding="utf-8"))
        if saved["status"] != "ok" or not saved["rows"]:
            continue
        header, *records = saved["rows"]
        for rec in records:
            r = dict(zip(header, rec))
            val = int(r.get("CON_VAL_MO") or 0)
            duty = int(r.get("CAL_DUT_MO") or 0)
            if "TOTAL FOR ALL" in (r.get("CTY_NAME") or "").upper():
                world_val += val
                world_duty += duty
            elif r.get("CTY_CODE") == INDIA and r.get("SUMMARY_LVL") == "DET":
                india_val += val
                india_duty += duty
    return india_val, india_duty, world_val, world_duty


def pct_change(old, new):
    return (new - old) / old * 100 if old else None


def main():
    codes = load_codes()
    groups = load_groups()
    rows = []
    excluded_small_india = []
    excluded_small_gap = []

    for code, level, desc in codes:
        india_2025 = india_2025_value(code)
        i_val_b, i_duty_b, w_val_b, w_duty_b = monthly_india_world(code, BASELINE_MONTHS)
        i_val_s, i_duty_s, w_val_s, w_duty_s = monthly_india_world(code, SHOCK_MONTHS)
        o_val_b, o_duty_b = w_val_b - i_val_b, w_duty_b - i_duty_b
        o_val_s, o_duty_s = w_val_s - i_val_s, w_duty_s - i_duty_s

        if india_2025 < 1_000_000:
            excluded_small_india.append(code)
            continue

        india_pct = pct_change(i_val_b, i_val_s)
        others_pct = pct_change(o_val_b, o_val_s)
        if india_pct is None or others_pct is None:
            continue
        relative_change = india_pct - others_pct

        india_duty_pct_b = (i_duty_b / i_val_b * 100) if i_val_b else None
        others_duty_pct_b = (o_duty_b / o_val_b * 100) if o_val_b else None
        india_duty_pct_s = (i_duty_s / i_val_s * 100) if i_val_s else None
        others_duty_pct_s = (o_duty_s / o_val_s * 100) if o_val_s else None
        if None in (india_duty_pct_b, others_duty_pct_b, india_duty_pct_s, others_duty_pct_s):
            continue
        gap_b = india_duty_pct_b - others_duty_pct_b
        gap_s = india_duty_pct_s - others_duty_pct_s
        gap_change = gap_s - gap_b

        if abs(gap_change) < 2:
            excluded_small_gap.append(code)
            continue

        epsilon = -relative_change / gap_change
        rows.append({
            "code": code, "description": desc, "group": groups.get(code, "Unknown"),
            "india_2025_usd": india_2025,
            "india_pct_change": round(india_pct, 2), "others_pct_change": round(others_pct, 2),
            "relative_change": round(relative_change, 2),
            "gap_baseline_pp": round(gap_b, 2), "gap_shock_pp": round(gap_s, 2),
            "gap_change_pp": round(gap_change, 2), "epsilon": round(epsilon, 3),
        })

    with open(DATA_DIR / "phase4_elasticity.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote data/phase4_elasticity.csv ({len(rows)} rows)")
    print(f"Excluded (India < $1M in 2025): {len(excluded_small_india)} codes: {excluded_small_india}")
    print(f"Excluded (|gap_change| < 2pp): {len(excluded_small_gap)} codes: {excluded_small_gap}")

    by_group = {}
    for r in rows:
        by_group.setdefault(r["group"], []).append(r)

    print(f"\n{'Group':<22}{'n':>4}{'median eps':>12}{'p25':>10}{'p75':>10}{'2025 India $':>16}  confidence")
    group_summary = []
    for g, glist in by_group.items():
        eps = sorted(r["epsilon"] for r in glist)
        n = len(eps)
        median_eps = statistics.median(eps)
        p25 = eps[max(0, int(0.25 * (n - 1)))]
        p75 = eps[min(n - 1, int(0.75 * (n - 1)))]
        total_india_2025 = sum(r["india_2025_usd"] for r in glist)
        confidence = "LOW CONFIDENCE" if n < 3 else ""
        group_summary.append({"group": g, "n": n, "median_epsilon": round(median_eps, 3),
                               "p25_epsilon": round(p25, 3), "p75_epsilon": round(p75, 3),
                               "india_2025_usd": total_india_2025, "low_confidence": bool(n < 3)})
        print(f"{g:<22}{n:>4}{median_eps:>12.3f}{p25:>10.3f}{p75:>10.3f}{total_india_2025:>16,}  {confidence}")

    with open(DATA_DIR / "phase4_elasticity_by_group.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(group_summary[0].keys()))
        w.writeheader()
        w.writerows(group_summary)
    print("\nWrote data/phase4_elasticity_by_group.csv")


if __name__ == "__main__":
    main()
