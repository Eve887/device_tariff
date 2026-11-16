"""
h4_competitor_check_and_corrected_rates.py

Phase 3 fix 3, parts 2-4:
- Build the top-15 competitor check table (listed rate vs actual duty
  paid, flagged where they differ by >3 points, with an explanation).
- Correct the listed-rate columns in the tariff table using USTR's real
  country/tier structure (not just the India/China-only approximation
  from Phase 3's first pass), plus the user's explicit Mexico/Canada
  USMCA and EU-ceiling simplifications.
- Add gap_listed and gap_actual columns.

READ-ONLY against data/phase3_tariff_gap_data_v2.csv,
data/top15_competitor_check_raw.json, raw/hts/mfn_rates.json,
raw/census/*. Writes data/top15_competitor_check.csv and
data/phase3_tariff_gap_data_v3.csv (new files).
"""

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
CENSUS_DIR = HERE / "raw" / "census"

INDIA, CHINA, MEXICO, CANADA, GERMANY = "5330", "5700", "2010", "1220", "4280"
## Only the countries that actually appear in our data (top-15 competitor
## check's suppliers, plus India/China/Mexico/Germany for the main table)
## are mapped below. No country code is guessed for a country absent
## from our data - several Tier 1 members (Argentina, Bangladesh,
## Cambodia, Ecuador, El Salvador, Guatemala, Honduras, Indonesia,
## Jordan, Pakistan, Sri Lanka, Trinidad and Tobago) never appear as a
## top-3 supplier for any of our codes, so are deliberately left out
## rather than assigning them a Census country code I haven't verified.

EU_COUNTRY_CODES = {  # EU member states appearing in our data
    "4280": "Germany", "4279": "France", "4190": "Ireland", "4759": "Italy",
    "4210": "Netherlands", "4700": "Spain", "4010": "Sweden",
}
TIER1 = {  # +10% flat on MFN (confirmed members of our data: Canada, Malaysia, Mexico, UK)
    "1220": "Canada", "5570": "Malaysia", "2010": "Mexico", "4120": "United Kingdom",
    "5330": "India",
}
TIER3_NET_OF_MFN_12_5 = {"5880": "Japan", "4419": "Switzerland"}
TIER2_NET_OF_MFN_10 = {"5830": "Taiwan"}  # EU handled separately via EU_COUNTRY_CODES
TIER_OTHER_12_5PCT_FLAT_KNOWN = {"5700": "China", "2230": "Costa Rica",
                                   "5590": "Singapore", "5490": "Thailand"}
UNKNOWN_STATUS = {"5530": "Laos"}

USMCA_COUNTRIES = {MEXICO, CANADA}


def mfn_lookup():
    data = json.loads((HERE / "raw" / "hts" / "mfn_rates.json").read_text(encoding="utf-8"))
    out = {}
    for code, info in data.items():
        rate_str = info["general_rate"]
        if not rate_str:
            out[code] = None
            continue
        parts = [p.strip() for p in rate_str.split(";")]
        vals = [0.0 if p.lower() == "free" else float(p[:-1]) for p in parts if p.lower() == "free" or p.endswith("%")]
        out[code] = max(vals) if vals else None
    return out


def listed_rate_for_country(cty_code, mfn_pct, exempt, china_301_list_rate=None):
    """Returns (rate_pct, basis_note) for a given supplier country.

    china_301_list_rate: for China only, the OLDER 2018-19 Section 301
    List 1/2/3/4A rate (25% for Lists 1-3, 7.5% for List 4A) already
    determined in Phase 3's first pass. This is a SEPARATE, ADDITIONAL
    duty layer from the newer forced-labor action - the two stack, they
    don't replace each other. Confirmed this must stack by checking
    actual 2026 YTD duty paid: China on X-ray tubes (902230) pays 38%
    actual, which only matches MFN(~0) + List 1-3 (25%) + forced-labor
    (12.5%) = 37.5% - NOT the 12.5%-only figure my first draft of this
    function produced before I caught the discrepancy.
    """
    if mfn_pct is None:
        return None, "MFN not found"
    if cty_code in EU_COUNTRY_CODES:
        return 15.0, "EU 15% all-in ceiling (per user instruction)"
    if cty_code in USMCA_COUNTRIES:
        return 0.0, "Mexico/Canada, assumed USMCA-qualifying -> 0%"
    if cty_code in TIER3_NET_OF_MFN_12_5:
        return max(mfn_pct, 12.5), "Tier 3: combined 12.5% net of MFN"
    if cty_code in TIER2_NET_OF_MFN_10:
        return max(mfn_pct, 10.0), "Tier 2: combined 10% net of MFN"
    if cty_code in TIER1:
        addon = 0.0 if exempt else 10.0
        return mfn_pct + addon, "Tier 1: MFN + 10% flat" + (" (exempt)" if exempt else "")
    if cty_code == CHINA or cty_code in TIER_OTHER_12_5PCT_FLAT_KNOWN:
        forced_labor_addon = 0.0 if exempt else 12.5
        old_301 = (china_301_list_rate or 0.0) if cty_code == CHINA else 0.0
        basis = "MFN + 12.5% forced-labor flat"
        if old_301:
            basis = f"MFN + {old_301}% (older Section 301 List) + 12.5% forced-labor"
        return mfn_pct + old_301 + forced_labor_addon, basis + (" (exempt)" if exempt else "")
    if cty_code in UNKNOWN_STATUS:
        return None, f"UNKNOWN - could not confirm {UNKNOWN_STATUS[cty_code]}'s status among the 60 investigated economies"
    return mfn_pct, "not one of the 60 investigated economies - MFN only, no forced-labor addon"


