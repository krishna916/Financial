# Strategy V2 Quality-Base Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use `subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable custom historical validator for Strategy V2 and mechanically report whether its precommitted signal-level gates pass, fail, or have insufficient evidence.

**Architecture:** Add one focused research module under `Swing Trading/research/swing/strategy_v2_quality_base/`. Reuse the committed point-in-time Nifty 500 membership and breadth datasets as read-only inputs; download one consistent adjusted OHLCV history; build point-in-time Nifty 500 RS in memory; run a deterministic per-symbol pivot/base state machine; allow exactly one next-session entry opportunity; simulate the two locked exit lenses; and emit compact audit/robustness outputs. Do not refactor existing T1 research.

**Tech Stack:** Python 3, pandas, numpy, yfinance, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-26-strategy-v2-quality-base-breakout-design.md`

**Issue:** `https://github.com/krishna916/Financial/issues/13`

## Global Constraints

- T1 remains retired. Strategy V2 is a new strategy family, not T5 and not a rescue experiment.
- Validation path is `CUSTOM_REQUIRED`; do not substitute a simplified Streak proxy.
- Primary signal window is `2023-08-01` through `2026-08-25` inclusive because committed point-in-time Nifty 500 membership starts on `2023-08-01`.
- Download warm-up OHLCV from `2022-01-01`; use `2026-08-27` as the yfinance exclusive end so the `2026-08-26` next-session Open can exist for a final-window signal. Trades without a completed exit by available data remain incomplete and are excluded from completed-trade gates.
- Use `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv` as the point-in-time universe source. Never backfill current membership into historical dates.
- A stock may use pre-membership prices for indicators, but it may signal only while active in the point-in-time Nifty 500 on the signal date.
- Use `yfinance` with `auto_adjust=True` for one consistent adjusted Open/High/Low/Close convention. Never mix adjusted and unadjusted OHLC inside a trade lifecycle.
- Preserve missing sessions. Never forward-fill OHLCV.
- Use standard Wilder ATR14: first ATR is the arithmetic mean of the first 14 valid True Range values; later ATR is `((prior_ATR * 13) + current_TR) / 14`.
- RS horizons are 21/63/126 sessions with 30/40/30 composite weights. Require `Composite_RS >= 70`.
- A date is research-safe for cross-sectional RS only if at least 80% of active Nifty 500 members have valid 21/63/126 returns. Do not rank an unsafe day for signal eligibility.
- Liquidity gate is 20-session median `Close * Volume >= ₹10 crore` on signal date.
- Trend gates are `Close > SMA50` and `SMA50 > SMA200`. Do not add rising SMA50.
- Pivot seed: `High[P]` equals the highest High over sessions `P-62..P`.
- Base session 1 is the next trading bar after the seed. Only one active base per symbol is tracked.
- Base duration is 10–30 sessions.
- Base depth is `(Active_Pivot - Base_Low) / ATR14_at_original_seed <= 4.0` at all times. If a failed probe raises `Active_Pivot`, recompute depth using the raised pivot immediately; if depth then exceeds 4.0, invalidate that base on the same bar.
- Failed probe is `High > Active_Pivot` and `Close <= Active_Pivot`; update pivot without resetting base age or seed ATR.
- Volatility contraction is `mean(TR of final 5 pre-breakout base bars) <= 0.80 * mean(TR of base bars 1..5)`.
- Breakout is `Close > Active_Pivot` during base sessions 10–30. The breakout bar is excluded from final-five contraction and structural-stop windows.
- Signal-day extension requires `Breakout_Close <= Active_Pivot + ATR14_signal`.
- Exactly one entry opportunity exists: immediately following market-session Open. Require `Active_Pivot <= Entry_Open <= Active_Pivot + ATR14_signal`.
- Structural stop is `lowest Low of final five pre-breakout base bars - 0.25 * ATR14_signal`.
- Reject before entry if `Structural_Stop >= Entry_Open` or `Entry_Open - Structural_Stop > 2.5 * ATR14_signal`.
- Structural stop stays fixed for this validation.
- Setup-quality lens ignores stop and exits at next Open after `Close < SMA20`.
- Practical lens uses fixed structural stop plus the same SMA20 close exit. Gap through stop exits at Open; intraday stop touch exits at stop.
- No profit target, breakeven move, trailing stop, time stop, volume gate, sector-RS gate, or breadth gate.
- Breadth is diagnostic only and must satisfy `Breadth_Matched_Date < Entry_Date` using the latest strict prior observation.
- Do not impose the ₹20k capital pool or 3–5-position cap in the first signal-level test.
- Do not optimize thresholds, remove inconvenient years/symbols, or add filters after results are known.
- Luna/Codex produces auditable evidence only. Portfolio Advisor decides what the result means.

---

## File Structure

Create:

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

Do **not** commit raw Yahoo downloads or a giant all-symbol daily feature cache. Rebuild daily data in memory; commit compact audits, signals, trades, summaries, report, code, and tests only.

