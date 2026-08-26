# T1 Stock Relative-Strength Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task using **inline execution only**. Do not use subagent-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproducibly test whether the already-defined point-in-time individual-stock relative-strength framework improves selection quality for the fixed 218-trade T1 swing-breakout sample, without tuning the feature or the trade rules after outcomes are visible.

**Architecture:** Read the immutable T1 trade sample and merged Issue #5 / PR #6 stock-RS output, validate both independently, perform a strict backward/as-of per-symbol join using the latest RS observation **strictly before** each next-session-open T1 entry, calculate only the predeclared primary comparisons, then run time/outlier/stock-identity robustness. Only after those primary outputs exist, independently strict-before join the existing market-regime and sector-leadership datasets for secondary interaction diagnostics. Export auditable CSVs plus an evidence-only report; final strategy interpretation remains with the Portfolio Advisor.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest, standard-library `hashlib`, `pathlib`.

**Spec:** GitHub Issue #7 — `https://github.com/krishna916/Financial/issues/7`

## Global Constraints

- This is **validation, not optimization**.
- Validation source is already locked as `CUSTOM_REQUIRED`; do not revisit Streak capability.
- T1 sample is locked at **218 completed trades / 20 symbols**.
- Do not re-run Streak or regenerate T1 trades.
- Do not change T1 entry/exit rules.
- Stock-RS methodology is immutable: 21/63/126-session returns, same-day cross-sectional percentiles, 30/40/30 composite, rank 1 strongest.
- Stock-RS status bands are immutable: `PREFERRED >= 80`, `VALID >= 70 and < 80`, `BELOW_VALID < 70`.
- Research-safe RS observations require `Stock_Count == 20` and `Is_Full_Universe == true`.
- Because Streak daily conditions are known only after the signal candle closes and the backtest entry is the next candle open, every feature/context join must use the latest observation **strictly before `Entry_Date`**.
- For stock RS use `RS_Matched_Date < Entry_Date`; same-entry-day rows are forbidden.
- For secondary market/sector interaction use `Context_Matched_Date < Entry_Date`; same-entry-day rows are forbidden.
- Never forward-match future data.
- Do not add a cutoff after rank results are visible.
- Do not drop bad trades, event losses, weak years, or weak stocks after seeing outcomes.
- Do not add RSI, ADX, MACD, volume, MA-slope, ATR, volatility, or other new filters.
- Interaction tables are secondary diagnostics and must not redefine the primary stock-RS conclusion.
- Do not create notebooks, dashboards, CI, shared-framework refactors, or unrelated repository infrastructure.
- Implementation must be mechanical enough for Luna to execute without trading-domain judgment.
- Execution mode is inline only.

---

## Existing Locked Inputs

### Fixed T1 trade sample

```text
Swing Trading/research/swing/t1_sector_validation/input/t1_trades.csv
```

Expected SHA-256 of the exact CSV bytes:

```text
6b4c2931f23f0e043816d973eba16b5bf3ca57411642d4528de060ea2febb1e4
```

Expected aggregates:

```text
Rows: 218
Unique symbols: 20
Winners (Return_Pct > 0): 76
Total PnL: -4631.32
Mean Return_Pct: approximately -0.0548680341
```

Required columns:

```text
Symbol
Entry_Date
Exit_Date
Entry_Price
Exit_Price
Qty
Return_Pct
PnL
Holding_Days
Source_Log
```

### Fixed stock-RS dataset

```text
Swing Trading/research/swing/stock_rs/output/stock_rs_daily.csv
```

Required columns:

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

Allowed status values:

```text
PREFERRED
VALID
BELOW_VALID
```

### Existing sector interaction dependencies

```text
Swing Trading/research/swing/sector_leadership/output/sector_leadership_daily.csv
Swing Trading/research/swing/sector_leadership/stock_sector_map.csv
```

Research-safe sector rows require:

```text
Sector_Count == 11
```

and `Is_Full_Universe == true` as well if that column exists.

### Existing market-regime interaction dependency

```text
Swing Trading/nifty500_regime_daily.csv
```

Allowed regimes:

```text
RISK_ON
MIXED
RISK_OFF
```

Do not use the already joined same-day context columns in `t1_sector_joined_trades.csv` for interaction logic. Re-match the raw locked context datasets with strict pre-entry timing.

