"""
step3_checks_and_summary.py

WHAT IT DOES
    Reads the two CSV files from step 1 and step 2 and builds one summary
    table per product code and year, plus a list of warnings to look at.

WHAT YOU GET
    data/phase2_summary.csv  - one row per code x year with:
        us_imports_world_usd       total US imports of that code (all countries)
        us_imports_from_india_usd  Exposure E (US-reported, imports for consumption)
        india_share_of_us_pct      India's share of the US market for that code
        top3_suppliers             the three biggest suppliers to the US
        india_exports_world_usd    India's exports of that code to all countries
        india_exports_usa_usd      India's exports to the US (India-reported)
        us_dependence_pct          share of India's exports that go to the US
        mirror_gap_pct             how far the US and Indian figures disagree
        india_effective_duty_pct   duty the US actually charged on Indian goods
        india_imports_world_usd    India's imports of that code (View B)
        india_imports_usa_usd      India's imports from the US (View B)
        flag                       short warnings (explained in phase2_checks.txt)
    data/phase2_checks.txt   - plain-English results of every check

HOW TO RUN
    py step3_checks_and_summary.py
"""

import csv
from collections import defaultdict

from common import DATA_DIR, log, read_codes, write_csv

LOG = "step3_checks"
INDIA_CENSUS_CODE = "5330"         # Census country code for India
EPCMD_FY25_USD = 782_570_000       # EPCMD: device exports to the US, FY 2024-25
MIN_EXPOSURE_USD = 1_000_000       # plan rule: keep a code if India > $1 million


def read(name):
    path = DATA_DIR / name
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def pct(a, b):
    return round(100 * a / b, 1) if b else ""


