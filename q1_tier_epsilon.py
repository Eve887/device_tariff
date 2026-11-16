"""
q1_tier_epsilon.py

Phase 4 fix 1: re-estimate epsilon by TIER (not small product group),
using the AGGREGATE method - sum dollars across a tier's qualifying
codes first, then compute one relative_change/gap_change/epsilon for
the whole tier. This avoids the small-base percentage-change blowup
that distorted the Implants group (via code 902190) in the first pass.

Tiers:
  A (simple disposables): Consumables, Dressings & Sutures, Gloves
  B (equipment): Electro-diagnostic, Imaging, Instruments,
                 Respiratory & Therapy, Ophthalmic, Furniture, Other
  C (implants and dental): Implants, Dental

A code qualifies for a tier's aggregate if its India value in the
BASELINE months alone (Oct 2024 - Mar 2025) is >= $1M - a different,
narrower test than Phase 4 v1's "$1M in 2025 full year."

epsilon_tier = -relative_change / gap_change, floored at 0, capped at 5.
Bootstrap: resample the tier's qualifying codes with replacement 1000
times, recompute epsilon_tier (same floor/cap) each time; report
median/p25/p75 of the bootstrap distribution as base/low/high.

Also computes one POOLED epsilon across all 60 core codes the same way,
as a check.

READ-ONLY against core_device_codes.csv, final_codes_grouped.csv,
raw/census_monthly/*. Writes data/phase4_tier_epsilon_v2.csv (new file).
"""

import csv
import json
import random
import statistics
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
MONTHLY_DIR = HERE / "raw" / "census_monthly"
INDIA = "5330"

BASELINE_MONTHS = ["2024-10", "2024-11", "2024-12", "2025-01", "2025-02", "2025-03"]
SHOCK_MONTHS = ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03"]

TIERS = {
    "Tier A (simple disposables)": {"Consumables", "Dressings & Sutures", "Gloves"},
    "Tier B (equipment)": {"Electro-diagnostic", "Imaging", "Instruments",
                            "Respiratory & Therapy", "Ophthalmic", "Furniture", "Other"},
    "Tier C (implants and dental)": {"Implants", "Dental"},
}

random.seed(20261115)  # reproducible bootstrap


def load_codes():
    with open(DATA_DIR / "core_device_codes.csv", newline="", encoding="utf-8-sig") as f:
        return [(r["code"], r["level"]) for r in csv.DictReader(f)]


def load_groups():
    with open(DATA_DIR / "final_codes_grouped.csv", newline="", encoding="utf-8-sig") as f:
        return {r["code"]: r["group"] for r in csv.DictReader(f)}


_cache = {}


def monthly_india_world(code, months):
    key = (code, tuple(months))
    if key in _cache:
        return _cache[key]
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
    result = (india_val, india_duty, world_val, world_duty)
    _cache[key] = result
    return result


def pct_change(old, new):
    return (new - old) / old * 100 if old else None


def aggregate_epsilon(codes, baseline_months=BASELINE_MONTHS, shock_months=SHOCK_MONTHS):
    """codes: list of hs6/hs10 codes. Returns (epsilon_raw_unclamped, relative_change,
    gap_change, gap_baseline, gap_shock) or None if not computable."""
    i_val_b = i_duty_b = w_val_b = w_duty_b = 0
    i_val_s = i_duty_s = w_val_s = w_duty_s = 0
    for code in codes:
        a = monthly_india_world(code, baseline_months)
        b = monthly_india_world(code, shock_months)
        i_val_b += a[0]; i_duty_b += a[1]; w_val_b += a[2]; w_duty_b += a[3]
        i_val_s += b[0]; i_duty_s += b[1]; w_val_s += b[2]; w_duty_s += b[3]
    o_val_b, o_duty_b = w_val_b - i_val_b, w_duty_b - i_duty_b
    o_val_s, o_duty_s = w_val_s - i_val_s, w_duty_s - i_duty_s

    india_pct = pct_change(i_val_b, i_val_s)
    others_pct = pct_change(o_val_b, o_val_s)
    if india_pct is None or others_pct is None:
        return None
    relative_change = india_pct - others_pct

    india_duty_pct_b = (i_duty_b / i_val_b * 100) if i_val_b else None
    others_duty_pct_b = (o_duty_b / o_val_b * 100) if o_val_b else None
    india_duty_pct_s = (i_duty_s / i_val_s * 100) if i_val_s else None
    others_duty_pct_s = (o_duty_s / o_val_s * 100) if o_val_s else None
    if None in (india_duty_pct_b, others_duty_pct_b, india_duty_pct_s, others_duty_pct_s):
        return None
    gap_b = india_duty_pct_b - others_duty_pct_b
    gap_s = india_duty_pct_s - others_duty_pct_s
    gap_change = gap_s - gap_b
    if gap_change == 0:
        return None

    epsilon = -relative_change / gap_change
    return epsilon, relative_change, gap_change, gap_b, gap_s


