# T1 Breadth-Regime Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task using **inline execution only**. Do not use subagent-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independently auditable Nifty 500 market-breadth regime and test whether the fixed T1 breakout sample has a materially stronger edge only during broad momentum-friendly markets.

**Architecture:** Keep breadth construction and T1 outcome validation in separate modules so the market feature is completed and validated before trade returns are loaded. Construct daily Nifty 500 breadth from an explicitly documented constituent universe, combine it with the existing Nifty 500 index SMA200 series using the locked 60/60 thresholds, then strictly backward-match the finished breadth regime to the immutable 218 T1 trades and run only the predeclared comparisons and robustness checks from Issue #9.

**Tech Stack:** Python 3.11+, pandas, numpy, yfinance only where required for stock price history, pytest, standard-library pathlib/hashlib/csv/json as needed.

**Spec:** GitHub Issue #9 — `https://github.com/krishna916/Financial/issues/9`

## Global Constraints

- This is the **final rescue test for T1**, not an optimization pass.
- Validation source is already decided: `CUSTOM_REQUIRED`; Luna does not revisit Streak-vs-custom.
- Breadth construction must not import, load, or inspect T1 trades, returns, or P&L.
- Target universe is Nifty 500 constituents; do not substitute Nifty 50, sectors, or the 20-stock T1 basket.
- Prefer reproducible point-in-time Nifty 500 membership. A fixed-universe proxy may be used only if it is explicitly labeled `FIXED_UNIVERSE_PROXY` and the Portfolio Advisor has accepted that limitation before T1 outcome validation runs.
- Never silently present current constituents as survivorship-free historical membership.
- Use adjusted daily closes for stock SMA50/SMA200 calculations.
- SMA windows are exactly 50 and 200 sessions with full-window `min_periods`.
- Locked breadth thresholds are exactly 60% / 60%.
- Locked coverage rule is `Eligible_Count_200 >= 80% * Universe_Member_Count`.
- Existing Nifty 500 index trend input is `Swing Trading/nifty500_regime_daily.csv`.
- T1 context join is strict-before-entry only: `Breadth_Matched_Date < Entry_Date`.
- No forward match, same-day close, interpolation, result-driven threshold, calendar-period filter, or post-result exclusion is allowed.
- Execution mode is inline only.

---

## Target File Map

Create:

```text
Swing Trading/research/swing/market_breadth/
├── build_nifty500_breadth.py
├── README.md
├── requirements.txt
├── config/
│   └── nifty500_membership.csv
├── tests/
│   └── test_nifty500_breadth.py
└── output/
    ├── nifty500_breadth_daily.csv
    ├── breadth_data_validation.csv
    └── breadth_universe_audit.csv

Swing Trading/research/swing/t1_breadth_regime_validation/
├── analyze_t1_breadth_regime.py
├── README.md
├── tests/
│   └── test_t1_breadth_regime.py
└── output/
    ├── t1_breadth_joined_trades.csv
    ├── t1_breadth_regime_summary.csv
    ├── t1_breadth_binary_tests.csv
    ├── t1_breadth_year_summary.csv
    ├── t1_breadth_outlier_robustness.csv
    ├── t1_breadth_leave_one_symbol_out.csv
    ├── t1_breadth_episode_summary.csv
    ├── validation_report.csv
    └── research_report.md
```

Do not add notebooks, dashboards, CI, generic frameworks, or unrelated refactors.

---

### Task 1: Lock and audit the Nifty 500 membership source before any breadth calculation

**Files:**
- Create: `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`
- Create: `Swing Trading/research/swing/market_breadth/README.md`
- Create: `Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py`

**Interfaces:**
- Membership CSV columns:

```text
Symbol,Yahoo_Ticker,Member_From,Member_To,Source,Universe_Method
```

- `Member_From` inclusive.
- `Member_To` inclusive; blank means still a member through the research end date.
- `Universe_Method` must be identical for all rows and exactly one of `POINT_IN_TIME` or `FIXED_UNIVERSE_PROXY`.

- [ ] **Step 1: Acquire membership from the best reproducible source permitted by Issue #9**