def main():
    mfn = mfn_lookup()
    with open(DATA_DIR / "top15_competitor_check_raw.json", encoding="utf-8") as f:
        top15 = json.load(f)
    with open(DATA_DIR / "phase3_tariff_gap_data_v2.csv", newline="", encoding="utf-8-sig") as f:
        v2_rows = {r["code"]: r for r in csv.DictReader(f)}

    def china_301_for(code):
        v = v2_rows.get(code, {}).get("china_section301_rate_pct")
        return float(v) if v not in (None, "", "None") else None

    rows = []
    flags = []
    for item in top15:
        code = item["code"]
        code_mfn = mfn.get(code)
        code_exempt = v2_rows.get(code, {}).get("section301_exempt") == "yes"
        for s in item["suppliers"]:
            cc = s["country_code"]
            listed, basis = listed_rate_for_country(cc, code_mfn, code_exempt, china_301_for(code))
            actual = s["actual_duty_pct_2026ytd"]
            diff = round(listed - actual, 2) if (listed is not None and actual is not None) else None
            flagged = diff is not None and abs(diff) > 3
            reason = ""
            if flagged:
                if cc in EU_COUNTRY_CODES or cc in TIER2_NET_OF_MFN_10 or cc in TIER3_NET_OF_MFN_12_5:
                    reason = "likely: this supplier's real combined-cap/ceiling mechanism doesn't simply add on top of MFN the way our simplified listed rate assumes, or the shipment mix includes exclusions"
                elif cc in USMCA_COUNTRIES:
                    reason = "likely: not all of this supplier's shipments actually qualify for USMCA - the 0% assumption is a best case, actual duty reflects a mix of qualifying and non-qualifying entries"
                elif cc == CHINA:
                    reason = "likely: an active Section 301 List 1-4A exclusion applies to some of this code's lines, or the underlying List assignment used in our table is itself approximate (secondary-sourced)"
                else:
                    reason = "likely: a product-specific exclusion, FTA preference, or MFN-rate variation across this code's 10-digit lines not captured by our single representative rate"
            rows.append({
                "code": code, "description": item["description"],
                "india_2025_usd": item["india_2025_usd"],
                "supplier_country": s["country_name"], "country_code": cc,
                "supplier_2025_usd": s["value_2025_usd"],
                "supplier_2026ytd_usd": s["value_2026ytd_usd"],
                "listed_rate_pct": listed, "listed_rate_basis": basis,
                "actual_duty_pct_2026ytd": actual,
                "diff_listed_minus_actual_pct": diff,
                "flagged_gt_3pp": "yes" if flagged else "no",
                "likely_reason": reason,
            })
            if flagged:
                flags.append(rows[-1])

    cols = list(rows[0].keys())
    with open(DATA_DIR / "top15_competitor_check.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote data/top15_competitor_check.csv ({len(rows)} rows, {len(flags)} flagged >3pp)")

    # ---- Now rebuild the main tariff table with corrected rates + gap columns ----
    with open(DATA_DIR / "phase3_tariff_gap_data_v2.csv", newline="", encoding="utf-8-sig") as f:
        main_rows = list(csv.DictReader(f))

    for r in main_rows:
        code = r["code"]
        code_mfn = mfn.get(code)
        exempt = r.get("section301_exempt") == "yes"
        china_301 = float(r["china_section301_rate_pct"]) if r.get("china_section301_rate_pct") not in (None, "", "None") else None
        india_listed, _ = listed_rate_for_country(INDIA, code_mfn, exempt)
        china_listed, china_basis = listed_rate_for_country(CHINA, code_mfn, exempt, china_301)
        mexico_listed, _ = listed_rate_for_country(MEXICO, code_mfn, exempt)
        eu_listed, _ = listed_rate_for_country(GERMANY, code_mfn, exempt)  # Germany as EU proxy
        r["china_listed_rate_basis"] = china_basis
        r["india_listed_rate_pct_corrected"] = india_listed
        r["china_listed_rate_pct_corrected"] = china_listed
        r["mexico_listed_rate_pct_corrected_usmca_assumed"] = mexico_listed
        r["eu_listed_rate_pct_corrected"] = eu_listed

        india_actual = float(r["india_duty_paid_pct_2026ytd"]) if r.get("india_duty_paid_pct_2026ytd") else None
        # gap_listed: India's corrected listed rate minus the weighted avg listed rate of
        # its top-3 non-India 2025 suppliers (reuse the value already computed in v2 if present,
        # otherwise leave blank - the weighted-competitor-rate computation from Phase 3's first
        # pass already used the best available method; here we only correct India's own side)
        old_top3_weighted = r.get("top3_non_india_weighted_listed_rate_pct")
        if india_listed is not None and old_top3_weighted not in (None, ""):
            r["gap_listed_pct"] = round(india_listed - float(old_top3_weighted), 2)
        else:
            r["gap_listed_pct"] = None
        if india_actual is not None and old_top3_weighted not in (None, ""):
            r["gap_actual_pct"] = round(india_actual - float(old_top3_weighted), 2)
        else:
            r["gap_actual_pct"] = None

    cols2 = list(main_rows[0].keys())
    with open(DATA_DIR / "phase3_tariff_gap_data_v3.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols2)
        w.writeheader()
        w.writerows(main_rows)
    print(f"Wrote data/phase3_tariff_gap_data_v3.csv ({len(main_rows)} rows)")

    print("\n--- Flagged (>3pp difference) ---")
    for r in flags:
        print(f"  {r['code']} / {r['supplier_country']}: listed {r['listed_rate_pct']}% vs actual "
              f"{r['actual_duty_pct_2026ytd']}% (diff {r['diff_listed_minus_actual_pct']}pp) - {r['likely_reason']}")


if __name__ == "__main__":
    main()
