"""
s4_download_prices.py

Phase 5, Part 6, step 1: download daily closing prices via yfinance
for the 4 listed companies' tickers plus Nifty 50 and Nifty
Healthcare, spanning well before the earliest event (7 Aug 2025) to
well after the latest (24 Jul 2026), with enough lead-in for each
event's 120-trading-day estimation window (ending 10 trading days
before the event - the earliest event's estimation window starts
roughly 130 trading days, i.e. ~6-7 calendar months, before 7 Aug
2025).

SMT (listed only 23 Oct 2026) and Translumina (not separately listed,
no ticker) are excluded here - SMT has no price history for ANY of
the 5 events (all predate its listing), and Translumina has no ticker
at all. This is noted explicitly rather than silently producing empty
rows.

Saved as raw evidence (one CSV per ticker, never overwritten once
downloaded - skip if exists, same checkpoint pattern as every other
download in this project) to raw/phase5_prices/.
"""

import time
from pathlib import Path

import yfinance as yf

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "raw" / "phase5_prices"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TICKERS = {
    "POLYMED": "POLYMED.NS",
    "LAXMIDENTL": "LAXMIDENTL.NS",
    "TARSONS": "TARSONS.NS",
    "NIFTY50": "^NSEI",
    "NIFTY_HEALTHCARE": "NIFTY_HEALTHCARE.NS",
}

START = "2025-01-01"  # well before the earliest event's estimation window
END = "2026-11-14"    # through the day before "today" in this project (2026-11-15)


def main():
    for name, ticker in TICKERS.items():
        out_file = OUT_DIR / f"{name}.csv"
        if out_file.exists():
            print(f"{name} ({ticker}): already downloaded, skipping")
            continue
        print(f"Downloading {name} ({ticker})...")
        df = yf.download(ticker, start=START, end=END, progress=False, auto_adjust=False)
        if df is None or df.empty:
            print(f"  FAILED or empty for {ticker}")
            continue
        df.to_csv(out_file)
        print(f"  {len(df)} rows -> {out_file}")
        time.sleep(1.0)


if __name__ == "__main__":
    main()