Use this hierarchy exactly:

1. official NSE/Nifty Indices historical constituent/reconstitution material sufficient to establish membership intervals for the 2023-08-01 through 2026-08-25 research window;
2. another reproducible high-quality historical constituent source only if official material cannot mechanically establish the intervals;
3. if neither path can establish point-in-time intervals, stop the point-in-time implementation and document the exact limitation before creating any fixed-universe proxy.

Do not infer entry/exit dates from price history.

- [ ] **Step 2: Normalize symbols mechanically**

Create one row per membership interval. For NSE equity tickers that map normally to Yahoo, use `SYMBOL.NS`. Record explicit exceptions in the CSV rather than coding hidden aliases.

Required validation:

```python
assert set(df["Universe_Method"]) <= {"POINT_IN_TIME", "FIXED_UNIVERSE_PROXY"}
assert df["Universe_Method"].nunique() == 1
assert df["Symbol"].notna().all()
assert df["Yahoo_Ticker"].notna().all()
assert pd.to_datetime(df["Member_From"], errors="coerce").notna().all()
```

For nonblank `Member_To` assert `Member_From <= Member_To`.

- [ ] **Step 3: Add overlap tests**

For every symbol, sorted membership intervals must not overlap. Adjacent intervals may be merged when they represent uninterrupted membership.

Test helper signature:

```python
def validate_membership_intervals(frame: pd.DataFrame) -> None:
    ...
```

Synthetic failing test:

```python
def test_membership_intervals_reject_overlap():
    frame = pd.DataFrame({
        "Symbol": ["AAA", "AAA"],
        "Yahoo_Ticker": ["AAA.NS", "AAA.NS"],
        "Member_From": ["2024-01-01", "2024-06-01"],
        "Member_To": ["2024-06-30", "2024-12-31"],
        "Source": ["x", "x"],
        "Universe_Method": ["POINT_IN_TIME", "POINT_IN_TIME"],
    })
    with pytest.raises(ValueError, match="overlap"):
        validate_membership_intervals(frame)
```

- [ ] **Step 4: Export a source audit in README**

README must state:

```text
Universe_Method: <POINT_IN_TIME or FIXED_UNIVERSE_PROXY>
Research window: 2023-08-01 through 2026-08-25
Membership source(s): <explicit source references>
Known limitations: <explicit factual limitations>
```

Do not claim survivorship-free research if `Universe_Method` is `FIXED_UNIVERSE_PROXY`.

- [ ] **Step 5: Run membership tests**

```bash
python -m pytest "Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py" -v
```

Expected: membership tests PASS before market-price code is added.

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv" \
        "Swing Trading/research/swing/market_breadth/README.md" \
        "Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py"
