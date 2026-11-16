"""
s2_company_risk.py

Phase 5, Parts 3-4: company revenue-at-risk and EBITDA-at-risk per
scenario S0-S5 (low/base/high).

    company_revenue_at_risk = company_US_revenue x (RAR% of the
        company's product codes, weighted by its product mix)

Per-code RAR% is derived from Phase 4 v3's own numbers
(data/phase4_revenue_at_risk_v3.csv: rar_usd / E_usd, per code x
scenario x low/base/high), then combined into one RAR% per company
using the category/product-mix weights in COMPANY_WEIGHTS below -
built from each company's own DISCLOSED segment-revenue % (POLYMED,
SMT, Translumina's Cardiovascular segment) where available, or an
explicit equal-weight split across mapped codes where no finer split
is disclosed (LAXMIDENTL, documented inline). TARSONS has no mapped
codes at all (see data/phase5_product_mapping.csv) - RAR is reported
as not computable, not zero.

"company_US_revenue": only LAXMIDENTL discloses an explicit US %
(19.4% of FY26 revenue). For POLYMED, SMT and Translumina, no US-
specific figure is disclosed - the closest available geography bucket
(Poly's/SMT's "RoW", which includes the US among many other
countries) is used as a labelled, flagged SUBSTITUTE, not a silent
assumption that RoW = US. This will overstate true US exposure for
those three. TARSONS has no usable revenue base either (no mapped
codes).

Part 4 EBITDA at risk:
    price-cut part = alpha x delta_t x E  (falls fully on EBITDA)
    lost-orders part = epsilon x (1-alpha) x delta_g x E, falling on
        EBITDA at the company's own gross margin
    EBITDA at risk = price-cut part + lost-orders part x gross margin
This requires splitting the already-computed company revenue-at-risk
back into its two components per code (both tracked in Phase 4's RAR
formula), re-weighted the same way, then combining with each company's
own disclosed gross margin (data/phase5_financials.csv, FY2025-26)
and FY2025-26 EBITDA for the % figure. USD/INR conversion uses the RBI
reference rate for 31 March 2026 - see RBI_RATE_SOURCE below.

READ-ONLY against data/phase4_revenue_at_risk_v3.csv,
data/phase5_companies.csv, data/phase5_geography.csv,
data/phase5_product_mapping.csv, data/phase5_financials.csv. Writes
data/phase5_revenue_at_risk.csv, data/phase5_ebitda_at_risk.csv (new
files).
"""

import csv
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
ND = "not disclosed"

RBI_RATE_31MAR2026 = 94.6543
RBI_RATE_SOURCE = ("RBI/FBIL reference rate for 30 March 2026 (94.6543 INR/USD), used as the "
                    "31 March 2026 closing rate because 31 March 2026 was a bank holiday "
                    "(Mahavir Jayanti) and no reference rate was published that day - same "
                    "substitution convention SMT's own DRHP uses for holiday dates. Source: "
                    "karwaandassociates.com/usd-inr-rate-30-march-2026-last-rate-for-fy-2025-26 "
                    "(citing the RBI/FBIL reference rate), cross-checked against "
                    "exchange-rates.org/exchange-rate-history/usd-inr-2026-03-31")

SCENARIOS = ["S0_Today", "S1_China_exclusion_expiry", "S2_Sec232_15pct_exemptions",
             "S3_Sec232_25pct_all", "S4_Phased_Sec232", "S5_India_deal_minus10"]