def clamp(eps):
    return max(0.0, min(5.0, eps))


def qualifying_codes(all_codes):
    """Codes with India baseline (Oct24-Mar25) value >= $1M."""
    out = []
    for code, level in all_codes:
        india_val_b, *_ = monthly_india_world(code, BASELINE_MONTHS)
        if india_val_b >= 1_000_000:
            out.append(code)
    return out, {code: monthly_india_world(code, BASELINE_MONTHS)[0] for code, level in all_codes}


def bootstrap_epsilon(codes, n=1000):
    draws = []
    k = len(codes)
    for _ in range(n):
        sample = [random.choice(codes) for _ in range(k)]
        result = aggregate_epsilon(sample)
        if result is not None:
            draws.append(clamp(result[0]))
    return draws


def main():
    all_codes = load_codes()
    groups = load_groups()

    tier_of_group = {}
    for tier, grouplist in TIERS.items():
        for g in grouplist:
            tier_of_group[g] = tier

    codes_by_tier = defaultdict(list)
    for code, level in all_codes:
        g = groups.get(code, "Unknown")
        t = tier_of_group.get(g)
        if t:
            codes_by_tier[t].append(code)

    all_qualifying, india_baseline_vals = qualifying_codes(all_codes)

    results = []
    for tier, codes_in_tier in list(codes_by_tier.items()) + [("POOLED (all tiers)", [c for c, l in all_codes])]:
        qualifying = [c for c in codes_in_tier if c in all_qualifying]
        point_result = aggregate_epsilon(qualifying)
        if point_result is None:
            print(f"{tier}: cannot compute (n={len(qualifying)}) - skipping")
            continue
        eps_point, rel_change, gap_change, gap_b, gap_s = point_result
        eps_point_clamped = clamp(eps_point)

        draws = bootstrap_epsilon(qualifying, n=1000)
        if not draws:
            print(f"{tier}: bootstrap produced no usable draws - skipping")
            continue
        draws.sort()
        n_d = len(draws)
        median_eps = statistics.median(draws)
        p25 = draws[max(0, int(0.25 * (n_d - 1)))]
        p75 = draws[min(n_d - 1, int(0.75 * (n_d - 1)))]

        results.append({
            "tier": tier, "n_codes": len(qualifying), "codes": ";".join(qualifying),
            "relative_change_pct": round(rel_change, 2),
            "gap_baseline_pp": round(gap_b, 2), "gap_shock_pp": round(gap_s, 2),
            "gap_change_pp": round(gap_change, 2),
            "epsilon_point_estimate": round(eps_point_clamped, 3),
            "epsilon_low_p25": round(p25, 3), "epsilon_base_median": round(median_eps, 3),
            "epsilon_high_p75": round(p75, 3),
            "n_bootstrap_draws_used": n_d,
        })

    with open(DATA_DIR / "phase4_tier_epsilon_v2.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=[k for k in results[0].keys() if k != "codes"] + ["codes"])
        w.writeheader()
        w.writerows(results)

    print(f"Wrote data/phase4_tier_epsilon_v2.csv ({len(results)} rows)\n")
    print(f"{'Tier':<32}{'n':>4}{'low':>8}{'base':>8}{'high':>8}{'gap_chg(pp)':>13}")
    for r in results:
        print(f"{r['tier']:<32}{r['n_codes']:>4}{r['epsilon_low_p25']:>8}{r['epsilon_base_median']:>8}"
              f"{r['epsilon_high_p75']:>8}{r['gap_change_pp']:>13}")


if __name__ == "__main__":
    main()
