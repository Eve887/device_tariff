"""
f1_build_grouped_codes.py

Phase 3, Part 1: assign every code in final_codes.csv exactly one group
from a fixed controlled vocabulary, and re-check the 382219 HS10 lines
against a stricter rule (own description must be diagnostic, not a
chemical-content split).

READ-ONLY against final_codes.csv, hs6_codes.csv, data/epcmd_151_codes.csv.
Writes data/final_codes_grouped.csv (new file) only.
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

ALLOWED_GROUPS = {"Consumables", "Instruments", "Electro-diagnostic", "Imaging",
                  "Implants", "Dental", "Diagnostics", "Dressings & Sutures",
                  "Gloves", "Respiratory & Therapy", "Ophthalmic", "Hearing",
                  "Furniture", "Other"}

MERGE_MAP = {
    "Consumable & Disposable": "Consumables",
    "Consumables": "Consumables",
    "Dressings": "Dressings & Sutures",
    "Sutures": "Dressings & Sutures",
    "Respiratory": "Respiratory & Therapy",
    "Therapy": "Respiratory & Therapy",
}

# explicit per-code overrides (take priority over the raw-group mapping)
CODE_OVERRIDES = {
    "902511": "Electro-diagnostic",       # thermometers
    "9025198010": "Electro-diagnostic",   # thermometer HS10 line
    "9025198020": "Electro-diagnostic",   # thermometer HS10 line
    "902710": "Other",                    # 9027 instrument family
    "902720": "Other",
    "902730": "Other",
    "902750": "Other",
    "902790": "Other",
    "842310": "Other",                    # weighing scales - no clean fit, catch-all
}

# 382219 re-check: keep only if the LINE'S OWN description says
# "diagnostic", not because the parent heading does and the line itself
# is split by chemical content. None of the 4 lines kept earlier
# qualify under this stricter rule.
REMOVE_382219_LINES = {
    "3822190010": "Containing antigens or antisera, with methyl chloroform/carbon tetrachloride",
    "3822190030": "Containing antigens or antisera, other",
    "3822190040": "Other, with methyl chloroform/carbon tetrachloride",
    "3822190080": "Other",
}


def raw_group(code, hs6_groups, epcmd_categories):
    hs6 = code[:6]
    g = hs6_groups.get(hs6)
    if g and g != "Candidate":
        return g
    return epcmd_categories.get(hs6, "")


def main():
    with open(HERE / "hs6_codes.csv", newline="", encoding="utf-8") as f:
        hs6_groups = {r["hs6"]: r["group"] for r in csv.DictReader(f)}
    with open(DATA_DIR / "epcmd_151_codes.csv", newline="", encoding="utf-8-sig") as f:
        epcmd_categories = {r["hs6"]: r["category"] for r in csv.DictReader(f)}

    with open(DATA_DIR / "final_codes.csv", newline="", encoding="utf-8-sig") as f:
        final_rows = list(csv.DictReader(f))

    out_rows = []
    removed_log = []
    unmapped_log = []

    for r in final_rows:
        code = r["code"]
        if code in REMOVE_382219_LINES:
            removed_log.append(f"{code} ({REMOVE_382219_LINES[code]}): removed - "
                                "own description is split by chemical content "
                                "(antigens/antisera vs methyl chloroform content), "
                                "not by a diagnostic-use term in the line itself")
            continue

        if code in CODE_OVERRIDES:
            group = CODE_OVERRIDES[code]
        else:
            rg = raw_group(code, hs6_groups, epcmd_categories)
            group = MERGE_MAP.get(rg, rg)
            if group not in ALLOWED_GROUPS:
                unmapped_log.append(f"{code} (raw group '{rg}'): no mapping found, "
                                     "defaulting to 'Other' - needs review")
                group = "Other"

        out_rows.append({**r, "group": group})

    columns = ["code", "level", "description", "group", "source", "rule_applied"]
    with open(DATA_DIR / "final_codes_grouped.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    print(f"data/final_codes_grouped.csv: {len(out_rows)} rows (was {len(final_rows)} "
          f"in final_codes.csv, {len(removed_log)} removed via the 382219 re-check)")
    print("\nGroup counts:")
    from collections import Counter
    for g, n in sorted(Counter(r["group"] for r in out_rows).items()):
        print(f"  {g}: {n}")
    print("\n--- REMOVED (382219 re-check) ---")
    for line in removed_log:
        print(" ", line)
    if unmapped_log:
        print("\n--- UNMAPPED (defaulted to Other, needs review) ---")
        for line in unmapped_log:
            print(" ", line)


if __name__ == "__main__":
    main()
