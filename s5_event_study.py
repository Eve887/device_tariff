"""
s5_event_study.py

Phase 5, Part 6, step 2: event study.

For each stock (POLYMED, LAXMIDENTL, TARSONS - SMT/Translumina
excluded, see log) and each event date, estimates the stock's market
model (simple OLS: R_stock = alpha + beta*R_nifty50) over the 120
trading days ending 10 trading days before the event (the "estimation
window"), then computes the abnormal return (actual - expected, using
the estimated alpha/beta applied to Nifty 50's actual return each day)
cumulated over two event windows: [day 0, day +1] and [day -1, day +5].
"Day 0" is the event date itself if it was a trading day, otherwise
the next trading day on or after it (standard event-study convention
for weekend/holiday announcements - only 7 Feb 2026, a Saturday, needs
this adjustment among the 5 dates given).

t-statistic for each CAR uses the standard event-study test (MacKinlay
1997): t = CAR / (sigma_epsilon * sqrt(L)), where sigma_epsilon is the
residual standard deviation from the estimation-window regression and
L is the number of trading days in the event window (2 or 7). 5%
two-tailed significance uses the normal-approximation critical value
of 1.96 (the estimation window has 120 observations, so the normal
approximation to the t-distribution is standard practice here).

Nifty Healthcare is NOT included as a benchmark - see log for why
(Yahoo Finance has only 1 day of history for that index; direct
NSE/niftyindices attempts returned 404/503 and were not pursued
further).

READ-ONLY against raw/phase5_prices/*.csv. Writes
data/phase5_event_study.csv (new file).
"""

import csv
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PRICE_DIR = HERE / "raw" / "phase5_prices"
DATA_DIR = HERE / "data"

STOCKS = ["POLYMED", "LAXMIDENTL", "TARSONS"]  # SMT/Translumina excluded - see log

EVENTS = [
    ("2025-08-07", "25% tariff announced"),
    ("2025-08-27", "50% tariff announced"),
    ("2026-02-07", "Oil tariff removed"),
    ("2026-02-20", "Supreme Court ruling"),
    ("2026-07-24", "Section 301 starts"),
]

ESTIMATION_WINDOW_LEN = 120
GAP_BEFORE_EVENT = 10  # estimation window ends this many trading days before day 0


def load_returns(name):
    df = pd.read_csv(PRICE_DIR / f"{name}.csv", skiprows=[1, 2], index_col=0, parse_dates=True)
    df = df.sort_index()
    close = df["Close"].astype(float)
    ret = close.pct_change().dropna()
    return ret


def trading_day_on_or_after(index, date):
    """Returns the integer position in `index` of the first trading day
    on or after `date`, or None if none exists."""
    pos = index.searchsorted(date)
    if pos >= len(index):
        return None
    return pos


def event_study_for_stock(stock_ret, mkt_ret, event_date_str):
    event_date = pd.Timestamp(event_date_str)
    common_idx = stock_ret.index.intersection(mkt_ret.index)
    stock_ret = stock_ret.reindex(common_idx)
    mkt_ret = mkt_ret.reindex(common_idx)

    day0_pos = trading_day_on_or_after(common_idx, event_date)
    if day0_pos is None:
        return None

    est_end = day0_pos - GAP_BEFORE_EVENT
    est_start = est_end - ESTIMATION_WINDOW_LEN
    if est_start < 0:
        return {"error": f"not enough price history before {event_date_str} for a full 120-day estimation window"}

    x = mkt_ret.iloc[est_start:est_end].values
    y = stock_ret.iloc[est_start:est_end].values
    X = np.column_stack([np.ones_like(x), x])
    beta_hat, residuals, rank, sv = np.linalg.lstsq(X, y, rcond=None)
    alpha, beta = beta_hat
    fitted = X @ beta_hat
    resid = y - fitted
    sigma_eps = resid.std(ddof=2)  # ddof=2 for 2 estimated parameters

    results = {}
    windows = {"day0_to_1": (0, 1), "day-1_to_5": (-1, 5)}
    for win_name, (w_start, w_end) in windows.items():
        idx_start = day0_pos + w_start
        idx_end = day0_pos + w_end
        if idx_start < 0 or idx_end >= len(common_idx):
            results[win_name] = {"car": None, "t_stat": None, "n_days": None, "significant_5pct": None}
            continue
        L = idx_end - idx_start + 1
        car = 0.0
        for i in range(idx_start, idx_end + 1):
            actual = stock_ret.iloc[i]
            expected = alpha + beta * mkt_ret.iloc[i]
            car += (actual - expected)
        t_stat = car / (sigma_eps * np.sqrt(L)) if sigma_eps > 0 else None
        sig = (abs(t_stat) > 1.96) if t_stat is not None else None
        results[win_name] = {"car": car, "t_stat": t_stat, "n_days": L, "significant_5pct": sig}

    return {"alpha": alpha, "beta": beta, "sigma_eps": sigma_eps,
            "n_est_obs": est_end - est_start, "day0_date": str(common_idx[day0_pos].date()),
            "windows": results}


def main():
    mkt_ret = load_returns("NIFTY50")
    rows = []
    for stock in STOCKS:
        stock_ret = load_returns(stock)
        for event_date, event_label in EVENTS:
            result = event_study_for_stock(stock_ret, mkt_ret, event_date)
            if result is None:
                rows.append({"stock": stock, "event_date": event_date, "event_label": event_label,
                             "error": "no trading day found on or after event date in available price history"})
                continue
            if "error" in result:
                rows.append({"stock": stock, "event_date": event_date, "event_label": event_label,
                             "error": result["error"]})
                continue
            for win_name, win in result["windows"].items():
                rows.append({
                    "stock": stock, "event_date": event_date, "event_label": event_label,
                    "day0_actual_trading_date": result["day0_date"],
                    "event_window": win_name,
                    "market_model_alpha": round(result["alpha"], 6),
                    "market_model_beta": round(result["beta"], 4),
                    "n_estimation_obs": result["n_est_obs"],
                    "car_pct": round(win["car"] * 100, 3) if win["car"] is not None else None,
                    "t_stat": round(win["t_stat"], 3) if win["t_stat"] is not None else None,
                    "n_days_in_window": win["n_days"],
                    "significant_at_5pct": win["significant_5pct"],
                    "error": None,
                })

    cols = ["stock", "event_date", "event_label", "day0_actual_trading_date", "event_window",
            "market_model_alpha", "market_model_beta", "n_estimation_obs",
            "car_pct", "t_stat", "n_days_in_window", "significant_at_5pct", "error"]
    with open(DATA_DIR / "phase5_event_study.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote data/phase5_event_study.csv ({len(rows)} rows)\n")

    for r in rows:
        if r.get("error"):
            print(f"{r['stock']:<12}{r['event_date']:<12}{r['event_label']:<25}ERROR: {r['error']}")
        else:
            sig = "SIGNIFICANT" if r["significant_at_5pct"] else "not significant"
            print(f"{r['stock']:<12}{r['event_date']:<12}{r['event_label']:<25}{r['event_window']:<14}"
                  f"CAR={r['car_pct']:>7}%  t={r['t_stat']:>7}  {sig}")


if __name__ == "__main__":
    main()
