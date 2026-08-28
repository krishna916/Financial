# R1 Price-Shock Reversal Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and historically validate the frozen R1 low-volume price-shock reversal hypothesis with point-in-time Nifty 500 membership, realistic next-open execution, fixed five-session outcomes, a structural-stop practical lens, a high-volume falsification cohort, friction/robustness gates, and artifact-derived integrity checks.

**Architecture:** Add a self-contained `r1_price_shock_reversal` research module using the repository's established three-stage pattern: feature construction, signal/entry construction, then outcome/validation analysis. Reuse the committed point-in-time membership manifest and adjusted Yahoo OHLCV convention, but keep R1 logic independent from V3 implementation code so future changes to failed momentum research cannot alter R1 semantics. Generated outputs are evidence only; no threshold/filter may change after outcomes are observed.

**Tech Stack:** Python 3, pandas, numpy, yfinance, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-28-r1-short-term-price-shock-reversal-design.md`

**Issue:** `https://github.com/krishna916/Financial/issues/19`

## Global Constraints

- Signal window: `2023-08-01` through `2026-08-25` inclusive.
- PIT membership source: `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`.
- Adjusted daily OHLCV only: Yahoo `auto_adjust=True`.
- Prior-20 median traded value must be at least `100_000_000` rupees, excluding the signal day.
- `Return[T] = Close[T] / Close[T-1] - 1`.
- `Sigma20[T]` is the sample standard deviation (`ddof=1`) of exactly the 20 returns before `T`.
- `Shock_Score[T] = Return[T] / Sigma20[T]` and must be `<= -2.0`.
- Low-volume R1 cohort: `Volume_Ratio <= 1.0`, using prior-20 median volume excluding `T`.
- High-volume control: `Volume_Ratio >= 1.5` with the same shock/PIT/liquidity rules.
- Middle-volume shocks are diagnostic only.
- Wilder ATR14 is frozen; structural stop is `Shock_Day_Low - 0.25 * ATR14_signal`.
- Entry is the immediate next canonical-session Open.
- Low-volume cancellation reasons are `SAME_SYMBOL_LOCKOUT`, `MISSING_NEXT_SESSION`, `MISSING_NEXT_SESSION_BAR`, and `OPEN_BELOW_STRUCTURAL_STOP`.
- No positive-gap/chase cancellation.
- Setup-quality horizon is `T+1 Open` to `T+6 Open`, five complete holding sessions.
- Practical lens uses the same accepted Entry_ID set and the fixed structural stop. No profit target, SMA exit, breakeven move, or trailing stop.
- Same-symbol low-volume lockout remains active until scheduled `T+6 Open` even if the practical trade stops early.
- High-volume controls have a separate same-symbol five-session lockout and no structural-stop cancellation/exit.
- Cross-stock overlaps are retained; portfolio-capacity/ranking is out of scope.
- Friction rates: base `0.004`, stress `0.006`, severe `0.008` of entry value.
- Bootstrap: 10,000 resamples, RNG seed `20260828`, 95% percentile CI.
- Diagnostics cannot become R1 filters.
- Any mandatory integrity failure produces `INVALID_RESEARCH_RUN` and blocks profitability interpretation.
- Do not modify T1/V2/V3 code or outputs.
- Do not add notebooks, dashboards, CI, broker integration, live trading, or unrelated refactors.

## Locked File Structure

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

### Task 1: Build adjusted R1 features and PIT membership

**Files:**
- Create: `Swing Trading/research/swing/r1_price_shock_reversal/build_r1_features.py`
- Create: `Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_features.py`
- Generate: `Swing Trading/research/swing/r1_price_shock_reversal/output/r1_data_validation.csv`
- Read only: `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`
- Reference only: `Swing Trading/research/swing/strategy_v3_shallow_pullback/build_v3_features.py`

