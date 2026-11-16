"""
e2_build_final_checks.py

Part 4: builds data/phase2_final_checks.txt with the reconciliation,
Jan-Sep country comparison, India-by-product-group breakdown, the
HOLDS/DOES-NOT-HOLD verdict, and the small-code list.

READ-ONLY against raw/census/*, final_codes.csv, lab_instruments_codes.csv,
data/phase2_final_summary.csv. Writes data/phase2_final_checks.txt only.
"""

import csv
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
CENSUS_DIR = HERE / "raw" / "census"
INDIA, CHINA, MEXICO = "5330", "5700", "2010"
EPCMD_TARGET = 782_570_000


def load_code_levels(fname):
    with open(DATA_DIR / fname, newline="", encoding="utf-8-sig") as f:
        return [(r["code"], r["level"]) for r in csv.DictReader(f)]


def load_country_value(code, period, cty_code):
    """Return (value, duty) for a given country code, or for 'WORLD'."""
    raw_file = CENSUS_DIR / f"{code}_{period}.json"
    if not raw_file.exists():
        return None
    saved = json.loads(raw_file.read_text(encoding="utf-8"))
    if saved["status"] != "ok" or not saved["rows"]:
        return (0, 0)
    header, *records = saved["rows"]
    for rec in records:
        r = dict(zip(header, rec))
        if cty_code == "WORLD":
            if "TOTAL FOR ALL" in (r.get("CTY_NAME") or "").upper():
                return (int(r.get("CON_VAL_YR") or 0), int(r.get("CAL_DUT_YR") or 0))
        elif r.get("CTY_CODE") == cty_code and r.get("SUMMARY_LVL") == "DET":
            return (int(r.get("CON_VAL_YR") or 0), int(r.get("CAL_DUT_YR") or 0))
    return (0, 0)


def fy2425(codes):
    total = 0
    for code, level in codes:
        v_dec24 = load_country_value(code, "2024-12", INDIA)
        v_mar24 = load_country_value(code, "2024-03", INDIA)
        v_mar25 = load_country_value(code, "2025-03", INDIA)
        if None in (v_dec24, v_mar24, v_mar25):
            continue
        total += v_dec24[0] - v_mar24[0] + v_mar25[0]
    return total


def jan_sep_totals(codes, period, cty_code):
    val = duty = 0
    for code, level in codes:
        r = load_country_value(code, period, cty_code)
        if r is None:
            continue
        val += r[0]
        duty += r[1]
    return val, duty


def pct_change(old, new):
    return round(100 * (new - old) / old, 1) if old else None


def duty_pct(duty, val):
    return round(100 * duty / val, 2) if val else None


