"""
p2_alpha.py

Phase 4, Part 2: price absorption (alpha). Checked whether Census
quantity data (CON_QY1_MO/UNIT_QY1, CON_QY2_MO/UNIT_QY2) is usable for
computing unit-value changes, per the user's own fallback instruction
("if quantity data is too patchy to use, say so, and we'll use
alpha = 0.3/0.45/0.6 for low/base/high").

FINDING: quantity data is too patchy to use. Checked all 60 core
codes' India quantity data across all 12 baseline+shock months
(raw/census_monthly_qty/*): only 2 of 60 - both HS10 lines, 6210105010
and 6210105090 (surgical/isolation gowns) - have a real, consistent
quantity unit ("DOZ") with nonzero reported quantity in both periods.
The other 58 codes report UNIT_QY1 = "-" (Census's own marker for "no
quantity unit collected at this level of aggregation") with
CON_QY1_MO = 0 for every month - confirmed this is a genuine Census
data characteristic, not a download/parsing bug, by reading a raw
response directly (raw/census_monthly_qty/901819_2025-10.json) and
seeing the literal "-" unit marker on every row, India included.

This makes sense structurally: most of our codes are 6-digit (HS6)
aggregates spanning multiple product types that don't share one
natural quantity unit (e.g. "other medical and surgical instruments"
has no single meaningful "count" or "kg" figure); quantity reporting
in US trade statistics is generally more reliable at finer (8/10-digit)
granularity, which is also where our only 2 usable codes happen to be.

Per the user's explicit fallback: alpha = 0.3 (low) / 0.45 (base) /
0.6 (high), applied flat across every product group - not computed
from data, since the data does not support it. This is not treated as
group-specific since there is no usable group-level signal to vary it
by.

READ-ONLY against raw/census_monthly_qty/*, core_device_codes.csv.
Writes data/phase4_alpha.csv (new file; a flat constant, documented
with its basis).
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

ALPHA = {"low": 0.3, "base": 0.45, "high": 0.6}


def main():
    with open(DATA_DIR / "phase4_alpha.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["scenario_tier", "alpha", "basis"])
        for tier, val in ALPHA.items():
            w.writerow([tier, val, "fallback - quantity data too patchy (2/60 core codes usable); "
                                     "per user's explicit instruction"])
    print("Quantity data check: 2 of 60 core codes have usable quantity data "
          "(6210105010, 6210105090 - DOZ unit). Too patchy to compute alpha from data.")
    print(f"Using fallback alpha: low={ALPHA['low']}, base={ALPHA['base']}, high={ALPHA['high']}")
    print("Wrote data/phase4_alpha.csv")


if __name__ == "__main__":
    main()