**Interfaces:**
- `load_membership(path: Path) -> pd.DataFrame`
- `active_members_on(membership: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame`
- `download_adjusted_ohlcv(ticker: str, start: str, end_exclusive: str) -> pd.DataFrame`
- `wilder_atr(true_range: pd.Series, period: int = 14) -> pd.Series`
- `compute_r1_features(frame: pd.DataFrame) -> pd.DataFrame`
- `build_feature_frames(membership: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]`

- [ ] **Step 1: Write failing prior-window tests**

Add this deterministic test skeleton and define all imports in the test file:

```python
def test_prior_20_windows_exclude_signal_day():
    dates = pd.bdate_range("2024-01-01", periods=30)
    close = pd.Series([100, 102, 101, 103, 102, 104, 103, 105, 104, 106,
                       105, 107, 106, 108, 107, 109, 108, 110, 109, 111,
                       110, 112, 111, 113, 112, 114, 113, 115, 114, 90], dtype=float)
    volume = pd.Series([100.0] * 29 + [10_000.0])
    frame = pd.DataFrame({
        "Date": dates,
        "Open": close,
        "High": close + 1.0,
        "Low": close - 1.0,
        "Close": close,
        "Volume": volume,
    })

    result = compute_r1_features(frame)
    row = result.iloc[-1]
    returns = close.pct_change()

    assert row["Sigma20"] == pytest.approx(returns.iloc[-21:-1].std(ddof=1))
    assert row["Prior20_Median_Volume"] == pytest.approx(volume.iloc[-21:-1].median())
    traded = close * volume
    assert row["Prior20_Median_Traded_Value"] == pytest.approx(traded.iloc[-21:-1].median())
    assert row["Return"] == pytest.approx(close.iloc[-1] / close.iloc[-2] - 1.0)
    assert row["Shock_Score"] == pytest.approx(row["Return"] / row["Sigma20"])
```

- [ ] **Step 2: Run the test and verify RED**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_features.py::test_prior_20_windows_exclude_signal_day"
```

Expected: FAIL before `compute_r1_features` exists.

- [ ] **Step 3: Implement the frozen feature formulas**

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

Compute True Range and Wilder ATR14 using:

```python
previous_close = result["Close"].shift(1)
true_range = pd.concat([
    result["High"] - result["Low"],
    (result["High"] - previous_close).abs(),
    (result["Low"] - previous_close).abs(),
], axis=1).max(axis=1)
result["ATR14"] = wilder_atr(true_range, 14)
```

Add diagnostic-only `SMA20`, `SMA50`, `SMA200`, `Return21`, `Return63`, `Return126`, and prior-252-session high/distance fields. Never read those fields in primary qualification.

- [ ] **Step 4: Add membership/download tests**

Use an inclusive interval test:

```python
def test_active_members_on_uses_inclusive_boundaries():
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

Also test rejection of invalid/duplicate Yahoo dates.

- [ ] **Step 5: Implement feature-frame build and audit**

Use:

```text
DOWNLOAD_START = 2022-01-01
DOWNLOAD_END_EXCLUSIVE = 2026-08-27
```

For each downloadable PIT symbol, download adjusted OHLCV, compute features, and persist `Point_In_Time_Member` for each date. Write `r1_data_validation.csv` with:

```text
Symbol, Yahoo_Ticker, Raw_Rows, Earliest_Date, Latest_Date,
Duplicate_Dates, Missing_Open, Missing_High, Missing_Low,
Missing_Close, Missing_Volume, First_Valid_Sigma20_Date,
First_Valid_ATR14_Date, Usable, Download_Error
```

Download failures remain visible in the audit.

- [ ] **Step 6: Run Task 1 verification**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_features.py"
python "Swing Trading/research/swing/r1_price_shock_reversal/build_r1_features.py"
```

Expected: zero test failures; feature stage exits 0.

- [ ] **Step 7: Commit Task 1**

```bash
git add "Swing Trading/research/swing/r1_price_shock_reversal/build_r1_features.py" \
        "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_features.py" \
        "Swing Trading/research/swing/r1_price_shock_reversal/output/r1_data_validation.csv"
