# Strategy V2 Quality-Base Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use `subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable custom historical validator for Strategy V2 and mechanically report whether its precommitted signal-level gates pass, fail, or have insufficient evidence.

**Architecture:** Add one focused research module under `Swing Trading/research/swing/strategy_v2_quality_base/`. The module will reuse the committed point-in-time Nifty 500 membership and breadth files, download one consistent corporate-action-adjusted OHLCV history, build point-in-time Nifty 500 RS in memory, run a deterministic per-symbol pivot/base state machine, apply exactly one next-session entry opportunity, simulate the two locked exit lenses, and generate robustness/gate outputs. Existing T1 research files remain read-only.

**Tech Stack:** Python 3, pandas, numpy, yfinance, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-26-strategy-v2-quality-base-breakout-design.md`

**Issue:** `https://github.com/krishna916/Financial/issues/13`

## Global Constraints

- T1 remains retired. This is a new strategy family, not T5 and not a T1 rescue experiment.
- Validation method is `CUSTOM_REQUIRED`; do not replace the design with a simplified Streak proxy.
- Primary signal window is `2023-08-01` through `2026-08-25` inclusive because committed point-in-time Nifty 500 membership begins on `2023-08-01`.
- Use enough pre-window OHLCV history for SMA200, ATR14, 63-session pivot logic, 20-session liquidity, and 126-session RS returns.
- Use the committed point-in-time membership manifest at `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`.
- Current Nifty 500 membership must never be applied retrospectively.
- A symbol may use valid pre-membership OHLCV for indicator warm-up, but may generate a signal only while active in the point-in-time Nifty 500 on the signal date.
- Use one consistent corporate-action-adjusted OHLCV convention for High/Low/Close, moving averages, ATR/True Range, entry/exit, and return calculations. Do not mix adjusted and unadjusted prices.
- Preserve missing sessions. Never forward-fill synthetic OHLCV.
- Same-day cross-sectional RS uses 21/63/126-session returns with weights 30/40/30 and requires `Composite_RS >= 70`.
- A ranked date is research-safe only when at least 80% of active Nifty 500 members have all 21/63/126 return horizons available.
- Liquidity gate: 20-session median traded value `>= ₹10 crore` on the breakout signal date.
- Trend gates: `Close > SMA50` and `SMA50 > SMA200`. Do not add rising-SMA50.
- Pivot seed: current High is the highest High over the current and prior 62 sessions.
- Base duration: 10–30 trading sessions.
- Base depth: `(Active_Pivot - Base_Low) / ATR14_at_original_pivot_seed <= 4.0`; breach invalidates immediately.
- Failed probe: `High > Active_Pivot` and `Close <= Active_Pivot` updates the active pivot without resetting base age.
- Volatility contraction: mean True Range of final five pre-breakout base sessions `<= 0.80 *` mean True Range of base sessions 1–5.
- Breakout: `Close > Active_Pivot` during base sessions 10–30.
- Breakout candle is excluded from final-five contraction and structural-stop windows.
- Signal-day extension: `Breakout_Close <= Active_Pivot + ATR14_signal`.
- Exactly one entry opportunity exists: immediately following market session Open.
- Entry requires `Active_Pivot <= Entry_Open <= Active_Pivot + ATR14_signal`; otherwise cancel and never delay/retry that breakout.
- Structural stop: lowest Low of final five pre-breakout base sessions minus `0.25 * ATR14_signal`.
- Reject before entry if stop is not below entry or if stop distance is `> 2.5 * ATR14_signal`.
- Initial stop is fixed throughout this validation.
- Setup-quality lens ignores the stop and exits next session Open after `Close < SMA20`.
- Practical lens uses the fixed stop plus the same SMA20 close-based exit. Gap through stop exits at session Open; intraday touch exits at stop.
- No profit target, breakeven move, trailing stop, time stop, breadth gate, sector-RS gate, or volume gate.
- Breadth is diagnostic only and must use a strict prior-date join: `Breadth_Matched_Date < Entry_Date`.
- Sector RS is optional diagnostic metadata only if reliable point-in-time data already exists; do not reconstruct hindsight sector mappings.
- Do not impose the ₹20k capital pool or 3–5 position cap in this first signal-level validation.
- Do not optimize thresholds, exclude inconvenient results, or alter the strategy after seeing output.
- Implementation must output factual gate status only; Portfolio Advisor interprets the research result.

