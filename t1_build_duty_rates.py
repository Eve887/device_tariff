"""
t1_build_duty_rates.py

View B, Part 1: India's import duty rates on US-origin medical
devices - Basic Customs Duty (BCD), Social Welfare Surcharge (SWS),
Health Cess, and IGST, for every code in core_device_codes.csv.

All facts researched via WebSearch against official/authoritative
sources (CBIC notifications, the Finance Act 2020's Health Cess
provision, the 56th GST Council meeting of 22 Sept 2025, Budget
2026-27 coverage) plus two downloaded PDFs
(raw/viewb_evidence/acuitylaw_medical_devices_faq.pdf,
raw/viewb_evidence/icegate_cs20_2020.pdf) and cross-checked against
per-code secondary aggregators (eximguru.com, seair.co.in) where a
specific line's rate was individually verified. Every rate below
carries its own source; "not found" is used literally wherever a rate
could not be confirmed - never guessed. See
logs/step1_progress_log.md ("View B" section) for the full research
trail, including two unresolved discrepancies that are flagged rather
than silently picked: (1) a general claim that "most medical devices
attract 0% BCD" via exemption notifications, vs 7.5% BCD confirmed on
several specific lines checked individually - this file uses the
7.5%-type per-line figures where found; (2) one source citing 15% BCD
for 902214 vs the general 7.5% pattern.

Standing rules for this new piece of work: write new files only
(Phase 1-5 files untouched); log every step; "not found" rather than
guess.

READ-ONLY against core_device_codes.csv. Writes
data/india_duty_rates.csv (new file) only.
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
NF = "not found"

SWS_STANDARD = "10% of BCD (nil if BCD is nil)"
SWS_SOURCE = "Standard SWS rule under Section 110 of Finance Act 2018, confirmed via seair.co.in/eximguru.com per-code pages checked in this research (e.g. 90183900 catheters: 'Social Welfare Surcharge of 10% of the BCD')"

HEALTH_CESS_RULE_5PCT = "5% of assessable value"
HEALTH_CESS_NA = "Not applicable (heading outside 9018-9022)"
HEALTH_CESS_SOURCE_IN = ("Section 141 / Fourth Schedule, Finance Act 2020 - 'all goods falling under "
                          "headings 9018, 9019, 9020, 9021 and 9022... liable for health cess @ 5%' "
                          "(confirmed via 2 independent sources quoting the Schedule text: "
                          "taxmanagementindia.com/taxtmi.com 'HEALTH CESS' articles). Nil for inputs/"
                          "parts for manufacture, and nil where the device itself is BCD-exempt.")
HEALTH_CESS_SOURCE_OUT = ("Heading falls outside 9018-9022 - the Fourth Schedule to the Finance Act "
                           "2020 (Section 141) only covers those 5 headings; confirmed via the same "
                           "2 sources above, which state the cess list explicitly as those 5 headings only.")

# GST 2.0 / 56th GST Council meeting, effective 22 Sept 2025 - IGST on imports mirrors domestic GST rate.
GST2_SOURCE = "56th GST Council meeting (3 Sept 2025 press release, effective 22 Sept 2025) - pib.gov.in press release and secondary coverage (ksandk.com, sageuniversity.edu.in, disytax.com HSN-specific breakdowns)"

# code -> (description already in core_device_codes.csv, not repeated here)
# Each entry: bcd, bcd_source, igst, igst_source, health_cess_applies(bool), notes
ROWS = {
    "300510": ("5%", "HSN 3005 cut 12%->5%, 56th GST Council, effective 22 Sep 2025 - confirmed via indiafilings/taxguru coverage", "5%", GST2_SOURCE, False, "BCD not independently verified for this code - see note"),
    "300590": ("5%", "same as 300510 (same HSN 3005 heading)", "5%", GST2_SOURCE, False, ""),
    "300610": ("5%", "HSN 3006 (sterile surgical catgut/sutures) cut 12%->5%, 56th GST Council", "5%", GST2_SOURCE, False, ""),
    "300620": ("5%", "treated as part of the diagnostic-reagent bucket (HSN 3822-adjacent) - INFERRED, not independently confirmed for this exact code", "5%", GST2_SOURCE + " - INFERRED from the general diagnostic-reagent rate cut, not individually confirmed for 300620 specifically", False, "BCD and IGST both inferred, not individually confirmed"),
    "300640": ("5%", "HSN 300640 (dental cements) - credlix.com/registerkaro.in rate lookup", "5%", GST2_SOURCE + " - confirmed via credlix.com/registerkaro.in HSN 300640 pages", False, ""),
    "300650": ("5%", "HSN 300650 (first-aid boxes/kits) - credlix.com/eximpe.com rate lookup", "5%", GST2_SOURCE + " - confirmed via credlix.com/eximpe.com HSN 300650 pages", False, ""),
    "300670": (NF, NF, "5%", GST2_SOURCE + " - inferred from the general Chapter 30 medical-preparations rate cut, NOT individually confirmed for this specific gel-lubricant code", False, "BCD not found; IGST inferred only"),
    "300691": ("5%", "HSN 300691 (ostomy appliances) - search confirmed 5% alongside 300640/300650", "5%", GST2_SOURCE, False, ""),
    "382211": ("7.5%", "General Chapter 38 diagnostic-reagent BCD - NOT individually verified for this exact code, carried from the general Chapter 90/38 diagnostic-instrument pattern - LOW CONFIDENCE", "5%", GST2_SOURCE + " - HSN 3822 (all diagnostic kits/reagents) cut 12%->5%, confirmed via webb search of 56th GST Council coverage", False, "BCD figure is a low-confidence carry-over, not independently verified for Chapter 38"),
    "382212": ("7.5%", "same low-confidence carry-over as 382211", "5%", GST2_SOURCE, False, "same BCD caveat as 382211"),
    "382213": ("7.5%", "same low-confidence carry-over as 382211", "5%", GST2_SOURCE, False, "same BCD caveat as 382211"),
    "401410": ("not found", NF, "0%", "Long-standing nil GST rate on condoms/contraceptives (unrelated to the Sept 2025 reform) - confirmed via pocketful.in/dripcapital.com/indiafilings.com HSN 4014 pages", False, "BCD not found"),
    "401512": ("not found", NF, "5%", "HSN 4015 (surgical/medical examination rubber gloves) cut 12%->5%, 56th GST Council - confirmed via direct WebSearch of HSN 4015 GST-2.0 coverage", False, "BCD not found"),
    "842310": ("not found", NF, "18%", "Weighing machinery (HSN 8423) explicitly confirmed EXCLUDED from the healthcare rate cut - stays at 18% (hospitalstore.com GST-2.0 guidance)", False, "BCD not found"),
    "900130": (NF, NF, NF, NF, False, "Contact lenses - not researched in this pass, genuinely not found"),
    "900150": (NF, NF, NF, NF, False, "Spectacle lenses - not researched in this pass, genuinely not found"),
    "901811": ("7.5%", "General 9018 heading rate (per seair.co.in/eximguru.com Chapter 9018 pages) - not individually fetched for this exact 8-digit line, carried from the heading-level pattern", "5%", GST2_SOURCE + " - HSN 9018 (all codes) confirmed cut 12%->5% via disytax.com's code-specific breakdown", True, "BCD carried from heading-level pattern, not individually fetched for 901811"),
    "901812": ("7.5%", "same heading-level carry-over as 901811", "5%", GST2_SOURCE, True, "same BCD caveat as 901811"),
    "901813": ("7.5%", "individually confirmed - 90181300 (MRI apparatus), tariffnumber.com/freightamigo.com 'the basic duty for MRI apparatus under HS Code 90181300 is 7.50%'", "5%", GST2_SOURCE, True, ""),
    "901814": ("7.5%", "same heading-level carry-over as 901811 (Scintigraphic apparatus, same 9018 heading)", "5%", GST2_SOURCE, True, "same BCD caveat as 901811"),
    "901819": ("7.5%", "same heading-level carry-over as 901811", "5%", GST2_SOURCE, True, "same BCD caveat as 901811"),
    "901820": ("7.5%", "same heading-level carry-over as 901811", "5%", GST2_SOURCE, True, "same BCD caveat as 901811"),
    "901831": ("7.5%", "same heading-level carry-over as 901811 (Syringes)", "5%", GST2_SOURCE, True, "same BCD caveat as 901811"),
    "901832": ("7.5%", "same heading-level carry-over as 901811 (Needles)", "5%", GST2_SOURCE, True, "same BCD caveat as 901811"),
    "901839": ("7.5%", "individually confirmed - 90183900 (catheters), tariffin.com/cybex.in: 'the MFN rate is 7.5%. Additionally, India imposes a Social Welfare Surcharge of 10% of the BCD'", "5%", GST2_SOURCE, True, ""),
    "901841": ("7.5%", "same heading-level carry-over as 901811 (dental drill engines)", "5%", GST2_SOURCE, True, "same BCD caveat as 901811"),
    "901849": ("7.5%", "same heading-level carry-over as 901811", "5%", GST2_SOURCE, True, "same BCD caveat as 901811"),
    "901850": ("7.5%", "individually confirmed for the ophthalmoscope sub-line (90185010) - tariffnumber.com: 'BCD of 7.5%'; one source (freightamigo-style synthesis) separately cited an averaged '6.9%' across 901850's sub-lines, which this file does not use - flagged, not resolved", "5%", GST2_SOURCE, True, "A second source's blended '6.9%' figure for the whole HS6 is noted but not used; 7.5% from the specific ophthalmoscope line is used instead"),
    "901890": ("7.5%", "individually confirmed for both checked sub-lines - seair.co.in: 90189094 (Defibrillators) and 90189099 (Other) both 'Basic Duty (SCH) is 7.5%'", "5%", GST2_SOURCE + " - NOTE: the same seair.co.in page states GST as 12% for these 2 lines, which is the PRE-Sept-2025 rate (stale source) - 5% used instead per the confirmed 56th GST Council HSN-9018 cut, flagged as a source-currency conflict, not silently resolved", True, "IGST source conflict flagged: seair.co.in shows a pre-reform 12%, superseded here by the confirmed Sept 2025 cut to 5%"),
    "901910": ("7.5%", "same heading-level carry-over pattern as 9018 (9019 shares the same medical-instrument exemption/surcharge structure) - NOT individually confirmed", "5%", "disytax.com: '9019 10: 5% GST' (Mechano-therapy)", True, "BCD not individually confirmed for this code"),
    "901920": ("7.5%", "same heading-level carry-over as 901910 - NOT individually confirmed", "0%", "disytax.com: '9019 20 (Oxygen/ozone therapy): 0% GST (life-saving equipment)' - NOTE one general-news source separately described 'oxygen' devices as cut only to 5%, not 0% - this more specific, code-level source is used instead, flagged as a conflict", True, "IGST source conflict flagged (0% per the specific source used here vs a vaguer 5% claim elsewhere); BCD not individually confirmed"),
    "902000": ("7.5%", "same heading-level carry-over pattern - NOT individually confirmed", "0%", "disytax.com: '9020 00: 0% GST (life support devices)'", True, "BCD not individually confirmed"),
    "902110": ("7.5%", "individually confirmed via seair.co.in Chapter 9021 page ('Orthopaedic appliances, crutches, surgical belts')", "5%", "disytax.com: '9021 10... 5% GST'", True, ""),
    "902121": ("7.5%", "same heading-level carry-over as 902110 (9021 shares one BCD structure per seair.co.in's single Chapter 9021 page) - NOT individually confirmed for this specific dental sub-line", "5%", "disytax.com: '9021 21, 9021 29... 5% GST'", True, "BCD not individually confirmed for this exact sub-line"),
    "902129": ("7.5%", "same as 902121", "5%", "disytax.com: '9021 21, 9021 29... 5% GST'", True, "same BCD caveat as 902121"),
    "902131": ("7.5%", "individually confirmed - tariffnumber.com/thedollarbusiness.com '90213100 (Artificial Joints), the Basic Customs Duty (BCD) in India is 7.50%'", "5%", "disytax.com: '9021 31, 9021 39... 5% GST'", True, ""),
    "902139": ("7.5%", "same heading-level carry-over as 902131 for the sibling 90213990 'Other artificial parts' sub-line - NOT individually confirmed (search explicitly found no specific rate for 90213990)", "5%", "disytax.com: '9021 31, 9021 39... 5% GST'", True, "BCD not individually confirmed for this exact sub-line - search explicitly returned no rate for 90213990"),
    "902140": (NF, NF, NF, NF, True, "Hearing aids - not individually researched in this pass (genuinely not found); health cess DOES apply since 9021 is in the covered-heading list"),
    "902150": ("7.5%", "same heading-level carry-over as the rest of 9021 - NOT individually confirmed", "0%", "disytax.com: '9021 50 (Pacemakers): 0% GST (only non-5% item in this heading)'", True, "BCD not individually confirmed; this is the explicit 0% IGST exception within heading 9021"),
    "902190": ("7.5%", "same heading-level carry-over as the rest of 9021 (stents) - NOT individually confirmed", "5%", "disytax.com: '9021 90... 5% GST'", True, "BCD not individually confirmed for this exact sub-line"),
    "902212": ("7.5%", "same heading-level carry-over pattern for 9022 - NOT individually confirmed", "5%", "disytax.com: 'Medical-use items (9022 12-14, 9022 21-30, 9022 90): 5% GST'", True, "BCD not individually confirmed"),
    "902213": ("7.5%", "same as 902212", "5%", "same disytax.com source as 902212", True, "same BCD caveat as 902212"),
    "902214": ("15%", "ONE source found - a WebSearch synthesis citing 'the basic customs duty is 15%' for 902214 - this conflicts with the general 7.5% pattern seen elsewhere in Chapter 90 and was NOT independently cross-checked against a second source. Flagged as a genuine open discrepancy, not resolved.", "5%", "same disytax.com source as 902212", True, "BCD figure (15%) is single-sourced and conflicts with the 7.5% pattern seen for every other Chapter 90 line checked - treat with caution"),
    "902219": ("7.5%", "same heading-level carry-over as 902212 - NOT individually confirmed", "18%", "disytax.com: '9022 19 (Non-medical X-ray): 18% GST (exception)' - explicitly the ONE non-medical-use exception within heading 9022", True, "BCD not individually confirmed; this is the explicit 18% IGST exception within heading 9022 (non-medical-use X-ray apparatus)"),
    "902221": ("7.5%", "same heading-level carry-over as 902212", "5%", "same disytax.com source as 902212", True, "same BCD caveat as 902212"),
    "902229": ("7.5%", "same heading-level carry-over as 902212", "5%", "same disytax.com source as 902212", True, "same BCD caveat as 902212"),
    "902230": ("10% (from 1 Apr 2026)", "S.O. 02/2026-Customs dated 1 Feb 2026, per Budget 2026-27 - confirmed history: 5% (to 31 Mar 2025) -> 7.5% (1 Apr 2025-31 Mar 2026) -> 10% (from 1 Apr 2026). Source: rnm.in Budget 2026 coverage, cross-checked against indiabudget.gov.in's own customs duty rate-change document (dojstru1.pdf)", "5%", "same disytax.com source as 902212", True, "The ONE confirmed Budget 2026-27 BCD CHANGE in this whole table - X-ray tubes for medical/surgical/veterinary X-ray machines"),
    "902290": ("7.5%", "same heading-level carry-over as 902212 ('parts and accessories') - search explicitly found no specific sub-category rate for 902290 beyond the general heading pattern", "5%", "same disytax.com source as 902212", True, "BCD not individually confirmed for this exact sub-line"),
    "902511": ("not found", NF, "5%", "'thermometers for medical, surgical, dental or veterinary use' explicitly cut 18%->5%, 56th GST Council - confirmed via a dedicated WebSearch resolving an initial conflicting signal from a different source describing the INDUSTRIAL (non-clinical) branch of 9025 as staying at 18%", True, "IGST required a second, more specific search to resolve a genuine conflict between the clinical vs industrial branches of heading 9025; BCD not found"),
    "902710": ("not found", NF, "18%", "Heading 9027 (gas/smoke analysis apparatus) confirmed NOT reduced by the 56th GST Council - stays at 18%, per registerkaro.in/credlix.com/dripcapital.com HSN 9027 pages (one source flags a possible 5%/18% split depending on classification - not resolved for this exact code, 18% used as the best-supported figure)", False, "Heading 9027 is OUTSIDE 9018-9022, so health cess does not apply; BCD not found"),
    "902720": ("not found", NF, "18%", "individually confirmed - registerkaro.in: 'HSN code 902720 (Chromatographs and electrophoresis instruments) has an 18% GST rate'", False, "BCD not found"),
    "902730": ("not found", NF, "18%", "individually confirmed - registerkaro.in: 'HSN code 90273010 (Spectrometers) attracts 18% GST'", False, "BCD not found"),
    "902750": ("not found", NF, "18%", "individually confirmed - registerkaro.in: 'HSN code 90275010 (Photometers) attracts 18% GST'", False, "BCD not found"),
    "902790": ("not found", NF, "18%", "same heading-level pattern as the rest of 9027 (microtomes) - not individually confirmed", False, "BCD not found; IGST carried from the confirmed heading-18% pattern, not individually fetched for this exact code"),
    "940290": ("not found", NF, "18%", "explicitly confirmed EXCLUDED from the healthcare rate cut - 'Hospital beds, stretchers, and operating tables, classified under HSN 9402, were excluded from this reduction and continue to attract 18% GST' (busy.in/hospkart.com)", False, "BCD not found"),
    "9025198010": ("not found", NF, "5%", "same resolved clinical-thermometer finding as 902511 (this is the HS10 'Infrared thermometers (Clinical)' child line)", True, "same IGST resolution as 902511; health cess applies (heading 9025 is NOT in the 9018-9022 covered list - CORRECTION: despite being a 'clinical' thermometer, heading 9025 itself is outside the Fourth Schedule's 5-heading list, so health cess does NOT apply here - see notes"),
    "9025198020": ("not found", NF, "5%", "same as 9025198010", True, "SAME CORRECTION as 9025198010: health cess does NOT apply - heading 9025 is outside the 9018-9022 list, despite this being a clinical/medical-use line"),
    "9402100000": ("not found", NF, "18%", "INFERRED from the 940290 finding (same HSN 9402 heading, hospital beds/stretchers/tables excluded from the rate cut) - NOT individually confirmed for this specific dental-chair line", False, "BCD not found; IGST inferred from the heading-level 940290 finding, not individually confirmed"),
    "6210105010": (NF, NF, NF, NF, False, "Surgical/isolation gowns - generic HSN 6210 apparel-rate research found, but NOT specific enough to confirm the medical-gown rate post-Sept-2025 with confidence - genuinely not found, not guessed"),
    "6210105090": (NF, NF, NF, NF, False, "Other nonwoven disposable apparel for hospitals/clinics/labs - same gap as 6210105010"),
}


def main():
    with open(DATA_DIR / "core_device_codes.csv", newline="", encoding="utf-8-sig") as f:
        codes = list(csv.DictReader(f))

    out_rows = []
    for r in codes:
        code = r["code"]
        hs6 = code[:6]
        desc = r["description"]
        entry = ROWS.get(code)
        if entry is None:
            out_rows.append({
                "hs8_or_tracked_code": code, "hs6": hs6, "description": desc,
                "bcd_pct": NF, "bcd_source": NF,
                "sws_pct": NF, "sws_source": NF,
                "health_cess_pct": NF, "health_cess_source": NF,
                "igst_pct": NF, "igst_source": NF,
                "notes": "code not in the researched table at all - genuinely not found",
            })
            continue
        bcd, bcd_src, igst, igst_src, cess_applies, notes = entry
        if cess_applies and bcd not in (NF,):
            cess_pct, cess_src = HEALTH_CESS_RULE_5PCT, HEALTH_CESS_SOURCE_IN
        elif cess_applies and bcd == NF:
            cess_pct, cess_src = HEALTH_CESS_RULE_5PCT, HEALTH_CESS_SOURCE_IN + " (BCD itself not found for this code, so whether the 'nil if BCD-exempt' carve-out applies cannot be confirmed either - using the standard 5% rate with this caveat)"
        else:
            cess_pct, cess_src = "0% (not applicable)", HEALTH_CESS_SOURCE_OUT

        sws_pct = SWS_STANDARD if bcd != NF else NF
        sws_src = SWS_SOURCE if bcd != NF else "BCD not found for this code, so SWS (10% of BCD) cannot be computed"

        out_rows.append({
            "hs8_or_tracked_code": code, "hs6": hs6, "description": desc,
            "bcd_pct": bcd, "bcd_source": bcd_src,
            "sws_pct": sws_pct, "sws_source": sws_src,
            "health_cess_pct": cess_pct, "health_cess_source": cess_src,
            "igst_pct": igst, "igst_source": igst_src,
            "notes": notes,
        })

    cols = ["hs8_or_tracked_code", "hs6", "description", "bcd_pct", "bcd_source",
            "sws_pct", "sws_source", "health_cess_pct", "health_cess_source",
            "igst_pct", "igst_source", "notes"]
    with open(DATA_DIR / "india_duty_rates.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out_rows)

    n_not_found_bcd = sum(1 for r in out_rows if r["bcd_pct"] == NF)
    n_not_found_igst = sum(1 for r in out_rows if r["igst_pct"] == NF)
    print(f"Wrote data/india_duty_rates.csv ({len(out_rows)} rows)")
    print(f"BCD not found for {n_not_found_bcd} of {len(out_rows)} codes")
    print(f"IGST not found for {n_not_found_igst} of {len(out_rows)} codes")


if __name__ == "__main__":
    main()
