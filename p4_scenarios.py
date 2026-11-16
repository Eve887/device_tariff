"""
p4_scenarios.py

Phase 4, Part 4: scenarios. For each of the 60 core codes, computes
today's actual-paid baseline (India vs. the top-3 non-India 2025
suppliers, weighted by 2025 value, using ACTUAL duty paid - Jan-Sep
2026 YTD - not listed rates, per the user's explicit instruction for
this whole phase), then delta_t (India's tariff change) and delta_g
(change in India's gap vs. that weighted competitor baseline) for each
scenario.

Scenario country treatment:
  S0 Today: no change anywhere.
  S1 China exclusion-expiry: China +delta on codes PROXY-IDENTIFIED as
     currently benefiting from an active exclusion (see note below -
     we do not have a confirmed per-code exclusion list, so this is a
     documented proxy, not ground truth). India unchanged; so are all
     non-China competitors.
  S2 Section 232 @ 15%, EU/Japan/UK/Mexico/Canada exempt: India +15,
     China +15, those five country-groups +0, everyone else
     (not otherwise classified) +15 by default (the "device tariff"
     scenario is described as broad, so an unlisted country is treated
     as subject to it, not exempt - the exemption list given is the
     complete named-exempt set).
  S3 Section 232 @ 25% on everyone: +25 for every country, India
     included. delta_g = 0 for every code by construction (uniform
     shock cancels out in the gap) - noted as an expected, sanity-
     checking consequence of the scenario design, not a bug.
  S4 Phased Section 232: +10 (year 1) then +25 (year 2) for everyone.
     Same delta_g = 0 consequence as S3, in both years.
  S5 India-US deal, India's forced-labor add-on to 0: India -10;
     every competitor unchanged.

S1 proxy methodology: a code is treated as "currently benefiting from
an active China exclusion" if China's actual 2026 YTD duty paid is
more than 3 percentage points BELOW its Phase-3-corrected listed rate
(china_listed_rate_pct_corrected, data/phase3_tariff_gap_data_v3.csv) -
exactly the same >3pp flagging threshold already used in Phase 3's
competitor check, where this exact pattern was attributed to "an
active Section 301 List 1-4A exclusion." The S1 bump itself is set to
that same listed-minus-actual gap, clipped to the user's stated 7.5-25
point range. This is a data-driven proxy, explicitly NOT the same as
having the real, named exclusion list (which Phase 3 already
established cannot be obtained from the Federal Register notice text
or the HTS REST API within reasonable effort).

READ-ONLY against core_device_codes.csv, raw/census/*,
data/phase3_tariff_gap_data_v3.csv. Writes data/phase4_scenarios.csv
(new file, one row per code x scenario x year-where-applicable).
"""

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
CENSUS_DIR = HERE / "raw" / "census"
INDIA = "5330"
CHINA = "5700"

EU_CODES = {"4280", "4279", "4190", "4759", "4210", "4700", "4010", "4231",
            "4330", "4370", "4550", "4490", "4510", "4470", "4710", "4840",
            "4850", "4870", "4792", "4359"}
JAPAN = "5880"
UK = "4120"
MEXICO = "2010"
CANADA = "1220"
S2_EXEMPT = EU_CODES | {JAPAN, UK, MEXICO, CANADA}


def load_codes():
    with open(DATA_DIR / "core_device_codes.csv", newline="", encoding="utf-8-sig") as f:
        return [(r["code"], r["level"], r["description"]) for r in csv.DictReader(f)]


def census_detail(code, period):
    raw_file = CENSUS_DIR / f"{code}_{period}.json"
    if not raw_file.exists():
        return None
    saved = json.loads(raw_file.read_text(encoding="utf-8"))
    if saved["status"] != "ok" or not saved["rows"]:
        return {"india": (0, 0), "world": (0, 0), "suppliers": {}}
    header, *records = saved["rows"]
    india = (0, 0)
    world = (0, 0)
    suppliers = {}
    for rec in records:
        r = dict(zip(header, rec))
        val = int(r.get("CON_VAL_YR") or 0)
        duty = int(r.get("CAL_DUT_YR") or 0)
        if "TOTAL FOR ALL" in (r.get("CTY_NAME") or "").upper():
            world = (val, duty)
        elif r.get("SUMMARY_LVL") == "DET":
            suppliers[r.get("CTY_CODE")] = (val, duty)
            if r.get("CTY_CODE") == INDIA:
                india = (val, duty)
    return {"india": india, "world": world, "suppliers": suppliers}


def duty_pct(val, duty):
    return round(100 * duty / val, 2) if val else None


