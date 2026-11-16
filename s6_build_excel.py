"""
s6_build_excel.py

Phase 5, Part 7: export everything to data/phase5_companies.xlsx -
plain typed values only (no formulas, no merged cells, nothing
locked), with a README sheet. Same typed_row()/assert pattern as every
prior workbook in this project (p7_build_excel.py, q5_build_excel_v2.py,
r2_build_excel_v3.py).

Sheets: README, Companies, Geography, Product_mapping, Revenue_at_risk,
EBITDA_at_risk, Reality_check, Event_study, Management_comments,
Sources.

READ-ONLY against the Phase 5 CSVs already produced. Writes
data/phase5_companies.xlsx (new file) only.
"""

import csv
from pathlib import Path
from openpyxl import Workbook

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

README_ROWS = [
    ("Sheet", "What it contains, in simple words"),
    ("Companies", "The 7 companies checked for this phase, with listing status, ticker, and why each was included or excluded. 5 are included (Poly Medicure, Laxmi Dental, Tarsons [flagged borderline - mainly lab plasticware], Sahajanand Medical Technologies/SMT [just listed Oct 2026], Translumina [via its parent Integris Medtech, also flagged borderline]). 2 are excluded with reasons: Healthium Medtech (still unlisted, only DRHP on file is 5+ years stale) and Meril Life Sciences (fully private, no public disclosure of any kind)."),
    ("Geography", "Where each company's revenue comes from, by period, as actually disclosed. IMPORTANT: only Laxmi Dental discloses a true US-specific %% (19.4%% of FY26 revenue) - every other company only gives India/Europe/Rest-of-World (or similar) buckets with NO US-only line. Where a cell says 'not disclosed', that is literally true - nothing was guessed."),
    ("Product_mapping", "Which of our 60 core medical-device HS codes (from core_device_codes.csv) each company's products map to, and on what basis. Tarsons has NO mapped codes at all - its lab-plasticware products fall outside every code in our list, which is the concrete reason it's flagged borderline."),
    ("Revenue_at_risk", "Company revenue at risk by scenario, low/base/high - calculated as (company's US/best-available revenue figure) x (the weighted revenue-at-risk %% of its mapped product codes, from the Phase 4 model). Every row states its own revenue-base caveat and weighting method in full."),
    ("EBITDA_at_risk", "The same risk split into its two parts as asked: the price-cut part (falls fully on EBITDA) plus the lost-orders part (falls on EBITDA only at the company's gross margin). Shown in Rs crore and as a %% of FY2025-26 EBITDA. 'Not disclosed' where a company's gross margin could not be found (POLYMED, SMT) - the split cannot be computed without it, so it is left blank rather than guessed."),
    ("Reality_check", "Compares each company's own reported growth figure against what India's actual trade data (Census) shows for that company's mapped codes, over the same Apr-Sep 2025 vs Apr-Sep 2026 window. Almost none of the companies report a true US-specific, exactly-matching-period figure - each row says plainly what the reported number actually measures (e.g. 'whole international revenue, not US-specific') rather than pretending it is a clean comparison."),
    ("Event_study", "For each stock and each of the 5 tariff-related event dates, whether the stock moved more or less than you'd expect given how it normally moves with the Nifty 50 (using 120 trading days of history ending 10 days before the event to learn the normal relationship). Shown for two windows (the event day plus the next day; and the day before through 5 days after), with a t-statistic and a plain yes/no on whether the move was big enough to be considered real (not just random noise) at the usual 5%% confidence level. SMT and Translumina are not in this sheet - SMT only listed in Oct 2026 (after every event date) and Translumina has no separate stock ticker at all. Nifty Healthcare could not be included as a second benchmark - Yahoo Finance only had 1 day of price history for it; only Nifty 50 is used."),
    ("Management_comments", "What company management actually said about tariffs, price cuts, lost customers, or moving production, quarter by quarter, with the call date and short quotes (under 15 words) plus a paraphrase of the fuller answer. Laxmi Dental has the most concrete numbers here - it is the only company that put an exact basis-point figure on the tariff hit to its margins, quarter by quarter."),
    ("Sources", "Every primary document used anywhere in this phase - annual reports, investor presentations, earnings-call transcripts, SEBI DRHPs - with its date and link, so every figure elsewhere in this workbook can be traced back to where it came from."),
    ("", ""),
    ("IMPORTANT CAVEAT 1 - US revenue is barely disclosed", "Of the 5 companies studied, only Laxmi Dental gives a real, audited US-specific revenue %%. For Poly Medicure, SMT and Translumina, this workbook uses the closest available substitute (a 'Rest of World' bucket, or a management-spoken dollar figure from an earnings call) and labels it clearly as NOT the real US figure every time it is used - this means Revenue_at_risk and EBITDA_at_risk for those three companies should be read as rough, not precise."),
    ("IMPORTANT CAVEAT 2 - Tarsons' product mix has no mapped codes", "Tarsons' core products (lab plasticware - pipettes, tubes, cryovials) fall under a different HS heading entirely from every code in our medical-device list. Every Tarsons row in Revenue_at_risk and EBITDA_at_risk is 'not computable', not zero - there is simply no bridge between Tarsons' real products and this project's tariff-gap model."),
    ("IMPORTANT CAVEAT 3 - SMT and Translumina have almost no post-event history", "SMT only became a listed company on 23 Oct 2026 - after all 5 event dates in the event study, and after most of the quarters this workbook otherwise covers. Translumina is not separately listed at all. Both companies' figures come mostly from their SEBI DRHP filings (pre-listing prospectuses), not from ongoing quarterly reporting."),
    ("Methodology notes", "Revenue-at-risk and EBITDA-at-risk reuse Phase 4's own tier-epsilon and fallback-alpha model (data/phase4_revenue_at_risk_v3.csv) exactly, combined per company using each company's own disclosed product-category weights where available (documented in Product_mapping), or an explicit equal-weight split where no finer split is disclosed. The RBI/FBIL reference rate for 31 March 2026 (94.6543 INR/USD, using 30 March 2026's rate since 31 March was a public holiday) is used for every USD-INR conversion in this workbook."),
    ("Blank cells", "Could not be reliably computed or found - deliberately left blank or 'not disclosed' rather than guessed. See logs/step1_progress_log.md for exactly what was tried."),
]

