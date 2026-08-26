# Stock Relative-Strength Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task using **inline execution only**. Do not use subagent-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, point-in-time stock relative-strength dataset for the fixed 20-stock T1 basket for later independent validation against the locked 218 T1 trades.

**Architecture:** The Portfolio Advisor has already made the methodology decision that Streak cannot faithfully test this exact feature because Streak can backtest conditions across a basket but does not historically calculate same-date cross-sectional percentile/rank of each stock against the basket. Therefore this plan has no Streak-capability decision step. Luna only implements the approved custom-data path: download the fixed 20 stocks, calculate 21/63/126-session returns, rank all 20 stocks cross-sectionally on complete dates, compute the locked 30/40/30 composite, validate every invariant, and export auditable artifacts. Trade P&L is intentionally absent from this phase.

**Tech Stack:** Python 3.11+, pandas, numpy, yfinance, pytest.

**Spec:** GitHub Issue #5 — `https://github.com/krishna916/Financial/issues/5`

## Portfolio-Advisor Methodology Decision — DO NOT RE-EVALUATE

```text
Validation source: CUSTOM_REQUIRED
Reason: the feature is historical same-day cross-sectional RS percentile/rank
        across a multi-stock comparison universe. Streak does not faithfully
        expose that feature as a historical strategy condition.
```

Luna must **not** research whether Streak can do it, substitute a superficially similar Streak indicator, or make a new methodology choice. The general project rule remains: the Portfolio Advisor prefers Streak whenever Streak can faithfully test the exact hypothesis, and makes that choice before delegating implementation.

## Global Constraints

- Data preparation only; do not inspect or join T1 trade returns/P&L.
- Fixed universe: exactly the 20 stocks in Issue #5.
- Historical window: `2022-01-01` through `2026-08-25` inclusive.
- Daily data; `auto_adjust=False`.
- Preserve `Close` and `Adj Close`; use `Adj Close` consistently for this proxy RS calculation and document that vendor/corporate-action adjustment is a limitation to be spot-checked before live use.
- Fixed session lookbacks: 21, 63, 126.
- Percentiles: `rank(method="average", pct=True, ascending=True) * 100`.
- Composite: `0.30 * RS21 + 0.40 * RS63 + 0.30 * RS126`.
- Research-safe dates require all 20 stocks.
- Composite rank 1 = strongest.
- Deterministic exact-score ties: sort `Symbol` ascending, then descending rank with `method="first"`.
- Statuses: `PREFERRED >= 80`, `VALID >= 70 and < 80`, `BELOW_VALID < 70`.
- No interpolation, synthetic dates, future rows, alternate securities/indicators, tuning, or result-driven exceptions.
- Do not modify existing sector-leadership or T1-validation methodology.

---

## Target File Map

```text
Swing Trading/research/swing/stock_rs/
├── build_stock_rs.py
├── stock_ticker_config.csv
├── requirements.txt
├── README.md
├── tests/
│   └── test_stock_rs.py
└── output/
    ├── stock_rs_daily.csv
    ├── stock_rs_summary.csv
    └── stock_rs_validation.csv
```

### Task 1: Lock universe and dependencies

Create `requirements.txt` containing only:

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

Add a pytest asserting exact mapping equality, 20 unique symbols, and 20 unique tickers. Run it, require PASS, commit.

---

### Task 2: Implement exact session-return and status logic with TDD

Create `build_stock_rs.py` and tests for:

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

Test exact shift behavior at rows 21/63/126 and boundaries 80/70. Run RED before implementation and GREEN afterward. Commit.

---

### Task 3: Implement full-20 cross-sectional ranking

Implement `calculate_daily_stock_rs(frame, expected_count=20)`.

Required input:

```text
Date,Symbol,Yahoo_Ticker,Close,Adj_Close,Ret21,Ret63,Ret126
```

TDD requirements:

- synthetic 20-stock date with strictly increasing returns: strongest percentile/composite = 100, rank = 1; weakest percentile = 5, rank = 20;
- 19-stock date is excluded;
- composite exactly equals 30/40/30 recomputation.

Implementation order:

