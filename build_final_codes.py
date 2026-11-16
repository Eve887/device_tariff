"""
build_final_codes.py

Builds data/final_codes.csv and data/lab_instruments_codes.csv per the
user's exact rules (see logs/step1_progress_log.md for the full
reasoning trail). Read-only against hs6_codes.csv and
data/epcmd_hs6_classification.csv; does not modify either.
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

EXPLICIT_KEEP_WHOLE = {"901890", "382211", "382212", "382213", "401512"}
EXCEPT_FROM_ORIGINAL_48 = {"382290", "940210", "382219"}  # dropped or moved to HS10-only
EXPLICIT_DROP = {"392390", "382290", "630790"}
HS10_ONLY_CODES = {"902519", "940210", "401490", "621040", "392321", "621010", "382219"}
LAB_INSTRUMENTS = {"902781", "902789"}

# (hs10, description, keep, reason)
HS10_LINES = {
    "902519": [
        ("9025198010", "Infrared thermometers (Clinical)", True, "child of 'Clinical' branch"),
        ("9025198020", "Other (Clinical)", True, "child of 'Clinical' branch"),
        ("9025194000", "Pyrometers", False, "industrial, not clinical"),
        ("9025198060", "Infrared thermometers (non-clinical 'Other' branch)", False, "sibling 'Other' branch to Clinical, not clinical"),
        ("9025198085", "Other (non-clinical 'Other' branch)", False, "sibling 'Other' branch to Clinical, not clinical"),
    ],
    "940210": [
        ("9402100000", "Dentists', barbers' or similar chairs and parts thereof", True, "'Dentists'' matches dental use"),
    ],
    "401490": [
        ("4014901000", "Nursing nipples", False, "no medical/surgical/dental/clinical/diagnostic keyword, parent is 'hygienic or pharmaceutical' not on keyword list"),
        ("4014905000", "Other", False, "same as above"),
    ],
    "621040": [
        ("6210401500", "Recreational performance outerwear, man-made fibers, impregnated/coated", False, "no medical keyword anywhere in hierarchy"),
        ("6210402531", "Ski/snowboard pants", False, "no medical keyword"),
        ("6210402539", "Other (ski/snowboard-type)", False, "no medical keyword"),
        ("6210402540", "Overalls and coveralls", False, "no medical keyword"),
        ("6210402550", "Other", False, "no medical keyword"),
        ("6210402800", "Other, impregnated/coated", False, "no medical keyword"),
        ("6210402917", "Other, silk content, trousers/breeches/shorts", False, "no medical keyword"),
        ("6210402918", "Other, silk content, overalls/coveralls", False, "no medical keyword"),
        ("6210402919", "Other, silk content, other", False, "no medical keyword"),
        ("6210402933", "Other, trousers/breeches/shorts", False, "no medical keyword"),
        ("6210402945", "Other, overalls/coveralls", False, "no medical keyword"),
        ("6210402960", "Other", False, "no medical keyword"),
        ("6210403500", "Other category, man-made fibers, impregnated/coated", False, "no medical keyword"),
        ("6210405531", "Ski/snowboard pants", False, "no medical keyword"),
        ("6210405539", "Other", False, "no medical keyword"),
        ("6210405540", "Overalls and coveralls", False, "no medical keyword"),
        ("6210405550", "Other", False, "no medical keyword"),
        ("6210407500", "Other, impregnated/coated", False, "no medical keyword"),
        ("6210408017", "Other, silk content, trousers/breeches/shorts", False, "no medical keyword"),
        ("6210408018", "Other, silk content, overalls/coveralls", False, "no medical keyword"),
        ("6210408019", "Other, silk content, other", False, "no medical keyword"),
        ("6210408033", "Other, trousers/breeches/shorts", False, "no medical keyword"),
        ("6210408045", "Other, overalls/coveralls", False, "no medical keyword"),
        ("6210408060", "Other", False, "no medical keyword"),
    ],
    "392321": [
        ("3923210011", "Reclosable bags, small, integral extruded closure", False, "no medical keyword, generic packaging"),
        ("3923210020", "Reclosable bags, with sliders", False, "no medical keyword"),
        ("3923210030", "Other reclosable bags", False, "no medical keyword"),
        ("3923210080", "Small bags, other", False, "no medical keyword"),
        ("3923210085", "Polyethylene retail carrier bags (PRCBs)", False, "no medical keyword, retail shopping bags"),
        ("3923210095", "Other", False, "no medical keyword"),
    ],
    "621010": [
        ("6210105010", "Surgical or isolation gowns", True, "explicit 'Surgical' keyword"),
        ("6210105090", "Other (nonwoven disposable apparel for hospitals/clinics/laboratories)", True, "parent text explicitly says hospitals/clinics/laboratories ('clinics' matches clinical use)"),
        ("6210102000", "Of fabrics formed on a base of paper", False, "no medical keyword"),
        ("6210107000", "Disposable briefs and panties designed for one-time use", False, "hygiene product, not explicitly medical/clinical"),
        ("6210109010", "Overalls and coveralls", False, "no medical keyword"),
        ("6210109040", "Other", False, "no medical keyword"),
    ],
    "382219": [
        ("3822190010", "Containing antigens or antisera, with methyl chloroform/carbon tetrachloride", True, "child of 'Diagnostic or laboratory reagents' parent heading"),
        ("3822190030", "Containing antigens or antisera, other", True, "child of 'Diagnostic or laboratory reagents' parent heading"),
        ("3822190040", "Other, with methyl chloroform/carbon tetrachloride", True, "child of 'Diagnostic or laboratory reagents' parent heading"),
        ("3822190080", "Other", True, "child of 'Diagnostic or laboratory reagents' parent heading"),
    ],
}


def main():
    with open(HERE / "hs6_codes.csv", newline="", encoding="utf-8") as f:
        original_48 = {r["hs6"]: r["description"] for r in csv.DictReader(f) if r["group"] != "Candidate"}

    with open(DATA_DIR / "epcmd_hs6_classification.csv", newline="", encoding="utf-8-sig") as f:
        epcmd_class = {r["hs6"]: r for r in csv.DictReader(f)}

    clean_52 = {hs6 for hs6, r in epcmd_class.items() if r["classification"] == "CLEAN"}

    whole_hs6 = set()
    whole_hs6 |= (set(original_48) - EXCEPT_FROM_ORIGINAL_48)
    whole_hs6 |= clean_52
    whole_hs6 |= EXPLICIT_KEEP_WHOLE
    whole_hs6 -= EXPLICIT_DROP  # safety net, in case of overlap

    final_rows = []
    dropped_log = []

    for hs6 in sorted(whole_hs6):
        in_48 = hs6 in original_48
        in_epcmd = hs6 in epcmd_class
        source = "both" if (in_48 and in_epcmd) else ("ours" if in_48 else "EPCMD")
        desc = original_48.get(hs6) or (epcmd_class[hs6]["description"] if in_epcmd else "")
        if hs6 in EXPLICIT_KEEP_WHOLE:
            rule = "explicitly kept whole HS6 per instruction (overrides non-CLEAN classification)"
        elif hs6 in clean_52 and in_48:
            rule = "CLEAN per EPCMD classification, also in our original 48"
        elif hs6 in clean_52:
            rule = "CLEAN per EPCMD classification, new addition beyond our original 48"
        elif in_48:
            rule = "kept from original 48 (no EPCMD match found for this hs6)" if not in_epcmd else "kept from original 48 (per 'keep all 48 except...' rule)"
        else:
            rule = "kept"
        final_rows.append({"code": hs6, "level": "HS6", "description": desc,
                            "source": source, "rule_applied": rule})

    for hs6, lines in HS10_LINES.items():
        any_kept = False
        for hs10, desc, keep, reason in lines:
            if keep:
                any_kept = True
                final_rows.append({"code": hs10, "level": "HS10", "description": desc,
                                    "source": "EPCMD" if hs6 not in original_48 else "both",
                                    "rule_applied": f"HS10-only filter on {hs6}: kept - {reason}"})
            else:
                dropped_log.append(f"{hs6} -> {hs10} ({desc}): excluded - {reason}")
        if not any_kept:
            dropped_log.append(f"{hs6}: ALL lines excluded, code dropped entirely (per 'if a code has none, drop it and log it')")

    for hs6 in EXPLICIT_DROP:
        dropped_log.append(f"{hs6}: dropped per explicit instruction")

    with open(DATA_DIR / "final_codes.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["code", "level", "description", "source", "rule_applied"])
        w.writeheader()
        w.writerows(final_rows)

    lab_rows = []
    for hs6 in sorted(LAB_INSTRUMENTS):
        desc = epcmd_class.get(hs6, {}).get("description", "")
        lab_rows.append({"code": hs6, "level": "HS6", "description": desc,
                          "source": "EPCMD",
                          "rule_applied": "HS2022 split of old 9027.80 (Mass spectrometers / Other analytical instruments) - kept separate per instruction, not in final_codes.csv"})
    with open(DATA_DIR / "lab_instruments_codes.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["code", "level", "description", "source", "rule_applied"])
        w.writeheader()
        w.writerows(lab_rows)

    print(f"final_codes.csv: {len(final_rows)} rows "
          f"({sum(1 for r in final_rows if r['level']=='HS6')} HS6, "
          f"{sum(1 for r in final_rows if r['level']=='HS10')} HS10)")
    print(f"lab_instruments_codes.csv: {len(lab_rows)} rows")
    print("\n--- DROPPED / EXCLUDED LOG ---")
    for line in dropped_log:
        print(" ", line)


if __name__ == "__main__":
    main()