---

## File Structure

Create this module without refactoring existing T1 research:

```text
Swing Trading/research/swing/strategy_v2_quality_base/
├── README.md
├── requirements.txt
├── build_v2_features.py
├── generate_v2_signals.py
├── analyze_v2_results.py
├── tests/
│   ├── test_v2_features.py
│   ├── test_v2_signals.py
│   ├── test_v2_analysis.py
│   └── test_v2_end_to_end.py
└── output/
    ├── v2_data_validation.csv
    ├── v2_universe_rs_audit.csv
    ├── v2_base_state_audit.csv
    ├── v2_signal_candidates.csv
    ├── v2_entries.csv
    ├── v2_entry_cancellations.csv
    ├── v2_setup_quality_trades.csv
    ├── v2_practical_trades.csv
    ├── v2_validation_summary.csv
    ├── v2_year_summary.csv
    ├── v2_outlier_robustness.csv
    ├── v2_leave_one_symbol_out.csv
    ├── v2_breadth_summary.csv
    ├── v2_overlap_diagnostic.csv
    └── research_report.md
```

Do **not** commit a giant all-symbol daily OHLCV/feature cache. Download/build daily features reproducibly in memory and commit only the compact audits, signal/trade datasets, summaries, and report above.

---

### Task 1: Scaffold reproducible adjusted OHLCV and point-in-time membership loading