# code -> weight, per company. Weights sum to 1.0 within a company.
# Documented derivation in each company's "basis" string.
COMPANY_WEIGHTS = {
    "POLYMED": {
        "weights": {"901831": 0.1767, "901832": 0.1767, "901839": 0.1767, "901890": 0.47},
        "basis": ("FY26 segment mix (Poly Medicure FY26 investor presentation, p.13): "
                  "Infusion Therapy 53% split equally across Syringes/Needles/Catheters "
                  "(901831/901832/901839, 17.67% each, since no finer split is disclosed); "
                  "Renal 10% + Others 37% = 47% mapped to 901890 (Other medical/surgical "
                  "instruments) as a catch-all, since dialysis/renal and 'Others' products "
                  "are not individually broken out to HS6 level in investor materials"),
    },
    "LAXMIDENTL": {
        "weights": {"902121": 0.5, "902129": 0.5},
        "basis": ("100% dental business. No disclosed split between Artificial teeth "
                  "(902121) and Other dental fittings (902129) - equal-weighted 50/50 as "
                  "an explicit placeholder, not a disclosed fact. Both codes are in the "
                  "same Tier C (Implants and Dental), so the RAR% result is not very "
                  "sensitive to this particular split."),
    },
    "TARSONS": {
        "weights": {},
        "basis": "NOT COMPUTABLE - no HS6 code in core_device_codes.csv maps to Tarsons' lab-plasticware products (HS 3926, outside the medical-device code list). See data/phase5_product_mapping.csv.",
    },
    "SMT": {
        "weights": {"902190": 0.3293, "901839": 0.5172, "902139": 0.1535},
        "basis": ("FY25 segment mix (SMT DRHP p.357-360): VI devices 65.86% split equally "
                  "between stents (902190) and balloon catheters (901839), 32.93% each; "
                  "SH devices 15.35% -> 902139 (TAVI/occluders = other artificial body "
                  "parts); Others 18.79% (explicitly 'PTMC balloons, sizing balloons, "
                  "Y-connectors, aspiration catheters and inflation devices' per the DRHP's "
                  "own wording) -> 901839, since these are catheter/balloon-type "
                  "accessories. 901839 total = 32.93%+18.79%=51.72%."),
    },
    "TRANSLUMINA": {
        "weights": {"902190": 0.2599, "901839": 0.2599, "902139": 0.4802},
        "basis": ("Weights apply WITHIN the Cardiovascular segment only (FY25: DES+Balloons "
                  "3,436.45mn + Other Cardiovascular 3,175.73mn = 6,612.18mn of Integris "
                  "Medtech's whole-company revenue of 19,024.66mn - the non-device Lab "
                  "Solutions business, ~65% of revenue, is excluded entirely from this "
                  "company's device-tariff exposure). DES+Balloons 51.98% of the "
                  "Cardiovascular segment split equally between 902190/901839 (25.99% "
                  "each, no finer disclosed split); Other Cardiovascular Products 48.02% "
                  "-> 902139 (valves/occluders), same logic as SMT's SH devices."),
    },
}

# Revenue base used as the "US revenue" input - explicit per company,
# with the caveat carried through every output row.
COMPANY_REVENUE_BASE = {
    "POLYMED": {
        "value_inr_cr": None, "value_usd_m": 3.5,
        "basis": ("US revenue NOT disclosed as a %% or audited segment line. Using the "
                  "upper end of management's own spoken range ('less than $3-3.5 million', "
                  "Q1 FY26 earnings call, ~Aug 2025, Rahul Gautam) as the best available "
                  "point figure for FY26 - this is a spoken approximation, not an audited "
                  "actual, and is the closest thing to a true US-only figure found for this "
                  "company (better than using the RoW bucket, which bundles in ~35%% of "
                  "revenue across many non-US countries)."),
        "period": "FY2026",
    },
    "LAXMIDENTL": {
        "value_inr_cr": 277.86 * 0.194, "value_usd_m": None,
        "basis": "US revenue explicitly disclosed: 19.4% of FY26 total revenue (Rs277.86cr) = Rs53.9cr. The ONE company in this study with a genuine US-specific %.",
        "period": "FY2026",
    },
    "TARSONS": {
        "value_inr_cr": None, "value_usd_m": None,
        "basis": "NOT COMPUTABLE - no mapped HS6 codes (see COMPANY_WEIGHTS above), so no revenue base is meaningful regardless of geography disclosure.",
        "period": "N/A",
    },
    "SMT": {
        "value_inr_cr": 1024.88 * 0.3576, "value_usd_m": None,
        "basis": ("US revenue NOT disclosed. Using FY25's 'RoW' geography bucket (35.76%% "
                  "of Rs1,024.88cr total revenue = Rs366.5cr) as the broadest available "
                  "SUBSTITUTE, explicitly flagged as NOT US-specific - RoW includes 70+ "
                  "countries for SMT (per its DRHP's own 'Presence in countries' KPI), "
                  "so this materially OVERSTATES true US exposure."),
        "period": "FY2025",
    },
    "TRANSLUMINA": {
        "value_inr_cr": (6612.18 / 100) * 0.038, "value_usd_m": None,
        "basis": ("US revenue NOT disclosed, and geography is only available at the WHOLE "
                  "Integris Medtech level (mixing in the non-device Lab Solutions business). "
                  "Applying the whole-company FY25 'Rest of World' %% (3.8%%) to the "
                  "Cardiovascular-segment-only revenue base (Rs661.2cr) as a doubly-"
                  "approximate SUBSTITUTE for US revenue - flagged as the weakest revenue "
                  "base in this entire study, given two layers of proxying (RoW != US, and "
                  "whole-company %% applied to a segment-only base)."),
        "period": "FY2025 (Cardiovascular segment estimate)",
    },
}

