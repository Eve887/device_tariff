"""
e1_build_final_summary.py

Part 3: builds data/phase2_final_summary.csv, one row per code (from
final_codes.csv) x year (2022, 2023, 2024, 2025, 2026 YTD), with:
  US imports from India; India's share of the US market; top 3
  suppliers; India's exports to USA and to the World (HS6 only); US
  dependence %; duty charged on Indian goods as % of value; India's
  imports from USA and from the World (HS6 only); product group.

READ-ONLY against raw/census/*, data/india_trade.csv,
data/india_trade_final_new_codes.csv, final_codes.csv, hs6_codes.csv,
data/epcmd_151_codes.csv. Writes data/phase2_final_summary.csv (new
file) only.
"""

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
CENSUS_DIR = HERE / "raw" / "census"
INDIA = "5330"
YEARS = ["2022", "2023", "2024", "2025", "2026"]
PERIOD_FOR_YEAR = {"2022": "2022-12", "2023": "2023-12", "2024": "2024-12",
                   "2025": "2025-12", "2026": "2026-09"}


def load_codes():
    with open(DATA_DIR / "final_codes.csv", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_product_groups():
    """Prefer our own hs6_codes.csv group, except "Candidate" - that was
    just an investigation-phase placeholder label, not a real product
    category, so for those codes fall back to EPCMD's category instead."""
    groups = {}
    with open(HERE / "hs6_codes.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["group"] != "Candidate":
                groups[r["hs6"]] = r["group"]
    with open(DATA_DIR / "epcmd_151_codes.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            groups.setdefault(r["hs6"], r["category"])
    return groups


def census_row_data(code, level, period):
    raw_file = CENSUS_DIR / f"{code}_{period}.json"
    if not raw_file.exists():
        return None
    saved = json.loads(raw_file.read_text(encoding="utf-8"))
    if saved["status"] != "ok" or not saved["rows"]:
        return {"world": 0, "india": 0, "india_duty": 0, "suppliers": []}
    header, *records = saved["rows"]
    world = india = india_duty = 0
    suppliers = []
    for rec in records:
        r = dict(zip(header, rec))
        val = int(r.get("CON_VAL_YR") or 0)
        if "TOTAL FOR ALL" in (r.get("CTY_NAME") or "").upper():
            world = val
        elif r.get("SUMMARY_LVL") == "DET":
            suppliers.append((val, (r.get("CTY_NAME") or "").title()))
            if r.get("CTY_CODE") == INDIA:
                india = val
                india_duty = int(r.get("CAL_DUT_YR") or 0)
    return {"world": world, "india": india, "india_duty": india_duty, "suppliers": suppliers}


def load_comtrade():
    ind_val = {}
    for fname in ("india_trade.csv", "india_trade_final_new_codes.csv"):
        path = DATA_DIR / fname
        if not path.exists():
            continue
        with open(path, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                ind_val[(r["flow"], r["hs6"], str(r["year"]), r["partner"])] = float(r["value_usd"] or 0)
    return ind_val


def pct(a, b):
    return round(100 * a / b, 1) if b else ""


def main():
    codes = load_codes()
    groups = load_product_groups()
    ind_val = load_comtrade()

    def iv(flow, hs6, year, partner):
        return ind_val.get((flow, hs6, year, partner), 0.0)

    rows = []
    for c in codes:
        code, level, desc = c["code"], c["level"], c["description"]
        hs6_for_group = code[:6]
        group = groups.get(hs6_for_group, "")
        for year in YEARS:
            period = PERIOD_FOR_YEAR[year]
            cd = census_row_data(code, level, period)
            if cd is None:
                continue
            top3 = sorted(cd["suppliers"], reverse=True)[:3]
            row = {
                "code": code, "level": level, "description": desc, "product_group": group,
                "year": year,
                "us_imports_from_india_usd": cd["india"],
                "us_imports_world_usd": cd["world"],
                "india_share_of_us_market_pct": pct(cd["india"], cd["world"]),
                "top3_suppliers": "; ".join(f"{n} {pct(v, cd['world'])}%" for v, n in top3),
                "effective_duty_pct_on_india": pct(cd["india_duty"], cd["india"]),
            }
            if level == "HS6":
                ex_world = iv("India exports", code, year, "World")
                ex_usa = iv("India exports", code, year, "USA")
                im_world = iv("India imports", code, year, "World")
                im_usa = iv("India imports", code, year, "USA")
                row.update({
                    "india_exports_to_usa_usd": round(ex_usa),
                    "india_exports_to_world_usd": round(ex_world),
                    "us_dependence_pct": pct(ex_usa, ex_world),
                    "india_imports_from_usa_usd": round(im_usa),
                    "india_imports_from_world_usd": round(im_world),
                })
            else:
                row.update({
                    "india_exports_to_usa_usd": "", "india_exports_to_world_usd": "",
                    "us_dependence_pct": "", "india_imports_from_usa_usd": "",
                    "india_imports_from_world_usd": "",
                })
            rows.append(row)

    columns = ["code", "level", "description", "product_group", "year",
               "us_imports_from_india_usd", "us_imports_world_usd",
               "india_share_of_us_market_pct", "top3_suppliers",
               "india_exports_to_usa_usd", "india_exports_to_world_usd",
               "us_dependence_pct", "effective_duty_pct_on_india",
               "india_imports_from_usa_usd", "india_imports_from_world_usd"]
    with open(DATA_DIR / "phase2_final_summary.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote data/phase2_final_summary.csv ({len(rows)} rows, "
          f"{len(codes)} codes x up to {len(YEARS)} years)")


if __name__ == "__main__":
    main()
