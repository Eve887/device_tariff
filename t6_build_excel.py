"""
t6_build_excel.py

View B, Part 6: export everything to data/view_b_india_imports.xlsx -
plain typed values only (no formulas, no merged cells, nothing
locked), with a README sheet. Same typed_row()/assert pattern as
every prior workbook in this project.

Sheets: README, Duty_rates, Landed_cost, Trade_flows, Trade_deal,
Scenarios, Totals.

READ-ONLY against the View B CSVs already produced. Writes
data/view_b_india_imports.xlsx (new file) only.
"""

import csv
from pathlib import Path
from openpyxl import Workbook

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

README_ROWS = [
    ("Sheet", "What it contains, in simple words"),
    ("Duty_rates", "India's import duty structure on each of our 60 core medical-device codes, as it stands today: Basic Customs Duty (BCD), Social Welfare Surcharge (SWS, normally 10% of the BCD), Health Cess (5%, but ONLY on tariff headings 9018-9022 - confirmed from the actual Finance Act 2020 text, not just 'medical devices' generally), and IGST (mostly cut to 5% since the 22 Sept 2025 GST reform, with some confirmed exceptions still at 18% or cut all the way to 0%). Every rate has its own source. Where a rate says 'not found', it genuinely could not be confirmed in this research pass - it is not a guess and not a zero."),
    ("Landed_cost", "For every code, what it actually costs to bring a $100-CIF-value US device into India today: the BCD, SWS, health cess and IGST amounts, the combined 'customs duty %' (BCD+SWS+cess only), and the 'total tax %' (everything including IGST). IGST is counted as a real cost here, not netted off - see the caveat below. 'Not computable' means one or more of the underlying rates was 'not found' in Duty_rates - never a silent zero."),
    ("Trade_flows", "India's actual imports of each code from the World, USA, China, Germany and Japan, 2022-2025 (India-reported, CIF values), plus the US's share of each code's total. Shows which codes India depends on US suppliers for, and how that's changed over time."),
    ("Trade_deal", "What the official India-US interim trade framework (Joint Statement, 7 Feb 2026) actually says about medical devices - in plain words, with short quotes and exactly where each clause sits in the document. Also notes, as a real finding: several points reported in the media (a phased tariff schedule, minimum-import-price safeguards) do NOT appear anywhere in the official text checked here."),
    ("Scenarios", "Four 'what if' scenarios for US-origin devices ONLY (every other country's duties stay the same): B0 is today; B1 cuts BCD to 0% on US devices; B2 removes the health cess on US devices; B3 does both together. For each code and scenario: how much cheaper the device becomes for an Indian hospital buying it (price fall %), how much MORE the US might sell to India as a result (using an ASSUMED, not measured, elasticity of 0.5/1.0/1.5 - low/base/high), how much customs revenue India would give up on today's import volume alone (ignoring the extra sales), and China/Germany/Japan's import values for the same code as context on who else supplies it."),
    ("Totals", "The Scenarios sheet added up by product group and overall, for quick reading."),
    ("", ""),
    ("IMPORTANT CAVEAT 1 - IGST is kept as a real cost, not credited back", "Most Indian hospitals' SERVICES are exempt from GST output tax, which under GST's normal input-tax-credit mechanism means they usually CANNOT claim back the IGST they pay on imported devices - unlike a fully GST-registered, taxable business (e.g. a distributor reselling to a taxable buyer), which generally can. This file treats IGST as a real, non-recoverable cost throughout, which is the correct lens for a hospital buyer, but would overstate the true cost for a different kind of importer."),
    ("IMPORTANT CAVEAT 2 - the elasticity in Scenarios is ASSUMED, not measured", "0.5 / 1.0 / 1.5 (low/base/high) was specified by the user as a reasonable assumed range for how much extra buying a given price fall produces - it is NOT estimated from this project's own trade data the way Phase 4's epsilon/alpha were. Every number downstream of it (every 'extra US sales' figure) inherits this assumption and should be read as illustrative, not a forecast."),
    ("IMPORTANT CAVEAT 3 - BCD has a genuine, unresolved source conflict", "One set of sources (a May 2026 legal-firm FAQ) says most medical devices attract 0% BCD via long-standing exemption notifications. A different set of sources (per-code aggregator sites, checked individually for several specific lines) consistently shows 7.5% BCD. This file uses the 7.5%-type figures where individually found, because the user's own B1 scenario ('BCD cut to 0%') only makes sense as a real change if BCD is currently non-zero - but this is a judgement call on a genuine conflict, not a settled fact, and is flagged throughout rather than silently picked. See logs/step1_progress_log.md for the full research trail."),
    ("IMPORTANT CAVEAT 4 - scope limits on 'every 8-digit line'", "The user asked for every Indian 8-digit tariff line under each HS6 code. Given ~60 HS6 codes (potentially 150-250+ actual 8-digit lines), this file reports rates at the SAME granularity core_device_codes.csv already tracks (60 codes, 3 of them already at 8/10-digit level) rather than exhaustively enumerating every possible 8-digit child of every HS6 - a scoping decision made explicit in the log, not a silent shortcut. Full 8-digit detail was specifically sought for the highest-value codes."),
    ("Methodology notes", "Every figure in Duty_rates, Landed_cost, Trade_flows and Trade_deal carries its own source column - check it before relying on any single number. Scenario math in the Scenarios/Totals sheets is laid out in full in t4_scenarios.py's own docstring and logs/step1_progress_log.md if you want to see exactly how each column was derived."),
    ("Blank cells / 'not found' / 'not computable'", "'not found' means a rate could not be confirmed from any source checked. 'not computable' means a downstream calculation could not be done because one or more of its inputs was 'not found'. Neither is ever filled in with a guessed value - see logs/step1_progress_log.md for exactly what was tried for any given code."),
]

SHEETS = [
    ("Duty_rates", "india_duty_rates.csv"),
    ("Landed_cost", "india_landed_cost.csv"),
    ("Trade_flows", "india_imports_by_country.csv"),
    ("Trade_deal", "view_b_trade_deal.csv"),
    ("Scenarios", "view_b_scenarios.csv"),
    ("Totals", "view_b_totals.csv"),
]


def typed_row(row):
    out = []
    for cell in row:
        if cell == "":
            out.append(None)
        elif cell in ("True", "False"):
            out.append(cell == "True")
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
    ws_readme.column_dimensions["A"].width = 44
    ws_readme.column_dimensions["B"].width = 110

    for sheet_name, fname in SHEETS:
        with open(DATA_DIR / fname, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader)
            data_rows = list(reader)
        ws = wb.create_sheet(sheet_name)
        ws.append(header)
        for row in data_rows:
            ws.append(typed_row(row))
        for i, col_name in enumerate(header, start=1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = max(14, min(45, len(col_name) + 2))

    for ws in wb.worksheets:
        assert not ws.protection.sheet, f"{ws.title} should not be protected"
        assert len(ws.merged_cells.ranges) == 0, f"{ws.title} should have no merged cells"
        for row in ws.iter_rows():
            for cell in row:
                assert cell.data_type != "f", f"{ws.title} cell {cell.coordinate} is a formula"

    out_path = DATA_DIR / "view_b_india_imports.xlsx"
    wb.save(out_path)
    print(f"Wrote {out_path}")
    for ws in wb.worksheets:
        print(f"  {ws.title}: {ws.dimensions}")


if __name__ == "__main__":
    main()
