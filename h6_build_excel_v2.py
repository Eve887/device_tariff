"""
h6_build_excel_v2.py

Phase 3 fix 5: export the corrected tariff table to
data/phase3_tariff_gap_v2.xlsx - plain typed values only (no formulas,
no merged cells, nothing locked), with a README sheet, the full
corrected data table, and the top-15 competitor check as a third sheet.

READ-ONLY against data/phase3_tariff_gap_data_v3.csv and
data/top15_competitor_check.csv. Writes data/phase3_tariff_gap_v2.xlsx
(new file) only - the original data/phase3_tariff_gap.xlsx from
Phase 3's first pass is untouched.
"""

import csv
from pathlib import Path
from openpyxl import Workbook

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

README_ROWS = [
    ("Column", "What it means, in simple words"),
    ("code / level / description / group", "Same as before: the HS6 or HS10 code, whether it's 6 or 10 digits, its plain description, and which of the 14 product groups it belongs to."),
    ("us_mfn_rate_str / us_mfn_pct", "The US's normal duty rate (hts.usitc.gov), as published text and as a single number (the highest rate found, if it varies across 10-digit lines)."),
    ("india_forced_labor_addon_pct", "India's flat 10% forced-labor add-on - now shown as '0 (exempt)' for the 3 codes found on CBP's official exemption list (see section301_exempt/exemption_source)."),
    ("india_listed_rate_pct", "India's listed rate from the FIRST pass of this table (MFN + 10%, or just MFN if exempt). Superseded by india_listed_rate_pct_corrected below, which uses the fuller, cross-checked tier logic - kept here so you can see what changed."),
    ("china_section301_list / _note / _rate_pct", "China's OLDER (2018-19) Section 301 List 1/2/3/4A assignment, where it could be confidently determined (many codes are MIXED/UNKNOWN - see the note)."),
    ("china_forced_labor_addon_pct / china_listed_rate_pct", "China's NEWER flat 12.5% forced-labor add-on, and the first-pass combined listed rate. Superseded by china_listed_rate_pct_corrected."),
    ("mexico_note / mexico_usmca_share_note", "Mexico's rule (MFN + 10% only for non-USMCA-qualifying goods) and an explicit note that we could not estimate what share of Mexico's trade actually qualifies for USMCA - the Census data used in this project has no FTA-qualification field."),
    ("eu_ceiling_pct", "The flat 15% all-in ceiling rule used for the EU in this exercise, per explicit instruction - see the IMPORTANT NOTE below about how this compares to what EU suppliers actually pay."),
    ("*_duty_paid_pct_2025 / _2026ytd", "ACTUAL duty collected (not a listed/legal rate) as a percent of value, for India, China, Mexico, Germany, and all countries combined - calculated by the US government from real import records."),
    ("top3_suppliers_2025", "The three countries that sold the US the most of this product in 2025, with each one's share of the US market."),
    ("top3_non_india_weighted_listed_rate_pct", "The average FIRST-PASS listed tariff rate of those top 3 suppliers (excluding India), weighted by how much each sold."),
    ("india_tariff_gap_pct", "FIRST-PASS gap: India's first-pass listed rate minus the above. Negative = India faces a lower tariff than its competitors (an advantage)."),
    ("us_imports_from_india_2025_usd / _2026ytd_usd / india_share_of_us_market_2025_pct", "How much the US imported from India, and India's share of the US market, in 2025 and Jan-Sep 2026."),
    ("section301_exempt / exemption_source", "Whether this code is on CBP's official Forced Labor HTS List exemption schedule (headings 9903.05.86 or 9903.05.89) - checked directly against the real PDF, not guessed. 'yes' for exactly 3 codes, all in Chapter 30."),
    ("china_listed_rate_basis", "Plain-English explanation of how china_listed_rate_pct_corrected was built for this specific code (which duty layers were added, and whether the older Section 301 List rate was known)."),
    ("india_listed_rate_pct_corrected", "CORRECTED India listed rate, using the real USTR forced-labor-action tier (Tier 1: MFN + 10%, or 0% addon if exempt)."),
    ("china_listed_rate_pct_corrected", "CORRECTED China listed rate = MFN + the older Section 301 List rate (where known) + the new 12.5% forced-labor add-on (or 0% if exempt). This is the number that was cross-checked against ACTUAL duty paid and found to reconcile well (within 0.5 percentage points) once the older List rate is included - see logs/step1_progress_log.md 'Fix 3' for the specific proof case (902230, X-ray tubes from China)."),
    ("mexico_listed_rate_pct_corrected_usmca_assumed", "CORRECTED Mexico listed rate, ASSUMING the shipment qualifies for USMCA (0%). Real-world duty paid is higher where shipments don't actually qualify - see the top-15 competitor check sheet, where Mexico's actual duty paid is consistently a few points above this assumed 0%."),
    ("eu_listed_rate_pct_corrected", "CORRECTED EU listed rate using the user-instructed flat 15% ceiling. IMPORTANT: cross-checking against actual duty paid (see the competitor check sheet) shows EU suppliers consistently pay only about 9-11% in practice - the real USTR mechanism for the EU under this specific action is a 10%-combined cap, not a flat 15%. The 15% figure may reflect a different, separate tariff framework. Treat this column as the user-requested simplification, not a confirmed real-world rate - flagged explicitly rather than silently corrected."),
    ("gap_listed_pct", "CORRECTED gap: india_listed_rate_pct_corrected minus the first-pass weighted competitor rate."),
    ("gap_actual_pct", "India's ACTUAL 2026-YTD duty paid minus the first-pass weighted competitor rate - a real-world, evidence-based gap, not a listed-rate one."),
    ("", ""),
    ("About the 'Top 15 Competitor Check' sheet", "For India's 15 largest device codes (by 2025 value), shows each of the top 3 non-India suppliers, their listed rate, and what they ACTUALLY paid in duty Jan-Sep 2026. Rows flagged 'yes' differ by more than 3 percentage points, with a likely reason."),
    ("Sourcing", "US MFN rates: hts.usitc.gov directly. CBP exemption list: the official PDF at the govdelivery.com URL given, read in full. USTR tier structure: a law-firm summary (hklaw.com) cross-checked against a second search - USTR's own primary report PDF could not be read (it is image-based and this environment lacks the PDF-rendering tool needed). China's Nov 2026 exclusion extension: confirmed directly from the Federal Register (govinfo.gov, FR Doc 2026-22925) - that notice does NOT name specific device codes; it only references HTS General Notes 20(vvv)/20(www), which we could not retrieve the full text of via the HTS REST API."),
    ("Blank cells", "Could not be reliably found or confirmed - deliberately left blank rather than guessed. See logs/step1_progress_log.md for exactly what was tried."),
]


