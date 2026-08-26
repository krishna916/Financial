# Stock Relative-Strength Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task using **inline execution only**. Do not use subagent-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, point-in-time stock relative-strength dataset for the fixed 20-stock T1 basket for later independent validation against the locked 218 T1 trades.

**Architecture:** The Portfolio Advisor has already made the methodology decision that Streak cannot faithfully test this exact feature because Streak can backtest conditions across a basket but does not historically calculate same-date cross-sectional percentile/rank of each stock against the basket. Therefore this plan has no Streak-capability decision step. Luna only implements the approved custom-data path: download the fixed 20 stocks, calculate adjusted-price 21/63/126-session returns, rank all 20 stocks cross-sectionally on complete dates, compute the locked 30/40/30 composite, validate every invariant, and export auditable artifacts. Trade P&L is intentionally absent from this phase.

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
- Preserve raw `Close`; calculate RS returns only from `Adj Close`.
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

Responsibilities:

- `stock_ticker_config.csv` — immutable 20-stock experiment universe.
- `build_stock_rs.py` — download, normalization, return calculation, full-universe ranking, validation, and exports.
- `tests/test_stock_rs.py` — deterministic tests for all methodology that does not require live network access.
- `README.md` — exact methodology, run commands, custom-data limitations, and the Portfolio Advisor's already-made Streak-vs-custom decision.
- `output/*.csv` — committed generated research artifacts only after final verification.

---

### Task 1: Lock the experiment universe and dependencies

**Files:**
- Create: `Swing Trading/research/swing/stock_rs/requirements.txt`
- Create: `Swing Trading/research/swing/stock_rs/stock_ticker_config.csv`
- Create: `Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py`

**Interfaces:**
- Produces config columns `Symbol,Yahoo_Ticker`.

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

- [ ] **Step 3: Write the config test**

```python
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]

EXPECTED = {
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "M&M": "M&M.NS",
    "MARUTI": "MARUTI.NS",
    "LT": "LT.NS",
    "RELIANCE": "RELIANCE.NS",
    "ONGC": "ONGC.NS",
    "ITC": "ITC.NS",
    "HINDUNILVR": "HINDUNILVR.NS",
    "SUNPHARMA": "SUNPHARMA.NS",
    "APOLLOHOSP": "APOLLOHOSP.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "TATASTEEL": "TATASTEEL.NS",
    "POWERGRID": "POWERGRID.NS",
    "ADANIENT": "ADANIENT.NS",
    "ULTRACEMCO": "ULTRACEMCO.NS",
}


def test_stock_config_is_exact_fixed_twenty_stock_universe():
    df = pd.read_csv(BASE_DIR / "stock_ticker_config.csv", dtype=str)
    assert df.columns.tolist() == ["Symbol", "Yahoo_Ticker"]
    assert len(df) == 20
    assert df["Symbol"].is_unique
    assert df["Yahoo_Ticker"].is_unique
    assert dict(zip(df["Symbol"], df["Yahoo_Ticker"])) == EXPECTED
```

- [ ] **Step 4: Run the config test**

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py::test_stock_config_is_exact_fixed_twenty_stock_universe" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/stock_rs/requirements.txt" \
        "Swing Trading/research/swing/stock_rs/stock_ticker_config.csv" \
        "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py"
git commit -m "research: lock stock RS universe"
```

---

### Task 2: Implement exact session-return and locked status logic with TDD

**Files:**
- Create: `Swing Trading/research/swing/stock_rs/build_stock_rs.py`
- Modify: `Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py`

**Interfaces:**
- Produces:
  - `calculate_returns(frame: pd.DataFrame) -> pd.DataFrame`
  - `assign_rs_status(composite_rs: float) -> str`

- [ ] **Step 1: Add failing return test**

```python
import math
import pandas as pd
import pytest

from research.swing.stock_rs.build_stock_rs import calculate_returns, assign_rs_status


def test_calculate_returns_uses_exact_adjusted_close_session_shifts():
    df = pd.DataFrame({"Adj_Close": [100.0 + i for i in range(140)]})
    result = calculate_returns(df)
    assert pd.isna(result.loc[20, "Ret21"])
    assert math.isclose(result.loc[21, "Ret21"], 121.0 / 100.0 - 1.0)
    assert math.isclose(result.loc[63, "Ret63"], 163.0 / 100.0 - 1.0)
    assert math.isclose(result.loc[126, "Ret126"], 226.0 / 100.0 - 1.0)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100.0, "PREFERRED"),
        (80.0, "PREFERRED"),
        (79.999, "VALID"),
        (70.0, "VALID"),
        (69.999, "BELOW_VALID"),
        (5.0, "BELOW_VALID"),
    ],
)
def test_assign_rs_status_uses_locked_v1_thresholds(score, expected):
    assert assign_rs_status(score) == expected