---

## Target File Map

Create only:

```text
Swing Trading/research/swing/t1_stock_rs_validation/
├── analyze_t1_stock_rs.py
├── README.md
├── tests/
│   └── test_t1_stock_rs.py
└── output/
    ├── t1_stock_rs_joined_trades.csv
    ├── t1_stock_rs_status_summary.csv
    ├── t1_stock_rs_binary_tests.csv
    ├── t1_stock_rs_rank_summary.csv
    ├── t1_stock_rs_year_summary.csv
    ├── t1_stock_rs_outlier_robustness.csv
    ├── t1_stock_rs_symbol_summary.csv
    ├── t1_stock_rs_leave_one_symbol_out.csv
    ├── t1_stock_rs_market_matrix.csv
    ├── t1_stock_rs_sector_matrix.csv
    ├── validation_report.csv
    └── research_report.md
```

Do **not** copy the T1 trade CSV or stock-RS CSV into this directory. Use the merged canonical repository inputs above.

---

## Locked Metric Definitions

Every grouped output that says “standard metrics” must use these columns:

```text
Trades
Winners
Losers
Win_Rate
Mean_Return
Median_Return
Average_Winner
Average_Loser
Payoff_Ratio
Return_Profit_Factor
PnL_Profit_Factor
Total_PnL
Median_Holding_Days
```

Definitions:

```text
Winners = Return_Pct > 0
Losers = Return_Pct <= 0
Win_Rate = Winners / Trades * 100
Mean_Return = mean(Return_Pct)
Median_Return = median(Return_Pct)
Average_Winner = mean(Return_Pct where > 0)
Average_Loser = mean(Return_Pct where <= 0)
Payoff_Ratio = Average_Winner / abs(Average_Loser)
Return_Profit_Factor = sum(positive Return_Pct) / abs(sum(non-positive Return_Pct))
PnL_Profit_Factor = sum(positive PnL) / abs(sum(non-positive PnL))
Total_PnL = sum(PnL)
Median_Holding_Days = median(Holding_Days)
```

Profit-factor edge behavior:

```text
positive numerator + zero losses -> inf
zero gains + positive losses -> 0
zero gains + zero losses -> NaN
```

Do not invent alternative metric formulas in later tasks.

---

### Task 1: Scaffold the validation module and lock both inputs with TDD

**Files:**
- Create: `Swing Trading/research/swing/t1_stock_rs_validation/analyze_t1_stock_rs.py`
- Create: `Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py`

**Interfaces:**
- Produces:
  - `load_and_validate_trades(path: Path = T1_TRADES_PATH) -> pd.DataFrame`
  - `load_and_validate_stock_rs(path: Path = STOCK_RS_PATH) -> pd.DataFrame`
  - `calculate_profit_factor(values: pd.Series) -> float`
  - `calculate_trade_metrics(frame: pd.DataFrame) -> dict[str, float | int]`

- [ ] **Step 1: Create module constants exactly**

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SWING_RESEARCH_DIR = BASE_DIR.parent
SWING_TRADING_DIR = BASE_DIR.parents[2]

T1_TRADES_PATH = SWING_RESEARCH_DIR / "t1_sector_validation" / "input" / "t1_trades.csv"
STOCK_RS_PATH = SWING_RESEARCH_DIR / "stock_rs" / "output" / "stock_rs_daily.csv"
SECTOR_RS_PATH = SWING_RESEARCH_DIR / "sector_leadership" / "output" / "sector_leadership_daily.csv"
STOCK_SECTOR_MAP_PATH = SWING_RESEARCH_DIR / "sector_leadership" / "stock_sector_map.csv"
MARKET_REGIME_PATH = SWING_TRADING_DIR / "nifty500_regime_daily.csv"
OUTPUT_DIR = BASE_DIR / "output"

EXPECTED_T1_SHA256 = "6b4c2931f23f0e043816d973eba16b5bf3ca57411642d4528de060ea2febb1e4"
ALLOWED_RS_STATUSES = {"PREFERRED", "VALID", "BELOW_VALID"}
ALLOWED_MARKET_REGIMES = {"RISK_ON", "MIXED", "RISK_OFF"}
ALLOWED_SECTOR_BUCKETS = {"LEADING", "ACCEPTABLE", "WEAK", "LAGGING"}
```

- [ ] **Step 2: Write failing T1-input validation test**

Test the real canonical input:

```python
import hashlib
import math


