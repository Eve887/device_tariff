"""
p5_revenue_at_risk.py

Phase 4, Part 5: revenue at risk per code and scenario.
    revenue_at_risk = E x [alpha x delta_t + epsilon_group x (1-alpha) x delta_g]
(delta_t, delta_g as fractions - 15 points = 0.15)

low  = 25th-percentile epsilon with low alpha (0.3)
base = median epsilon with base alpha (0.45)
high = 75th-percentile epsilon with high alpha (0.6)

Two E definitions: 2025 full calendar year, and latest 12 months
(Oct 2025 - Sep 2026).

READ-ONLY against data/phase4_scenarios.csv, data/phase4_elasticity_by_group.csv,
data/final_codes_grouped.csv, raw/census/*, raw/census_monthly/*.
Writes data/phase4_revenue_at_risk.csv and
data/phase4_revenue_at_risk_totals.csv (new files).
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

ALPHA = {"low": 0.3, "base": 0.45, "high": 0.6}
LATEST_12MO = [f"2025-{m:02d}" for m in (10, 11, 12)] + [f"2026-{m:02d}" for m in range(1, 10)]


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


def main():
    with open(DATA_DIR / "phase4_scenarios.csv", newline="", encoding="utf-8-sig") as f:
        scen_rows = list(csv.DictReader(f))
    with open(DATA_DIR / "phase4_elasticity_by_group.csv", newline="", encoding="utf-8-sig") as f:
        group_eps = {r["group"]: r for r in csv.DictReader(f)}
    with open(DATA_DIR / "final_codes_grouped.csv", newline="", encoding="utf-8-sig") as f:
        group_of = {r["code"]: r["group"] for r in csv.DictReader(f)}

    e_cache_2025, e_cache_12mo = {}, {}
    out_rows = []
    for r in scen_rows:
        code = r["code"]
        if code not in e_cache_2025:
            e_cache_2025[code] = e_2025_full_year(code)
            e_cache_12mo[code] = e_latest_12mo(code)
        e_2025 = e_cache_2025[code]
        e_12mo = e_cache_12mo[code]

        group = group_of.get(code, "Unknown")
        eps = group_eps.get(group)
        if eps is None:
            continue
        eps_p25, eps_median, eps_p75 = float(eps["p25_epsilon"]), float(eps["median_epsilon"]), float(eps["p75_epsilon"])

        delta_t = float(r["delta_t_pp"]) / 100
        delta_g = float(r["delta_g_pp"]) / 100

        def rar(E, alpha, epsilon):
            return E * (alpha * delta_t + epsilon * (1 - alpha) * delta_g)

        row = {
            "code": code, "description": r["description"], "group": group,
            "scenario": r["scenario"], "scenario_year": r["scenario_year"],
            "delta_t_pp": r["delta_t_pp"], "delta_g_pp": r["delta_g_pp"],
            "E_2025_full_year_usd": e_2025, "E_latest_12mo_usd": e_12mo,
            "rar_2025_low_usd": round(rar(e_2025, ALPHA["low"], eps_p25)),
            "rar_2025_base_usd": round(rar(e_2025, ALPHA["base"], eps_median)),
            "rar_2025_high_usd": round(rar(e_2025, ALPHA["high"], eps_p75)),
            "rar_12mo_low_usd": round(rar(e_12mo, ALPHA["low"], eps_p25)),
            "rar_12mo_base_usd": round(rar(e_12mo, ALPHA["base"], eps_median)),
            "rar_12mo_high_usd": round(rar(e_12mo, ALPHA["high"], eps_p75)),
        }
        out_rows.append(row)

    with open(DATA_DIR / "phase4_revenue_at_risk.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print(f"Wrote data/phase4_revenue_at_risk.csv ({len(out_rows)} rows)")

    # ---- totals by scenario (+ year), by group and overall ----
    totals = defaultdict(lambda: defaultdict(float))
    e_totals = defaultdict(float)
    overall_e_2025 = overall_e_12mo = 0
    seen_codes = set()
    for row in out_rows:
        key = (row["scenario"], row["scenario_year"] or "")
        for tier in ("low", "base", "high"):
            totals[key][f"rar_2025_{tier}"] += row[f"rar_2025_{tier}_usd"]
            totals[key][f"rar_12mo_{tier}"] += row[f"rar_12mo_{tier}_usd"]
        totals[key]["E_2025"] += row["E_2025_full_year_usd"]
        totals[key]["E_12mo"] += row["E_latest_12mo_usd"]
        if row["code"] not in seen_codes:
            seen_codes.add(row["code"])
            overall_e_2025 += row["E_2025_full_year_usd"]
            overall_e_12mo += row["E_latest_12mo_usd"]

    total_rows = []
    for (scen, year), vals in totals.items():
        e2025 = vals["E_2025"]
        e12mo = vals["E_12mo"]
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

    with open(DATA_DIR / "phase4_revenue_at_risk_totals.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(total_rows[0].keys()))
        w.writeheader()
        w.writerows(total_rows)
    print(f"Wrote data/phase4_revenue_at_risk_totals.csv ({len(total_rows)} rows)")
    print(f"\nOverall E 2025 full year: ${overall_e_2025:,}  |  E latest 12mo: ${overall_e_12mo:,}\n")

    print(f"{'Scenario':<32}{'Year':<10}{'low $M':>10}{'base $M':>10}{'high $M':>10}{'low%':>8}{'base%':>8}{'high%':>8}")
    for r in sorted(total_rows, key=lambda x: (x["scenario"], x["scenario_year"])):
        print(f"{r['scenario']:<32}{r['scenario_year']:<10}"
              f"{r['rar_2025_low_usd']/1e6:>10.2f}{r['rar_2025_base_usd']/1e6:>10.2f}{r['rar_2025_high_usd']/1e6:>10.2f}"
              f"{r['rar_2025_low_pct'] if r['rar_2025_low_pct'] is not None else '':>8}"
              f"{r['rar_2025_base_pct'] if r['rar_2025_base_pct'] is not None else '':>8}"
              f"{r['rar_2025_high_pct'] if r['rar_2025_high_pct'] is not None else '':>8}")


if __name__ == "__main__":
    main()
