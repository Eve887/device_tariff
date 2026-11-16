"""
g2_build_tariff_gap.py

Phase 3, Part 3: build the full tariff-gap table for every code in
final_codes_grouped.csv.

Sources combined:
  - raw/hts/mfn_rates.json (US MFN "general" rate, fetched directly
    from hts.usitc.gov in this session)
  - a hardcoded China Section-301 table transcribed from separate
    research findings (secondary source - hts.cybermaxtools.com,
    since ustr.gov's own exclusion-annex PDFs were not machine-readable
    and the HTS REST API's own additionalDuties field is null even
    where Section 301 clearly applies). Flagged per-row as such.
  - Census (actual duty paid, top suppliers, import values) - read
    directly from raw/census/*, the same way every other step in this
    project has computed these.
  - Flat policy rules supplied by the user for this exercise: India
    +10% forced-labor duty; China +12.5% forced-labor duty; Mexico +10%
    for non-USMCA-qualifying goods; EU 15% all-in ceiling.

READ-ONLY against everything above. Writes data/phase3_tariff_gap_data.csv
(new file; a later script turns this into the requested .xlsx).
"""

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
CENSUS_DIR = HERE / "raw" / "census"
INDIA, CHINA, MEXICO, GERMANY = "5330", "5700", "2010", "4280"
INDIA_FORCED_LABOR_ADDON = 10.0
CHINA_FORCED_LABOR_ADDON = 12.5
MEXICO_NON_USMCA_ADDON = 10.0
EU_CEILING = 15.0

# China Section 301 list -> rate. Source: separate research step, using
# hts.cybermaxtools.com (third-party aggregator, NOT ustr.gov/hts.usitc.gov
# directly - flagged explicitly per the user's "log it, don't guess" rule).
SECTION301_RATE = {"List 1": 25.0, "List 2": 25.0, "List 3": 25.0, "List 4A": 7.5,
                    "List 4B": 0.0, "Four-Year-Review": 100.0, "none": 0.0}

# code -> (list_or_note, confidence_note)
CHINA_SECTION301 = {
    "300510": ("none", "clean per secondary source"), "300590": ("none", "clean"),
    "300610": ("none", "clean"), "300620": ("UNKNOWN", "not researched - not an EPCMD code"),
    "300630": ("none", "clean"), "300640": ("none", "clean"), "300650": ("none", "clean"),
    "300660": ("none", "clean"), "300670": ("none", "clean"), "300691": ("none", "clean"),
    "382211": ("none", "clean"), "382212": ("none", "clean"), "382213": ("none", "clean"),
    "401410": ("none", "clean"),
    "401512": ("Four-Year-Review", "MIXED at 8-digit level: 'medical/surgical gloves' line = Four-Year-Review +100%; 'other' line = List 3 +25% - using the medical-gloves line's rate since that's what this code represents here"),
    "842310": ("List 4B", "suspended/no extra duty per source"),
    "900130": ("List 4A", ""), "900150": ("List 4A", ""),
    "901811": ("List 1", ""), "901812": ("List 1", ""), "901813": ("List 1", ""),
    "901814": ("List 1", ""), "901819": ("List 1", ""), "901820": ("List 1", ""),
    "901831": ("Four-Year-Review", "separate 2024 action, not a List 1-4A number"),
    "901832": ("Four-Year-Review", "separate 2024 action, not a List 1-4A number"),
    "901839": ("none", "clean"), "901841": ("none", "clean"), "901849": ("none", "clean"),
    "901850": ("none", "clean"),
    "901890": ("MIXED", "~4 of 10 US lines on List 1 (optical instr, anesthetic, electro-surgical, other therapeutic/dialysis); ~6 clean (mirrors, stethoscopes, sphygmomanometers, defibrillators+parts, other) - too mixed to assign one rate to the whole HS6, left UNKNOWN"),
    "901910": ("none", "clean"), "901920": ("none", "clean"), "902000": ("none", "clean, duty varies by MFN only"),
    "902110": ("none", "clean"), "902121": ("none", "clean"), "902129": ("none", "clean"),
    "902131": ("none", "clean"), "902139": ("none", "clean"), "902140": ("none", "clean"),
    "902150": ("List 1", ""), "902190": ("none", "clean"),
    "902212": ("List 1", ""), "902213": ("List 1", ""), "902214": ("List 1", ""),
    "902219": ("List 1", ""), "902221": ("List 1", ""),
    "902229": ("MIXED", "mostly List 1, one line clean"),
    "902230": ("List 1", ""),
    "902290": ("MIXED", "mostly List 1, one line clean"),
    "902511": ("none", "clean"),
    "9025198010": ("List 2", "inherited from 8-digit parent 9025.19.80"),
    "9025198020": ("List 2", "inherited from 8-digit parent 9025.19.80"),
    "902710": ("MIXED", "List 2 and List 3 across its lines"),
    "902720": ("List 1", ""), "902730": ("List 1", ""),
    "902750": ("List 1", ""),
    "902790": ("MIXED", "mostly List 1, one List 3, one List 4A"),
    "9402100000": ("none", "clean"), "940290": ("none", "clean"),
    "961900": ("UNKNOWN", "not researched"),
    "6210105010": ("List 4A", "per fork's research on 621010's 10-digit lines; source also noted '2 product exclusions may apply', unspecified which"),
    "6210105090": ("List 4A", "same as 6210105010"),
}


