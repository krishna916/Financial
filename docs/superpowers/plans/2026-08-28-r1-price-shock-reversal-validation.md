# R1 Price-Shock Reversal Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and historically validate the frozen R1 short-term low-volume price-shock reversal hypothesis with point-in-time Nifty 500 membership, realistic next-open execution, fixed five-session outcomes, a structural-stop practical lens, a high-volume falsification cohort, friction/robustness gates, and artifact-derived research integrity checks.

**Architecture:** Add a self-contained `r1_price_shock_reversal` research module following the repository's established three-stage pattern: feature construction -> signal/entry construction -> outcome/validation analysis. Reuse the committed Nifty 500 membership manifest and adjusted Yahoo OHLCV conventions, but keep R1 logic independent from failed V3 strategy internals so a future change to V3 cannot alter R1 semantics. Generated artifacts are evidence-only; no R1 threshold or filter may be modified after outcomes are observed.

**Tech Stack:** Python 3, pandas, numpy, yfinance, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-28-r1-short-term-price-shock-reversal-design.md`

**Issue:** `https://github.com/krishna916/Financial/issues/19`

## Global Constraints

- Signal window is exactly `2023-08-01` through `2026-08-25` inclusive.
- Use point-in-time Nifty 500 membership from `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`.
- Use Yahoo adjusted OHLCV consistently with `auto_adjust=True`; never mix adjusted/unadjusted fields.
- Primary liquidity gate is prior-20-session median traded value `>= 100_000_000` rupees; the signal day is excluded from the baseline.
- `Return[T] = Close[T] / Close[T-1] - 1`.
- `Sigma20[T]` is the **sample** standard deviation (`ddof=1`) of the 20 prior daily returns `T-20 ... T-1`; the shock-day return is excluded.
- `Shock_Score[T] = Return[T] / Sigma20[T]` and primary large-shock threshold is exactly `<= -2.0`.
- Low-volume R1 cohort requires `Volume_Ratio <= 1.0`, where the denominator is prior-20 median volume excluding the signal day.
- High-volume control cohort requires `Volume_Ratio >= 1.5`; it is not a practical-stop trade cohort.
- Middle-volume shocks `1.0 < Volume_Ratio < 1.5` are diagnostic only.
- Structural stop is exactly `Shock_Day_Low - 0.25 * ATR14_signal`, with Wilder ATR14.
- Each qualified low-volume signal gets one immediate-next-canonical-session Open opportunity. Cancel if next session/bar is unavailable, if same-symbol lifecycle lockout applies, or if `Entry_Open <= Structural_Stop`.
- No upside-gap cancellation/chase rule.
- Primary setup-quality horizon is `T+1 Open` to `T+6 Open` (five complete holding sessions).
- Practical lens uses the same accepted Entry_ID set and the fixed structural stop; no profit target, trailing stop, breakeven move, or SMA exit.
- Same-symbol low-volume lockout lasts until the original signal's scheduled `T+6 Open`, even if the practical trade stops early. The high-volume control has its own independent same-symbol five-session lockout.
- Do not suppress cross-stock overlap; portfolio-capacity/ranking is out of scope.
- Friction rates are frozen at 0.004 base, 0.006 stress, 0.008 severe of entry value.
- Market regime, RS, moving-average state, sector, and other context are diagnostic only and may not gate R1.
- Bootstrap reporting uses 10,000 resamples, RNG seed `20260828`, 95% confidence intervals.
- Any PIT/integrity violation makes the run `INVALID_RESEARCH_RUN`; do not interpret profitability from an invalid run.
- No outcome-driven tuning or rescue. A failed gate means R1 fails as specified.
- Do not modify T1, V2, V3 logic or historical outputs.
- Do not add notebooks, dashboards, CI infrastructure, live trading code, broker integration, or unrelated refactors.

## Locked File Structure

Create exactly this module shape unless an existing filename collision requires an equivalent name:

```text
Swing Trading/research/swing/r1_price_shock_reversal/
├── build_r1_features.py
├── generate_r1_signals.py
├── analyze_r1_results.py
├── README.md
├── tests/
│   ├── test_r1_features.py
│   ├── test_r1_signals.py
│   └── test_r1_analysis.py
└── output/
    ├── r1_data_validation.csv
    ├── r1_shock_candidates.csv
    ├── r1_low_volume_signals.csv
    ├── r1_high_volume_control_signals.csv
    ├── r1_entries.csv
    ├── r1_entry_cancellations.csv
    ├── r1_setup_quality_trades.csv
    ├── r1_practical_trades.csv
    ├── r1_control_outcomes.csv
    ├── r1_forward_diagnostics.csv
    ├── r1_validation_summary.csv
    ├── r1_temporal_summary.csv
    ├── r1_outlier_robustness.csv
    ├── r1_leave_one_symbol_out.csv
    ├── r1_control_comparison.csv
    ├── r1_bootstrap_summary.csv
    ├── r1_overlap_diagnostic.csv
    ├── r1_pit_audit.csv
    ├── r1_validation_gates.csv
    └── research_report.md
```

Do not commit raw Yahoo downloads or all-symbol feature caches.

