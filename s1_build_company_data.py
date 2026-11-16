"""
s1_build_company_data.py

Phase 5, Part 1-2: builds the company master list, geography revenue,
product-code mapping, financials, and management-commentary tables
from research gathered via WebSearch/WebFetch and primary-source PDFs
(annual reports, investor presentations, earnings call transcripts,
DRHPs) downloaded to raw/phase5_evidence/.

Every row carries its own source (document, date, and URL/page where
available). Where a figure could not be confirmed from a document,
the cell is left as "not disclosed" - never silently estimated, per
the user's explicit instruction for this phase.

Writes (new files): data/phase5_companies.csv, data/phase5_geography.csv,
data/phase5_product_mapping.csv, data/phase5_financials.csv,
data/phase5_management_comments.csv.
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

ND = "not disclosed"

# ---------------------------------------------------------------------------
# Part 1: company master list
# ---------------------------------------------------------------------------
COMPANIES = [
    {
        "ticker": "POLYMED", "name": "Poly Medicure Limited", "nse_yf_ticker": "POLYMED.NS",
        "listing_status": "Listed (NSE: POLYMED, BSE: 531768)", "borderline": "No",
        "business": "IV cannulas/infusion sets, syringes, needles, catheters, dialysis/renal products, surgical and respiratory disposables",
        "source": "Company is a long-listed NSE/BSE constituent; confirmed via SMT DRHP peer table (bseindia.com/corporates/download/356364/.../SMTDRHP_20250726031147.pdf, p.120) and Integris Medtech DRHP peer table (nsearchives.nseindia.com/corporate/Registration_10102025124732_DRHP.pdf, p.173-176)",
    },
    {
        "ticker": "LAXMIDENTL", "name": "Laxmi Dental Limited", "nse_yf_ticker": "LAXMIDENTL.NS",
        "listing_status": "Listed (NSE: LAXMIDENTL, BSE: 544339); listed 20 Jan 2025", "borderline": "No",
        "business": "Dental lab products (crowns, bridges, aligners), dental lab digital scanners, Clear aligners (Illusion Aligners)",
        "source": "Listing date and BSE scrip code from Laxmi Dental Q2 FY27 investor presentation (nsearchives.nseindia.com/corporate/LAXMI_03112026201100_Investor_Presentation.pdf, p.15); also in SMT/Integris DRHP peer tables",
    },
    {
        "ticker": "TARSONS", "name": "Tarsons Products Limited", "nse_yf_ticker": "TARSONS.NS",
        "listing_status": "Listed (NSE: TARSONS, BSE: 543399)", "borderline": "Yes - mainly lab plasticware (pipettes, centrifuge tubes, cryovials), not a device company; its core products fall under HS heading 3926 (plastic articles), OUTSIDE core_device_codes.csv entirely",
        "business": "Laboratory plasticware/labware (consumables + reusables) for life-science research and diagnostics labs",
        "source": "User's own framing in the Phase 5 request; confirmed via Tarsons Q2 FY26 investor presentation (tarsons.com/wp-content/uploads/2025/11/SE_Investor_Presentation_Q2_FY26.pdf, p.21-22 - 'plasticware' market framing throughout, no HS6 medical-device code overlap found in core_device_codes.csv",
    },
    {
        "ticker": "SMT", "name": "Sahajanand Medical Technologies Limited", "nse_yf_ticker": "SMT.NS",
        "listing_status": "Listed (NSE: SMT, BSE: 545001) on 23 Oct 2026", "borderline": "No",
        "business": "Cardiovascular devices: coronary drug-eluting stents (Supraflex Cruz), PTCA/drug-coated balloons, TAVI systems, occluders",
        "source": "Listing date/tickers confirmed via WebSearch (chittorgarh.com/ipo/sahajanand-medical-technologies-ipo/2550/, trendlyne.com/equity/3696010/SMT/). Financials from SMT's DRHP dated 26 Jul 2025 (bseindia.com/corporates/download/356364/IPO%20Prior/SMTDRHP_20250726031147.pdf), only FY23/24/25 + no post-listing quarterly results yet as of 15 Nov 2026 (listed too recently for a Q3 FY26 or later filing)",
    },
    {
        "ticker": "TRANSLUMINA", "name": "Translumina Therapeutics Pvt Ltd (via parent Integris Medtech Limited)",
        "nse_yf_ticker": ND,
        "listing_status": "NOT separately listed - Translumina is a 'material subsidiary' of Integris Medtech Limited, whose IPO (DRHP dated 9 Oct 2025, SEBI-approved 13 Feb 2026, opened 8 Nov 2026) was not confirmed as listed as of 15 Nov 2026 (no listing date/ticker found)",
        "borderline": "Yes - Integris Medtech is a mixed-business parent: ~55-60% of its FY25 revenue is a non-device Lab Solutions business (clinical diagnostics + scientific lab consumables), only the remaining Cardiovascular segment (DES, balloons, other cardiovascular products) is Translumina's actual device business. EBITDA, margins and geography are disclosed ONLY at the whole-Integris level in the DRHP - there is no way to isolate Translumina-only EBITDA or US/geography exposure from what's disclosed.",
        "business": "Cardiovascular devices: drug-eluting stents (DES), drug-coated balloons/balloon catheters, other cardiovascular products (within Integris Medtech, alongside its separate, larger Lab Solutions business)",
        "source": "Integris Medtech Limited DRHP dated 9 Oct 2025 (nsearchives.nseindia.com/corporate/Registration_10102025124732_DRHP.pdf), KPI table pp.169-176",
    },
    {
        "ticker": "HEALTHIUM", "name": "Healthium Medtech Limited", "nse_yf_ticker": ND,
        "listing_status": "NOT listed. KKR announced acquiring a controlling stake from Apax Partners-advised funds (announced ~Jan 2026). Only DRHP on file is dated September 2021 (sebi.gov.in/sebi_data/attachdocs/sep-2021/1631013990540.PDF) - more than 5 years stale, predates FY2024-25/FY2025-26 entirely. IPO dates remain 'to be announced' per multiple 2026 sources.",
        "borderline": "EXCLUDED - no usable current-period numbers",
        "business": "Surgical sutures, wound care, needles, urology products (owns Sutures India, Clinisupplies, Quality Needles)",
        "source": "WebSearch: business-standard.com/companies/news/kkr-to-acquire-bengaluru-based-medical-devices-company-healthium-medtech, religareonline.com/ipo/healthium-medtech-ipo, angelone.in/ipo/healthium-medtech-ipo",
    },
    {
        "ticker": "MERIL", "name": "Meril Life Sciences Private Limited", "nse_yf_ticker": ND,
        "listing_status": "NOT listed. Confirmed private/unlisted. No DRHP found anywhere.",
        "borderline": "EXCLUDED - no usable numbers, no public disclosure of any kind",
        "business": "Vascular intervention, orthopedic implants, robotics, endo-surgery, diagnostics",
        "source": "tracxn.com/d/legal-entities/india/meril-life-sciences-private-limited (CIN U24239GJ2007PTC051137, status Unlisted/Private), thecompanycheck.com",
    },
]

# ---------------------------------------------------------------------------
# Part 2b: revenue by geography
# ---------------------------------------------------------------------------
GEOGRAPHY = [
    # POLYMED - only India/Europe/RoW given; no US/Americas-specific % in any
    # investor presentation found. US revenue instead comes only from
    # earnings-call management commentary (a dollar figure, not a %).
    {"company": "POLYMED", "period": "FY2025", "india_pct": "31", "europe_pct": "32", "row_pct": "37",
     "us_or_americas_pct": ND, "us_revenue_usd_m": ND, "exports_pct": "69",
     "note": "Geography given only as India/Europe/RoW (no US/Americas line disclosed)",
     "source": "Poly Medicure FY26 annual investor presentation (nseindia.com, POLYMED_25052026192531), p.12"},
    {"company": "POLYMED", "period": "FY2026", "india_pct": "31", "europe_pct": "32", "row_pct": "36",
     "us_or_americas_pct": ND, "us_revenue_usd_m": ND, "exports_pct": "69",
     "note": "Geography given only as India/Europe/RoW. Management separately disclosed (not in this slide) that FY26 US revenue was 'less than $3-3.5 million' - a dollar figure from the Q1 FY26 earnings call, not a %, and not reconcilable to the RoW % bucket precisely",
     "source": "Poly Medicure FY26 annual investor presentation, p.12; US-dollar figure from Q1 FY26 earnings call (~Aug 2025), management commentary (Rahul Gautam) per WebSearch of multibagg.ai/scanx.trade coverage - exact transcript page not independently verified"},
    {"company": "POLYMED", "period": "9M FY2026 (Apr-Dec 2025)", "india_pct": "31", "europe_pct": "32", "row_pct": "37",
     "us_or_americas_pct": ND, "us_revenue_usd_m": ND, "exports_pct": "69",
     "note": "Geography given only as India/Europe/RoW",
     "source": "Poly Medicure Q3 FY26 investor presentation (nseindia.com, POLYMED_07032026154146), p.13"},
    {"company": "POLYMED", "period": "Q2 FY2027 (Jul-Sep 2026) / guidance", "india_pct": ND, "europe_pct": ND, "row_pct": ND,
     "us_or_americas_pct": ND, "us_revenue_usd_m": "7-8 (management TARGET for FY27, not an actual reported figure)",
     "exports_pct": ND,
     "note": "No geography % slide found for this specific quarter; management reiterated a USD 7-8 million FY27 group-level US sales target (scaling to USD15-25m over 3-4 years), and said US projects stalled by tariffs 'have picked up pace'",
     "source": "Poly Medicure Q2 FY27 earnings call transcript, Nov 5 2026 (bseindia.com/xml-data/corpfiling/AttachLive/69faed0a-dab2-4511-b8be-188eb9c1ce8d.pdf, p.6-7)"},

    # LAXMI DENTAL - the one company with an explicit disclosed USA %.
    {"company": "LAXMIDENTL", "period": "FY2026", "india_pct": "64.4", "europe_pct": ND, "row_pct": ND,
     "us_or_americas_pct": "19.4 (USA specifically)", "us_revenue_usd_m": ND, "exports_pct": "35.6",
     "note": "Explicit USA % disclosed: India 64.4%, USA 19.4%, UK 10.1%, Others 6.1% (sums to 100%). This is the clearest US-specific disclosure found across all 5 companies.",
     "source": "Laxmi Dental Q2 FY27 investor presentation (nsearchives.nseindia.com/corporate/LAXMI_03112026201100_Investor_Presentation.pdf), p.24 'Connecting Dental Care across Geographies'"},
    {"company": "LAXMIDENTL", "period": "FY2026 (Dental Lab segment only)", "india_pct": ND, "europe_pct": ND, "row_pct": ND,
     "us_or_americas_pct": "~25 of laboratory business specifically (not whole-company)", "us_revenue_usd_m": ND,
     "exports_pct": ND,
     "note": "Segment-specific (narrower) disclosure: 'US is ~25% of laboratory business; a dedicated CEO drives market-specific growth' - this is a different base (lab segment only) than the whole-company 19.4% figure above, not directly comparable",
     "source": "Laxmi Dental Q2 FY27 investor presentation, p.18 'Dental Laboratory: Top-2 Domestic Player & Largest Indian Exporter'"},

    # TARSONS - no numeric geography % found; only qualitative export commentary.
    {"company": "TARSONS", "period": "FY2025", "india_pct": ND, "europe_pct": ND, "row_pct": ND,
     "us_or_americas_pct": ND, "us_revenue_usd_m": ND, "exports_pct": ND,
     "note": "No numeric US/Americas % disclosed in the investor presentation searched. Export revenue (all geographies combined) was INR 998 million in FY25 vs INR 480 million in FY19 (65%/35% branded-ODM split FY25 vs 69%/31% FY19) - geography within exports not broken out by country",
     "source": "Tarsons Q2 FY26 investor presentation (tarsons.com/wp-content/uploads/2025/11/SE_Investor_Presentation_Q2_FY26.pdf), p.22"},

    # SMT - India/Europe/RoW only, same gap as POLYMED.
    {"company": "SMT", "period": "FY2025", "india_pct": "31.28", "europe_pct": "32.96", "row_pct": "35.76",
     "us_or_americas_pct": ND, "us_revenue_usd_m": ND, "exports_pct": "68.72",
     "note": "Geography given only as India/Europe/RoW (no US/Americas line). US appears in the DRHP only via FDA-related legal boilerplate, not a revenue breakdown",
     "source": "SMT DRHP (bseindia.com/corporates/download/356364/.../SMTDRHP_20250726031147.pdf), p.121, KPI table 'Revenue Split by Geography'"},
    {"company": "SMT", "period": "FY2024", "india_pct": "34.80", "europe_pct": "29.52", "row_pct": "35.68",
     "us_or_americas_pct": ND, "us_revenue_usd_m": ND, "exports_pct": "65.2",
     "note": "Geography given only as India/Europe/RoW", "source": "SMT DRHP, p.121"},
    {"company": "SMT", "period": "FY2023", "india_pct": "36.39", "europe_pct": "27.82", "row_pct": "35.78",
     "us_or_americas_pct": ND, "us_revenue_usd_m": ND, "exports_pct": "63.6",
     "note": "Geography given only as India/Europe/RoW", "source": "SMT DRHP, p.121"},

    # TRANSLUMINA/Integris - India/Europe/Asia(ex-India)/ROW only, whole-company level.
    {"company": "TRANSLUMINA", "period": "FY2025 (whole Integris, mixed with Lab Solutions)",
     "india_pct": "35.1 (6,674.88 of 19,024.66 mn)", "europe_pct": "8.0 (1,514.22mn)",
     "row_pct": "3.8 (728.67mn, labelled Rest of World)", "us_or_americas_pct": ND, "us_revenue_usd_m": ND,
     "exports_pct": "64.9 (includes 53.1% 'Asia excl. India' = 10,106.89mn)",
     "note": "No US/Americas line; geography mixes the non-device Lab Solutions business with Translumina's Cardiovascular segment - cannot be isolated to Translumina alone from what's disclosed",
     "source": "Integris Medtech DRHP (nsearchives.nseindia.com/corporate/Registration_10102025124732_DRHP.pdf), p.170"},
]

# ---------------------------------------------------------------------------
# Part 2c: product mapping to core_device_codes.csv
# ---------------------------------------------------------------------------
PRODUCT_MAPPING = [
    {"company": "POLYMED", "hs6_code": "901839", "hs6_description": "Catheters cannulas and the like",
     "group": "Consumables", "weight_basis": "Primary product line (IV cannulas, infusion sets) - Infusion Therapy segment was 53% of FY26 revenue",
     "source": "Poly Medicure FY26 investor presentation p.13 (segment mix); product identity from company's own product catalogue (polymedicure.com) - not independently re-verified against HS code text beyond the obvious 'cannula' match"},
    {"company": "POLYMED", "hs6_code": "901831", "hs6_description": "Syringes", "group": "Consumables",
     "weight_basis": "Safety syringes and blood-collection products are a core Poly Medicure line",
     "source": "Company product catalogue (polymedicure.com); not separately broken out as its own segment in investor materials"},
    {"company": "POLYMED", "hs6_code": "901832", "hs6_description": "Tubular metal needles and suture needles",
     "group": "Consumables", "weight_basis": "Needles are part of the IV/infusion product family",
     "source": "Company product catalogue (polymedicure.com)"},
    {"company": "POLYMED", "hs6_code": "901890", "hs6_description": "Other medical and surgical instruments",
     "group": "Instruments", "weight_basis": "Catch-all for Poly Medicure's surgical, anaesthesia and renal/dialysis product lines (Renal segment was 10% of FY26 revenue)",
     "source": "Poly Medicure FY26 investor presentation p.13 (segment mix: Renal 10%, Others 37%); exact HS6-level product identity not independently confirmed - FLAGGED AS APPROXIMATE"},
    {"company": "LAXMIDENTL", "hs6_code": "902121", "hs6_description": "Artificial teeth", "group": "Dental",
     "weight_basis": "Primary product (zirconia-led crowns, bridges, aesthetic prostheses) - this IS the company's core Dental Laboratory business",
     "source": "Laxmi Dental Q2 FY27 investor presentation p.18 ('Zirconia-led, aesthetic metal-free crowns, bridges and prostheses')"},
    {"company": "LAXMIDENTL", "hs6_code": "902129", "hs6_description": "Other dental fittings", "group": "Dental",
     "weight_basis": "Secondary dental-lab product category (fittings/appliances beyond artificial teeth)",
     "source": "Company product catalogue (laxmidentallimited.com)"},
    {"company": "TARSONS", "hs6_code": ND, "hs6_description": "NO MAPPED CODE",
     "group": "N/A", "weight_basis": "Tarsons' core products (pipettes, centrifuge tubes, cryovials, labware) fall under HS heading 3926 (plastic articles) - this heading does NOT appear anywhere in core_device_codes.csv, which covers HS Chapters 30/38/40/84/90/94 medical-device codes only",
     "source": "Reviewed full core_device_codes.csv (60 codes) - no overlap found. This is the concrete basis for flagging Tarsons as 'borderline' per the user's own framing"},
    {"company": "SMT", "hs6_code": "902190", "hs6_description": "Other appliances implanted or worn incl. stents",
     "group": "Implants", "weight_basis": "Primary product (coronary drug-eluting stents, e.g. Supraflex Cruz) - VI devices were 65.86% of FY25 revenue",
     "source": "SMT DRHP p.357 ('Revenue from sale of VI devices... Supraflex Cruz... single largest contributor')"},
    {"company": "SMT", "hs6_code": "901839", "hs6_description": "Catheters cannulas and the like", "group": "Consumables",
     "weight_basis": "PTCA/drug-coated balloon catheters are part of the VI product family",
     "source": "SMT DRHP p.360 (VI products include 'coronary balloon, peripheral drug coated balloons')"},
    {"company": "SMT", "hs6_code": "902139", "hs6_description": "Other artificial parts of the body", "group": "Implants",
     "weight_basis": "TAVI (transcatheter aortic valve implantation) systems and occluders - Structural Heart (SH) segment, 15.35% of FY25 revenue",
     "source": "SMT DRHP p.360 ('structural heart therapy (SH) products including aortic valve and occluders')"},
    {"company": "TRANSLUMINA", "hs6_code": "902190", "hs6_description": "Other appliances implanted or worn incl. stents",
     "group": "Implants", "weight_basis": "Drug-eluting stents (DES) - part of the Cardiovascular segment (DES and Balloons: INR3,436.45mn of FY25 revenue)",
     "source": "Integris Medtech DRHP p.169 (KPI table, 'Cardiovascular - DES and Balloon')"},
    {"company": "TRANSLUMINA", "hs6_code": "901839", "hs6_description": "Catheters cannulas and the like",
     "group": "Consumables", "weight_basis": "Drug-coated balloons/balloon catheters - same Cardiovascular segment line as above",
     "source": "Integris Medtech DRHP p.169"},
]

# ---------------------------------------------------------------------------
# Part 2a: financials (revenue, EBITDA, margins) - annual + quarterly
# ---------------------------------------------------------------------------
FINANCIALS = [
    # POLYMED
    {"company": "POLYMED", "period": "FY2023", "period_type": "Annual", "revenue_cr": "1115.23",
     "ebitda_cr": "274.28", "ebitda_margin_pct": "24.59", "gross_margin_pct": "63.61", "pat_cr": "179.28",
     "source": "Integris Medtech DRHP p.176 (FY ended 31 Mar 2023, sourced from F&S Report using POLYMED's own audited financials)"},
    {"company": "POLYMED", "period": "FY2024", "period_type": "Annual", "revenue_cr": "1375.80",
     "ebitda_cr": "375.92", "ebitda_margin_pct": "27.32", "gross_margin_pct": "64.92", "pat_cr": "258.26",
     "source": "Integris Medtech DRHP p.175 (FY ended 31 Mar 2024)"},
    {"company": "POLYMED", "period": "FY2025", "period_type": "Annual", "revenue_cr": "1669.83",
     "ebitda_cr": "479.65", "ebitda_margin_pct": "28.72", "gross_margin_pct": "66.78", "pat_cr": "338.56",
     "source": "Integris Medtech DRHP p.174 (FY ended 31 Mar 2025); NOTE a slightly different consolidated EBITDA margin of 27.5% for FY25 is cited elsewhere in secondary market commentary (WebSearch of multibagg.ai) - discrepancy not silently resolved, likely different EBITDA construct (reported consolidated vs F&S-report definition); both are recorded rather than picking one"},
    {"company": "POLYMED", "period": "FY2026", "period_type": "Annual", "revenue_cr": "1875.30",
     "ebitda_cr": "457.70", "ebitda_margin_pct": "24.40", "gross_margin_pct": ND, "pat_cr": ND,
     "source": "WebSearch of multibagg.ai coverage of Q4/FY26 results ('Consolidated FY26 operating EBITDA... INR 457.7 crore... margin declined to 24.4% from 27.5% in FY25'); standalone EBITDA margin separately reported at 26.8%; gross margin and PAT for FY26 not independently located - recorded as not disclosed rather than estimated"},
    {"company": "POLYMED", "period": "Q4 FY2026 (Jan-Mar 2026)", "period_type": "Quarterly", "revenue_cr": "534.51",
     "ebitda_cr": ND, "ebitda_margin_pct": "21", "gross_margin_pct": ND, "pat_cr": "65.04",
     "source": "WebSearch of multibagg.ai/business-standard.com coverage ('Q4 FY26 consolidated revenue +21.25% YoY to Rs534.51cr, PAT -29.17% to Rs65.04cr, EBITDA margin dropped to ~21%')"},
    {"company": "POLYMED", "period": "Q2 FY2027 (Jul-Sep 2026)", "period_type": "Quarterly", "revenue_cr": "580.5",
     "ebitda_cr": ND, "ebitda_margin_pct": ND, "gross_margin_pct": ND, "pat_cr": "95",
     "source": "WebSearch of businessupturn.com/investywise.com coverage of Q2 FY27 results (revenue Rs580.5cr, +30.7% YoY; PAT Rs95cr, +3.3% YoY); EBITDA figure not independently located for this specific quarter in isolation (only H1 FY27 cumulative EBITDA of Rs255cr, +20% YoY, was found) - recorded as not disclosed rather than estimated"},

    # LAXMIDENTL
    {"company": "LAXMIDENTL", "period": "FY2023", "period_type": "Annual", "revenue_cr": "161.63",
     "ebitda_cr": "10.25", "ebitda_margin_pct": "6.34", "gross_margin_pct": "74.14", "pat_cr": "(4.16)",
     "source": "Integris Medtech DRHP p.176 (FY ended 31 Mar 2023)"},
    {"company": "LAXMIDENTL", "period": "FY2024", "period_type": "Annual", "revenue_cr": "193.56",
     "ebitda_cr": "24.36", "ebitda_margin_pct": "12.59", "gross_margin_pct": "74.95", "pat_cr": "25.23",
     "source": "Integris Medtech DRHP p.175 (FY ended 31 Mar 2024)"},
    {"company": "LAXMIDENTL", "period": "FY2025", "period_type": "Annual", "revenue_cr": "239.11",
     "ebitda_cr": "43.44", "ebitda_margin_pct": "18.17", "gross_margin_pct": "76.06", "pat_cr": "31.83",
     "source": "Integris Medtech DRHP p.174 (FY ended 31 Mar 2025); NOTE WebSearch secondary coverage cites FY25 EBITDA margin as 17.5% (slightly different) - both recorded rather than silently reconciled"},
    {"company": "LAXMIDENTL", "period": "FY2026", "period_type": "Annual", "revenue_cr": "277.86",
     "ebitda_cr": "43.4", "ebitda_margin_pct": "15.6", "gross_margin_pct": ND, "pat_cr": "28.9",
     "source": "WebSearch of multibagg.ai coverage ('FY26 consolidated revenue +16.2% YoY to Rs277.86cr... EBITDA rose 3.6% to Rs43.4cr, margin 15.6% vs 17.5% in FY25... PAT Rs28.9cr'). Margin decline explicitly attributed by management to one-off factors including 72bps from US tariffs, Rs5.78cr labour-code one-time expense, higher ESOP expense"},
    {"company": "LAXMIDENTL", "period": "Q2 FY2026 (Jul-Sep 2025)", "period_type": "Quarterly", "revenue_cr": "72.27",
     "ebitda_cr": "11.02", "ebitda_margin_pct": ND, "gross_margin_pct": ND, "pat_cr": "8.53",
     "source": "WebSearch of sahyadristartups.com coverage (revenue INR722.7mn, PAT +44.7% YoY to INR85.3mn, EBITDA INR110.2mn +26.3% YoY)"},
    {"company": "LAXMIDENTL", "period": "Q2 FY2027 (Jul-Sep 2026)", "period_type": "Quarterly", "revenue_cr": "79.52",
     "ebitda_cr": ND, "ebitda_margin_pct": "19.2", "gross_margin_pct": "76.9", "pat_cr": "10.04",
     "source": "WebSearch of multibagg.ai coverage (revenue Rs79.52cr vs Rs72.3cr Q2FY26, highest-ever quarterly; PAT Rs10.04cr; gross margin expanded to 76.9% from 68.5% YoY on favourable mix). A separate ~INR5.5 crore tariff REFUND (excl. interest) was disclosed as to be reflected in Q3 FY27, not this quarter",
     },

    # TARSONS
    {"company": "TARSONS", "period": "FY2025 (2024-25)", "period_type": "Annual", "revenue_cr": "392",
     "ebitda_cr": "110.7", "ebitda_margin_pct": "28.2", "gross_margin_pct": ND, "pat_cr": ND,
     "source": "WebSearch of company-check/scanx.trade coverage of Tarsons AR2024-25 (tarsons.com/wp-content/uploads/2025/08/Tarsons_AR2024-25_C2C_SGAAds_V6-Interactive.pdf - PDF located but not independently re-read page-by-page for this figure, taken from WebSearch summary of its contents)"},
    {"company": "TARSONS", "period": "FY2026 (2025-26)", "period_type": "Annual", "revenue_cr": "422.5",
     "ebitda_cr": "117.9", "ebitda_margin_pct": "27.9", "gross_margin_pct": ND, "pat_cr": ND,
     "source": "WebSearch of scanx.trade coverage ('FY26 revenue +7.7% YoY to Rs422.5cr, EBITDA +7.0% to Rs117.9cr, margin 27.9% vs 28.2% FY25'); corresponds to Tarsons_AR2025-26.pdf (tarsons.com/wp-content/uploads/2026/09/)"},
    {"company": "TARSONS", "period": "Q2 FY2026 (Jul-Sep 2025)", "period_type": "Quarterly", "revenue_cr": "102",
     "ebitda_cr": "27", "ebitda_margin_pct": "26.8", "gross_margin_pct": ND, "pat_cr": "3.3",
     "source": "Tarsons Q2 FY26 earnings call transcript (tarsons.com/wp-content/uploads/2025/08/SE_Transcripts_Q2_FY26.pdf), p.4 - management's own spoken figures"},
    {"company": "TARSONS", "period": "Q2 FY2027 (Jul-Sep 2026)", "period_type": "Quarterly", "revenue_cr": "123.65",
     "ebitda_cr": ND, "ebitda_margin_pct": ND, "gross_margin_pct": "~67 (down from 'early 70s')", "pat_cr": "(0.34)",
     "source": "WebSearch of univest.in/multibagg.ai coverage of Q2 FY27 results (revenue +20.83% YoY to Rs123.65cr; consolidated net LOSS of Rs0.34cr vs Rs3.32cr profit in Q2FY26; gross margin pressured to ~67% from low-to-mid 70s by a 30-50% surge in crude-linked raw material prices since March 2026; export revenue +37% YoY)"},

    # SMT
    {"company": "SMT", "period": "FY2023", "period_type": "Annual", "revenue_cr": "795.55",
     "ebitda_cr": "110.77", "ebitda_margin_pct": "13.92", "gross_margin_pct": ND, "pat_cr": "11.93",
     "source": "SMT DRHP p.120-121 KPI table (FY ended 31 Mar 2023; revenue 7,955.49mn, EBITDA 1,107.73mn, PAT 119.34mn - gross margin not given as a separate KPI by SMT, unlike the Integris-format tables)"},
    {"company": "SMT", "period": "FY2024", "period_type": "Annual", "revenue_cr": "901.60",
     "ebitda_cr": "110.05", "ebitda_margin_pct": "12.21", "gross_margin_pct": ND, "pat_cr": "(7.35)",
     "source": "SMT DRHP p.120-121 (revenue 9,016.04mn, EBITDA 1,100.47mn, PAT loss 73.54mn)"},
    {"company": "SMT", "period": "FY2025", "period_type": "Annual", "revenue_cr": "1024.88",
     "ebitda_cr": "128.02", "ebitda_margin_pct": "12.49", "gross_margin_pct": ND, "pat_cr": "25.15",
     "source": "SMT DRHP p.120-121 (revenue 10,248.79mn, EBITDA 1,280.21mn, PAT 251.52mn)"},
    {"company": "SMT", "period": "FY2026 / Q1-Q2 FY2027", "period_type": "Annual/Quarterly", "revenue_cr": ND,
     "ebitda_cr": ND, "ebitda_margin_pct": ND, "gross_margin_pct": ND, "pat_cr": ND,
     "source": "NOT DISCLOSED - SMT listed only on 23 Oct 2026; no post-listing quarterly results have been filed as of 15 Nov 2026 (first results as a listed company will likely be Q3 FY26, due ~Jan/Feb 2027, or a maiden post-IPO update)"},

    # TRANSLUMINA (whole Integris Medtech, mixed with Lab Solutions)
    {"company": "TRANSLUMINA", "period": "FY2023 (whole Integris)", "period_type": "Annual", "revenue_cr": "1348.10",
     "ebitda_cr": "168.82", "ebitda_margin_pct": "12.52", "gross_margin_pct": "42.47", "pat_cr": "(40.54)",
     "source": "Integris Medtech DRHP p.169 (FY ended 31 Mar 2023; whole-company, not Translumina/Cardiovascular segment alone - EBITDA/margin NOT available at segment level)"},
    {"company": "TRANSLUMINA", "period": "FY2024 (whole Integris)", "period_type": "Annual", "revenue_cr": "1553.38",
     "ebitda_cr": "190.45", "ebitda_margin_pct": "12.26", "gross_margin_pct": "43.29", "pat_cr": "(4.88)",
     "source": "Integris Medtech DRHP p.169 (FY ended 31 Mar 2024, whole-company)"},
    {"company": "TRANSLUMINA", "period": "FY2025 (whole Integris)", "period_type": "Annual", "revenue_cr": "1902.47",
     "ebitda_cr": "309.40", "ebitda_margin_pct": "16.26", "gross_margin_pct": "43.95", "pat_cr": "70.68",
     "source": "Integris Medtech DRHP p.169 (FY ended 31 Mar 2025, whole-company)"},
    {"company": "TRANSLUMINA", "period": "Q1 FY2026 (Apr-Jun 2025, whole Integris)", "period_type": "Quarterly",
     "revenue_cr": "485.25", "ebitda_cr": "78.73", "ebitda_margin_pct": "16.22", "gross_margin_pct": "45.09",
     "pat_cr": "267.57",
     "source": "Integris Medtech DRHP p.169 (3 months ended 30 Jun 2025, whole-company; large PAT figure reflects a one-off item per DRHP context, not restated here beyond what's shown)"},
]

# ---------------------------------------------------------------------------
# Part 2d: management commentary on tariffs/price cuts/lost customers/production
# ---------------------------------------------------------------------------
MANAGEMENT_COMMENTS = [
    {"company": "POLYMED", "quarter": "Q2 FY2027", "call_date": "2026-11-05",
     "speaker": "Rahul Gautam (management)",
     "quote_short": "'projects... had come to a standstill last year because of the tariffs issue, have picked up pace'",
     "paraphrase": "Management said the US business is recovering after projects stalled by tariffs last year resumed, with a new 510(k) approval (irrigation set) and the company on track to hit its $7-8M US sales guidance for the group this year.",
     "source": "Poly Medicure Q2 FY27 earnings call transcript (bseindia.com/xml-data/corpfiling/AttachLive/69faed0a-dab2-4511-b8be-188eb9c1ce8d.pdf), p.6"},
    {"company": "POLYMED", "quarter": "Q2 FY2027", "call_date": "2026-11-05",
     "speaker": "Rahul Gautam (management)",
     "quote_short": "'reasons for it... challenges of tariffs, as well as the dumping'",
     "paraphrase": "On Europe: last year was tough due to over-inventory and tariff challenges plus Chinese dumping, but the company has since deepened customer engagement (28-29 new customers added in H1) and expects continued organic growth; said Chinese dumping 'is not a medical device issue' specifically and is a broader rhetoric point, while the company competes via customer relationships and new product registrations (30 pending in the relevant market).",
     "source": "Poly Medicure Q2 FY27 earnings call transcript, p.7-8"},
    {"company": "POLYMED", "quarter": "FY2026 (annual presentation)", "call_date": "2026-05-25 (approx, FY26 annual presentation date)",
     "speaker": "Company presentation (PendraCare subsidiary slide)",
     "quote_short": "'Reinitiated conversations with customers post reduction of US tariffs'",
     "paraphrase": "For the PendraCare subsidiary specifically, the company said it had reinitiated customer conversations after a reduction in US tariffs, with revenue ramp-up expected in FY27.",
     "source": "Poly Medicure FY26 annual investor presentation (POLYMED_25052026192531), p.39 'International Strategy – US'"},
    {"company": "LAXMIDENTL", "quarter": "FY2026 (full year)", "call_date": "2026-05-22 (approx, Q4/FY26 results date)",
     "speaker": "Management (FY26 results commentary)",
     "quote_short": "'72 basis points impact from US tariffs'",
     "paraphrase": "Management explicitly quantified the FY26 EBITDA margin decline (17.5% to 15.6%) as driven partly by a 72bps hit from US tariffs, alongside a one-time Rs5.78cr labour-code expense and higher ESOP costs.",
     "source": "WebSearch of multibagg.ai/business-standard.com coverage of Laxmi Dental FY26/Q4FY26 results"},
    {"company": "LAXMIDENTL", "quarter": "Q3 FY2026", "call_date": "2026-02-17 (approx, per financepulse.ai Q3 FY26 call date)",
     "speaker": "Management (Q3 FY26 results commentary)",
     "quote_short": "'150 basis points' impact from higher US tariffs",
     "paraphrase": "In Q3 FY26 specifically, management said EBITDA margin was hit by 150bps due to higher US tariffs - a larger single-quarter impact than the full-year 72bps figure, implying other quarters were less affected or partially offset.",
     "source": "WebSearch of secondary coverage (financepulse.ai/multibagg.ai) of Laxmi Dental Q3 FY26 earnings call"},
    {"company": "LAXMIDENTL", "quarter": "Q4 FY2026", "call_date": "2026-05-22 (approx)",
     "speaker": "Management (Q4 FY26 results commentary)",
     "quote_short": "'74 basis points' half-quarter impact",
     "paraphrase": "Q4 FY26 included a half-quarter impact from higher US tariffs, estimated at 74bps on EBITDA margin.",
     "source": "WebSearch of secondary coverage (multibagg.ai) of Laxmi Dental Q4 FY26 results"},
    {"company": "LAXMIDENTL", "quarter": "Q2 FY2027", "call_date": "2026-11-04",
     "speaker": "Management (Q2/H1 FY27 results commentary)",
     "quote_short": "~INR5.5 crore tariff REFUND to be reflected in Q3 FY27",
     "paraphrase": "Management disclosed an approximately Rs5.5 crore tariff refund (excluding interest) that will be reflected in Q3 FY27 results - the first positive/reversing tariff-related disclosure found across any of the five companies, suggesting a prior overpayment or duty-drawback type refund is being processed.",
     "source": "WebSearch of secondary coverage (per the Q2FY27/H1FY27 earnings call, 4 Nov 2026) - exact transcript page not independently verified, as the downloaded transcript PDFs (laxmi_q2fy27_transcript_v2.pdf / _v3.pdf) were not read page-by-page for this specific figure"},
    {"company": "TARSONS", "quarter": "Q2 FY2026", "call_date": "2025-11-13",
     "speaker": "Santosh Agarwal (management)",
     "quote_short": "'we have not lost any customers, and any orders'",
     "paraphrase": "On the 50% US tariff: management called it 'a kind of no trade zone for everyone' but said Tarsons has a decade-long relationship with US customers and has not lost any customers or orders; both sides remain optimistic about a tariff reduction. On passing costs through: management said they 'have not discussed until that level' and are waiting for a US tariff trade deal before deciding. Export softness was attributed mainly to a bill-of-lading/logistics delay and capacity constraints, not demand or tariff-driven order loss.",
     "source": "Tarsons Q2 FY26 earnings call transcript (tarsons.com/wp-content/uploads/2025/08/SE_Transcripts_Q2_FY26.pdf), p.4-5"},
    {"company": "TARSONS", "quarter": "Q2 FY2026", "call_date": "2025-11-13",
     "speaker": "Santosh Agarwal (management)",
     "quote_short": "'things... not worked out... like U.S. tariff'",
     "paraphrase": "Asked what didn't work out versus plan for the year, management cited several factors beyond its control including the global freight situation, a bill-of-lading implementation issue, and the US tariff - saying growth would have been better without them.",
     "source": "Tarsons Q2 FY26 earnings call transcript, p.13"},
    {"company": "TARSONS", "quarter": "Q2 FY2027", "call_date": "2026-11-13 (approx, per gurufocus coverage)",
     "speaker": "Management (Q2 FY27 results commentary)",
     "quote_short": "export revenue +37% YoY despite margin pressure",
     "paraphrase": "Export revenue showed a strong 37% YoY recovery in Q2 FY27 (33% in H1 FY27), but gross margins were separately pressured by a 30-50% surge in crude-linked raw material prices since March 2026 (unrelated to tariffs) - the quarter's net loss was attributed to this input-cost pressure plus newly commissioned facility costs, not tariffs specifically.",
     "source": "WebSearch of gurufocus.com (via ca.investing.com mirror) coverage of Tarsons Q2 2027 earnings call highlights"},
    {"company": "SMT", "quarter": "N/A - DRHP risk factors (pre-listing)", "call_date": "2025-07-26 (DRHP date)",
     "speaker": "DRHP risk-factor disclosure (not an earnings call - SMT had no public shareholders/calls before its Oct 2026 listing)",
     "quote_short": "no US tariff-specific commentary found in the DRHP text searched",
     "paraphrase": "The SMT DRHP's 15 pages mentioning 'tariff' were reviewed by search but a specific US Section 301/232 tariff passage was not located in the pages checked (44, 49, 61-63, 131, 138-141, 159-160, 252, 356); SMT had no earnings calls before its 23 Oct 2026 listing and has not yet reported results as a listed company.",
     "source": "SMT DRHP full-text term search (bseindia.com/.../SMTDRHP_20250726031147.pdf) - pages containing 'tariff' identified but not all individually read in full; recorded as not disclosed/not found rather than guessed"},
    {"company": "TRANSLUMINA", "quarter": "N/A - DRHP (pre-listing)", "call_date": "2025-10-09 (DRHP date)",
     "speaker": "DRHP text",
     "quote_short": "no Section 301/232-specific commentary found",
     "paraphrase": "The Integris Medtech DRHP's 6 pages mentioning 'tariff' (pp.40, 76, 182, 187, 199, 203) were general industry-risk language about regulatory complexity (FDA, EU MDR) rather than Section 301/232-specific commentary; 'Section 301' and 'Section 232' do not appear anywhere in the document's searchable text. No earnings calls exist yet (not confirmed listed).",
     "source": "Integris Medtech DRHP full-text term search (nsearchives.nseindia.com/corporate/Registration_10102025124732_DRHP.pdf)"},
]


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {path} ({len(rows)} rows)")


def main():
    write_csv(DATA_DIR / "phase5_companies.csv", COMPANIES)
    write_csv(DATA_DIR / "phase5_geography.csv", GEOGRAPHY)
    write_csv(DATA_DIR / "phase5_product_mapping.csv", PRODUCT_MAPPING)
    write_csv(DATA_DIR / "phase5_financials.csv", FINANCIALS)
    write_csv(DATA_DIR / "phase5_management_comments.csv", MANAGEMENT_COMMENTS)


if __name__ == "__main__":
    main()