1. drop rows missing any horizon return;
2. reject duplicate `(Date,Symbol)`;
3. retain only dates with exactly 20 distinct symbols;
4. rank each horizon cross-sectionally using `rank(method="average", pct=True, ascending=True)*100`;
5. compute 30/40/30 Composite_RS;
6. deterministic descending Composite_Rank;
7. set `Stock_Count=20`, `Is_Full_Universe=True`;
8. assign RS_Status;
9. sort `Date,Composite_Rank`.

Run tests and commit.

---

### Task 4: Implement Yahoo download/normalization

Implement one-ticker-at-a-time download:

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

TDD must cover single-level columns, one-ticker MultiIndex columns, and missing `Adj Close` rejection.

Rules:

- require both `Close` and `Adj Close`;
- timezone-naive dates;
- ascending sort;
- reject duplicate dates;
- do not forward-fill prices;
- record missing values; production build fails if usable required prices are missing.

Run tests and commit.

---

### Task 5: Build end-to-end outputs

For each configured stock: download → normalize → raw validation → calculate returns → append. If any required stock fails, stop before producing a research-safe primary output.

After all 20 histories exist, concatenate and run cross-sectional ranking.

Validate:

```text
no duplicate (Date,Symbol)
no missing required values
all Stock_Count == 20
all Is_Full_Universe == true
each date exactly 20 symbols
ranks exactly 1..20
all horizon percentiles and Composite_RS in (0,100]
statuses only PREFERRED/VALID/BELOW_VALID
Composite_RS equals 30/40/30 recomputation
rank 1 score >= rank 20 score on every date
```

Export `stock_rs_daily.csv` columns exactly:

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

Build `stock_rs_summary.csv` per symbol with valid ranked days, status counts, earliest/latest ranked date, mean/median Composite_RS.

Build `stock_rs_validation.csv` per symbol with download status, raw rows, earliest/latest raw date, duplicate-date count, missing Close count, missing Adj_Close count.

---

### Task 6: Add end-to-end invariant tests

Add deterministic tests for duplicate-row rejection, invalid rank set, invalid universe count/flag, invalid status, and summary count reconciliation.

Run:

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" -v
```

Require zero failures and commit.

---

### Task 7: README and reliability caveats

README must explicitly state:

```text
Streak is preferred whenever it can faithfully express the exact hypothesis.
For this experiment the Portfolio Advisor already determined Streak cannot
perform the required historical same-day cross-sectional universe ranking,
so the custom dataset path was selected before implementation.
```

Document methodology and limitations:

- fixed 20-stock universe is a proxy, not final Nifty 500 implementation;
- Yahoo/yfinance may differ from exchange/broker/Streak histories, including corporate-action adjustments;
- any promising result should be spot-checked against trusted market/broker data before live use;
- no T1 outcome data was used;
- future hypotheses should use Streak when exactly representable.

Document commands:

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" -v
python "Swing Trading/research/swing/stock_rs/build_stock_rs.py"
```

Commit.

---

### Task 8: Final verification

Use `superpowers:verification-before-completion`.

- Run all stock-RS tests fresh; require zero failures.
- Run production build fresh; require exit 0.
- Independently assert non-empty outputs, no duplicates, full-20 dates only, ranks 1..20, 20 summary rows, 20 validation rows, all downloads OK, and status-count reconciliation.
- Print per-stock raw row counts/date ranges and flag anomalies.
- Spot-check at least three date/symbol combinations by recomputing the horizon returns, same-day percentiles and Composite_RS.
- Commit outputs only after checks pass.
- Open PR referencing Issue #5.

PR body must include:

```text
Portfolio Advisor methodology decision: CUSTOM_REQUIRED
Test command and exact pass count
Build command and exit result
Python/yfinance/pandas versions
20/20 download success status
Raw and ranked date ranges
Primary output row count/ranked-date count
Any vendor/calendar/corporate-action anomalies
Generated artifact paths
Explicit statement: no T1 trade P&L was inspected
```

## Completion Rule

Luna's responsibility is implementation and verification only. The Portfolio Advisor retains methodology responsibility, including Streak-vs-custom selection and whether the resulting signal has enough evidence to affect Swing Strategy V1.