---

### Task 1: Build adjusted price features and point-in-time membership

**Files:**
- Create: `Swing Trading/research/swing/r1_price_shock_reversal/build_r1_features.py`
- Create: `Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_features.py`
- Generate: `Swing Trading/research/swing/r1_price_shock_reversal/output/r1_data_validation.csv`
- Read only: `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`
- Reference only: `Swing Trading/research/swing/strategy_v3_shallow_pullback/build_v3_features.py`

**Interfaces:**
- Produces `load_membership(path: Path) -> pd.DataFrame`.
- Produces `active_members_on(membership: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame`.
- Produces `download_adjusted_ohlcv(ticker: str, start: str, end_exclusive: str) -> pd.DataFrame`.
- Produces `wilder_atr(true_range: pd.Series, period: int = 14) -> pd.Series`.
- Produces `compute_r1_features(frame: pd.DataFrame) -> pd.DataFrame`.
- Produces `build_feature_frames(membership: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]` where the second value is the per-symbol data audit.

- [ ] **Step 1: Write failing tests for the frozen prior-window semantics**

Add deterministic tests that prove the signal day is excluded from all three prior-20 baselines and that `Sigma20` uses sample standard deviation:

```python
def test_compute_r1_features_excludes_signal_day_from_prior_windows():
    close = pd.Series([100.0 + i for i in range(30)])
    frame = pd.DataFrame({
        "Date": pd.bdate_range("2024-01-01", periods=30),
        "Open": close,
        "High": close + 1.0,
        "Low": close - 1.0,
        "Close": close,
        "Volume": [100.0] * 29 + [10_000.0],
    })
    result = compute_r1_features(frame)
    row = result.iloc[-1]

    returns = close.pct_change()
    expected_sigma = returns.iloc[-21:-1].std(ddof=1)
    expected_volume = pd.Series([100.0] * 20).median()
    traded_value = close * pd.Series([100.0] * 29 + [10_000.0])
    expected_traded = traded_value.iloc[-21:-1].median()

    assert row["Sigma20"] == pytest.approx(expected_sigma)
    assert row["Prior20_Median_Volume"] == pytest.approx(expected_volume)
    assert row["Prior20_Median_Traded_Value"] == pytest.approx(expected_traded)
```

Also add a shock-score test:

```python
def test_shock_score_uses_current_return_over_prior_sigma():
    frame = make_feature_frame_with_nonzero_prior_return_variance()
    result = compute_r1_features(frame)
    row = result.iloc[-1]
    expected_return = row["Close"] / result.iloc[-2]["Close"] - 1.0
    assert row["Return"] == pytest.approx(expected_return)
    assert row["Shock_Score"] == pytest.approx(expected_return / row["Sigma20"])
```

- [ ] **Step 2: Run focused tests and verify they fail before implementation**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_features.py" -k "prior_windows or shock_score"
```

Expected: FAIL because `compute_r1_features` does not yet exist.

- [ ] **Step 3: Implement the frozen feature calculations**

`compute_r1_features()` must implement these expressions exactly:

```python
result["Return"] = result["Close"].pct_change()
result["Sigma20"] = result["Return"].shift(1).rolling(20, min_periods=20).std(ddof=1)
result["Prior20_Median_Volume"] = result["Volume"].shift(1).rolling(20, min_periods=20).median()
result["Daily_Traded_Value"] = result["Close"] * result["Volume"]
result["Prior20_Median_Traded_Value"] = (
    result["Daily_Traded_Value"].shift(1).rolling(20, min_periods=20).median()
)
result["Volume_Ratio"] = result["Volume"] / result["Prior20_Median_Volume"]
result["Shock_Score"] = result["Return"] / result["Sigma20"]
```

Compute Wilder ATR14 from adjusted High/Low/Close exactly as the spec requires. Add diagnostic-only fields in the same function so later analysis does not need to mutate primary eligibility logic:

```python
result["SMA20"] = result["Close"].rolling(20, min_periods=20).mean()
result["SMA50"] = result["Close"].rolling(50, min_periods=50).mean()
result["SMA200"] = result["Close"].rolling(200, min_periods=200).mean()
result["Return21"] = result["Close"] / result["Close"].shift(21) - 1.0
result["Return63"] = result["Close"] / result["Close"].shift(63) - 1.0
result["Return126"] = result["Close"] / result["Close"].shift(126) - 1.0
result["Prior252_High"] = result["Close"].shift(1).rolling(252, min_periods=252).max()
result["Distance_From_Prior252_High"] = result["Close"] / result["Prior252_High"] - 1.0
```

Do **not** use any diagnostic field in primary qualification.

- [ ] **Step 4: Add PIT-membership and adjusted-download tests**

Copy/adapt the already-proven manifest validation/download conventions, but keep the code local to R1. Tests must cover inclusive membership boundaries and reject duplicate/invalid dates:

```python
def test_active_members_on_uses_inclusive_manifest_intervals():
    membership = pd.DataFrame({
        "Symbol": ["AAA"],
        "Member_From": [pd.Timestamp("2024-01-02")],
        "Member_To": [pd.Timestamp("2024-01-05")],
        "Downloadable": [True],
        "Yahoo_Ticker": ["AAA.NS"],
    })
    assert active_members_on(membership, pd.Timestamp("2024-01-02"))["Symbol"].tolist() == ["AAA"]
    assert active_members_on(membership, pd.Timestamp("2024-01-05"))["Symbol"].tolist() == ["AAA"]