**Files:**
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/requirements.txt`
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/build_v2_features.py`
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_features.py`

**Interfaces:**
- Produces `load_membership(path: Path) -> pd.DataFrame`.
- Produces `download_adjusted_ohlcv(ticker: str, start: str, end_exclusive: str) -> pd.DataFrame`.
- Produces `compute_price_features(frame: pd.DataFrame) -> pd.DataFrame`.
- Produces `active_members_on(membership: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame`.
- Later tasks import these functions; keep them pure except the downloader.

- [ ] **Step 1: Create dependencies matching the existing research stack**

Create `requirements.txt` with:

```text
numpy>=1.24
pandas>=2.0
yfinance>=0.2
pytest>=7.0
```

- [ ] **Step 2: Write failing unit tests for membership and adjusted OHLCV normalization**

Cover all of these cases in `test_v2_features.py`:

```python
def test_active_members_on_uses_inclusive_member_intervals():
    ...

def test_compute_price_features_uses_no_forward_fill():
    ...

def test_true_range_uses_prior_close():
    ...

def test_atr14_is_wilder_atr():
    ...

def test_liquidity_is_20_session_median_close_times_volume():
    ...
```

Use small deterministic DataFrames. Do not make network calls in unit tests.

- [ ] **Step 3: Run the focused tests and confirm they fail**

Run:

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_features.py"
```

Expected: FAIL because the module/functions do not exist yet.

- [ ] **Step 4: Implement membership loading and OHLCV normalization**

In `build_v2_features.py` lock these constants:

```python
SIGNAL_START = pd.Timestamp("2023-08-01")
SIGNAL_END = pd.Timestamp("2026-08-25")
DOWNLOAD_START = "2022-01-01"
DOWNLOAD_END_EXCLUSIVE = "2026-08-27"
MIN_RS_COVERAGE = 0.80
LIQUIDITY_FLOOR = 100_000_000.0  # ₹10 crore
```

Use `yfinance` one ticker at a time with `auto_adjust=True`, `actions=False`, and no parallel hidden batching. Normalize returned columns to exactly:

```text
Date, Open, High, Low, Close, Volume
```

Normalize dates to timezone-naive trading dates, sort ascending, reject duplicate dates, coerce numeric fields, and drop only rows that cannot provide valid OHLC values. Never forward-fill prices.

Document that `auto_adjust=True` is the single corporate-action adjustment convention for this experiment.

- [ ] **Step 5: Implement standard indicators without third-party TA libraries**

`compute_price_features()` must add:

```text
True_Range
ATR14
SMA20
SMA50
SMA200
Median_Traded_Value_20
Return21
Return63
Return126
```

Use standard Wilder ATR14:

```python
tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
```

Seed ATR with the arithmetic mean of the first 14 valid True Range observations, then recursively apply:

```python
atr_t = ((atr_prev * 13) + tr_t) / 14
```

Use `Close * Volume` for daily traded value and a rolling 20-session median.

- [ ] **Step 6: Run the focused tests and make them pass**

Run:

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_features.py"
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: scaffold Strategy V2 adjusted price features"
```

---

### Task 2: Build point-in-time Nifty 500 cross-sectional RS and data-quality audits

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/build_v2_features.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_features.py`
- Create on execution: `Swing Trading/research/swing/strategy_v2_quality_base/output/v2_data_validation.csv`
- Create on execution: `Swing Trading/research/swing/strategy_v2_quality_base/output/v2_universe_rs_audit.csv`

**Interfaces:**
- Produces `rank_point_in_time_rs(feature_frames: dict[str, pd.DataFrame], membership: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]`.
- Produces in-memory symbol feature frames containing `RS21`, `RS63`, `RS126`, `Composite_RS`, `RS_Active_Count`, `RS_Eligible_Count`, `RS_Coverage`, `RS_Research_Safe`.
- Produces the per-date audit consumed by later signal generation.

- [ ] **Step 1: Add failing tests for cross-sectional ranking**

Test:

```python
def test_rs_ranks_only_active_point_in_time_members():
    ...

def test_rs_requires_all_three_horizons_for_rank_eligibility():
    ...

def test_rs_day_is_unsafe_below_80_percent_coverage():
    ...

def test_composite_rs_uses_locked_30_40_30_weights():
    ...

def test_current_membership_is_not_backfilled_into_prior_dates():
    ...
```

Use synthetic membership intervals where one symbol joins and another leaves so the expected cross-section is unambiguous.

- [ ] **Step 2: Run tests and confirm the new cases fail**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_features.py"
```

Expected: the new RS tests FAIL.

- [ ] **Step 3: Implement point-in-time ranking**

For each market date in the signal window:

1. Resolve active membership using inclusive `Member_From <= Date <= Member_To` logic; open-ended `Member_To` stays active.
2. Count `Active_Member_Count` from the manifest, including non-downloadable/dummy members in the denominator exactly as the committed membership source represents them.
3. A symbol is RS-eligible only if it is active, has a valid adjusted Close on that date, and has valid Return21/Return63/Return126.
4. Compute `RS_Coverage = RS_Eligible_Count / Active_Member_Count`.
5. Mark `RS_Research_Safe = RS_Coverage >= 0.80`.
6. Only on research-safe dates rank eligible symbols independently for 21/63/126 returns with:

```python
series.rank(method="average", pct=True, ascending=True) * 100.0
```

7. Compute:

```python
Composite_RS = 0.30 * RS21 + 0.40 * RS63 + 0.30 * RS126
```

Do not rank inactive symbols and do not force the cross-section to exactly 500 names.

- [ ] **Step 4: Implement compact audit outputs**

`v2_data_validation.csv` must contain one row per distinct Yahoo ticker with at least:

```text
Symbol,Yahoo_Ticker,Download_Start,Download_End,Raw_Rows,Duplicate_Dates,
Missing_Open,Missing_High,Missing_Low,Missing_Close,Missing_Volume,Usable
```

`v2_universe_rs_audit.csv` must contain one row per signal-window market date with:

```text
Date,Active_Member_Count,Downloadable_Active_Count,RS_Eligible_Count,
RS_Coverage,RS_Research_Safe
```

Do not write a huge full daily feature cache.

- [ ] **Step 5: Add the executable build path**

Running:

```bash
python "Swing Trading/research/swing/strategy_v2_quality_base/build_v2_features.py"
```

must load the committed membership manifest, download all distinct downloadable tickers needed for the membership window plus warm-up, compute features/RS in memory, write the two compact audits, and expose the same build function for signal generation to call without changing methodology.

- [ ] **Step 6: Run tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_features.py"
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: add point-in-time Nifty 500 RS for Strategy V2"
```

---

### Task 3: Implement the deterministic pivot/base state machine and signal-date gates

**Files:**
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py`
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py`
- Create on execution: `output/v2_base_state_audit.csv`
- Create on execution: `output/v2_signal_candidates.csv`

**Interfaces:**
- Produces `scan_symbol_bases(symbol: str, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]`.
- State audit rows have explicit `Event` values.
- Signal candidates contain all frozen signal-date values needed by Task 4; do not recompute historical state from future information.

- [ ] **Step 1: Write state-machine tests before implementation**

Cover these exact behaviors:

```python
def test_63_session_high_seeds_base_and_next_session_is_age_one():
    ...

def test_failed_probe_updates_pivot_without_resetting_age():
    ...

def test_failed_probe_keeps_original_seed_atr_for_depth_denominator():
    ...

def test_close_above_pivot_before_age_10_cancels_too_short_base():
    ...

def test_same_day_after_too_short_cancel_can_seed_new_63_day_high_base():
    ...

def test_depth_above_four_seed_atr_invalidates_immediately():
    ...

def test_base_expires_after_session_30():
    ...

def test_breakout_on_session_10_is_allowed():
    ...

def test_breakout_on_session_30_is_allowed():
    ...

def test_breakout_candle_is_excluded_from_final_five_contraction_window():
    ...

def test_breakout_finishes_base_even_when_other_signal_gate_fails():
    ...
```

- [ ] **Step 2: Run the signal tests and confirm they fail**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py"
```

Expected: FAIL because the signal module is not implemented.

- [ ] **Step 3: Implement state ordering explicitly**

For each symbol process bars chronologically. Use this order while a base is active:

1. Increment the base-session count for the current bar.
2. Update the running base low including the current bar Low.
3. Evaluate base-depth invalidation against the current active pivot and original seed ATR.
4. If depth invalidates, record `DEPTH_INVALIDATED`, close the active base, then independently allow the current date to seed a new base if it is a 63-session high.
5. If still active and `Close > Active_Pivot`:
   - age `< 10`: record `TOO_SHORT_BREAKOUT`, close the base, and independently allow same-day reseeding;
   - age `10..30`: freeze a breakout candidate from the pre-breakout active-pivot/base state, record `BREAKOUT_CANDIDATE`, and close the base.
6. Else if `High > Active_Pivot` and `Close <= Active_Pivot`, record `FAILED_PROBE` and update `Active_Pivot = High`; do not reset age or seed ATR.
7. If still active after base session 30 without breakout, record `EXPIRED` and close the base.
8. If no base remains, independently test whether the current bar is a 63-session-high seed.

The breakout candidate's final-five pre-breakout window must use the five base bars immediately before the breakout bar. The breakout bar may affect the running base low for the depth check because depth is required on the signal date, but it must not enter the contraction or structural-stop final-five windows.

- [ ] **Step 4: Implement signal-date gates without changing base termination**

For each breakout candidate freeze and emit:

```text
Symbol,Seed_Date,Signal_Date,Base_Age,Original_Pivot,Active_Pivot,
ATR14_Seed,ATR14_Signal,Base_Low,Base_Depth_ATR,
Initial_TR_Mean,Final_TR_Mean,Contraction_Ratio,
Close,SMA50,SMA200,Median_Traded_Value_20,
RS21,RS63,RS126,Composite_RS,RS_Coverage,
Breakout_Volume_Ratio,Signal_Extension_ATR,
Membership_OK,Liquidity_OK,Trend_OK,RS_OK,Contraction_OK,Extension_OK,
Signal_Qualified,Signal_Rejection_Reason
```

`Signal_Qualified` is true only when all locked signal-date gates pass:

```text
point-in-time membership
RS_Research_Safe
Median_Traded_Value_20 >= 100_000_000
Close > SMA50
SMA50 > SMA200
Composite_RS >= 70
Base_Depth_ATR <= 4.0
Final_TR_Mean <= 0.80 * Initial_TR_Mean
Close <= Active_Pivot + ATR14_Signal
```

A close above pivot ends the base regardless of whether `Signal_Qualified` is false.

Use deterministic semicolon-separated rejection reasons in fixed order so tests can assert them.

- [ ] **Step 5: Emit a compact base-state audit**

Write one row only for meaningful transitions, not every bar. Required event values:

```text
SEEDED
FAILED_PROBE
DEPTH_INVALIDATED
TOO_SHORT_BREAKOUT
EXPIRED
BREAKOUT_CANDIDATE
```

Include symbol/date, base age, seed date, old/new pivot where relevant, seed ATR, base low/depth, and reason.

- [ ] **Step 6: Run signal tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py"
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: implement Strategy V2 base and breakout state machine"
```

---

### Task 4: Implement the one-shot next-session entry and structural-stop acceptance

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py`
- Create on execution: `output/v2_entries.csv`
- Create on execution: `output/v2_entry_cancellations.csv`

**Interfaces:**
- Produces `build_entries(signals: pd.DataFrame, price_frames: dict[str, pd.DataFrame], market_sessions: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]`.
- Accepted entries are the immutable signal set consumed by both exit lenses.

- [ ] **Step 1: Add failing entry tests**

Cover:

```python
def test_entry_uses_immediately_following_market_session_open():
    ...

def test_missing_symbol_bar_on_immediate_next_market_session_cancels_instead_of_delaying():
    ...

def test_open_below_pivot_cancels_entry():
    ...

def test_open_above_one_signal_atr_extension_cancels_entry():
    ...

def test_structural_stop_uses_final_five_pre_breakout_lows():
    ...

def test_stop_at_or_above_entry_is_rejected():
    ...

def test_stop_distance_above_two_point_five_signal_atr_is_rejected():
    ...

def test_cancelled_breakout_never_retries_on_later_session():
    ...
```

- [ ] **Step 2: Define the market-session calendar**

Use dates from the committed breadth series:

`Swing Trading/research/swing/market_breadth/output/nifty500_breadth_daily.csv`

for market sessions inside its covered range. If the final signal date requires one next session not present in that file but present in downloaded market data, append only that objectively observed next session. Do not infer weekends/holidays using calendar arithmetic.

If the symbol lacks an OHLCV bar on the immediately following market session, cancel with `MISSING_NEXT_SESSION_BAR`; do not enter on a later available symbol bar.

- [ ] **Step 3: Implement deterministic entry cancellation reasons**

Use exactly one primary cancellation reason in this order:

```text
MISSING_NEXT_SESSION
MISSING_NEXT_SESSION_BAR
OPEN_BELOW_PIVOT
OPEN_ABOVE_EXTENSION_LIMIT
STOP_NOT_BELOW_ENTRY
STOP_TOO_WIDE
```

For accepted rows calculate:

```python
structural_stop = final_five_pre_breakout_low - 0.25 * atr14_signal
initial_risk = entry_open - structural_stop
```

and freeze all signal-date context into `v2_entries.csv`.

- [ ] **Step 4: Run signal/entry tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py"
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: add Strategy V2 next-session entry rules"
```

---

### Task 5: Simulate setup-quality and practical-trading exit lenses

**Files:**
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py`
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py`
- Create on execution: `output/v2_setup_quality_trades.csv`
- Create on execution: `output/v2_practical_trades.csv`

**Interfaces:**
- Produces `simulate_setup_quality_trade(entry_row: pd.Series, prices: pd.DataFrame) -> dict | None`.
- Produces `simulate_practical_trade(entry_row: pd.Series, prices: pd.DataFrame) -> dict | None`.
- Produces `safe_profit_factor(values: pd.Series) -> float`.
- `None` means incomplete/open at dataset end and is excluded from completed-trade gate counts while remaining auditable.

- [ ] **Step 1: Write failing exit tests**

Cover:

```python
def test_setup_quality_ignores_structural_stop():
    ...

def test_setup_quality_exits_next_open_after_close_below_sma20():
    ...

def test_practical_entry_day_low_can_hit_stop_after_open_entry():
    ...

def test_practical_gap_below_stop_exits_at_gap_open():
    ...

def test_practical_intraday_stop_touch_exits_at_stop_price():
    ...

def test_prior_close_sma20_signal_exits_next_open_before_intraday_stop_logic():
    ...

def test_gap_stop_can_realize_worse_than_minus_one_r():
    ...

def test_trade_without_future_exit_is_marked_incomplete():
    ...
```

- [ ] **Step 2: Implement setup-quality lens**

From the entry session onward, find the first session whose **Close** is below that session's SMA20. Exit at the immediately following market session Open for the symbol. If that next bar is unavailable before dataset end, mark the trade incomplete.

Calculate:

```python
return_pct = (exit_price - entry_open) / entry_open
```

Record signal date, entry date/price, exit-signal date, exit date/price, holding sessions, return, and `Exit_Reason="SMA20"`.

- [ ] **Step 3: Implement practical lens with fixed stop precedence**

For the entry session and each subsequent session while open:

```python
if session_is_scheduled_sma20_exit_open:
    exit at session Open with Exit_Reason="SMA20"
elif Open <= Structural_Stop:
    exit at Open with Exit_Reason="STOP_GAP"
elif Low <= Structural_Stop:
    exit at Structural_Stop with Exit_Reason="STOP_INTRADAY"
elif Close < SMA20:
    schedule exit for immediately following market session Open
```

This precedence guarantees that a prior close-based exit closes the position at the next Open before any later intraday stop logic.

Calculate:

```python
initial_risk = entry_open - structural_stop
r_multiple = (exit_price - entry_open) / initial_risk
return_pct = (exit_price - entry_open) / entry_open
```

- [ ] **Step 4: Implement deterministic profit-factor helper**

For either returns or R multiples:

```python
positive_sum = values[values > 0].sum()
negative_abs_sum = -values[values < 0].sum()
```

Return:

- `np.inf` if positive sum > 0 and negative sum == 0;
- `0.0` if positive sum == 0 and negative sum > 0;
- `np.nan` if both are zero/no completed observations;
- otherwise `positive_sum / negative_abs_sum`.

- [ ] **Step 5: Run analysis tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py"
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: simulate Strategy V2 exit lenses"
```

---

### Task 6: Attach strict-prior breadth context and compute locked robustness/gate outputs

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py`
- Create on execution: all summary/robustness CSVs listed in File Structure

**Interfaces:**
- Produces `attach_prior_breadth(trades: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame`.
- Produces `summarize_lens(...)`, `year_summary(...)`, `outlier_robustness(...)`, `leave_one_symbol_out(...)`, `breadth_summary(...)`, `evaluate_gates(...)`.

- [ ] **Step 1: Add failing strict-timing and robustness tests**

Cover:

```python
def test_breadth_asof_join_forbids_equal_entry_date():
    ...

def test_breadth_join_uses_latest_strict_prior_observation():
    ...

def test_top_winner_removal_is_global_and_sorted_by_setup_quality_return():
    ...

def test_leave_one_symbol_out_recomputes_metrics_for_every_symbol():
    ...

def test_less_than_100_completed_trades_is_insufficient_evidence():
    ...

def test_all_precommitted_gates_required_for_pass():
    ...
```

- [ ] **Step 2: Implement strict-prior breadth attachment**

Load:

`Swing Trading/research/swing/market_breadth/output/nifty500_breadth_daily.csv`

Use a sorted as-of merge with exact matches forbidden, equivalent to:

```python
pd.merge_asof(
    trades.sort_values("Entry_Date"),
    breadth.sort_values("Date"),
    left_on="Entry_Date",
    right_on="Date",
    direction="backward",
    allow_exact_matches=False,
)
```

Rename the matched source date to `Breadth_Matched_Date` and assert for every matched trade:

```python
Breadth_Matched_Date < Entry_Date
```

Breadth remains diagnostic only; never remove or add trades because of breadth regime.

- [ ] **Step 3: Generate overall and calendar-year summaries**

`v2_validation_summary.csv` must contain at least both lenses with:

```text
Lens,Completed_Trades,Winners,Losers,Win_Rate,Mean_Return,Median_Return,
Return_PF,Mean_R,R_PF,Median_Holding_Sessions
```

Use `Mean_R`/`R_PF` as blank/NA for setup-quality lens if not meaningful there.

`v2_year_summary.csv` must group by **Entry_Date calendar year** and report both lenses, completed trade counts, mean return, return PF, and practical mean R/R PF.

- [ ] **Step 4: Implement precommitted top-winner robustness**

For `N in {1, 3, 5}` remove the globally highest **setup-quality return** accepted entries, then recompute setup-quality mean return/PF and the corresponding practical lens metrics on the same remaining entry IDs. Write `v2_outlier_robustness.csv` with `Removed_Top_N` and exact removed entry IDs/symbols.

Do not choose winners separately per year/symbol and do not change N after seeing results.

- [ ] **Step 5: Implement leave-one-symbol-out robustness**

For every unique accepted symbol, remove all accepted entries for that symbol and recompute the metrics on both lenses. Write one row per omitted symbol to `v2_leave_one_symbol_out.csv`.

- [ ] **Step 6: Implement breadth and overlap diagnostics**

`v2_breadth_summary.csv` should summarize completed trades by the existing breadth regime labels without using those labels as a filter.

`v2_overlap_diagnostic.csv` should report factual clustering only, including at minimum:

```text
Total_Accepted_Entries
Entries_With_Another_Open_Same_Symbol_Trade
Max_Simultaneous_Signal_Level_Trades
Max_Same_Day_Entries
```

Do not use overlap diagnostics to change the primary signal set.

- [ ] **Step 7: Implement exact gate evaluation**

Evaluate using completed setup-quality/practical trades from the same accepted entry IDs.

First gate:

```text
Completed_Trades < 100 => Overall_Status = INSUFFICIENT_EVIDENCE
```

If `>=100`, all of these must pass for `Overall_Status = PASS`:

```text
Setup-quality mean return > 0
Setup-quality return PF >= 1.20
Practical mean R >= +0.15
Practical R PF >= 1.20
At least two entry calendar years each have >=20 completed setup-quality trades,
  mean return >0, and return PF >=1.0
After removing top 5 setup-quality-return winners:
  setup-quality mean return >0 and return PF >=1.0
For every leave-one-symbol-out sample:
  setup-quality mean return >0 and return PF >=1.0
Zero point-in-time violations
```

If sample size is sufficient but any gate fails, `Overall_Status = FAIL`.

Write one row per gate plus final status to `v2_validation_summary.csv`; do not hide failed gates.

- [ ] **Step 8: Run tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py"
```

Expected: PASS.

- [ ] **Step 9: Commit Task 6**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: add Strategy V2 robustness and gate analysis"
```

---

### Task 7: Add an end-to-end synthetic research-safety test

**Files:**
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_end_to_end.py`

**Interfaces:**
- Uses public functions from the three research scripts.
- No network access in the test.

- [ ] **Step 1: Build a deterministic synthetic mini-universe fixture**

Create enough sessions for SMA200/RS126 warm-up and at least three symbols with point-in-time membership changes. Construct one symbol that forms a valid 10-session contracting base and breakout, one that fails contraction, and one that breaks too early.

The valid symbol must have a known next-session Open and later SMA20 exit, with a practical stop path that can be asserted exactly.

- [ ] **Step 2: Assert the full data flow**

The test must verify in one flow:

```text
membership -> features -> point-in-time RS -> base state -> signal gates ->
next-session entry -> structural stop -> both exit lenses -> strict-prior breadth
```

Also assert:

- no signal before membership start;
- no equal-date breadth context;
- failed contraction never reaches accepted entries;
- too-short breakout never reaches accepted entries;
- both lenses share the exact same accepted entry ID.

- [ ] **Step 3: Run the entire V2 test suite**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests"
```

Expected: PASS.

- [ ] **Step 4: Run all existing swing research tests to catch regressions**

```bash
python -m pytest -q "Swing Trading/research/swing"
```

Expected: all existing and V2 tests PASS. Do not modify old tests merely to accommodate V2.

- [ ] **Step 5: Commit Task 7**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base/tests"
git commit -m "test: cover Strategy V2 research flow end to end"
```

---

### Task 8: Execute the historical build, audit outputs, and document reproducibility

**Files:**
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/README.md`
- Modify only if necessary to fix implementation defects revealed by execution: the three V2 Python scripts/tests
- Generate and commit: all `output/` files listed in File Structure

**Interfaces:**
- README is the operator entry point.
- `research_report.md` is factual evidence only; it must not recommend strategy changes.

- [ ] **Step 1: Write README before the first full run**

README must document exactly:

- Strategy V2 is a new family and T1 is retired.
- Design spec and Issue #13 links/paths.
- `CUSTOM_REQUIRED` rationale.
- Signal window `2023-08-01` to `2026-08-25`.
- Membership manifest path and point-in-time rule.
- Yahoo/yfinance source and `auto_adjust=True` OHLCV convention.
- Wilder ATR14 formula.
- 80% RS coverage safety rule.
- All locked entry/base/stop/exit thresholds.
- Breadth as diagnostic-only strict-prior context.
- No sector gate and no historical hindsight governance filter.
- Exact rebuild/test commands.
- Output-file descriptions.
- Statement that outputs are evidence for Portfolio Advisor; the builder does not optimize or interpret the strategy.

- [ ] **Step 2: Run the full feature/signal/trade pipeline**

From repository root use the module's documented commands. A simple acceptable operator flow is:

```bash
python "Swing Trading/research/swing/strategy_v2_quality_base/build_v2_features.py"
python "Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py"
python "Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py"
```

If scripts share an in-memory build function and would otherwise redownload repeatedly, it is acceptable for `generate_v2_signals.py` or `analyze_v2_results.py` to orchestrate a single rebuild in-process. Keep the README command canonical and reproducible; do not create infrastructure unrelated to this research task.

- [ ] **Step 3: Audit data integrity before reading strategy results**

Check and fail the build for implementation/data-integrity defects such as:

```text
duplicate symbol/date price rows
non-monotonic dates
mixed adjustment columns
membership interval parse failures
RS research-safe rows below 80% coverage
accepted signal with inactive membership
accepted signal with Composite_RS < 70
accepted signal outside base age 10..30
accepted entry not on immediately following market session
accepted entry outside pivot..pivot+1ATR
accepted stop >= entry
accepted stop wider than 2.5ATR
Breadth_Matched_Date >= Entry_Date
```

Do **not** fail simply because profitability gates fail.

- [ ] **Step 4: Generate `research_report.md` mechanically**

Include:

1. data window and membership method;
2. ticker/download/audit counts;
3. RS coverage range and number of unsafe dates;
4. base candidate and rejection counts by reason;
5. accepted vs cancelled entry counts;
6. setup-quality headline metrics;
7. practical headline metrics;
8. calendar-year table;
9. top-1/3/5 winner robustness table;
10. leave-one-symbol-out worst case;
11. breadth diagnostic table;
12. overlap diagnostics;
13. each precommitted gate with PASS/FAIL/INSUFFICIENT status;
14. final mechanical `PASS`, `FAIL`, or `INSUFFICIENT_EVIDENCE`.

End with this interpretation boundary:

> This report supplies locked evidence only. It does not tune Strategy V2 or prescribe a follow-up change. Portfolio Advisor retains the strategy decision.

- [ ] **Step 5: Run the full test suite again after generated outputs exist**

```bash
python -m pytest -q "Swing Trading/research/swing"
```

Expected: PASS.

- [ ] **Step 6: Inspect generated diffs for accidental giant caches or raw downloads**

Use:

```bash
git status --short
git diff --stat
```

Only source/tests/README and compact committed outputs should appear. Do not commit downloaded raw-price caches or giant all-symbol feature tables.

- [ ] **Step 7: Commit the reproducible research result**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: validate Strategy V2 quality-base breakout"
```

- [ ] **Step 8: Open a PR linked to Issue #13**

PR title:

```text
research: validate Strategy V2 quality-base breakout
```

PR body must summarize data-integrity results and factual gate outputs, link Issue #13, and explicitly state that no threshold/filter was tuned after observing outcomes.

Do not make a strategy recommendation in the PR body.

---

## Final Verification Checklist

Before claiming Issue #13 implementation is complete, verify all of the following from actual command output/files:

- [ ] `python -m pytest -q "Swing Trading/research/swing"` passes.
- [ ] Point-in-time membership source is the committed official reconstruction.
- [ ] Signal window begins no earlier than `2023-08-01`.
- [ ] RS is ranked against active point-in-time Nifty 500 members, not the old 20-stock dataset.
- [ ] All accepted signal dates have RS coverage `>=80%` and `Composite_RS >=70`.
- [ ] No current-membership survivorship substitution exists.
- [ ] No price forward-fill exists.
- [ ] Pivot/base state behavior matches the locked state machine.
- [ ] Final-five contraction/stop windows exclude the breakout candle.
- [ ] Every accepted entry is the immediate next market-session Open.
- [ ] No cancelled breakout is entered later without a new base.
- [ ] Every accepted structural stop is below entry and within `2.5 ATR14_signal`.
- [ ] Setup-quality and practical lenses use exactly the same accepted entry IDs.
- [ ] Practical stop precedence handles gaps and intraday touches correctly.
- [ ] Every breadth match satisfies `Breadth_Matched_Date < Entry_Date`.
- [ ] Breadth, sector, and volume were not used as entry gates.
- [ ] No capital/position-count constraint altered the primary signal set.
- [ ] Top-1/3/5 and leave-one-symbol-out robustness outputs are present.
- [ ] Gate evaluation uses the precommitted thresholds without post-result edits.
- [ ] Raw downloads/giant feature caches are not committed.
- [ ] `research_report.md` is factual and contains no result-driven optimization recommendation.

## Execution Handoff

Execute this plan with **`superpowers:executing-plans` in inline mode only**. Work task-by-task, run the specified tests before and after each implementation step, and use the commits as checkpoints. Never invoke `subagent-driven-development`.