def parse_pct(rate_str):
    """Turn 'Free' / '5%' / '14%; Free' into a single float (max of any
    range found) or None if blank/varies-with-no-clear-number."""
    if not rate_str:
        return None
    if rate_str.strip().lower() == "free":
        return 0.0
    parts = [p.strip() for p in rate_str.split(";")]
    vals = []
    for p in parts:
        if p.lower() == "free":
            vals.append(0.0)
        elif p.endswith("%"):
            try:
                vals.append(float(p[:-1]))
            except ValueError:
                pass
    return max(vals) if vals else None


def load_mfn():
    data = json.loads((HERE / "raw" / "hts" / "mfn_rates.json").read_text(encoding="utf-8"))
    return {code: info["general_rate"] for code, info in data.items()}


def census_full_year(code, level, period, cty_code=None):
    raw_file = CENSUS_DIR / f"{code}_{period}.json"
    if not raw_file.exists():
        return None
    saved = json.loads(raw_file.read_text(encoding="utf-8"))
    if saved["status"] != "ok" or not saved["rows"]:
        return {"value": 0, "duty": 0, "suppliers": [], "world": 0}
    header, *records = saved["rows"]
    world = 0
    target_val = target_duty = 0
    suppliers = []
    for rec in records:
        r = dict(zip(header, rec))
        val = int(r.get("CON_VAL_YR") or 0)
        duty = int(r.get("CAL_DUT_YR") or 0)
        if "TOTAL FOR ALL" in (r.get("CTY_NAME") or "").upper():
            world = val
        elif r.get("SUMMARY_LVL") == "DET":
            suppliers.append((val, (r.get("CTY_NAME") or "").title(), r.get("CTY_CODE")))
            if cty_code and r.get("CTY_CODE") == cty_code:
                target_val, target_duty = val, duty
    return {"value": target_val if cty_code else world, "duty": target_duty,
            "world": world, "suppliers": suppliers}


def pct(a, b):
    return round(100 * a / b, 2) if b else None