```

- [ ] **Step 5: Run all feature tests**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_features.py"
```

Expected: zero failures.

- [ ] **Step 6: Implement `build_feature_frames()` and data-quality artifact**

Download every distinct `Downloadable=True` Yahoo ticker represented in the PIT manifest using at least:

```text
DOWNLOAD_START = 2022-01-01
DOWNLOAD_END_EXCLUSIVE = 2026-08-27
```

This gives enough warmup for ATR, 20-session baselines, SMA200 and diagnostic 252-session context while preserving the frozen signal window.

For each symbol, add `Point_In_Time_Member` by testing each row date against its manifest interval(s). Write `r1_data_validation.csv` with at minimum:

```text
Symbol
Yahoo_Ticker
Raw_Rows
Earliest_Date
Latest_Date
Duplicate_Dates
Missing_Open
Missing_High
Missing_Low
Missing_Close
Missing_Volume
First_Valid_Sigma20_Date
First_Valid_ATR14_Date
Usable
Download_Error
```

A failed ticker remains in the audit; do not silently remove it.

- [ ] **Step 7: Run the feature stage once from the repository root**

```bash
python "Swing Trading/research/swing/r1_price_shock_reversal/build_r1_features.py"
```

Expected: script exits 0 and writes `output/r1_data_validation.csv`.

- [ ] **Step 8: Commit Task 1**

```bash
git add \
  "Swing Trading/research/swing/r1_price_shock_reversal/build_r1_features.py" \
  "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_features.py" \
  "Swing Trading/research/swing/r1_price_shock_reversal/output/r1_data_validation.csv"
git commit -m "research: build R1 price-shock features"
```

---

### Task 2: Generate shock cohorts, qualified signals, entries, and lockouts

**Files:**
- Create: `Swing Trading/research/swing/r1_price_shock_reversal/generate_r1_signals.py`
- Create: `Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_signals.py`
- Generate: `output/r1_shock_candidates.csv`
- Generate: `output/r1_low_volume_signals.csv`
- Generate: `output/r1_high_volume_control_signals.csv`
- Generate: `output/r1_entries.csv`
- Generate: `output/r1_entry_cancellations.csv`

**Interfaces:**
- Consumes feature frames from `build_feature_frames()`.
- Produces `classify_shock_row(row: pd.Series) -> str` returning exactly `LOW_VOLUME`, `MIDDLE_VOLUME`, `HIGH_VOLUME`, or `NOT_ELIGIBLE_SHOCK`.
- Produces `qualified_low_volume_signal(row: pd.Series) -> tuple[bool, str]`.
- Produces `next_session(date: pd.Timestamp, sessions: pd.DatetimeIndex, steps: int = 1) -> pd.Timestamp | None`.
- Produces `build_low_volume_entries(signals, feature_frames, canonical_sessions) -> tuple[pd.DataFrame, pd.DataFrame]`.
- Produces `build_control_signals_and_entries(...) -> tuple[pd.DataFrame, pd.DataFrame]` for the raw high-volume control.

- [ ] **Step 1: Write threshold-boundary tests before implementation**

```python
def test_volume_boundaries_are_frozen():
    low = pd.Series({"Shock_Score": -2.0, "Volume_Ratio": 1.0})
    middle = pd.Series({"Shock_Score": -2.0, "Volume_Ratio": 1.0001})
    high = pd.Series({"Shock_Score": -2.0, "Volume_Ratio": 1.5})
    assert classify_shock_row(low) == "LOW_VOLUME"
    assert classify_shock_row(middle) == "MIDDLE_VOLUME"
    assert classify_shock_row(high) == "HIGH_VOLUME"
```

Add an exact shock threshold test (`-2.0` qualifies, `-1.9999` does not).

