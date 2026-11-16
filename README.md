# Medical Device Tariff Exposure: India → US

How exposed are Indian medical device exporters to US tariffs? This project builds the answer step by step:

1. **Which products count as medical devices?** (a list of trade codes, called HS codes)
2. **How much does India actually sell to the US?** (official US Census and UN Comtrade trade data)
3. **What tariff does India pay, compared with competitors?** (the rate on paper vs. the duty actually paid)
4. **What happens under different future tariff scenarios?** (revenue at risk)
5. **Which listed Indian companies are actually exposed?** (company filings, plus a share-price event study)

A sixth part, **"View B"**, looks at the other direction: what happens if India cuts its own import duties on medical devices as part of a US–India trade deal.

> **Where to start:** open the [`final_outputs/`](final_outputs/) folder. It holds only the final version of each deliverable. [`final_outputs/README.txt`](final_outputs/README.txt) explains every file and the order to run the scripts in.

---

## Key results

All figures are US imports from India, in US dollars, for the **60 core device codes** (medicines, hygiene products and lab instruments are split out separately).

**India's sales to the US fell sharply after the tariffs started**

| Period (Jan–Sep) | US imports from India | Average duty actually paid |
|---|---|---|
| 2024 | $391.3M | 0.07% |
| 2025 | $427.9M | 9.86% |
| 2026 | $335.7M | 14.16% |

- That is a **21.5% fall** from 2025 to 2026. All countries together fell only 4.3% over the same period, so India was hit much harder than average.
- The biggest falls were in consumables (−38.9%), instruments (−27.5%) and electro-diagnostic equipment (−25.8%). Implants grew (+25.8%).

**The tariff gap with competitors**

- In the same period, China's actual duty fell from 20.5% to 13.66%, and Mexico paid about 1.6%. So by 2026, India was paying a **higher** actual rate than China on these devices.

**Revenue at risk under future scenarios** (base case, on about $550M of 2025 exports)

| Scenario | Revenue at risk |
|---|---|
| S1: China exclusions expire | about $0.7M **gain** for India |
| S2: Section 232 tariff at 15%, with exemptions | $58.1M (10.6%) |
| S3: Section 232 tariff at 25% on everything | $61.8M (11.3%) |
| S4: Phased Section 232 (10% in year 1, then 25%) | $24.7M in year 1, then $61.8M |
| S5: US–India deal lowers India's rate by 10 points | about $45.2M **gain** |

Each scenario also has a low and a high estimate in [`phase4_scenarios_v3.xlsx`](final_outputs/phase4_scenarios_v3.xlsx).

> **Important limit:** India's actual fall was larger than the tariff gaps alone can explain, especially for simple disposables and equipment. One possible reason is that US buyers who moved away during the 50% tariff period (Oct 2025 – Feb 2026) did not come back. The scenario totals leave this out, so they are a **lower bound** (the real loss could be bigger).

**Companies checked** (Phase 5): Poly Medicure, Laxmi Dental, Tarsons and Sahajanand Medical Technologies (listed); Translumina via Integris Medtech, and Healthium (not listed, so only filings were used). Meril was excluded because it is private and publishes no usable numbers.

---

## Folder map

| Folder / file | What it holds |
|---|---|
| `final_outputs/` | **The deliverables.** Phase 1 rulebook, Phase 2 trade summary and checks, Phase 3 tariff gap (v2), Phase 4 scenarios (v3), Phase 5 companies, and the full project log. |
| Root `*.py` files | Every script, in the working layout they were run from. The letter at the start shows the phase: `step1–3`, `a`–`f` = Phase 2; `g`, `h` = Phase 3; `p`, `q`, `r` = Phase 4; `s` = Phase 5; `t` = View B. |
| `common.py` | Shared helper functions (safe file saving, logging, downloads with retries). |
| `hs6_codes.csv` | The starting list of HS6 product codes. |
| `run_phase2.bat` | Runs the first three Phase 2 steps in order on Windows. |
| `data/` | Every intermediate and output table. **Earlier versions are kept on purpose** (`_v2`, `_v3`, `_48codes_backup`) so you can see how the numbers changed after each fix. The latest version is always the highest number. |
| `data/view_b_*` | View B: India's import duties, landed costs and trade-deal scenarios. |
| `logs/` | Text logs of every download run. `logs/step1_progress_log.md` is the **complete** project log, including View B. (The copy in `final_outputs/` was taken before View B was added.) |
| `raw/` | Small source files: US tariff (HTS) rates, Census variable list, daily share prices used in the event study, page-text extracts from company filings and trade-deal documents. |

### What is not in this repository, and why

- **The Census API key** (`census_key.txt`) is private. To re-run the download scripts, get your own free key from <https://api.census.gov/data/key_signup.html> and save it as `census_key.txt` next to the scripts.
- **Bulk raw API answers** (about 2,000 small JSON files from the US Census and UN Comtrade). The scripts download these again automatically, and the cleaned results are already in `data/`.
- **PDFs** (company DRHPs, investor presentations, call transcripts, the EPCMD code list, the CBP forced-labour HTS list, a law-firm FAQ). These are other organisations' documents and are publicly available from their original sources. The page-text extracts actually used are in `raw/phase5_evidence/` and `raw/viewb_evidence/`.

---

## How to re-run it

1. Install Python 3 and the packages: `pip install -r requirements.txt`
2. Add your own `census_key.txt` (see above).
3. Run the scripts in the order listed in [`final_outputs/README.txt`](final_outputs/README.txt). Each download script skips anything it has already downloaded, so it is safe to stop and restart.

Note: some steps were real research (reading PDFs, checking official tariff schedules, transcribing company figures). Their results are stored inside the scripts or in hand-built CSV files. A script can rebuild the tables from them, but it cannot redo the research itself.

---

## Data sources

- **US Census Bureau** International Trade API: US imports by country, HS6/HS10 code, value, quantity and calculated duty
- **UN Comtrade**: India's exports and imports
- **USITC Harmonized Tariff Schedule** (hts.usitc.gov): US MFN (normal) tariff rates
- **US CBP**: Forced Labor HTS list; USTR / White House tariff notices for country rates
- **EPCMD** (Export Promotion Council for Medical Devices): the official 151-code medical device definition and the $782.57M FY2024-25 export figure used as a cross-check
- **CBIC / ICEGATE / DGFT**: Indian import duty rates (View B)
- **PIB** (Press Information Bureau): US–India trade framework announcement (View B)
- **Company filings**: DRHPs, annual reports, investor presentations and earnings-call transcripts
- **Yahoo Finance** (via `yfinance`): daily share prices and the NIFTY 50 index for the event study

---

## License

MIT. See [`LICENSE`](LICENSE).