def main():
    mfn_rates = load_mfn()
    with open(DATA_DIR / "final_codes_grouped.csv", newline="", encoding="utf-8-sig") as f:
        codes = list(csv.DictReader(f))

    rows = []
    not_found_log = []

    for c in codes:
        code, level, desc, group = c["code"], c["level"], c["description"], c["group"]
        mfn_str = mfn_rates.get(code, "")
        mfn_pct = parse_pct(mfn_str)
        if mfn_pct is None:
            not_found_log.append(f"{code}: MFN rate not found/not parseable ('{mfn_str}')")

        # --- China ---
        china_list, china_note = CHINA_SECTION301.get(code, ("UNKNOWN", "not in lookup table"))
        china_301_rate = SECTION301_RATE.get(china_list)
        if china_301_rate is None:
            not_found_log.append(f"{code}: China Section 301 list UNKNOWN/MIXED ({china_note})")

        india_listed = (mfn_pct + INDIA_FORCED_LABOR_ADDON) if mfn_pct is not None else None
        china_listed = (mfn_pct + china_301_rate + CHINA_FORCED_LABOR_ADDON) if (mfn_pct is not None and china_301_rate is not None) else None
        mexico_listed_note = f"MFN {mfn_str or 'unknown'} + 10% only for non-USMCA-qualifying goods"

        # --- Census-derived: 2025 full year, 2026 Jan-Sep YTD ---
        y2025 = census_full_year(code, level, "2025-12")
        y2026 = census_full_year(code, level, "2026-09")
        india_2025 = census_full_year(code, level, "2025-12", INDIA)
        china_2025 = census_full_year(code, level, "2025-12", CHINA)
        mexico_2025 = census_full_year(code, level, "2025-12", MEXICO)
        germany_2025 = census_full_year(code, level, "2025-12", GERMANY)
        india_2026 = census_full_year(code, level, "2026-09", INDIA)

        top3 = sorted(y2025["suppliers"], reverse=True)[:3] if y2025 else []
        top3_non_india = [(v, n, cc) for v, n, cc in top3 if cc != INDIA][:3]
        top3_weighted_rate = None
        if top3_non_india and sum(v for v, n, cc in top3_non_india) > 0:
            total_v = sum(v for v, n, cc in top3_non_india)
            parts = []
            for v, n, cc in top3_non_india:
                if cc == CHINA:
                    r = china_listed
                elif cc == MEXICO:
                    r = mfn_pct  # assume USMCA-qualifying as the base case; see note column
                else:
                    r = mfn_pct
                if r is not None:
                    parts.append(v * r)
            if parts:
                top3_weighted_rate = round(sum(parts) / total_v, 2)

        india_gap = round(india_listed - top3_weighted_rate, 2) if (india_listed is not None and top3_weighted_rate is not None) else None

        rows.append({
            "code": code, "level": level, "description": desc, "group": group,
            "us_mfn_rate_str": mfn_str, "us_mfn_pct": mfn_pct,
            "india_forced_labor_addon_pct": INDIA_FORCED_LABOR_ADDON,
            "india_listed_rate_pct": india_listed,
            "china_section301_list": china_list, "china_section301_note": china_note,
            "china_section301_rate_pct": china_301_rate,
            "china_forced_labor_addon_pct": CHINA_FORCED_LABOR_ADDON,
            "china_listed_rate_pct": china_listed,
            "mexico_note": mexico_listed_note,
            "mexico_usmca_share_note": "not available from this Census endpoint (no FTA-qualification field in the international trade timeseries API)",
            "eu_ceiling_pct": EU_CEILING,
            "india_duty_paid_pct_2025": pct(india_2025["duty"], india_2025["value"]) if india_2025 else None,
            "india_duty_paid_pct_2026ytd": pct(india_2026["duty"], india_2026["value"]) if india_2026 else None,
            "china_duty_paid_pct_2025": pct(china_2025["duty"], china_2025["value"]) if china_2025 else None,
            "mexico_duty_paid_pct_2025": pct(mexico_2025["duty"], mexico_2025["value"]) if mexico_2025 else None,
            "germany_duty_paid_pct_2025": pct(germany_2025["duty"], germany_2025["value"]) if germany_2025 else None,
            "all_countries_duty_paid_pct_2025": pct(y2025["duty"], y2025["world"]) if y2025 else None,
            "top3_suppliers_2025": "; ".join(f"{n} {pct(v, y2025['world'])}%" for v, n, cc in top3) if y2025 else "",
            "top3_non_india_weighted_listed_rate_pct": top3_weighted_rate,
            "india_tariff_gap_pct": india_gap,
            "us_imports_from_india_2025_usd": india_2025["value"] if india_2025 else None,
            "us_imports_from_india_2026ytd_usd": india_2026["value"] if india_2026 else None,
            "india_share_of_us_market_2025_pct": pct(india_2025["value"], y2025["world"]) if (india_2025 and y2025) else None,
        })

    columns = list(rows[0].keys())
    with open(DATA_DIR / "phase3_tariff_gap_data.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote data/phase3_tariff_gap_data.csv ({len(rows)} rows)")
    print(f"\n--- Rates/classifications not found or unresolved ({len(not_found_log)}) ---")
    for line in not_found_log:
        print(" ", line)


if __name__ == "__main__":
    main()