GROSS_MARGIN_PCT = {
    # most recent disclosed gross margin, FY2025-26 where available, else FY2025.
    "POLYMED": (None, "FY26 gross margin not independently located (see phase5_financials.csv) - NOT DISCLOSED, EBITDA-at-risk split into price-cut/lost-orders not computable for POLYMED without it"),
    "LAXMIDENTL": (None, "FY26 whole-company gross margin not independently located (Q2FY27 quarterly gross margin of 76.9% was found but not a full FY26 figure) - using FY25's 76.06% as the nearest available full-year figure instead, flagged as one year stale"),
    "SMT": (None, "SMT's DRHP KPI table does not include Gross Margin as a disclosed metric at all (unlike the Integris-format tables) - NOT DISCLOSED"),
    "TRANSLUMINA": (43.95, "FY25 whole-Integris gross margin (mixes Lab Solutions + Cardiovascular - no segment-level gross margin disclosed)"),
}
# Explicit overrides where a usable figure WAS found above but needed a fallback period:
GROSS_MARGIN_PCT["LAXMIDENTL"] = (76.06, "FY25 gross margin (Integris DRHP p.174) used as the nearest available full-year figure - FY26 whole-company gross margin not independently located")


def load_percode_rar():
    """Returns dict: code -> scenario -> {low,base,high: (rar_usd, e_usd)} using 2025-E basis."""
    out = defaultdict(lambda: defaultdict(dict))
    with open(DATA_DIR / "phase4_revenue_at_risk_v3.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            code = r["code"]
            scen = r["scenario"]
            e = float(r["E_2025_full_year_usd"])
            for tier in ("low", "base", "high"):
                rar = float(r[f"rar_2025_{tier}_usd"])
                # multiple rows exist for S4 (Year1/Year2) - keep both, keyed by scenario+year
                key = scen if not r["scenario_year"] else f"{scen}|{r['scenario_year']}"
                out[code][key][tier] = (rar, e)
    return out


def company_rar_pct(code_rar, weights, scenario_key):
    """Weighted RAR% for a company given its code weights, for one scenario key."""
    result = {}
    for tier in ("low", "base", "high"):
        total = 0.0
        missing = []
        for code, w in weights.items():
            cell = code_rar.get(code, {}).get(scenario_key)
            if cell is None or tier not in cell:
                missing.append(code)
                continue
            rar, e = cell[tier]
            pct = (rar / e) if e else 0.0
            total += w * pct
        result[tier] = total
    return result


def main():
    code_rar = load_percode_rar()
    scen_keys = SCENARIOS[:4] + ["S4_Phased_Sec232|Year1_10pct", "S4_Phased_Sec232|Year2_25pct"] + [SCENARIOS[5]]

    rar_rows = []
    for company, cfg in COMPANY_WEIGHTS.items():
        weights = cfg["weights"]
        basis = cfg["basis"]
        rev_cfg = COMPANY_REVENUE_BASE[company]

        if not weights:
            for sk in scen_keys:
                rar_rows.append({
                    "company": company, "scenario": sk,
                    "low_inr_cr": ND, "base_inr_cr": ND, "high_inr_cr": ND,
                    "low_usd_m": ND, "base_usd_m": ND, "high_usd_m": ND,
                    "low_pct_of_revenue": ND, "base_pct_of_revenue": ND, "high_pct_of_revenue": ND,
                    "revenue_base_basis": rev_cfg["basis"], "weighting_basis": basis,
                })
            continue

        rev_usd_m = rev_cfg["value_usd_m"]
        rev_inr_cr = rev_cfg["value_inr_cr"]
        # normalize revenue base to USD for the % calc (RAR% is dimensionless, so either works -
        # keep the company's own natural unit for the $ output columns)
        for sk in scen_keys:
            pcts = company_rar_pct(code_rar, weights, sk)
            row = {
                "company": company, "scenario": sk,
                "low_pct_of_revenue": round(pcts["low"] * 100, 3),
                "base_pct_of_revenue": round(pcts["base"] * 100, 3),
                "high_pct_of_revenue": round(pcts["high"] * 100, 3),
                "revenue_base_basis": rev_cfg["basis"], "weighting_basis": basis,
            }
            if rev_usd_m is not None:
                row["low_usd_m"] = round(rev_usd_m * pcts["low"], 4)
                row["base_usd_m"] = round(rev_usd_m * pcts["base"], 4)
                row["high_usd_m"] = round(rev_usd_m * pcts["high"], 4)
                row["low_inr_cr"] = round(row["low_usd_m"] * RBI_RATE_31MAR2026 / 100, 3)
                row["base_inr_cr"] = round(row["base_usd_m"] * RBI_RATE_31MAR2026 / 100, 3)
                row["high_inr_cr"] = round(row["high_usd_m"] * RBI_RATE_31MAR2026 / 100, 3)
            else:
                row["low_inr_cr"] = round(rev_inr_cr * pcts["low"], 3)
                row["base_inr_cr"] = round(rev_inr_cr * pcts["base"], 3)
                row["high_inr_cr"] = round(rev_inr_cr * pcts["high"], 3)
                row["low_usd_m"] = round(row["low_inr_cr"] * 1e7 / RBI_RATE_31MAR2026 / 1e6, 4)
                row["base_usd_m"] = round(row["base_inr_cr"] * 1e7 / RBI_RATE_31MAR2026 / 1e6, 4)
                row["high_usd_m"] = round(row["high_inr_cr"] * 1e7 / RBI_RATE_31MAR2026 / 1e6, 4)
            rar_rows.append(row)

    cols = ["company", "scenario", "low_inr_cr", "base_inr_cr", "high_inr_cr",
            "low_usd_m", "base_usd_m", "high_usd_m",
            "low_pct_of_revenue", "base_pct_of_revenue", "high_pct_of_revenue",
            "revenue_base_basis", "weighting_basis"]
    with open(DATA_DIR / "phase5_revenue_at_risk.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rar_rows)
    print(f"Wrote data/phase5_revenue_at_risk.csv ({len(rar_rows)} rows)")

    # ---- Part 4: EBITDA at risk ----
    # Need the price-cut vs lost-orders split per code. Recompute from
    # Phase 4's own formula components (delta_t, delta_g, alpha, epsilon)
    # rather than just the combined $ - re-derive alpha/epsilon contributions.
    with open(DATA_DIR / "phase4_revenue_at_risk_v3.csv", newline="", encoding="utf-8-sig") as f:
        rows_v3 = list(csv.DictReader(f))
    with open(DATA_DIR / "phase4_tier_epsilon_v3.csv", newline="", encoding="utf-8-sig") as f:
        tier_eps = {r["tier"]: r for r in csv.DictReader(f)}
    FALLBACK_ALPHA = {"low": 0.3, "base": 0.45, "high": 0.6}

    def price_cut_and_lost_orders(code_row, tier_name, alpha_tier, eps_tier):
        delta_t = float(code_row["delta_t_pp"]) / 100
        delta_g = float(code_row["delta_g_pp"]) / 100
        e = float(code_row["E_2025_full_year_usd"])
        price_cut = e * alpha_tier * delta_t
        lost_orders = e * eps_tier * (1 - alpha_tier) * delta_g
        return price_cut, lost_orders

    # index rows_v3 by (code, scenario, scenario_year)
    idx = {}
    for r in rows_v3:
        key = (r["code"], r["scenario"], r["scenario_year"] or "")
        idx[key] = r

    ebitda_rows = []
    for company, cfg in COMPANY_WEIGHTS.items():
        weights = cfg["weights"]
        gm_pct, gm_note = GROSS_MARGIN_PCT.get(company, (None, "not defined"))
        rev_cfg = COMPANY_REVENUE_BASE[company]

        if not weights:
            for sk in scen_keys:
                ebitda_rows.append({
                    "company": company, "scenario": sk,
                    "ebitda_at_risk_low_inr_cr": ND, "ebitda_at_risk_base_inr_cr": ND, "ebitda_at_risk_high_inr_cr": ND,
                    "pct_of_fy2026_ebitda_low": ND, "pct_of_fy2026_ebitda_base": ND, "pct_of_fy2026_ebitda_high": ND,
                    "gross_margin_pct_used": ND, "gross_margin_basis": gm_note,
                })
            continue

        if gm_pct is None:
            for sk in scen_keys:
                ebitda_rows.append({
                    "company": company, "scenario": sk,
                    "ebitda_at_risk_low_inr_cr": ND, "ebitda_at_risk_base_inr_cr": ND, "ebitda_at_risk_high_inr_cr": ND,
                    "pct_of_fy2026_ebitda_low": ND, "pct_of_fy2026_ebitda_base": ND, "pct_of_fy2026_ebitda_high": ND,
                    "gross_margin_pct_used": ND, "gross_margin_basis": gm_note,
                })
            continue

        gm = gm_pct / 100
        for sk in scen_keys:
            if "|" in sk:
                scen, year = sk.split("|")
            else:
                scen, year = sk, ""

            # EBITDA-at-risk as a % of each code's own E (national revenue base),
            # weighted the same way as Part 3's revenue-at-risk %, then applied
            # to the company's own revenue base (not the national E) below.
            ebitda_pct = {"low": 0.0, "base": 0.0, "high": 0.0}
            for code, w in weights.items():
                row = idx.get((code, scen, year))
                if row is None:
                    continue
                e = float(row["E_2025_full_year_usd"])
                if e == 0:
                    continue
                tier_name = row["tier"]
                eps = tier_eps.get(tier_name)
                for lvl in ("low", "base", "high"):
                    alpha_tier = FALLBACK_ALPHA[lvl]
                    eps_col = {"low": "epsilon_low_p25", "base": "epsilon_base_median", "high": "epsilon_high_p75"}[lvl]
                    eps_tier = float(eps[eps_col]) if eps else 0.0
                    price_cut, lost_orders = price_cut_and_lost_orders(row, tier_name, alpha_tier, eps_tier)
                    ebitda_at_risk_pct_of_E = (price_cut + lost_orders * gm) / e
                    ebitda_pct[lvl] += w * ebitda_at_risk_pct_of_E

            rev_usd_m = rev_cfg["value_usd_m"]
            rev_inr_cr = rev_cfg["value_inr_cr"]
            out = {"company": company, "scenario": sk, "gross_margin_pct_used": gm_pct, "gross_margin_basis": gm_note}
            for lvl in ("low", "base", "high"):
                if rev_usd_m is not None:
                    inr_cr = rev_usd_m * ebitda_pct[lvl] * RBI_RATE_31MAR2026 / 100
                else:
                    inr_cr = rev_inr_cr * ebitda_pct[lvl]
                out[f"ebitda_at_risk_{lvl}_inr_cr"] = round(inr_cr, 3)
            ebitda_rows.append(out)

    # add FY2025-26 EBITDA and % of it
    fin = {}
    with open(DATA_DIR / "phase5_financials.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["period_type"] == "Annual" and "2026" in r["period"]:
                fin[r["company"]] = r

    final_rows = []
    for row in ebitda_rows:
        company = row["company"]
        fy26 = fin.get(company)
        ebitda_fy26 = None
        if fy26 and fy26["ebitda_cr"] not in (ND, ""):
            try:
                ebitda_fy26 = float(fy26["ebitda_cr"])
            except ValueError:
                ebitda_fy26 = None
        new_row = dict(row)
        new_row["fy2025_26_ebitda_inr_cr_used"] = ebitda_fy26 if ebitda_fy26 is not None else ND
        for lvl in ("low", "base", "high"):
            key = f"ebitda_at_risk_{lvl}_inr_cr"
            if key in row and row[key] not in (ND, "") and ebitda_fy26:
                new_row[f"pct_of_fy2025_26_ebitda_{lvl}"] = round(100 * row[key] / ebitda_fy26, 2)
            else:
                new_row[f"pct_of_fy2025_26_ebitda_{lvl}"] = ND
        final_rows.append(new_row)

    cols2 = ["company", "scenario", "ebitda_at_risk_low_inr_cr", "ebitda_at_risk_base_inr_cr",
             "ebitda_at_risk_high_inr_cr", "fy2025_26_ebitda_inr_cr_used",
             "pct_of_fy2025_26_ebitda_low", "pct_of_fy2025_26_ebitda_base", "pct_of_fy2025_26_ebitda_high",
             "gross_margin_pct_used", "gross_margin_basis"]
    with open(DATA_DIR / "phase5_ebitda_at_risk.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols2, extrasaction="ignore")
        w.writeheader()
        w.writerows(final_rows)
    print(f"Wrote data/phase5_ebitda_at_risk.csv ({len(final_rows)} rows)")

    print(f"\nRBI rate used: {RBI_RATE_31MAR2026} INR/USD - {RBI_RATE_SOURCE[:80]}...")
    print("\nRevenue at risk (base case, INR cr):")
    for r in rar_rows:
        if r["scenario"] in ("S2_Sec232_15pct_exemptions", "S3_Sec232_25pct_all"):
            print(f"  {r['company']:<14}{r['scenario']:<30}base={r.get('base_inr_cr', r.get('base_usd', ND))}")


if __name__ == "__main__":
    main()
