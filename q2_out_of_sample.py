"""
q2_out_of_sample.py

Phase 4 fix 2: out-of-sample test. The tier epsilons from Fix 1 were
estimated on Oct 2025-Mar 2026 (shock) vs Oct 2024-Mar 2025 (baseline).
This tests them on a DIFFERENT window: Apr-Sep 2026 (new "shock") vs
Apr-Sep 2024 (new "baseline") - a genuine out-of-sample test since
neither period was used to fit epsilon.

predicted_relative_change = -epsilon_tier_base x gap_change_new_period
(gap_change computed fresh for this new period, same aggregate method
as Fix 1, using the SAME qualifying codes identified in Fix 1 for each
tier - the parameter is out-of-sample, the code membership is not re-
selected).

naive benchmark: predicted = 0 (India moves exactly with the market).

"Persistent loss": if actual fell further than predicted (model UNDER-
predicted the damage), the extra shortfall - the gap between what the
model expected and what really happened - converted to dollars using
the tier's India baseline value in this new period, is reported as a
proxy for buyers who switched away and did not come back within the
window measured.

READ-ONLY against data/phase4_tier_epsilon_v2.csv, core_device_codes.csv,
final_codes_grouped.csv, raw/census_monthly/*. Writes
data/phase4_out_of_sample_v2.csv (new file).
"""

import csv
from pathlib import Path

from q1_tier_epsilon import aggregate_epsilon, monthly_india_world

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

NEW_BASELINE_MONTHS = [f"2024-{m:02d}" for m in range(4, 10)]  # Apr-Sep 2024
NEW_SHOCK_MONTHS = [f"2026-{m:02d}" for m in range(4, 10)]     # Apr-Sep 2026


def main():
    with open(DATA_DIR / "phase4_tier_epsilon_v2.csv", newline="", encoding="utf-8-sig") as f:
        tier_eps = {r["tier"]: r for r in csv.DictReader(f)}

    rows = []
    for tier_name, tier_row in tier_eps.items():
        if tier_name.startswith("POOLED"):
            continue
        codes = tier_row["codes"].split(";")
        epsilon_base = float(tier_row["epsilon_base_median"])

        result = aggregate_epsilon(codes, NEW_BASELINE_MONTHS, NEW_SHOCK_MONTHS)
        if result is None:
            print(f"{tier_name}: cannot compute out-of-sample test (insufficient data)")
            continue
        eps_unused, actual_relative_change, gap_change_new, gap_b_new, gap_s_new = result

        predicted_relative_change = -epsilon_base * gap_change_new
        error = predicted_relative_change - actual_relative_change
        naive_predicted = 0.0
        naive_error = naive_predicted - actual_relative_change
        model_beats_naive = abs(error) < abs(naive_error)

        # persistent loss: only when actual is WORSE (more negative) than predicted
        india_baseline_val = sum(monthly_india_world(c, NEW_BASELINE_MONTHS)[0] for c in codes)
        persistent_loss_usd = None
        if actual_relative_change < predicted_relative_change:
            shortfall_pct = predicted_relative_change - actual_relative_change
            persistent_loss_usd = round(india_baseline_val * shortfall_pct / 100)

        rows.append({
            "tier": tier_name, "n_codes": len(codes),
            "gap_change_new_period_pp": round(gap_change_new, 2),
            "epsilon_used_from_fix1_base": epsilon_base,
            "predicted_relative_change_pct": round(predicted_relative_change, 2),
            "actual_relative_change_pct": round(actual_relative_change, 2),
            "model_error_pp": round(error, 2),
            "naive_predicted_pct": naive_predicted,
            "naive_error_pp": round(naive_error, 2),
            "model_beats_naive": model_beats_naive,
            "india_baseline_usd_this_period": india_baseline_val,
            "persistent_loss_usd": persistent_loss_usd,
        })

    with open(DATA_DIR / "phase4_out_of_sample_v2.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote data/phase4_out_of_sample_v2.csv ({len(rows)} rows)\n")
    print(f"{'Tier':<32}{'predicted %':>13}{'actual %':>11}{'model err':>11}{'naive err':>11}  beats naive?")
    for r in rows:
        print(f"{r['tier']:<32}{r['predicted_relative_change_pct']:>13}{r['actual_relative_change_pct']:>11}"
              f"{r['model_error_pp']:>11}{r['naive_error_pp']:>11}  {r['model_beats_naive']}")
        if r["persistent_loss_usd"]:
            print(f"    -> persistent loss: ${r['persistent_loss_usd']:,}")


if __name__ == "__main__":
    main()