```

- [ ] **Step 2: Run tests and verify RED**

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" -v
```

Expected: import/function failures.

- [ ] **Step 3: Implement the minimum functions**

```python
def calculate_returns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["Ret21"] = result["Adj_Close"] / result["Adj_Close"].shift(21) - 1.0
    result["Ret63"] = result["Adj_Close"] / result["Adj_Close"].shift(63) - 1.0
    result["Ret126"] = result["Adj_Close"] / result["Adj_Close"].shift(126) - 1.0
    return result


def assign_rs_status(composite_rs: float) -> str:
    if composite_rs >= 80.0:
        return "PREFERRED"
    if composite_rs >= 70.0:
        return "VALID"
    return "BELOW_VALID"
```

- [ ] **Step 4: Run tests and verify GREEN**

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/stock_rs/build_stock_rs.py" \
        "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py"
git commit -m "research: add stock RS return rules"
```

---

### Task 3: Implement full-20 cross-sectional percentile/composite/rank logic

**Files:**
- Modify: `Swing Trading/research/swing/stock_rs/build_stock_rs.py`
- Modify: `Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py`

**Interfaces:**
- Produces `calculate_daily_stock_rs(frame: pd.DataFrame, expected_count: int = 20) -> pd.DataFrame`.

Required input columns:

```text
Date,Symbol,Yahoo_Ticker,Close,Adj_Close,Ret21,Ret63,Ret126
```

- [ ] **Step 1: Add failing strongest/weakest test**

```python
def test_daily_rs_percentiles_and_composite_rank_strongest_stock_first():
    rows = []
    for i in range(20):
        rows.append({
            "Date": pd.Timestamp("2026-01-02"),
            "Symbol": f"S{i:02d}",
            "Yahoo_Ticker": f"S{i:02d}.NS",
            "Close": 100.0,
            "Adj_Close": 100.0,
            "Ret21": float(i),
            "Ret63": float(i),
            "Ret126": float(i),
        })
    result = calculate_daily_stock_rs(pd.DataFrame(rows))
    strongest = result.loc[result["Symbol"].eq("S19")].iloc[0]
    weakest = result.loc[result["Symbol"].eq("S00")].iloc[0]
    assert len(result) == 20
    assert strongest["RS21_Percentile"] == 100.0
    assert strongest["Composite_RS"] == 100.0
    assert strongest["Composite_Rank"] == 1
    assert strongest["RS_Status"] == "PREFERRED"
    assert weakest["RS21_Percentile"] == 5.0
    assert weakest["Composite_Rank"] == 20
    assert result["Stock_Count"].eq(20).all()
    assert result["Is_Full_Universe"].all()
```

- [ ] **Step 2: Add failing incomplete-date test**

Construct one date with 20 stocks and one with 19. Assert only the 20-stock date survives.

- [ ] **Step 3: Add failing composite-equation test**

```python
expected = (
    0.30 * target["RS21_Percentile"]
    + 0.40 * target["RS63_Percentile"]
    + 0.30 * target["RS126_Percentile"]
)
assert target["Composite_RS"] == pytest.approx(expected)
```

- [ ] **Step 4: Run tests and verify RED**

- [ ] **Step 5: Implement mechanically in this exact order**

1. remove rows missing any of `Ret21,Ret63,Ret126`;
2. reject duplicate `(Date,Symbol)` rows;
3. calculate date-level distinct symbol count;
4. retain only dates with exactly 20 stocks;
5. calculate each horizon percentile with:

```python
result["RS21_Percentile"] = result.groupby("Date")["Ret21"].rank(
    method="average", pct=True, ascending=True
) * 100.0
```

Repeat identically for 63 and 126.

6. calculate:

```python
result["Composite_RS"] = (
    0.30 * result["RS21_Percentile"]
    + 0.40 * result["RS63_Percentile"]
    + 0.30 * result["RS126_Percentile"]
)
```

7. sort by `Date,Symbol` before ties;
8. calculate descending per-date `Composite_Rank` with `method="first"`;
9. set `Stock_Count=20`, `Is_Full_Universe=True`;
10. derive `RS_Status` from the locked helper;
11. final sort `Date,Composite_Rank`.

- [ ] **Step 6: Run tests and verify GREEN**

- [ ] **Step 7: Commit**

```bash
git add "Swing Trading/research/swing/stock_rs/build_stock_rs.py" \
        "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py"
