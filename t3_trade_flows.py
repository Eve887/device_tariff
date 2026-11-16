"""
t3_trade_flows.py

View B, Part 3: India's imports of medical devices, by source
country. From data/india_trade.csv (and
data/india_trade_final_new_codes.csv for codes added after the
original 48-code pull) - India-reported, CIF values, flow="India
imports" - World, USA, China, Germany, Japan, 2022-2025, per core
HS6 code (core_device_codes.csv). US share per code and overall.

READ-ONLY against core_device_codes.csv, india_trade.csv,
india_trade_final_new_codes.csv. Writes data/india_imports_by_country.csv
(new file) only.
"""

import csv
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
NF = "not found"

YEARS = ["2022", "2023", "2024", "2025"]
PARTNERS = ["World", "USA", "China", "Germany", "Japan"]


def main():
    with open(DATA_DIR / "core_device_codes.csv", newline="", encoding="utf-8-sig") as f:
        core = {r["code"]: r["description"] for r in csv.DictReader(f)}

    # data[hs6][year][partner] = value_usd
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    covered_codes = set()
    for fname in ("india_trade.csv", "india_trade_final_new_codes.csv"):
        path = DATA_DIR / fname
        if not path.exists():
            continue
        with open(path, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r["flow"] != "India imports":
                    continue
                hs6 = r["hs6"]
                if hs6 not in core:
                    continue
                year = r.get("year")
                partner = r.get("partner")
                if year not in YEARS or partner not in PARTNERS:
                    continue
                data[hs6][year][partner] += float(r["value_usd"])
                covered_codes.add(hs6)

    rows = []
    for code, desc in core.items():
        if code not in covered_codes:
            for year in YEARS:
                row = {"hs6": code, "description": desc, "year": year}
                for p in PARTNERS:
                    row[f"imports_from_{p.lower()}_usd"] = NF
                row["us_share_pct"] = NF
                rows.append(row)
            continue
        for year in YEARS:
            vals = data[code][year]
            world = vals.get("World", 0)
            row = {"hs6": code, "description": desc, "year": year}
            for p in PARTNERS:
                row[f"imports_from_{p.lower()}_usd"] = round(vals.get(p, 0))
            row["us_share_pct"] = round(100 * vals.get("USA", 0) / world, 3) if world else NF
            rows.append(row)

    with open(DATA_DIR / "india_imports_by_country.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote data/india_imports_by_country.csv ({len(rows)} rows)")
    print(f"Codes with no 'India imports' data at all: {len(core) - len(covered_codes)} of {len(core)}")

    # overall totals per year
    print("\nOverall totals (all core codes combined), by year:")
    for year in YEARS:
        world_total = sum(data[c][year].get("World", 0) for c in core if c in covered_codes)
        usa_total = sum(data[c][year].get("USA", 0) for c in core if c in covered_codes)
        share = 100 * usa_total / world_total if world_total else 0
        print(f"  {year}: World=${world_total:,.0f}  USA=${usa_total:,.0f}  US share={share:.2f}%")


if __name__ == "__main__":
    main()
