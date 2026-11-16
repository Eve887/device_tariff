"""
p3_backtest.py

Phase 4, Part 3: back-test the elasticity model. For each product
group, predict India's relative change in the shock months using:
    predicted_relative_change = -epsilon_group x gap_change_group
(using each group's median epsilon and median gap_change from Part 1),
and compare against the group's ACTUAL relative change (recomputed
from aggregated group-level totals, not averaged per-code percentages,
to avoid distortion from small-denominator codes).

READ-ONLY against data/phase4_elasticity.csv,
data/phase4_elasticity_by_group.csv, raw/census_monthly/*.
Writes data/phase4_backtest.csv (new file).
"""

import csv
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
MONTHLY_DIR = HERE / "raw" / "census_monthly"
INDIA = "5330"

BASELINE_MONTHS = ["2024-10", "2024-11", "2024-12", "2025-01", "2025-02", "2025-03"]
SHOCK_MONTHS = ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03"]


def monthly_india_world(code, months):
    india_val = world_val = 0
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
            if "TOTAL FOR ALL" in (r.get("CTY_NAME") or "").upper():
                world_val += val
            elif r.get("CTY_CODE") == INDIA and r.get("SUMMARY_LVL") == "DET":
                india_val += val
    return india_val, world_val


def pct_change(old, new):
    return (new - old) / old * 100 if old else None


def main():
    with open(DATA_DIR / "phase4_elasticity.csv", newline="", encoding="utf-8-sig") as f:
        code_rows = list(csv.DictReader(f))
    with open(DATA_DIR / "phase4_elasticity_by_group.csv", newline="", encoding="utf-8-sig") as f:
        group_summary = {r["group"]: r for r in csv.DictReader(f)}

    by_group_codes = {}
    for r in code_rows:
        by_group_codes.setdefault(r["group"], []).append(r["code"])

    results = []
    for group, codes in by_group_codes.items():
        gs = group_summary[group]
        median_epsilon = float(gs["median_epsilon"])
        gap_changes = [float(r["gap_change_pp"]) for r in code_rows if r["group"] == group]
        median_gap_change = statistics.median(gap_changes)
        predicted_relative_change = -median_epsilon * median_gap_change

        i_val_b, w_val_b = monthly_india_world_group(codes, BASELINE_MONTHS)
        i_val_s, w_val_s = monthly_india_world_group(codes, SHOCK_MONTHS)
        o_val_b, o_val_s = w_val_b - i_val_b, w_val_s - i_val_s
        india_pct = pct_change(i_val_b, i_val_s)
        others_pct = pct_change(o_val_b, o_val_s)
        actual_relative_change = (india_pct - others_pct) if (india_pct is not None and others_pct is not None) else None

        error = (predicted_relative_change - actual_relative_change) if actual_relative_change is not None else None
        results.append({
            "group": group, "n_codes": len(codes),
            "median_epsilon": round(median_epsilon, 3),
            "median_gap_change_pp": round(median_gap_change, 2),
            "predicted_relative_change_pct": round(predicted_relative_change, 2),
            "actual_relative_change_pct": round(actual_relative_change, 2) if actual_relative_change is not None else None,
            "error_pct_points": round(error, 2) if error is not None else None,
        })

    with open(DATA_DIR / "phase4_backtest.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    print(f"Wrote data/phase4_backtest.csv ({len(results)} rows)\n")
    print(f"{'Group':<22}{'n':>4}{'predicted %':>14}{'actual %':>12}{'error (pp)':>12}")
    errors = []
    for r in results:
        print(f"{r['group']:<22}{r['n_codes']:>4}{r['predicted_relative_change_pct']:>14}"
              f"{r['actual_relative_change_pct']:>12}{r['error_pct_points']:>12}")
        if r["error_pct_points"] is not None:
            errors.append(abs(r["error_pct_points"]))
    if errors:
        print(f"\nOverall mean absolute error: {round(statistics.mean(errors), 2)} percentage points "
              f"(across {len(errors)} groups)")


def monthly_india_world_group(codes, months):
    total_india = total_world = 0
    for code in codes:
        i, w = monthly_india_world(code, months)
        total_india += i
        total_world += w
    return total_india, total_world


if __name__ == "__main__":
    main()
