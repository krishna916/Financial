# RR1 Objective Range Sweep Reversion Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and run one frozen historical validation of RR1 objective range sweep reversion using point-in-time Nifty 500 membership, exact 60-session range history, next-session execution, paired raw/practical lenses, an upper-range falsification cohort, benchmark comparison, integrity auditing, and precommitted PASS/FAIL/INSUFFICIENT/INVALID gates.

**Architecture:** Add a self-contained `rr1_range_sweep_reversion` research module. Keep edge-defining logic isolated from failed T1/V2/V3/M1/R1 modules, while reusing only generic project inputs/conventions: PIT membership, canonical Nifty 500 sessions, adjusted Yahoo OHLCV, and the Nifty 500 benchmark ticker. Split the work into feature construction, signal/entry construction, outcome simulation, independent integrity audit, and analysis/reporting so each layer is testable and the validator can fail closed without turning into a generic research platform.

**Tech Stack:** Python 3, pandas, numpy, yfinance, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-31-rr1-objective-range-sweep-reversion-design.md`

**Issue:** https://github.com/krishna916/Financial/issues/37

## Global Constraints

- RR1 is Candidate 3 and the final planned strategy-family experiment. After its formal verdict, stop strategy-family research and reassess the program.
- Signal window: `2023-08-01` through `2026-08-25` inclusive.
- PIT membership source: `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`.
- Adjusted OHLCV only: Yahoo `auto_adjust=True`.
- Nifty 500 benchmark/canonical-session ticker: `^CRSLDX`.
- Deterministic acquisition snapshot for this experiment: `DOWNLOAD_START = "2023-01-01"`, `DOWNLOAD_END_EXCLUSIVE = "2026-08-27"`. This matches the established non-event research snapshot style and intentionally leaves late signals incomplete rather than fetching later data to improve sample size.
- Exact pre-signal stock bars are required on every canonical session `T-61..T`; a missing bar makes that session ineligible rather than silently stretching the lookback.
- Range uses only `T-60..T-1`: `Range_Low=min(Low)`, `Range_High=max(High)`, `Range_Mid=(Range_Low+Range_High)/2`.
- `ER60 = abs(Close[T-1]-Close[T-61]) / sum(abs(Close[i]-Close[i-1])) for i=T-60..T-1`; require finite positive denominator and `ER60 <= 0.25`.
- Liquidity: prior-20 median `Close * Volume >= 100_000_000` rupees, excluding signal day.
- Lower signal: `Low[T] < Range_Low` and `Close[T] > Range_Low`.
- Upper mirror: `High[T] > Range_High` and `Close[T] < Range_High`.
- No primary RSI, stochastic, Bollinger Band, SMA, RS, sector, breadth, regime, volume-ratio, shock-size, candlestick, news/event, 52-week-high, or gap filter.
- Wilder ATR14 is frozen. Lower structural stop: `Signal_Low - 0.25 * ATR14_signal`.
- Lower target: frozen pre-signal `Range_Mid`.
- Entry/reference timing: immediate next canonical-session Open.
- Lower entry must satisfy `Structural_Stop < Entry_Open < Target` and `Initial_RR >= 2.0`.
- Lower cancellation reasons are exactly: `SAME_SYMBOL_LOCKOUT`, `SIGNAL_ALREADY_AT_OR_ABOVE_TARGET`, `MISSING_NEXT_SESSION`, `MISSING_NEXT_SESSION_BAR`, `OPEN_AT_OR_BELOW_STRUCTURAL_STOP`, `OPEN_AT_OR_ABOVE_TARGET`, `INSUFFICIENT_REWARD_RISK`.
- Upper mirror cancellation reasons are exactly: `SAME_SYMBOL_LOCKOUT`, `MISSING_NEXT_SESSION`, `MISSING_NEXT_SESSION_BAR`.
- Lower and upper same-symbol lockouts are cohort-local and remain active until scheduled `T+16 Open`; a new same-cohort signal on `T+16` is allowed because the prior lifecycle ended at that session's Open.
- Lens A uses accepted lower entries only: `T+1 Open -> T+16 Open`, no stop or target.
- Lens B uses the same completed lower `Entry_ID` set: structural stop / midpoint target / `T+16 Open` time exit.
- Practical EOD ambiguity rule: if stop and target are both touched within the same daily bar, score stop first.
- Open precedence after entry: `Open <= stop` exits at Open; else `Open >= target` exits at Open; otherwise inspect intraday Low/High.
- Accepted lower evidence is primary-complete only when Lens A, Lens B, and required benchmark evidence are all evaluable. An early Lens B exit does not waive the later `T+16` Lens A requirement.
- Mirror outcome: next Open to `T+16 Open`; no short trade, stop, or target.
- Base friction `0.004`, stress `0.006`, severe `0.008` of entry value round trip.
- Lens B excess return is percentage-return excess, not R-minus-index-return: `Base_Practical_Excess_Return = Base_Practical_Net_Return - Benchmark_Return`; practical R is retained separately.
- Bootstrap: 10,000 resamples, seed `20260831`, 95% percentile interval.
- Temporal split: FIRST `2023-08-01..2025-02-11`; SECOND `2025-02-12..2026-08-25`.
- Minimum samples: paired lower `>=300`, FIRST lower `>=100`, SECOND lower `>=100`, completed upper mirror `>=100`.
- Formal status precedence: integrity/evidence problem -> `INVALID_RESEARCH_RUN`; valid but any sample minimum missed -> `INSUFFICIENT_EVIDENCE`; valid+sufficient+all mandatory gates pass -> `PASS`; otherwise -> `FAIL`.
- Do not change any threshold, range length, ER cutoff, stop buffer, target, R:R rule, holding period, sample gate, year, sector, or diagnostic after outcomes.
- Do not modify or regenerate failed T1/V2/V3/M1/R1 evidence as part of RR1.
- Do not add notebooks, dashboards, broker/live-trading integration, generic security-master work, generic research-framework abstractions, or unrelated refactors.

## Locked File Structure

```text
Swing Trading/research/swing/rr1_range_sweep_reversion/
├── constants.py
├── build_rr1_features.py
├── generate_rr1_signals.py
├── simulate_rr1_outcomes.py
├── audit_rr1_integrity.py
├── analyze_rr1_results.py
├── run_rr1_validation.py
├── README.md
├── tests/
│   ├── test_rr1_features.py
│   ├── test_rr1_signals.py
│   ├── test_rr1_outcomes.py
│   ├── test_rr1_integrity.py
│   ├── test_rr1_analysis.py
│   └── test_rr1_end_to_end.py
└── output/
    ├── rr1_data_validation.csv
    ├── rr1_range_candidates.csv
    ├── rr1_lower_signals.csv
    ├── rr1_upper_signals.csv
    ├── rr1_lower_entries.csv
    ├── rr1_lower_entry_cancellations.csv
    ├── rr1_upper_references.csv
    ├── rr1_upper_cancellations.csv
    ├── rr1_lens_a_trades.csv
    ├── rr1_practical_trades.csv
    ├── rr1_upper_outcomes.csv
    ├── rr1_forward_diagnostics.csv
    ├── rr1_validation_summary.csv
    ├── rr1_temporal_summary.csv
    ├── rr1_top_five_robustness.csv
    ├── rr1_leave_one_year_out.csv
    ├── rr1_leave_one_symbol_out.csv
    ├── rr1_bootstrap_summary.csv
    ├── rr1_overlap_diagnostic.csv
    ├── rr1_integrity_audit.csv
    ├── rr1_validation_gates.csv
    └── research_report.md