- [ ] **Step 2: Run the boundary tests and verify RED**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_signals.py" -k "boundary or threshold"
```

Expected: FAIL before implementation.

- [ ] **Step 3: Implement candidate and low-volume qualification rules**

`r1_shock_candidates.csv` must retain all finite `Shock_Score <= -2.0` sessions in the signal window and include numeric evidence:

```text
Signal_ID
Symbol
Signal_Date
Open
High
Low
Close
Volume
Return
Sigma20
Shock_Score
Prior20_Median_Volume
Volume_Ratio
Prior20_Median_Traded_Value
ATR14_Signal
Point_In_Time_Member
Cohort
Data_Eligible
Liquidity_OK
```

Low-volume qualification must require only:

```python
SIGNAL_START <= Signal_Date <= SIGNAL_END
Point_In_Time_Member is True
Sigma20 is finite and > 0
Shock_Score <= -2.0
Prior20_Median_Volume is finite and > 0
Volume_Ratio <= 1.0
Prior20_Median_Traded_Value >= 100_000_000.0
ATR14_Signal is finite and > 0
```

`ATR14` is required because the approved practical stop cannot be constructed without it; do not replace a missing ATR with another stop.

- [ ] **Step 4: Add immediate-next-session and cancellation-order tests**

Freeze low-volume entry cancellation precedence as:

```text
1. SAME_SYMBOL_LOCKOUT
2. MISSING_NEXT_SESSION
3. MISSING_NEXT_SESSION_BAR
4. OPEN_BELOW_STRUCTURAL_STOP
5. otherwise ACCEPT
```

This ordering makes every qualified signal map to exactly one outcome and ensures lockout is observable even when a later price bar is unavailable.

Tests:

```python
def test_lockout_is_entry_cancellation_not_signal_rejection():
    # First signal is accepted and schedules unlock at T+6 Open.
    # Second same-symbol signal before that date is still qualified,
    # but appears once in cancellations as SAME_SYMBOL_LOCKOUT.
    ...


def test_open_equal_to_structural_stop_is_cancelled():
    signal = make_signal(low=95.0, atr14=4.0)
    # stop = 94.0
    prices = frame_with_next_open(94.0)
    entries, cancellations = build_low_volume_entries(...)
    assert entries.empty
    assert cancellations.iloc[0]["Cancellation_Reason"] == "OPEN_BELOW_STRUCTURAL_STOP"
```

Implement the actual fixture helpers in the test file; do not leave ellipses in committed tests.

- [ ] **Step 5: Implement same-symbol lockout exactly**

For an accepted signal on `T`, compute:

```python
entry_date = next_session(T, canonical_sessions, 1)
scheduled_exit_date = next_session(T, canonical_sessions, 6)
```

Maintain `locked_until[symbol] = scheduled_exit_date`. A later signal is locked only when:

```python
signal_date < locked_until[symbol]
```

A signal occurring on the scheduled exit date itself is allowed because the prior lifecycle exited at that day's Open before the new signal is known at the Close.

A practical early stop must **not** release this lockout.

- [ ] **Step 6: Implement the independent high-volume control lifecycle**

High-volume controls use:

```text
Shock_Score <= -2.0
Volume_Ratio >= 1.5
same PIT/liquidity/data requirements
same immediate-next-open timing
same five-session same-symbol lockout
```

They do **not** use structural-stop cancellation or a practical-stop exit. Their output must retain enough information to calculate `T+1 Open -> T+6 Open` gross return later.

Use a separate `control_locked_until` dictionary so a low-volume R1 trade does not suppress a high-volume control observation and vice versa.

- [ ] **Step 7: Run all signal tests**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_signals.py"
```

Expected: zero failures.

- [ ] **Step 8: Generate signal/entry artifacts and verify accounting**

Run:

```bash
python "Swing Trading/research/swing/r1_price_shock_reversal/generate_r1_signals.py"
```

Programmatically assert before writing final artifacts:

```text
Qualified_Low_Volume_Signals = Accepted_Entries + Entry_Cancellations
```

and every `Signal_ID` appears at most once in accepted/cancelled entry outcomes.

- [ ] **Step 9: Commit Task 2**

```bash
git add \
  "Swing Trading/research/swing/r1_price_shock_reversal/generate_r1_signals.py" \
  "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_signals.py" \
  "Swing Trading/research/swing/r1_price_shock_reversal/output/r1_shock_candidates.csv" \
  "Swing Trading/research/swing/r1_price_shock_reversal/output/r1_low_volume_signals.csv" \
  "Swing Trading/research/swing/r1_price_shock_reversal/output/r1_high_volume_control_signals.csv" \
  "Swing Trading/research/swing/r1_price_shock_reversal/output/r1_entries.csv" \
  "Swing Trading/research/swing/r1_price_shock_reversal/output/r1_entry_cancellations.csv"
git commit -m "research: generate R1 reversal entries"
```

---

### Task 3: Implement fixed-horizon and practical-stop outcomes

**Files:**
- Create/modify: `Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py`
- Create: `Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py`
- Generate: `output/r1_setup_quality_trades.csv`
- Generate: `output/r1_practical_trades.csv`
- Generate: `output/r1_control_outcomes.csv`
- Generate: `output/r1_forward_diagnostics.csv`

**Interfaces:**
- Produces `simulate_setup_quality_trade(entry_row: pd.Series, prices: pd.DataFrame, canonical_sessions: pd.DatetimeIndex) -> dict[str, object] | None`.
- Produces `simulate_practical_trade(...) -> dict[str, object] | None`.
- Produces `simulate_control_outcome(control_row: pd.Series, prices: pd.DataFrame, canonical_sessions: pd.DatetimeIndex) -> dict[str, object] | None`.
- Produces `forward_open_return(entry_open: float, signal_date: pd.Timestamp, sessions: ..., prices: ..., holding_sessions: int) -> float | np.nan`.

- [ ] **Step 1: Write exact session-count tests**

Use a seven-session deterministic fixture where signal is `T`, entry is `T+1`, and fixed exit is `T+6`:

