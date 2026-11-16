"""
build_epcmd_151_csv.py

Part 1a: turn the text extracted from raw/epcmd/151_HS_code.pdf (EPCMD's
own "151 HS code" PDF, downloaded from
https://www.epcmd.in/assets/img/product_panel/151%20HS%20code.pdf) into
a structured CSV. The code/category/description triples below were
transcribed directly from that PDF (read twice, independently, from two
separate downloads of the same file, with identical results both times)
and were not altered.

OUTPUT: data/epcmd_151_codes.csv (new file) with columns:
    hs8, description, hs6, category
hs6 is simply the first 6 characters of hs8 (the literal numeric
prefix). Whether that string prefix always equals a real internationally
harmonized 6-digit subheading is checked separately in Part 1b, not
assumed here - a couple of codes (e.g. 90278100) look like they might
not follow the usual digit-7/8 national-split convention, and that is
exactly what Part 1b's CBIC/DGFT cross-check resolves.
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

ROWS = [
    # (hs8, category, description)
    ("30051010", "Consumable & Disposable", "Adhesive guaze"),
    ("30051020", "Consumable & Disposable", "Adhesive tape"),
    ("30051090", "Consumable & Disposable", "other"),
    ("30059010", "Consumable & Disposable", "Cotton wool, medicated"),
    ("30059020", "Consumable & Disposable", "Poultice of kaolin"),
    ("30059030", "Consumable & Disposable", "Lint, medicated"),
    ("30059040", "Consumable & Disposable", "Bandages"),
    ("30059050", "Consumable & Disposable", "Burn therapy dressing soaked in protective gel"),
    ("30059060", "Consumable & Disposable", "Micro pores surgical tapes"),
    ("30059070", "Consumable & Disposable", "Corn removers and callous removers"),
    ("30059090", "Consumable & Disposable", "other"),
    ("30061010", "Consumable & Disposable", "Sterile, surgical catgut and similar sterile suture materials (including sterile absorbable surgical or dental yarns) and sterile tissue adhesives for wound closure"),
    ("30061020", "Consumable & Disposable", "Sterile laminaria and sterile laminaria tents, sterile absorbable surgical or dental haemostatics, sterile surgical or dental adhesion barriers, whether or not absorbable"),
    ("30063000", "Consumable & Disposable", "Opacifying preparations for X-ray examinations; diagnostic reagents designed to be administered to the patient"),
    ("30065000", "Consumable & Disposable", "First-aid boxes and kits"),
    ("30066010", "Consumable & Disposable", "Contraceptive based on hormones"),
    ("30066020", "Consumable & Disposable", "Contraceptive base on other product of heading 2937"),
    ("30066030", "Consumable & Disposable", "Contraceptive based on spermicides"),
    ("30067000", "Consumable & Disposable", "Gel preparations designed to be used in human or veterinary medicine as a lubricant for parts of the body for surgical operations or physical examinations or as a coupling agent between the body and medical instruments"),
    ("30069100", "Consumable & Disposable", "Appliances identifiable for ostomy use"),
    ("39232100", "Consumable & Disposable", "Sacks and bags (including cones): Of polymers of ethylene"),
    ("39239090", "Consumable & Disposable", "other"),
    ("40141010", "Consumable & Disposable", "Rubber contraceptives, male (condoms)"),
    ("40141020", "Consumable & Disposable", "Rubber contraceptives, female (diaphragms), such as cervical caps"),
    ("40149010", "Consumable & Disposable", "Hot water bottles"),
    ("40149020", "Consumable & Disposable", "Ice bag"),
    ("40151200", "Consumable & Disposable", "Gloves, Mittens, Mitts - Of a kind used for medical, surgical, dental or veterinary purposes"),
    ("62101010", "Consumable & Disposable", "Personal protective garments for surgical/medical use (felt or non-woven) conforming to IS 17423"),
    ("62101020", "Consumable & Disposable", "Surgical gowns and drapes conforming to IS 17334"),
    ("62104060", "Consumable & Disposable", "Personal protective garments for surgical/medical use (felt or non-woven) conforming to IS 17423"),
    ("62104070", "Consumable & Disposable", "Surgical gowns and drapes conforming to IS 17334"),
    ("62104090", "Consumable & Disposable", "Other personal protective garments"),
    ("90013000", "Consumable & Disposable", "Contact lenses of any material, unmounted"),
    ("90015000", "Consumable & Disposable", "Spectacle lenses of other materials"),
    ("90183100", "Consumable & Disposable", "Syringes, with or without needles"),
    ("90183210", "Consumable & Disposable", "Needles for suture"),
    ("90183220", "Consumable & Disposable", "Hollow needles for injection, aspiration biopsy and transfusion"),
    ("90183230", "Consumable & Disposable", "Hilerio Venus Fistula Needles"),
    ("90183290", "Consumable & Disposable", "Other"),
    ("90183910", "Consumable & Disposable", "Catheters (for Urine, Stool)"),
    ("90183930", "Consumable & Disposable", "Cannulae"),
    ("90183990", "Consumable & Disposable", "Others"),
    ("90189012", "Consumable & Disposable", "Stethoscopes"),
    ("90189032", "Consumable & Disposable", "Blood transfusion apparatus"),
    ("90189043", "Consumable & Disposable", "Acupuncture Apparatus"),
    ("90200000", "Consumable & Disposable", "Other breathing appliances and gas masks excluding protective masks having neither mechanical parts nor replaceable filters"),
    ("90219010", "Consumable & Disposable", "Parts and accessories of hearing aids"),
    ("96190010", "Consumable & Disposable", "Sanitary towels (pads) or sanitary napkins"),
    ("96190020", "Consumable & Disposable", "Tampons"),
    ("96190030", "Consumable & Disposable", "Napkins and napkin liners for babies"),
    ("96190040", "Consumable & Disposable", "Clinical diapers"),
    ("96190090", "Consumable & Disposable", "Other articles of heading 961900"),
    ("84231000", "Electronic Equipment", "Personal weighing machines, including baby scales household scales"),
    ("90181100", "Electronic Equipment", "Electro-cardiographs"),
    ("90181210", "Electronic Equipment", "Linear ultrasound scanner"),
    ("90181290", "Electronic Equipment", "other"),
    ("90181300", "Electronic Equipment", "Magnetic resonance imaging apparatus"),
    ("90181400", "Electronic Equipment", "Scientigraphic apparatus"),
    ("90181910", "Electronic Equipment", "Electro encephalographs"),
    ("90181920", "Electronic Equipment", "Echo cardiograph"),
    ("90181990", "Electronic Equipment", "Others"),
    ("90182000", "Electronic Equipment", "Ultra-Violet or infra-red ray apparatus"),
    ("90184900", "Electronic Equipment", "Other"),
    ("90185010", "Electronic Equipment", "Ophthalmoscopes"),
    ("90185020", "Electronic Equipment", "Tonometers"),
    ("90185030", "Electronic Equipment", "Ophthalmic lasers"),
    ("90185090", "Electronic Equipment", "other"),
    ("90189011", "Electronic Equipment", "Instrument and apparatus for measuring blood pressure"),
    ("90189019", "Electronic Equipment", "other"),
    ("90189031", "Electronic Equipment", "Artificial kidney (dialysis) apparatus"),
    ("90189041", "Electronic Equipment", "Anesthetic apparatus and instruments"),
    ("90189044", "Electronic Equipment", "Endoscopes"),
    ("90189092", "Electronic Equipment", "Baby incubators"),
    ("90189093", "Electronic Equipment", "Heart-Lung Machines"),
    ("90189094", "Electronic Equipment", "Defibrillators"),
    ("90189095", "Electronic Equipment", "Fibrescopes"),
    ("90189096", "Electronic Equipment", "Laproscopes"),
    ("90189097", "Electronic Equipment", "Vetrasonic lithotripsy instruments"),
    ("90189098", "Electronic Equipment", "Apparatus for nerve stimulation"),
    ("90189099", "Electronic Equipment", "Other"),
    ("90191010", "Electronic Equipment", "Mechano-therapy appliances"),
    ("90191020", "Electronic Equipment", "Massage Apparatus"),
    ("90191090", "Electronic Equipment", "Other"),
    ("90192010", "Electronic Equipment", "Oxygen therapy apparatus"),
    ("90192090", "Electronic Equipment", "Other"),
    ("90211000", "Electronic Equipment", "Orthopaedic or fracture appliances"),
    ("90214010", "Electronic Equipment", "Frequency modulated hearing aid system used for hearing by handicapped persons in group situation"),
    ("90214090", "Electronic Equipment", "Others"),
    ("90215000", "Electronic Equipment", "Pacemakers for stimulating heart muscles, excluding parts and accessories"),
    ("90219090", "Electronic Equipment", "Other"),
    ("90221200", "Electronic Equipment", "Computed tomography apparatus"),
    ("90221300", "Electronic Equipment", "Other for dental uses"),
    ("90221410", "Electronic Equipment", "X-ray generators and apparatus (non-portable)"),
    ("90221420", "Electronic Equipment", "Portable X-ray machine"),
    ("90221490", "Electronic Equipment", "Other"),
    ("90221900", "Electronic Equipment", "For other uses"),
    ("90222100", "Electronic Equipment", "Apparatus based on the use of alpha, beta or gamma or other ionising radiations, whether or not for medical, surgical, dental or veterinary uses, including radiography or radiotherapy apparatus: for medical, surgical, dental or veterinary uses"),
    ("90222900", "Electronic Equipment", "Apparatus based on the use of alpha, beta or gamma or other ionising radiations, whether or not for medical, surgical, dental or veterinary uses, including radiography or radiotherapy: for other uses"),
    ("90223000", "Electronic Equipment", "X-ray tubes"),
    ("90229010", "Electronic Equipment", "X-ray valves"),
    ("90229020", "Electronic Equipment", "Radiation generation units"),
    ("90229030", "Electronic Equipment", "Radiation beam delivery units"),
    ("90229040", "Electronic Equipment", "X-ray examination or treatment table, chairs and the like"),
    ("90229090", "Electronic Equipment", "other"),
    ("90251110", "Electronic Equipment", "Clinical thermometers"),
    ("90251190", "Electronic Equipment", "other"),
    ("90251910", "Electronic Equipment", "Digital thermometers"),
    ("90251920", "Electronic Equipment", "Pyrometers"),
    ("90271000", "Electronic Equipment", "Gas or smoke analysis apparatus"),
    ("90272000", "Electronic Equipment", "Chromatographs and electrophoresis instruments"),
    ("90273010", "Electronic Equipment", "Spectrometers"),
    ("90273020", "Electronic Equipment", "Spectrophotometers"),
    ("90273090", "Electronic Equipment", "other"),
    ("90275010", "Electronic Equipment", "Photometers"),
    ("90275020", "Electronic Equipment", "Refractometers"),
    ("90275030", "Electronic Equipment", "Polarimeters"),
    ("90275090", "Electronic Equipment", "Other"),
    ("90278100", "Electronic Equipment", "Mass spectrometers"),
    ("90278910", "Electronic Equipment", "Viscometers"),
    ("90278920", "Electronic Equipment", "Calorimeters"),
    ("90278930", "Electronic Equipment", "Instruments and apparatus for measuring the surface or interfacial tension of liquids"),
    ("90278990", "Electronic Equipment", "other"),
    ("90279010", "Electronic Equipment", "Microtomes, including parts and accessories thereof"),
    ("90279020", "Electronic Equipment", "Printed circuit assemblies for the goods of sub-heading 902780"),
    ("90279090", "Electronic Equipment", "Others parts and accessories of heading 9027"),
    ("94021010", "Electronic Equipment", "Dentists' chairs and parts thereof"),
    ("94029010", "Electronic Equipment", "Hospital beds with mechanical fittings"),
    ("94029020", "Electronic Equipment", "Parts"),
    ("94029090", "Electronic Equipment", "Other"),
    ("30064000", "Implant", "Dental cements and other dental fillings, bone reconstruction cements"),
    ("90183920", "Implant", "Cardiac Catheters"),
    ("90189091", "Implant", "Hilerial and Venous Shunt"),
    ("90212100", "Implant", "Artificial Teeth"),
    ("90212900", "Implant", "Other"),
    ("90213100", "Implant", "Artificial Joints"),
    ("90213900", "Implant", "Other"),
    ("38221100", "IVD Reagents", "Malaria Diagnostic Test Kits"),
    ("38221200", "IVD Reagents", "For Zika and other diseases transmitted by mosquitoes of the genus Aedes"),
    ("38221300", "IVD Reagents", "For blood-grouping"),
    ("38221910", "IVD Reagents", "Pregnancy test kit"),
    ("38221990", "IVD Reagents", "other"),
    ("38229010", "IVD Reagents", "Certified reference materials"),
    ("38229090", "IVD Reagents", "other"),
    ("90184100", "Surgical Instrument", "Dental drill engines, whether or not combined on a single base with other dental equipment"),
    ("90189021", "Surgical Instrument", "Surgical Bone Saws, Drills, Trephines and Burrs"),
    ("90189022", "Surgical Instrument", "Surgical Knives, Scissors and Blades"),
    ("90189023", "Surgical Instrument", "Forceps, forcep clamps, clips, needle holders, introducers, cephalotribe bone holding and other holding instruments"),
    ("90189024", "Surgical Instrument", "Chisel, gauges, elevators, raspatories, osteotomes, craniotomes, bone cutters"),
    ("90189025", "Surgical Instrument", "Retractors, spatula probes, hooks, dilators, sounds, mallets"),
    ("90189029", "Surgical Instrument", "Other"),
    ("90189042", "Surgical Instrument", "ENT Precision Instruments"),
]


def main():
    assert len(ROWS) == 151, f"expected 151 rows, got {len(ROWS)}"
    assert len(set(r[0] for r in ROWS)) == 151, "duplicate hs8 code found"

    out_rows = [{"hs8": hs8, "description": desc, "hs6": hs8[:6], "category": cat}
                for hs8, cat, desc in ROWS]

    with open(DATA_DIR / "epcmd_151_codes.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hs8", "description", "hs6", "category"])
        w.writeheader()
        w.writerows(out_rows)

    unique_hs6 = sorted(set(r["hs6"] for r in out_rows))
    print(f"Wrote data/epcmd_151_codes.csv: {len(out_rows)} hs8 rows, "
          f"{len(unique_hs6)} unique hs6 groups")
    print("\nUnique hs6 groups (count of hs8 lines each):")
    from collections import Counter
    counts = Counter(r["hs6"] for r in out_rows)
    for hs6 in unique_hs6:
        print(f"  {hs6}: {counts[hs6]} line(s)")


if __name__ == "__main__":
    main()