```

Do not commit raw Yahoo downloads or all-symbol feature caches. Commit the compact formal evidence outputs and report after the unchanged final run.

---

### Task 1: Freeze RR1 constants and generic PIT/session data access

**Files:**
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/constants.py`
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/build_rr1_features.py`
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_features.py`
- Read only: `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`
- Reference only: `Swing Trading/research/swing/r1_price_shock_reversal/build_r1_features.py`
- Reference only: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/constants.py`

**Interfaces:**
- `load_membership(path: Path) -> pd.DataFrame`
- `active_members_on(membership: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame`
- `download_adjusted_ohlcv(ticker: str, start: str, end_exclusive: str) -> pd.DataFrame`
- `load_nifty500_benchmark(start: str, end_exclusive: str) -> pd.DataFrame`
- `canonical_sessions(benchmark: pd.DataFrame) -> pd.DatetimeIndex`
- Constants exported from `constants.py` with the exact values in Global Constraints.

- [ ] **Step 1: Write failing constants/session tests**

```python
import pandas as pd

from constants import (
    BASE_FRICTION,
    ER60_MAX,
    HOLDING_SESSIONS,
    LIQUIDITY_FLOOR,
    MIN_INITIAL_RR,
    RANGE_LOOKBACK,
    SIGNAL_END,
    SIGNAL_START,
    STOP_ATR_BUFFER,
)
from build_rr1_features import active_members_on, canonical_sessions


def test_frozen_rr1_constants():
    assert SIGNAL_START == pd.Timestamp("2023-08-01")
    assert SIGNAL_END == pd.Timestamp("2026-08-25")
    assert RANGE_LOOKBACK == 60
    assert ER60_MAX == 0.25
    assert LIQUIDITY_FLOOR == 100_000_000.0
    assert STOP_ATR_BUFFER == 0.25
    assert MIN_INITIAL_RR == 2.0
    assert HOLDING_SESSIONS == 15
    assert BASE_FRICTION == 0.004


def test_active_members_on_is_inclusive():
    membership = pd.DataFrame({
        "Symbol": ["AAA"],
        "Member_From": [pd.Timestamp("2024-01-02")],
        "Member_To": [pd.Timestamp("2024-01-05")],
        "Downloadable": [True],
        "Yahoo_Ticker": ["AAA.NS"],
    })
    assert active_members_on(membership, pd.Timestamp("2024-01-02"))["Symbol"].tolist() == ["AAA"]
    assert active_members_on(membership, pd.Timestamp("2024-01-05"))["Symbol"].tolist() == ["AAA"]


def test_canonical_sessions_use_sorted_unique_benchmark_dates():
    benchmark = pd.DataFrame({
        "Date": pd.to_datetime(["2024-01-03", "2024-01-02", "2024-01-03"]),
        "Open": [101.0, 100.0, 101.0],
    })
    assert canonical_sessions(benchmark).tolist() == [
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-01-03"),
    ]
```

- [ ] **Step 2: Run RED tests**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_features.py"
```

Expected: FAIL because RR1 modules do not exist.

- [ ] **Step 3: Implement frozen constants**

```python
from pathlib import Path
import pandas as pd

SIGNAL_START = pd.Timestamp("2023-08-01")
SIGNAL_END = pd.Timestamp("2026-08-25")
FIRST_HALF_END = pd.Timestamp("2025-02-11")
SECOND_HALF_START = pd.Timestamp("2025-02-12")

DOWNLOAD_START = "2023-01-01"
DOWNLOAD_END_EXCLUSIVE = "2026-08-27"
NIFTY500_YAHOO_TICKER = "^CRSLDX"
MEMBERSHIP_PATH = Path(__file__).parents[1] / "market_breadth" / "config" / "nifty500_membership.csv"

RANGE_LOOKBACK = 60
ER60_MAX = 0.25
LIQUIDITY_FLOOR = 100_000_000.0
ATR_PERIOD = 14
STOP_ATR_BUFFER = 0.25
MIN_INITIAL_RR = 2.0
HOLDING_SESSIONS = 15

BASE_FRICTION = 0.004
STRESS_FRICTION = 0.006
SEVERE_FRICTION = 0.008

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260831
MIN_LOWER_COMPLETED = 300
MIN_HALF_COMPLETED = 100
MIN_UPPER_COMPLETED = 100
```

- [ ] **Step 4: Implement deterministic data adapters**

`download_adjusted_ohlcv()` must call Yahoo with `auto_adjust=True`, normalize the date column to timezone-naive normalized `Timestamp`, sort ascending, reject duplicate dates, and return exactly `Date, Open, High, Low, Close, Volume`.

```python
def canonical_sessions(benchmark: pd.DataFrame) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(benchmark["Date"]).dt.normalize())
    return pd.DatetimeIndex(sorted(dates.unique()))
```

`load_nifty500_benchmark()` must use the same adjusted-OHLCV adapter with `^CRSLDX`; do not synthesize missing sessions from weekdays.

- [ ] **Step 5: Run Task 1 verification**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_features.py"
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add "Swing Trading/research/swing/rr1_range_sweep_reversion/constants.py" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/build_rr1_features.py" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_features.py"
git commit -m "research: scaffold RR1 frozen data conventions"
```

---

### Task 2: Build exact-history range, ER60, liquidity, ATR, and PIT feature frames

**Files:**
- Modify: `Swing Trading/research/swing/rr1_range_sweep_reversion/build_rr1_features.py`
- Modify: `Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_features.py`
- Generate: `Swing Trading/research/swing/rr1_range_sweep_reversion/output/rr1_data_validation.csv`

**Interfaces:**
- `wilder_atr(true_range: pd.Series, period: int = 14) -> pd.Series`
- `compute_rr1_features(frame: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame`
- `build_feature_frames(membership: pd.DataFrame, benchmark: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]`

- [ ] **Step 1: Write failing formula/exclusion tests**

```python
def test_range_er_and_liquidity_exclude_signal_day():
    sessions = pd.bdate_range("2024-01-01", periods=70)
    close = pd.Series([100.0 + (i % 4) for i in range(70)])
    high = close + 2.0
    low = close - 2.0
    volume = pd.Series([2_000_000.0] * 69 + [100_000_000.0])
    frame = pd.DataFrame({
        "Date": sessions,
        "Open": close,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })

    out = compute_rr1_features(frame, pd.DatetimeIndex(sessions))
    row = out.iloc[-1]

    assert row["Range_Low"] == pytest.approx(low.iloc[-61:-1].min())
    assert row["Range_High"] == pytest.approx(high.iloc[-61:-1].max())
    assert row["Range_Mid"] == pytest.approx((row["Range_Low"] + row["Range_High"]) / 2.0)

    expected_num = abs(close.iloc[-2] - close.iloc[-62])
    expected_den = close.diff().abs().iloc[-61:-1].sum()
    assert row["ER60"] == pytest.approx(expected_num / expected_den)

    expected_traded = (close * volume).iloc[-21:-1].median()
    assert row["Prior20_Median_Traded_Value"] == pytest.approx(expected_traded)
```

```python
def test_exact_prehistory_fails_when_one_canonical_bar_is_missing():
    sessions = pd.bdate_range("2024-01-01", periods=70)
    frame = make_valid_price_frame(sessions)
    frame = frame[frame["Date"] != sessions[-20]]

    out = compute_rr1_features(frame, pd.DatetimeIndex(sessions))
    signal_row = out.loc[out["Date"] == sessions[-1]].iloc[0]
    assert bool(signal_row["Exact_Prehistory_61"]) is False
```

- [ ] **Step 2: Run RED tests**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_features.py::test_range_er_and_liquidity_exclude_signal_day" \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_features.py::test_exact_prehistory_fails_when_one_canonical_bar_is_missing"
```

Expected: FAIL before feature implementation.

- [ ] **Step 3: Reindex to canonical sessions before rolling**

Use the benchmark calendar as the only session clock:

```python
indexed = frame.set_index("Date").reindex(sessions)
indexed.index.name = "Date"
result = indexed.reset_index()
bar_valid = result[["Open", "High", "Low", "Close"]].notna().all(axis=1)
result["Exact_Prehistory_61"] = (
    bar_valid.rolling(62, min_periods=62).sum().eq(62)
)
```

Do not forward-fill OHLCV.

- [ ] **Step 4: Implement exact frozen formulas**

```python
result["Range_Low"] = result["Low"].shift(1).rolling(60, min_periods=60).min()
result["Range_High"] = result["High"].shift(1).rolling(60, min_periods=60).max()
result["Range_Mid"] = (result["Range_Low"] + result["Range_High"]) / 2.0

er_num = (result["Close"].shift(1) - result["Close"].shift(61)).abs()
er_den = result["Close"].diff().abs().shift(1).rolling(60, min_periods=60).sum()
result["ER60_Denominator"] = er_den
result["ER60"] = er_num / er_den

result["Daily_Traded_Value"] = result["Close"] * result["Volume"]
result["Prior20_Median_Traded_Value"] = (
    result["Daily_Traded_Value"].shift(1).rolling(20, min_periods=20).median()
)
```

Implement Wilder ATR14 using the established project recursion. Do not use pandas `ewm()` unless tests prove identical initialization to the frozen convention.

- [ ] **Step 5: Add PIT interval assignment and acquisition audit**

For each membership/provider interval, retain provider identity and active interval. Build a symbol frame without inventing aliases. If provider rows overlap for the same research symbol/date, fail that date closed and record it in the audit instead of picking one silently.

Write `rr1_data_validation.csv` with at minimum:

```text
Symbol,Yahoo_Ticker,Member_From,Member_To,Raw_Rows,Canonical_Rows,
Earliest_Date,Latest_Date,Duplicate_Dates,Provider_Overlap_Dates,
Missing_Open,Missing_High,Missing_Low,Missing_Close,Missing_Volume,
Exact_Prehistory_Sessions,Usable_Signal_Window_Sessions,Download_Error
```

Do not attempt to repair dead historical tickers unless the existing provider identity data already resolves them.

- [ ] **Step 6: Add diagnostic-only fields without using them in eligibility**

If cheap from the same frame, retain `Signal_Return`, `Volume_Ratio`, `Range_Width_Pct`, `Sweep_Depth_ATR`, `SMA20`, `SMA50`, `SMA200`, and calendar year. No signal code may require them.

- [ ] **Step 7: Verify Task 2**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_features.py"
python "Swing Trading/research/swing/rr1_range_sweep_reversion/build_rr1_features.py"
```

Expected: tests PASS; acquisition/feature stage exits 0 and writes `rr1_data_validation.csv`.

- [ ] **Step 8: Commit Task 2**

```bash
git add "Swing Trading/research/swing/rr1_range_sweep_reversion/build_rr1_features.py" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_features.py" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/output/rr1_data_validation.csv"
git commit -m "research: build RR1 range features"
```

---

### Task 3: Generate lower/upper qualified signal cohorts

**Files:**
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/generate_rr1_signals.py`
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_signals.py`
- Generate: `output/rr1_range_candidates.csv`
- Generate: `output/rr1_lower_signals.csv`
- Generate: `output/rr1_upper_signals.csv`

**Interfaces:**
- `qualify_range_row(row: pd.Series) -> tuple[bool, str]`
- `is_lower_signal(row: pd.Series) -> bool`
- `is_upper_signal(row: pd.Series) -> bool`
- `build_signal_tables(feature_frames: dict[str, pd.DataFrame], membership: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`

- [ ] **Step 1: Write exact-boundary signal tests**

```python
def test_er60_boundary_is_inclusive():
    row = base_row(ER60=0.25)
    ok, reason = qualify_range_row(row)
    assert ok is True
    assert reason == "QUALIFIED_RANGE"


def test_lower_signal_requires_strict_sweep_and_strict_reclaim():
    assert is_lower_signal(base_row(Low=99.99, Range_Low=100.0, Close=100.01)) is True
    assert is_lower_signal(base_row(Low=100.0, Range_Low=100.0, Close=100.01)) is False
    assert is_lower_signal(base_row(Low=99.99, Range_Low=100.0, Close=100.0)) is False


def test_upper_mirror_requires_strict_sweep_and_strict_rejection():
    assert is_upper_signal(base_row(High=110.01, Range_High=110.0, Close=109.99)) is True
    assert is_upper_signal(base_row(High=110.0, Range_High=110.0, Close=109.99)) is False
    assert is_upper_signal(base_row(High=110.01, Range_High=110.0, Close=110.0)) is False
```

- [ ] **Step 2: Prove forbidden diagnostics do not affect qualification**

```python
def test_volume_momentum_and_regime_fields_do_not_change_signal():
    a = base_row(Low=99.0, Range_Low=100.0, Close=101.0,
                 Volume_Ratio=0.2, RS_Percentile=5.0, Regime="HOSTILE")
    b = a.copy()
    b["Volume_Ratio"] = 4.0
    b["RS_Percentile"] = 99.0
    b["Regime"] = "STRONG_MOMENTUM"
    assert is_lower_signal(a) is True
    assert is_lower_signal(b) is True
```

- [ ] **Step 3: Run RED tests**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_signals.py"
```

Expected: FAIL before module exists.

- [ ] **Step 4: Implement range qualification exactly once**

`qualify_range_row()` must require only:

```python
in_window = SIGNAL_START <= row["Date"] <= SIGNAL_END
pit = bool(row["Point_In_Time_Member"])
exact = bool(row["Exact_Prehistory_61"])
range_ok = np.isfinite(row["Range_Low"]) and np.isfinite(row["Range_High"]) and row["Range_High"] > row["Range_Low"]
er_ok = np.isfinite(row["ER60_Denominator"]) and row["ER60_Denominator"] > 0 and np.isfinite(row["ER60"]) and row["ER60"] <= ER60_MAX
liq_ok = np.isfinite(row["Prior20_Median_Traded_Value"]) and row["Prior20_Median_Traded_Value"] >= LIQUIDITY_FLOOR
```

Do not add any other primary predicate.

- [ ] **Step 5: Persist the signal funnel**

`rr1_range_candidates.csv` must contain every PIT/in-window session that has exact prehistory, valid range, valid ER denominator, and liquidity fields, with explicit booleans for `Liquidity_OK`, `ER60_OK`, `Lower_Signal`, `Upper_Signal`, and one `Range_Eligibility_Reason`.

`rr1_lower_signals.csv` and `rr1_upper_signals.csv` contain only fully qualified signal rows and retain:

```text
Signal_ID,Symbol,Signal_Date,Yahoo_Ticker,Range_Low,Range_High,Range_Mid,
ER60,Prior20_Median_Traded_Value,Open,High,Low,Close,Volume,ATR14,
Point_In_Time_Member,Exact_Prehistory_61
```

Use deterministic IDs such as `LOWER|SYMBOL|YYYY-MM-DD` and `UPPER|SYMBOL|YYYY-MM-DD`.

- [ ] **Step 6: Verify and commit Task 3**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_signals.py"
python "Swing Trading/research/swing/rr1_range_sweep_reversion/generate_rr1_signals.py"
```

```bash
git add "Swing Trading/research/swing/rr1_range_sweep_reversion/generate_rr1_signals.py" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_signals.py" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/output/rr1_range_candidates.csv" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/output/rr1_lower_signals.csv" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/output/rr1_upper_signals.csv"
git commit -m "research: generate RR1 range-sweep signals"
```

---

### Task 4: Build lower entries, upper references, cancellation accounting, and cohort-local lockouts

**Files:**
- Modify: `Swing Trading/research/swing/rr1_range_sweep_reversion/generate_rr1_signals.py`
- Modify: `Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_signals.py`
- Generate: `output/rr1_lower_entries.csv`
- Generate: `output/rr1_lower_entry_cancellations.csv`
- Generate: `output/rr1_upper_references.csv`
- Generate: `output/rr1_upper_cancellations.csv`

**Interfaces:**
- `session_after(date: pd.Timestamp, sessions: pd.DatetimeIndex, steps: int) -> pd.Timestamp | None`
- `build_lower_entries(signals: pd.DataFrame, feature_frames: dict[str, pd.DataFrame], sessions: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]`
- `build_upper_references(signals: pd.DataFrame, feature_frames: dict[str, pd.DataFrame], sessions: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]`

- [ ] **Step 1: Write cancellation-precedence and 2R tests**

Freeze lower cancellation precedence as:

```text
1. SAME_SYMBOL_LOCKOUT
2. SIGNAL_ALREADY_AT_OR_ABOVE_TARGET
3. MISSING_NEXT_SESSION
4. MISSING_NEXT_SESSION_BAR
5. OPEN_AT_OR_BELOW_STRUCTURAL_STOP
6. OPEN_AT_OR_ABOVE_TARGET
7. INSUFFICIENT_REWARD_RISK
8. ACCEPT
```

Test the economics directly:

```python
def test_initial_rr_boundary_is_inclusive():
    signal = lower_signal(Low=95.0, ATR14=4.0, Range_Mid=110.0, Close=101.0)
    # stop = 94; entry = 99.333333... gives risk 5.333333..., reward 10.666666... => exactly 2R
    prices = price_frame_for_entry(open_price=99.33333333333333)
    entries, cancellations = build_lower_entries(
        pd.DataFrame([signal]), {"AAA": prices}, canonical_index(prices)
    )
    assert cancellations.empty
    assert entries.iloc[0]["Initial_RR"] == pytest.approx(2.0)
```

- [ ] **Step 2: Write cohort-local lockout boundary tests**

```python
def test_lower_signal_on_scheduled_t16_session_is_allowed():
    sessions = pd.bdate_range("2024-01-01", periods=40)
    first = lower_signal(signal_date=sessions[0], signal_id="LOWER|AAA|1")
    second = lower_signal(signal_date=sessions[16], signal_id="LOWER|AAA|2")
    entries, cancellations = build_lower_entries(
        pd.DataFrame([first, second]), {"AAA": make_prices(sessions)}, sessions
    )
    assert entries["Signal_ID"].tolist() == ["LOWER|AAA|1", "LOWER|AAA|2"]
    assert cancellations.empty


def test_upper_lockout_does_not_suppress_lower_signal():
    # Build upper references and lower entries independently for the same symbol/date cluster.
    # Both must be accepted when their own cohort lockouts are clear.
    ...
```

Replace the final test body with concrete fixture rows in the test file; do not leave ellipses in committed code.

- [ ] **Step 3: Run RED tests**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_signals.py"
```

Expected: new tests FAIL.

- [ ] **Step 4: Implement lower structural economics**

```python
structural_stop = signal.Low - STOP_ATR_BUFFER * signal.ATR14
initial_risk = entry_open - structural_stop
reward = signal.Range_Mid - entry_open
initial_rr = reward / initial_risk
```

An accepted row must persist:

```text
Entry_ID,Signal_ID,Symbol,Signal_Date,Entry_Date,Entry_Open,
Range_Low,Range_High,Target,ATR14_Signal,Structural_Stop,
Initial_Risk,Reward,Initial_RR,Scheduled_Exit_Date
```

`Scheduled_Exit_Date` is `T+16`, not entry date + 16 independent stock bars.

- [ ] **Step 5: Implement upper reference lifecycle**

Upper references have no target/stop/R:R. Persist:

```text
Reference_ID,Signal_ID,Symbol,Signal_Date,Entry_Date,Entry_Open,Scheduled_Exit_Date
```

Apply only upper cohort lockout and missing-next-session/bar cancellations.

- [ ] **Step 6: Add accounting invariant tests**

```python
def test_qualified_lower_equals_entries_plus_cancellations():
    entries, cancellations = build_lower_entries(...)
    assert len(lower_signals) == len(entries) + len(cancellations)
    assert set(entries["Signal_ID"]).isdisjoint(set(cancellations["Signal_ID"]))
```

Use concrete fixtures in committed tests.

- [ ] **Step 7: Verify and commit Task 4**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_signals.py"
python "Swing Trading/research/swing/rr1_range_sweep_reversion/generate_rr1_signals.py"
```

```bash
git add "Swing Trading/research/swing/rr1_range_sweep_reversion/generate_rr1_signals.py" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_signals.py" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/output/rr1_lower_entries.csv" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/output/rr1_lower_entry_cancellations.csv" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/output/rr1_upper_references.csv" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/output/rr1_upper_cancellations.csv"
git commit -m "research: construct RR1 executable cohorts"
```

---

### Task 5: Simulate paired Lens A / Lens B, mirror outcomes, benchmark excess, and diagnostics

**Files:**
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/simulate_rr1_outcomes.py`
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_outcomes.py`
- Generate: `output/rr1_lens_a_trades.csv`
- Generate: `output/rr1_practical_trades.csv`
- Generate: `output/rr1_upper_outcomes.csv`
- Generate: `output/rr1_forward_diagnostics.csv`

**Interfaces:**
- `simulate_lens_a(entry: pd.Series, prices: pd.DataFrame, benchmark: pd.DataFrame, sessions: pd.DatetimeIndex) -> dict | None`
- `simulate_practical(entry: pd.Series, prices: pd.DataFrame, benchmark: pd.DataFrame, sessions: pd.DatetimeIndex) -> dict | None`
- `simulate_upper(reference: pd.Series, prices: pd.DataFrame, sessions: pd.DatetimeIndex) -> dict | None`
- `build_outcomes(entries: pd.DataFrame, upper_refs: pd.DataFrame, feature_frames: dict[str, pd.DataFrame], benchmark: pd.DataFrame, sessions: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]`

- [ ] **Step 1: Write fixed-horizon and incomplete-pair tests**

```python
def test_lens_a_exits_at_t16_open():
    sessions = pd.bdate_range("2024-01-01", periods=20)
    entry = make_entry(signal_date=sessions[0], entry_date=sessions[1], scheduled_exit=sessions[16])
    prices = make_prices(sessions, opens=list(range(100, 120)))
    result = simulate_lens_a(entry, prices, make_benchmark(sessions), sessions)
    assert result["Exit_Date"] == sessions[16]
    assert result["Exit_Price"] == pytest.approx(prices.loc[prices.Date == sessions[16], "Open"].iloc[0])


def test_early_practical_exit_is_still_incomplete_if_t16_lens_a_bar_missing():
    sessions = pd.bdate_range("2024-01-01", periods=16)  # no T+16
    entry = make_entry(signal_date=sessions[0], entry_date=sessions[1], scheduled_exit=pd.Timestamp("2024-01-23"))
    prices = make_prices_that_hit_stop_on_entry_day(sessions)
    lens_a = simulate_lens_a(entry, prices, make_benchmark(sessions), sessions)
    assert lens_a is None
```

- [ ] **Step 2: Write practical execution precedence tests**

```python
def test_same_bar_stop_and_target_scores_stop_first():
    entry = make_entry(entry_open=100.0, stop=95.0, target=110.0)
    prices = one_holding_bar(open_=100.0, high=111.0, low=94.0, close=105.0)
    result = simulate_practical(entry, prices, benchmark_for(prices), canonical_index(prices))
    assert result["Exit_Reason"] == "STRUCTURAL_STOP"
    assert result["Exit_Price"] == pytest.approx(95.0)


def test_gap_below_stop_exits_at_open_not_stop():
    entry = make_entry(entry_open=100.0, stop=95.0, target=110.0)
    prices = later_holding_bar(open_=92.0, high=96.0, low=90.0, close=94.0)
    result = simulate_practical(entry, prices, benchmark_for(prices), canonical_index(prices))
    assert result["Exit_Reason"] == "GAP_BELOW_STRUCTURAL_STOP"
    assert result["Exit_Price"] == pytest.approx(92.0)


def test_gap_above_target_exits_at_open():
    entry = make_entry(entry_open=100.0, stop=95.0, target=110.0)
    prices = later_holding_bar(open_=113.0, high=114.0, low=112.0, close=113.5)
    result = simulate_practical(entry, prices, benchmark_for(prices), canonical_index(prices))
    assert result["Exit_Reason"] == "GAP_ABOVE_TARGET"
    assert result["Exit_Price"] == pytest.approx(113.0)
```

- [ ] **Step 3: Run RED outcome tests**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_outcomes.py"
```

Expected: FAIL before simulator exists.

- [ ] **Step 4: Implement paired-completion gate before practical interpretation**

For each accepted lower entry, first require exact stock and benchmark evidence through scheduled `T+16`. If that horizon is absent, record the accepted entry as incomplete and exclude it from both Lens A and Lens B completed primary tables, even when Lens B could have exited earlier.

Require mechanically:

```python
assert set(lens_a["Entry_ID"]) == set(practical["Entry_ID"])
```

- [ ] **Step 5: Implement Lens A and friction columns**

Persist:

```text
Entry_ID,Symbol,Signal_Date,Entry_Date,Exit_Date,Entry_Open,Exit_Price,
Gross_Return,Base_Net_Return,Stress_Net_Return,Severe_Net_Return,
Benchmark_Return,Base_Excess_Return
```

where:

```python
gross = exit_price / entry_open - 1.0
base_net = gross - BASE_FRICTION
benchmark_return = benchmark_exit_open / benchmark_entry_open - 1.0
base_excess = base_net - benchmark_return
```

- [ ] **Step 6: Implement Lens B return, R, and excess columns**

Persist both percentage returns and R multiples:

```python
gross_return = exit_price / entry_open - 1.0
base_net_return = gross_return - BASE_FRICTION
base_net_r = ((exit_price - entry_open) - BASE_FRICTION * entry_open) / initial_risk
benchmark_return = benchmark_exit_open / benchmark_entry_open - 1.0
base_practical_excess = base_net_return - benchmark_return
```

Store analogous stress/severe values. The mandatory practical expectancy gate uses `Base_Net_R`; the mandatory excess gate uses `Base_Practical_Excess_Return`.

- [ ] **Step 7: Implement upper mirror and forward diagnostics**

Upper outcome is only `T+1 Open -> T+16 Open` gross return. No synthetic short return.

Forward diagnostics for completed lower entries may include 3/5/10/15/20-session Open-to-Open outcomes, MFE/MAE, target/stop timing, signal-to-entry gap, and same-day stop+target ambiguity. Diagnostics must never be read by eligibility code.

- [ ] **Step 8: Verify and commit Task 5**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_outcomes.py"
```

```bash
git add "Swing Trading/research/swing/rr1_range_sweep_reversion/simulate_rr1_outcomes.py" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_outcomes.py"
git commit -m "research: simulate RR1 paired outcomes"
```

Do not commit final outcome CSVs yet; Task 8 creates the fresh formal evidence package after all integrity/gate code is frozen.

---

### Task 6: Build an independent integrity audit and accounting reconciliation

**Files:**
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/audit_rr1_integrity.py`
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_integrity.py`
- Generate: `output/rr1_integrity_audit.csv`

**Interfaces:**
- `audit_lower_entry(entry: pd.Series, raw_prices: pd.DataFrame, membership: pd.DataFrame, benchmark: pd.DataFrame, sessions: pd.DatetimeIndex) -> list[dict]`
- `audit_upper_reference(reference: pd.Series, raw_prices: pd.DataFrame, membership: pd.DataFrame, sessions: pd.DatetimeIndex) -> list[dict]`
- `run_integrity_audit(...) -> pd.DataFrame`
- `accounting_invariants(...) -> dict[str, bool]`

- [ ] **Step 1: Write corruption-detection tests**

```python
def test_audit_catches_range_low_using_signal_day():
    entry, prices, membership, benchmark, sessions = valid_lower_case()
    entry["Range_Low"] = prices.loc[prices.Date == entry.Signal_Date, "Low"].iloc[0]
    failures = audit_lower_entry(entry, prices, membership, benchmark, sessions)
    assert any(x["Check"] == "RANGE_LOW_RECOMPUTE" and not x["Passed"] for x in failures)


def test_audit_catches_non_immediate_entry_date():
    entry, prices, membership, benchmark, sessions = valid_lower_case()
    entry["Entry_Date"] = sessions[sessions.get_loc(entry.Signal_Date) + 2]
    failures = audit_lower_entry(entry, prices, membership, benchmark, sessions)
    assert any(x["Check"] == "IMMEDIATE_NEXT_SESSION_ENTRY" and not x["Passed"] for x in failures)
```

- [ ] **Step 2: Run RED audit tests**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_integrity.py"
```

Expected: FAIL before audit module exists.

- [ ] **Step 3: Recompute primary evidence independently**

The audit may import frozen constants, but it must not call `qualify_range_row()`, `is_lower_signal()`, `is_upper_signal()`, or trust persisted `*_OK` booleans.

For every accepted lower entry independently recompute from raw aligned OHLCV:

```text
Signal_Date window
PIT membership
exact T-61..T bars
Range_Low / Range_High / Range_Mid from T-60..T-1
ER60 numerator/denominator/value
prior-20 median traded value
Low < Range_Low and Close > Range_Low
Wilder ATR14 and Structural_Stop
immediate next canonical Entry_Date
Close[T] < Target
Structural_Stop < Entry_Open < Target
Initial_Risk, Reward, Initial_RR >= 2.0
cohort-local lockout
scheduled T+16 date
Lens A / Lens B completed Entry_ID equality
benchmark dates/opens
practical exit precedence
```

Use `np.isclose(observed, recomputed, rtol=1e-9, atol=1e-12)` for numeric comparisons unless exact equality is appropriate.

For upper references independently recompute PIT/history/range/ER/liquidity, failed upper break, immediate next Open, upper lockout, and scheduled `T+16`.

- [ ] **Step 4: Implement exact accounting invariants**

```python
checks = {
    "LOWER_SIGNAL_ACCOUNTING": len(lower_signals) == len(lower_entries) + len(lower_cancellations),
    "LOWER_ACCEPTED_ACCOUNTING": len(lower_entries) == len(paired_completed) + len(lower_incomplete),
    "UPPER_SIGNAL_ACCOUNTING": len(upper_signals) == len(upper_refs) + len(upper_cancellations),
    "UPPER_ACCEPTED_ACCOUNTING": len(upper_refs) == len(upper_completed) + len(upper_incomplete),
    "PAIRED_IDS_MATCH": set(lens_a.Entry_ID) == set(practical.Entry_ID),
}
```

Also assert each qualified signal appears exactly once in accepted-or-cancelled and IDs are unique.

- [ ] **Step 5: Verify and commit Task 6**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_integrity.py"
```

```bash
git add "Swing Trading/research/swing/rr1_range_sweep_reversion/audit_rr1_integrity.py" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_integrity.py"
git commit -m "research: add RR1 independent integrity audit"
```

---

### Task 7: Implement metrics, robustness, formal gates, and report generation

**Files:**
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/analyze_rr1_results.py`
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_analysis.py`
- Generate all summary/robustness/gate/report outputs listed in Locked File Structure.

**Interfaces:**
- `profit_factor(values: pd.Series) -> float`
- `summarize_lens_a(trades: pd.DataFrame) -> dict[str, float]`
- `summarize_practical(trades: pd.DataFrame) -> dict[str, float]`
- `bootstrap_mean_ci(values: np.ndarray, seed: int = BOOTSTRAP_SEED, resamples: int = BOOTSTRAP_RESAMPLES) -> tuple[float, float]`
- `build_temporal_summary(practical: pd.DataFrame, lens_a: pd.DataFrame) -> pd.DataFrame`
- `build_top_five_robustness(practical: pd.DataFrame) -> pd.DataFrame`
- `build_leave_one_year_out(practical: pd.DataFrame) -> pd.DataFrame`
- `build_leave_one_symbol_out(practical: pd.DataFrame) -> pd.DataFrame`
- `build_overlap_diagnostic(entries: pd.DataFrame) -> pd.DataFrame`
- `evaluate_gates(...) -> tuple[pd.DataFrame, str]`
- `render_report(...) -> str`

- [ ] **Step 1: Write metric/gate-precedence tests**

```python
def test_profit_factor_uses_sum_winners_over_abs_sum_losers():
    assert profit_factor(pd.Series([2.0, 1.0, -1.0, -0.5])) == pytest.approx(2.0)


def test_integrity_failure_precedes_sample_and_profitability():
    gates, status = evaluate_gates(fake_evidence(integrity_ok=False, lower_count=0))
    assert status == "INVALID_RESEARCH_RUN"


def test_sample_failure_precedes_strategy_fail():
    gates, status = evaluate_gates(fake_evidence(integrity_ok=True, lower_count=299,
                                                 first_count=150, second_count=149,
                                                 upper_count=200, profitable=False))
    assert status == "INSUFFICIENT_EVIDENCE"


def test_positive_median_is_not_a_gate():
    evidence = passing_fake_evidence()
    evidence["Practical_Median_R"] = -0.25
    gates, status = evaluate_gates(evidence)
    assert status == "PASS"
```

- [ ] **Step 2: Write exact mandatory-gate boundary tests**

Test strict/inclusive semantics from the spec:

```text
Lens A: Base_Net_Mean_Return > 0; Base_Net_Return_PF > 1.00; Mean_Base_Excess_Return > 0
Lens B: Base_Practical_Mean_R >= 0.15; Base_Practical_R_PF >= 1.20; Mean_Base_Practical_Excess_Return > 0
Stress: Stress_Practical_Mean_R > 0; Stress_Practical_R_PF > 1.00
Mirror: Mean_Return_LOWER > Mean_Return_UPPER; Mean_Return_UPPER < 0
Both halves: Base_Practical_Mean_R > 0; Base_Practical_R_PF > 1.00; Mean_Base_Practical_Excess_Return > 0
Top-five: mean R > 0 and RPF > 1.00
Every leave-one-year-out: mean R > 0 and RPF > 1.00
Every leave-one-symbol-out: mean R > 0 and RPF > 1.00
```

Include tests showing `0.15` and `1.20` pass their inclusive practical gates, while zero excess and upper mean zero fail their strict gates.

- [ ] **Step 3: Run RED analysis tests**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_analysis.py"
```

Expected: FAIL before analyzer exists.

- [ ] **Step 4: Implement deterministic bootstrap**

```python
def bootstrap_mean_ci(values, seed=BOOTSTRAP_SEED, resamples=BOOTSTRAP_RESAMPLES):
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    rng = np.random.default_rng(seed)
    means = np.empty(resamples, dtype=float)
    for i in range(resamples):
        means[i] = rng.choice(x, size=len(x), replace=True).mean()
    return tuple(np.quantile(means, [0.025, 0.975]))
```

Use distinct deterministic seed offsets per reported bootstrap series while keeping `20260831` as the base seed, or call the function separately with explicitly documented seeds. Never use unseeded randomness.

- [ ] **Step 5: Implement temporal/outlier/concentration robustness**

Temporal halves are assigned from `Signal_Date`, not exit date.

Top-five removes the five largest `Gross_R` practical winners and recomputes base practical mean R/RPF.

Leave-one-year-out removes one signal-year cohort at a time, including partial 2023 and 2026.

Leave-one-symbol-out removes all completed trades of each symbol independently.

Do not skip a bad omission; every represented year/symbol is a mandatory row.

- [ ] **Step 6: Implement mirror and overlap summaries**

Mirror primary comparison uses **gross 15-session** lower Lens A return vs **gross 15-session** upper return.

Overlap diagnostics must not suppress signals. Compute max/average concurrent accepted lower lifecycles, max same-day entries, overlap percentage, and rough capital risk count. Sector mapping is optional only when an existing mapping can be read without new infrastructure.

- [ ] **Step 7: Implement formal status precedence exactly**

```python
if not integrity_ok:
    final_status = "INVALID_RESEARCH_RUN"
elif lower_count < 300 or first_count < 100 or second_count < 100 or upper_count < 100:
    final_status = "INSUFFICIENT_EVIDENCE"
elif all(mandatory_strategy_gates):
    final_status = "PASS"
else:
    final_status = "FAIL"
```

When status is `INVALID_RESEARCH_RUN`, the report must say profitability gates are not interpretable rather than presenting them as a strategy verdict.

- [ ] **Step 8: Generate required report text from artifacts**

`research_report.md` must contain:

```text
Frozen hypothesis/rules
Universe/window/data coverage
Range-qualified session count
Lower/upper signal counts
Accepted/cancelled/completed/incomplete accounting
Cancellation reason counts
Lens A gross/base/stress/severe metrics
Lens B gross/base/stress/severe R and return metrics
Nifty500 excess
Target/stop/time-exit diagnostics
Upper mirror comparison
Temporal halves + calendar-year diagnostics
Top-five removal
Leave-one-year-out
Leave-one-symbol-out
Bootstrap intervals
Overlap/capacity diagnostics
Integrity audit
Every mandatory gate
Exactly one FINAL_STATUS
Explicit no-rescue / final-candidate statement
```

- [ ] **Step 9: Verify and commit Task 7**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_analysis.py"
```

```bash
git add "Swing Trading/research/swing/rr1_range_sweep_reversion/analyze_rr1_results.py" \
        "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_analysis.py"
git commit -m "research: add RR1 validation gates and reporting"
```

---

### Task 8: Add one deterministic end-to-end runner and freeze the real evidence package

**Files:**
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/run_rr1_validation.py`
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_end_to_end.py`
- Create: `Swing Trading/research/swing/rr1_range_sweep_reversion/README.md`
- Generate/commit: all formal CSV/report outputs under `output/`.

**Interfaces:**
- `run_validation() -> str` returning exactly one final status.
- CLI: `python run_rr1_validation.py` exits 0 for an interpretable `PASS`, `FAIL`, or `INSUFFICIENT_EVIDENCE`; exits non-zero for `INVALID_RESEARCH_RUN` or source/build failure.

- [ ] **Step 1: Write deterministic synthetic end-to-end test**

Build a small synthetic calendar containing:

```text
one accepted lower signal that reaches target
one accepted lower signal that stops
one lower signal cancelled for <2R
one lower signal cancelled by same-symbol lockout
one accepted upper mirror observation
one upper mirror lockout cancellation
one accepted late lower observation without T+16 -> incomplete
```

Assert:

```python
assert len(lower_signals) == len(lower_entries) + len(lower_cancellations)
assert set(lens_a.Entry_ID) == set(practical.Entry_ID)
assert incomplete_entry_id not in set(lens_a.Entry_ID)
assert integrity_audit["Passed"].all()
assert final_status in {"PASS", "FAIL", "INSUFFICIENT_EVIDENCE"}
```

Do not make the tiny synthetic sample pass production sample gates; the test may expect `INSUFFICIENT_EVIDENCE` after all integrity checks pass.

- [ ] **Step 2: Run RED end-to-end test**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_end_to_end.py"
```

Expected: FAIL before runner exists.

- [ ] **Step 3: Implement the runner in immutable stage order**

```text
benchmark + canonical sessions + PIT membership
-> adjusted stock frames
-> exact range/ER/liquidity/ATR features
-> qualified lower/upper signals
-> lower entries/cancellations + upper references/cancellations
-> paired lower outcomes + upper outcomes
-> independent integrity/accounting audit
-> if valid: metrics/robustness/gates
-> report + FINAL_STATUS
```

Do not read previous RR1 output CSVs as inputs to the formal run unless a future explicitly reviewed checkpoint design is added. This first implementation should rebuild evidence from frozen source inputs in one run.

- [ ] **Step 4: Make report/evidence writes atomic enough to avoid stale mixed runs**

Before formal generation, write into a temporary run directory under the module, then replace the tracked `output/` evidence set only after the entire valid/interpretable pipeline finishes. On source/build failure or `INVALID_RESEARCH_RUN`, preserve the failure audit/report but do not combine new partial CSVs with prior successful outputs.

Do not build a generic checkpoint framework.

- [ ] **Step 5: Add README with exact run commands and research discipline**

README must state:

```bash
cd "Swing Trading"
python -m pytest -q research/swing/rr1_range_sweep_reversion/tests
python research/swing/rr1_range_sweep_reversion/run_rr1_validation.py
```

It must also state that RR1 is frozen, diagnostics cannot tune it, and RR1 is the final planned strategy-family test.

- [ ] **Step 6: Run module tests**

```bash
cd "Swing Trading"
python -m pytest -q research/swing/rr1_range_sweep_reversion/tests
```

Expected: all RR1 tests PASS.

- [ ] **Step 7: Run the full existing swing research suite before real evidence**

```bash
cd "Swing Trading"
python -m pytest -q research/swing
```

Expected: zero failures. Existing known warnings may be documented but not hidden.

- [ ] **Step 8: Run one fresh RR1 formal historical validation**

```bash
cd "Swing Trading"
python research/swing/rr1_range_sweep_reversion/run_rr1_validation.py
```

Do **not** change any frozen rule after seeing the result.

If the run fails because an observation required by RR1 is corrupt/misparsed, repair only that integrity/data bug with a regression test, then rerun the unchanged methodology. Do not solve data problems for securities/sessions that do not affect RR1 evidence.

- [ ] **Step 9: Inspect formal evidence mechanically**

Verify:

```text
rr1_integrity_audit.csv has zero mandatory failures
lower qualified = lower accepted + lower cancelled
lower accepted = paired completed + incomplete accepted
upper qualified = upper accepted + upper cancelled
upper accepted = completed + incomplete
Lens A completed IDs == Lens B completed IDs
rr1_validation_gates.csv contains every frozen gate
research_report.md contains exactly one FINAL_STATUS
```

If sample minima fail, keep `INSUFFICIENT_EVIDENCE`. Do not extend dates or loosen rules.

- [ ] **Step 10: Commit the frozen real evidence**

```bash
git add "Swing Trading/research/swing/rr1_range_sweep_reversion"
git commit -m "research: validate RR1 range sweep reversion"
```

The commit must include code, tests, README, compact evidence CSVs, gate file, and report; it must not include raw Yahoo download caches.

- [ ] **Step 11: Final verification before PR**

Run again from the committed tree:

```bash
cd "Swing Trading"
python -m pytest -q research/swing/rr1_range_sweep_reversion/tests
python -m pytest -q research/swing
```

Then inspect:

```bash
git status --short
git diff HEAD^ -- "Swing Trading/research/swing/rr1_range_sweep_reversion/output/rr1_validation_gates.csv"
git diff HEAD^ -- "Swing Trading/research/swing/rr1_range_sweep_reversion/output/research_report.md"
```

Expected: tests pass; no unintended modified files; formal status is unchanged from the fresh run.

- [ ] **Step 12: Push and open the implementation PR linked to Issue #37**

Use a feature branch such as:

```text
feature/issue-37-rr1-range-sweep-reversion-validation
```

PR title:

```text
research: validate RR1 objective range sweep reversion
```

PR body must link Issue #37, the frozen spec, this implementation plan, test counts, data coverage, cohort counts, all gate outcomes, and the exact `FINAL_STATUS`. Keep Issue #37 open until the formal evidence and implementation are reviewed/merged.

---

## Plan Self-Review Checklist

Before execution begins, verify this plan against the spec:

- [ ] Range is exactly 60 pre-signal sessions and excludes T.
- [ ] ER60 denominator contains exactly 60 absolute changes ending T-1.
- [ ] Exact canonical `T-61..T` prehistory is enforced without forward fill.
- [ ] PIT and ₹10 crore liquidity are the only non-price-structure eligibility filters.
- [ ] Lower and upper definitions use strict inequality exactly as frozen.
- [ ] No volume/momentum/regime/sector filter leaked into eligibility.
- [ ] Lower target and stop are frozen before entry.
- [ ] Actual next Open is used for 2R economics.
- [ ] Lower/upper lockouts are separate and end at scheduled T+16 Open.
- [ ] Lens A and Lens B use the same completed lower IDs.
- [ ] Same-bar stop+target is stop-first.
- [ ] Practical benchmark excess uses percentage returns, while R gates use net R.
- [ ] Upper cohort is only a long-return reference, never a synthetic short strategy.
- [ ] Independent audit recomputes rather than trusts signal booleans.
- [ ] Sample insufficiency outranks economic FAIL.
- [ ] Median/win rate remain diagnostics only.
- [ ] Severe friction/bootstrap/other diagnostics do not become hidden mandatory gates.
- [ ] RR1 results cannot create Candidate 4.

## Execution Handoff

Plan implementation must use **inline `superpowers:executing-plans` only**, task-by-task with the TDD/commit checkpoints above. Do not use or suggest subagent-driven execution.
