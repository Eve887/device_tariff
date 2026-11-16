"""
g3_build_excel.py

Phase 3, Part 4: export data/phase3_tariff_gap_data.csv to
data/phase3_tariff_gap.xlsx - plain typed values only (no formulas, no
merged cells, nothing locked/protected), plus a README sheet explaining
every column in simple words.

READ-ONLY against data/phase3_tariff_gap_data.csv. Writes
data/phase3_tariff_gap.xlsx (new file) only.
"""

import csv
from pathlib import Path
from openpyxl import Workbook

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

README_ROWS = [
    ("Column", "What it means, in simple words"),
    ("code", "The HS6 (6-digit) or HS10 (10-digit) tariff code for this product."),
    ("level", "Whether 'code' is a 6-digit (HS6) or 10-digit (HS10) code."),
    ("description", "Plain-English product description."),
    ("group", "Which of the 14 product groups this code belongs to (Consumables, Imaging, etc.)."),
    ("us_mfn_rate_str", "The US's normal ('Most Favoured Nation') duty rate for this code, exactly as published on hts.usitc.gov. If it says 'varies', the code covers several 10-digit lines with different rates, listed separated by semicolons."),
    ("us_mfn_pct", "The same MFN rate as a single number, for calculations. If the rate 'varies', this is the HIGHEST of the rates found (a worst-case choice - see the raw string column for the full picture)."),
    ("india_forced_labor_addon_pct", "The flat 10% extra duty applied to India under the forced-labor tariff action (fixed value, not looked up)."),
    ("india_listed_rate_pct", "India's total listed tariff rate = US MFN rate + the 10% forced-labor add-on."),
    ("china_section301_list", "Which of the original 2018-2019 Section 301 tariff lists (List 1, 2, 3, or 4A) this code falls under for China, if any. 'none' = not covered by any list. 'MIXED' or 'UNKNOWN' = could not confidently assign one answer - see the note column."),
    ("china_section301_note", "Extra detail/caveat about the Section 301 classification for this code."),
    ("china_section301_rate_pct", "The extra duty rate that List adds (25% for Lists 1-3, 7.5% for List 4A, 100% for the separate 2024 'Four-Year Review' action on some codes). Blank if the list is MIXED/UNKNOWN."),
    ("china_forced_labor_addon_pct", "The flat 12.5% extra duty applied to China under the forced-labor tariff action (fixed value)."),
    ("china_listed_rate_pct", "China's total listed tariff rate = US MFN rate + Section 301 rate + the 12.5% forced-labor add-on. Blank if the Section 301 rate could not be determined."),
    ("mexico_note", "Mexico's rule: the normal MFN rate applies, PLUS a 10% add-on only for goods that do NOT qualify for USMCA (the US-Mexico-Canada trade agreement) preference."),
    ("mexico_usmca_share_note", "Whether we could tell what share of Mexico's exports to the US qualify for USMCA treatment. We could not - the Census data used in this project does not include an FTA-qualification field."),
    ("eu_ceiling_pct", "The flat rule used for the EU/Germany: a combined tariff ceiling of 15%, no matter what the normal rate would otherwise add up to."),
    ("india_duty_paid_pct_2025", "The ACTUAL duty collected on India's 2025 shipments, as a percent of their value - calculated by the US government from real import records (not a listed/legal rate, but what was really paid on average)."),
    ("india_duty_paid_pct_2026ytd", "Same as above, but for January-September 2026 only (the latest period available)."),
    ("china_duty_paid_pct_2025", "Actual duty paid on China's 2025 shipments, as a percent of value."),
    ("mexico_duty_paid_pct_2025", "Actual duty paid on Mexico's 2025 shipments, as a percent of value."),
    ("germany_duty_paid_pct_2025", "Actual duty paid on Germany's 2025 shipments, as a percent of value."),
    ("all_countries_duty_paid_pct_2025", "Actual duty paid on ALL countries' 2025 shipments combined, as a percent of value."),
    ("top3_suppliers_2025", "The three countries that sold the US the most of this product in 2025, with each one's share of the US market."),
    ("top3_non_india_weighted_listed_rate_pct", "The average listed tariff rate of those top 3 suppliers (excluding India if India was one of them), weighted by how much each one sold - used to compare against India's rate."),
    ("india_tariff_gap_pct", "India's listed rate MINUS that weighted average rate. A NEGATIVE number means India's goods face a LOWER tariff than its main competitors (an advantage for India); a positive number means India faces a HIGHER tariff (a disadvantage)."),
    ("us_imports_from_india_2025_usd", "How much the US imported of this product from India in 2025, in US dollars."),
    ("us_imports_from_india_2026ytd_usd", "Same, for January-September 2026 only."),
    ("india_share_of_us_market_2025_pct", "India's share of total US imports of this product in 2025, as a percent."),
    ("", ""),
    ("General notes", ""),
    ("Sourcing", "US MFN rates were fetched directly from the official US International Trade Commission tariff database (hts.usitc.gov) in this session. China's Section 301 list assignments came from a secondary, non-government research source (a third-party tariff-lookup website), because the official USTR exclusion documents could not be read as plain text and the official HTS database does not include this information directly - treat those specific entries as a starting point, not as fully government-confirmed facts."),
    ("Nov 9 2026 exclusion check", "We confirmed directly from the US Federal Register that on 10 November 2026, the US government extended ALL of its roughly 178 active Section 301 tariff exclusions through 9 January 2027. That official notice does not say which specific medical-device codes are among those 178, so we could not confirm, code by code, which of our products currently have an active exclusion."),
    ("Blank cells", "A blank cell means the rate or classification could not be reliably found or confirmed - it was deliberately left blank instead of being guessed. See the project's step-by-step log (logs/step1_progress_log.md) for exactly what was tried for each one."),
]


def main():
    with open(DATA_DIR / "phase3_tariff_gap_data.csv", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        data_rows = list(reader)

    wb = Workbook()

    ws_readme = wb.active
    ws_readme.title = "README"
    for row in README_ROWS:
        ws_readme.append(row)
    ws_readme.column_dimensions["A"].width = 38
    ws_readme.column_dimensions["B"].width = 110

    ws_data = wb.create_sheet("Tariff Gap Data")
    ws_data.append(header)
    for row in data_rows:
        typed_row = []
        for cell in row:
            if cell == "":
                typed_row.append(None)
            else:
                try:
                    typed_row.append(int(cell))
                except ValueError:
                    try:
                        typed_row.append(float(cell))
                    except ValueError:
                        typed_row.append(cell)
        ws_data.append(typed_row)
    for i, col_name in enumerate(header, start=1):
        ws_data.column_dimensions[ws_data.cell(row=1, column=i).column_letter].width = max(14, min(40, len(col_name) + 2))

    # Plain values only: no formulas were ever written, no cells merged,
    # and openpyxl leaves sheet/workbook protection off by default - so
    # there is nothing to strip here, but confirm explicitly.
    assert not ws_data.protection.sheet, "sheet should not be protected"
    assert not ws_readme.protection.sheet, "sheet should not be protected"

    out_path = DATA_DIR / "phase3_tariff_gap.xlsx"
    wb.save(out_path)
    print(f"Wrote {out_path} ({len(data_rows)} data rows, 2 sheets: README, Tariff Gap Data)")


if __name__ == "__main__":
    main()
