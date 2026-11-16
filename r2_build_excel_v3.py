"""
r2_build_excel_v3.py

Final Phase 4 run, step 6: export everything into
data/phase4_scenarios_v3.xlsx - plain typed values only (no formulas,
no merged cells, nothing locked), with a README sheet. Same
typed_row()/assert pattern as every prior Phase 4 workbook.

READ-ONLY against the v3 CSVs (plus the v2 measured-alpha CSVs, kept
as their own "unstable, not used" sheets). Writes
data/phase4_scenarios_v3.xlsx (new file) only.
"""

import csv
from pathlib import Path
from openpyxl import Workbook

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

README_ROWS = [
    ("Sheet", "What it contains, in simple words"),
    ("Tier_Epsilon_v3", "How strongly buyers switch away from India when India's tariff rises, per tier. Tier A and Tier B keep the exact same bootstrapped numbers as the previous workbook (not recomputed). Tier C's epsilon is now the POOLED value (measured across all three tiers together) instead of Tier C's own narrow estimate - the user's decision, because Tier C's own estimate was built from only 3 qualifying codes and did not hold up in the out-of-sample test. Code 902140 (Hearing aids) is now a member of Tier B (it had no tier at all before) - this is a membership assignment only; it does not change Tier B's epsilon number."),
    ("Alpha_fallback_used", "The alpha (price pass-through) actually used in every dollar figure in this workbook: a fixed 0.3 (low) / 0.45 (base) / 0.6 (high) for every code, per the user's decision. This replaces the data-measured alpha from the previous workbook, which was judged too unstable to use directly (see the next sheet)."),
    ("Alpha_measured_unstable", "The alpha actually measured from 10-digit US quantity data (17 usable lines): low=-1.292, base=0.063, high=0.908. Kept here as a reported finding, NOT used anywhere in this workbook's totals or exposure score - the range crosses zero and includes an implausible negative value, so it was judged unreliable. See logs/step1_progress_log.md for full detail on why."),
    ("Revenue_at_Risk_v3", "The dollar revenue-at-risk for every code and scenario, using Tier_Epsilon_v3 and the fallback alpha. low/base/high pair the low/base/high alpha with the low/base/high epsilon for that code's tier."),
    ("Totals_v3", "The dollar bottom line for each scenario, added up across all codes: how much of India's US medical-device sales are 'at risk', low/base/high, in dollars and as a percent, shown twice (2025 full year, and the latest 12 months Oct 2025-Sep 2026). SANITY CHECK PASSED: low <= base <= high holds for every loss scenario (S0-S4), and S5 (the India-US deal scenario) shows a GAIN in all three of low/base/high - using the fallback alpha removed the sign-flip problem the previous workbook had."),
    ("Persistent_Loss_v3", "A check on whether the tier-epsilon model explains the REAL change in India's trade from Apr-Sep 2024 to Apr-Sep 2026 (a period the model was not fit to). For each tier: the actual % change, what the model predicted using its epsilon, and the gap between them in $ millions. Tiers A and B show a real, substantial gap (the model under-predicted how much trade was actually lost) - read as evidence that some of the loss is NOT explained by tariff gaps alone. Tier C's gap is small and slightly favorable (actual beat predicted). Explanation: the extra, unexplained fall is consistent with US buyers who switched away during the 50% tariff period (Oct 2025-Feb 2026) not coming back afterward - a 'sticky' loss of customers that a tariff-gap-only model cannot capture. Because the scenario Totals above do NOT include this effect, they should be read as a LOWER BOUND on the real risk, not the full picture."),
    ("Exposure_score_v3", "Every core code with at least $1M of India trade in 2025 (30 of 60, now including 902140/Hearing aids for the first time), ranked 0-100 by how exposed it is overall - US dependence (30%), tariff level (20%), competitor gap (20%), ease of switching using Tier_Epsilon_v3 (15%), Section 232 policy risk (15%). Two extra columns: E_2025_full_year_musd (India's 2025 trade in $ millions) and base_S2_rar_musd (base-case dollars at risk under scenario S2, in $ millions) for sorting by dollar impact instead of score."),
    ("", ""),
    ("Methodology notes", "This is the third and final Phase 4 workbook. Changes from the second workbook (phase4_scenarios_v2.xlsx): (1) alpha switched from the unstable measured value to the fixed fallback 0.3/0.45/0.6; (2) Tier C's epsilon switched from its own narrow estimate to the pooled estimate; (3) code 902140 (Hearing aids) now has a tier (Tier B) and appears in every table for the first time; (4) a new Persistent_Loss_v3 sheet quantifies the part of the real-world trade fall that the tariff-gap model does not explain. Competitor comparisons throughout still use ACTUAL duty paid (Census calculated duty), not listed/legal tariff rates, per the standing instruction for this whole phase."),
    ("Blank cells", "Could not be reliably computed or found - deliberately left blank rather than guessed. See logs/step1_progress_log.md for what was tried."),
]

SHEETS = [
    ("Tier_Epsilon_v3", "phase4_tier_epsilon_v3.csv"),
    ("Alpha_fallback_used", None),  # built inline below
    ("Alpha_measured_unstable", "phase4_alpha_hs10_summary_v2.csv"),
    ("Revenue_at_Risk_v3", "phase4_revenue_at_risk_v3.csv"),
    ("Totals_v3", "phase4_revenue_at_risk_totals_v3.csv"),
    ("Persistent_Loss_v3", "phase4_persistent_loss_v3.csv"),
    ("Exposure_score_v3", "phase4_exposure_score_v3.csv"),
]

ALPHA_FALLBACK_ROWS = [
    ("tier", "alpha", "basis"),
    ("low", "0.3", "fallback value specified by the user, used for every code"),
    ("base", "0.45", "fallback value specified by the user, used for every code"),
    ("high", "0.6", "fallback value specified by the user, used for every code"),
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
        ws = wb.create_sheet(sheet_name)
        if fname is None:
            for row in ALPHA_FALLBACK_ROWS:
                ws.append(typed_row(row) if row != ALPHA_FALLBACK_ROWS[0] else list(row))
            header = list(ALPHA_FALLBACK_ROWS[0])
        else:
            with open(DATA_DIR / fname, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
                data_rows = list(reader)
            ws.append(header)
            for row in data_rows:
                ws.append(typed_row(row))
        for i, col_name in enumerate(header, start=1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = max(14, min(40, len(col_name) + 2))

    for ws in wb.worksheets:
        assert not ws.protection.sheet, f"{ws.title} should not be protected"
        assert len(ws.merged_cells.ranges) == 0, f"{ws.title} should have no merged cells"
        for row in ws.iter_rows():
            for cell in row:
                assert cell.data_type != "f", f"{ws.title} cell {cell.coordinate} is a formula"

    out_path = DATA_DIR / "phase4_scenarios_v3.xlsx"
    wb.save(out_path)
    print(f"Wrote {out_path}")
    for ws in wb.worksheets:
        print(f"  {ws.title}: {ws.dimensions}")


if __name__ == "__main__":
    main()