def test_locked_t1_input_is_exact_218_trade_sample():
    raw = T1_TRADES_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_T1_SHA256

    trades = load_and_validate_trades(T1_TRADES_PATH)
    assert len(trades) == 218
    assert trades["Symbol"].nunique() == 20
    assert int((trades["Return_Pct"] > 0).sum()) == 76
    assert math.isclose(float(trades["PnL"].sum()), -4631.32, abs_tol=0.01)
    assert math.isclose(float(trades["Return_Pct"].mean()), -0.0548680341, abs_tol=1e-8)
```

Also test inside `load_and_validate_trades`:

```text
exact required columns
Entry_Date and Exit_Date parse successfully
Entry_Date <= Exit_Date
Qty > 0
no null required fields
no duplicate normalized trade key
```

Use duplicate key:

```text
Symbol,Entry_Date,Exit_Date,Entry_Price,Exit_Price,Qty
```

- [ ] **Step 3: Write failing stock-RS validation tests**

Validate the real canonical stock-RS dataset:

```python
def test_stock_rs_input_is_research_safe_and_locked():
    rs = load_and_validate_stock_rs(STOCK_RS_PATH)
    assert set(rs["RS_Status"].unique()) <= ALLOWED_RS_STATUSES
    assert (rs["Stock_Count"] == 20).all()
    assert rs["Is_Full_Universe"].all()
    assert rs["Composite_Rank"].between(1, 20).all()
    assert not rs.duplicated(["Date", "Symbol"]).any()
```

The loader must fail loudly if any unsafe row exists rather than silently filtering a malformed canonical file.

- [ ] **Step 4: Write failing standard-metric tests**

Use a tiny deterministic frame with known `Return_Pct`, `PnL`, and `Holding_Days`. Verify every metric definition in the “Locked Metric Definitions” section and the profit-factor edge behavior.

- [ ] **Step 5: Run tests and verify RED**

```bash
python -m pytest "Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py" -v
```

Expected: import/function failures.

- [ ] **Step 6: Implement minimum loaders and metric helpers**

Use `pd.to_datetime(..., errors="coerce")` for dates and `pd.to_numeric(..., errors="coerce")` for numeric required fields. Do not coerce malformed required data into dropped rows.

- [ ] **Step 7: Run tests and verify GREEN**

```bash
python -m pytest "Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py" -v
```

- [ ] **Step 8: Commit**

```bash
git add "Swing Trading/research/swing/t1_stock_rs_validation/analyze_t1_stock_rs.py" \
        "Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py"
