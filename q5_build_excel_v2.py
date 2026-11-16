"""
q5_build_excel_v2.py

Phase 4 fixes, step 5: export everything from the four fixes into
data/phase4_scenarios_v2.xlsx - plain typed values only (no formulas,
no merged cells, nothing locked), with a README sheet explaining every
column in simple words. Mirrors p7_build_excel.py's approach exactly
(same typed_row() conversion, same post-write assert checks), applied
to the new v2 outputs.

READ-ONLY against all the v2 CSVs already produced by q1-q4. Writes
data/phase4_scenarios_v2.xlsx (new file) only.
"""

import csv
from pathlib import Path
from openpyxl import Workbook

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

README_ROWS = [
    ("Sheet", "What it contains, in simple words"),
    ("Tier_Epsilon", "Fix 1: how strongly buyers switch away from India when India's tariff rises, now measured per TIER (not small product group) by adding up dollars across each tier's qualifying codes first, then computing one change for the whole tier - this avoids one small, noisy code from swinging the whole result. Tier A = simple disposables (Consumables, Dressings & Sutures, Gloves). Tier B = equipment (Electro-diagnostic, Imaging, Instruments, Respiratory & Therapy, Ophthalmic, Furniture, Other). Tier C = implants and dental. epsilon_base/low/high come from resampling each tier's codes 1,000 times (with replacement) and taking the median/25th/75th percentile. POOLED is one epsilon across every tier, as a cross-check. NOTE: code 902140 (Hearing aids) has no tier - the three named tiers never included a 'Hearing' group, so this one code is left out of every tier-based number in this workbook rather than guessed into one."),
    ("Out_of_Sample", "Fix 2: a genuine test of Tier_Epsilon's numbers on data they were NOT fit to - predicting India's Apr-Sep 2026 vs Apr-Sep 2024 change using each tier's own epsilon_base and that period's own tariff-gap change. 'predicted' vs 'actual' vs naive (naive always guesses 0% change). Tiers A and B beat the naive guess; Tier C does not (reported honestly - Tier C's epsilon was always the least certain of the three, built from only 3 qualifying codes). 'persistent_loss_usd' is filled in only when the real outcome was worse than predicted - a rough dollar estimate of buyers who switched away and had not come back by the end of the test window."),
    ("Alpha_HS10_lines", "Fix 3: an attempt to measure alpha (how much of a tariff increase shows up in price vs. just fewer units sold) using actual quantities, at the detailed 10-digit US product-code level, for the 10 biggest India product codes. Each row is one 10-digit line that had a usable, matching quantity unit in both the baseline and shock periods AND at least $1M of India trade."),
    ("Alpha_HS10_summary", "The headline number from Alpha_HS10_lines: 17 lines were usable (8 or more, so per the agreed rule the measured value is used instead of the fallback). IMPORTANT CAVEAT: this measured alpha is NOT stable - the 17 lines range from -89 to +3.2 and cross both positive and negative, so the 'low' value is actually negative (-1.292), which does not make economic sense on its own (it would mean prices move the opposite way from the tariff). This is flagged, not hidden - see the Methodology_notes row below and the log for the full reasoning. If you want a more conservative, stable alternative, the old fallback (0.3 low / 0.45 base / 0.6 high) is still valid and is described here for reference."),
    ("Scenarios_by_code", "Unchanged from the first Phase 4 workbook: for every code and every what-if scenario (S0 Today, S1 China's exclusions expiring, S2/S3/S4 different Section 232 tariff levels, S5 an India-US deal), shows delta_t (how much India's own tariff would change) and delta_g (how much the gap between India and its competitors would change), both in percentage points."),
    ("Revenue_at_Risk_v2", "Fix 4: the dollar revenue-at-risk for every code and scenario, now using each code's TIER epsilon (from Tier_Epsilon) and the new alpha (from Alpha_HS10_summary) instead of the old per-group epsilon and fallback alpha. low/base/high pair the low/base/high alpha with the low/base/high epsilon for that code's tier."),
    ("Totals_v2", "The dollar bottom line for each scenario, added up across all codes: how much of India's US medical-device sales are 'at risk', low/base/high, in dollars and as a percent, shown twice (2025 full year, and the latest 12 months Oct 2025-Sep 2026)."),
    ("Monotonicity_Check", "A sanity check the user asked for: does low always fall at or below base, which always falls at or below high? YES for every scenario except S5 (the India-US deal scenario) - there, because the new alpha's 'low' value is negative, the 'low' case actually shows a GAIN while base and high both show a LOSS, which flips direction and fails the check. This is a direct, traceable result of Alpha_HS10_summary's own flagged instability, not a new error - treat S5's 'low' number with real caution; base and high still point the same way as each other."),
    ("Exposure_score_v2", "Every core code with at least $1M of India trade in 2025 (30 of the 60), ranked 0-100 by how exposed it is overall - same five weighted factors as before (US dependence, tariff level, competitor gap, ease of switching, Section 232 policy risk), but 'ease of switching' now uses the code's new TIER epsilon instead of the old product-group epsilon. Two new columns: E_2025_full_year_musd (India's 2025 trade in that code, in $ millions) and base_S2_rar_musd (the base-case dollar amount at risk under scenario S2, in $ millions) - useful for sorting by dollar impact instead of by the 0-100 score."),
    ("", ""),
    ("IMPORTANT CAVEAT 1 - Fix 3's measured alpha is not stable", "17 of 42 ten-digit lines were usable (>= 8, so the rule says use the measured value), but the 17 alphas range from -89 to +3.2 and include both positive and negative numbers. The headline low/base/high (-1.292 / 0.063 / 0.908) is reported because that is what the stated rule produces, but it should not be read as a confident number - see Alpha_HS10_summary above and the log for full detail, including the one line (9018390020) whose tariff barely moved (0.05 points) and therefore produced an extreme, unstable alpha on its own."),
    ("IMPORTANT CAVEAT 2 - S5's 'low' scenario total flips direction", "Because Fix 3's alpha_low is negative, multiplying it by S5's negative delta_t (India's OWN tariff going down 10 points) flips the sign of that term. The result: S5's 'low' total shows a small GAIN while 'base' and 'high' both show a LOSS of several million dollars. Every other scenario (where delta_t is zero or positive) is unaffected and passes the low<=base<=high check normally - this is specific to S5. Full detail in logs/step1_progress_log.md."),
    ("IMPORTANT CAVEAT 3 - one code has no tier", "Code 902140 (Hearing aids) belongs to a group called 'Hearing', which was never included in any of the three named tiers (A/B/C) in the original fix request. It is therefore left out of Tier_Epsilon, Revenue_at_Risk_v2, Totals_v2, and Exposure_score_v2's tier-dependent figures - not guessed into a tier. It was already excluded the same way back in Fix 1."),
    ("Methodology notes", "Competitor comparisons throughout this phase use ACTUAL duty paid (Census calculated duty), not listed/legal tariff rates, per instruction. Epsilon is now computed by adding up dollars across a tier's qualifying codes BEFORE taking any percentage change (Fix 1), which is more stable than the original per-code approach used in the first Phase 4 workbook (phase4_scenarios.xlsx) - that workbook's Implants-group blow-up (code 902190) does not recur here."),
    ("Blank cells", "Could not be reliably computed or found - deliberately left blank rather than guessed. See logs/step1_progress_log.md for what was tried."),
]

SHEETS = [
    ("Tier_Epsilon", "phase4_tier_epsilon_v2.csv"),
    ("Out_of_Sample", "phase4_out_of_sample_v2.csv"),
    ("Alpha_HS10_lines", "phase4_alpha_hs10_v2.csv"),
    ("Alpha_HS10_summary", "phase4_alpha_hs10_summary_v2.csv"),
    ("Scenarios_by_code", "phase4_scenarios.csv"),
    ("Revenue_at_Risk_v2", "phase4_revenue_at_risk_v2.csv"),
    ("Totals_v2", "phase4_revenue_at_risk_totals_v2.csv"),
    ("Monotonicity_Check", "phase4_monotonicity_check_v2.csv"),
    ("Exposure_score_v2", "phase4_exposure_score_v2.csv"),
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
        for row in ws.iter_rows():
            for cell in row:
                assert cell.data_type != "f", f"{ws.title} cell {cell.coordinate} is a formula"

    out_path = DATA_DIR / "phase4_scenarios_v2.xlsx"
    wb.save(out_path)
    print(f"Wrote {out_path}")
    for ws in wb.worksheets:
        print(f"  {ws.title}: {ws.dimensions}")


if __name__ == "__main__":
    main()
