"""
t4_scenarios.py

View B, Part 5: scenarios for US-origin devices only (every other
country's duty treatment unchanged).
    B0: today
    B1: BCD cut to 0% on US devices (SWS, being 10% of BCD, follows
        BCD to 0 mechanically; health cess UNCHANGED - the scenario
        deliberately isolates BCD from health cess, even though in
        today's actual law the two are linked - see note below)
    B2: health cess removed on US devices (BCD/SWS UNCHANGED)
    B3: both cuts together (BCD=0, SWS=0, health cess=0)
IGST is never switched off in any scenario - only its BASE changes
(since IGST = (AV+BCD+SWS+cess) x IGST%), because the Joint Statement
research in Part 4 found no mention of IGST/health-cess changes in
the actual trade deal text - these are the user's own hypothetical
"what if" scenarios, not deal provisions.

NOTE on B1 vs today's actual law: Part 1's research found that health
cess is, under current law, ALSO nil whenever the device itself is
BCD-exempt (Finance Act 2020, Section 141). B1 here does NOT apply
that real-world link (it changes BCD only, leaving health cess as a
separate, independent lever) - this is a deliberate, requested
scenario design to isolate the two cost components for analysis, not
an error, and is called out here and in the Excel README so it is
not mistaken for a claim about current law.

For each code x scenario:
  a. price_fall_pct = (total_tax_pct_B0 - total_tax_pct_Bx) / (100 + total_tax_pct_B0)
  b. extra_us_sales_usd = 2025_india_imports_from_usa_usd x elasticity x price_fall_pct
     elasticity in {0.5, 1.0, 1.5} (low/base/high) - an ASSUMED range,
     NOT measured from data, labelled as such everywhere it appears.
  c. lost_customs_revenue_usd = 2025_india_imports_from_usa_usd x
     (customs_duty_pct_B0 - customs_duty_pct_Bx) / 100
     (ignores the extra-imports effect, per instruction - uses the
     SAME 2025 base as (b), not a grown base)
  d. competitor context: China/Germany/Japan 2025 import values for
     the same code, shown side by side (no scenario math applied to
     them - they're context for "who else supplies this code", not a
     projection of share loss).

Only computable for the 40 codes that have BOTH a computable landed-
cost (Part 2) AND 2025 India-imports-from-USA data (Part 3) - for
every other code, every scenario figure is "not computable", not
zero.

READ-ONLY against data/india_duty_rates.csv,
data/india_landed_cost.csv, data/india_imports_by_country.csv,
core_device_codes.csv. Writes data/view_b_scenarios.csv,
data/view_b_totals.csv (new files).
"""

import csv
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
NF = "not found"
NC = "not computable"

ELASTICITY = {"low": 0.5, "base": 1.0, "high": 1.5}


def parse_pct(s):
    if not s or NF in str(s):
        return None
    token = str(s).split("%")[0].strip()
    try:
        return float(token)
    except ValueError:
        return None


def landed_cost_waterfall(av, bcd_pct, sws_pct, cess_pct, igst_pct):
    bcd = av * bcd_pct / 100
    sws = bcd * sws_pct / 100
    cess = av * cess_pct / 100
    igst = (av + bcd + sws + cess) * igst_pct / 100
    customs_duty_pct = (bcd + sws + cess) / av * 100
    total_tax_pct = (bcd + sws + cess + igst) / av * 100
    return customs_duty_pct, total_tax_pct