```python
def test_setup_quality_holds_five_complete_sessions():
    prices = make_linear_prices(start="2024-01-02", sessions=7)
    entry = pd.Series({
        "Entry_ID": "AAA-2024-01-02",
        "Signal_Date": prices.loc[0, "Date"],
        "Entry_Date": prices.loc[1, "Date"],
        "Entry_Open": 101.0,
        "Structural_Stop": 90.0,
    })
    trade = simulate_setup_quality_trade(entry, prices, pd.DatetimeIndex(prices["Date"]))
    assert trade["Exit_Date"] == prices.loc[6, "Date"]
    assert trade["Holding_Sessions"] == 5
```

- [ ] **Step 2: Add practical precedence tests**

Cover all frozen cases:

1. Entry-session `Low <= stop` after valid `Entry_Open > stop` exits at stop.
2. Later-session `Open <= stop` exits at actual Open and may be worse than `-1R`.
3. Later-session `Open > stop` but `Low <= stop` exits at stop.
4. No stop through T+5 exits at T+6 Open.

Example:

```python
def test_practical_gap_below_stop_exits_at_gap_open():
    prices = make_trade_prices()
    prices.loc[3, "Open"] = 88.0
    prices.loc[3, "Low"] = 87.0
    entry = make_entry(entry_open=100.0, stop=90.0)
    trade = simulate_practical_trade(entry, prices, pd.DatetimeIndex(prices["Date"]))
    assert trade["Exit_Reason"] == "STOP_GAP"
    assert trade["Exit_Price"] == pytest.approx(88.0)
    assert trade["Gross_R"] == pytest.approx(-1.2)
```

- [ ] **Step 3: Verify RED, then implement both lenses minimally**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py" -k "setup_quality or practical"
```

Expected before implementation: FAIL.

Implement fixed-horizon lookup via canonical session positions, not calendar-day arithmetic.

- [ ] **Step 4: Implement friction fields exactly**

For every completed setup/practical outcome persist:

```python
BASE_FRICTION = 0.004
STRESS_FRICTION = 0.006
SEVERE_FRICTION = 0.008

trade["Base_Net_Return"] = trade["Gross_Return"] - BASE_FRICTION
trade["Stress_Net_Return"] = trade["Gross_Return"] - STRESS_FRICTION
trade["Severe_Net_Return"] = trade["Gross_Return"] - SEVERE_FRICTION
```

For practical R:

```python
for name, c in [("Base", 0.004), ("Stress", 0.006), ("Severe", 0.008)]:
    trade[f"{name}_Net_R"] = (
        (trade["Exit_Price"] - trade["Entry_Open"]) - c * trade["Entry_Open"]
    ) / trade["Initial_Risk"]
```

- [ ] **Step 5: Enforce the paired-completed sample rule**

Generate setup and practical simulations for all accepted entries, but retain an Entry_ID in the **primary completed sample only when the fixed T+6 setup exit can be evaluated**. A practical early stop with missing T+6 setup data stays incomplete and must not enter practical primary metrics.

After filtering, assert:

```python
set(setup_completed["Entry_ID"]) == set(practical_completed["Entry_ID"])
```

- [ ] **Step 6: Implement high-volume raw control outcomes**

For each accepted control observation, calculate only:

```text
Entry = T+1 Open
Exit = T+6 Open
Gross_Return
```

No stop, no structural cancellation, and no friction gate is applied to the mechanism comparison.

- [ ] **Step 7: Freeze forward diagnostics as open-to-open horizons**

Diagnostic horizon `N` means:

```text
Entry = T+1 Open
Diagnostic exit = T+(N+1) Open
```

Persist `Forward_1`, `Forward_3`, `Forward_5`, `Forward_10`, `Forward_20` when those future Opens exist. These fields are diagnostics only.

- [ ] **Step 8: Run complete analysis unit tests**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py"
```

Expected: zero failures.

- [ ] **Step 9: Commit Task 3 code/tests**

```bash
git add \
  "Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py" \
  "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py"
git commit -m "research: simulate R1 reversal outcomes"
```

---

### Task 4: Add metrics, temporal/outlier/LOSO robustness, and control falsification

**Files:**
- Modify: `Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py`
- Modify: `Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py`
- Generate: `output/r1_validation_summary.csv`
- Generate: `output/r1_temporal_summary.csv`
- Generate: `output/r1_outlier_robustness.csv`
- Generate: `output/r1_leave_one_symbol_out.csv`
- Generate: `output/r1_control_comparison.csv`
- Generate: `output/r1_bootstrap_summary.csv`

**Interfaces:**
- Produces `safe_profit_factor(values: pd.Series) -> float`.
- Produces `summary_metrics(trades: pd.DataFrame) -> dict[str, float]`.
- Produces `bootstrap_mean_ci(values: pd.Series, seed: int = 20260828, resamples: int = 10_000) -> tuple[float, float]`.
- Produces `bootstrap_difference_ci(low: pd.Series, high: pd.Series, ...) -> tuple[float, float]`.

- [ ] **Step 1: Add deterministic profit-factor and bootstrap tests**

