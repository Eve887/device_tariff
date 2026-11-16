"""
t5_build_trade_deal_csv.py

View B, Part 4 (write-up): turns the research already logged in
logs/step1_progress_log.md into a structured CSV for the Excel
workbook's Trade_deal sheet.

READ-ONLY (this is hand-compiled research, sourced from
raw/viewb_evidence/pib_2224783.html - the official PIB press release
of the US-India Joint Statement, 7 Feb 2026 - cross-checked against
whitehouse.gov and a DPNC Global summary PDF). Writes
data/view_b_trade_deal.csv (new file) only.
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

ROWS = [
    {"topic": "Duty/tariff cuts - medical devices specifically",
     "what_it_says": "Medical devices are NOT individually named in the tariff-cut clause. That clause says only: India will eliminate or reduce tariffs on all U.S. industrial goods and a wide range of U.S. food and agricultural products - with named EXAMPLES given being agricultural (DDGs, sorghum, tree nuts, fruit, soybean oil, wine/spirits), not devices. Medical devices would presumably fall under the broad, unnamed 'industrial goods' bucket, but this is an inference from the document, not a textual statement naming devices.",
     "short_quote": "'eliminate or reduce tariffs on all U.S. industrial goods'",
     "source_section": "Section 1, 'Enhanced Market Access & Tariff Reforms' bullet 1"},
    {"topic": "Non-tariff barriers - medical devices",
     "what_it_says": "India commits to address long-standing barriers to US medical device trade. This is a general, unspecified commitment - it does NOT include the specific 'eliminate restrictive import licensing / quantitative restrictions' language, which the same sentence applies only to ICT goods, not medical devices (several secondary news sources incorrectly ran these together - checked carefully against the primary text, which uses semicolons to separate 3 distinct clauses).",
     "short_quote": "'India agrees to address long-standing barriers to the trade in U.S. medical devices'",
     "source_section": "Section 3, 'Addressing Non-Tariff Barriers' - single sentence, clause 1 of 3"},
    {"topic": "Import licensing - who it actually applies to",
     "what_it_says": "The specific commitment to eliminate restrictive import licensing procedures and quantitative restrictions applies to US Information and Communication Technology (ICT) goods - NOT medical devices, despite how some secondary coverage described it.",
     "short_quote": "'eliminate restrictive import licensing procedures...on...ICT goods'",
     "source_section": "Section 3, same sentence, clause 2 of 3"},
    {"topic": "Product registration / standards acceptance",
     "what_it_says": "Within 6 months of the Agreement taking effect, both countries will determine whether US-developed or international standards (including testing requirements) are acceptable for US exports entering India - but only for 'identified sectors', which are not named in this sentence. Whether medical devices are one of those sectors is not stated explicitly here.",
     "short_quote": "'determine...whether U.S.-developed or international standards...are acceptable...in identified sectors'",
     "source_section": "Section 3, same sentence, clause 3 of 3"},
    {"topic": "Health cess",
     "what_it_says": "Not mentioned anywhere in the document - checked directly against the full extracted text (searched for the literal word 'cess').",
     "short_quote": "(no mention found)",
     "source_section": "N/A - absence confirmed by full-text search"},
    {"topic": "Price controls",
     "what_it_says": "Not mentioned anywhere in the document - checked directly against the full extracted text.",
     "short_quote": "(no mention found)",
     "source_section": "N/A - absence confirmed by full-text search"},
    {"topic": "Broader context - US side of the deal",
     "what_it_says": "The US will apply an 18% reciprocal tariff on a list of Indian goods (textiles/apparel, leather/footwear, plastic/rubber, organic chemicals, home decor, artisanal products, certain machinery) and will remove tariffs on generic pharmaceuticals, gems & diamonds, and aircraft parts entirely - none of these lists name medical devices either way.",
     "short_quote": "'reciprocal tariff rate of 18%...' / 'remove tariff for generic pharmaceuticals...'",
     "source_section": "Section 1, bullets 2-3"},
    {"topic": "Gap between official text and media reporting - flagged, not resolved",
     "what_it_says": "Several secondary sources (Medical Buyer, India Briefing, and others) describe more specific provisions for medical devices - a 'long and staggered phasing schedule', tariff concessions 'with safeguards such as minimum import prices' - none of which appear anywhere in the official Joint Statement text checked here. This may reflect a more detailed annex, a separate briefing, or reported negotiating detail not yet in the public primary-source text. Not confirmed either way - recorded as a gap, not treated as fact.",
     "short_quote": "(not found in the primary source)",
     "source_section": "N/A - comparison across secondary sources, see logs/step1_progress_log.md"},
]


def main():
    with open(DATA_DIR / "view_b_trade_deal.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["topic", "what_it_says", "short_quote", "source_section"])
        w.writeheader()
        w.writerows(ROWS)
    print(f"Wrote data/view_b_trade_deal.csv ({len(ROWS)} rows)")


if __name__ == "__main__":
    main()
