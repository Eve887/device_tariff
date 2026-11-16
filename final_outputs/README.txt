================================================================
 MEDICAL DEVICE TARIFF PROJECT - FINAL OUTPUTS
 Packaged 2026-11-15
================================================================

WHAT THIS FOLDER IS
--------------------
This folder holds only the FINAL, user-facing deliverable from each
phase of the project, plus every script that was used to build them
and the full step-by-step log of how they were made. Nothing here
was changed from the working copies in E:\device_tariff\data\ and
E:\device_tariff\logs\ - these are plain copies.

FILES IN THIS FOLDER
----------------------

Phase 1 (official tariff rates and exemption check, made 8 Nov 2026
outside this log):
  Medical_Device_Tariff_Rulebook_Phase1.xlsx
                               Official tariff rates and exemption check,
                               made 8 Nov 2026 outside this log - produced
                               in a separate chat before step1_progress_log.md
                               started, which is why this project's own log
                               never mentions it and an earlier version of
                               this README said it could not be found.
                               NOTE - three facts in this file are
                               SUPERSEDED by Phase 3: China exclusions were
                               extended to 9 Jan 2027; EU suppliers actually
                               paid about 9-11%, not a flat 15%; Mexico
                               actually paid about 1.6-3.5%, not 0%. See
                               phase3_tariff_gap_v2.xlsx for the corrected
                               values.

Phase 2 (US-India medical device trade data):
  core_device_codes.csv       The 60 HS codes this whole project treats as
                               "real" medical devices (Phase 3's Fix 1 output).
  pharma_like_codes.csv       2 codes split OUT of the device list because
                               they're medicines, not devices (hormonal
                               contraceptives, X-ray contrast preparations).
  hygiene_codes.csv           1 code split OUT because it's a hygiene product
                               (sanitary pads/tampons/diapers), not a device.
  lab_instruments_codes.csv   2 codes (902781/902789, lab/scientific
                               instruments) kept separate from the main device
                               list since Census confirmed they're a real,
                               current HS2022 split, but not core devices.
  phase2_final_summary.csv    One row per code x year (2022-2026 YTD):
                               US imports from India, India's US market share,
                               top 3 suppliers, exports, duty paid, etc.
  phase2_final_checks.txt     The reconciliation report: does our total match
                               EPCMD's official $782.57M figure, country
                               comparisons, HOLDS/DOES-NOT-HOLD verdicts.

Phase 3 (tariff gap - who pays what, and the real competitor rates):
  phase3_tariff_gap_v2.xlsx   THE Phase 3 deliverable (not the first-pass
                               phase3_tariff_gap.xlsx, which this v2
                               supersedes) - every code's listed vs. actual
                               duty paid, corrected for the real USTR
                               country-tier structure, plus the top-15
                               competitor check sheet. README sheet inside
                               explains every column.
  monthly_imports.csv         Month-by-month India/China/all-countries import
                               values, used to check whether India
                               "front-loaded" shipments ahead of tariff
                               deadlines.

Phase 4 (scenarios, revenue at risk, exposure score):
  phase4_scenarios_v3.xlsx    THE Phase 4 deliverable (the third and final
                               version, after two rounds of user-directed
                               fixes) - tier-level elasticity, the fallback
                               price-absorption assumption (with the
                               unstable measured alternative kept for
                               reference only), scenario-by-scenario revenue
                               and EBITDA at risk for S0-S5, the persistent-
                               loss check, and the exposure score ranking.

Phase 5 (which listed companies are actually exposed):
  phase5_companies.xlsx       THE Phase 5 deliverable - the 5 companies
                               checked, where each gets its revenue (US or
                               best available substitute, clearly labelled),
                               product-code mapping, revenue/EBITDA at risk
                               by scenario, the reality check against real
                               trade data, the share-price event study
                               around 5 tariff-related dates, and every
                               management quote on tariffs found, with
                               sources.

step1_progress_log.md         The complete, unedited step-by-step log of
                               this entire project - every command run,
                               every bug found and fixed, every data source
                               checked, every number's origin. If you want
                               to know WHY a number is what it is, or what
                               was tried and didn't work, this is where to
                               look. (Despite its name, this is the single
                               log file for the WHOLE project, all phases.)

scripts\                      Every Python script used anywhere in this
                               project (55 files), described below in the
                               order you'd run them to rebuild everything.

