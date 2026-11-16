"""
q4_rerun_scenarios.py

Phase 4 fix 4: re-run the Totals table and exposure score using Fix 1's
tier epsilons (data/phase4_tier_epsilon_v2.csv) in place of the old
per-group epsilon, and Fix 3's measured alpha
(data/phase4_alpha_hs10_summary_v2.csv) in place of the 0.3/0.45/0.6
fallback. Scenario deltas themselves (delta_t, delta_g per code) are
unchanged from data/phase4_scenarios.csv - only the epsilon and alpha
parameters feeding the revenue-at-risk formula change.

    revenue_at_risk = E x [alpha x delta_t + epsilon x (1-alpha) x delta_g]
    low  = alpha_low  x epsilon_low   (tier)
    base = alpha_base x epsilon_base  (tier)
    high = alpha_high x epsilon_high  (tier)

Also runs the sanity check the user asked for: low <= base <= high for
every scenario row, and (for S5 specifically) that the sign of the
gain is the same in low/base/high. Because Fix 3's measured alpha
includes a NEGATIVE low value (-1.292) - already flagged as unstable -
this pairing is not guaranteed to be monotonic, so failures are
expected and are reported explicitly, not silently patched.

Exposure score is restricted to codes with >= $1M India value in 2025
(scenario S0's E_2025_full_year_usd), re-uses the same five weighted
components as p6 but swaps "ease of switching" from the old per-group
median epsilon to the code's new tier base epsilon, and adds two new
columns: E_2025_full_year_musd and base_S2_rar_musd.

READ-ONLY against data/phase4_scenarios.csv, data/phase4_tier_epsilon_v2.csv,
data/phase4_alpha_hs10_summary_v2.csv, data/final_codes_grouped.csv,
core_device_codes.csv, data/india_trade*.csv, raw/census/*,
raw/census_monthly/*. Writes data/phase4_revenue_at_risk_v2.csv,
data/phase4_revenue_at_risk_totals_v2.csv,
data/phase4_monotonicity_check_v2.csv, data/phase4_exposure_score_v2.csv
(new files).
"""

import csv
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
CENSUS_DIR = HERE / "raw" / "census"
MONTHLY_DIR = HERE / "raw" / "census_monthly"
INDIA = "5330"

LATEST_12MO = [f"2025-{m:02d}" for m in (10, 11, 12)] + [f"2026-{m:02d}" for m in range(1, 10)]

TIERS = {
    "Tier A (simple disposables)": {"Consumables", "Dressings & Sutures", "Gloves"},
    "Tier B (equipment)": {"Electro-diagnostic", "Imaging", "Instruments",
                            "Respiratory & Therapy", "Ophthalmic", "Furniture", "Other"},
    "Tier C (implants and dental)": {"Implants", "Dental"},
}

SEC232_NAMED = {
    "300510": True, "300590": True, "300610": True, "300620": True, "300640": False,
    "300650": False, "300691": False, "382211": True, "382212": True, "382213": True,
    "401410": False, "401512": True, "6210105010": True, "6210105090": True,
    "842310": False, "900130": False, "900150": False,
    "901811": True, "901812": True, "901813": True, "901814": True, "901819": True, "901820": True,
    "901831": True, "901832": True, "901839": True, "901841": False, "901849": False,
    "901850": False, "901890": True, "901910": False, "901920": True, "902000": True,
    "902110": True, "902121": False, "902129": False, "902131": True, "902139": True,
    "902140": True, "902150": True, "902190": True, "902212": True, "902213": True,
    "902214": True, "902219": True, "902221": True, "902229": True, "902230": True,
    "902290": True, "902511": False, "9025198010": False, "9025198020": False,
    "902710": False, "902720": False, "902730": False, "902750": False, "902790": False,
    "940210": False, "9402100000": False, "940290": True,
}


def load_codes():
    with open(DATA_DIR / "core_device_codes.csv", newline="", encoding="utf-8-sig") as f:
        return [(r["code"], r["level"], r["description"]) for r in csv.DictReader(f)]