git commit -m "research: add cross-sectional stock RS ranking"
```

---

### Task 4: Implement Yahoo normalization and raw-data validation

**Files:**
- Modify: `Swing Trading/research/swing/stock_rs/build_stock_rs.py`
- Modify: `Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py`

**Interfaces:**
- Produces:
  - `normalize_yahoo_frame(frame, symbol, ticker) -> pd.DataFrame`
  - `download_stock_history(symbol, ticker) -> pd.DataFrame`
  - `build_raw_validation_row(...) -> dict[str, object]`

Normalized columns:

```text
Date,Symbol,Yahoo_Ticker,Close,Adj_Close
```

- [ ] **Step 1: Add failing single-level normalization test**

Use a synthetic frame containing `Close` and `Adj Close`; assert exact normalized values and columns.

- [ ] **Step 2: Add failing MultiIndex normalization test**

Use synthetic columns `("Close","SBIN.NS")` and `("Adj Close","SBIN.NS")`; assert identical normalized result.

- [ ] **Step 3: Add failing missing-adjusted-close test**

A frame without `Adj Close` must raise `ValueError`. Do not silently use raw Close instead.

- [ ] **Step 4: Run tests and verify RED**

- [ ] **Step 5: Implement `yfinance` download exactly**

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

Use one ticker per download for easier validation.

Normalization must:

- flatten/resolve one-ticker MultiIndex safely;
- require both `Close` and `Adj Close`;
- rename `Adj Close` to `Adj_Close`;
- make Date timezone-naive consistently;
- sort ascending;
- reject duplicate dates;
- record missing values rather than forward-fill them;
- fail the production build if usable Close/Adj_Close data is missing.

- [ ] **Step 6: Run tests and verify GREEN**

- [ ] **Step 7: Commit**

```bash
git add "Swing Trading/research/swing/stock_rs/build_stock_rs.py" \
        "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py"
git commit -m "research: add stock RS market data loader"
```

---

### Task 5: Build end-to-end dataset and exports

**Files:**
- Modify: `Swing Trading/research/swing/stock_rs/build_stock_rs.py`
- Create generated outputs under `Swing Trading/research/swing/stock_rs/output/`

**Interfaces:**
- Produces:
  - `build_stock_rs_dataset(...) -> tuple[pd.DataFrame, pd.DataFrame]`
  - `build_stock_summary(frame) -> pd.DataFrame`
  - `validate_primary_output(frame) -> None`

- [ ] **Step 1: Validate config against exact mapping**

Require exactly 20 unique symbols/tickers and exact equality with Issue #5.

- [ ] **Step 2: Process each stock independently**

For every configured stock:

1. download;
2. normalize;
3. create raw validation record;
4. calculate 21/63/126 returns on that stock's own ordered sessions;
5. append rows.

If any stock fails, print/export the failure and terminate before writing a research-safe `stock_rs_daily.csv`.

- [ ] **Step 3: Run cross-sectional ranking only after all 20 histories exist**

Concatenate all return frames and call `calculate_daily_stock_rs(..., expected_count=20)`.

- [ ] **Step 4: Validate primary output**

Fail on any violation:

```text
no duplicate (Date,Symbol)
no missing required values
all Stock_Count == 20
all Is_Full_Universe == true
each date exactly 20 rows / 20 symbols
ranks exactly 1..20 per date
all horizon percentiles >0 and <=100
all Composite_RS >0 and <=100
statuses only PREFERRED/VALID/BELOW_VALID
Composite_RS equals 30/40/30 recomputation
rank 1 Composite_RS >= rank 20 Composite_RS on every date
```

- [ ] **Step 5: Build `stock_rs_summary.csv`**

Per symbol output exactly:

```text
Symbol
Yahoo_Ticker
Valid_Ranked_Days
Preferred_Days
Valid_Days
Below_Valid_Days
Earliest_Ranked_Date
Latest_Ranked_Date
Mean_Composite_RS
Median_Composite_RS
```

Assert status counts reconcile to `Valid_Ranked_Days`.

- [ ] **Step 6: Build `stock_rs_validation.csv`**

Per symbol output:

```text
Symbol
Yahoo_Ticker
Download_Status
Raw_Rows
Earliest_Raw_Date
Latest_Raw_Date
Duplicate_Date_Count
Missing_Close_Count
Missing_Adj_Close_Count
```

Successful final build requires all `Download_Status == OK`.

- [ ] **Step 7: Export primary file with exact columns**

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

Write dates as `YYYY-MM-DD` and sort by `Date,Composite_Rank`.

---

### Task 6: Add deterministic end-to-end invariant tests

**Files:**
- Modify: `Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py`

- [ ] **Step 1: Test duplicate `(Date,Symbol)` rejection**
- [ ] **Step 2: Test invalid rank-set rejection** — modify one rank so the set is not exactly `1..20`; require `ValueError`.
- [ ] **Step 3: Test invalid universe count/flag rejection** — separately set `Stock_Count=19` and `Is_Full_Universe=False`; require `ValueError`.
- [ ] **Step 4: Test invalid status rejection** — use `STRONG`; require `ValueError`.
- [ ] **Step 5: Test summary reconciliation** — `Preferred_Days + Valid_Days + Below_Valid_Days == Valid_Ranked_Days` for every stock.

- [ ] **Step 6: Run full test module**

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" -v
```

