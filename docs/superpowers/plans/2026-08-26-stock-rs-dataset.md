# Stock Relative-Strength Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task using **inline execution only**. Do not use subagent-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, point-in-time stock relative-strength dataset for the fixed 20-stock T1 basket for later independent validation against the locked 218 T1 trades.

**Architecture:** The Portfolio Advisor has already decided that Streak cannot faithfully test this exact feature because the feature requires historical same-date cross-sectional percentile/rank of each stock against the comparison basket. Luna does not decide Streak capability. Luna only implements the approved custom-data path: download the fixed 20 stocks, calculate 21/63/126-session returns, rank all 20 stocks cross-sectionally on complete dates, compute the locked 30/40/30 composite, validate invariants, and export auditable artifacts. T1 outcome data is excluded from this phase.

**Tech Stack:** Python 3.11+, pandas, numpy, yfinance, pytest.

**Spec:** GitHub Issue #5 — `https://github.com/krishna916/Financial/issues/5`

## Methodology Decision — LOCKED BY PORTFOLIO ADVISOR

```text
Validation source: CUSTOM_REQUIRED
Why: Streak supports applying/backtesting stock-specific conditions across a basket,
     but does not provide the historical same-date cross-sectional universe ranking
     required by this RS hypothesis.
```

Luna must not research or revisit this decision, substitute RSI/ROC/Momentum/SMA, or make any new methodology choice.

General project rule: **Portfolio Advisor chooses Streak whenever Streak can faithfully represent the exact hypothesis; custom code is used only when it cannot.**

## Global Constraints

- Data preparation only; never inspect/join T1 trade returns or P&L.
- Fixed universe: exactly the 20 stocks in Issue #5.
- Historical period: `2022-01-01` through `2026-08-25` inclusive.
- Daily data; `auto_adjust=False`.
- Keep `Close` and `Adj Close`; use `Adj Close` consistently for this proxy RS calculation. Document vendor/corporate-action adjustment as a limitation to spot-check before live use.
- Session lookbacks: 21, 63, 126.
- Percentile: `rank(method="average", pct=True, ascending=True) * 100`.
- Composite: `0.30 * RS21 + 0.40 * RS63 + 0.30 * RS126`.
- Only dates with all 20 valid stocks are research-safe.
- Composite rank 1 = strongest.
- Exact-score tie handling: sort Symbol ascending, then rank descending with `method="first"`.
- Statuses: `PREFERRED >= 80`, `VALID >= 70 and < 80`, `BELOW_VALID < 70`.
- No interpolation, synthetic trading dates, future rows, alternate securities, extra indicators, tuning, or result-driven exceptions.
- Do not modify existing sector-leadership/T1 methodology.

## Files

```text
Swing Trading/research/swing/stock_rs/
├── build_stock_rs.py
├── stock_ticker_config.csv
├── requirements.txt
├── README.md
├── tests/test_stock_rs.py
└── output/
    ├── stock_rs_daily.csv
    ├── stock_rs_summary.csv
    └── stock_rs_validation.csv
```

### Task 1: Lock universe and dependencies

Create `requirements.txt`:

```text
yfinance
pandas
numpy
pytest
```

Create `stock_ticker_config.csv` exactly:

```csv
Symbol,Yahoo_Ticker
HDFCBANK,HDFCBANK.NS
ICICIBANK,ICICIBANK.NS
SBIN,SBIN.NS
BAJFINANCE,BAJFINANCE.NS
TCS,TCS.NS
INFY,INFY.NS
M&M,M&M.NS
MARUTI,MARUTI.NS
LT,LT.NS
RELIANCE,RELIANCE.NS
ONGC,ONGC.NS
ITC,ITC.NS
HINDUNILVR,HINDUNILVR.NS
SUNPHARMA,SUNPHARMA.NS
APOLLOHOSP,APOLLOHOSP.NS
BHARTIARTL,BHARTIARTL.NS
TATASTEEL,TATASTEEL.NS
POWERGRID,POWERGRID.NS
ADANIENT,ADANIENT.NS
ULTRACEMCO,ULTRACEMCO.NS
```

Write pytest asserting exact mapping equality, exactly 20 unique symbols and tickers. Run, require PASS, commit.

---

### Task 2: Implement session returns and status rules with TDD

Create `build_stock_rs.py` functions:

```python
def calculate_returns(frame):
    result = frame.copy()
    result["Ret21"] = result["Adj_Close"] / result["Adj_Close"].shift(21) - 1.0
    result["Ret63"] = result["Adj_Close"] / result["Adj_Close"].shift(63) - 1.0
    result["Ret126"] = result["Adj_Close"] / result["Adj_Close"].shift(126) - 1.0
    return result


def assign_rs_status(score):
    if score >= 80: return "PREFERRED"
    if score >= 70: return "VALID"
    return "BELOW_VALID"
```

Before implementation, tests must cover exact session shifts at 21/63/126 and status boundaries 80/70. Verify RED, implement, verify GREEN, commit.

---

### Task 3: Implement full-20 cross-sectional RS

Implement `calculate_daily_stock_rs(frame, expected_count=20)` over columns:

