"""
a1_census_vs_comtrade.py

Investigation A1: compare the US-reported (Census) total of "US imports
for consumption from India" against the India-reported (Comtrade) total
of "India exports to the USA", for the same 48 HS6 codes and years
2022-2025 (the years Comtrade has).

READ-ONLY: only reads data/us_imports_by_country.csv and
data/india_trade.csv. Does not modify or overwrite either file.

OUTPUT: data/a1_census_vs_comtrade.csv (new file; does not overwrite
anything).
"""

import csv
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
INDIA_CENSUS_CODE = "5330"
YEARS = ["2022", "2023", "2024", "2025"]


def main():
    census_total = defaultdict(float)
    with open(DATA_DIR / "us_imports_by_country.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["year"] in YEARS and r["cty_code"] == INDIA_CENSUS_CODE and r["summary_lvl"] == "DET":
                census_total[r["year"]] += int(r["imports_for_consumption_usd"] or 0)

    comtrade_total = defaultdict(float)
    with open(DATA_DIR / "india_trade.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["flow"] == "India exports" and r["partner"] == "USA" and r["year"] in YEARS:
                comtrade_total[r["year"]] += float(r["value_usd"] or 0)

    rows = []
    for y in YEARS:
        c = census_total.get(y, 0)
        t = comtrade_total.get(y, 0)
        diff_pct = round(100 * (c - t) / t, 1) if t else ""
        rows.append({
            "year": y,
            "us_reported_imports_from_india_usd": round(c),
            "india_reported_exports_to_usa_usd": round(t),
            "difference_pct": diff_pct,
        })

    with open(DATA_DIR / "a1_census_vs_comtrade.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"{'year':<6}{'US-reported (Census) $':>26}{'India-reported (Comtrade) $':>30}{'diff %':>10}")
    for r in rows:
        print(f"{r['year']:<6}{r['us_reported_imports_from_india_usd']:>26,}"
              f"{r['india_reported_exports_to_usa_usd']:>30,}{r['difference_pct']:>10}")
    print(f"\nWrote data/a1_census_vs_comtrade.csv ({len(rows)} rows)")


if __name__ == "__main__":
    main()