def load_groups():
    with open(DATA_DIR / "final_codes_grouped.csv", newline="", encoding="utf-8-sig") as f:
        return {r["code"]: r["group"] for r in csv.DictReader(f)}


def load_tier_epsilon():
    with open(DATA_DIR / "phase4_tier_epsilon_v2.csv", newline="", encoding="utf-8-sig") as f:
        rows = {r["tier"]: r for r in csv.DictReader(f)}
    tier_eps = {}
    for tier, r in rows.items():
        if tier.startswith("POOLED"):
            continue
        tier_eps[tier] = {
            "low": float(r["epsilon_low_p25"]),
            "base": float(r["epsilon_base_median"]),
            "high": float(r["epsilon_high_p75"]),
        }
    return tier_eps


def load_alpha():
    with open(DATA_DIR / "phase4_alpha_hs10_summary_v2.csv", newline="", encoding="utf-8-sig") as f:
        rows = {r["tier"]: float(r["alpha"]) for r in csv.DictReader(f)}
    return rows  # keys: low, base, high


def e_2025_full_year(code):
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


def e_latest_12mo(code):
    total = 0
    for m in LATEST_12MO:
        raw_file = MONTHLY_DIR / f"{code}_{m}.json"
        if not raw_file.exists():
            continue
        saved = json.loads(raw_file.read_text(encoding="utf-8"))
        if saved["status"] != "ok" or not saved["rows"]:
            continue
        header, *records = saved["rows"]
        for rec in records:
            r = dict(zip(header, rec))
            if r.get("CTY_CODE") == INDIA and r.get("SUMMARY_LVL") == "DET":
                total += int(r.get("CON_VAL_MO") or 0)
    return total


