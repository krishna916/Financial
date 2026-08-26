# Stock Relative-Strength Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task using **inline execution only**. Do not use subagent-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, point-in-time stock relative-strength dataset for the fixed 20-stock T1 basket for later independent validation against the locked 218 T1 trades.

**Architecture:** The Portfolio Advisor has already made the methodology decision that Streak cannot faithfully test this exact feature because Streak can backtest conditions across a basket but does not historically calculate same-date cross-sectional percentile/rank of each stock against the basket. Therefore this plan has no Streak-capability decision step. Luna only implements the approved custom-data path: download the fixed 20 stocks, calculate point-in-time 21/63/126-session returns, rank all 20 stocks cross-sectionally on complete dates, compute the locked 30/40/30 composite, validate every invariant, and export auditable artifacts. Trade P&L is intentionally absent from this phase.

**Tech Stack:** Python 3.11+, pandas, numpy, yfinance, pytest.

**Spec:** GitHub Issue #5 — `https://github.com/krishna916/Financial/issues/5`

## Portfolio-Advisor Methodology Decision — DO NOT RE-EVALUATE

The decision for this experiment is already locked:

```text
Validation source: CUSTOM_REQUIRED
Reason: the feature is historical same-day cross-sectional RS percentile/rank
        across a multi-stock comparison universe. Streak does not faithfully
        expose that feature as a historical strategy condition.
```

Luna must **not**:

- research whether Streak can do it;
- replace the feature with RSI, ROC, momentum, SMA, or another single-stock Streak indicator;
- stop the task because it finds a superficially similar Streak feature;
- make a new methodological decision.

General project rule remains: **the Portfolio Advisor should prefer Streak whenever Streak can faithfully test the exact hypothesis.** That decision is made before a Luna implementation task is written.

## Global Constraints

- This task is **data preparation only**. Do not inspect or join T1 trade returns/P&L.
- Fixed universe: exactly the 20 stocks in Issue #5.
- Historical window: `2022-01-01` through `2026-08-25` inclusive.
- Download settings: daily, `auto_adjust=False`.
- Preserve raw `Close`.
- For RS, use a **point-in-time price series that is safe from future corporate-action leakage**. Do not blindly use Yahoo's current `Adj Close` across historical dates because later splits/dividends can revise past values using future information.
- Preferred implementation: use raw `Close`, but explicitly detect/handle stock splits from Yahoo `actions=True` / split data so a historical split does not create a false return jump. Dividends need not be reinvested for this price-momentum proxy.
- If the implementation instead uses `Adj Close`, it must first document and test that the adjustment is point-in-time-safe for the historical date being scored. Do not assume this.
- Fixed session lookbacks: 21, 63, 126.
- Fixed percentile rule: `rank(method="average", pct=True, ascending=True) * 100`.
- Fixed composite: `0.30 * RS21 + 0.40 * RS63 + 0.30 * RS126`.
- Research-safe dates require all 20 stocks.
- Composite rank 1 = strongest.
- Exact Composite_RS ties are deterministic: sort `Symbol` ascending first, then use `rank(method="first", ascending=False)`.
- Locked status labels: `PREFERRED >= 80`, `VALID >= 70 and < 80`, `BELOW_VALID < 70`.
- No interpolation, forward-filled synthetic prices, future data, alternate securities, alternate indicators, parameter tuning, or result-driven exceptions.
- Do not modify existing sector-leadership or T1-validation methodology.
- Execution mode is inline only.

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

---

### Task 1: Lock the experiment universe and dependencies

**Files:**
- Create: `Swing Trading/research/swing/stock_rs/requirements.txt`
- Create: `Swing Trading/research/swing/stock_rs/stock_ticker_config.csv`
- Create: `Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py`

- [ ] **Step 1: Create `requirements.txt` exactly**

```text
yfinance
pandas
numpy
pytest
```

- [ ] **Step 2: Create `stock_ticker_config.csv` exactly**

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

- [ ] **Step 3: Write exact-universe test**