git commit -m "research: scaffold T1 stock RS validation"
```

---

### Task 2: Implement the strict pre-entry stock-RS join with no-lookahead tests

**Files:**
- Modify: `Swing Trading/research/swing/t1_stock_rs_validation/analyze_t1_stock_rs.py`
- Modify: `Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py`

**Interfaces:**
- Produces `join_stock_rs_at_decision_time(trades: pd.DataFrame, rs: pd.DataFrame) -> pd.DataFrame`.

- [ ] **Step 1: Write failing test proving same-entry-day RS is forbidden**

Synthetic data:

```text
RS dates for SBIN: 2026-01-02, 2026-01-05
Trade Entry_Date: 2026-01-05
```

Expected:

```text
RS_Matched_Date == 2026-01-02
```

The 2026-01-05 RS row must **not** match.

- [ ] **Step 2: Write failing test proving future rows are forbidden**

Synthetic data:

```text
RS dates:        2026-01-05
Trade Entry_Date:2026-01-04
```

Expected: unmatched/NaN result before integrity validation; never forward-match 2026-01-05.

- [ ] **Step 3: Write failing per-symbol isolation test**

Create SBIN and INFY RS rows on overlapping dates and an SBIN trade. Assert the SBIN trade never receives INFY feature values.

- [ ] **Step 4: Write failing lag test**

For `Entry_Date=2026-01-05`, `RS_Matched_Date=2026-01-02`:

```text
RS_Date_Lag_Days == 3
```

Lag is calendar days and must be strictly `> 0`.

- [ ] **Step 5: Implement strict backward/as-of join**

Use `pd.merge_asof` with:

```python
direction="backward"
allow_exact_matches=False
```

and same-symbol grouping via `by="Symbol"` or an equivalent deterministic per-symbol merge.

Rename the RS `Date` column to:

```text
RS_Matched_Date
```

before/after the join as appropriate, then calculate:

```python
joined["RS_Date_Lag_Days"] = (
    joined["Entry_Date"] - joined["RS_Matched_Date"]
).dt.days
```

- [ ] **Step 6: Add real-data join integrity test**

Using canonical inputs, assert:

```text
joined rows == 218
unmatched RS trades == 0
all RS_Matched_Date < Entry_Date
all RS_Date_Lag_Days > 0
all Stock_Count == 20
all Is_Full_Universe == true
all Composite_Rank in 1..20
```

Also assert the joined trade-side PnL still sums to `-4631.32` within 0.01.

- [ ] **Step 7: Run tests**

```bash
python -m pytest "Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py" -v
```

- [ ] **Step 8: Commit**

```bash
git add "Swing Trading/research/swing/t1_stock_rs_validation"
git commit -m "research: join T1 trades to prior-day stock RS"
```

---

### Task 3: Export the audited trade-level join and primary status summaries

**Files:**
- Modify: `Swing Trading/research/swing/t1_stock_rs_validation/analyze_t1_stock_rs.py`
- Modify: `Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py`
- Create on execution: `Swing Trading/research/swing/t1_stock_rs_validation/output/t1_stock_rs_joined_trades.csv`
- Create on execution: `Swing Trading/research/swing/t1_stock_rs_validation/output/t1_stock_rs_status_summary.csv`

**Interfaces:**
- Produces:
  - `summarize_status_groups(joined: pd.DataFrame) -> pd.DataFrame`
  - deterministic joined-trade export.

- [ ] **Step 1: Lock joined export columns**

Export at minimum, in this order:

```text
Symbol
Entry_Date
Exit_Date
Entry_Price
Exit_Price
Qty
Return_Pct
PnL
Holding_Days
Source_Log
RS_Matched_Date
RS_Date_Lag_Days
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

Sort deterministically by:

```text
Entry_Date, Symbol, Exit_Date
```

- [ ] **Step 2: Write failing exact-status-summary test**

Output exactly these group labels and order:

```text
PREFERRED
VALID
BELOW_VALID
```

Each row includes all standard metrics.

- [ ] **Step 3: Implement status summary**

Do not merge or rename status bands based on observed sample sizes.

- [ ] **Step 4: Add reconciliation tests**

Assert:

```text
sum(status Trades) == 218
sum(status Total_PnL) == -4631.32 within 0.01
```

- [ ] **Step 5: Run tests and generate outputs**

```bash
python -m pytest "Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py" -v
python "Swing Trading/research/swing/t1_stock_rs_validation/analyze_t1_stock_rs.py"
```

The script may temporarily generate only outputs implemented so far; later tasks complete the full set.

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/t1_stock_rs_validation"
git commit -m "research: add T1 stock RS primary status outputs"
```

---

### Task 4: Implement only the two predeclared primary binary tests

**Files:**
- Modify: `Swing Trading/research/swing/t1_stock_rs_validation/analyze_t1_stock_rs.py`
- Modify: `Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py`
- Create on execution: `output/t1_stock_rs_binary_tests.csv`

**Interfaces:**
- Produces `summarize_primary_binary_tests(joined: pd.DataFrame) -> pd.DataFrame`.

- [ ] **Step 1: Lock the only allowed comparisons**

```text
PREFERRED_TEST:
  PREFERRED
  NON_PREFERRED = VALID + BELOW_VALID

VALID_OR_BETTER_TEST:
  VALID_OR_BETTER = PREFERRED + VALID
  BELOW_VALID