def main():
    with open(DATA_DIR / "core_device_codes.csv", newline="", encoding="utf-8-sig") as f:
        core = {r["code"]: r for r in csv.DictReader(f)}

    with open(DATA_DIR / "india_duty_rates.csv", newline="", encoding="utf-8-sig") as f:
        rates = {r["hs8_or_tracked_code"]: r for r in csv.DictReader(f)}

    with open(DATA_DIR / "india_imports_by_country.csv", newline="", encoding="utf-8-sig") as f:
        imports_2025 = {r["hs6"]: r for r in csv.DictReader(f) if r["year"] == "2025"}

    rows = []
    for code, crow in core.items():
        group = crow["group"]
        desc = crow["description"]
        rate_row = rates.get(code)
        imp_row = imports_2025.get(code)

        bcd0 = parse_pct(rate_row["bcd_pct"]) if rate_row else None
        sws0 = parse_pct(rate_row["sws_pct"]) if rate_row else None
        cess0 = parse_pct(rate_row["health_cess_pct"]) if rate_row else None
        igst0 = parse_pct(rate_row["igst_pct"]) if rate_row else None
        usa_2025 = None
        if imp_row and imp_row["imports_from_usa_usd"] != NF:
            usa_2025 = float(imp_row["imports_from_usa_usd"])
        china_2025 = imp_row["imports_from_china_usd"] if imp_row else NF
        germany_2025 = imp_row["imports_from_germany_usd"] if imp_row else NF
        japan_2025 = imp_row["imports_from_japan_usd"] if imp_row else NF

        computable = None not in (bcd0, sws0, cess0, igst0) and usa_2025 is not None

        if not computable:
            missing = []
            if bcd0 is None or sws0 is None or cess0 is None or igst0 is None:
                missing.append("duty rate(s) not found")
            if usa_2025 is None:
                missing.append("no 2025 India-imports-from-USA data")
            for scen in ("B0", "B1", "B2", "B3"):
                rows.append({
                    "code": code, "group": group, "description": desc, "scenario": scen,
                    "price_fall_pct": NC, "extra_us_sales_low_usd": NC, "extra_us_sales_base_usd": NC,
                    "extra_us_sales_high_usd": NC, "lost_customs_revenue_usd": NC,
                    "china_2025_usd": china_2025, "germany_2025_usd": germany_2025, "japan_2025_usd": japan_2025,
                    "note": "; ".join(missing),
                })
            continue

        customs0, total0 = landed_cost_waterfall(100, bcd0, sws0, cess0, igst0)

        scenarios = {
            "B0": (bcd0, sws0, cess0, igst0),
            "B1": (0.0, 0.0, cess0, igst0),
            "B2": (bcd0, sws0, 0.0, igst0),
            "B3": (0.0, 0.0, 0.0, igst0),
        }
        for scen, (b, s, c, i) in scenarios.items():
            customs_x, total_x = landed_cost_waterfall(100, b, s, c, i)
            price_fall = (total0 - total_x) / (100 + total0)
            lost_rev = usa_2025 * (customs0 - customs_x) / 100

            extra_sales = {}
            for lvl, elas in ELASTICITY.items():
                extra_sales[lvl] = usa_2025 * elas * price_fall

            rows.append({
                "code": code, "group": group, "description": desc, "scenario": scen,
                "price_fall_pct": round(price_fall * 100, 4),
                "extra_us_sales_low_usd": round(extra_sales["low"]),
                "extra_us_sales_base_usd": round(extra_sales["base"]),
                "extra_us_sales_high_usd": round(extra_sales["high"]),
                "lost_customs_revenue_usd": round(lost_rev),
                "china_2025_usd": china_2025, "germany_2025_usd": germany_2025, "japan_2025_usd": japan_2025,
                "note": "",
            })

    with open(DATA_DIR / "view_b_scenarios.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    n_codes_computable = len({r["code"] for r in rows if r["note"] == ""})
    print(f"Wrote data/view_b_scenarios.csv ({len(rows)} rows, {n_codes_computable} of 60 codes computable)")

    # ---- totals, per group and overall ----
    totals_by_group = defaultdict(lambda: defaultdict(float))
    totals_overall = defaultdict(float)
    for r in rows:
        if r["note"] != "":
            continue
        scen = r["scenario"]
        g = r["group"]
        key = (g, scen)
        totals_by_group[key]["extra_us_sales_low"] += r["extra_us_sales_low_usd"]
        totals_by_group[key]["extra_us_sales_base"] += r["extra_us_sales_base_usd"]
        totals_by_group[key]["extra_us_sales_high"] += r["extra_us_sales_high_usd"]
        totals_by_group[key]["lost_customs_revenue"] += r["lost_customs_revenue_usd"]
        okey = scen
        totals_overall[(okey, "extra_us_sales_low")] += r["extra_us_sales_low_usd"]
        totals_overall[(okey, "extra_us_sales_base")] += r["extra_us_sales_base_usd"]
        totals_overall[(okey, "extra_us_sales_high")] += r["extra_us_sales_high_usd"]
        totals_overall[(okey, "lost_customs_revenue")] += r["lost_customs_revenue_usd"]

    total_rows = []
    for (g, scen), vals in totals_by_group.items():
        total_rows.append({
            "level": "group", "group_or_overall": g, "scenario": scen,
            "extra_us_sales_low_usd": round(vals["extra_us_sales_low"]),
            "extra_us_sales_base_usd": round(vals["extra_us_sales_base"]),
            "extra_us_sales_high_usd": round(vals["extra_us_sales_high"]),
            "lost_customs_revenue_usd": round(vals["lost_customs_revenue"]),
        })
    for scen in ("B0", "B1", "B2", "B3"):
        total_rows.append({
            "level": "OVERALL", "group_or_overall": "ALL CODES", "scenario": scen,
            "extra_us_sales_low_usd": round(totals_overall[(scen, "extra_us_sales_low")]),
            "extra_us_sales_base_usd": round(totals_overall[(scen, "extra_us_sales_base")]),
            "extra_us_sales_high_usd": round(totals_overall[(scen, "extra_us_sales_high")]),
            "lost_customs_revenue_usd": round(totals_overall[(scen, "lost_customs_revenue")]),
        })

    with open(DATA_DIR / "view_b_totals.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(total_rows[0].keys()))
        w.writeheader()
        w.writerows(total_rows)
    print(f"Wrote data/view_b_totals.csv ({len(total_rows)} rows)")

    print("\nOverall totals (base elasticity, $M):")
    for scen in ("B1", "B2", "B3"):
        r = next(r for r in total_rows if r["level"] == "OVERALL" and r["scenario"] == scen)
        print(f"  {scen}: extra US sales base=${r['extra_us_sales_base_usd']/1e6:.2f}M "
              f"(low=${r['extra_us_sales_low_usd']/1e6:.2f}M, high=${r['extra_us_sales_high_usd']/1e6:.2f}M)  "
              f"lost customs revenue=${r['lost_customs_revenue_usd']/1e6:.2f}M")


if __name__ == "__main__":
    main()
