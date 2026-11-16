"""
h2_apply_exemptions.py

Phase 3 fix 2: apply CBP's official Section 301 Forced Labor HTS List
exemptions (raw/cbp/Forced_Labor_HTS_List.pdf, downloaded from the
govdelivery.com URL given) to every code in core_device_codes.csv,
pharma_like_codes.csv, and hygiene_codes.csv.

Checked against exactly two exemption headings, as instructed:
    9903.05.86 - general product exemptions (Chapter 1 to 97 scope,
                 but the actual codes listed are overwhelmingly
                 chapters 1-39 plus scattered metals/machinery - no
                 medical-device chapter (90/94/96) code appears)
    9903.05.89 - "for use in pharmaceutical applications" exemptions
                 (chapters 28-39 only)

Read the full 39-page PDF directly (via the Read tool, not programmatic
PDF parsing - the document is a non-machine-readable layout with
multi-column code tables) and checked every one of our 63 codes'
HS6/HS8/HS10 prefixes against both lists by direct text search.

RESULT: exactly 3 codes are exempt, all three in Chapter 30
(pharmaceutical-adjacent), none in the device chapters:
    300630 (X-ray contrast preparations) - exempt via 9903.05.86
        (3006.30.10 and 3006.30.50 are explicitly listed)
    300660 (hormonal contraceptives) - exempt via 9903.05.86
        (3006.60.00 is explicitly listed)
    300670 (gel preparations) - exempt via 9903.05.89
        (3006.70.00 is explicitly listed, under the pharmaceutical-use
        heading)
All 60 core device codes (chapters 38, 40, 62, 84, 90, 94) and 961900
(hygiene) were checked and NOT found in either list.

READ-ONLY against core_device_codes.csv, pharma_like_codes.csv,
hygiene_codes.csv, data/phase3_tariff_gap_data.csv. Writes
data/phase3_tariff_gap_data_v2.csv (new file - the exemption-adjusted
version; the original data/phase3_tariff_gap_data.csv from Phase 3's
first pass is untouched).
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

EXEMPT_CODES = {
    "300630": "9903.05.86 (3006.30.10 / 3006.30.50 explicitly listed)",
    "300660": "9903.05.86 (3006.60.00 explicitly listed)",
    "300670": "9903.05.89 (3006.70.00 explicitly listed, pharmaceutical-use heading)",
}


def main():
    with open(DATA_DIR / "phase3_tariff_gap_data.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    columns = list(rows[0].keys()) + ["section301_exempt", "exemption_source"]
    for r in rows:
        if r["code"] in EXEMPT_CODES:
            r["section301_exempt"] = "yes"
            r["exemption_source"] = EXEMPT_CODES[r["code"]]
            # Zero out India's forced-labor-driven Section 301 rate
            # component. india_listed_rate_pct in the original table was
            # mfn + 10 (India's flat forced-labor add-on) - an exempt
            # code pays 0 for that add-on, so the listed rate collapses
            # to just the MFN rate.
            if r["us_mfn_pct"]:
                r["india_listed_rate_pct"] = r["us_mfn_pct"]
            r["india_forced_labor_addon_pct"] = "0 (exempt)"
        else:
            r["section301_exempt"] = "no"
            r["exemption_source"] = ""

    with open(DATA_DIR / "phase3_tariff_gap_data_v2.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)

    exempt_rows = [r for r in rows if r["section301_exempt"] == "yes"]
    print(f"Wrote data/phase3_tariff_gap_data_v2.csv ({len(rows)} rows)")
    print(f"\nExempt codes ({len(exempt_rows)}):")
    for r in exempt_rows:
        print(f"  {r['code']} ({r['description'][:50]}): {r['exemption_source']}")


if __name__ == "__main__":
    main()