git commit -m "research: build R1 price-shock features"
```

---

### Task 2: Generate low/middle/high shock cohorts and one-shot entries

**Files:**
- Create: `Swing Trading/research/swing/r1_price_shock_reversal/generate_r1_signals.py`
- Create: `Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_signals.py`
- Generate: `output/r1_shock_candidates.csv`
- Generate: `output/r1_low_volume_signals.csv`
- Generate: `output/r1_high_volume_control_signals.csv`
- Generate: `output/r1_entries.csv`
- Generate: `output/r1_entry_cancellations.csv`

**Interfaces:**
- `classify_shock_row(row: pd.Series) -> str`
- `qualify_low_volume_signal(row: pd.Series) -> tuple[bool, str]`
- `next_session(date: pd.Timestamp, sessions: pd.DatetimeIndex, steps: int = 1) -> pd.Timestamp | None`
- `build_low_volume_entries(signals: pd.DataFrame, feature_frames: dict[str, pd.DataFrame], canonical_sessions: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]`
- `build_control_entries(signals: pd.DataFrame, feature_frames: dict[str, pd.DataFrame], canonical_sessions: pd.DatetimeIndex) -> pd.DataFrame`

- [ ] **Step 1: Write threshold-boundary tests**

```python
def test_shock_and_volume_boundaries_are_exact():
    assert classify_shock_row(pd.Series({"Shock_Score": -2.0, "Volume_Ratio": 1.0})) == "LOW_VOLUME"
    assert classify_shock_row(pd.Series({"Shock_Score": -2.0, "Volume_Ratio": 1.0001})) == "MIDDLE_VOLUME"
    assert classify_shock_row(pd.Series({"Shock_Score": -2.0, "Volume_Ratio": 1.5})) == "HIGH_VOLUME"
    assert classify_shock_row(pd.Series({"Shock_Score": -1.9999, "Volume_Ratio": 1.0})) == "NOT_ELIGIBLE_SHOCK"
```

- [ ] **Step 2: Run RED boundary test**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_signals.py::test_shock_and_volume_boundaries_are_exact"
```

Expected: FAIL before implementation.

- [ ] **Step 3: Implement candidate schema and low-volume qualification**

Retain every finite shock `Shock_Score <= -2.0` in `r1_shock_candidates.csv` with:

```text
Signal_ID, Symbol, Signal_Date, Open, High, Low, Close, Volume,
Return, Sigma20, Shock_Score, Prior20_Median_Volume, Volume_Ratio,
Prior20_Median_Traded_Value, ATR14_Signal, Point_In_Time_Member,
Cohort, Data_Eligible, Liquidity_OK
```

Low-volume qualification requires only the frozen signal window, active PIT membership, valid `Sigma20 > 0`, `Shock_Score <= -2.0`, valid prior-volume denominator, `Volume_Ratio <= 1.0`, prior median traded value at least ₹10 crore, and valid `ATR14_Signal > 0` so the approved structural stop can be calculated.

- [ ] **Step 4: Write concrete cancellation/lockout tests**

Use this full lockout test structure:

```python
def test_second_signal_before_unlock_is_cancelled_as_lockout():
    sessions = pd.bdate_range("2024-01-01", periods=12)
    signals = pd.DataFrame([
        {"Signal_ID": "AAA-1", "Symbol": "AAA", "Signal_Date": sessions[0],
         "Low": 95.0, "ATR14_Signal": 4.0},
        {"Signal_ID": "AAA-2", "Symbol": "AAA", "Signal_Date": sessions[3],
         "Low": 96.0, "ATR14_Signal": 4.0},
    ])
    prices = pd.DataFrame({"Date": sessions, "Open": [100.0] * 12})
    entries, cancellations = build_low_volume_entries(
        signals,
        {"AAA": prices},
        pd.DatetimeIndex(sessions),
    )
    assert entries["Signal_ID"].tolist() == ["AAA-1"]
    row = cancellations.loc[cancellations["Signal_ID"].eq("AAA-2")].iloc[0]
    assert row["Cancellation_Reason"] == "SAME_SYMBOL_LOCKOUT"
```