```python
def test_safe_profit_factor():
    assert safe_profit_factor(pd.Series([2.0, -1.0])) == pytest.approx(2.0)
    assert safe_profit_factor(pd.Series([2.0, 1.0])) == np.inf
    assert safe_profit_factor(pd.Series([-2.0, -1.0])) == 0.0


def test_bootstrap_is_reproducible_with_frozen_seed():
    values = pd.Series([0.01, 0.02, -0.01, 0.03])
    assert bootstrap_mean_ci(values) == bootstrap_mean_ci(values)
```

- [ ] **Step 2: Implement primary summary metrics**

At minimum report for setup and practical samples:

```text
Completed_Trades
Winners
Losers
Win_Rate
Gross_Mean_Return
Gross_Median_Return
Gross_Return_PF
Base_Net_Mean_Return
Base_Net_Return_PF
Stress_Net_Mean_Return
Stress_Net_Return_PF
Severe_Net_Mean_Return
Severe_Net_Return_PF
Practical_Gross_Mean_R
Practical_Gross_R_PF
Practical_Base_Mean_R
Practical_Base_R_PF
Practical_Stress_Mean_R
Practical_Stress_R_PF
```

- [ ] **Step 3: Implement the frozen temporal split**

Use exactly:

```text
FIRST_HALF  = 2023-08-01 through 2025-02-11 inclusive
SECOND_HALF = 2025-02-12 through 2026-08-25 inclusive
```

For each half report completed trades, base-net mean, and base-net PF. Do not move the split.

- [ ] **Step 4: Implement top-five winner removal**

Rank low-volume completed setup trades by **gross return**, remove exactly the top five individual winners, then recompute base-net mean and base-net PF. Persist removed Entry_IDs/Symbols in the artifact.

- [ ] **Step 5: Implement leave-one-symbol-out**

For every symbol represented in the completed low-volume sample, remove all of that symbol's trades and recompute base-net mean and base-net PF. Never use this table to remove a symbol from R1.

- [ ] **Step 6: Implement the high-volume mechanism comparison**

Compare gross five-session setup-quality outcomes only:

```text
Low_Volume_Mean_Return
High_Volume_Mean_Return
Low_Volume_Return_PF
High_Volume_Return_PF
Mean_Difference = Low - High
```

The control gate passes only when both:

```python
low_mean > high_mean
low_pf > high_pf
```

- [ ] **Step 7: Implement frozen bootstrap reporting**

Use `np.random.default_rng(20260828)` and 10,000 resamples. Report percentile 2.5%/97.5% intervals for:

```text
Gross low-volume five-session mean
Base-net low-volume five-session mean
Practical base-net mean R
Low-volume minus high-volume gross mean difference
```

Bootstrap intervals are evidence only; do not invent a p-value gate.

- [ ] **Step 8: Run robustness tests**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py" -k "profit_factor or bootstrap or temporal or outlier or leave_one or control"
```

Expected: zero failures.

- [ ] **Step 9: Commit Task 4**

```bash
git add \
  "Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py" \
  "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py"
git commit -m "research: add R1 robustness analysis"
```

---

### Task 5: Add artifact-derived PIT/integrity audit and overlap diagnostics

**Files:**
- Modify: `Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py`
- Modify: `Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py`
- Generate: `output/r1_pit_audit.csv`
- Generate: `output/r1_overlap_diagnostic.csv`

**Interfaces:**
- Produces `count_integrity_violations(signals, entries, cancellations, setup, practical, controls, feature_frames, membership, canonical_sessions) -> tuple[int, pd.DataFrame]`.
- Produces `overlap_diagnostics(entries: pd.DataFrame, canonical_sessions: pd.DatetimeIndex) -> pd.DataFrame`.

- [ ] **Step 1: Write red tests proving the audit recomputes numeric evidence**

Do not trust convenience booleans. Create fixtures where persisted booleans remain true but numeric values are corrupted:

```python
def test_integrity_audit_recomputes_shock_score():
    fixture = make_integrity_fixture()
    fixture.signals.loc[0, "Shock_Score"] = -9.0
    count, audit = count_integrity_violations(...)
    assert count > 0
    assert "SHOCK_SCORE_MISMATCH" in set(audit["Violation"])


def test_integrity_audit_recomputes_prior_volume_baseline():
    fixture = make_integrity_fixture()
    fixture.signals.loc[0, "Prior20_Median_Volume"] *= 2.0
    count, audit = count_integrity_violations(...)
    assert "PRIOR_VOLUME_MISMATCH" in set(audit["Violation"])
