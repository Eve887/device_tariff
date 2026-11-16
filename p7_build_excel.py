"""
p7_build_excel.py

Phase 4, Part 7: export everything to data/phase4_scenarios.xlsx -
plain typed values only (no formulas, no merged cells, nothing
locked), with a README sheet plus Elasticity, Alpha, Backtest,
Scenarios_by_code, Totals, Exposure_score.

READ-ONLY against all the Phase 4 CSVs already produced. Writes
data/phase4_scenarios.xlsx (new file) only.
"""

import csv
from pathlib import Path
from openpyxl import Workbook

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

README_ROWS = [
    ("Sheet", "What it contains, in simple words"),
    ("Elasticity", "How strongly buyers switch away from India when India's tariff rises, one row per product group. epsilon: the measured switching strength (higher = buyers switch away more for the same tariff change). p25/p75: the range epsilon could plausibly fall in, given the data. n: how many codes the group's epsilon is based on - groups with fewer than 3 are marked LOW CONFIDENCE. Codes where India sold under $1M in 2025, or where the India-vs-competitor tariff gap barely moved, were left out (listed in the log)."),
    ("Alpha", "Price absorption - how much of a tariff increase gets passed into price (vs. just cutting how much is bought). We could NOT measure this from the data: only 2 of 60 codes had usable quantity figures (Census does not collect a meaningful quantity unit for most of these 6-digit product groups). So this sheet shows the FALLBACK values you specified (0.3 low / 0.45 base / 0.6 high), used flat for every group."),
    ("Backtest", "A reality-check on the elasticity model: for each group, 'predicted' is what the model would have guessed India's trade change should have been (using epsilon and the measured tariff gap change), and 'actual' is what really happened. 'error' is predicted minus actual, in percentage points - smaller is better. Groups with only one code show almost zero error by design (the model is built from that same code), which is an expected sanity check, not evidence the model is perfect elsewhere."),
    ("Scenarios_by_code", "For every code and every what-if scenario (S0 Today, S1 China's exclusions expiring, S2/S3/S4 different Section 232 tariff levels, S5 an India-US deal), shows delta_t (how much India's own tariff would change) and delta_g (how much the gap between India and its competitors would change), both in percentage points. Also shows today's actual starting point: India's real duty paid and the weighted real duty paid by India's top 3 competitors for that code."),
    ("Totals", "The dollar bottom line for each scenario: how much of India's US medical-device sales are 'at risk' (could be lost to price effects and buyers switching to competitors), shown as low/base/high estimates, in dollars and as a percent of the trade being measured. Shown twice: once using 2025's full-year trade as the base, once using the most recent 12 months (Oct 2025-Sep 2026)."),
    ("Exposure_score", "Every core code ranked 0-100 by how exposed it is overall, combining: how dependent India is on the US market for that product (30%), how high a tariff India's goods currently pay (20%), how much worse India's tariff is than its competitors' (20%), how easily buyers could switch away (15%), and whether the product is explicitly named in the pending Section 232 medical-device investigation (15%). Higher score = more exposed."),
    ("", ""),
    ("IMPORTANT CAVEAT - read before trusting low/high scenario numbers", "One code (902190, 'other appliances implanted or worn,' Implants group) had a very small starting trade value, so its measured swing came out as +1057% - mathematically correct, but it alone drags the whole Implants group's low-end (25th percentile) epsilon down to an extreme, implausible value. This mainly affects scenario S2's 'low' total, which should NOT be trusted at face value - use the BASE (median-epsilon) figures as the primary numbers; treat low/high as a rough sensitivity range, not hard bounds. Full detail in logs/step1_progress_log.md."),
    ("Methodology notes", "Competitor comparisons throughout this phase use ACTUAL duty paid (Census calculated duty), not listed/legal tariff rates, per instruction. S1's 'excluded codes only' bump uses a data-driven proxy (codes where China's actual duty sits notably below its listed rate) because no official list of which specific codes currently hold an active China exclusion could be found - see the log for the two primary sources checked. The Section 232 'named' determination in Exposure_score is based on the notice's explicitly named product examples (read directly from the Federal Register), not its broader general definitions, which would have made that factor carry no information."),
    ("Blank cells", "Could not be reliably computed or found - deliberately left blank rather than guessed. See logs/step1_progress_log.md for what was tried."),
]

SHEETS = [
    ("Elasticity", "phase4_elasticity_by_group.csv"),
    ("Alpha", "phase4_alpha.csv"),
    ("Backtest", "phase4_backtest.csv"),
    ("Scenarios_by_code", "phase4_scenarios.csv"),
    ("Totals", "phase4_revenue_at_risk_totals.csv"),
    ("Exposure_score", "phase4_exposure_score.csv"),
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
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = max(14, min(40, len(col_name) + 2))

    for ws in wb.worksheets:
        assert not ws.protection.sheet, f"{ws.title} should not be protected"
        assert len(ws.merged_cells.ranges) == 0, f"{ws.title} should have no merged cells"

    out_path = DATA_DIR / "phase4_scenarios.xlsx"
    wb.save(out_path)
    print(f"Wrote {out_path}")
    for ws in wb.worksheets:
        print(f"  {ws.title}: {ws.dimensions}")


if __name__ == "__main__":
    main()