Require zero failures.

- [ ] **Step 7: Commit**

```bash
git add "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" \
        "Swing Trading/research/swing/stock_rs/build_stock_rs.py"
git commit -m "test: validate stock RS research invariants"
```

---

### Task 7: Write README with methodology and reliability limitations

**Files:**
- Create: `Swing Trading/research/swing/stock_rs/README.md`

- [ ] **Step 1: Document source hierarchy accurately**

README must state:

```text
Streak is preferred whenever it can faithfully express the exact hypothesis.
For this experiment the Portfolio Advisor already determined Streak cannot
perform the required historical same-day cross-sectional universe ranking,
so the custom dataset path was selected before implementation.
```

Do not present that decision as Luna's finding.

- [ ] **Step 2: Document exact methodology**

Include fixed 20-stock universe, adjusted-close 21/63/126-session returns, same-date percentiles, 30/40/30 composite, full-20 date requirement, 70/80 statuses, and explicit statement that no T1 outcome data was used.

- [ ] **Step 3: Document reliability caveats**

Explicitly state:

- Yahoo/yfinance histories can differ from broker/exchange/Streak histories due to vendor adjustments or corporate-action handling;
- the fixed 20-stock universe is a proxy, not the intended final Nifty 500 universe;
- any promising result requires spot-checking against trusted market/broker data before live use;
- future experiments should use Streak instead whenever the exact hypothesis is representable there.

- [ ] **Step 4: Document commands from repo root**

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" -v
python "Swing Trading/research/swing/stock_rs/build_stock_rs.py"
```

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/stock_rs/README.md"
git commit -m "docs: document stock RS research pipeline"
```

---

### Task 8: Final verification before completion

Use `superpowers:verification-before-completion`.

- [ ] **Step 1: Run full tests fresh**

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" -v
```

Require zero failures.

- [ ] **Step 2: Run production dataset build fresh**

```bash
python "Swing Trading/research/swing/stock_rs/build_stock_rs.py"
```

Require exit code 0.

- [ ] **Step 3: Independently validate generated artifacts**

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd

base = Path('Swing Trading/research/swing/stock_rs/output')
daily = pd.read_csv(base / 'stock_rs_daily.csv')
summary = pd.read_csv(base / 'stock_rs_summary.csv')
validation = pd.read_csv(base / 'stock_rs_validation.csv')

assert not daily.empty
assert daily[['Date','Symbol']].duplicated().sum() == 0
assert daily['Stock_Count'].eq(20).all()
assert daily['Is_Full_Universe'].astype(str).str.lower().eq('true').all()
assert daily.groupby('Date')['Symbol'].nunique().eq(20).all()
assert daily.groupby('Date')['Composite_Rank'].apply(lambda s: set(s) == set(range(1, 21))).all()
assert validation['Download_Status'].eq('OK').all()
assert len(validation) == 20
assert len(summary) == 20
assert (summary['Preferred_Days'] + summary['Valid_Days'] + summary['Below_Valid_Days']).eq(summary['Valid_Ranked_Days']).all()
print('independent stock-RS artifact validation passed')
PY
```

Expected: `independent stock-RS artifact validation passed`.

- [ ] **Step 4: Review vendor/calendar anomalies**

Print per-stock raw row counts/date ranges and explicitly flag any materially shorter or anomalous history. Do not silently accept it merely because common-date filtering still produces output.

- [ ] **Step 5: Commit verified outputs**

Only after Steps 1-4 pass:

```bash
git add "Swing Trading/research/swing/stock_rs/output/stock_rs_daily.csv" \
        "Swing Trading/research/swing/stock_rs/output/stock_rs_summary.csv" \
        "Swing Trading/research/swing/stock_rs/output/stock_rs_validation.csv"
git commit -m "research: add verified stock RS artifacts"
```

- [ ] **Step 6: Open PR referencing Issue #5**

PR body must include:

```text
Portfolio Advisor methodology decision: CUSTOM_REQUIRED
Test command and exact pass count
Build command and exit result
Python/yfinance/pandas versions
20/20 download success status
Raw and ranked date ranges
Primary output row count and ranked-date count
Any vendor/calendar anomalies
Generated artifact paths
Explicit statement: no T1 trade P&L was inspected in this issue
```

## Completion Rule

The task is complete only when a fully verified fixed-20, point-in-time stock-RS dataset is produced without using T1 outcome data. Luna's responsibility is implementation and verification only. The Portfolio Advisor retains responsibility for methodology choices, including whether Streak can faithfully represent a future hypothesis and whether a generated signal has enough evidence to affect Swing Strategy V1.