def typed_row(row):
    out = []
    for cell in row:
        if cell == "":
            out.append(None)
        else:
            try:
                out.append(int(cell))
            except ValueError:
                try:
                    out.append(float(cell))
                except ValueError:
                    out.append(cell)
    return out


def main():
    wb = Workbook()
    ws_readme = wb.active
    ws_readme.title = "README"
    for row in README_ROWS:
        ws_readme.append(row)
    ws_readme.column_dimensions["A"].width = 42
    ws_readme.column_dimensions["B"].width = 110

    with open(DATA_DIR / "phase3_tariff_gap_data_v3.csv", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        data_rows = list(reader)
    ws_data = wb.create_sheet("Tariff Gap Data v2")
    ws_data.append(header)
    for row in data_rows:
        ws_data.append(typed_row(row))
    for i, col_name in enumerate(header, start=1):
        ws_data.column_dimensions[ws_data.cell(row=1, column=i).column_letter].width = max(14, min(40, len(col_name) + 2))

    with open(DATA_DIR / "top15_competitor_check.csv", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header2 = next(reader)
        data_rows2 = list(reader)
    ws_comp = wb.create_sheet("Top 15 Competitor Check")
    ws_comp.append(header2)
    for row in data_rows2:
        ws_comp.append(typed_row(row))
    for i, col_name in enumerate(header2, start=1):
        ws_comp.column_dimensions[ws_comp.cell(row=1, column=i).column_letter].width = max(14, min(40, len(col_name) + 2))

    for ws in (ws_readme, ws_data, ws_comp):
        assert not ws.protection.sheet, "sheet should not be protected"
        assert len(ws.merged_cells.ranges) == 0, "sheet should have no merged cells"

    out_path = DATA_DIR / "phase3_tariff_gap_v2.xlsx"
    wb.save(out_path)
    print(f"Wrote {out_path}")
    print(f"  README: {len(README_ROWS)} rows")
    print(f"  Tariff Gap Data v2: {len(data_rows)} rows")
    print(f"  Top 15 Competitor Check: {len(data_rows2)} rows")


if __name__ == "__main__":
    main()