```

- [ ] **Step 2: Implement deterministic numeric tolerance**

Use:

```python
np.isclose(observed, recomputed, rtol=1e-9, atol=1e-12)
```

for numeric audit comparisons.

- [ ] **Step 3: Independently audit every accepted low-volume entry**

Verify at minimum:

```text
Signal_Date inside frozen window
Signal_Date < Entry_Date
PIT membership active on Signal_Date
exactly 20 valid prior returns precede Signal_Date
Sigma20 recomputes from prior returns only
Shock_Score recomputes and <= -2.0
exactly 20 valid prior volume observations precede Signal_Date
prior median volume and Volume_Ratio recompute
Volume_Ratio <= 1.0
exactly 20 valid prior traded-value observations precede Signal_Date
prior median traded value recomputes and >= ₹10cr
ATR14_signal and Shock_Day_Low are signal-date known
Structural_Stop recomputes exactly
Entry_Date is immediate next canonical session
Entry_Open > Structural_Stop
same-symbol lockout is respected
scheduled fixed exit is T+6 canonical Open
setup/practical completed Entry_ID sets are identical
qualified = accepted + cancelled accounting reconciles
```

Use explicit violation codes; deduplicate identical `(Entry_ID, Symbol, Violation)` rows before counting.

- [ ] **Step 4: Audit the high-volume control independently**

At minimum verify PIT membership, liquidity, `Shock_Score <= -2`, `Volume_Ratio >= 1.5`, same-symbol control lockout, immediate-next-open entry, and T+6 fixed exit timing. Do not require R1 structural-stop fields in the control.

- [ ] **Step 5: Implement overlap diagnostics without suppressing signals**

From all accepted low-volume entries, calculate:

```text
Total_Accepted_Entries
Max_Simultaneous_Trades
Average_Simultaneous_Trades
Max_Same_Day_Entries
Entries_Overlapping_Another
Pct_Entries_Overlapping
```

Also export same-day entry-count distribution rows. Use each entry's scheduled T+6 lifecycle for overlap, not its practical early-stop date, because the signal-level experiment reserves the lifecycle for comparison/lockout consistency.

- [ ] **Step 6: Run integrity/overlap tests**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py" -k "integrity or overlap or pit"
```

Expected: zero failures.

- [ ] **Step 7: Commit Task 5**

```bash
git add \
  "Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py" \
  "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py"
git commit -m "research: audit R1 point-in-time integrity"
```

---

### Task 6: Implement frozen validation gates and evidence-only report

**Files:**
- Modify: `Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py`
- Modify: `Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py`
- Create: `Swing Trading/research/swing/r1_price_shock_reversal/README.md`
- Generate: `output/r1_validation_gates.csv`
- Generate: `output/research_report.md`

**Interfaces:**
- Produces `evaluate_validation_gates(...) -> pd.DataFrame`.
- Produces exactly one final formal status: `PASS`, `FAIL`, `INSUFFICIENT_EVIDENCE`, or `INVALID_RESEARCH_RUN`.

- [ ] **Step 1: Add gate-boundary tests**

Create compact synthetic summary fixtures that prove exact threshold semantics. At minimum test:

```text
Completed paired outcomes < 300 -> INSUFFICIENT_EVIDENCE (unless invalid)
PIT/integrity violations > 0 -> INVALID_RESEARCH_RUN
Base net mean exactly 0.002 -> passes +0.20% gate
Base net PF exactly 1.20 -> passes
Stress net mean exactly 0.0 -> fails because requirement is > 0
Practical base mean R exactly 0.15 -> passes
Practical base R-PF exactly 1.20 -> passes
```

- [ ] **Step 2: Implement mandatory gates exactly**

When the research run is valid and completed paired outcomes are at least 300, R1 passes only if all are true:

```text
Gross setup mean return > 0
Base-net setup mean return >= +0.002
Base-net setup Return PF >= 1.20
Stress-net setup mean return > 0
Stress-net setup Return PF > 1.00
Practical base-net mean R >= +0.15R
Practical base-net R-PF >= 1.20
Low-volume gross mean > high-volume gross mean
Low-volume gross PF > high-volume gross PF
Both fixed temporal halves: base-net mean > 0 AND base-net PF > 1.0
After removing top five gross winners: base-net mean > 0 AND base-net PF > 1.0
Every leave-one-symbol-out row: base-net mean > 0 AND base-net PF > 1.0
Zero PIT/integrity violations
```

Status precedence must be:

```text
1. INVALID_RESEARCH_RUN
2. INSUFFICIENT_EVIDENCE
3. PASS if every mandatory gate passes
4. otherwise FAIL
```

- [ ] **Step 3: Generate an evidence-only Markdown report**

`research_report.md` must include factual sections only:

```text
1. Frozen hypothesis/spec reference
2. Data convention/window/PIT universe
3. Data-quality counts
4. Shock/cohort/accounting funnel
5. Low-volume setup-quality metrics
6. Practical-stop metrics
7. Friction sensitivity
8. High-volume control comparison
9. Temporal robustness
10. Top-five winner robustness
11. Leave-one-symbol-out robustness
12. Bootstrap intervals
13. Overlap/capacity diagnostics
14. PIT/integrity audit result
15. Validation gates and formal status
16. Diagnostic-only context summary
```

Do not recommend new thresholds, filters, regime exclusions, or follow-up strategy changes in code/report. Portfolio Advisor will interpret the evidence later.

- [ ] **Step 4: Write README with exact rebuild/test commands**

README commands:

```bash
python "Swing Trading/research/swing/r1_price_shock_reversal/build_r1_features.py"
python "Swing Trading/research/swing/r1_price_shock_reversal/generate_r1_signals.py"
python "Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py"
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests"
```