HOW TO REBUILD EVERYTHING FROM SCRATCH
-----------------------------------------
Before starting: you need (1) Python 3.14+ with pandas, numpy, scipy,
openpyxl, pymupdf, pypdf, and yfinance installed (`pip install
pandas numpy scipy openpyxl pymupdf pypdf yfinance`), (2) a free
Census Bureau API key saved as "census_key.txt" in the same folder as
the scripts (https://api.census.gov/data/key_signup.html) - this key
is NOT included in this package for security reasons, you must get
your own, (3) an internet connection, since most early steps download
real government/market data.

Run the scripts from a working copy of E:\device_tariff (not from
inside this final_outputs folder) in this order:

PHASE 2 - build the trade dataset
  1.  common.py                          (just defines shared helpers)
  2.  step1_us_imports_census.py         (needs census_key.txt)
  3.  step2_india_trade_comtrade.py
  4.  step3_checks_and_summary.py
      - these 3 steps can also be run together via run_phase2.bat
      - at this point hs6_codes.csv has the original 48 codes

  Investigation A (why our total is below EPCMD's $782.57M):
  5.  a1_census_vs_comtrade.py
      - MANUAL STEP: hs6_codes.csv was then hand-edited to append 13
        candidate codes (group="Candidate") - see the log's
        "A2 - test 13 candidate 'missing' HS6 codes" section for the
        exact 13 codes and the 2 CSV-quoting bugs that were caught
        and fixed while doing this. After this edit, hs6_codes.csv
        has 61 codes.
  6.  re-run step1_us_imports_census.py and step2_india_trade_comtrade.py
      (now against the 61-code list)
  7.  a2_candidate_codes_compare.py

  Investigation B (like-for-like Jan-Sep 2025 vs 2026):
  8.  b1_census_ytd2025.py
  9.  b2_ytd_2025_vs_2026.py

  Adopting EPCMD's official 151-code definition exactly:
  10. build_epcmd_151_csv.py
  11. b1b_census_fy2425_periods.py
  12. build_epcmd_classification.py   (combines separate CBIC/DGFT
                                        research with a manual correction
                                        on codes 902781/902789 - see log)
  13. c2c_fy2425_reconciliation.py
      (Part 2d of this section was manual HTS-website lookups, no script)

  Finishing Phase 2:
  14. build_final_codes.py            -> final_codes.csv, lab_instruments_codes.csv
  15. d1_census_final.py
  16. d1b_census_backfill_2022_2023.py
  17. d2_comtrade_final.py
  18. e1_build_final_summary.py       -> phase2_final_summary.csv
  19. e2_build_final_checks.py        -> phase2_final_checks.txt

PHASE 3 - link trade to tariffs
  20. f1_build_grouped_codes.py       -> final_codes_grouped.csv
  21. d3_census_monthly.py            (monthly Census data, Jan 2024 onward)
  22. e3_build_monthly_imports.py     -> monthly_imports.csv
  23. g1_fetch_mfn_rates.py           (US MFN rates from hts.usitc.gov)
  24. g2_build_tariff_gap.py          -> phase3_tariff_gap_data.csv
  25. g3_build_excel.py               -> phase3_tariff_gap.xlsx (first pass,
                                        superseded - kept, never overwritten)

  Three fixes before Phase 4:
  26. h1_split_core_codes.py          -> core_device_codes.csv,
                                          pharma_like_codes.csv, hygiene_codes.csv
  27. h2_apply_exemptions.py          (CBP Forced Labor HTS List exemptions)
  28. h3_top15_suppliers.py
  29. h4_competitor_check_and_corrected_rates.py
  30. h5_core_headline_numbers.py
  31. h6_build_excel_v2.py            -> phase3_tariff_gap_v2.xlsx (THE deliverable)

PHASE 4 - scenarios, revenue at risk, exposure score
  32. p1_elasticity.py
  33. p2_download_quantity.py
  34. p2_alpha.py
  35. p3_backtest.py
  36. p4_scenarios.py
  37. p5_revenue_at_risk.py
  38. p6_exposure_score.py
  39. p7_build_excel.py               -> phase4_scenarios.xlsx (v1, superseded)

  Four fixes to the Phase 4 model:
  40. q1_tier_epsilon.py
  41. q2_out_of_sample.py
  42. q3a_fetch_hts10_lines.py
  43. q3b_download_hs10_quantity.py
  44. q3d_download_hs10_duty.py
  45. q3c_alpha_hs10.py
  46. q4_rerun_scenarios.py
  47. q5_build_excel_v2.py            -> phase4_scenarios_v2.xlsx (v2, superseded)

  Final Phase 4 settlement:
  48. r1_phase4_v3.py
  49. r2_build_excel_v3.py            -> phase4_scenarios_v3.xlsx (THE deliverable)

PHASE 5 - company exposure
  50. s1_build_company_data.py        (this one is hand-researched data,
                                        transcribed from company filings -
                                        re-running it just re-writes the
                                        same recorded figures, it does not
                                        re-do the research itself)
  51. s2_company_risk.py
  52. s3_reality_check.py
  53. s4_download_prices.py           (needs yfinance + internet)
  54. s5_event_study.py
  55. s6_build_excel.py               -> phase5_companies.xlsx (THE deliverable)

NOTES
------
- Every script in this project follows a "skip if already downloaded"
  pattern for anything that hits a network API, so re-running an
  already-completed step is safe and fast - it won't re-download or
  overwrite anything that succeeded before.
- Several steps (the EPCMD 151-code transcription, the CBIC/DGFT
  country-tier research, the Section 301 forced-labor country list,
  all of Phase 5's company research) involved real research - reading
  PDFs, web searches - captured as data inside the scripts themselves
  or in separate hand-built CSVs, not something a script can
  regenerate on its own from nothing.
- Nothing in this folder or in E:\device_tariff\data\ was overwritten
  by this packaging step - every version (v1, v2, v3 where they exist)
  is still present in the working copy; final_outputs\ only takes the
  LATEST version of each deliverable.
================================================================