```python
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
EXPECTED = {
    "HDFCBANK":"HDFCBANK.NS","ICICIBANK":"ICICIBANK.NS","SBIN":"SBIN.NS",
    "BAJFINANCE":"BAJFINANCE.NS","TCS":"TCS.NS","INFY":"INFY.NS",
    "M&M":"M&M.NS","MARUTI":"MARUTI.NS","LT":"LT.NS","RELIANCE":"RELIANCE.NS",
    "ONGC":"ONGC.NS","ITC":"ITC.NS","HINDUNILVR":"HINDUNILVR.NS",
    "SUNPHARMA":"SUNPHARMA.NS","APOLLOHOSP":"APOLLOHOSP.NS",
    "BHARTIARTL":"BHARTIARTL.NS","TATASTEEL":"TATASTEEL.NS",
    "POWERGRID":"POWERGRID.NS","ADANIENT":"ADANIENT.NS","ULTRACEMCO":"ULTRACEMCO.NS",
}

def test_stock_config_is_exact_fixed_twenty_stock_universe():
    df = pd.read_csv(BASE_DIR / "stock_ticker_config.csv", dtype=str)
    assert df.columns.tolist() == ["Symbol", "Yahoo_Ticker"]
    assert len(df) == 20
    assert df["Symbol"].is_unique
    assert df["Yahoo_Ticker"].is_unique
    assert dict(zip(df["Symbol"], df["Yahoo_Ticker"])) == EXPECTED
```

- [ ] **Step 4: Run test**

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py::test_stock_config_is_exact_fixed_twenty_stock_universe" -v
```

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/stock_rs/requirements.txt" \
        "Swing Trading/research/swing/stock_rs/stock_ticker_config.csv" \
        "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py"
git commit -m "research: lock stock RS universe"
```

---

### Task 2: Implement point-in-time session returns and status logic with TDD

**Files:**
- Create: `Swing Trading/research/swing/stock_rs/build_stock_rs.py`
- Modify: `Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py`

**Interfaces:**
- `calculate_returns(frame: pd.DataFrame) -> pd.DataFrame`
- `assign_rs_status(composite_rs: float) -> str`

The normalized frame must expose `RS_Price`, the already-sanitized point-in-time price series used for momentum returns.

- [ ] **Step 1: Add failing return/status tests**

```python
import math
import pandas as pd
import pytest
from research.swing.stock_rs.build_stock_rs import calculate_returns, assign_rs_status

def test_calculate_returns_uses_exact_session_shifts():
    df = pd.DataFrame({"RS_Price": [100.0 + i for i in range(140)]})
    result = calculate_returns(df)
    assert pd.isna(result.loc[20, "Ret21"])
    assert math.isclose(result.loc[21, "Ret21"], 121.0 / 100.0 - 1.0)
    assert math.isclose(result.loc[63, "Ret63"], 163.0 / 100.0 - 1.0)
    assert math.isclose(result.loc[126, "Ret126"], 226.0 / 100.0 - 1.0)

@pytest.mark.parametrize(("score","expected"), [
    (100.0,"PREFERRED"),(80.0,"PREFERRED"),(79.999,"VALID"),
    (70.0,"VALID"),(69.999,"BELOW_VALID"),(5.0,"BELOW_VALID")])
def test_assign_rs_status_uses_locked_v1_thresholds(score, expected):
    assert assign_rs_status(score) == expected
```

- [ ] **Step 2: Verify RED**

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" -v
```

- [ ] **Step 3: Implement minimal functions**

```python
def calculate_returns(frame):
    result = frame.copy()
    result["Ret21"] = result["RS_Price"] / result["RS_Price"].shift(21) - 1.0
    result["Ret63"] = result["RS_Price"] / result["RS_Price"].shift(63) - 1.0
    result["Ret126"] = result["RS_Price"] / result["RS_Price"].shift(126) - 1.0
    return result

def assign_rs_status(score):
    if score >= 80: return "PREFERRED"
    if score >= 70: return "VALID"
    return "BELOW_VALID"
