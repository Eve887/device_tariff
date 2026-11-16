"""
t2_landed_cost.py

View B, Part 2: landed cost of a US-origin device in India.

For each tracked code (AV = assessable value = CIF value = 100):
    BCD           = AV x BCD%
    SWS           = BCD x SWS%
    Health cess   = AV x cess%
    IGST          = (AV + BCD + SWS + health cess) x IGST%
    Customs duty% = (BCD + SWS + health cess) / AV
    Total tax%    = (BCD + SWS + health cess + IGST) / AV

IGST is kept as a real COST in this model (not netted off), because
most Indian hospitals' services are GST-exempt, so they usually
cannot claim it back as input tax credit - this is noted explicitly
in the Excel README per the user's instruction, and is a deliberate
departure from how a GST-registered, fully taxable importer (e.g. a
distributor who resells to a non-hospital, taxable buyer) would treat
IGST (as creditable, per the Acuity Law FAQ's general statement -
that general statement applies to taxable businesses, not GST-exempt
hospital end-use, which is the relevant lens for this View B study).

Rolled up to HS6 (weighted EQUALLY across the HS6's tracked lines -
only two HS6 groups in this project's code list actually have more
than one tracked line under them: 621010 (6210105010 + 6210105090)
and 902519 (9025198010 + 9025198020); every other HS6 has exactly one
tracked line, so its "rollup" is identical to that single line).
Flags any HS6 whose lines have different rates (neither of the two
multi-line HS6 groups above has any rate found for either sibling, so
this check currently finds nothing to flag either way - recorded as
such, not silently skipped).

Where BCD, SWS, health cess or IGST is "not found" for a line, that
line's entire landed-cost row is "not computable" - never filled in
with an assumed value.

READ-ONLY against data/india_duty_rates.csv. Writes
data/india_landed_cost.csv (new file) only.
"""

import csv
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
NF = "not found"
NC = "not computable (one or more rates not found)"

AV = 100.0


def parse_pct(s):
    """Parses a percentage string like '7.5%' or '10% (from 1 Apr 2026)' ->
    7.5 or 10.0. Returns None if not parseable (e.g. 'not found')."""
    if not s or NF in s:
        return None
    # take the leading number before any '%'
    token = s.split("%")[0].strip()
    try:
        return float(token)
    except ValueError:
        return None


def main():
    with open(DATA_DIR / "india_duty_rates.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    line_rows = []
    for r in rows:
        bcd_pct = parse_pct(r["bcd_pct"])
        sws_pct = parse_pct(r["sws_pct"])
        cess_pct = parse_pct(r["health_cess_pct"])
        igst_pct = parse_pct(r["igst_pct"])

        if None in (bcd_pct, sws_pct, cess_pct, igst_pct):
            line_rows.append({
                "code": r["hs8_or_tracked_code"], "hs6": r["hs6"], "description": r["description"],
                "bcd_amount": NC, "sws_amount": NC, "health_cess_amount": NC, "igst_amount": NC,
                "customs_duty_pct": NC, "total_tax_pct": NC,
                "missing": ", ".join(name for name, v in
                                      [("BCD", bcd_pct), ("SWS", sws_pct), ("health cess", cess_pct), ("IGST", igst_pct)]
                                      if v is None),
            })
            continue

        bcd_amt = AV * bcd_pct / 100
        sws_amt = bcd_amt * sws_pct / 100
        cess_amt = AV * cess_pct / 100
        igst_amt = (AV + bcd_amt + sws_amt + cess_amt) * igst_pct / 100
        customs_duty_pct = (bcd_amt + sws_amt + cess_amt) / AV * 100
        total_tax_pct = (bcd_amt + sws_amt + cess_amt + igst_amt) / AV * 100

        line_rows.append({
            "code": r["hs8_or_tracked_code"], "hs6": r["hs6"], "description": r["description"],
            "bcd_amount": round(bcd_amt, 4), "sws_amount": round(sws_amt, 4),
            "health_cess_amount": round(cess_amt, 4), "igst_amount": round(igst_amt, 4),
            "customs_duty_pct": round(customs_duty_pct, 4), "total_tax_pct": round(total_tax_pct, 4),
            "missing": "",
        })

    with open(DATA_DIR / "india_landed_cost.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(line_rows[0].keys()))
        w.writeheader()
        w.writerows(line_rows)
    n_computable = sum(1 for r in line_rows if r["bcd_amount"] != NC)
    print(f"Wrote data/india_landed_cost.csv ({len(line_rows)} lines, {n_computable} computable)")

    # ---- roll up to HS6, equal weight across tracked lines ----
    by_hs6 = defaultdict(list)
    for r in line_rows:
        by_hs6[r["hs6"]].append(r)

    hs6_rows = []
    for hs6, lines in by_hs6.items():
        computable = [l for l in lines if l["bcd_amount"] != NC]
        desc = lines[0]["description"] if len(lines) == 1 else f"{len(lines)} tracked lines"
        if not computable:
            hs6_rows.append({
                "hs6": hs6, "n_tracked_lines": len(lines), "description": desc,
                "customs_duty_pct": NC, "total_tax_pct": NC,
                "lines_differ": "N/A - no computable lines",
            })
            continue
        avg_customs = sum(l["customs_duty_pct"] for l in computable) / len(computable)
        avg_total = sum(l["total_tax_pct"] for l in computable) / len(computable)
        differ = False
        if len(computable) > 1:
            customs_vals = {l["customs_duty_pct"] for l in computable}
            total_vals = {l["total_tax_pct"] for l in computable}
            differ = len(customs_vals) > 1 or len(total_vals) > 1
        note = ""
        if len(lines) > len(computable):
            note = f"{len(lines) - len(computable)} of {len(lines)} tracked lines under this HS6 were not computable and excluded from the average"
        hs6_rows.append({
            "hs6": hs6, "n_tracked_lines": len(lines), "description": desc,
            "customs_duty_pct": round(avg_customs, 4), "total_tax_pct": round(avg_total, 4),
            "lines_differ": ("YES - rates differ across this HS6's tracked lines" if differ
                              else ("N/A - only 1 tracked line" if len(computable) == 1 else "no - uniform")) + (f" ({note})" if note else ""),
        })

    with open(DATA_DIR / "india_landed_cost_hs6_rollup.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(hs6_rows[0].keys()))
        w.writeheader()
        w.writerows(hs6_rows)
    n_flagged = sum(1 for r in hs6_rows if r["lines_differ"].startswith("YES"))
    print(f"Wrote data/india_landed_cost_hs6_rollup.csv ({len(hs6_rows)} HS6 groups, {n_flagged} flagged as differing)")


if __name__ == "__main__":
    main()