def main():
    final_codes = load_code_levels("final_codes.csv")
    lab_codes = load_code_levels("lab_instruments_codes.csv")
    all_codes = final_codes + lab_codes

    lines = []

    # ---- 4a: FY2024-25 reconciliation ----
    fy_final = fy2425(final_codes)
    fy_with_lab = fy2425(all_codes)
    lines.append("=== 4a. FY2024-25 reconciliation (April 2024 - March 2025) ===")
    lines.append(f"final_codes.csv only: US imports from India = ${fy_final:,}")
    gap1 = EPCMD_TARGET - fy_final
    lines.append(f"  vs EPCMD $782,570,000: gap = ${gap1:,} ({100*gap1/EPCMD_TARGET:.1f}% of target)")
    lines.append(f"final_codes.csv + lab_instruments_codes.csv: US imports from India = ${fy_with_lab:,}")
    gap2 = EPCMD_TARGET - fy_with_lab
    lines.append(f"  vs EPCMD $782,570,000: gap = ${gap2:,} ({100*gap2/EPCMD_TARGET:.1f}% of target)")
    lines.append("")

    # ---- 4b: Jan-Sep comparison 2024/2025/2026, India/China/Mexico/All countries ----
    lines.append("=== 4b. January-September comparison, 2024 vs 2025 vs 2026 (final_codes.csv, 67 codes) ===")
    periods = {"2024": "2024-09", "2025": "2025-09", "2026": "2026-09"}
    groups = {"India": INDIA, "China": CHINA, "Mexico": MEXICO, "All countries": "WORLD"}
    country_totals = {}
    for gname, gcode in groups.items():
        vals = {}
        for y, p in periods.items():
            v, d = jan_sep_totals(final_codes, p, gcode)
            vals[y] = (v, d)
        country_totals[gname] = vals
        chg_24_25 = pct_change(vals["2024"][0], vals["2025"][0])
        chg_25_26 = pct_change(vals["2025"][0], vals["2026"][0])
        lines.append(f"{gname}:")
        lines.append(f"  2024 Jan-Sep: ${vals['2024'][0]:,}  (duty {duty_pct(vals['2024'][1], vals['2024'][0])}%)")
        lines.append(f"  2025 Jan-Sep: ${vals['2025'][0]:,}  (duty {duty_pct(vals['2025'][1], vals['2025'][0])}%)  change vs 2024: {chg_24_25}%")
        lines.append(f"  2026 Jan-Sep: ${vals['2026'][0]:,}  (duty {duty_pct(vals['2026'][1], vals['2026'][0])}%)  change vs 2025: {chg_25_26}%")
    lines.append("")

    # ---- 4c: 2025-to-2026 India comparison by product group ----
    lines.append("=== 4c. India Jan-Sep 2025 vs 2026, by product group (final_codes.csv) ===")
    # Prefer our own hs6_codes.csv group, except "Candidate" - that was
    # just an investigation-phase placeholder label, not a real product
    # category, so for those codes fall back to EPCMD's category instead.
    group_of = {}
    with open(HERE / "hs6_codes.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["group"] != "Candidate":
                group_of[r["hs6"]] = r["group"]
    with open(DATA_DIR / "epcmd_151_codes.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            group_of.setdefault(r["hs6"], r["category"])

    by_group_codes = defaultdict(list)
    for code, level in final_codes:
        g = group_of.get(code[:6], "Unknown")
        by_group_codes[g].append((code, level))

    group_rows = []
    for g, glist in sorted(by_group_codes.items()):
        v25, _ = jan_sep_totals(glist, "2025-09", INDIA)
        v26, _ = jan_sep_totals(glist, "2026-09", INDIA)
        chg = pct_change(v25, v26)
        group_rows.append((g, v25, v26, chg))
    group_rows.sort(key=lambda r: r[1], reverse=True)
    for g, v25, v26, chg in group_rows:
        lines.append(f"  {g:<22} 2025: ${v25:>14,}   2026: ${v26:>14,}   change: {chg}%")
    lines.append("")

    # ---- 4d: verdict ----
    india_chg = pct_change(country_totals["India"]["2025"][0], country_totals["India"]["2026"][0])
    all_chg = pct_change(country_totals["All countries"]["2025"][0], country_totals["All countries"]["2026"][0])
    diff = (all_chg - india_chg) if (india_chg is not None and all_chg is not None) else None
    verdict = "HOLDS" if (diff is not None and diff >= 5) else "DOES NOT HOLD"
    lines.append("=== 4d. Verdict ===")
    lines.append(f'"{verdict}": India\'s 2025-to-2026 Jan-Sep change = {india_chg}%, '
                 f"all countries' change = {all_chg}% "
                 f"(India's fall is {abs(india_chg) - abs(all_chg):.1f} points "
                 f"{'larger' if abs(india_chg) > abs(all_chg) else 'smaller'} than all countries')")
    lines.append("")

    # ---- 4e: code count and small-value codes ----
    lines.append("=== 4e. Code count and small-value codes ===")
    lines.append(f"Number of codes in final_codes.csv: {len(final_codes)}")
    with open(DATA_DIR / "phase2_final_summary.csv", newline="", encoding="utf-8-sig") as f:
        summary = list(csv.DictReader(f))
    small = [r for r in summary if r["year"] == "2025"
             and r["us_imports_from_india_usd"] not in ("", None)
             and int(r["us_imports_from_india_usd"]) < 1_000_000]
    lines.append(f"Codes where India sold under $1M to the US in 2025: {len(small)}")
    for r in sorted(small, key=lambda r: int(r["us_imports_from_india_usd"])):
        lines.append(f"  {r['code']} ({r['level']}, {r['product_group']}): "
                     f"${int(r['us_imports_from_india_usd']):,} - {r['description'][:60]}")

    text = "\n".join(lines)
    (DATA_DIR / "phase2_final_checks.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