git commit -m "research: lock Nifty 500 breadth universe"
```

**STOP GATE:** If point-in-time membership cannot be established and no Portfolio-Advisor-approved fixed proxy exists, stop execution here. Do not create T1 validation outputs.

---

### Task 2: Add deterministic membership expansion and price-history rules with TDD

**Files:**
- Create: `Swing Trading/research/swing/market_breadth/build_nifty500_breadth.py`
- Modify: `Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py`
- Create: `Swing Trading/research/swing/market_breadth/requirements.txt`

**Interfaces:**

```python
load_membership(path: Path) -> pd.DataFrame
members_on_date(membership: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame
calculate_stock_smas(frame: pd.DataFrame) -> pd.DataFrame
```

- [ ] **Step 1: Create minimal requirements**

```text
pandas
numpy
pytest
yfinance
```

Do not add libraries already unnecessary for the implementation.

- [ ] **Step 2: Write failing inclusive membership-boundary test**

```python
def test_members_on_date_uses_inclusive_membership_bounds():
    frame = pd.DataFrame({
        "Symbol": ["AAA"],
        "Yahoo_Ticker": ["AAA.NS"],
        "Member_From": pd.to_datetime(["2024-01-01"]),
        "Member_To": pd.to_datetime(["2024-06-30"]),
        "Source": ["x"],
        "Universe_Method": ["POINT_IN_TIME"],
    })
    assert members_on_date(frame, pd.Timestamp("2024-01-01"))["Symbol"].tolist() == ["AAA"]
    assert members_on_date(frame, pd.Timestamp("2024-06-30"))["Symbol"].tolist() == ["AAA"]
    assert members_on_date(frame, pd.Timestamp("2024-07-01")).empty
```

Blank `Member_To` is treated as open-ended.

- [ ] **Step 3: Write failing SMA-window tests**

```python
def test_calculate_stock_smas_requires_full_50_and_200_sessions():
    frame = pd.DataFrame({"Adj_Close": [100.0 + i for i in range(210)]})
    out = calculate_stock_smas(frame)
    assert pd.isna(out.loc[48, "SMA50"])
    assert out.loc[49, "SMA50"] == pytest.approx(sum(100.0 + i for i in range(50)) / 50)
    assert pd.isna(out.loc[198, "SMA200"])
    assert out.loc[199, "SMA200"] == pytest.approx(sum(100.0 + i for i in range(200)) / 200)
```

Implementation must use:

```python
rolling(50, min_periods=50).mean()
rolling(200, min_periods=200).mean()
```

- [ ] **Step 4: Implement minimum code to pass tests**

Do not add breadth classification yet.

- [ ] **Step 5: Run tests**

```bash
python -m pytest "Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py" -v
```

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/market_breadth/build_nifty500_breadth.py" \
        "Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py" \
        "Swing Trading/research/swing/market_breadth/requirements.txt"
git commit -m "research: add breadth membership and SMA rules"
```

---

### Task 3: Download and validate stock histories without synthetic filling

**Files:**
- Modify: `Swing Trading/research/swing/market_breadth/build_nifty500_breadth.py`
- Modify: `Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py`

**Interfaces:**

```python
download_stock_history(yahoo_ticker: str, start: str, end: str) -> pd.DataFrame
normalize_stock_history(raw: pd.DataFrame, symbol: str, yahoo_ticker: str) -> pd.DataFrame
```

- [ ] **Step 1: Lock download window**

To support 200-session SMA before the first T1 trade, download enough warm-up history. Use:

```text
Download start: 2022-08-01
Research-output start: 2023-08-01
Download end: 2026-08-26 (exclusive yfinance end so 2026-08-25 is included)
```

Use daily data and `auto_adjust=False`.

- [ ] **Step 2: Preserve raw Close and Adj Close**

Normalized columns:

```text
Date,Symbol,Yahoo_Ticker,Close,Adj_Close
```

Reject duplicate dates per ticker. Do not forward-fill missing dates or prices.

- [ ] **Step 3: Add tests for no synthetic filling and duplicate-date rejection**

Synthetic input with dates `2026-01-02` and `2026-01-06` must remain exactly two rows after normalization; the missing intervening session is not generated.

- [ ] **Step 4: Add download/audit collection**

For every configured ticker record at minimum:

```text
Symbol
Yahoo_Ticker
Download_Status
Raw_Row_Count
Raw_Date_Min
Raw_Date_Max
Missing_Close_Count
Missing_Adj_Close_Count
Duplicate_Date_Count
```

Do not abort merely because a delisted/renamed historical constituent fails Yahoo; record the failure so breadth coverage rules can decide whether dates remain research-safe.

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/market_breadth/build_nifty500_breadth.py" \
        "Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py"
git commit -m "research: add breadth stock history loading"
```

---

### Task 4: Calculate daily breadth with exact denominators

**Interfaces:**

```python
calculate_daily_breadth(
    membership: pd.DataFrame,
    stock_history: pd.DataFrame,
    research_start: pd.Timestamp,
    research_end: pd.Timestamp,
) -> pd.DataFrame
```

Required daily output before index join:

```text
Date
Universe_Method
Universe_Member_Count
Eligible_Count_50
Eligible_Count_200
Above_SMA50_Count
Above_SMA200_Count
Pct_Above_SMA50
Pct_Above_SMA200
Coverage_200_Pct
Is_Research_Safe
```

- [ ] **Step 1: Write exact-denominator synthetic test**

Construct three universe members where on one date:

```text
AAA: valid SMA50 and SMA200, above both
BBB: valid SMA50 and SMA200, below both
CCC: valid SMA50 but SMA200 unavailable
```

Expected:

```text
Universe_Member_Count = 3
Eligible_Count_50 = 3
Eligible_Count_200 = 2
Above_SMA50_Count = <according to fixture>
Above_SMA200_Count = 1
Pct_Above_SMA200 = 50.0
Coverage_200_Pct = 66.666...
Is_Research_Safe = False
```

- [ ] **Step 2: Implement membership-first denominators**

Only stocks that are members on the date may enter either denominator.

A stock contributes to `Eligible_Count_N` only when:

```text
current Adj_Close is finite
SMA_N is finite
```

Do not count nonmembers even if their price history exists.

- [ ] **Step 3: Implement exact coverage rule**

```python
Coverage_200_Pct = 100.0 * Eligible_Count_200 / Universe_Member_Count
Is_Research_Safe = Coverage_200_Pct >= 80.0
```

If `Universe_Member_Count == 0`, mark row unsafe and breadth percentages `NaN`.

- [ ] **Step 4: Validate bounds**

Fail on:

```text
Pct_Above_SMA50 outside [0,100]
Pct_Above_SMA200 outside [0,100]
Eligible_Count_50 > Universe_Member_Count
Eligible_Count_200 > Universe_Member_Count
Above count > eligible count
```

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/market_breadth/build_nifty500_breadth.py" \
        "Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py"
git commit -m "research: calculate Nifty 500 breadth"
```

---

### Task 5: Join existing Nifty 500 trend and classify the locked breadth regime

**Files:**
- Modify: `Swing Trading/research/swing/market_breadth/build_nifty500_breadth.py`
- Modify: `Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py`

**Interfaces:**

```python
load_nifty500_index_regime(path: Path) -> pd.DataFrame
classify_momentum_regime(row: pd.Series) -> str
join_index_trend(breadth: pd.DataFrame, index_data: pd.DataFrame) -> pd.DataFrame
```

- [ ] **Step 1: Load existing index file only**

Use:

```text
Swing Trading/nifty500_regime_daily.csv
```

Required columns:

```text
Date,Close,SMA200
```

Rename to:

```text
Nifty500_Close,Nifty500_SMA200
```

Reject duplicate dates and invalid numeric values on matched research dates.

- [ ] **Step 2: Write boundary tests before implementation**

Exact classification:

```python
@pytest.mark.parametrize(
    ("close", "sma200", "b50", "b200", "expected"),
    [
        (101, 100, 60.0, 60.0, "STRONG_MOMENTUM"),
        (101, 100, 59.999, 60.0, "NORMAL"),
        (101, 100, 60.0, 59.999, "NORMAL"),
        (100, 100, 90.0, 90.0, "HOSTILE"),
        (99, 100, 90.0, 90.0, "HOSTILE"),
    ],
)
def test_locked_momentum_regime_boundaries(close, sma200, b50, b200, expected):
    ...
```

Classification rule exactly:

```python
if close <= sma200:
    return "HOSTILE"
if b50 >= 60.0 and b200 >= 60.0:
    return "STRONG_MOMENTUM"
return "NORMAL"
```

- [ ] **Step 3: Unsafe breadth rows are not primary regime rows**

When `Is_Research_Safe == False`, preserve calculated/audit fields but set primary `Momentum_Regime` to blank/NA and mark `Regime_Status = INSUFFICIENT_COVERAGE`.

Research-safe rows use `Regime_Status = VALID`.

- [ ] **Step 4: Export independent breadth artifacts**

Write only after validations pass:

```text
output/nifty500_breadth_daily.csv
output/breadth_data_validation.csv
output/breadth_universe_audit.csv
```

`nifty500_breadth_daily.csv` minimum columns:

```text
Date
Universe_Method
Universe_Member_Count
Eligible_Count_50
Eligible_Count_200
Above_SMA50_Count
Above_SMA200_Count
Pct_Above_SMA50
Pct_Above_SMA200
Coverage_200_Pct
Is_Research_Safe
Nifty500_Close
Nifty500_SMA200
Momentum_Regime
Regime_Status
```

- [ ] **Step 5: Prove T1 independence**

The breadth module must contain no import/path/reference to:

```text
t1_trades.csv
Return_Pct
PnL
Holding_Days
```

Add a source-text test that fails if these tokens appear in `build_nifty500_breadth.py` except in an explicit comments/documentation denylist test itself.

- [ ] **Step 6: Run the builder**

```bash
python -m pytest "Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py" -v
python "Swing Trading/research/swing/market_breadth/build_nifty500_breadth.py"
```

Do not continue to Task 6 until the breadth output and audit have been reviewed and the universe method/coverage are acceptable under Issue #9.

- [ ] **Step 7: Commit**

```bash
git add "Swing Trading/research/swing/market_breadth"
git commit -m "research: build locked Nifty 500 breadth regime"
```

---

### Task 6: Scaffold the separate T1 breadth validation with strict timing tests

**Files:**
- Create: `Swing Trading/research/swing/t1_breadth_regime_validation/analyze_t1_breadth_regime.py`
- Create: `Swing Trading/research/swing/t1_breadth_regime_validation/tests/test_t1_breadth_regime.py`

**Interfaces:**

```python
load_and_validate_trades(path: Path) -> pd.DataFrame
load_and_validate_breadth(path: Path) -> pd.DataFrame
join_breadth_strictly_before_entry(trades: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame
calculate_profit_factor(values: pd.Series) -> float
calculate_trade_metrics(frame: pd.DataFrame) -> dict[str, float | int]
```

- [ ] **Step 1: Reuse the immutable T1 invariants, not regenerated trades**

Input:

```text
Swing Trading/research/swing/t1_sector_validation/input/t1_trades.csv
```

Assert:

```text
rows = 218
symbols = 20
winners = 76
total PnL = -4631.32 ± 0.01
mean Return_Pct = -0.0548680341 ± 1e-8
```

Use the existing locked SHA check where practical.

- [ ] **Step 2: Write strict no-lookahead tests**

Synthetic breadth rows:

```text
2026-01-02 STRONG_MOMENTUM
2026-01-05 HOSTILE
```

Trade entry:

```text
2026-01-05
```

Expected matched date/regime:

```text
2026-01-02 / STRONG_MOMENTUM
```

Implement with:

```python
pd.merge_asof(..., direction="backward", allow_exact_matches=False)
```

- [ ] **Step 3: Unsafe breadth rows must never match**

Filter breadth input to:

```text
Is_Research_Safe == true
Regime_Status == VALID
Momentum_Regime in STRONG_MOMENTUM,NORMAL,HOSTILE
```

before as-of joining.

- [ ] **Step 4: Validate joined sample**

Require:

```text
joined rows == 218
unmatched == 0
Breadth_Matched_Date < Entry_Date for every row
Breadth_Date_Lag_Days > 0
```

If unmatched rows exist because research-safe breadth is unavailable, fail with their exact symbols/entry dates. Do not drop them and continue.

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/t1_breadth_regime_validation/analyze_t1_breadth_regime.py" \
        "Swing Trading/research/swing/t1_breadth_regime_validation/tests/test_t1_breadth_regime.py"
git commit -m "research: add strict T1 breadth join"
```

---

### Task 7: Produce only the locked regime and binary comparisons

**Interfaces:**

```python
summarize_regimes(joined: pd.DataFrame) -> pd.DataFrame
summarize_binary_tests(joined: pd.DataFrame) -> pd.DataFrame
```

- [ ] **Step 1: Three-regime summary**

Order exactly:

```text
STRONG_MOMENTUM
NORMAL
HOSTILE
```

Standard metrics:

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

Export:

```text
output/t1_breadth_regime_summary.csv
```

- [ ] **Step 2: Binary tests exactly**

```text
STRONG_TEST:
    STRONG_MOMENTUM
    NON_STRONG = NORMAL + HOSTILE

HOSTILE_TEST:
    HOSTILE
    NON_HOSTILE = STRONG_MOMENTUM + NORMAL
```

Export:

```text
output/t1_breadth_binary_tests.csv
```

No other thresholds or regime combinations.

- [ ] **Step 3: Reconciliation**

Each binary partition must sum to 218 trades and total PnL `-4631.32 ± 0.01`.

- [ ] **Step 4: Commit**

```bash
git add "Swing Trading/research/swing/t1_breadth_regime_validation"
git commit -m "research: add locked breadth regime comparisons"
```

---

### Task 8: Add predeclared time, outlier, stock-identity, and episode robustness

**Interfaces:**

```python
summarize_by_entry_year(joined: pd.DataFrame) -> pd.DataFrame
summarize_outlier_robustness(joined: pd.DataFrame) -> pd.DataFrame
summarize_leave_one_symbol_out(joined: pd.DataFrame) -> pd.DataFrame
summarize_strong_episodes(breadth: pd.DataFrame, joined: pd.DataFrame) -> pd.DataFrame
```

- [ ] **Step 1: Year stability**

For years 2023, 2024, 2025, 2026, calculate only `STRONG_MOMENTUM vs NON_STRONG`.

Export:

```text
output/t1_breadth_year_summary.csv
```

- [ ] **Step 2: Outlier scenarios**

Exactly:

```text
ALL_TRADES
EXCLUDE_TOP_1_POSITIVE_PNL
EXCLUDE_TOP_3_POSITIVE_PNL
EXCLUDE_TOP_5_POSITIVE_PNL
```

Remove globally largest positive-PnL trades using deterministic tie-break ordering:

```text
PnL descending, Entry_Date ascending, Symbol ascending, Exit_Date ascending
```

Export excluded `Symbol|Entry_Date|PnL` audit text.

- [ ] **Step 3: Leave-one-symbol-out**

For each of the fixed 20 symbols, exclude that symbol and recompute only `STRONG_MOMENTUM vs NON_STRONG`.

Export:

```text
output/t1_breadth_leave_one_symbol_out.csv
```

- [ ] **Step 4: Strong-regime episodes**

Using research-safe daily breadth rows sorted by date, create an episode boundary whenever consecutive `STRONG_MOMENTUM` rows are not adjacent available trading dates in the breadth dataset or when regime changes away from strong.

For each episode export:

```text
Episode_ID
Start_Date
End_Date
Trading_Sessions
T1_Trades
Mean_T1_Return
Total_T1_PnL
```

Also include aggregate rows/fields for:

```text
Episode_Count
Median_Episode_Sessions
Max_Episode_Sessions
```

This is diagnostic only. Do not impose an episode-duration entry rule.

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/t1_breadth_regime_validation"
git commit -m "research: add breadth regime robustness"
```

---

### Task 9: Compare factual separation with the earlier simple market regime

**Files:**
- Modify: `Swing Trading/research/swing/t1_breadth_regime_validation/analyze_t1_breadth_regime.py`
- Modify: `Swing Trading/research/swing/t1_breadth_regime_validation/tests/test_t1_breadth_regime.py`

- [ ] **Step 1: Load the existing strict-timing market-regime interaction output only for comparison**

Preferred existing evidence source after PR #8 merge:

```text
Swing Trading/research/swing/t1_stock_rs_validation/output/t1_stock_rs_market_matrix.csv
```

Use the regime-wide rows to reconstruct factual T1 performance by `RISK_ON`, `MIXED`, `RISK_OFF` only when their trade partitions reconcile to 218.

If this artifact structure does not support clean regime-wide reconstruction, calculate the strict simple regime comparison again from `nifty500_regime_daily.csv` using the same `< Entry_Date` timing. Do not use the older same-day sector-validation join.

- [ ] **Step 2: Report, do not optimize**

Research report must show side-by-side:

```text
Simple regime: RISK_ON / MIXED / RISK_OFF
Breadth regime: STRONG_MOMENTUM / NORMAL / HOSTILE
```

Compare trade count, mean return, return PF, PnL PF, and total PnL.

Do not create a numeric score and tune the breadth definition to maximize separation.

- [ ] **Step 3: Commit**

```bash
git add "Swing Trading/research/swing/t1_breadth_regime_validation"
git commit -m "research: compare breadth and simple regimes"
```

---

### Task 10: Validate all outputs and write evidence-only report

**Files:**
- Create: `Swing Trading/research/swing/t1_breadth_regime_validation/README.md`
- Create: `Swing Trading/research/swing/t1_breadth_regime_validation/output/validation_report.csv`
- Create: `Swing Trading/research/swing/t1_breadth_regime_validation/output/research_report.md`

- [ ] **Step 1: Final machine-readable validation report**

Include at minimum:

```text
Input_Trade_Count
Unique_Symbols
Input_Total_PnL
Breadth_Universe_Method
Breadth_Research_Safe_Dates
Unmatched_Breadth_Trades
Same_Day_Breadth_Matches
Future_Breadth_Matches
Median_Breadth_Lag_Days
Max_Breadth_Lag_Days
Breadth_Lag_Over_7_Days_Count
Regime_Count_Reconciles
Regime_PnL_Reconciles
Strong_Test_Count_Reconciles
Strong_Test_PnL_Reconciles
Hostile_Test_Count_Reconciles
Hostile_Test_PnL_Reconciles
```

All same-day/future/unmatched values must be zero for a complete primary analysis.

- [ ] **Step 2: Evidence-only research report**

Report:

1. universe method and limitations;
2. breadth data coverage;
3. unfiltered T1 baseline;
4. three regime results;
5. `STRONG_MOMENTUM vs NON_STRONG`;
6. `HOSTILE vs NON_HOSTILE`;
7. year stability;
8. top-1/3/5 winner robustness;
9. leave-one-symbol-out range;
10. strong-regime episode count/duration/trade distribution;
11. factual comparison with simple index regime.

The report must explicitly say:

```text
Final keep/retire decision is outside this script and belongs to the Portfolio Advisor review.
```

Do not automatically declare the rescue successful based on thresholds.

- [ ] **Step 3: README commands**

From repo root:

```bash
python -m pytest "Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py" -v
python "Swing Trading/research/swing/market_breadth/build_nifty500_breadth.py"
python -m pytest "Swing Trading/research/swing/t1_breadth_regime_validation/tests/test_t1_breadth_regime.py" -v
python "Swing Trading/research/swing/t1_breadth_regime_validation/analyze_t1_breadth_regime.py"
```

- [ ] **Step 4: Full verification**

Run both focused suites and any existing repository research tests that are directly affected. Confirm zero failures from fresh output.

Then re-run both builders/analyses and confirm generated artifacts are deterministic for unchanged inputs.

- [ ] **Step 5: Self-review against Issue #9**

Check explicitly:

- no 55/65/70 breadth threshold appears in classification code;
- no T1 import/reference exists in breadth builder;
- no same-day matching exists;
- no 20-stock market-breadth shortcut exists;
- no losing/event trade exclusion exists;
- no post-result minimum episode duration exists;
- no RSI/ADX/MACD/ATR/volume/stock-RS/sector-RS filter was added;
- all deliverables required by Issue #9 exist or a documented stop gate prevented validation.

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/market_breadth" \
        "Swing Trading/research/swing/t1_breadth_regime_validation"
git commit -m "research: complete T1 breadth regime validation"
```

---

## Execution Handoff

Execute this plan using `superpowers:executing-plans` with **inline execution only**.

The required sequence is:

```text
1. Lock/audit Nifty 500 membership.
2. Build and validate breadth WITHOUT T1 data.
3. Stop if universe integrity/coverage is not research-safe.
4. Only after breadth is frozen, load the immutable 218 T1 trades.
5. Run the locked strict-before-entry comparisons and robustness checks.
6. Raise a PR containing factual outputs only.
7. Portfolio Advisor reviews the PR and applies the precommitted keep/retire gate.
```

Luna must not make strategy decisions, optimize parameters, or weaken the stop/decision gates.