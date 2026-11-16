"""
h5_core_headline_numbers.py

Phase 3 fix 4: re-run the headline numbers on core_device_codes.csv
(60 codes) only, plus a repeat with pharma-like and hygiene codes
added back in (63 codes total = final_codes_grouped.csv) for
comparison.

READ-ONLY against core_device_codes.csv, pharma_like_codes.csv,
hygiene_codes.csv, final_codes_grouped.csv, raw/census_monthly/*.
Writes data/phase3_headline_core.txt (new file) and prints the same
content.
"""

import csv
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
MONTHLY_DIR = HERE / "raw" / "census_monthly"
INDIA, CHINA, MEXICO = "5330", "5700", "2010"


def load_codes(fname):
    with open(DATA_DIR / fname, newline="", encoding="utf-8-sig") as f:
        return [(r["code"], r["level"]) for r in csv.DictReader(f)]


def month_values(code, period):
    raw_file = MONTHLY_DIR / f"{code}_{period}.json"
    if not raw_file.exists():
        return None
    saved = json.loads(raw_file.read_text(encoding="utf-8"))
    out = {"india": (0, 0), "china": (0, 0), "mexico": (0, 0), "world": (0, 0)}
    if saved["status"] != "ok" or not saved["rows"]:
        return out
    header, *records = saved["rows"]
    for rec in records:
        r = dict(zip(header, rec))
        val = int(r.get("CON_VAL_MO") or 0)
        duty = int(r.get("CAL_DUT_MO") or 0)
        if "TOTAL FOR ALL" in (r.get("CTY_NAME") or "").upper():
            out["world"] = (val, duty)
        elif r.get("SUMMARY_LVL") == "DET":
            if r.get("CTY_CODE") == INDIA:
                out["india"] = (val, duty)
            elif r.get("CTY_CODE") == CHINA:
                out["china"] = (val, duty)
            elif r.get("CTY_CODE") == MEXICO:
                out["mexico"] = (val, duty)
    return out


def months_in(year, start, end):
    return [f"{year}-{m:02d}" for m in range(start, end + 1)]


def sum_group(codes, months, key):
    val = duty = 0
    for m in months:
        for code, level in codes:
            r = month_values(code, m)
            if r is None:
                continue
            v, d = r[key]
            val += v
            duty += d
    return val, duty


def pct_change(old, new):
    return round(100 * (new - old) / old, 1) if old else None


def duty_pct(duty, val):
    return round(100 * duty / val, 2) if val else None