```text
Date,Symbol,Yahoo_Ticker,Close,Adj_Close,Ret21,Ret63,Ret126
```

Tests before implementation:

1. one synthetic 20-stock date with increasing returns → strongest horizon percentile/composite 100 and rank 1; weakest percentile 5 and rank 20;
2. 19-stock date excluded;
3. composite exactly equals 30/40/30 calculation.

Implementation sequence:

1. reject duplicate `(Date,Symbol)`;
2. drop rows missing any horizon return;
3. retain dates with exactly 20 distinct symbols;
4. calculate 21/63/126 percentiles cross-sectionally with the locked percentile rule;
5. calculate Composite_RS 30/40/30;
6. deterministic descending Composite_Rank;
7. set `Stock_Count=20`, `Is_Full_Universe=True`;
8. assign RS_Status;
9. sort `Date,Composite_Rank`.

Run tests, require GREEN, commit.

---

### Task 4: Yahoo download and normalization

Download each ticker separately:

```python
yf.download(
    ticker,
    start="2022-01-01",
    end="2026-08-26",
    interval="1d",
    auto_adjust=False,
    progress=False,
    actions=False,
)
```

Normalize to:

```text
Date,Symbol,Yahoo_Ticker,Close,Adj_Close
```

Tests must cover single-level columns, one-ticker MultiIndex, and rejection when `Adj Close` is missing.

Rules:

- require Close and Adj Close;
- timezone-naive dates;
- sort ascending;
- reject duplicate dates;
- do not forward-fill prices;
- record missing values and fail the research-safe build if required prices are missing.

Run tests, commit.

---

### Task 5: Build and validate final artifacts

For every configured stock: download → normalize → raw validation → calculate returns → append. If any required stock fails, stop before producing research-safe primary output.

After all 20 histories exist, concatenate and calculate cross-sectional RS.

Validate:

```text
no duplicate (Date,Symbol)
no missing required values
all Stock_Count == 20
all Is_Full_Universe == true
each ranked date exactly 20 symbols
Composite_Rank set exactly 1..20 each date
percentiles and Composite_RS in (0,100]
RS_Status only PREFERRED/VALID/BELOW_VALID
Composite_RS equals 30/40/30 recomputation
rank 1 score >= rank 20 score
```

Export `stock_rs_daily.csv`:

```text
Date
Symbol
Yahoo_Ticker
Close
Adj_Close
Ret21
Ret63
Ret126
RS21_Percentile
RS63_Percentile
RS126_Percentile
Composite_RS
Composite_Rank
Stock_Count
Is_Full_Universe
RS_Status
```

Export `stock_rs_summary.csv` per symbol:

```text
Symbol,Yahoo_Ticker,Valid_Ranked_Days,Preferred_Days,Valid_Days,
Below_Valid_Days,Earliest_Ranked_Date,Latest_Ranked_Date,
Mean_Composite_RS,Median_Composite_RS
```

Export `stock_rs_validation.csv` per symbol:

```text
Symbol,Yahoo_Ticker,Download_Status,Raw_Rows,Earliest_Raw_Date,
Latest_Raw_Date,Duplicate_Date_Count,Missing_Close_Count,Missing_Adj_Close_Count
```

Require 20/20 `Download_Status == OK`.

---

### Task 6: Deterministic invariant tests

Add tests for duplicate Date/Symbol rejection, invalid rank set, invalid universe count/flag, invalid status, and summary status-count reconciliation.

Run:

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" -v
```

Require zero failures, commit.

---

### Task 7: README

README must say explicitly:

```text
Streak is preferred when it can faithfully express the exact hypothesis.
For this experiment, the Portfolio Advisor already determined Streak cannot
perform historical same-day cross-sectional universe ranking, so custom data
was selected before Luna execution.
```

Also document methodology, fixed-20 proxy limitation, Yahoo/vendor/corporate-action differences from Streak/exchange data, requirement to spot-check promising results against trusted data before live deployment, and that no T1 outcome data was used.

Document run commands:

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" -v
python "Swing Trading/research/swing/stock_rs/build_stock_rs.py"
```

Commit.

---

### Task 8: Verification and PR

Use `superpowers:verification-before-completion`.

Freshly run full tests and production build. Independently verify outputs non-empty, no duplicates, full-20 dates only, exact ranks 1..20, 20 validation rows/all downloads OK, 20 summary rows, and status-count reconciliation.

Print raw row counts/date ranges for all stocks and flag vendor/calendar anomalies. Spot-check at least three symbol/dates by independently recomputing Ret21/63/126, same-day percentile ranks, and Composite_RS.

Commit generated outputs only after verification. Open a PR referencing Issue #5 with exact test pass count, build result, Python/yfinance/pandas versions, 20/20 download status, raw/ranked date ranges, output counts, anomalies, artifacts, and explicit statement that no T1 trade P&L was inspected.

## Completion Rule

Luna implements and verifies only. The Portfolio Advisor owns methodology decisions, including Streak-vs-custom selection and later interpretation of whether stock RS improves Swing Strategy V1.