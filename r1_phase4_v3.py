"""
r1_phase4_v3.py

Final Phase 4 run (v3). User-decided settlement of the v2 open
questions:
  1. Alpha: use the fallback 0.3/0.45/0.6 (low/base/high) in all
     totals/exposure figures. The measured alpha from Fix 3
     (data/phase4_alpha_hs10_summary_v2.csv, median 0.063, range
     -1.292 to 0.908, n=17) is carried into its own output/sheet,
     explicitly labelled unstable and NOT used here.
  2. Epsilon: Tier A and Tier B keep their v2 bootstrapped values
     unchanged. Tier C's epsilon is REPLACED with v2's POOLED epsilon
     (0.539/0.673/0.833). Code 902140 (Hearing aids, group "Hearing")
     is assigned to Tier B for scenario/exposure membership purposes
     only - Tier B's own epsilon number is not recomputed to include
     it (consistent with "keep the v2 bootstrapped values").
  3. Re-run Totals (S0-S5, low/base/high, $M and %, both E bases).
     Sanity checks: low<=base<=high for every LOSS scenario (S0-S4),
     and S5 shows a GAIN (this script's sign convention: a negative
     revenue-at-risk number = a gain) in all three of low/base/high.
  4. Persistent-loss section: for Tiers A, B, C, Apr-Sep 2026 vs
     Apr-Sep 2024 (the same out-of-sample window as Fix 2) - actual
     change, model-predicted change (using each tier's NEW base
     epsilon), and the gap in $M. Tier A and B reuse Fix 2's own
     numbers unchanged (their epsilon_base didn't change). Tier C is
     recomputed with the new pooled-epsilon base (0.673) against the
     SAME already-measured gap_change_new_period_pp and actual change
     Fix 2 found for Tier C's own qualifying codes (codes list
     unchanged - only the epsilon parameter changed).
  5. Exposure score re-run (>= $1M India value in 2025 only), with
     902140 now included via its new Tier B membership.

READ-ONLY against data/phase4_tier_epsilon_v2.csv,
data/phase4_out_of_sample_v2.csv, data/phase4_scenarios.csv,
data/final_codes_grouped.csv, core_device_codes.csv,
data/india_trade*.csv, raw/census/*, raw/census_monthly/*. Writes
data/phase4_tier_epsilon_v3.csv, data/phase4_revenue_at_risk_v3.csv,
data/phase4_revenue_at_risk_totals_v3.csv,
data/phase4_monotonicity_check_v3.csv,
data/phase4_persistent_loss_v3.csv, data/phase4_exposure_score_v3.csv
(new files, v2 files untouched).
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

TIERS_V3 = {
    "Tier A (simple disposables)": {"Consumables", "Dressings & Sutures", "Gloves"},
    "Tier B (equipment)": {"Electro-diagnostic", "Imaging", "Instruments",
                            "Respiratory & Therapy", "Ophthalmic", "Furniture", "Other",
                            "Hearing"},  # 902140 added here per user decision
    "Tier C (implants and dental)": {"Implants", "Dental"},
}

FALLBACK_ALPHA = {"low": 0.3, "base": 0.45, "high": 0.6}

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


def build_tier_epsilon_v3():
    with open(DATA_DIR / "phase4_tier_epsilon_v2.csv", newline="", encoding="utf-8-sig") as f:
        v2 = {r["tier"]: r for r in csv.DictReader(f)}

    pooled = v2["POOLED (all tiers)"]
    rows = []
    for tier_name in ("Tier A (simple disposables)", "Tier B (equipment)", "Tier C (implants and dental)"):
        if tier_name == "Tier C (implants and dental)":
            src = pooled
            note = ("Epsilon REPLACED with v2's POOLED value per user decision "
                    "(Tier C's own estimate, n=3, was the least trustworthy of the "
                    "three and failed Fix 2's out-of-sample test). Codes list below "
                    "is still Tier C's own qualifying codes (used for the persistent-"
                    "loss out-of-sample comparison) - NOT the pooled code list.")
            codes_for_display = v2[tier_name]["codes"]
        elif tier_name == "Tier B (equipment)":
            src = v2[tier_name]
            note = ("Epsilon value UNCHANGED from v2 (not recomputed). Code 902140 "
                    "(Hearing aids) added to this tier's membership for scenario/"
                    "exposure-score purposes only, per user decision - it is not "
                    "included in the epsilon bootstrap below.")
            codes_for_display = v2[tier_name]["codes"] + ";902140"
        else:
            src = v2[tier_name]
            note = "Epsilon value UNCHANGED from v2 (not recomputed)."
            codes_for_display = v2[tier_name]["codes"]

        rows.append({
            "tier": tier_name,
            "n_codes": src["n_codes"] if tier_name != "Tier B (equipment)" else str(int(src["n_codes"]) + 1),
            "epsilon_low_p25": src["epsilon_low_p25"],
            "epsilon_base_median": src["epsilon_base_median"],
            "epsilon_high_p75": src["epsilon_high_p75"],
            "gap_change_pp_v2_fit_window": src["gap_change_pp"],
            "note": note,
            "codes": codes_for_display,
        })

    with open(DATA_DIR / "phase4_tier_epsilon_v3.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("Wrote data/phase4_tier_epsilon_v3.csv")
    for r in rows:
        print(f"  {r['tier']}: low={r['epsilon_low_p25']} base={r['epsilon_base_median']} high={r['epsilon_high_p75']}")
    return {r["tier"]: {"low": float(r["epsilon_low_p25"]), "base": float(r["epsilon_base_median"]),
                         "high": float(r["epsilon_high_p75"])} for r in rows}


def build_persistent_loss_v3(tier_eps_v3):
    with open(DATA_DIR / "phase4_out_of_sample_v2.csv", newline="", encoding="utf-8-sig") as f:
        v2_oos = {r["tier"]: r for r in csv.DictReader(f)}

    rows = []
    for tier_name, r in v2_oos.items():
        gap_change_new = float(r["gap_change_new_period_pp"])
        actual = float(r["actual_relative_change_pct"])
        india_baseline = int(r["india_baseline_usd_this_period"])

        if tier_name == "Tier C (implants and dental)":
            eps_base_new = tier_eps_v3[tier_name]["base"]  # now 0.673 (pooled)
        else:
            eps_base_new = float(r["epsilon_used_from_fix1_base"])  # unchanged

        predicted = -eps_base_new * gap_change_new
        gap_pp = predicted - actual
        gap_usd = india_baseline * gap_pp / 100

        rows.append({
            "tier": tier_name,
            "epsilon_base_used": round(eps_base_new, 3),
            "gap_change_apr_sep_pp": round(gap_change_new, 2),
            "actual_change_pct": round(actual, 2),
            "model_predicted_change_pct": round(predicted, 2),
            "gap_musd": round(gap_usd / 1e6, 2),
        })

    rows.append({
        "tier": "NOTE",
        "epsilon_base_used": "",
        "gap_change_apr_sep_pp": "",
        "actual_change_pct": "",
        "model_predicted_change_pct": "",
        "gap_musd": ("Fall larger than tariff gaps explain, consistent with US buyers "
                     "not returning after the 50% period (Oct 2025-Feb 2026). Scenario "
                     "totals exclude this, so they are a lower bound."),
    })

    with open(DATA_DIR / "phase4_persistent_loss_v3.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("\nWrote data/phase4_persistent_loss_v3.csv")
    for r in rows[:-1]:
        print(f"  {r['tier']}: actual={r['actual_change_pct']}%  predicted={r['model_predicted_change_pct']}%  gap=${r['gap_musd']}M")


def main():
    tier_eps_v3 = build_tier_epsilon_v3()
    build_persistent_loss_v3(tier_eps_v3)

    groups = load_groups()
    tier_of_group = {}
    for tier, grouplist in TIERS_V3.items():
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
        e_2025, e_12mo = e_cache_2025[code], e_cache_12mo[code]

        group = groups.get(code, "Unknown")
        tier = tier_of_group.get(group)
        if tier is None:
            skipped_no_tier.add(code)
            continue
        eps = tier_eps_v3[tier]

        delta_t = float(r["delta_t_pp"]) / 100
        delta_g = float(r["delta_g_pp"]) / 100

        def rar(E, a, e):
            return E * (a * delta_t + e * (1 - a) * delta_g)

        rar_2025 = {k: rar(e_2025, FALLBACK_ALPHA[k], eps[k]) for k in ("low", "base", "high")}
        rar_12mo = {k: rar(e_12mo, FALLBACK_ALPHA[k], eps[k]) for k in ("low", "base", "high")}

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

    with open(DATA_DIR / "phase4_revenue_at_risk_v3.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print(f"\nWrote data/phase4_revenue_at_risk_v3.csv ({len(out_rows)} rows)")
    if skipped_no_tier:
        print(f"Codes skipped (no tier mapping): {sorted(skipped_no_tier)}")
    else:
        print("All codes now have a tier assignment (902140 gap closed).")

    # ---- totals ----
    totals = defaultdict(lambda: defaultdict(float))
    seen_codes = set()
    overall_e_2025 = overall_e_12mo = 0
    for row in out_rows:
        key = (row["scenario"], row["scenario_year"] or "")
        for lbl in ("low", "base", "high"):
            totals[key][f"rar_2025_{lbl}"] += row[f"rar_2025_{lbl}_usd"]
            totals[key][f"rar_12mo_{lbl}"] += row[f"rar_12mo_{lbl}_usd"]
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

    with open(DATA_DIR / "phase4_revenue_at_risk_totals_v3.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(total_rows[0].keys()))
        w.writeheader()
        w.writerows(total_rows)
    print(f"Wrote data/phase4_revenue_at_risk_totals_v3.csv ({len(total_rows)} rows)")

    # ---- monotonicity / sign check ----
    check_rows = []
    n_fail_order, n_fail_s5_gain = 0, 0
    for r in total_rows:
        for basis in ("2025", "12mo"):
            lo, ba, hi = r[f"rar_{basis}_low_usd"], r[f"rar_{basis}_base_usd"], r[f"rar_{basis}_high_usd"]
            is_s5 = r["scenario"] == "S5_India_deal_minus10"
            if not is_s5:
                order_ok = lo <= ba <= hi
                if not order_ok:
                    n_fail_order += 1
                s5_all_gain = None
            else:
                order_ok = None
                s5_all_gain = (lo < 0) and (ba < 0) and (hi < 0)  # negative rar = gain in this sign convention
                if not s5_all_gain:
                    n_fail_s5_gain += 1
            check_rows.append({
                "scenario": r["scenario"], "scenario_year": r["scenario_year"], "basis": basis,
                "low_usd": lo, "base_usd": ba, "high_usd": hi,
                "low_le_base_le_high_loss_scenario": order_ok,
                "s5_gain_in_all_three": s5_all_gain,
            })

    with open(DATA_DIR / "phase4_monotonicity_check_v3.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(check_rows[0].keys()))
        w.writeheader()
        w.writerows(check_rows)
    print(f"Wrote data/phase4_monotonicity_check_v3.csv ({len(check_rows)} rows)")
    print(f"Loss-scenario ordering failures: {n_fail_order}")
    print(f"S5 'gain in all three' failures: {n_fail_s5_gain}")

    print(f"\nOverall E 2025 full year: ${overall_e_2025:,}  |  E latest 12mo: ${overall_e_12mo:,}\n")
    print(f"{'Scenario':<32}{'Year':<10}{'low $M':>10}{'base $M':>10}{'high $M':>10}{'base%':>8}")
    for r in sorted(total_rows, key=lambda x: (x["scenario"], x["scenario_year"])):
        print(f"{r['scenario']:<32}{r['scenario_year']:<10}"
              f"{r['rar_2025_low_usd']/1e6:>10.2f}{r['rar_2025_base_usd']/1e6:>10.2f}{r['rar_2025_high_usd']/1e6:>10.2f}"
              f"{r['rar_2025_base_pct'] if r['rar_2025_base_pct'] is not None else '':>8}")

    # ---- exposure score v3 ----
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
        ease_switch = tier_eps_v3[tier]["base"] if tier else None

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
    with open(DATA_DIR / "phase4_exposure_score_v3.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(exp_rows)

    print(f"\nWrote data/phase4_exposure_score_v3.csv ({len(exp_rows)} rows, "
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
