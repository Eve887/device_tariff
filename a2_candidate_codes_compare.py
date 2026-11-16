"""
a2_candidate_codes_compare.py

Investigation A2: for the 13 candidate HS6 codes added to hs6_codes.csv
(group == "Candidate"), show US imports from India (Census) and
India-reported exports to USA (Comtrade) for 2024 and 2025, sorted by the
2024 US figure, largest first.

READ-ONLY: reads data/us_imports_by_country.csv, data/india_trade.csv,
hs6_codes.csv. Does not modify any of them.

OUTPUT: data/a2_candidate_codes_compare.csv (new file).
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
INDIA_CENSUS_CODE = "5330"
YEARS = ["2024", "2025"]


def main():
    with open(HERE / "hs6_codes.csv", newline="", encoding="utf-8") as f:
        candidates = {r["hs6"]: r["description"] for r in csv.DictReader(f) if r["group"] == "Candidate"}

    us_val = {}  # (hs6, year) -> usd
    with open(DATA_DIR / "us_imports_by_country.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["hs6"] in candidates and r["year"] in YEARS and r["cty_code"] == INDIA_CENSUS_CODE and r["summary_lvl"] == "DET":
                us_val[(r["hs6"], r["year"])] = int(r["imports_for_consumption_usd"] or 0)

    ind_val = {}  # (hs6, year) -> usd
    with open(DATA_DIR / "india_trade.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["hs6"] in candidates and r["flow"] == "India exports" and r["partner"] == "USA" and r["year"] in YEARS:
                ind_val[(r["hs6"], r["year"])] = float(r["value_usd"] or 0)

    rows = []
    for hs6, desc in candidates.items():
        rows.append({
            "hs6": hs6,
            "description": desc,
            "us_imports_from_india_2024_usd": round(us_val.get((hs6, "2024"), 0)),
            "india_exports_to_usa_2024_usd": round(ind_val.get((hs6, "2024"), 0)),
            "us_imports_from_india_2025_usd": round(us_val.get((hs6, "2025"), 0)),
            "india_exports_to_usa_2025_usd": round(ind_val.get((hs6, "2025"), 0)),
        })
    rows.sort(key=lambda r: r["us_imports_from_india_2024_usd"], reverse=True)

    with open(DATA_DIR / "a2_candidate_codes_compare.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"{'hs6':<8}{'description':<52}{'US<-India 2024':>16}{'IN->USA 2024':>16}{'US<-India 2025':>16}{'IN->USA 2025':>16}")
    for r in rows:
        print(f"{r['hs6']:<8}{r['description'][:50]:<52}{r['us_imports_from_india_2024_usd']:>16,}"
              f"{r['india_exports_to_usa_2024_usd']:>16,}{r['us_imports_from_india_2025_usd']:>16,}"
              f"{r['india_exports_to_usa_2025_usd']:>16,}")
    print(f"\nWrote data/a2_candidate_codes_compare.csv ({len(rows)} rows)")


if __name__ == "__main__":
    main()