def main():
    groups = load_groups()
    tier_eps = load_tier_epsilon()
    alpha = load_alpha()

    tier_of_group = {}
    for tier, grouplist in TIERS.items():
        for g in grouplist:
            tier_of_group[g] = tier

    with open(DATA_DIR / "phase4_scenarios.csv", newline="", encoding="utf-8-sig") as f:
        scen_rows = list(csv.DictReader(f))

    e_cache_2025, e_cache_12mo = {}, {}
    out_rows = []
    skipped_no_tier = set()
    for r in scen_rows:
        code = r["code"]
        if code not in e_cache_2025:
            e_cache_2025[code] = e_2025_full_year(code)
            e_cache_12mo[code] = e_latest_12mo(code)
        e_2025 = e_cache_2025[code]
        e_12mo = e_cache_12mo[code]

        group = groups.get(code, "Unknown")
        tier = tier_of_group.get(group)
        if tier is None:
            skipped_no_tier.add(code)
            continue
        eps = tier_eps[tier]

        delta_t = float(r["delta_t_pp"]) / 100
        delta_g = float(r["delta_g_pp"]) / 100

        def rar(E, a, e):
            return E * (a * delta_t + e * (1 - a) * delta_g)

        rar_2025 = {k: rar(e_2025, alpha[k], eps[k]) for k in ("low", "base", "high")}
        rar_12mo = {k: rar(e_12mo, alpha[k], eps[k]) for k in ("low", "base", "high")}

        out_rows.append({
            "code": code, "description": r["description"], "group": group, "tier": tier,
            "scenario": r["scenario"], "scenario_year": r["scenario_year"],
            "delta_t_pp": r["delta_t_pp"], "delta_g_pp": r["delta_g_pp"],
            "E_2025_full_year_usd": e_2025, "E_latest_12mo_usd": e_12mo,
            "rar_2025_low_usd": round(rar_2025["low"]),
            "rar_2025_base_usd": round(rar_2025["base"]),
            "rar_2025_high_usd": round(rar_2025["high"]),
            "rar_12mo_low_usd": round(rar_12mo["low"]),
            "rar_12mo_base_usd": round(rar_12mo["base"]),
            "rar_12mo_high_usd": round(rar_12mo["high"]),
        })

    with open(DATA_DIR / "phase4_revenue_at_risk_v2.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print(f"Wrote data/phase4_revenue_at_risk_v2.csv ({len(out_rows)} rows)")
    if skipped_no_tier:
        print(f"Codes skipped (no tier mapping): {sorted(skipped_no_tier)}")

    # ---- totals by scenario (+ year) ----
    totals = defaultdict(lambda: defaultdict(float))
    seen_codes = set()
    overall_e_2025 = overall_e_12mo = 0
    for row in out_rows:
        key = (row["scenario"], row["scenario_year"] or "")
        for tier_lbl in ("low", "base", "high"):
            totals[key][f"rar_2025_{tier_lbl}"] += row[f"rar_2025_{tier_lbl}_usd"]
            totals[key][f"rar_12mo_{tier_lbl}"] += row[f"rar_12mo_{tier_lbl}_usd"]
        totals[key]["E_2025"] += row["E_2025_full_year_usd"]
        totals[key]["E_12mo"] += row["E_latest_12mo_usd"]
        if row["code"] not in seen_codes:
            seen_codes.add(row["code"])
            overall_e_2025 += row["E_2025_full_year_usd"]
            overall_e_12mo += row["E_latest_12mo_usd"]

    total_rows = []
    for (scen, year), vals in totals.items():
        e2025, e12mo = vals["E_2025"], vals["E_12mo"]
        total_rows.append({
            "scenario": scen, "scenario_year": year,
            "E_2025_full_year_usd": round(e2025),
            "rar_2025_low_usd": round(vals["rar_2025_low"]),
            "rar_2025_base_usd": round(vals["rar_2025_base"]),
            "rar_2025_high_usd": round(vals["rar_2025_high"]),
            "rar_2025_low_pct": round(100 * vals["rar_2025_low"] / e2025, 2) if e2025 else None,
            "rar_2025_base_pct": round(100 * vals["rar_2025_base"] / e2025, 2) if e2025 else None,
            "rar_2025_high_pct": round(100 * vals["rar_2025_high"] / e2025, 2) if e2025 else None,
            "E_12mo_usd": round(e12mo),
            "rar_12mo_low_usd": round(vals["rar_12mo_low"]),
            "rar_12mo_base_usd": round(vals["rar_12mo_base"]),
            "rar_12mo_high_usd": round(vals["rar_12mo_high"]),
            "rar_12mo_low_pct": round(100 * vals["rar_12mo_low"] / e12mo, 2) if e12mo else None,
            "rar_12mo_base_pct": round(100 * vals["rar_12mo_base"] / e12mo, 2) if e12mo else None,
            "rar_12mo_high_pct": round(100 * vals["rar_12mo_high"] / e12mo, 2) if e12mo else None,
        })

    with open(DATA_DIR / "phase4_revenue_at_risk_totals_v2.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(total_rows[0].keys()))
        w.writeheader()
        w.writerows(total_rows)
    print(f"Wrote data/phase4_revenue_at_risk_totals_v2.csv ({len(total_rows)} rows)")

    # ---- monotonicity sanity check ----
    check_rows = []
    n_fail_order, n_fail_s5_sign = 0, 0
    for r in total_rows:
        for basis in ("2025", "12mo"):
            lo, ba, hi = r[f"rar_{basis}_low_usd"], r[f"rar_{basis}_base_usd"], r[f"rar_{basis}_high_usd"]
            order_ok = lo <= ba <= hi
            if not order_ok:
                n_fail_order += 1
            s5_sign_ok = None
            if r["scenario"] == "S5_India_deal_minus10":
                signs = {1 if v > 0 else (-1 if v < 0 else 0) for v in (lo, ba, hi)}
                s5_sign_ok = len(signs) == 1
                if not s5_sign_ok:
                    n_fail_s5_sign += 1
            check_rows.append({
                "scenario": r["scenario"], "scenario_year": r["scenario_year"], "basis": basis,
                "low_usd": lo, "base_usd": ba, "high_usd": hi,
                "low_le_base_le_high": order_ok,
                "s5_same_direction_all_three": s5_sign_ok,
            })

    with open(DATA_DIR / "phase4_monotonicity_check_v2.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(check_rows[0].keys()))
        w.writeheader()
        w.writerows(check_rows)
    print(f"Wrote data/phase4_monotonicity_check_v2.csv ({len(check_rows)} rows)")
    print(f"Monotonicity failures (low<=base<=high violated): {n_fail_order} of {len(check_rows)} rows")
    print(f"S5 sign-consistency failures: {n_fail_s5_sign}")

    print(f"\nOverall E 2025 full year: ${overall_e_2025:,}  |  E latest 12mo: ${overall_e_12mo:,}\n")
    print(f"{'Scenario':<32}{'Year':<10}{'low $M':>10}{'base $M':>10}{'high $M':>10}{'base%':>8}")
    for r in sorted(total_rows, key=lambda x: (x["scenario"], x["scenario_year"])):
        print(f"{r['scenario']:<32}{r['scenario_year']:<10}"
              f"{r['rar_2025_low_usd']/1e6:>10.2f}{r['rar_2025_base_usd']/1e6:>10.2f}{r['rar_2025_high_usd']/1e6:>10.2f}"
              f"{r['rar_2025_base_pct'] if r['rar_2025_base_pct'] is not None else '':>8}")

    # ---- exposure score v2 ----
    codes = load_codes()
    ind_ex_usa, ind_ex_world = {}, {}
    for fname in ("india_trade.csv", "india_trade_final_new_codes.csv"):
        path = DATA_DIR / fname
        if not path.exists():
            continue
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("flow") == "India exports" and row.get("year") == "2025":
                    val = float(row.get("value_usd") or 0)
                    if row.get("partner") == "USA":
                        ind_ex_usa[row["hs6"]] = ind_ex_usa.get(row["hs6"], 0) + val
                    elif row.get("partner") == "World":
                        ind_ex_world[row["hs6"]] = ind_ex_world.get(row["hs6"], 0) + val

    scen_s0 = {r["code"]: r for r in scen_rows if r["scenario"] == "S0_Today"}
    rar_by_code_scenyear = {(r["code"], r["scenario"], r["scenario_year"] or ""): r for r in out_rows}

    raw = {}
    missing_us_dep = []
    excluded_below_1m = []
    for code, level, desc in codes:
        e_2025 = e_cache_2025.get(code, e_2025_full_year(code))
        if e_2025 < 1_000_000:
            excluded_below_1m.append(code)
            continue

        hs6 = code[:6]
        us_dep = None
        if hs6 in ind_ex_world and ind_ex_world[hs6] > 0:
            us_dep = 100 * ind_ex_usa.get(hs6, 0) / ind_ex_world[hs6]
        else:
            missing_us_dep.append(code)

        s0 = scen_s0.get(code)
        tariff_level = float(s0["india_actual_duty_2026ytd_pct"]) if s0 else None
        gap_actual = float(s0["gap_today_pct_points"]) if s0 else None

        group = groups.get(code, "Unknown")
        tier = tier_of_group.get(group)
        ease_switch = tier_eps[tier]["base"] if tier else None

        policy_risk = 1.0 if SEC232_NAMED.get(code, False) else 0.0

        s2_row = rar_by_code_scenyear.get((code, "S2_Sec232_15pct_exemptions", ""))
        base_s2_rar_usd = s2_row["rar_2025_base_usd"] if s2_row else None

        raw[code] = {
            "description": desc, "group": group, "tier": tier,
            "us_dependence_raw": us_dep, "tariff_level_raw": tariff_level,
            "competitor_gap_raw": gap_actual, "ease_switch_raw": ease_switch,
            "policy_risk_raw": policy_risk,
            "E_2025_full_year_usd": e_2025,
            "base_s2_rar_usd": base_s2_rar_usd,
        }

    def collect(key):
        return {c: v[key] for c, v in raw.items() if v[key] is not None}

    def scale_0_100(values_by_code):
        vals = list(values_by_code.values())
        if not vals:
            return {}
        lo, hi = min(vals), max(vals)
        if hi == lo:
            return {c: 50.0 for c in values_by_code}
        return {c: round(100 * (v - lo) / (hi - lo), 2) for c, v in values_by_code.items()}

    scaled = {}
    for key in ("us_dependence_raw", "tariff_level_raw", "competitor_gap_raw", "ease_switch_raw", "policy_risk_raw"):
        scaled[key] = scale_0_100(collect(key))

    WEIGHTS = {"us_dependence_raw": 0.30, "tariff_level_raw": 0.20, "competitor_gap_raw": 0.20,
               "ease_switch_raw": 0.15, "policy_risk_raw": 0.15}

    exp_rows = []
    for code, v in raw.items():
        parts = {}
        score = 0.0
        missing_parts = []
        for key, weight in WEIGHTS.items():
            s = scaled[key].get(code)
            parts[key] = s
            if s is None:
                missing_parts.append(key)
            else:
                score += weight * s
        exp_rows.append({
            "code": code, "description": v["description"], "group": v["group"], "tier": v["tier"],
            "E_2025_full_year_musd": round(v["E_2025_full_year_usd"] / 1e6, 3),
            "base_S2_rar_musd": round(v["base_s2_rar_usd"] / 1e6, 3) if v["base_s2_rar_usd"] is not None else None,
            "us_dependence_pct": round(v["us_dependence_raw"], 2) if v["us_dependence_raw"] is not None else None,
            "tariff_level_pct": v["tariff_level_raw"],
            "competitor_gap_pp": v["competitor_gap_raw"],
            "ease_of_switching_epsilon_tier_base": v["ease_switch_raw"],
            "policy_risk_named": bool(v["policy_risk_raw"]),
            "us_dependence_scaled": parts["us_dependence_raw"],
            "tariff_level_scaled": parts["tariff_level_raw"],
            "competitor_gap_scaled": parts["competitor_gap_raw"],
            "ease_of_switching_scaled": parts["ease_switch_raw"],
            "policy_risk_scaled": parts["policy_risk_raw"],
            "missing_components": ";".join(k.replace("_raw", "") for k in missing_parts),
            "exposure_score": round(score, 1),
        })

    exp_rows.sort(key=lambda r: r["exposure_score"], reverse=True)
    for i, r in enumerate(exp_rows, start=1):
        r["rank_by_score"] = i

    cols = ["rank_by_score"] + [k for k in exp_rows[0].keys() if k != "rank_by_score"]
    with open(DATA_DIR / "phase4_exposure_score_v2.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(exp_rows)

    print(f"\nWrote data/phase4_exposure_score_v2.csv ({len(exp_rows)} rows, "
          f"{len(excluded_below_1m)} codes excluded for < $1M India value in 2025)")
    print(f"Codes missing US-dependence data: {missing_us_dep}")

    print(f"\nTop 10 by exposure score:")
    for r in exp_rows[:10]:
        print(f"{r['rank_by_score']:<5}{r['code']:<14}{r['exposure_score']:>8}  {r['description'][:40]}")

    by_s2 = sorted((r for r in exp_rows if r["base_S2_rar_musd"] is not None),
                   key=lambda r: r["base_S2_rar_musd"], reverse=True)
    print(f"\nTop 10 by base-S2 $ at risk:")
    for i, r in enumerate(by_s2[:10], start=1):
        print(f"{i:<5}{r['code']:<14}${r['base_S2_rar_musd']:>8.2f}M  {r['description'][:40]}")


if __name__ == "__main__":
    main()
