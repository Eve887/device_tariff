"""
h1_split_core_codes.py

Phase 3 fix 1: split final_codes_grouped.csv into three lists:
  - data/pharma_like_codes.csv: 300660 (hormonal contraceptives), 300630
    (X-ray contrast preparations) - these are medicines, not devices.
  - data/hygiene_codes.csv: 961900 (sanitary pads/tampons/diapers etc.)
  - data/core_device_codes.csv: everything else (the real device list).

READ-ONLY against final_codes_grouped.csv. Writes the three new files
only; final_codes_grouped.csv itself is untouched.
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

PHARMA_LIKE = {"300660", "300630"}
HYGIENE = {"961900"}


def main():
    with open(DATA_DIR / "final_codes_grouped.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    pharma_rows = [r for r in rows if r["code"] in PHARMA_LIKE]
    hygiene_rows = [r for r in rows if r["code"] in HYGIENE]
    core_rows = [r for r in rows if r["code"] not in PHARMA_LIKE and r["code"] not in HYGIENE]

    columns = list(rows[0].keys())
    for fname, out_rows in (("pharma_like_codes.csv", pharma_rows),
                             ("hygiene_codes.csv", hygiene_rows),
                             ("core_device_codes.csv", core_rows)):
        with open(DATA_DIR / fname, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=columns)
            w.writeheader()
            w.writerows(out_rows)

    print(f"pharma_like_codes.csv: {len(pharma_rows)} rows -> {[r['code'] for r in pharma_rows]}")
    print(f"hygiene_codes.csv: {len(hygiene_rows)} rows -> {[r['code'] for r in hygiene_rows]}")
    print(f"core_device_codes.csv: {len(core_rows)} rows (was {len(rows)} in final_codes_grouped.csv)")


if __name__ == "__main__":
    main()