def main():
    codes = load_codes()
    with open(DATA_DIR / "phase3_tariff_gap_data_v3.csv", newline="", encoding="utf-8-sig") as f:
        v3 = {r["code"]: r for r in csv.DictReader(f)}

    rows = []
    for code, level, desc in codes:
        d2025 = census_detail(code, "2025-12")
        d2026 = census_detail(code, "2026-09")
        if d2025 is None or d2026 is None:
            continue

        top3 = sorted(((cc, v) for cc, v in d2025["suppliers"].items() if cc != INDIA),
                      key=lambda x: x[1][0], reverse=True)[:3]
        total_top3_2025 = sum(v[0] for cc, v in top3)

        india_actual_2026 = duty_pct(*d2026["india"])
        weighted_actual_2026 = None
        if total_top3_2025 > 0:
            parts = []
            for cc, v2025 in top3:
                v2026 = d2026["suppliers"].get(cc, (0, 0))
                dp = duty_pct(*v2026)
                if dp is not None:
                    parts.append(v2025[0] * dp)
            if parts:
                weighted_actual_2026 = round(sum(parts) / total_top3_2025, 2)

        if india_actual_2026 is None or weighted_actual_2026 is None:
            continue
        gap_today = round(india_actual_2026 - weighted_actual_2026, 2)

        # S1 proxy: is China a top-3 supplier, and does it show the
        # listed-vs-actual gap pattern identified in Phase 3 as likely
        # an active exclusion?
        china_v2025 = next((v for cc, v in top3 if cc == CHINA), None)
        china_exclusion_bump = 0.0
        if china_v2025 is not None:
            china_listed = v3.get(code, {}).get("china_listed_rate_pct_corrected")
            china_v2026 = d2026["suppliers"].get(CHINA, (0, 0))
            china_actual_2026 = duty_pct(*china_v2026)
            if china_listed not in (None, "") and china_actual_2026 is not None:
                diff = float(china_listed) - china_actual_2026
                if diff > 3:
                    china_exclusion_bump = min(25.0, max(7.5, diff))

        def weighted_delta(country_deltas_by_cc):
            """country_deltas_by_cc: dict cc -> delta. Missing cc = 0."""
            if total_top3_2025 == 0:
                return 0.0
            parts = [v2025[0] * country_deltas_by_cc.get(cc, 0.0) for cc, v2025 in top3]
            return sum(parts) / total_top3_2025

        scenarios = []

        # S0
        scenarios.append(("S0_Today", None, 0.0, 0.0))

        # S1
        delta_g_s1 = weighted_delta({CHINA: china_exclusion_bump})
        scenarios.append(("S1_China_exclusion_expiry", None, 0.0, 0.0 - delta_g_s1))

        # S2
        india_delta_s2 = 15.0
        competitor_deltas_s2 = {cc: (0.0 if cc in S2_EXEMPT else 15.0) for cc, _ in top3}
        delta_g_s2 = india_delta_s2 - weighted_delta(competitor_deltas_s2)
        scenarios.append(("S2_Sec232_15pct_exemptions", None, india_delta_s2, delta_g_s2))

        # S3
        scenarios.append(("S3_Sec232_25pct_all", None, 25.0, 0.0))  # uniform -> gap unchanged

        # S4 (two years)
        scenarios.append(("S4_Phased_Sec232", "Year1_10pct", 10.0, 0.0))
        scenarios.append(("S4_Phased_Sec232", "Year2_25pct", 25.0, 0.0))

        # S5
        scenarios.append(("S5_India_deal_minus10", None, -10.0, -10.0))

        for scen_name, scen_year, delta_t, delta_g in scenarios:
            rows.append({
                "code": code, "description": desc, "level": level,
                "india_actual_duty_2026ytd_pct": india_actual_2026,
                "top3_weighted_actual_duty_2026ytd_pct": weighted_actual_2026,
                "gap_today_pct_points": gap_today,
                "china_in_top3": china_v2025 is not None,
                "china_exclusion_bump_pp_proxy": round(china_exclusion_bump, 2),
                "scenario": scen_name, "scenario_year": scen_year,
                "delta_t_pp": delta_t, "delta_g_pp": round(delta_g, 2),
            })

    with open(DATA_DIR / "phase4_scenarios.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    n_codes = len(set(r["code"] for r in rows))
    n_china_proxy = len(set(r["code"] for r in rows if r["china_exclusion_bump_pp_proxy"] > 0))
    print(f"Wrote data/phase4_scenarios.csv ({len(rows)} rows, {n_codes} codes x scenarios)")
    print(f"Codes where China is top-3 AND shows the exclusion-proxy pattern (>3pp listed-vs-actual gap): {n_china_proxy}")


if __name__ == "__main__":
    main()
