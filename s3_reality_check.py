"""
s3_reality_check.py

Phase 5, Part 5: reality check. Compares each company's reported
US/Americas revenue change (H1 FY2026-27 i.e. Apr-Sep 2026 vs H1
FY2025-26 i.e. Apr-Sep 2025, or the nearest disclosed periods) against
India's own US-bound trade change for that company's mapped HS6 codes
over the same months (from raw/census_monthly/, India's value to the
"TOTAL FOR ALL" world figure is NOT what we want here - we want
India's exports TO THE US specifically, i.e. the CTY_CODE=5330 rows in
the Census import data ARE already "imports BY the US FROM India", so
the "India value" field in these files already IS India-to-US trade -
same convention as every earlier phase in this project).

Honesty constraint carried through: NONE of the 5 companies disclose a
precise, directly-comparable US-specific revenue change for exactly
this window. What IS shown on the "reported" side is the closest
available disclosed figure, with its real basis stated plainly (e.g.
"international revenue growth, not US-specific" or "quarterly, not
H1") - never silently treated as if it were the real US figure.
TARSONS has no mapped codes, so the trade-side comparison is not
computable for it either.

READ-ONLY against data/phase5_product_mapping.csv,
raw/census_monthly/*. Writes data/phase5_reality_check.csv (new file).
"""

import csv
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
MONTHLY_DIR = HERE / "raw" / "census_monthly"
INDIA = "5330"
ND = "not disclosed"

H1_FY2526 = [f"2025-{m:02d}" for m in range(4, 10)]  # Apr-Sep 2025
H1_FY2627 = [f"2026-{m:02d}" for m in range(4, 10)]  # Apr-Sep 2026

# Reported figures found via research - see logs/step1_progress_log.md
# and data/phase5_management_comments.csv for full sourcing. Each entry
# states its REAL basis so it is never mistaken for a true US-specific,
# H1-matched figure.
REPORTED = {
    "POLYMED": {
        "value_pct": "+35.0 (Q2 FY27 only, not H1; this is whole INTERNATIONAL revenue growth [Europe+RoW combined], NOT US-specific)",
        "source": "WebSearch of investywise.com coverage of Poly Medicure Q2 FY27 results",
    },
    "LAXMIDENTL": {
        "value_pct": "+32 (Q2 FY27 only, not H1; this is INTERNATIONAL dental-lab revenue growth, NOT US-specific - whole lab business, not isolated to the US)",
        "source": "WebSearch coverage of Laxmi Dental Q2 FY27 earnings call commentary",
    },
    "TARSONS": {
        "value_pct": "+33 (H1 FY27 vs H1 FY26 - correct window, but this is EXPORT revenue to ALL countries, NOT US-specific; no HS6 code mapping exists for Tarsons anyway, so no trade-side comparison is possible regardless)",
        "source": "WebSearch of multibagg.ai/gurufocus.com coverage of Tarsons Q2 FY27 results ('Export revenue... growing 37% in Q2 FY27 and 33% in H1 FY27')",
    },
    "SMT": {
        "value_pct": ND,
        "source": "SMT listed only 23 Oct 2026 - no post-listing quarterly results exist yet for any period, let alone H1 FY27 vs H1 FY26",
    },
    "TRANSLUMINA": {
        "value_pct": ND,
        "source": "Integris Medtech not confirmed listed as of 15 Nov 2026 - no quarterly results exist for H1 FY27 vs H1 FY26 (only the DRHP's Q1 FY26 data point exists, a single quarter, not H1, and whole-company not Translumina-segment)",
    },
}

COMPANY_WEIGHTS = {
    "POLYMED": {"901831": 0.1767, "901832": 0.1767, "901839": 0.1767, "901890": 0.47},
    "LAXMIDENTL": {"902121": 0.5, "902129": 0.5},
    "TARSONS": {},
    "SMT": {"902190": 0.3293, "901839": 0.5172, "902139": 0.1535},
    "TRANSLUMINA": {"902190": 0.2599, "901839": 0.2599, "902139": 0.4802},
}


def india_to_us_value(code, months):
    """Sum of India's export value TO THE US for one HS6 code across months.
    (CTY_CODE=5330, SUMMARY_LVL=DET, CON_VAL_MO - this IS the US-side import-
    from-India figure, i.e. India-to-US trade, same convention as every prior
    phase in this project.)"""
    total = 0
    for m in months:
        f = MONTHLY_DIR / f"{code}_{m}.json"
        if not f.exists():
            continue
        saved = json.loads(f.read_text(encoding="utf-8"))
        if saved["status"] != "ok" or not saved["rows"]:
            continue
        header, *records = saved["rows"]
        for rec in records:
            r = dict(zip(header, rec))
            if r.get("CTY_CODE") == INDIA and r.get("SUMMARY_LVL") == "DET":
                total += int(r.get("CON_VAL_MO") or 0)
    return total


def main():
    rows = []
    for company, weights in COMPANY_WEIGHTS.items():
        reported = REPORTED[company]
        if not weights:
            rows.append({
                "company": company,
                "h1_fy2526_india_to_us_usd": ND, "h1_fy2627_india_to_us_usd": ND,
                "trade_pct_change": ND,
                "reported_pct_change": reported["value_pct"], "reported_basis_and_source": reported["source"],
                "match_assessment": "NOT COMPUTABLE - no HS6 codes map to this company's products",
            })
            continue

        v_old = v_new = 0.0
        for code, w in weights.items():
            v_old += w * india_to_us_value(code, H1_FY2526)
            v_new += w * india_to_us_value(code, H1_FY2627)
        trade_pct = ((v_new - v_old) / v_old * 100) if v_old else None

        match_note = (
            f"Reported figure is NOT a like-for-like US-specific H1 number (see basis) - "
            f"a numeric 'match/mismatch' verdict would overstate precision that doesn't exist here. "
            f"Shown side-by-side for context only."
        )
        if reported["value_pct"] == ND:
            match_note = "NOT COMPARABLE - company has no reported figure for this window at all"

        rows.append({
            "company": company,
            "h1_fy2526_india_to_us_usd": round(v_old),
            "h1_fy2627_india_to_us_usd": round(v_new),
            "trade_pct_change": round(trade_pct, 2) if trade_pct is not None else ND,
            "reported_pct_change": reported["value_pct"], "reported_basis_and_source": reported["source"],
            "match_assessment": match_note,
        })

    with open(DATA_DIR / "phase5_reality_check.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote data/phase5_reality_check.csv ({len(rows)} rows)\n")
    for r in rows:
        print(f"{r['company']:<14} trade%={r['trade_pct_change']!s:<10} reported={str(r['reported_pct_change'])[:70]}")


if __name__ == "__main__":
    main()