```

- [ ] **Step 4: Verify GREEN and commit**

```bash
git add "Swing Trading/research/swing/stock_rs/build_stock_rs.py" \
        "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py"
git commit -m "research: add stock RS return rules"
```

---

### Task 3: Implement full-20 cross-sectional percentile/composite/rank logic

**Files:**
- Modify: `build_stock_rs.py`
- Modify: `tests/test_stock_rs.py`

**Interface:** `calculate_daily_stock_rs(frame, expected_count=20) -> pd.DataFrame`

Required input columns:

```text
Date,Symbol,Yahoo_Ticker,Close,RS_Price,Ret21,Ret63,Ret126
```

- [ ] **Step 1: Add strongest/weakest synthetic test** using 20 stocks with strictly increasing returns; require strongest percentile/composite `100`, rank `1`, weakest percentile `5`, rank `20`.
- [ ] **Step 2: Add incomplete-date test** — 20-stock date survives; 19-stock date does not.
- [ ] **Step 3: Add composite-equation test**:

```python
expected = 0.30*target["RS21_Percentile"] + 0.40*target["RS63_Percentile"] + 0.30*target["RS126_Percentile"]
assert target["Composite_RS"] == pytest.approx(expected)
```

- [ ] **Step 4: Verify RED.**
- [ ] **Step 5: Implement mechanically:** drop missing horizon returns; reject duplicate `(Date,Symbol)`; retain only dates with exactly 20 symbols; percentile-rank each horizon with `rank(method="average", pct=True, ascending=True)*100`; compute 30/40/30 composite; deterministic descending composite rank; set `Stock_Count=20`, `Is_Full_Universe=True`; derive status; sort `Date,Composite_Rank`.
- [ ] **Step 6: Verify GREEN and commit.**

---

### Task 4: Implement Yahoo normalization with explicit split-safe RS price construction

**Files:**
- Modify: `build_stock_rs.py`
- Modify: `tests/test_stock_rs.py`

**Interfaces:**
- `normalize_yahoo_frame(frame, symbol, ticker) -> pd.DataFrame`
- `build_point_in_time_rs_price(frame) -> pd.Series`
- `download_stock_history(symbol, ticker) -> pd.DataFrame`
- `build_raw_validation_row(...) -> dict`

Normalized output must include:

```text
Date,Symbol,Yahoo_Ticker,Close,RS_Price,Stock_Splits
```

- [ ] **Step 1: Add single-level and MultiIndex normalization tests.**
- [ ] **Step 2: Add a synthetic split test.** Construct a price series where a 2-for-1 split halves raw Close and `Stock Splits == 2.0` on the split date. Require `RS_Price` to remove the artificial 50% discontinuity without modifying observations using corporate actions that occur after the scored date.
- [ ] **Step 3: Add a no-split test.** Require `RS_Price == Close` when no split occurs.
- [ ] **Step 4: Verify RED.**
- [ ] **Step 5: Download exactly:**

```python
yf.download(
    ticker,
    start="2022-01-01",
    end="2026-08-26",
    interval="1d",
    auto_adjust=False,
    progress=False,
    actions=True,
)
```

- [ ] **Step 6: Implement normalization:** require `Close`; preserve `Stock Splits` (fill missing split events with `0`, not prices); make dates timezone-naive; sort ascending; reject duplicate dates; do not forward-fill prices.
- [ ] **Step 7: Implement `RS_Price` using only split events known on or before each observation.** The test must demonstrate no future split is applied to earlier scored dates. If a robust point-in-time-safe split adjustment cannot be constructed or verified, fail the build and document the limitation rather than silently switching to current Yahoo `Adj Close`.
- [ ] **Step 8: Verify GREEN and commit.**

---

### Task 5: Build end-to-end dataset and exports

For each configured stock: download, normalize, build raw validation record, construct `RS_Price`, calculate returns, append. If any stock fails, terminate before writing research-safe primary output.

After all 20 histories exist, run cross-sectional ranking.

Primary validation must require:

```text
no duplicate (Date,Symbol)
no missing required values
all Stock_Count == 20
all Is_Full_Universe == true
each date exactly 20 symbols
ranks exactly 1..20
percentiles and Composite_RS within (0,100]
statuses only PREFERRED/VALID/BELOW_VALID
30/40/30 recomputation matches
rank 1 score >= rank 20 score
```

Export `stock_rs_daily.csv` with:

```text
Date,Symbol,Yahoo_Ticker,Close,RS_Price,Ret21,Ret63,Ret126,
RS21_Percentile,RS63_Percentile,RS126_Percentile,Composite_RS,
Composite_Rank,Stock_Count,Is_Full_Universe,RS_Status
```

Build `stock_rs_summary.csv` per symbol with ranked days/status counts/date range/mean/median Composite_RS.

Build `stock_rs_validation.csv` per symbol with download status, raw rows/date range, duplicate dates, missing Close, split-event count, and explicit `RS_Price_Method`.

---

### Task 6: Add end-to-end invariant tests

- [ ] duplicate `(Date,Symbol)` rejection;
- [ ] invalid rank-set rejection;
- [ ] invalid universe count/flag rejection;
- [ ] invalid status rejection;
- [ ] summary reconciliation;
- [ ] point-in-time split test proving a future split is not used to revise an earlier scored date.

Run:

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" -v
```

