"""
build_epcmd_classification.py

Part 1b/1c: classify each of EPCMD's 68 hs6 groups as CLEAN / MIXED /
UNKNOWN, based on:
  - separate research against eximguru.com (secondary source;
    CBIC's own site was unreachable - DNS failure during that research)
  - my own correction for 902781/902789: that research concluded
    these were an EPCMD transcription error for hs6=902780, but direct
    evidence contradicts that - the Census API (raw/census/902781_2024-12.json,
    raw/census/902789_2024-12.json) shows real, substantial, populated
    trade under both codes ($732.7M and $1.16B world total respectively
    for 2024), while 902780 itself returns "no_data" entirely. Two
    independent web searches confirmed the 2022 Harmonized System
    revision (effective 2022-01-01, adopted by India and the US) split
    the old 9027.80 subheading into 9027.81 "Mass spectrometers" and
    9027.89 "Other" - so 902781/902789 are real, current, distinct hs6
    codes, and the "transcription error" theory is wrong. The secondary
    source (eximguru) the fork used was evidently showing a stale,
    pre-2022 tariff structure.

OUTPUT: data/epcmd_hs6_classification.csv (new file).
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

# classification, official_total_lines (None = unknown), source
CLASSIFICATION = {
    "300510": ("CLEAN", 3, "eximguru.com/hs-codes/3005 (secondary source; CBIC unreachable)"),
    "300590": ("CLEAN", 8, "eximguru.com/hs-codes/3005"),
    "300610": ("CLEAN", 2, "eximguru.com/hs-codes/3006"),
    "300630": ("CLEAN", 1, "eximguru.com/hs-codes/3006"),
    "300640": ("CLEAN", 1, "eximguru.com/hs-codes/3006"),
    "300650": ("CLEAN", 1, "eximguru.com/hs-codes/3006"),
    "300660": ("CLEAN", 3, "eximguru.com/hs-codes/3006"),
    "300670": ("CLEAN", 1, "eximguru.com/hs-codes/3006"),
    "300691": ("CLEAN", 1, "eximguru.com/hs-codes/3006"),
    "382211": ("UNKNOWN", None, "no single authoritative full-chapter-38 source found; multiple HSN DBs confirm the code is real but not that it's the only line"),
    "382212": ("UNKNOWN", None, "same as 382211"),
    "382213": ("UNKNOWN", None, "same as 382211"),
    "382219": ("UNKNOWN", None, "same as 382211"),
    "382290": ("UNKNOWN", None, "same as 382211"),
    "392321": ("UNKNOWN", None, "eximguru.com/hs-codes/3923 page did not show a breakdown"),
    "392390": ("MIXED", 3, "eximguru.com/hs-codes/3923 (official: insulated ware, aseptic bags, other - EPCMD has only 'other')"),
    "401410": ("CLEAN", 2, "eximguru.com/hs-codes/4014"),
    "401490": ("MIXED", 4, "eximguru.com/hs-codes/4014 (official adds feeding-bottle nipples, not in EPCMD)"),
    "401512": ("UNKNOWN", None, "conflicting sources - eximguru shows older 40151100/40151900 numbering, not current 40151200; no source found giving the current complete breakdown"),
    "621010": ("UNKNOWN", None, "62101010/62101020 confirmed real (DGFT notification ref. dated 2022-07-07) but no source found confirming there's no 3rd line"),
    "621040": ("MIXED", None, "multiple independent HSN DBs show non-medical lines under this hs6 (bulletproof/bomb-disposal jackets, fighter-aircraft clothing) alongside EPCMD's 3 PPE lines - at least 6 total, exact count not pinned to one authoritative source"),
    "842310": ("CLEAN", 1, "eximguru.com/hs-codes/8423"),
    "900130": ("CLEAN", 1, "eximguru.com/hs-codes/9001"),
    "900150": ("CLEAN", 1, "eximguru.com/hs-codes/9001"),
    "901811": ("CLEAN", 1, "eximguru.com/hs-codes/9018 (full heading breakdown on one page)"),
    "901812": ("CLEAN", 2, "eximguru.com/hs-codes/9018"),
    "901813": ("CLEAN", 1, "eximguru.com/hs-codes/9018"),
    "901814": ("CLEAN", 1, "eximguru.com/hs-codes/9018"),
    "901819": ("CLEAN", 3, "eximguru.com/hs-codes/9018"),
    "901820": ("CLEAN", 1, "eximguru.com/hs-codes/9018"),
    "901831": ("CLEAN", 1, "eximguru.com/hs-codes/9018"),
    "901832": ("CLEAN", 4, "eximguru.com/hs-codes/9018"),
    "901839": ("CLEAN", 4, "eximguru.com/hs-codes/9018"),
    "901841": ("CLEAN", 1, "eximguru.com/hs-codes/9018"),
    "901849": ("CLEAN", 1, "eximguru.com/hs-codes/9018"),
    "901850": ("CLEAN", 4, "eximguru.com/hs-codes/9018"),
    "901890": ("MIXED", 25, "eximguru.com/hs-codes/9018 - official has 90189033 'Haemofiltration instruments', missing from EPCMD's 24 lines"),
    "901910": ("CLEAN", 3, "eximguru.com/hs-codes/9019"),
    "901920": ("CLEAN", 2, "eximguru.com/hs-codes/9019"),
    "902000": ("CLEAN", 1, "eximguru.com/hs-codes/9020"),
    "902110": ("CLEAN", 1, "eximguru.com/hs-codes/9021"),
    "902121": ("CLEAN", 1, "eximguru.com/hs-codes/9021"),
    "902129": ("CLEAN", 1, "eximguru.com/hs-codes/9021"),
    "902131": ("CLEAN", 1, "eximguru.com/hs-codes/9021"),
    "902139": ("CLEAN", 1, "eximguru.com/hs-codes/9021"),
    "902140": ("CLEAN", 2, "eximguru.com/hs-codes/9021"),
    "902150": ("CLEAN", 1, "eximguru.com/hs-codes/9021"),
    "902190": ("CLEAN", 2, "eximguru.com/hs-codes/9021"),
    "902212": ("CLEAN", 1, "eximguru.com/hs-codes/9022"),
    "902213": ("CLEAN", 1, "eximguru.com/hs-codes/9022"),
    "902214": ("CLEAN", 3, "eximguru.com/hs-codes/9022"),
    "902219": ("CLEAN", 1, "eximguru.com/hs-codes/9022"),
    "902221": ("CLEAN", 1, "eximguru.com/hs-codes/9022"),
    "902229": ("CLEAN", 1, "eximguru.com/hs-codes/9022"),
    "902230": ("CLEAN", 1, "eximguru.com/hs-codes/9022"),
    "902290": ("CLEAN", 5, "eximguru.com/hs-codes/9022"),
    "902511": ("CLEAN", 2, "eximguru.com/hs-codes/9025"),
    "902519": ("MIXED", 3, "eximguru.com/hs-codes/9025 - official adds 90251990 'other', missing from EPCMD"),
    "902710": ("CLEAN", 1, "eximguru.com/hs-codes/9027"),
    "902720": ("CLEAN", 1, "eximguru.com/hs-codes/9027"),
    "902730": ("CLEAN", 3, "eximguru.com/hs-codes/9027"),
    "902750": ("CLEAN", 4, "eximguru.com/hs-codes/9027"),
    "902780": ("N/A - NOT A REAL ACTIVE CODE", 0, "Census API returns no_data entirely for this hs6 (raw/census/902780_2024-12.json) - this hs6 is effectively obsolete/unused post-HS2022, superseded by 902781+902789. Not counted as one of the 68 groups; see 902781/902789 instead."),
    "902781": ("UNKNOWN (corrected from fork's finding)", None, "Fork concluded this was a transcription error for 902780 - OVERRIDDEN: Census API shows real, substantial trade under 902781 specifically ($732.7M world, 2024; raw/census/902781_2024-12.json), and two independent web searches confirm HS2022 created 9027.81 'Mass spectrometers' as a genuine new subheading (effective 2022-01-01, adopted by India). Single EPCMD line (90278100) plausibly = the whole subheading (common pattern when a new subheading isn't further split nationally), but no authoritative Indian 8-digit source was found to confirm there's exactly 1 line - marking UNKNOWN rather than assuming CLEAN."),
    "902789": ("UNKNOWN (corrected from fork's finding)", None, "Same correction as 902781 - this is the real 'Other' half of the HS2022 split (9027.89), not a transcription error. Census shows $1.16B world trade under this code (2024). EPCMD has 4 lines (90278910/20/30/90); by analogy with the OLD undivided 9027.80 structure (which the fork found had 5 lines including 90278040 'Nuclear magnetic resonance instruments'), there MAY be an equivalent 90278940-type line carried over under the new 902789 split that EPCMD is missing - but this is an unconfirmed hypothesis, not a sourced fact. Marking UNKNOWN rather than asserting MIXED on an analogy alone."),
    "902790": ("CLEAN", 3, "eximguru.com/hs-codes/9027"),
    "940210": ("MIXED", 2, "eximguru.com/hs-codes/9402 - official adds 94021090 'other' (ambiguous - could itself be medical, but EPCMD doesn't list it), missing from EPCMD"),
    "940290": ("CLEAN", 3, "eximguru.com/hs-codes/9402"),
    "961900": ("CLEAN", 5, "eximguru.com/hs-codes/9619"),
}


def main():
    with open(DATA_DIR / "epcmd_151_codes.csv", newline="", encoding="utf-8-sig") as f:
        epcmd_rows = list(csv.DictReader(f))

    epcmd_hs6_info = {}
    for r in epcmd_rows:
        hs6 = r["hs6"]
        epcmd_hs6_info.setdefault(hs6, {"count": 0, "desc": r["description"]})
        epcmd_hs6_info[hs6]["count"] += 1

    with open(HERE / "hs6_codes.csv", newline="", encoding="utf-8") as f:
        original_48 = set(r["hs6"] for r in csv.DictReader(f) if r["group"] != "Candidate")

    out_rows = []
    for hs6 in sorted(epcmd_hs6_info):
        cls, total, source = CLASSIFICATION.get(hs6, ("UNKNOWN", None, "not researched"))
        out_rows.append({
            "hs6": hs6,
            "description": epcmd_hs6_info[hs6]["desc"][:80],
            "classification": cls,
            "epcmd_line_count": epcmd_hs6_info[hs6]["count"],
            "total_line_count": total if total is not None else "unknown",
            "in_original_48": "yes" if hs6 in original_48 else "no",
            "source": source,
        })

    with open(DATA_DIR / "epcmd_hs6_classification.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    counts = {}
    for r in out_rows:
        key = r["classification"].split(" ")[0].split("(")[0].strip()
        counts[key] = counts.get(key, 0) + 1
    print("Classification counts:", counts)
    print(f"\nWrote data/epcmd_hs6_classification.csv ({len(out_rows)} rows)")


if __name__ == "__main__":
    main()