Explicitly state that raw downloads/full feature caches are not committed and that the report is evidence only.

- [ ] **Step 5: Run the complete deterministic test suite**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests"
```

Expected: zero failures.

- [ ] **Step 6: Commit Task 6**

```bash
git add \
  "Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py" \
  "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py" \
  "Swing Trading/research/swing/r1_price_shock_reversal/README.md"
git commit -m "research: finalize R1 validation gates"
```

---

### Task 7: Regenerate all historical evidence and verify the final branch

**Files:**
- Regenerate every `Swing Trading/research/swing/r1_price_shock_reversal/output/*` artifact listed in the locked file structure.
- Do not hand-edit generated CSV/report outputs.

- [ ] **Step 1: Remove stale R1 outputs only**

From repository root, remove generated files under:

```text
Swing Trading/research/swing/r1_price_shock_reversal/output/
```

Do not remove V1/V2/V3 or shared membership/breadth evidence.

- [ ] **Step 2: Rebuild features from scratch**

```bash
python "Swing Trading/research/swing/r1_price_shock_reversal/build_r1_features.py"
```

Expected: exit 0.

- [ ] **Step 3: Rebuild signals/entries from scratch**

```bash
python "Swing Trading/research/swing/r1_price_shock_reversal/generate_r1_signals.py"
```

Expected: exit 0 and accounting identity holds.

- [ ] **Step 4: Rebuild analysis/gates/report from scratch**

```bash
python "Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py"
```

Expected: exit 0 for a valid research run even when formal strategy status is `FAIL` or `INSUFFICIENT_EVIDENCE`. Exit non-zero only for implementation/data-integrity failures that prevent trustworthy analysis.

- [ ] **Step 5: Run R1 tests after the fresh historical run**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests"
```

Expected: zero failures.

- [ ] **Step 6: Run existing V3 tests as a regression guard**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests"
```

Expected: zero failures. R1 implementation must not break the existing merged research module.

- [ ] **Step 7: Mechanically reconcile final artifacts**

Verify from generated CSVs/report, not memory:

```text
Qualified low-volume signals = accepted entries + cancellations
Completed setup Entry_IDs = completed practical Entry_IDs
PIT/integrity violation count = value reported in gate table
Control sample satisfies only control rules, not practical-stop rules
Temporal split dates are exact
Bootstrap seed/resample count are reported exactly
Every mandatory gate in r1_validation_gates.csv matches the corresponding generated metric
Formal status precedence is correct
```

If any reconciliation fails, stop and fix correctness only. Do not change strategy thresholds.

- [ ] **Step 8: Commit all fresh generated evidence**

```bash
git add "Swing Trading/research/swing/r1_price_shock_reversal"
git commit -m "research: validate R1 price-shock reversal"
```

- [ ] **Step 9: Record final handoff evidence for Issue #19 / PR**

The execution handoff comment should include only mechanically derived facts:

```text
final commit SHA
exact three run commands
test command + pass count
usable/download-failed symbol counts
all-shock / low / middle / high cohort counts
qualified / accepted / cancelled / incomplete / completed paired counts
setup gross/base/stress metrics
practical base/stress R metrics
control comparison metrics
fixed-half temporal metrics
top-five removal metrics
LOSO worst row
bootstrap intervals
PIT/integrity violation count
formal PASS/FAIL/INSUFFICIENT_EVIDENCE/INVALID_RESEARCH_RUN status
paths to report and gate artifacts
```

Do not add a strategy recommendation. Portfolio Advisor owns interpretation after reviewing the evidence.

---

## Plan Self-Review Checklist

Before execution, verify mechanically that the plan still matches the approved spec:

- [ ] No RSI/trend/RS/sector/regime filter entered primary eligibility.
- [ ] Prior 20 return/volume/liquidity windows exclude the shock day.
- [ ] `Sigma20` uses `ddof=1`.
- [ ] Shock threshold remains `-2.0`.
- [ ] Volume thresholds remain `<=1.0` and `>=1.5`.
- [ ] Structural stop remains shock low minus `0.25 ATR14`.
- [ ] Entry remains immediate next Open with no positive-gap cancellation.
- [ ] Fixed setup horizon remains T+6 Open.
- [ ] Same-symbol lockout remains active through scheduled T+6 Open despite early practical stops.
- [ ] Control cohort does not inherit practical-stop cancellation/exit rules.
- [ ] Friction remains 0.40% / 0.60% / 0.80%.
- [ ] Sample threshold remains 300 completed paired trades.
- [ ] Temporal split remains 2025-02-11 / 2025-02-12 boundary.
- [ ] Bootstrap remains 10,000 resamples / seed 20260828 / 95% CI.
- [ ] Invalid research runs abort profitability interpretation.
- [ ] No outcome-based rescue path exists.

## Execution Handoff

Plan execution is **inline only** using `superpowers:executing-plans`. Execute task-by-task with tests and commits at each checkpoint. If historical evidence fails a precommitted strategy gate, preserve the failure and continue only with evidence/report generation; do not tune R1.