Require zero failures, then commit.

---

### Task 7: Write README with methodology and reliability limitations

README must state:

```text
Streak is preferred whenever it can faithfully express the exact hypothesis.
For this experiment the Portfolio Advisor already determined Streak cannot
perform the required historical same-day cross-sectional universe ranking,
so the custom dataset path was selected before implementation.
```

Also document fixed universe, 21/63/126 session returns, cross-sectional percentiles, 30/40/30 composite, full-20 requirement, 70/80 statuses, `RS_Price` construction, no T1 outcome data, and the following caveats:

- Yahoo/yfinance data may differ from broker/exchange/Streak histories;
- corporate-action handling is a material reliability concern and must remain point-in-time safe;
- fixed 20-stock universe is a proxy, not final Nifty 500 implementation;
- any promising result should be spot-checked against trusted market/broker data before live use;
- future hypotheses should use Streak whenever Streak can represent them exactly.

Document commands:

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" -v
python "Swing Trading/research/swing/stock_rs/build_stock_rs.py"
```

---

### Task 8: Final verification before completion

Use `superpowers:verification-before-completion`.

- [ ] Run all stock-RS tests fresh; require zero failures.
- [ ] Run production build fresh; require exit 0.
- [ ] Independently assert non-empty outputs, no duplicate `(Date,Symbol)`, full-20 dates only, ranks exactly `1..20`, 20 validation rows, 20 summary rows, and reconciled status counts.
- [ ] Print per-stock row counts/date ranges/split-event counts and flag anomalies.
- [ ] Spot-check at least three dates/symbols by recomputing `Ret21`, `Ret63`, `Ret126`, percentiles, and Composite_RS from the exported point-in-time `RS_Price` history.
- [ ] Commit outputs only after all checks pass.
- [ ] Open PR referencing Issue #5.

PR body must include:

```text
Portfolio Advisor methodology decision: CUSTOM_REQUIRED
Test command and exact pass count
Build command and exit result
Python/yfinance/pandas versions
20/20 download success status
RS_Price method and corporate-action safeguards
Raw and ranked date ranges
Primary output row count/ranked-date count
Any vendor/calendar/corporate-action anomalies
Generated artifact paths
Explicit statement: no T1 trade P&L was inspected
```

## Completion Rule

The task is complete only when a fully verified fixed-20 point-in-time stock-RS dataset is produced without T1 outcome data and without future corporate-action leakage. Luna's responsibility is implementation and verification only. The Portfolio Advisor retains responsibility for methodology choices, including Streak-vs-custom selection and whether the signal has enough evidence to affect Swing Strategy V1.