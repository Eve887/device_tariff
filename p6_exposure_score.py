"""
p6_exposure_score.py

Phase 4, Part 6: exposure score (0-100) per core code.
    US dependence        30% (India exports to USA / to World, Comtrade 2025)
    tariff level         20% (India's actual duty paid, Jan-Sep 2026)
    competitor gap       20% (gap_actual = Phase 4's own actual-paid gap,
                               NOT Phase 3's hybrid actual-vs-listed figure -
                               this whole phase's standing instruction is to
                               use actual duty paid for competitor comparisons)
    ease of switching    15% (the code's GROUP median epsilon, from Part 1)
    policy risk          15% (code's product matches one of the Section 232
                               notice's explicitly NAMED categories - see the
                               per-code list and reasoning in
                               logs/step1_progress_log.md; NOT the notice's
                               maximally-broad general definition, which
                               would match almost everything and carry no
                               information)
Each part scaled 0-100 (min-max) across the codes that HAVE a value for
that part, before weighting - codes missing a given part (the 5 HS10
lines, which have no Comtrade data of their own) are flagged, not
guessed.

READ-ONLY against core_device_codes.csv, final_codes_grouped.csv,
data/phase4_scenarios.csv (for gap_today/india_actual_duty),
data/phase4_elasticity_by_group.csv, data/india_trade.csv,
data/india_trade_final_new_codes.csv. Writes data/phase4_exposure_score.csv
(new file).
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

# Section 232 notice "named" determination - see logs/step1_progress_log.md
# for the full per-category reasoning. True = matches an explicitly named
# category/example in the notice; False = does not (e.g. dental and
# ophthalmic are never mentioned anywhere in the notice's text).
SEC232_NAMED = {
    "300510": True,   # gauze/bandages (adhesive dressings are a bandage)
    "300590": True,   # gauze/bandages
    "300610": True,   # sutures
    "300620": True,   # diagnostic/laboratory reagents (blood-grouping)
    "300640": False,  # dental
    "300650": False,  # first-aid KIT (bundle) - not an individually named item, borderline exclusion
    "300691": False,  # ostomy appliances - not named
    "382211": True, "382212": True, "382213": True,  # diagnostic/laboratory reagents
    "401410": False,  # rubber contraceptives - not medical per the notice's own scope
    "401512": True,   # gloves (PPE)
    "6210105010": True, "6210105090": True,  # gowns (PPE) - both lines, sibling to the named "gowns" line
    "842310": False,  # personal/household weighing scales - not named
    "900130": False, "900150": False,  # lenses - vision/ophthalmic never mentioned
    "901811": True, "901812": True, "901813": True, "901814": True, "901819": True, "901820": True,  # electromedical apparatus family
    "901831": True,   # syringes
    "901832": True,   # needles
    "901839": True,   # catheters
    "901841": False, "901849": False,  # dental
    "901850": False,  # ophthalmic - never mentioned
    "901890": True,   # medical/surgical instruments incl. forceps/scalpels, electro-surgical apparatus
    "901910": False,  # mechano-therapy/massage - not named
    "901920": True,   # respiratory machines (oxygen apparatus)
    "902000": True,   # respiratory machines (breathing appliances)
    "902110": True,   # orthopedic appliances
    "902121": False, "902129": False,  # dental (artificial teeth/fittings)
    "902131": True,   # orthopedic appliances/prosthetics (artificial joints)
    "902139": True,   # prosthetics (other artificial parts of the body)
    "902140": True,   # hearing aids
    "902150": True,   # pacemakers
    "902190": True,   # coronary stents ("other appliances implanted")
    "902212": True,   # electromedical apparatus (CT)
    "902213": True, "902214": True, "902219": True,  # x-ray apparatus
    "902221": True, "902229": True,  # x-ray/radiation equipment
    "902230": True, "902290": True,  # x-ray apparatus and parts
    "902511": False,  # clinical thermometers - not named (only glucose monitors are)
    "9025198010": False, "9025198020": False,  # thermometer HS10 lines - same
    "902710": False, "902720": False, "902730": False, "902750": False, "902790": False,  # lab analytical instruments - not named
    "940210": False, "9402100000": False,  # dentists'/barbers' chairs - dental
    "940290": True,   # hospital beds
}


def load_codes():
    with open(DATA_DIR / "core_device_codes.csv", newline="", encoding="utf-8-sig") as f:
        return [(r["code"], r["level"], r["description"]) for r in csv.DictReader(f)]


def load_groups():
    with open(DATA_DIR / "final_codes_grouped.csv", newline="", encoding="utf-8-sig") as f:
        return {r["code"]: r["group"] for r in csv.DictReader(f)}


def load_comtrade_us_dependence():
    ind_ex_usa, ind_ex_world = {}, {}
    for fname in ("india_trade.csv", "india_trade_final_new_codes.csv"):
        path = DATA_DIR / fname
        if not path.exists():
            continue
        with open(path, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r.get("flow") == "India exports" and r.get("year") == "2025":
                    val = float(r.get("value_usd") or 0)
                    if r.get("partner") == "USA":
                        ind_ex_usa[r["hs6"]] = ind_ex_usa.get(r["hs6"], 0) + val
                    elif r.get("partner") == "World":
                        ind_ex_world[r["hs6"]] = ind_ex_world.get(r["hs6"], 0) + val
    return ind_ex_usa, ind_ex_world


def load_scenario_baseline():
    with open(DATA_DIR / "phase4_scenarios.csv", newline="", encoding="utf-8-sig") as f:
        return {r["code"]: r for r in csv.DictReader(f) if r["scenario"] == "S0_Today"}


def scale_0_100(values_by_code):
    """values_by_code: dict code -> float (only codes that HAVE a value).
    Returns dict code -> scaled 0-100."""
    vals = list(values_by_code.values())
    if not vals:
        return {}
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return {c: 50.0 for c in values_by_code}  # all equal - no information, put at midpoint
    return {c: round(100 * (v - lo) / (hi - lo), 2) for c, v in values_by_code.items()}


def main():
    codes = load_codes()
    groups = load_groups()
    ind_ex_usa, ind_ex_world = load_comtrade_us_dependence()
    scen = load_scenario_baseline()
    with open(DATA_DIR / "phase4_elasticity_by_group.csv", newline="", encoding="utf-8-sig") as f:
        group_eps = {r["group"]: float(r["median_epsilon"]) for r in csv.DictReader(f)}

    raw = {}  # code -> dict of raw component values (or None if missing)
    missing_us_dep = []
    for code, level, desc in codes:
        hs6 = code[:6]
        us_dep = None
        if hs6 in ind_ex_world and ind_ex_world[hs6] > 0:
            us_dep = 100 * ind_ex_usa.get(hs6, 0) / ind_ex_world[hs6]
        else:
            missing_us_dep.append(code)

        s0 = scen.get(code)
        tariff_level = float(s0["india_actual_duty_2026ytd_pct"]) if s0 else None
        gap_actual = float(s0["gap_today_pct_points"]) if s0 else None

        group = groups.get(code, "Unknown")
        ease_switch = group_eps.get(group)  # median epsilon for the group

        policy_risk = 1.0 if SEC232_NAMED.get(code, False) else 0.0

        raw[code] = {
            "description": desc, "group": group,
            "us_dependence_raw": us_dep, "tariff_level_raw": tariff_level,
            "competitor_gap_raw": gap_actual, "ease_switch_raw": ease_switch,
            "policy_risk_raw": policy_risk,
        }

    def collect(key):
        return {c: v[key] for c, v in raw.items() if v[key] is not None}

    scaled = {}
    for key in ("us_dependence_raw", "tariff_level_raw", "competitor_gap_raw", "ease_switch_raw", "policy_risk_raw"):
        scaled[key] = scale_0_100(collect(key))

    WEIGHTS = {"us_dependence_raw": 0.30, "tariff_level_raw": 0.20, "competitor_gap_raw": 0.20,
               "ease_switch_raw": 0.15, "policy_risk_raw": 0.15}

    out_rows = []
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
        out_rows.append({
            "code": code, "description": v["description"], "group": v["group"],
            "us_dependence_pct": round(v["us_dependence_raw"], 2) if v["us_dependence_raw"] is not None else None,
            "tariff_level_pct": v["tariff_level_raw"],
            "competitor_gap_pp": v["competitor_gap_raw"],
            "ease_of_switching_epsilon": v["ease_switch_raw"],
            "policy_risk_named": bool(v["policy_risk_raw"]),
            "us_dependence_scaled": parts["us_dependence_raw"],
            "tariff_level_scaled": parts["tariff_level_raw"],
            "competitor_gap_scaled": parts["competitor_gap_raw"],
            "ease_of_switching_scaled": parts["ease_switch_raw"],
            "policy_risk_scaled": parts["policy_risk_raw"],
            "missing_components": ";".join(k.replace("_raw", "") for k in missing_parts),
            "exposure_score": round(score, 1),
        })

    out_rows.sort(key=lambda r: r["exposure_score"], reverse=True)
    for i, r in enumerate(out_rows, start=1):
        r["rank"] = i

    cols = ["rank"] + [k for k in out_rows[0].keys() if k != "rank"]
    with open(DATA_DIR / "phase4_exposure_score.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out_rows)

    print(f"Wrote data/phase4_exposure_score.csv ({len(out_rows)} rows)")
    print(f"Codes missing US-dependence data (no Comtrade for this HS6): {missing_us_dep}")
    print(f"\nTop 10 by exposure score:")
    print(f"{'Rank':<6}{'Code':<14}{'Description':<42}{'Score':>8}")
    for r in out_rows[:10]:
        print(f"{r['rank']:<6}{r['code']:<14}{r['description'][:40]:<42}{r['exposure_score']:>8}")


if __name__ == "__main__":
    main()