def main():
    us = read("us_imports_by_country.csv")
    ind = read("india_trade.csv")
    checks = []
    if not us:
        checks.append("No US data found. Run step 1 first.")
    if not ind:
        checks.append("No India data found. Run step 2 first.")

    # ---- Organise US data: (hs6, year) -> world total, India, country list
    us_world, us_india, us_duty_india = {}, {}, {}
    us_countries = defaultdict(list)
    months = {}
    for r in us:
        k = (r["hs6"], r["year"])
        months[r["year"]] = r["months_covered"]
        value = int(r["imports_for_consumption_usd"] or 0)
        if "TOTAL FOR ALL" in r["cty_name"].upper():
            us_world[k] = value
        elif r["summary_lvl"] == "DET":          # single countries only
            us_countries[k].append((value, r["cty_name"].title()))
            if r["cty_code"] == INDIA_CENSUS_CODE:
                us_india[k] = value
                us_duty_india[k] = int(r["calculated_duty_usd"] or 0)

    # ---- Organise India data: (flow, hs6, year, partner) -> value
    ind_val = {}
    for r in ind:
        ind_val[(r["flow"], r["hs6"], str(r["year"]), r["partner"])] = float(r["value_usd"] or 0)

    def iv(flow, hs6, year, partner):
        return ind_val.get((flow, hs6, year, partner), 0.0)

    years = sorted({r["year"] for r in us} | {str(r["year"]) for r in ind})
    rows = []
    for code in read_codes():
        hs6 = code["hs6"]
        for y in years:
            k = (hs6, y)
            world = us_world.get(k, 0)
            india = us_india.get(k, 0)
            top3 = sorted(us_countries.get(k, []), reverse=True)[:3]
            ex_world = iv("India exports", hs6, y, "World")
            ex_usa = iv("India exports", hs6, y, "USA")
            mirror = pct(india - ex_usa, ex_usa) if ex_usa else ""
            flags = []
            if world and india < MIN_EXPOSURE_USD:
                flags.append("SMALL")           # India sells < $1m to the US
            if mirror != "" and abs(mirror) > 25:
                flags.append("MIRROR_GAP")      # US and India disagree by > 25%
            if ex_world and ex_usa > ex_world:
                flags.append("CHECK_INDIA_DATA")
            rows.append({
                "hs6": hs6, "group": code["group"], "description": code["description"],
                "year": y, "us_months_covered": months.get(y, ""),
                "us_imports_world_usd": world,
                "us_imports_from_india_usd": india,
                "india_share_of_us_pct": pct(india, world),
                "top3_suppliers": "; ".join(f"{n} {pct(v, world)}%" for v, n in top3),
                "india_exports_world_usd": round(ex_world),
                "india_exports_usa_usd": round(ex_usa),
                "us_dependence_pct": pct(ex_usa, ex_world),
                "mirror_gap_pct": mirror,
                "india_effective_duty_pct": pct(us_duty_india.get(k, 0), india),
                "india_imports_world_usd": round(iv("India imports", hs6, y, "World")),
                "india_imports_usa_usd": round(iv("India imports", hs6, y, "USA")),
                "india_imports_china_usd": round(iv("India imports", hs6, y, "China")),
                "flag": " ".join(flags),
            })
    if rows:
        write_csv(DATA_DIR / "phase2_summary.csv", rows, list(rows[0].keys()))

    # ---- Check 1: our India-to-US total vs the EPCMD figure
    for y in years:
        total = sum(v for (h, yy), v in us_india.items() if yy == y)
        if total:
            checks.append(
                f"Check 1, {y} ({months.get(y, '?')} months): US imports from India "
                f"across our {len(read_codes())} codes = ${total / 1e6:,.1f} million.")
    checks.append(
        f"Compare with EPCMD FY 2024-25 = ${EPCMD_FY25_USD / 1e6:,.2f} million "
        "(April 2024 to March 2025, India-reported). Calendar 2024 and 2025 should "
        "sit near it. A result far below it means a missing code; far above means "
        "our list includes codes EPCMD does not count as devices.")

    # ---- Check 2: mirror gaps
    gaps = [r for r in rows if "MIRROR_GAP" in r["flag"]]
    checks.append(
        f"Check 2: {len(gaps)} code-years where US-reported imports from India and "
        "India-reported exports to the US differ by more than 25%. Some gap is "
        "normal (shipping time across year-end, freight in the value, goods "
        "routed via other countries). We use the US figure as Exposure because "
        "duty is charged on it.")

    # ---- Check 3: codes too small to keep
    latest_full = max((y for y in years if months.get(y) == "12"), default=None)
    if latest_full:
        small = [r["hs6"] for r in rows if r["year"] == latest_full and "SMALL" in r["flag"]]
        checks.append(
            f"Check 3: in {latest_full}, {len(small)} code(s) had US imports from India "
            f"below $1 million: {', '.join(small) or 'none'}. Per the plan these drop "
            "out of View A unless they matter for View B or C.")

    # ---- Check 4: did the duty actually charged rise after the 10% started?
    for y in years:
        val = sum(v for (h, yy), v in us_india.items() if yy == y)
        duty = sum(v for (h, yy), v in us_duty_india.items() if yy == y)
        if val:
            checks.append(f"Check 4, {y}: duty charged on Indian device imports = "
                          f"{100 * duty / val:.2f}% of value.")
    checks.append(
        "Expect roughly 0-2% in 2022-2024 (MFN only), higher in 2025 "
        "(reciprocal tariffs from August), and in 2026 a mix of Section 122 "
        "(Feb-Jul) and Section 301 (from 24 July). If 2026 stays near 0%, Census "
        "may not include Chapter 99 duties in its calculated duty - note it and "
        "use the Rulebook rates instead.")

    text = "\n\n".join(checks)
    (DATA_DIR / "phase2_checks.txt").write_text(text, encoding="utf-8")
    log("Step 3 results:\n" + text, LOG)
    log(f"Wrote data/phase2_summary.csv ({len(rows)} rows) and data/phase2_checks.txt", LOG)


if __name__ == "__main__":
    main()