def run_headline(codes, label, lines):
    lines.append(f"=== Headline numbers: {label} ({len(codes)} codes) ===\n")

    # 4a: Jan-Sep 2024/2025/2026, India/China/Mexico/All countries
    periods = {"2024": months_in(2024, 1, 9), "2025": months_in(2025, 1, 9), "2026": months_in(2026, 1, 9)}
    lines.append("--- 4a. Jan-Sep comparison ---")
    group_vals = {}
    for gname, key in (("India", "india"), ("China", "china"), ("Mexico", "mexico"), ("All countries", "world")):
        vals = {}
        for y, months in periods.items():
            vals[y] = sum_group(codes, months, key)
        group_vals[gname] = vals
        chg_24_25 = pct_change(vals["2024"][0], vals["2025"][0])
        chg_25_26 = pct_change(vals["2025"][0], vals["2026"][0])
        lines.append(f"{gname}:")
        lines.append(f"  2024 Jan-Sep: ${vals['2024'][0]:,}  (duty {duty_pct(vals['2024'][1], vals['2024'][0])}%)")
        lines.append(f"  2025 Jan-Sep: ${vals['2025'][0]:,}  (duty {duty_pct(vals['2025'][1], vals['2025'][0])}%)  change vs 2024: {chg_24_25}%")
        lines.append(f"  2026 Jan-Sep: ${vals['2026'][0]:,}  (duty {duty_pct(vals['2026'][1], vals['2026'][0])}%)  change vs 2025: {chg_25_26}%")
    lines.append("")

    # 4b: India 2025-to-2026 change by product group
    lines.append("--- 4b. India Jan-Sep 2025 vs 2026, by product group ---")
    group_of = {}
    with open(DATA_DIR / "final_codes_grouped.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            group_of[r["code"]] = r["group"]
    by_group = defaultdict(list)
    for code, level in codes:
        by_group[group_of.get(code, "Unknown")].append((code, level))
    group_rows = []
    for g, glist in by_group.items():
        v25, _ = sum_group(glist, periods["2025"], "india")
        v26, _ = sum_group(glist, periods["2026"], "india")
        group_rows.append((g, v25, v26, pct_change(v25, v26)))
    group_rows.sort(key=lambda r: r[1], reverse=True)
    for g, v25, v26, chg in group_rows:
        lines.append(f"  {g:<22} 2025: ${v25:>14,}   2026: ${v26:>14,}   change: {chg}%")
    lines.append("")

    # 4c: India by tariff period, vs same months a year earlier, with all countries beside it
    lines.append("--- 4c. India by tariff period, vs same months a year earlier ---")
    tariff_periods = [
        ("Apr-Sep 2025", months_in(2025, 4, 9), months_in(2024, 4, 9)),
        ("Oct-Dec 2025", months_in(2025, 10, 12), months_in(2024, 10, 12)),
        ("Jan-Mar 2026", months_in(2026, 1, 3), months_in(2025, 1, 3)),
        ("Apr-Sep 2026", months_in(2026, 4, 9), months_in(2025, 4, 9)),
    ]
    for label_p, cur_months, prior_months in tariff_periods:
        india_cur, _ = sum_group(codes, cur_months, "india")
        india_prior, _ = sum_group(codes, prior_months, "india")
        world_cur, _ = sum_group(codes, cur_months, "world")
        world_prior, _ = sum_group(codes, prior_months, "world")
        lines.append(f"  {label_p}: India ${india_cur:,} vs prior-year ${india_prior:,} "
                     f"({pct_change(india_prior, india_cur)}%)  |  All countries ${world_cur:,} vs "
                     f"prior-year ${world_prior:,} ({pct_change(world_prior, world_cur)}%)")
    lines.append("")

    # 4d: verdict
    india_chg = pct_change(group_vals["India"]["2025"][0], group_vals["India"]["2026"][0])
    all_chg = pct_change(group_vals["All countries"]["2025"][0], group_vals["All countries"]["2026"][0])
    diff = abs(india_chg) - abs(all_chg) if (india_chg is not None and all_chg is not None) else None
    verdict = "HOLDS" if (diff is not None and diff >= 5) else "DOES NOT HOLD"
    lines.append(f'--- 4d. Verdict: "{verdict}" ---')
    lines.append(f"India's Jan-Sep 2025-to-2026 change = {india_chg}%, all countries' change = {all_chg}% "
                 f"(India's fall is {diff:.1f} points larger than all countries')" if diff is not None else
                 "insufficient data for verdict")
    lines.append("")
    return verdict, india_chg, all_chg


def main():
    core = load_codes("core_device_codes.csv")
    pharma = load_codes("pharma_like_codes.csv")
    hygiene = load_codes("hygiene_codes.csv")
    all63 = core + pharma + hygiene

    lines = []
    v1, i1, a1 = run_headline(core, "core_device_codes.csv ONLY", lines)
    lines.append("=" * 70)
    lines.append("")
    v2, i2, a2 = run_headline(all63, "core + pharma-like + hygiene (63 codes, for comparison)", lines)

    lines.append("=== 4e. Verdict comparison ===")
    lines.append(f"Core devices only (60 codes): \"{v1}\" - India {i1}% vs all countries {a1}%")
    lines.append(f"Core + pharma-like + hygiene (63 codes): \"{v2}\" - India {i2}% vs all countries {a2}%")

    text = "\n".join(lines)
    (DATA_DIR / "phase3_headline_core.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