```

Use output columns:

```text
Comparison
Group
<standard metrics>
```

- [ ] **Step 2: Write failing group-membership tests**

Synthetic statuses:

```text
PREFERRED, VALID, BELOW_VALID
```

Assert:

```text
PREFERRED_TEST/PREFERRED -> only PREFERRED
PREFERRED_TEST/NON_PREFERRED -> VALID + BELOW_VALID
VALID_OR_BETTER_TEST/VALID_OR_BETTER -> PREFERRED + VALID
VALID_OR_BETTER_TEST/BELOW_VALID -> only BELOW_VALID
```

- [ ] **Step 3: Implement without alternate thresholds**

Do not add top-5/top-8/top-10/top-half rank filters.

- [ ] **Step 4: Reconcile each partition**

For each `Comparison` independently:

```text
sum(Trades) == 218
sum(Total_PnL) == -4631.32 within 0.01
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest "Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py" -v
```

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/t1_stock_rs_validation"
git commit -m "research: add locked stock RS binary tests"
```

---

### Task 5: Produce rank 1–20 diagnostics without optimizing a cutoff

**Files:**
- Modify: `Swing Trading/research/swing/t1_stock_rs_validation/analyze_t1_stock_rs.py`
- Modify: `Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py`
- Create on execution: `output/t1_stock_rs_rank_summary.csv`

**Interfaces:**
- Produces `summarize_composite_ranks(joined: pd.DataFrame) -> pd.DataFrame`.

- [ ] **Step 1: Lock diagnostic ranks**

Group by integer `Composite_Rank` exactly 1 through 20.

Include:

```text
Composite_Rank
Trades
<remaining standard metrics>
Mean_Composite_RS
Median_Composite_RS
```

- [ ] **Step 2: Write failing test that preserves exact rank identity**

Use synthetic ranks `1, 2, 20` and assert they remain separate rows. No rank bucketing is permitted.

- [ ] **Step 3: Implement rank summary**

If a rank has zero trades, include a zero-trade row if implementation is straightforward; otherwise document absent ranks consistently in the report. Never combine ranks to manufacture sample size.

- [ ] **Step 4: Add explicit guard test against helper-created optimized cutoff columns**

The rank summary must not contain columns or labels such as:

```text
TOP_5
TOP_8
TOP_10
TOP_HALF
OPTIMAL_CUTOFF
```

- [ ] **Step 5: Run tests and commit**

```bash
python -m pytest "Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py" -v
git add "Swing Trading/research/swing/t1_stock_rs_validation"
git commit -m "research: add stock RS rank diagnostics"
```

---

### Task 6: Add time, outlier, and stock-identity robustness

**Files:**
- Modify: `Swing Trading/research/swing/t1_stock_rs_validation/analyze_t1_stock_rs.py`
- Modify: `Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py`
- Create on execution:
  - `output/t1_stock_rs_year_summary.csv`
  - `output/t1_stock_rs_outlier_robustness.csv`
  - `output/t1_stock_rs_symbol_summary.csv`
  - `output/t1_stock_rs_leave_one_symbol_out.csv`

**Interfaces:**
- Produces:
  - `summarize_by_entry_year(...)`
  - `summarize_outlier_robustness(...)`
  - `summarize_symbol_status(...)`
  - `summarize_leave_one_symbol_out(...)`

- [ ] **Step 1: Lock entry-year output**

Use only:

```text
2023
2024
2025
2026
```

For each year, produce both primary comparisons from Task 4.

Columns begin with:

```text
Entry_Year
Comparison
Group
```

then all standard metrics.

Do not combine years after results are visible.

- [ ] **Step 2: Write failing outlier-removal test**

Create a tiny sample with known positive PnLs and losers. Verify exclusions are chosen globally by descending **positive `PnL` only**.

Scenarios exactly:

```text
ALL_TRADES
EXCLUDE_TOP_1_POSITIVE_PNL
EXCLUDE_TOP_3_POSITIVE_PNL
EXCLUDE_TOP_5_POSITIVE_PNL
```

For each scenario, recompute both primary comparisons.

Never exclude a loser.

- [ ] **Step 3: Export outlier audit identity**

Include:

```text
Excluded_Trades
```

formatted deterministically as semicolon-separated values such as:

```text
M&M|2024-01-10|2817.00;SUNPHARMA|2025-02-03|2400.00
```

using the actual excluded rows.

- [ ] **Step 4: Lock symbol × status summary**

Group by:

```text
Symbol
RS_Status
```

Include standard metrics and:

```text
Small_Sample = Trades < 5
```

Do not suppress small cells.

- [ ] **Step 5: Lock leave-one-symbol-out robustness**

For each of the exact 20 T1 symbols, remove **all trades for that one symbol**, then recompute both Task-4 comparisons.