Use this structural boundary test:

```python
def test_entry_open_equal_to_structural_stop_is_cancelled():
    sessions = pd.bdate_range("2024-01-01", periods=8)
    signals = pd.DataFrame([
        {"Signal_ID": "AAA-1", "Symbol": "AAA", "Signal_Date": sessions[0],
         "Low": 95.0, "ATR14_Signal": 4.0},
    ])
    prices = pd.DataFrame({"Date": sessions, "Open": [100.0, 94.0] + [100.0] * 6})
    entries, cancellations = build_low_volume_entries(
        signals,
        {"AAA": prices},
        pd.DatetimeIndex(sessions),
    )
    assert entries.empty
    assert cancellations.iloc[0]["Cancellation_Reason"] == "OPEN_BELOW_STRUCTURAL_STOP"
```

- [ ] **Step 5: Implement cancellation precedence and lockout**

For low-volume signals evaluate exactly:

```text
1. SAME_SYMBOL_LOCKOUT
2. MISSING_NEXT_SESSION
3. MISSING_NEXT_SESSION_BAR
4. OPEN_BELOW_STRUCTURAL_STOP
5. ACCEPT
```

For accepted `T`, store `locked_until[symbol] = next_session(T, sessions, 6)`. A later signal is locked only when `signal_date < locked_until[symbol]`. A signal on the scheduled exit date is allowed because the old lifecycle exited at that day's Open before the new Close signal exists.

- [ ] **Step 6: Implement independent high-volume control entries**

Use the same shock/PIT/liquidity/data rules and immediate-next-open timing, but no structural-stop cancellation. Maintain a separate `control_locked_until`. Control observations do not suppress low-volume R1 signals and vice versa.

- [ ] **Step 7: Generate and reconcile artifacts**

Before writing outputs assert:

```text
Qualified_R1_Signals = Accepted_Entries + Entry_Cancellations
```

Every qualified low-volume Signal_ID must appear exactly once in accepted or cancelled outcomes.

- [ ] **Step 8: Run Task 2 verification**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_signals.py"
python "Swing Trading/research/swing/r1_price_shock_reversal/generate_r1_signals.py"
```

Expected: zero test failures; signal stage exits 0.

- [ ] **Step 9: Commit Task 2**

```bash
git add "Swing Trading/research/swing/r1_price_shock_reversal/generate_r1_signals.py" \
        "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_signals.py" \
        "Swing Trading/research/swing/r1_price_shock_reversal/output/r1_shock_candidates.csv" \
        "Swing Trading/research/swing/r1_price_shock_reversal/output/r1_low_volume_signals.csv" \
        "Swing Trading/research/swing/r1_price_shock_reversal/output/r1_high_volume_control_signals.csv" \
        "Swing Trading/research/swing/r1_price_shock_reversal/output/r1_entries.csv" \
        "Swing Trading/research/swing/r1_price_shock_reversal/output/r1_entry_cancellations.csv"