SHEETS = [
    ("Companies", "phase5_companies.csv"),
    ("Geography", "phase5_geography.csv"),
    ("Product_mapping", "phase5_product_mapping.csv"),
    ("Revenue_at_risk", "phase5_revenue_at_risk.csv"),
    ("EBITDA_at_risk", "phase5_ebitda_at_risk.csv"),
    ("Reality_check", "phase5_reality_check.csv"),
    ("Event_study", "phase5_event_study.csv"),
    ("Management_comments", "phase5_management_comments.csv"),
]

SOURCES_ROWS = [
    ("document", "company", "type", "date", "url"),
    ("DRHP", "SMT", "SEBI draft prospectus", "2025-07-26",
     "https://www.bseindia.com/corporates/download/356364/IPO%20Prior/SMTDRHP_20250726031147.pdf"),
    ("DRHP", "Integris Medtech / Translumina", "SEBI draft prospectus", "2025-10-09",
     "https://nsearchives.nseindia.com/corporate/Registration_10102025124732_DRHP.pdf"),
    ("DRHP (stale, not used for figures)", "Healthium Medtech", "SEBI draft prospectus", "2021-09-09",
     "https://www.bseindia.com/corporates/download/307520/HMLDRHP_20210909182436.pdf"),
    ("Q2 FY27 earnings call transcript", "POLYMED", "Earnings call transcript", "2026-11-05",
     "https://www.bseindia.com/xml-data/corpfiling/AttachLive/69faed0a-dab2-4511-b8be-188eb9c1ce8d.pdf"),
    ("FY26 annual investor presentation", "POLYMED", "Investor presentation", "2026-05-25 (approx)",
     "https://nsearchives.nseindia.com/corporate/POLYMED_25052026192531_Investor_Presentation_For_signed_final.pdf"),
    ("Q3 FY26 investor presentation", "POLYMED", "Investor presentation", "2026-03-07",
     "https://nsearchives.nseindia.com/corporate/POLYMED_07032026154146_Investor_Presentation_Final.pdf"),
    ("Q2 FY27 investor presentation", "LAXMIDENTL", "Investor presentation", "2026-11-03",
     "https://nsearchives.nseindia.com/corporate/LAXMI_03112026201100_Investor_Presentation.pdf"),
    ("Q2 FY27 earnings call transcript", "LAXMIDENTL", "Earnings call transcript", "2026-11-04",
     "https://www.bseindia.com/xml-data/corpfiling/AttachHis/8f013c28-ee49-45b7-99d4-43478495a6e2.pdf"),
    ("Q2 FY26 earnings call transcript", "TARSONS", "Earnings call transcript", "2025-11-13",
     "https://www.tarsons.com/wp-content/uploads/2025/08/SE_Transcripts_Q2_FY26.pdf"),
    ("Q2 FY26 investor presentation", "TARSONS", "Investor presentation", "2025-11 (approx)",
     "https://www.tarsons.com/wp-content/uploads/2025/11/SE_Investor_Presentation_Q2_FY26.pdf"),
    ("FY2024-25 annual report", "TARSONS", "Annual report", "2025-08 (approx)",
     "https://www.tarsons.com/wp-content/uploads/2025/08/Tarsons_AR2024-25_C2C_SGAAds_V6-Interactive.pdf"),
    ("FY2025-26 annual report", "TARSONS", "Annual report", "2026-09 (approx)",
     "https://www.tarsons.com/wp-content/uploads/2026/09/Tarsons_AR2025-26.pdf"),
    ("Daily share price history (yfinance)", "POLYMED/LAXMIDENTL/TARSONS/Nifty 50", "Market data", "downloaded 2026-11-15",
     "yfinance tickers POLYMED.NS, LAXMIDENTL.NS, TARSONS.NS, ^NSEI (Yahoo Finance)"),
    ("RBI/FBIL reference rate, 30 Mar 2026", "N/A - exchange rate", "Reference rate", "2026-03-30",
     "https://karwaandassociates.com/usd-inr-rate-30-march-2026-last-rate-for-fy-2025-26/ (cross-checked: https://www.exchange-rates.org/exchange-rate-history/usd-inr-2026-03-31)"),
    ("Phase 4 revenue-at-risk model (v3)", "N/A - internal", "This project's own prior output", "2026-11-15",
     "data/phase4_revenue_at_risk_v3.csv, data/phase4_tier_epsilon_v3.csv (built earlier in this same project)"),
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

    ws_sources = wb.create_sheet("Sources")
    for row in SOURCES_ROWS:
        ws_sources.append(row)
    for i in range(1, 6):
        ws_sources.column_dimensions[ws_sources.cell(row=1, column=i).column_letter].width = 28

    for ws in wb.worksheets:
        assert not ws.protection.sheet, f"{ws.title} should not be protected"
        assert len(ws.merged_cells.ranges) == 0, f"{ws.title} should have no merged cells"
        for row in ws.iter_rows():
            for cell in row:
                assert cell.data_type != "f", f"{ws.title} cell {cell.coordinate} is a formula"

    out_path = DATA_DIR / "phase5_companies.xlsx"
    wb.save(out_path)
    print(f"Wrote {out_path}")
    for ws in wb.worksheets:
        print(f"  {ws.title}: {ws.dimensions}")


if __name__ == "__main__":
    main()