Columns:

```text
Excluded_Symbol
Comparison
Group
<standard metrics>
```

This yields 20 × 2 comparisons × 2 groups = 80 rows if every group remains represented. If a group becomes empty, retain the row with zero/NaN metrics rather than dropping the scenario.

Do not interpret a weak symbol as a reason to remove it from the fixed universe.

- [ ] **Step 6: Add deterministic tests for all four robustness outputs**

Test:
- exact years only;
- exact four outlier scenarios;
- losers never excluded by outlier routine;
- every observed symbol/status cell is retained;
- leave-one-symbol-out excludes exactly one requested symbol and no other symbols.

- [ ] **Step 7: Run tests and commit**

```bash
python -m pytest "Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py" -v
git add "Swing Trading/research/swing/t1_stock_rs_validation"
git commit -m "research: add stock RS robustness analysis"
```

---

### Task 7: Add secondary market and sector interactions with corrected strict timing

**Files:**
- Modify: `Swing Trading/research/swing/t1_stock_rs_validation/analyze_t1_stock_rs.py`
- Modify: `Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py`
- Create on execution:
  - `output/t1_stock_rs_market_matrix.csv`
  - `output/t1_stock_rs_sector_matrix.csv`

**Interfaces:**
- Produces:
  - `join_market_regime_strictly_before_entry(...)`
  - `join_sector_leadership_strictly_before_entry(...)`
  - `summarize_market_interactions(...)`
  - `summarize_sector_interactions(...)`

**Important:** Task 7 must run only after Tasks 3–6 primary outputs are implemented. Do not use interaction results to alter prior outputs.

- [ ] **Step 1: Write strict market-timing test**

Synthetic data:

```text
Market dates:     2026-01-02 RISK_ON, 2026-01-05 RISK_OFF
Trade Entry_Date: 2026-01-05
```

Expected matched regime:

```text
RISK_ON from 2026-01-02
```

The same-entry-day 2026-01-05 `RISK_OFF` row is forbidden.

- [ ] **Step 2: Write strict sector-timing test**

Synthetic same-sector rows:

```text
2026-01-02 LEADING
2026-01-05 LAGGING
Trade Entry_Date 2026-01-05
```

Expected: `LEADING` from 2026-01-02.

Also prove a row with `Sector_Count != 11` can never be matched.

- [ ] **Step 3: Load and validate stock-sector mapping**

Use:

```text
Swing Trading/research/swing/sector_leadership/stock_sector_map.csv
```

Assert exactly 20 unique stocks and every T1 symbol maps exactly once.

Do not remap based on observed outcomes.

- [ ] **Step 4: Implement strict context joins**

Use backward/as-of matching with:

```python
allow_exact_matches=False
direction="backward"
```

For sector join, match within `Sector_Key` and only research-safe sector rows.

Export matched date and lag:

```text
Market_Matched_Date
Market_Date_Lag_Days
Market_Regime

Sector_Key
Sector_Matched_Date
Sector_Date_Lag_Days
Leadership_Bucket
Sector_Composite_RS
Sector_Composite_Rank
Sector_Count
```

Rename sector composite columns so they cannot collide with stock RS columns.

- [ ] **Step 5: Assert context integrity on real data**

For all 218 joined trades:

```text
Market_Matched_Date < Entry_Date
Market_Date_Lag_Days > 0
Sector_Matched_Date < Entry_Date
Sector_Date_Lag_Days > 0
Sector_Count == 11
Market_Regime in RISK_ON/MIXED/RISK_OFF
Leadership_Bucket in LEADING/ACCEPTABLE/WEAK/LAGGING
```

If a canonical dependency unexpectedly lacks historical coverage and creates unmatched rows, fail loudly and report the exact missing trades. Do not forward-fill from the future or silently drop them.

- [ ] **Step 6: Lock market interaction output**

Produce two sections distinguished by `Analysis_Type` in the same CSV:

```text
STATUS_MATRIX
BINARY_WITHIN_REGIME
```

For `STATUS_MATRIX`, group by:

```text
Market_Regime
RS_Status
```

For `BINARY_WITHIN_REGIME`, for each regime reproduce both Task-4 primary comparisons exactly.

Every row includes standard metrics plus:

```text
Small_Sample = Trades < 5
```

- [ ] **Step 7: Lock sector interaction output**

Produce two sections distinguished by `Analysis_Type`:

```text
STATUS_MATRIX
BINARY_WITHIN_SECTOR_BUCKET
```

For `STATUS_MATRIX`, group by:

```text
Leadership_Bucket
RS_Status
```

For `BINARY_WITHIN_SECTOR_BUCKET`, for each leadership bucket reproduce both Task-4 comparisons exactly.

Add `Small_Sample = Trades < 5`.

Do not create a new combined buy rule from these tables.

- [ ] **Step 8: Run tests and commit**

```bash
python -m pytest "Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py" -v
git add "Swing Trading/research/swing/t1_stock_rs_validation"
git commit -m "research: add strict-timing RS interaction checks"
```

---

### Task 8: Create validation report, evidence-only research report, README, and final verification

**Files:**
- Modify: `Swing Trading/research/swing/t1_stock_rs_validation/analyze_t1_stock_rs.py`
- Create: `Swing Trading/research/swing/t1_stock_rs_validation/README.md`
- Create on execution:
  - `output/validation_report.csv`
  - `output/research_report.md`

- [ ] **Step 1: Make the main script produce the complete output set atomically**

On a successful run, write all expected CSVs/report files to `output/`.

Before writing final research outputs, all validation invariants must pass. Do not leave a mixture of fresh and stale outputs after a failure. A simple acceptable approach is:

1. calculate/validate all dataframes in memory;
2. create `OUTPUT_DIR` only after validation;
3. write every output in deterministic order.

No extra staging framework is required.

- [ ] **Step 2: Write `validation_report.csv` as key/value audit rows**

Include at minimum:

```text
Input_Trade_Count,218
Unique_Symbols,20
Winners,76
Input_Total_PnL,-4631.32
Unmatched_RS_Trades,0
Same_Day_RS_Matches,0
Future_RS_Matches,0
NonFullUniverse_RS_Matches,0
Median_RS_Lag_Days,<value>
Max_RS_Lag_Days,<value>
RS_Lag_Over_7_Days_Count,<value>
Primary_Status_Count_Reconciles,true
Primary_Status_PnL_Reconciles,true
Preferred_Test_Count_Reconciles,true
Preferred_Test_PnL_Reconciles,true
ValidOrBetter_Test_Count_Reconciles,true
ValidOrBetter_Test_PnL_Reconciles,true
Same_Day_Market_Matches,0
Future_Market_Matches,0
Same_Day_Sector_Matches,0
Future_Sector_Matches,0
NonFullUniverse_Sector_Matches,0
```

Also include actual min/max matched dates for RS, market, and sector.

- [ ] **Step 3: Write `research_report.md` from already-generated outputs only**

The report must contain these sections in order:

```markdown
# T1 Stock Relative-Strength Validation

## Methodology
## Decision-Time Integrity
## Unfiltered T1 Baseline
## RS Status Results
## Primary Binary Comparisons
## Rank Diagnostics
## Year Stability
## Outlier Robustness
## Stock-Identity Robustness
## Market-Regime Interaction
## Sector-Leadership Interaction
## Data / Method Limitations
## Evidence Summary
```

The report may state factual comparisons such as:

```text
PREFERRED mean return was X versus Y for NON_PREFERRED.
```

It must **not** say:

```text
Adopt RS >= 80.
The strategy is validated.
Change the strategy.
Optimize the cutoff to rank <= N.
```

Final strategy interpretation belongs to the Portfolio Advisor.

- [ ] **Step 4: Make outlier dependence explicit in the report**

Name the actual globally excluded top 1 / 3 / 5 positive-PnL trades and show whether the direction of each primary comparison survives those removals.

Also state the range of leave-one-symbol-out results for each primary comparison so giant winners or one dominant symbol cannot be hidden behind aggregate metrics.

- [ ] **Step 5: Document the timing correction explicitly**

In `README.md` and `research_report.md`, state:

```text
T1's Streak daily entry is next-candle-open after an EOD signal, so this validation uses only feature/context observations strictly before Entry_Date. Same-entry-day daily RS/market/sector closes are not decision-time-safe for this experiment.
```

Do not rewrite or retroactively modify the earlier sector experiment in this issue. This task only uses corrected timing for its own interaction diagnostics.