git commit -m "research: generate R1 reversal entries"
```

---

### Task 3: Simulate fixed-horizon, practical, control, and forward outcomes

**Files:**
- Create: `Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py`
- Create: `Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py`
- Generate: `output/r1_setup_quality_trades.csv`
- Generate: `output/r1_practical_trades.csv`
- Generate: `output/r1_control_outcomes.csv`
- Generate: `output/r1_forward_diagnostics.csv`

**Interfaces:**
- `simulate_setup_quality_trade(entry_row: pd.Series, prices: pd.DataFrame, canonical_sessions: pd.DatetimeIndex) -> dict[str, object] | None`
- `simulate_practical_trade(entry_row: pd.Series, prices: pd.DataFrame, canonical_sessions: pd.DatetimeIndex) -> dict[str, object] | None`
- `simulate_control_outcome(control_row: pd.Series, prices: pd.DataFrame, canonical_sessions: pd.DatetimeIndex) -> dict[str, object] | None`
- `forward_open_return(entry_open: float, signal_date: pd.Timestamp, canonical_sessions: pd.DatetimeIndex, prices: pd.DataFrame, holding_sessions: int) -> float`

- [ ] **Step 1: Write exact five-session test**

```python
def test_setup_exit_is_t_plus_6_open():
    dates = pd.bdate_range("2024-01-01", periods=7)
    prices = pd.DataFrame({
        "Date": dates,
        "Open": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
        "High": [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
        "Low": [99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
    })
    entry = pd.Series({
        "Entry_ID": "AAA-2024-01-01",
        "Signal_Date": dates[0],
        "Entry_Date": dates[1],
        "Entry_Open": 101.0,
        "Structural_Stop": 90.0,
    })
    trade = simulate_setup_quality_trade(entry, prices, pd.DatetimeIndex(dates))
    assert trade["Exit_Date"] == dates[6]
    assert trade["Exit_Price"] == pytest.approx(106.0)
    assert trade["Holding_Sessions"] == 5
```

- [ ] **Step 2: Write practical precedence tests**

At minimum cover entry-session intraday stop, later gap below stop, later intraday stop, and fixed T+6 exit. Example gap test:

```python
def test_practical_gap_below_stop_exits_at_actual_open():
    dates = pd.bdate_range("2024-01-01", periods=7)
    prices = pd.DataFrame({
        "Date": dates,
        "Open": [100.0, 100.0, 100.0, 88.0, 100.0, 100.0, 100.0],
        "High": [101.0] * 7,
        "Low": [99.0, 95.0, 95.0, 87.0, 95.0, 95.0, 95.0],
    })
    entry = pd.Series({
        "Entry_ID": "AAA-1", "Signal_Date": dates[0], "Entry_Date": dates[1],
        "Entry_Open": 100.0, "Structural_Stop": 90.0,
    })
    trade = simulate_practical_trade(entry, prices, pd.DatetimeIndex(dates))
    assert trade["Exit_Reason"] == "STOP_GAP"
    assert trade["Exit_Price"] == pytest.approx(88.0)
    assert trade["Gross_R"] == pytest.approx(-1.2)
```

- [ ] **Step 3: Implement fixed-session lookup and both low-volume lenses**

Use canonical session positions, never calendar-day arithmetic. Entry session is `T+1`; fixed exit is `T+6`. On entry day, after a valid `Entry_Open > Structural_Stop`, an intraday `Low <= Structural_Stop` exits at the stop. On later sessions apply Open-before-Low precedence.

- [ ] **Step 4: Add frozen friction fields**

```python
BASE_FRICTION = 0.004
STRESS_FRICTION = 0.006
SEVERE_FRICTION = 0.008

trade["Base_Net_Return"] = trade["Gross_Return"] - BASE_FRICTION
trade["Stress_Net_Return"] = trade["Gross_Return"] - STRESS_FRICTION
trade["Severe_Net_Return"] = trade["Gross_Return"] - SEVERE_FRICTION
```

Practical R fields:

```python
for label, friction in (("Base", 0.004), ("Stress", 0.006), ("Severe", 0.008)):
    trade[f"{label}_Net_R"] = (
        (trade["Exit_Price"] - trade["Entry_Open"]) - friction * trade["Entry_Open"]
    ) / trade["Initial_Risk"]
```

- [ ] **Step 5: Enforce paired completion**

Only entries with evaluable T+6 setup exits enter the primary completed sample. A practical trade that stops early but lacks T+6 setup data remains incomplete. Assert exact Entry_ID equality between completed setup and practical files.

- [ ] **Step 6: Implement raw high-volume control outcomes**

Control output uses only `T+1 Open` to `T+6 Open` gross return. No structural stop, no practical exit, and no friction gate.

- [ ] **Step 7: Freeze diagnostic forward returns**

For holding horizon `N`, use Entry `T+1 Open` and diagnostic exit `T+(N+1) Open`. Persist N = 1, 3, 5, 10, 20 when data exists.

- [ ] **Step 8: Run Task 3 verification and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py" -k "setup or practical or control or forward"
git add "Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py" \
        "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py"
git commit -m "research: simulate R1 reversal outcomes"
```

---

### Task 4: Add metrics, falsification, bootstrap, temporal, outlier, and LOSO robustness

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
- `safe_profit_factor(values: pd.Series) -> float`
- `bootstrap_mean_ci(values: pd.Series, seed: int = 20260828, resamples: int = 10_000) -> tuple[float, float]`
- `bootstrap_difference_ci(low: pd.Series, high: pd.Series, seed: int = 20260828, resamples: int = 10_000) -> tuple[float, float]`

- [ ] **Step 1: Add metric/bootstrap tests**

```python
def test_safe_profit_factor_boundaries():
    assert safe_profit_factor(pd.Series([2.0, -1.0])) == pytest.approx(2.0)
    assert safe_profit_factor(pd.Series([2.0, 1.0])) == np.inf
    assert safe_profit_factor(pd.Series([-2.0, -1.0])) == 0.0


def test_bootstrap_is_deterministic():
    values = pd.Series([0.01, 0.02, -0.01, 0.03])
    assert bootstrap_mean_ci(values) == bootstrap_mean_ci(values)
```

- [ ] **Step 2: Implement primary metrics**

Report completed count, winners/losers, win rate, gross mean/median/PF, base/stress/severe net mean/PF, practical gross mean R/PF, and practical base/stress/severe net mean R/PF.

- [ ] **Step 3: Implement exact temporal split**

```text
First half:  2023-08-01 through 2025-02-11 inclusive
Second half: 2025-02-12 through 2026-08-25 inclusive
```

Each half reports base-net mean and base-net PF.

- [ ] **Step 4: Implement top-five winner removal and LOSO**

Remove the five largest **gross-return** setup winners, then recompute base-net mean/PF. For LOSO, remove every represented symbol one at a time and recompute base-net mean/PF. Persist omitted symbol and remaining trade count.

- [ ] **Step 5: Implement high-volume falsification comparison**

Compare gross five-session means and PFs. The mechanism gate requires low-volume mean > high-volume mean **and** low-volume PF > high-volume PF.

- [ ] **Step 6: Implement bootstrap reporting exactly**

Use `np.random.default_rng(20260828)`, 10,000 resamples, percentile 2.5%/97.5% bounds for gross setup mean, base-net setup mean, practical base-net mean R, and low-minus-high gross mean difference. No p-value gate.

- [ ] **Step 7: Run Task 4 verification and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py" -k "profit_factor or bootstrap or temporal or outlier or leave_one or falsification"
git add "Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py" \
        "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py"
git commit -m "research: add R1 robustness analysis"
```

---

### Task 5: Add artifact-derived integrity audit and overlap diagnostics

**Files:**
- Modify: `Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py`
- Modify: `Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py`
- Generate: `output/r1_pit_audit.csv`
- Generate: `output/r1_overlap_diagnostic.csv`

**Interfaces:**
- `count_integrity_violations(signals: pd.DataFrame, entries: pd.DataFrame, cancellations: pd.DataFrame, setup: pd.DataFrame, practical: pd.DataFrame, controls: pd.DataFrame, feature_frames: dict[str, pd.DataFrame], membership: pd.DataFrame, canonical_sessions: pd.DatetimeIndex) -> tuple[int, pd.DataFrame]`
- `overlap_diagnostics(entries: pd.DataFrame, canonical_sessions: pd.DatetimeIndex) -> pd.DataFrame`

- [ ] **Step 1: Add numeric-recomputation audit tests**

Use a fixture with 21 pre-signal rows plus one signal row and one next-session row. Corrupt persisted `Shock_Score` after building the fixture and assert the audit emits `SHOCK_SCORE_MISMATCH`. Repeat for `Prior20_Median_Volume` and assert `PRIOR_VOLUME_MISMATCH`.

The test calls must use the full signature shown above; do not bypass feature frames or membership.

- [ ] **Step 2: Implement frozen numeric tolerance**

```python
np.isclose(observed, recomputed, rtol=1e-9, atol=1e-12)
```

Use exact equality for dates/integers.

- [ ] **Step 3: Independently audit accepted low-volume entries**

Recompute and verify: signal window, PIT membership, 20 prior returns, `Sigma20`, signal return, `Shock_Score`, 20 prior volumes, prior median volume, `Volume_Ratio`, 20 prior traded values, prior median traded value, liquidity floor, ATR14 signal timing, structural stop, immediate-next-session entry, `Entry_Open > stop`, lockout, T+6 scheduled exit, qualified/accepted/cancelled accounting, and identical completed setup/practical Entry_ID sets.

Deduplicate identical `(Entry_ID, Symbol, Violation)` rows before counting.

- [ ] **Step 4: Independently audit high-volume controls**

Verify PIT/liquidity, `Shock_Score <= -2.0`, `Volume_Ratio >= 1.5`, immediate-next-open entry, independent control lockout, and T+6 fixed exit. Do not require structural-stop fields.

- [ ] **Step 5: Implement overlap diagnostics without suppressing entries**

Using scheduled T+6 lifecycles, report total accepted entries, maximum/average simultaneous trades, maximum same-day entries, overlapping-entry count, overlap percentage, and same-day entry-count distribution.

- [ ] **Step 6: Run Task 5 verification and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py" -k "integrity or pit or overlap"
git add "Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py" \
        "Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py"
git commit -m "research: audit R1 point-in-time integrity"
```

---

### Task 6: Add frozen validation gates, evidence report, README, and fresh historical run

**Files:**
- Modify: `Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py`
- Modify: `Swing Trading/research/swing/r1_price_shock_reversal/tests/test_r1_analysis.py`
- Create: `Swing Trading/research/swing/r1_price_shock_reversal/README.md`
- Generate all remaining output artifacts, especially `r1_validation_gates.csv` and `research_report.md`.

- [ ] **Step 1: Add exact gate-boundary tests**

Synthetic summaries must prove:

```text
Integrity violation count > 0 -> INVALID_RESEARCH_RUN
Completed paired outcomes 299 -> INSUFFICIENT_EVIDENCE
Base net mean exactly 0.002 -> setup mean gate passes
Base net PF exactly 1.20 -> setup PF gate passes
Stress net mean exactly 0 -> stress mean gate fails
Practical base mean R exactly 0.15 -> practical mean gate passes
Practical base R-PF exactly 1.20 -> practical PF gate passes
```

- [ ] **Step 2: Implement all mandatory gates exactly**

For a valid run with at least 300 completed paired outcomes, `PASS` requires all:

```text
Gross setup mean > 0
Base-net setup mean >= 0.002
Base-net setup PF >= 1.20
Stress-net setup mean > 0
Stress-net setup PF > 1.00
Practical base-net mean R >= 0.15
Practical base-net R-PF >= 1.20
Low-volume gross mean > high-volume gross mean
Low-volume gross PF > high-volume gross PF
Both frozen halves: base-net mean > 0 and base-net PF > 1.0
Top-five-removed sample: base-net mean > 0 and base-net PF > 1.0
Every LOSO sample: base-net mean > 0 and base-net PF > 1.0
Zero mandatory integrity violations
```

Final status precedence:

```text
1. INVALID_RESEARCH_RUN
2. INSUFFICIENT_EVIDENCE
3. PASS when every mandatory gate passes
4. FAIL otherwise
```

- [ ] **Step 3: Generate evidence-only report and README**

Report factual data-quality counts, cohort/accounting funnel, setup/practical metrics, friction sensitivity, control comparison, temporal/outlier/LOSO robustness, bootstrap intervals, overlap diagnostics, integrity result, gate table, and formal status. Do not recommend filters or a next strategy in generated code/report.

README must contain exactly these run commands:

```bash
python "Swing Trading/research/swing/r1_price_shock_reversal/build_r1_features.py"
python "Swing Trading/research/swing/r1_price_shock_reversal/generate_r1_signals.py"
python "Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py"
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests"
```

- [ ] **Step 4: Run the full R1 test suite**

```bash
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests"
```

Expected: zero failures.

- [ ] **Step 5: Regenerate all R1 outputs from scratch**

Remove only files under the R1 `output/` directory, then run in order:

```bash
python "Swing Trading/research/swing/r1_price_shock_reversal/build_r1_features.py"
python "Swing Trading/research/swing/r1_price_shock_reversal/generate_r1_signals.py"
python "Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py"
```

A valid run may end with formal strategy status `FAIL` or `INSUFFICIENT_EVIDENCE`; those are research results, not script failures. Exit non-zero only for implementation/data-integrity failures that prevent trustworthy analysis.

- [ ] **Step 6: Run existing V3 tests as regression guard**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests"
```

Expected: zero failures.

- [ ] **Step 7: Mechanically reconcile fresh artifacts**

Verify from generated files:

```text
Qualified = Accepted + Cancelled
Completed setup Entry_IDs = completed practical Entry_IDs
All required PIT/integrity values match r1_pit_audit.csv
Temporal split boundary is exact
Bootstrap seed/resample count is exact
Control cohort never uses structural-stop rules
Every gate row matches its source metric
Formal status follows the required precedence
```

Fix correctness defects only. Never change R1 thresholds because of results.

- [ ] **Step 8: Commit fresh implementation and evidence**

```bash
git add "Swing Trading/research/swing/r1_price_shock_reversal"
git commit -m "research: validate R1 price-shock reversal"
```

- [ ] **Step 9: Final execution handoff for Issue #19 / PR**

Report only mechanically derived facts: final SHA, exact run/test commands, usable/download-failed symbols, cohort counts, qualified/accepted/cancelled/incomplete/completed counts, setup gross/base/stress metrics, practical base/stress R metrics, control comparison, both temporal halves, top-five result, worst LOSO row, bootstrap intervals, integrity violation count, formal status, and report/gate paths. Do not add a strategy recommendation; Portfolio Advisor interprets the evidence.

## Plan Self-Review

Before execution confirm:

- [ ] No momentum/trend/RS/sector/regime filter is primary.
- [ ] All prior-20 baselines exclude the shock day.
- [ ] `Sigma20` uses `ddof=1`.
- [ ] Shock threshold remains `-2.0`.
- [ ] Volume thresholds remain `<= 1.0` and `>= 1.5`.
- [ ] Stop remains shock low minus `0.25 ATR14`.
- [ ] Entry remains immediate next Open with no positive-gap cancellation.
- [ ] Setup exit remains T+6 Open.
- [ ] Same-symbol lockout remains through scheduled T+6 Open despite early practical stops.
- [ ] Control cohort does not inherit practical-stop mechanics.
- [ ] Friction remains 0.40% / 0.60% / 0.80%.
- [ ] Sample threshold remains 300.
- [ ] Temporal boundary remains 2025-02-11 / 2025-02-12.
- [ ] Bootstrap remains 10,000 / seed 20260828 / 95% CI.
- [ ] Any invalid research run blocks profitability interpretation.
- [ ] No outcome-based rescue path exists.

## Execution Handoff

Execute this plan **inline only** with `superpowers:executing-plans`, task-by-task with tests and commits at each checkpoint. Preserve a failing strategy result exactly as generated; do not optimize R1.