---

### Task 1: Adjusted OHLCV, membership, and deterministic indicators

**Files:**
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/requirements.txt`
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/build_v2_features.py`
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_features.py`

**Interfaces:**

```python
load_membership(path: Path) -> pd.DataFrame
download_adjusted_ohlcv(ticker: str, start: str, end_exclusive: str) -> pd.DataFrame
compute_price_features(frame: pd.DataFrame) -> pd.DataFrame
active_members_on(membership: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame
```

- [ ] **Step 1: Create dependencies**

`requirements.txt`:

```text
numpy>=1.24
pandas>=2.0
yfinance>=0.2
pytest>=7.0
```

- [ ] **Step 2: Write concrete failing feature tests**

Start `test_v2_features.py` with imports and these tests:

```python
import numpy as np
import pandas as pd

from build_v2_features import active_members_on, compute_price_features


def test_active_members_on_uses_inclusive_intervals():
    membership = pd.DataFrame({
        "Symbol": ["AAA", "BBB"],
        "Member_From": pd.to_datetime(["2023-08-01", "2023-08-02"]),
        "Member_To": pd.to_datetime(["2023-08-02", "2023-08-03"]),
        "Downloadable": [True, True],
    })
    on_aug_1 = active_members_on(membership, pd.Timestamp("2023-08-01"))
    on_aug_2 = active_members_on(membership, pd.Timestamp("2023-08-02"))
    assert on_aug_1["Symbol"].tolist() == ["AAA"]
    assert set(on_aug_2["Symbol"]) == {"AAA", "BBB"}


def test_compute_price_features_uses_wilder_atr14():
    dates = pd.date_range("2023-01-01", periods=16, freq="D")
    frame = pd.DataFrame({
        "Date": dates,
        "Open": np.full(16, 100.0),
        "High": np.full(16, 101.0),
        "Low": np.full(16, 99.0),
        "Close": np.full(16, 100.0),
        "Volume": np.full(16, 1_000_000.0),
    })
    result = compute_price_features(frame)
    assert result.loc[13, "ATR14"] == 2.0
    assert result.loc[14, "ATR14"] == 2.0


def test_liquidity_is_twenty_session_median_close_times_volume():
    dates = pd.date_range("2023-01-01", periods=20, freq="D")
    frame = pd.DataFrame({
        "Date": dates,
        "Open": np.full(20, 100.0),
        "High": np.full(20, 101.0),
        "Low": np.full(20, 99.0),
        "Close": np.full(20, 100.0),
        "Volume": np.full(20, 1_000_000.0),
    })
    result = compute_price_features(frame)
    assert result.loc[19, "Median_Traded_Value_20"] == 100_000_000.0
```

Also add a no-forward-fill assertion by placing a `NaN` Close on one row and verifying `compute_price_features()` does not replace it with the prior Close.

- [ ] **Step 3: Run tests and verify failure**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_features.py"
```

Expected: import/function failures.

- [ ] **Step 4: Implement loader/downloader/indicators**

Lock constants:

```python
SIGNAL_START = pd.Timestamp("2023-08-01")
SIGNAL_END = pd.Timestamp("2026-08-25")
DOWNLOAD_START = "2022-01-01"
DOWNLOAD_END_EXCLUSIVE = "2026-08-27"
MIN_RS_COVERAGE = 0.80
LIQUIDITY_FLOOR = 100_000_000.0
```

`download_adjusted_ohlcv()` must call yfinance one ticker at a time with `auto_adjust=True`, `actions=False`, `progress=False`, normalize columns to `Date/Open/High/Low/Close/Volume`, sort ascending, make dates timezone-naive, reject duplicate dates, and never forward-fill.

`compute_price_features()` must add `True_Range`, Wilder `ATR14`, `SMA20`, `SMA50`, `SMA200`, `Median_Traded_Value_20`, `Return21`, `Return63`, and `Return126`.

- [ ] **Step 5: Run tests and verify pass**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_features.py"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: scaffold Strategy V2 price features"
```

---

### Task 2: Point-in-time Nifty 500 RS and data-quality audit

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/build_v2_features.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_features.py`
- Generate: `output/v2_data_validation.csv`
- Generate: `output/v2_universe_rs_audit.csv`

**Interfaces:**

```python
rank_point_in_time_rs(
    feature_frames: dict[str, pd.DataFrame],
    membership: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]
```

Each ranked feature row must expose `RS21`, `RS63`, `RS126`, `Composite_RS`, `RS_Active_Count`, `RS_Eligible_Count`, `RS_Coverage`, and `RS_Research_Safe`.

- [ ] **Step 1: Add concrete RS tests**

Use this synthetic ranked-day test:

```python
def test_rs_uses_only_active_members_and_locked_weights():
    date = pd.Timestamp("2023-08-10")
    membership = pd.DataFrame({
        "Symbol": ["AAA", "BBB", "CCC", "DDD"],
        "Member_From": pd.to_datetime(["2023-08-01"] * 4),
        "Member_To": pd.to_datetime(["2023-12-31"] * 4),
        "Downloadable": [True] * 4,
    })
    frames = {}
    for i, symbol in enumerate(["AAA", "BBB", "CCC", "DDD"], start=1):
        frames[symbol] = pd.DataFrame({
            "Date": [date],
            "Return21": [float(i)],
            "Return63": [float(i)],
            "Return126": [float(i)],
        })
    ranked, audit = rank_point_in_time_rs(frames, membership)
    assert ranked["DDD"].loc[0, "RS21"] == 100.0
    assert ranked["DDD"].loc[0, "Composite_RS"] == 100.0
    assert audit.loc[0, "RS_Coverage"] == 1.0
    assert bool(audit.loc[0, "RS_Research_Safe"])
```

Add a second test with five active members but only three having all return horizons; assert `RS_Coverage == 0.6`, `RS_Research_Safe == False`, and all same-day RS outputs remain ineligible for signal use.

Add a membership-change test where `EEE` starts tomorrow; assert `EEE` is absent from today's ranking even if its price frame has today's data.

- [ ] **Step 2: Run focused tests and confirm failure**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_features.py"
```

- [ ] **Step 3: Implement cross-sectional RS**

For each signal-window date:

1. Resolve active point-in-time membership with inclusive intervals.
2. `Active_Member_Count` includes every manifest member, including non-downloadable/dummy members, because the manifest is the official denominator.
3. RS-eligible means active plus valid current adjusted Close plus valid 21/63/126 returns.
4. `RS_Coverage = RS_Eligible_Count / Active_Member_Count`.
5. If coverage `< 0.80`, set `RS_Research_Safe=False`; do not allow that date to satisfy a signal's RS gate.
6. On safe dates rank each return horizon with:

```python
ranked = returns.rank(method="average", pct=True, ascending=True) * 100.0
```

7. Compute `Composite_RS = 0.30*RS21 + 0.40*RS63 + 0.30*RS126`.

Do not use the old fixed-20-stock RS dataset.

- [ ] **Step 4: Emit compact audits**

`v2_data_validation.csv` columns:

```text
Symbol,Yahoo_Ticker,Download_Start,Download_End,Raw_Rows,Duplicate_Dates,
Missing_Open,Missing_High,Missing_Low,Missing_Close,Missing_Volume,Usable
```

`v2_universe_rs_audit.csv` columns:

```text
Date,Active_Member_Count,Downloadable_Active_Count,RS_Eligible_Count,
RS_Coverage,RS_Research_Safe
```

- [ ] **Step 5: Run tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_features.py"
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: add point-in-time Nifty 500 RS"
```

---

### Task 3: Pivot/base state machine and signal-date gates

**Files:**
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py`
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py`
- Generate: `output/v2_base_state_audit.csv`
- Generate: `output/v2_signal_candidates.csv`

**Interfaces:**

```python
scan_symbol_bases(symbol: str, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]
```

Return `(state_audit, breakout_candidates)`.

- [ ] **Step 1: Build a concrete synthetic valid-base fixture**

In `test_v2_signals.py` create:

```python
import numpy as np
import pandas as pd

from generate_v2_signals import scan_symbol_bases


def make_valid_base_frame() -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=73, freq="D")
    rows = []
    for i, date in enumerate(dates):
        if i < 62:
            high, low, close, tr = 90.0, 88.0, 89.0, 2.0
        elif i == 62:
            high, low, close, tr = 100.0, 98.0, 99.0, 2.0
        elif 63 <= i <= 67:
            high, low, close, tr = 99.0, 95.0, 98.0, 4.0
        elif 68 <= i <= 71:
            high, low, close, tr = 99.0, 97.0, 98.5, 2.0
        else:
            high, low, close, tr = 102.0, 98.0, 101.0, 4.0
        rows.append({
            "Date": date,
            "Open": close,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": 2_000_000.0,
            "True_Range": tr,
            "ATR14": 2.0,
            "SMA50": 95.0,
            "SMA200": 90.0,
            "Median_Traded_Value_20": 200_000_000.0,
            "RS21": 80.0,
            "RS63": 80.0,
            "RS126": 80.0,
            "Composite_RS": 80.0,
            "RS_Coverage": 1.0,
            "RS_Research_Safe": True,
            "Point_In_Time_Member": True,
            "Breakout_Volume_Ratio": 1.0,
        })
    return pd.DataFrame(rows)
```

The seed is row 62. Rows 63–71 are nine base sessions. Row 72 is base session 10 and the breakout. Initial five base TR values average 4.0; final five pre-breakout values are one 4.0 plus four 2.0 values, average 2.4, so contraction ratio is 0.6 and passes.

- [ ] **Step 2: Write concrete state tests**

```python
def test_valid_breakout_occurs_on_base_session_ten():
    audit, candidates = scan_symbol_bases("AAA", make_valid_base_frame())
    assert len(candidates) == 1
    row = candidates.iloc[0]
    assert row["Base_Age"] == 10
    assert row["Active_Pivot"] == 100.0
    assert row["Contraction_Ratio"] == 0.6
    assert bool(row["Signal_Qualified"])
    assert "BREAKOUT_CANDIDATE" in set(audit["Event"])


def test_failed_probe_raises_pivot_without_resetting_age():
    frame = make_valid_base_frame()
    frame.loc[67, ["High", "Close"]] = [101.0, 99.0]
    frame.loc[72, ["High", "Close"]] = [103.0, 102.0]
    audit, candidates = scan_symbol_bases("AAA", frame)
    probe = audit[audit["Event"] == "FAILED_PROBE"].iloc[0]
    assert probe["Base_Age"] == 5
    assert probe["New_Pivot"] == 101.0
    assert candidates.iloc[0]["Base_Age"] == 10
    assert candidates.iloc[0]["Active_Pivot"] == 101.0


def test_failed_probe_rechecks_depth_using_raised_pivot():
    frame = make_valid_base_frame()
    frame.loc[67, ["High", "Low", "Close"]] = [104.0, 95.0, 99.0]
    audit, candidates = scan_symbol_bases("AAA", frame)
    events_on_probe_day = audit.loc[audit["Date"] == frame.loc[67, "Date"], "Event"].tolist()
    assert events_on_probe_day == ["FAILED_PROBE", "DEPTH_INVALIDATED"]
    assert len(candidates) == 0
```

Add deterministic tests for too-short breakout at age 9, valid breakout at age 30, expiration after age 30, and same-day reseeding after a too-short breakout when that same bar is a 63-session high.

- [ ] **Step 3: Run tests and confirm failure**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py"
```

- [ ] **Step 4: Implement exact state ordering**

While a base is active on bar `t`:

1. Increment age; update running base low with `Low[t]`.
2. If `Close[t] > Active_Pivot`, compute depth using the current pivot. If depth exceeds 4.0, record `DEPTH_INVALIDATED` and do not treat the bar as a breakout. Otherwise age `<10` records `TOO_SHORT_BREAKOUT`; age `10..30` freezes `BREAKOUT_CANDIDATE`. Either event closes the old base.
3. Else, if `High[t] > Active_Pivot` and `Close[t] <= Active_Pivot`, first record `FAILED_PROBE`, update `Active_Pivot = High[t]`, then recompute depth immediately with the raised pivot. If depth now exceeds 4.0, record `DEPTH_INVALIDATED` and close the base.
4. Else compute depth with the unchanged active pivot; depth breach records `DEPTH_INVALIDATED` and closes the base.
5. If still active at the end of base session 30 with no breakout, record `EXPIRED` and close the base.
6. After any close/cancel/invalidation, independently test the same bar as a possible new 63-session-high seed. A new seed starts a new base whose session 1 is the next bar.

Meaningful state events are exactly:

```text
SEEDED
FAILED_PROBE
DEPTH_INVALIDATED
TOO_SHORT_BREAKOUT
EXPIRED
BREAKOUT_CANDIDATE
```

- [ ] **Step 5: Freeze all signal-date gates into each candidate**

`v2_signal_candidates.csv` must include:

```text
Symbol,Seed_Date,Signal_Date,Base_Age,Original_Pivot,Active_Pivot,
ATR14_Seed,ATR14_Signal,Base_Low,Base_Depth_ATR,
Initial_TR_Mean,Final_TR_Mean,Contraction_Ratio,
Close,SMA50,SMA200,Median_Traded_Value_20,
RS21,RS63,RS126,Composite_RS,RS_Coverage,
Breakout_Volume_Ratio,Signal_Extension_ATR,
Membership_OK,RS_Coverage_OK,Liquidity_OK,Trend_OK,RS_OK,
Contraction_OK,Extension_OK,Signal_Qualified,Signal_Rejection_Reason
```

Gate conditions are exactly the Global Constraints. A close above pivot ends the old base even if `Signal_Qualified=False`.

Use fixed rejection-reason order:

```text
NOT_POINT_IN_TIME_MEMBER
RS_COVERAGE_UNSAFE
LIQUIDITY_FAIL
TREND_FAIL
RS_FAIL
CONTRACTION_FAIL
SIGNAL_EXTENDED
```

When multiple gates fail, join reasons with `;` in that order.

- [ ] **Step 6: Run tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py"
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: implement Strategy V2 base state machine"
```

---

### Task 4: Immediate next-session entry and structural stop

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py`
- Generate: `output/v2_entries.csv`
- Generate: `output/v2_entry_cancellations.csv`

**Interface:**

```python
build_entries(
    signals: pd.DataFrame,
    price_frames: dict[str, pd.DataFrame],
    market_sessions: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]
```

- [ ] **Step 1: Write concrete entry tests**

```python
def test_entry_uses_only_immediate_next_market_session():
    signals = pd.DataFrame([{
        "Entry_ID": "AAA-2023-08-10",
        "Symbol": "AAA",
        "Signal_Date": pd.Timestamp("2023-08-10"),
        "Active_Pivot": 100.0,
        "ATR14_Signal": 4.0,
        "Final_5_Prebreakout_Low": 98.0,
        "Signal_Qualified": True,
    }])
    prices = {"AAA": pd.DataFrame({
        "Date": pd.to_datetime(["2023-08-11", "2023-08-14"]),
        "Open": [101.0, 102.0],
        "High": [103.0, 104.0],
        "Low": [99.0, 100.0],
        "Close": [102.0, 103.0],
    })}
    sessions = pd.DatetimeIndex(pd.to_datetime(["2023-08-10", "2023-08-11", "2023-08-14"]))
    accepted, cancelled = build_entries(signals, prices, sessions)
    assert cancelled.empty
    assert accepted.iloc[0]["Entry_Date"] == pd.Timestamp("2023-08-11")
    assert accepted.iloc[0]["Entry_Open"] == 101.0
    assert accepted.iloc[0]["Structural_Stop"] == 97.0


def test_missing_immediate_symbol_bar_cancels_instead_of_delaying():
    signals = pd.DataFrame([{
        "Entry_ID": "AAA-2023-08-10",
        "Symbol": "AAA",
        "Signal_Date": pd.Timestamp("2023-08-10"),
        "Active_Pivot": 100.0,
        "ATR14_Signal": 4.0,
        "Final_5_Prebreakout_Low": 98.0,
        "Signal_Qualified": True,
    }])
    prices = {"AAA": pd.DataFrame({
        "Date": pd.to_datetime(["2023-08-14"]),
        "Open": [101.0], "High": [103.0], "Low": [99.0], "Close": [102.0],
    })}
    sessions = pd.DatetimeIndex(pd.to_datetime(["2023-08-10", "2023-08-11", "2023-08-14"]))
    accepted, cancelled = build_entries(signals, prices, sessions)
    assert accepted.empty
    assert cancelled.iloc[0]["Cancellation_Reason"] == "MISSING_NEXT_SESSION_BAR"
```

Add exact cases asserting `OPEN_BELOW_PIVOT`, `OPEN_ABOVE_EXTENSION_LIMIT`, `STOP_NOT_BELOW_ENTRY`, and `STOP_TOO_WIDE`.

- [ ] **Step 2: Use objective market sessions**

Primary session calendar comes from:

`Swing Trading/research/swing/market_breadth/output/nifty500_breadth_daily.csv`

Use its `Date` rows, not weekday arithmetic. If the final `2026-08-25` signal needs `2026-08-26` and the breadth file ends on the 25th, append the objectively downloaded 26th session only when it is present in the market data. Never delay an entry because a stock-specific bar is missing.

- [ ] **Step 3: Implement cancellation precedence**

Use one primary reason in this order:

```text
MISSING_NEXT_SESSION
MISSING_NEXT_SESSION_BAR
OPEN_BELOW_PIVOT
OPEN_ABOVE_EXTENSION_LIMIT
STOP_NOT_BELOW_ENTRY
STOP_TOO_WIDE
```

For accepted entries:

```python
structural_stop = final_5_prebreakout_low - 0.25 * atr14_signal
initial_risk = entry_open - structural_stop
```

The accepted-entry file is immutable input to both exit lenses.

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py"
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: add Strategy V2 next-session entries"
```

---

### Task 5: Setup-quality and practical exit simulation

**Files:**
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py`
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py`
- Generate: `output/v2_setup_quality_trades.csv`
- Generate: `output/v2_practical_trades.csv`

**Interfaces:**

```python
simulate_setup_quality_trade(entry_row: pd.Series, prices: pd.DataFrame) -> dict | None
simulate_practical_trade(entry_row: pd.Series, prices: pd.DataFrame) -> dict | None
safe_profit_factor(values: pd.Series) -> float
```

- [ ] **Step 1: Write concrete exit tests**

```python
def test_practical_gap_below_stop_exits_at_open_and_can_be_worse_than_minus_one_r():
    entry = pd.Series({
        "Entry_ID": "AAA-1", "Entry_Date": pd.Timestamp("2023-08-10"),
        "Entry_Open": 100.0, "Structural_Stop": 95.0,
    })
    prices = pd.DataFrame({
        "Date": pd.to_datetime(["2023-08-10", "2023-08-11"]),
        "Open": [100.0, 90.0],
        "High": [102.0, 92.0],
        "Low": [99.0, 88.0],
        "Close": [101.0, 91.0],
        "SMA20": [98.0, 98.0],
    })
    result = simulate_practical_trade(entry, prices)
    assert result["Exit_Date"] == pd.Timestamp("2023-08-11")
    assert result["Exit_Price"] == 90.0
    assert result["Exit_Reason"] == "STOP_GAP"
    assert result["R_Multiple"] == -2.0


def test_practical_intraday_touch_exits_at_stop():
    entry = pd.Series({
        "Entry_ID": "AAA-1", "Entry_Date": pd.Timestamp("2023-08-10"),
        "Entry_Open": 100.0, "Structural_Stop": 95.0,
    })
    prices = pd.DataFrame({
        "Date": pd.to_datetime(["2023-08-10"]),
        "Open": [100.0], "High": [101.0], "Low": [94.0], "Close": [96.0], "SMA20": [90.0],
    })
    result = simulate_practical_trade(entry, prices)
    assert result["Exit_Price"] == 95.0
    assert result["Exit_Reason"] == "STOP_INTRADAY"
    assert result["R_Multiple"] == -1.0


def test_setup_quality_exits_next_open_after_close_below_sma20():
    entry = pd.Series({
        "Entry_ID": "AAA-1", "Entry_Date": pd.Timestamp("2023-08-10"),
        "Entry_Open": 100.0, "Structural_Stop": 95.0,
    })
    prices = pd.DataFrame({
        "Date": pd.to_datetime(["2023-08-10", "2023-08-11", "2023-08-14"]),
        "Open": [100.0, 101.0, 99.0],
        "High": [102.0, 102.0, 100.0],
        "Low": [99.0, 96.0, 98.0],
        "Close": [101.0, 97.0, 99.0],
        "SMA20": [98.0, 98.0, 98.0],
    })
    result = simulate_setup_quality_trade(entry, prices)
    assert result["Exit_Signal_Date"] == pd.Timestamp("2023-08-11")
    assert result["Exit_Date"] == pd.Timestamp("2023-08-14")
    assert result["Exit_Price"] == 99.0
```

Add a precedence test where yesterday's Close is below SMA20 and today's Open is also below the stop; assert the scheduled SMA20 exit closes at today's Open with `Exit_Reason="SMA20"` before today's intraday stop logic.

- [ ] **Step 2: Implement both lenses**

Setup-quality ignores stop completely. Practical checks each open session in this order:

```python
if scheduled_sma20_exit_today:
    exit at Open with reason SMA20
elif Open <= structural_stop:
    exit at Open with reason STOP_GAP
elif Low <= structural_stop:
    exit at structural_stop with reason STOP_INTRADAY
elif Close < SMA20:
    schedule next-session-open SMA20 exit
```

If a required future exit Open is unavailable at dataset end, return `None` and separately record the entry as incomplete.

- [ ] **Step 3: Implement metrics**

Setup-quality:

```python
Return = (Exit_Price - Entry_Open) / Entry_Open
```

Practical:

```python
Initial_Risk = Entry_Open - Structural_Stop
R_Multiple = (Exit_Price - Entry_Open) / Initial_Risk
```

`safe_profit_factor()` is positive sum divided by absolute negative sum; return `inf` when positives exist and no losses, `0.0` when losses exist and no positives, and `NaN` when neither exists.

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py"
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: simulate Strategy V2 exit lenses"
```

---

### Task 6: Strict-prior breadth, robustness, and precommitted gates

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py`
- Generate: summary/robustness CSVs listed in File Structure

**Interfaces:**

```python
attach_prior_breadth(trades: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame
summarize_lens(trades: pd.DataFrame, lens: str) -> dict
year_summary(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
outlier_robustness(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
leave_one_symbol_out(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
evaluate_gates(...) -> pd.DataFrame
```

- [ ] **Step 1: Write a concrete strict-prior breadth test**

```python
def test_breadth_join_forbids_equal_entry_date():
    trades = pd.DataFrame({
        "Entry_ID": ["A"],
        "Entry_Date": pd.to_datetime(["2023-08-10"]),
    })
    breadth = pd.DataFrame({
        "Date": pd.to_datetime(["2023-08-09", "2023-08-10"]),
        "Regime": ["NORMAL", "HOSTILE"],
    })
    joined = attach_prior_breadth(trades, breadth)
    assert joined.loc[0, "Breadth_Matched_Date"] == pd.Timestamp("2023-08-09")
    assert joined.loc[0, "Regime"] == "NORMAL"
    assert joined.loc[0, "Breadth_Matched_Date"] < joined.loc[0, "Entry_Date"]
```

Add tests that `evaluate_gates()` returns `INSUFFICIENT_EVIDENCE` at 99 completed setup-quality trades and cannot return `PASS` if any one locked gate is false.

- [ ] **Step 2: Implement strict-prior breadth attachment**

Load `Swing Trading/research/swing/market_breadth/output/nifty500_breadth_daily.csv` and use:

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

Rename matched date to `Breadth_Matched_Date` and assert every match is strictly earlier than entry. Breadth must not alter trade eligibility.

- [ ] **Step 3: Generate headline and year summaries**

`v2_validation_summary.csv` must report both lenses with completed trade count, winners, losers, win rate, mean/median return, return PF, mean/median R where applicable, R PF where applicable, and median holding sessions.

`v2_year_summary.csv` groups by **Entry_Date calendar year** and reports both lenses.

- [ ] **Step 4: Implement global top-winner robustness**

For `N = 1, 3, 5`, rank accepted entries by setup-quality `Return` descending, remove the global top N entry IDs, and recompute setup-quality and practical metrics on the same remaining entry IDs. Save exact removed IDs/symbols in `v2_outlier_robustness.csv`.

- [ ] **Step 5: Implement leave-one-symbol-out robustness**

For every accepted symbol remove all of its accepted entry IDs and recompute both lenses. One output row per omitted symbol.

- [ ] **Step 6: Implement breadth and overlap diagnostics**

`v2_breadth_summary.csv` reports both-lens metrics by the existing breadth regime labels.

`v2_overlap_diagnostic.csv` reports:

```text
Total_Accepted_Entries
Entries_With_Another_Open_Same_Symbol_Trade
Max_Simultaneous_Signal_Level_Trades
Max_Same_Day_Entries
```

These diagnostics do not change the primary signal set.

- [ ] **Step 7: Implement exact decision gates**

If setup-quality completed trades `<100`, final status is `INSUFFICIENT_EVIDENCE` regardless of profitability metrics.

At `>=100`, final status is `PASS` only if every gate is true:

```text
Setup-quality mean return > 0
Setup-quality return PF >= 1.20
Practical mean R >= +0.15
Practical R PF >= 1.20
At least two Entry_Date calendar years each have >=20 completed setup-quality trades,
  mean return >0, and return PF >=1.0
After global top-5 setup-quality winners are removed:
  setup-quality mean return >0 and return PF >=1.0
Every leave-one-symbol-out setup-quality sample has mean return >0 and return PF >=1.0
Zero point-in-time violations
```

If sample size is sufficient and any gate fails, final status is `FAIL`.

Write one row per gate plus the final status; never hide failed gates.

- [ ] **Step 8: Run tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py"
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: add Strategy V2 robustness gates"
```

---

### Task 7: End-to-end synthetic safety test

**Files:**
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_end_to_end.py`

- [ ] **Step 1: Create one deterministic integration test using the pure interfaces**

The fixture must include five synthetic active symbols so RS can be ranked. Give four symbols monotonic valid return histories and make `AAA` the strongest. Use the `make_valid_base_frame()` shape for `AAA`, point-in-time membership starting before the seed, and a breadth table with one row on the same entry date plus one row on the prior date.

The test must run the public functions in this order:

```text
compute_price_features
rank_point_in_time_rs
scan_symbol_bases
build_entries
simulate_setup_quality_trade
simulate_practical_trade
attach_prior_breadth
```

Then assert all of these concrete properties:

```python
assert len(accepted_entries) == 1
assert accepted_entries.iloc[0]["Symbol"] == "AAA"
assert accepted_entries.iloc[0]["Entry_Date"] > accepted_entries.iloc[0]["Signal_Date"]
assert setup_trade["Entry_ID"] == practical_trade["Entry_ID"]
assert joined.iloc[0]["Breadth_Matched_Date"] < joined.iloc[0]["Entry_Date"]
```

Also mutate the fixture once so contraction ratio exceeds 0.80 and assert zero accepted entries; mutate it once so breakout occurs at base age 9 and assert zero accepted entries.

- [ ] **Step 2: Run the V2 suite**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests"
```

Expected: PASS.

- [ ] **Step 3: Run all existing swing research tests**

```bash
python -m pytest -q "Swing Trading/research/swing"
```

Expected: all existing tests plus V2 tests PASS. Do not change old tests to make V2 fit.

- [ ] **Step 4: Commit**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base/tests"
git commit -m "test: cover Strategy V2 research flow end to end"
```

---

### Task 8: Historical execution, compact outputs, and factual report

**Files:**
- Create: `Swing Trading/research/swing/strategy_v2_quality_base/README.md`
- Generate and commit every `output/` file listed in File Structure
- Modify V2 scripts/tests only to correct implementation defects revealed by execution; never alter strategy parameters because of result quality

- [ ] **Step 1: Write README before full historical execution**

README must explicitly document:

```text
Strategy V2 is a new strategy family; T1 is retired
Design spec path and Issue #13
CUSTOM_REQUIRED rationale
Signal window 2023-08-01..2026-08-25
Point-in-time membership input path
Yahoo/yfinance auto_adjust=True convention
Wilder ATR14 formula
80% RS coverage safety rule
21/63/126 30/40/30 RS and Composite_RS >=70
10..30 base duration
4 ATR base depth
20% contraction requirement
1 ATR signal/entry extension limit
0.25 ATR structural-stop buffer
2.5 ATR maximum stop distance
SMA20 exit mechanics for both lenses
Breadth diagnostic-only strict-prior join
No sector/volume/breadth entry gates
No historical hindsight governance filter
Exact test/build commands
Every committed output and its purpose
No outcome-driven optimization
```

- [ ] **Step 2: Run the historical pipeline**

Canonical commands from repository root:

```bash
python "Swing Trading/research/swing/strategy_v2_quality_base/build_v2_features.py"
python "Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py"
python "Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py"
```

The scripts may share one in-process feature-build function to avoid repeated downloads, but do not add unrelated infrastructure or services.

- [ ] **Step 3: Fail on data/research-integrity defects before looking at profitability**

Programmatic assertions must reject the build for any of these:

```text
duplicate symbol/date OHLCV rows
non-monotonic symbol dates
mixed price adjustment conventions
membership interval parse failure
accepted signal on RS coverage below 80%
accepted signal for inactive point-in-time member
accepted signal with Composite_RS <70
accepted signal with base age outside 10..30
accepted signal with contraction ratio >0.80
accepted signal with signal extension >1 ATR
accepted entry not on immediate next market session
accepted entry outside pivot..pivot+1ATR
accepted stop >= entry
accepted stop distance >2.5ATR
Breadth_Matched_Date >= Entry_Date
setup/practical accepted Entry_ID set mismatch
```

A profitability gate failure is a valid research result, not a build failure.

- [ ] **Step 4: Generate `research_report.md` mechanically**

Report these sections in order:

1. Locked hypothesis and design-spec path.
2. Data window, adjustment convention, and point-in-time membership method.
3. Download/audit counts.
4. RS coverage minimum/median and unsafe-date count.
5. Base events and signal-rejection counts.
6. Qualified signals, accepted entries, and next-session cancellation counts.
7. Setup-quality headline metrics.
8. Practical headline metrics.
9. Entry-year summary.
10. Top-1/3/5 global-winner robustness.
11. Worst leave-one-symbol-out result and full CSV reference.
12. Breadth diagnostic summary.
13. Overlap diagnostic summary.
14. Every precommitted gate with explicit status.
15. Final `PASS`, `FAIL`, or `INSUFFICIENT_EVIDENCE`.

End exactly with:

> This report supplies locked evidence only. It does not tune Strategy V2 or prescribe a follow-up change. Portfolio Advisor retains the strategy decision.

- [ ] **Step 5: Run all swing tests after outputs are generated**

```bash
python -m pytest -q "Swing Trading/research/swing"
```

Expected: PASS.

- [ ] **Step 6: Verify no giant/raw cache is staged**

```bash
git status --short
git diff --stat
```

Only V2 code/tests/README and compact output evidence may be committed. Do not commit downloaded raw OHLCV or full daily feature matrices.

- [ ] **Step 7: Commit historical evidence**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: validate Strategy V2 quality-base breakout"
```

- [ ] **Step 8: Open the implementation PR**

PR title:

```text
research: validate Strategy V2 quality-base breakout
```

PR body must link Issue #13, list test/data-integrity results, state the mechanical final gate status, and explicitly say no threshold/filter was tuned after observing outcomes. Do not make a follow-up strategy recommendation in the PR.

---

## Final Verification Checklist

Before claiming Issue #13 implementation complete:

- [ ] `python -m pytest -q "Swing Trading/research/swing"` passes.
- [ ] Point-in-time membership is the committed official reconstruction.
- [ ] No signal occurs before `2023-08-01`.
- [ ] RS is active-universe Nifty 500 RS, not the old fixed-20-stock dataset.
- [ ] Every accepted signal has RS coverage `>=0.80` and `Composite_RS >=70`.
- [ ] No current-membership survivorship substitution exists.
- [ ] No OHLCV forward-fill exists.
- [ ] Wilder ATR14 is used consistently.
- [ ] Failed probes immediately re-check base depth using the raised pivot.
- [ ] Breakout candle is excluded from final-five contraction and stop windows.
- [ ] Every accepted entry is the immediate next market-session Open.
- [ ] No cancelled breakout receives a later delayed entry.
- [ ] Every structural stop is below entry and within `2.5 ATR14_signal`.
- [ ] Setup-quality and practical lenses share identical accepted Entry_IDs.
- [ ] Practical stop precedence handles scheduled SMA20 exit, gap stop, and intraday stop deterministically.
- [ ] Every breadth match is strictly before entry.
- [ ] Breadth, sector, and volume never gate primary entries.
- [ ] No capital-position constraint changes the primary signal set.
- [ ] Top-1/3/5 and leave-one-symbol-out outputs exist.
- [ ] Gate evaluation uses precommitted thresholds unchanged.
- [ ] No raw download or giant feature cache is committed.
- [ ] `research_report.md` contains evidence only and no result-driven optimization advice.

## Execution Handoff

Execute with **`superpowers:executing-plans` in inline mode only**. Work task-by-task, run the specified tests, and use the listed commits as checkpoints. Never invoke `subagent-driven-development`.