- [ ] **Step 6: Write concise `README.md`**

Include:
- purpose: validation, not optimization;
- canonical input paths;
- strict `< Entry_Date` join rule;
- locked comparisons;
- run commands;
- output list;
- note that Portfolio Advisor owns the final strategy decision.

Run commands:

```bash
python -m pytest "Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py" -v
python "Swing Trading/research/swing/t1_stock_rs_validation/analyze_t1_stock_rs.py"
```

- [ ] **Step 7: Full final verification**

Run from repository root:

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" -q -p no:cacheprovider
python -m pytest "Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py" -q -p no:cacheprovider
python "Swing Trading/research/swing/t1_stock_rs_validation/analyze_t1_stock_rs.py"
```

Then run a lightweight independent output audit:

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd

out = Path("Swing Trading/research/swing/t1_stock_rs_validation/output")
joined = pd.read_csv(out / "t1_stock_rs_joined_trades.csv", parse_dates=["Entry_Date", "RS_Matched_Date"])
status = pd.read_csv(out / "t1_stock_rs_status_summary.csv")
binary = pd.read_csv(out / "t1_stock_rs_binary_tests.csv")

assert len(joined) == 218
assert (joined["RS_Matched_Date"] < joined["Entry_Date"]).all()
assert (joined["RS_Date_Lag_Days"] > 0).all()
assert (joined["Stock_Count"] == 20).all()
assert joined["Is_Full_Universe"].astype(str).str.lower().eq("true").all()
assert abs(joined["PnL"].sum() - (-4631.32)) <= 0.01
assert status["Trades"].sum() == 218
assert abs(status["Total_PnL"].sum() - (-4631.32)) <= 0.01
for comparison in ["PREFERRED_TEST", "VALID_OR_BETTER_TEST"]:
    part = binary[binary["Comparison"] == comparison]
    assert part["Trades"].sum() == 218
    assert abs(part["Total_PnL"].sum() - (-4631.32)) <= 0.01
print("independent output audit: PASS")
PY
```

Expected: all commands exit 0 and the audit prints `PASS`.

- [ ] **Step 8: Inspect generated evidence for data-quality anomalies only**

Before committing outputs, inspect:
- any RS lag > 7 calendar days;
- any unmatched market/sector context;
- any unexpected empty primary group;
- any reconciliation failure;
- any malformed `inf`/`NaN` serialization that makes CSVs unreadable.

Do **not** alter thresholds or filters because performance looks weak.

- [ ] **Step 9: Commit final artifacts**

```bash
git add "Swing Trading/research/swing/t1_stock_rs_validation"
git commit -m "research: complete T1 stock RS validation"
```

---

## Self-Review Checklist Before Luna Executes

The plan author must verify:

- [x] Primary hypothesis is fixed before outcomes are joined.
- [x] T1 sample remains 218 immutable trades.
- [x] Stock-RS feature definition is reused exactly from merged PR #6.
- [x] `PREFERRED`, `VALID`, `BELOW_VALID` are unchanged.
- [x] Only two primary binary comparisons are allowed.
- [x] Rank 1–20 output is diagnostic only; no optimized cutoff is introduced.
- [x] Strict `RS_Matched_Date < Entry_Date` is enforced and tested.
- [x] Same-day entry context is explicitly forbidden.
- [x] Time, top-1/top-3/top-5 outlier, symbol/status, and leave-one-symbol-out robustness are predeclared.
- [x] Market and sector interactions happen only after primary outputs.
- [x] Market and sector interaction joins also use strict `< Entry_Date` timing.
- [x] Existing market/sector definitions are not recalculated or tuned.
- [x] No unrelated indicators or repository infrastructure are added.
- [x] Research report cannot make the final strategy decision.
- [x] Execution is inline only; subagent-driven development is forbidden.

---

## Execution Handoff

Plan complete at:

```text
docs/superpowers/plans/2026-08-26-t1-stock-rs-validation.md
```

Execute with `superpowers:executing-plans` using **inline execution only**. Work task-by-task, run the specified tests/checks at each checkpoint, and stop on research-integrity failures rather than inventing a workaround. After the validated outputs are committed and a PR is raised, return the PR to the Portfolio Advisor for evidence review and the strategy decision.