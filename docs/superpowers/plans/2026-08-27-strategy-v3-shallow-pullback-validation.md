# Strategy V3 Shallow-Pullback Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable historical validator for Strategy V3 and mechanically report whether the precommitted RS-leader shallow-pullback/resumption hypothesis passes, fails, or has insufficient evidence.

**Architecture:** Add one focused V3 research module under `Swing Trading/research/swing/strategy_v3_shallow_pullback/`. Reuse V2's proven data/indicator/RS and generic analysis semantics by copying them unchanged where the V3 spec explicitly says semantics are identical; do not modify V2 code or evidence. Implement a new deterministic per-symbol leader/pullback state machine, one-shot next-session entry logic, the locked setup/practical exit lenses, artifact-derived PIT integrity audit, predeclared diagnostics, robustness gates, and an evidence-only report.

**Tech Stack:** Python 3, pandas, numpy, yfinance, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-27-strategy-v3-shallow-pullback-resumption-design.md`

**Issue:** `https://github.com/krishna916/Financial/issues/16`

## Global Constraints

- T1 remains retired. Strategy V2 remains closed research evidence. Do not change T1/V2 methodology, outputs, thresholds, or historical results while implementing V3.
- V3 is a new strategy family, not a rescue experiment.
- Validation path is custom Python; do not substitute a Streak proxy or manual chart selection.
- Primary counted resumption-signal window is `2023-08-01` through `2026-08-25` inclusive.
- Leader seeds may occur up to exactly 10 canonical market sessions before `2023-08-01`, provided normal seed-date PIT membership, RS safety, liquidity, trend, and `Composite_RS >= 70` rules pass. Signals before `2023-08-01` are never counted.
- Download warmup is `2022-01-01`; yfinance end is exclusive `2026-08-27`, allowing a `2026-08-26` next-session Open where data exists.
- Use `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv` as the PIT universe source. Never backfill current membership historically.
- Use yfinance adjusted OHLCV with `auto_adjust=True`, `actions=False`, `progress=False`. Never mix adjusted and unadjusted OHLCV inside a trade lifecycle.
- Preserve missing sessions. Never forward-fill OHLCV.
- Use standard Wilder ATR14: first valid ATR is the arithmetic mean of the first 14 True Range observations; later ATR is `((prior_ATR * 13) + current_TR) / 14`.
- RS horizons are 21/63/126 sessions with 30/40/30 weights. `Composite_RS = 0.30*RS21 + 0.40*RS63 + 0.30*RS126`.
- A seed or signal is RS-safe only when at least 80% of active PIT Nifty 500 members have valid 21/63/126 returns on that date.
- Require on both seed and signal date: PIT membership active, `Median_Traded_Value_20 >= 100_000_000`, `Close > SMA50 > SMA200`, and `Composite_RS >= 70`.
- Leader seed: `Close[P] == highest Close over P-19..P`. Equality is intentional.
- One active V3 pullback per symbol.
- Pullback age starts at 1 on the first session after leader seed; valid resumption ages are 3 through 10 inclusive.
- Depth uses original seed ATR forever: `(Leader_Close - running lowest Low from pullback session 1 through current bar) / ATR14_Seed`.
- Hard state ordering is frozen: update age/window/depth; SMA50 invalidation; depth invalidation; new-leader close; resumption trigger; age-specific handling; expiry; then same-bar reseed after every closure.
- `Close < SMA50` invalidates before all other signal logic.
- Depth `> 2.5 ATR14_Seed` invalidates before new-leader/resumption logic.
- `Close > Leader_Close` closes as `NEW_LEADER_CLOSE`; it never creates a V3 candidate from the old state. Same bar may seed a fresh state.
- Resumption trigger is exactly `Close[t] > High[t-1] AND Close[t] > SMA20[t]`.
- Trigger at age 1 or 2 closes as `TOO_SHORT_RESUMPTION`.
- First trigger at age 3 through 10 creates exactly one candidate and closes the state regardless of later signal-gate acceptance.
- Candidate minimum depth is `>= 0.5 ATR14_Seed`; otherwise rejection is `PULLBACK_TOO_SHALLOW` and the old state is still finished.
- Qualified signal requires `Close <= Leader_Close`; a close above leader is handled earlier as `NEW_LEADER_CLOSE`.
- No resumption by the end of age 10 closes as `EXPIRED`.
- After **every** state closure, independently test the same bar as a fresh leader seed. A new state starts at age 0; its pullback session 1 is the following market session.
- All close-derived context must satisfy `Context_Date < Entry_Date`.
- Exactly one entry opportunity exists: the immediate next canonical market-session Open.
- Entry requires `Entry_Open >= SMA20_signal` and `Entry_Open <= Leader_Close + 0.5*ATR14_signal`.
- Structural stop is `running Pullback_Low through signal bar inclusive - 0.25*ATR14_signal`.
- Reject before entry if `Structural_Stop >= Entry_Open` or `Entry_Open - Structural_Stop > 2.5*ATR14_signal`.
- Structural stop remains fixed for the practical lens.
- Setup-quality lens ignores stop and exits at the immediate next Open after `Close < SMA20`.
- Practical lens precedence: previously scheduled SMA20 exit at current Open; else gap stop at Open; else intraday stop at stop; else schedule next-open exit after `Close < SMA20`.
- No target, breakeven rule, trailing ATR stop, hard time stop, volume gate, breadth gate, sector-RS gate, RSI/MACD/ADX, candlestick score, Fibonacci geometry, or hindsight news filter.
- Breadth and volume are diagnostics only.
- Do not impose capital occupancy, the user's starting capital, or a 3–5-position cap in this signal-level test.
- Do not tune duration/depth/RS/extension/stop thresholds or promote favorable diagnostic subgroups after outcomes are seen.
- Generated outputs must come from code. Do not manually edit historical result CSVs or report metrics.
- Luna/Codex produces auditable evidence only. Portfolio Advisor decides what the result means.

---

## File Structure

Create:

```text
Swing Trading/research/swing/strategy_v3_shallow_pullback/
├── README.md
├── requirements.txt
├── build_v3_features.py
├── generate_v3_signals.py
├── analyze_v3_results.py
├── tests/
│   ├── test_v3_features.py
│   ├── test_v3_signals.py
│   ├── test_v3_analysis.py
│   └── test_v3_end_to_end.py
└── output/
    ├── v3_data_validation.csv
    ├── v3_universe_rs_audit.csv
    ├── v3_pullback_state_audit.csv
    ├── v3_signal_candidates.csv
    ├── v3_entries.csv
    ├── v3_entry_cancellations.csv
    ├── v3_setup_quality_trades.csv
    ├── v3_practical_trades.csv
    ├── v3_validation_summary.csv
    ├── v3_year_summary.csv
    ├── v3_outlier_robustness.csv
    ├── v3_leave_one_symbol_out.csv
    ├── v3_breadth_summary.csv
    ├── v3_pullback_diagnostics.csv
    ├── v3_overlap_diagnostic.csv
    ├── v3_validation_gates.csv
    ├── research_report.md
    └── v3_point_in_time_violations.csv   # only when violations exist
```

Do **not** commit raw Yahoo downloads or a giant all-symbol daily feature cache. Rebuild daily feature frames in memory; commit compact audits, signals, trades, diagnostics, summaries, report, code, and tests only.

---

### Task 1: Reproduce the proven V2 data, indicator, membership, and PIT-RS infrastructure inside V3

**Files:**
- Create: `Swing Trading/research/swing/strategy_v3_shallow_pullback/requirements.txt`
- Create: `Swing Trading/research/swing/strategy_v3_shallow_pullback/build_v3_features.py`
- Create: `Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_features.py`

**Interfaces:**

```python
SIGNAL_START = pd.Timestamp("2023-08-01")
SIGNAL_END = pd.Timestamp("2026-08-25")
DOWNLOAD_START = "2022-01-01"
DOWNLOAD_END_EXCLUSIVE = "2026-08-27"
MIN_RS_COVERAGE = 0.80
LIQUIDITY_FLOOR = 100_000_000.0

load_membership(path: Path) -> pd.DataFrame
download_adjusted_ohlcv(ticker: str, start: str, end_exclusive: str) -> pd.DataFrame
compute_price_features(frame: pd.DataFrame) -> pd.DataFrame
active_members_on(membership: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame
rank_point_in_time_rs(
    feature_frames: dict[str, pd.DataFrame],
    membership: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]
build_feature_frames(
    membership: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict[str, str]]
```

- [ ] **Step 1: Create V3 dependencies**

`requirements.txt`:

```text
numpy>=1.24
pandas>=2.0
yfinance>=0.2
pytest>=7.0
```

- [ ] **Step 2: Copy only semantics-identical V2 feature infrastructure**

Start from:

```text
Swing Trading/research/swing/strategy_v2_quality_base/build_v2_features.py
```

Create `build_v3_features.py` with the same implementations for membership loading, adjusted one-ticker-at-a-time Yahoo download, no-forward-fill normalization, True Range, Wilder ATR14, SMA20/SMA50/SMA200, 20-session median traded value, 21/63/126 returns, active PIT membership, cross-sectional percentile RS, 80% coverage safety, and per-symbol data audit.

Do not import V2 output files and do not edit the V2 module. V3 owns an independent copy so later V3 work cannot mutate V2 evidence.

- [ ] **Step 3: Write deterministic equivalence tests before any V3-specific logic**

Create `test_v3_features.py`:

```python
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_v3_features import (
    active_members_on,
    compute_price_features,
    rank_point_in_time_rs,
)


def test_active_members_on_uses_inclusive_intervals():
    membership = pd.DataFrame({
        "Symbol": ["AAA", "BBB"],
        "Member_From": pd.to_datetime(["2023-08-01", "2023-08-02"]),
        "Member_To": pd.to_datetime(["2023-08-02", "2023-08-03"]),
        "Downloadable": [True, True],
    })
    assert active_members_on(membership, pd.Timestamp("2023-08-01"))["Symbol"].tolist() == ["AAA"]
    assert set(active_members_on(membership, pd.Timestamp("2023-08-02"))["Symbol"]) == {"AAA", "BBB"}


def test_compute_price_features_uses_wilder_atr14_and_does_not_forward_fill():
    frame = pd.DataFrame({
        "Date": pd.date_range("2023-01-01", periods=16, freq="D"),
        "Open": np.full(16, 100.0),
        "High": np.full(16, 101.0),
        "Low": np.full(16, 99.0),
        "Close": np.full(16, 100.0),
        "Volume": np.full(16, 1_000_000.0),
    })
    result = compute_price_features(frame)
    assert result.loc[13, "ATR14"] == 2.0
    assert result.loc[14, "ATR14"] == 2.0
    assert result.loc[15, "Median_Traded_Value_20"] != result.loc[15, "Median_Traded_Value_20"]  # fewer than 20 bars

    frame.loc[10, "Close"] = np.nan
    missing = compute_price_features(frame)
    assert pd.isna(missing.loc[10, "Close"])


def test_rs_uses_active_members_locked_weights_and_coverage():
    date = pd.Timestamp("2023-08-10")
    membership = pd.DataFrame({
        "Symbol": ["AAA", "BBB", "CCC", "DDD", "EEE"],
        "Member_From": pd.to_datetime(["2023-08-01"] * 5),
        "Member_To": pd.to_datetime(["2023-12-31"] * 5),
        "Downloadable": [True] * 5,
    })
    frames = {}
    for i, symbol in enumerate(["AAA", "BBB", "CCC", "DDD", "EEE"], start=1):
        frames[symbol] = pd.DataFrame({
            "Date": [date],
            "Return21": [float(i)],
            "Return63": [float(i)],
            "Return126": [float(i)],
        })
    ranked, audit = rank_point_in_time_rs(frames, membership)
    assert ranked["EEE"].loc[0, "RS21"] == 100.0
    assert ranked["EEE"].loc[0, "Composite_RS"] == 100.0
    assert audit.loc[0, "RS_Coverage"] == 1.0
    assert bool(audit.loc[0, "RS_Research_Safe"])

    frames["DDD"].loc[0, "Return126"] = np.nan
    frames["EEE"].loc[0, "Return63"] = np.nan
    _, unsafe = rank_point_in_time_rs(frames, membership)
    assert unsafe.loc[0, "RS_Coverage"] == 0.6
    assert not bool(unsafe.loc[0, "RS_Research_Safe"])
```

Also add a membership-change test where a sixth symbol starts on the following day; assert it is not in the current day's RS denominator/ranking.

- [ ] **Step 4: Run the focused feature tests**

Run from repository root:

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_features.py"
```

Expected: PASS.

If copying V2 code causes any of these tests to fail, fix only V3's copy. Do not edit V2 to make V3 work.

- [ ] **Step 5: Emit V3-prefixed data and RS audits**

`build_v3_features.py` must be capable of writing:

```text
output/v3_data_validation.csv
output/v3_universe_rs_audit.csv
```

Use the same columns and meanings as V2's equivalent audits. No V2 output path may be written.

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: scaffold Strategy V3 feature infrastructure"
```

---

### Task 2: Implement leader eligibility and the deterministic V3 pullback state machine

**Files:**
- Create: `Swing Trading/research/swing/strategy_v3_shallow_pullback/generate_v3_signals.py`
- Create: `Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py`

**Interfaces:**

```python
MIN_PULLBACK_AGE = 3
MAX_PULLBACK_AGE = 10
MIN_PULLBACK_DEPTH_ATR = 0.5
MAX_PULLBACK_DEPTH_ATR = 2.5
MIN_COMPOSITE_RS = 70.0
MAX_ENTRY_EXTENSION_ATR = 0.5
STOP_BUFFER_ATR = 0.25
MAX_STOP_DISTANCE_ATR = 2.5

is_leader_seed(frame: pd.DataFrame, index: int) -> bool
seed_eligibility(row: pd.Series) -> tuple[bool, str]
scan_symbol_pullbacks(
    symbol: str,
    frame: pd.DataFrame,
    canonical_market_sessions: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]
```

State events must use exact event names:

```text
SEEDED
SMA50_INVALIDATED
DEPTH_INVALIDATED
NEW_LEADER_CLOSE
TOO_SHORT_RESUMPTION
PULLBACK_TOO_SHALLOW
RESUMPTION_CANDIDATE
EXPIRED
```

- [ ] **Step 1: Create a deterministic synthetic frame helper**

Start `test_v3_signals.py` with a helper that creates at least 220 bars so SMA200 and the 20-session seed rule are genuinely available:

```python
def make_v3_frame() -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=230)
    close = np.linspace(80.0, 100.0, len(dates))
    frame = pd.DataFrame({
        "Date": dates,
        "Open": close,
        "High": close + 1.0,
        "Low": close - 1.0,
        "Close": close,
        "Volume": 2_000_000.0,
        "True_Range": 2.0,
        "ATR14": 2.0,
        "SMA20": close - 2.0,
        "SMA50": close - 4.0,
        "SMA200": close - 8.0,
        "Median_Traded_Value_20": 200_000_000.0,
        "RS21": 80.0,
        "RS63": 80.0,
        "RS126": 80.0,
        "Composite_RS": 80.0,
        "RS_Coverage": 1.0,
        "RS_Research_Safe": True,
        "Point_In_Time_Member": True,
    })
    return frame
```

Tests may overwrite the final 15–20 bars to create exact seed/pullback sequences. Do not derive expected values from the function under test.

- [ ] **Step 2: Write seed tests**

Add tests proving:

```python
def test_leader_seed_is_twenty_session_closing_high_with_equality_allowed():
    frame = make_v3_frame()
    i = 210
    frame.loc[i-19:i, "Close"] = np.linspace(90.0, 100.0, 20)
    frame.loc[i, "Close"] = 100.0
    assert is_leader_seed(frame, i)


def test_seed_rejects_any_failed_pit_eligibility_gate():
    row = pd.Series({
        "Point_In_Time_Member": True,
        "RS_Research_Safe": True,
        "RS_Coverage": 1.0,
        "Median_Traded_Value_20": 200_000_000.0,
        "Close": 100.0,
        "SMA50": 95.0,
        "SMA200": 90.0,
        "Composite_RS": 80.0,
    })
    assert seed_eligibility(row)[0]
    for column, bad in [
        ("Point_In_Time_Member", False),
        ("RS_Research_Safe", False),
        ("Median_Traded_Value_20", 99_999_999.0),
        ("Close", 94.0),
        ("Composite_RS", 69.99),
    ]:
        mutated = row.copy()
        mutated[column] = bad
        if column == "Close":
            mutated["SMA50"] = 95.0
        assert not seed_eligibility(mutated)[0]
```

Also add an explicit `SMA50 <= SMA200` rejection and `RS_Coverage < 0.80` rejection.

- [ ] **Step 3: Run seed tests and verify they fail before implementation**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py" -k "leader_seed or seed_rejects"
```

Expected: import/function failures.

- [ ] **Step 4: Implement seed detection and seed eligibility**

`is_leader_seed()`:

```python
def is_leader_seed(frame: pd.DataFrame, index: int) -> bool:
    if index < 19 or pd.isna(frame.loc[index, "Close"]):
        return False
    window = pd.to_numeric(frame.loc[index-19:index, "Close"], errors="coerce")
    return bool(window.notna().all() and float(frame.loc[index, "Close"]) == float(window.max()))
```

`seed_eligibility()` must return a boolean plus semicolon-separated failure codes drawn from:

```text
NOT_POINT_IN_TIME_MEMBER
RS_COVERAGE_UNSAFE
LIQUIDITY_FAIL
TREND_FAIL
RS_FAIL
```

Trend is exactly `Close > SMA50 > SMA200`; RS is exactly `Composite_RS >= 70`.

- [ ] **Step 5: Write state-ordering tests for all closure paths**

Add deterministic tests for these exact behaviors:

1. age 1 is the session immediately after seed;
2. depth uses original `Leader_Close`, running lowest Low, and original `ATR14_Seed`;
3. `Close < SMA50` closes as `SMA50_INVALIDATED` even if the same bar also exceeds 2.5 ATR or triggers resumption;
4. depth `>2.5` closes as `DEPTH_INVALIDATED` before new-leader/resumption logic;
5. `Close > Leader_Close` closes as `NEW_LEADER_CLOSE` without candidate;
6. resumption at age 1 or 2 closes `TOO_SHORT_RESUMPTION`;
7. resumption at age 3 creates a candidate;
8. resumption at age 10 creates a candidate;
9. no resumption through age 10 closes `EXPIRED`;
10. first trigger below 0.5 ATR records `PULLBACK_TOO_SHALLOW` and creates a candidate row with `Signal_Qualified=False` and rejection reason containing `PULLBACK_TOO_SHALLOW`;
11. same-bar reseeding occurs after **each** closure type when that bar is itself an eligible 20-session closing-high leader seed.

The same-bar reseed test must assert same-date event ordering. Example for new-leader closure:

```python
events = audit.loc[audit["Date"].eq(target_date), "Event"].tolist()
assert events == ["NEW_LEADER_CLOSE", "SEEDED"]
```

For `SMA50_INVALIDATED` and `DEPTH_INVALIDATED`, construct the bar so it qualifies as a seed after closure and assert `[closure, "SEEDED"]`.

- [ ] **Step 6: Implement the state machine using one closure/reseed path**

Use a single per-bar loop. After updating age, pullback indices, running low, and depth, apply this exact branch order:

```python
closed = False
candidate = None

if close < sma50:
    record("SMA50_INVALIDATED")
    closed = True
elif depth > MAX_PULLBACK_DEPTH_ATR:
    record("DEPTH_INVALIDATED")
    closed = True
elif close > leader_close:
    record("NEW_LEADER_CLOSE")
    closed = True
else:
    resumes = close > prior_high and close > sma20
    if resumes and age <= 2:
        record("TOO_SHORT_RESUMPTION")
        closed = True
    elif resumes and MIN_PULLBACK_AGE <= age <= MAX_PULLBACK_AGE:
        candidate = build_candidate(...)
        if depth < MIN_PULLBACK_DEPTH_ATR:
            record("PULLBACK_TOO_SHALLOW")
        else:
            record("RESUMPTION_CANDIDATE")
        candidates.append(candidate)
        closed = True
    elif age >= MAX_PULLBACK_AGE:
        record("EXPIRED")
        closed = True

if closed:
    active = None
    if seed_date_allowed(current_date, canonical_market_sessions) and is_leader_seed(data, index):
        ok, _ = seed_eligibility(row)
        if ok:
            active = new_state(...)
            record("SEEDED")
```

Do not implement separate reseed logic per closure type.

- [ ] **Step 7: Implement pre-window seed eligibility using canonical market sessions**

Add:

```python
prewindow_seed_start(
    canonical_market_sessions: pd.DatetimeIndex,
    signal_start: pd.Timestamp = SIGNAL_START,
) -> pd.Timestamp
```

Rules:

1. sort/deduplicate canonical sessions;
2. find the first session `>= SIGNAL_START`;
3. allow seeds from the session exactly 10 market sessions before that position through `SIGNAL_END`;
4. counted candidates still require `SIGNAL_START <= Signal_Date <= SIGNAL_END`.

Add a regression where a valid leader seed exactly 10 canonical sessions before `2023-08-01` survives into an in-window age-3..10 signal. Add another where the candidate signal itself is `2023-07-31`; assert it is excluded from `v3_signal_candidates.csv` counted window even if technically valid.

- [ ] **Step 8: Run signal-state tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py"
```

Expected: PASS.

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback/generate_v3_signals.py" \
        "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py"
git commit -m "research: add Strategy V3 pullback state machine"
```

---

### Task 3: Build candidate fields, signal qualification, one-shot next-session entries, and structural stops

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/generate_v3_signals.py`
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py`
- Generate: `output/v3_pullback_state_audit.csv`
- Generate: `output/v3_signal_candidates.csv`
- Generate: `output/v3_entries.csv`
- Generate: `output/v3_entry_cancellations.csv`

**Interfaces:**

```python
build_entries(
    signals: pd.DataFrame,
    price_frames: dict[str, pd.DataFrame],
    canonical_market_sessions: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]

validate_signal_integrity(
    signals: pd.DataFrame,
    entries: pd.DataFrame,
    canonical_market_sessions: pd.DatetimeIndex,
) -> None
```

Each candidate row must carry at minimum:

```text
Entry_ID,Symbol,Leader_Date,Signal_Date,Pullback_Age,
Leader_Close,ATR14_Seed,ATR14_Signal,Pullback_Low,Pullback_Depth_ATR,
Close,Prior_High,SMA20,SMA50,SMA200,Median_Traded_Value_20,
RS21,RS63,RS126,Composite_RS,RS_Coverage,Resumption_Volume_Ratio,
Seed_Membership_OK,Seed_RS_Coverage_OK,Seed_Liquidity_OK,Seed_Trend_OK,Seed_RS_OK,
Signal_Membership_OK,Signal_RS_Coverage_OK,Signal_Liquidity_OK,Signal_Trend_OK,Signal_RS_OK,
Age_OK,Depth_OK,Resumption_OK,Not_New_Leader_OK,
Signal_Qualified,Signal_Rejection_Reason
```

- [ ] **Step 1: Add exact signal-qualification tests**

Create a valid candidate fixture and mutate one gate at a time. Assert a candidate qualifies only with:

```text
Signal_Membership_OK = True
Signal_RS_Coverage_OK = True
Signal_Liquidity_OK = True
Signal_Trend_OK = True
Signal_RS_OK = True
3 <= Pullback_Age <= 10
0.5 <= Pullback_Depth_ATR <= 2.5
Resumption_OK = True
Close <= Leader_Close
```

Although seed gates already controlled state creation, keep seed gate values on the candidate artifact for PIT auditing.

Add an explicit test that a trigger closes the state even when signal-day RS falls to 69.9; there must be one candidate with `Signal_Qualified=False`, and no later trigger from that old leader may appear.

- [ ] **Step 2: Add resumption-volume diagnostic test**

If the signal bar has volume and at least 20 volume observations, store:

```python
Resumption_Volume_Ratio = signal_volume / median(last_20_session_volumes_including_signal)
```

If unavailable, store `NaN`. Never use this value in `Signal_Qualified`.

- [ ] **Step 3: Add immediate-next-session entry tests**

Use canonical sessions `2024-01-10`, `2024-01-11`, `2024-01-12` and a signal on Jan 10. Add exact tests for:

- accepted Jan 11 entry;
- `MISSING_NEXT_SESSION` when signal has no following canonical session;
- `MISSING_NEXT_SESSION_BAR` when the symbol has no Jan 11 bar even if Jan 12 exists;
- `OPEN_BELOW_SMA20_SIGNAL` when `Entry_Open < SMA20_signal`;
- `OPEN_ABOVE_EXTENSION_LIMIT` when `Entry_Open > Leader_Close + 0.5*ATR14_signal`;
- no waiting for Jan 12 after a Jan 11 cancellation.

- [ ] **Step 4: Add structural-stop tests**

Candidate stores `Pullback_Low` including the signal bar. Assert:

```python
Structural_Stop = Pullback_Low - 0.25 * ATR14_signal
```

Add cancellation tests for:

```text
STOP_NOT_BELOW_ENTRY
STOP_TOO_WIDE
```

`STOP_TOO_WIDE` means `Entry_Open - Structural_Stop > 2.5*ATR14_signal`.

- [ ] **Step 5: Implement entry handling with fixed precedence**

For each qualified signal:

1. find the immediate next canonical market session;
2. require exactly one symbol bar on that date;
3. read that bar's Open only;
4. test `Entry_Open < SMA20_signal` first;
5. test `Entry_Open > Leader_Close + 0.5*ATR14_signal` second;
6. compute fixed structural stop from signal artifact;
7. reject stop-not-below-entry;
8. reject stop-too-wide;
9. otherwise accept and store `Entry_Date`, `Entry_Open`, `Structural_Stop`, `Initial_Risk`.

Do not use the entry-day Close, High, Low, RS, breadth, or moving averages to justify entry.

- [ ] **Step 6: Add signal-integrity assertions**

`validate_signal_integrity()` must assert accepted entries:

- are backed by qualified signals;
- satisfy `Leader_Date < Signal_Date < Entry_Date`;
- have counted `Signal_Date` inside the locked window;
- occur on the immediate next canonical session;
- satisfy entry Open bounds;
- have stop below entry and within 2.5 ATR.

This function is an early invariant check; the artifact-derived PIT audit in Task 5 remains the authoritative final gate.

- [ ] **Step 7: Run tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py"
```

Expected: PASS.

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: add Strategy V3 signals and entries"
```

---

### Task 4: Implement locked setup-quality and practical exit lenses

**Files:**
- Create: `Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py`
- Create: `Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py`

**Interfaces:**

```python
simulate_setup_quality_trade(entry_row: pd.Series, prices: pd.DataFrame) -> dict[str, object] | None
simulate_practical_trade(entry_row: pd.Series, prices: pd.DataFrame) -> dict[str, object] | None
safe_profit_factor(values: pd.Series) -> float
summarize_lens(trades: pd.DataFrame, lens: str) -> dict[str, object]
```

- [ ] **Step 1: Copy V2's semantics-identical exit/profit-factor helpers into V3**

Use V2's `analyze_v2_results.py` as the source for:

- date/price normalization;
- `safe_profit_factor()`;
- setup SMA20 next-open exit;
- practical fixed-stop + SMA20 exit precedence;
- lens summary calculations.

Do not import or mutate V2 trade/output artifacts.

- [ ] **Step 2: Write the exact regression tests before relying on copied logic**

Add:

```python
def test_setup_exits_next_open_after_close_below_sma20():
    ...
    assert result["Exit_Signal_Date"] == pd.Timestamp("2024-01-11")
    assert result["Exit_Date"] == pd.Timestamp("2024-01-12")
    assert result["Exit_Reason"] == "SMA20"


def test_practical_scheduled_sma20_exit_precedes_same_day_stop():
    ...
    assert result["Exit_Reason"] == "SMA20"


def test_practical_gap_below_stop_exits_at_open_and_can_be_worse_than_minus_one_r():
    ...
    assert result["Exit_Reason"] == "STOP_GAP"
    assert result["R_Multiple"] < -1.0


def test_practical_intraday_touch_exits_at_fixed_stop():
    ...
    assert result["Exit_Reason"] == "STOP_INTRADAY"
    assert result["R_Multiple"] == -1.0
```

Also verify no target/time/breakeven/trailing stop exists in simulation behavior.

- [ ] **Step 3: Run focused analysis tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py" -k "setup or practical or profit_factor"
```

Expected: PASS after implementation.

- [ ] **Step 4: Commit**

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py" \
        "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py"
git commit -m "research: add Strategy V3 exit lenses"
```

---

### Task 5: Add strict-prior breadth, artifact-derived PIT integrity, and sample reconciliation

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py`
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py`
- Generate conditionally: `output/v3_point_in_time_violations.csv`

**Interfaces:**

```python
attach_prior_breadth(trades: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame
validate_trade_integrity(setup: pd.DataFrame, practical: pd.DataFrame) -> None
count_point_in_time_violations(
    signals: pd.DataFrame,
    entries: pd.DataFrame,
    setup: pd.DataFrame,
    practical: pd.DataFrame,
    membership: pd.DataFrame,
    canonical_market_sessions: pd.DatetimeIndex,
) -> tuple[int, pd.DataFrame]
```

PIT audit columns:

```text
Entry_ID,Symbol,Violation
```

Required violation codes:

```text
ACCEPTED_ENTRY_MISSING_QUALIFIED_SIGNAL
LEADER_NOT_BEFORE_SIGNAL
SIGNAL_NOT_BEFORE_ENTRY
SIGNAL_OUTSIDE_PRIMARY_WINDOW
PREWINDOW_SEED_TOO_EARLY
SEED_INACTIVE_MEMBER
SIGNAL_INACTIVE_MEMBER
SEED_RS_COVERAGE_UNSAFE
SIGNAL_RS_COVERAGE_UNSAFE
SEED_RS_BELOW_THRESHOLD
SIGNAL_RS_BELOW_THRESHOLD
ENTRY_NOT_IMMEDIATE_NEXT_SESSION
BREADTH_NOT_STRICT_PRIOR_SETUP
BREADTH_NOT_STRICT_PRIOR_PRACTICAL
LENS_ENTRY_ID_MISMATCH
```

- [ ] **Step 1: Copy and verify V2's strict-prior breadth join**

Use `pd.merge_asof(... direction="backward", allow_exact_matches=False)` so:

```text
Breadth_Matched_Date < Entry_Date
```

Add the regression where breadth has rows on Jan 9 and Jan 10 while entry is Jan 10; assert Jan 9 is attached.

- [ ] **Step 2: Add valid-zero PIT audit test**

Build one accepted entry with:

```text
Leader_Date = 2024-01-05
Signal_Date = 2024-01-10
Entry_Date = 2024-01-11
seed/signal membership = active
seed/signal RS safety = true
seed/signal Composite_RS = 80
breadth = 2024-01-10 or earlier, but strictly before Entry_Date
setup/practical Entry_ID sets equal
```

Assert `count == 0` and audit is empty.

- [ ] **Step 3: Add mutation tests for every timing/leakage family**

At minimum mutate the valid fixture to prove detection of:

- leader date equal to signal date;
- signal date equal to entry date;
- signal before `2023-08-01` and after `2026-08-25`;
- pre-window leader seed more than 10 canonical market sessions before Aug 1;
- inactive seed membership;
- inactive signal membership;
- unsafe seed RS coverage;
- unsafe signal RS coverage;
- seed RS 69.9;
- signal RS 69.9;
- entry delayed by one canonical session;
- breadth date equal to entry date;
- setup/practical Entry_ID mismatch.

Assert exact violation codes, not just non-zero counts.

- [ ] **Step 4: Implement artifact-derived PIT audit with no default-zero path**

The function must inspect actual signal/entry/lens artifacts and canonical membership/session inputs. Do **not** define a default `point_in_time_violations=0` anywhere in gate evaluation.

For membership checks, resolve `Leader_Date` and `Signal_Date` against the membership manifest, not against a current-symbol list.

For the pre-window boundary, use the canonical market-session index and compare the leader seed position with the first session `>= 2023-08-01`.

- [ ] **Step 5: Abort before profitability interpretation on any PIT violation**

Historical analysis must do:

```python
pit_count, pit_audit = count_point_in_time_violations(...)
if pit_count:
    pit_audit.to_csv(output_dir / "v3_point_in_time_violations.csv", index=False)
    raise AssertionError(f"point-in-time integrity violations: {pit_count}")
```

Only if count is exactly zero may robustness/profitability gates be generated.

- [ ] **Step 6: Add accounting reconciliation**

Before analysis continues, assert:

```python
qualified_ids = set(signals.loc[signals["Signal_Qualified"], "Entry_ID"])
accepted_ids = set(entries["Entry_ID"])
cancelled_ids = set(cancellations["Entry_ID"])
assert qualified_ids == accepted_ids | cancelled_ids
assert accepted_ids.isdisjoint(cancelled_ids)
assert set(setup["Entry_ID"]) == set(practical["Entry_ID"])
assert set(setup["Entry_ID"]).issubset(accepted_ids)
```

Incomplete accepted entries remain in `v3_entries.csv`; they are not silently dropped from acceptance or overlap accounting.

- [ ] **Step 7: Run PIT/breadth tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py" -k "breadth or point_in_time or integrity or mismatch"
```

Expected: PASS.

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: add Strategy V3 PIT integrity audit"
```

---

### Task 6: Add precommitted robustness gates, overlap, and diagnostic-only subgroup summaries

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py`
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py`
- Generate: summary/diagnostic CSVs under `output/`

**Interfaces:**

```python
year_summary(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
outlier_robustness(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
leave_one_symbol_out(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
overlap_diagnostic(entries: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
pullback_diagnostics(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
evaluate_gates(
    setup: pd.DataFrame,
    practical: pd.DataFrame,
    *,
    point_in_time_violations: int,
) -> pd.DataFrame
```

- [ ] **Step 1: Reuse V2 generic robustness semantics unchanged**

Copy V2's safe profit factor, paired-lens handling, year summary, top-1/3/5 winner removal, leave-one-symbol-out, and all-accepted-entry overlap logic where semantics are identical.

Overlap must start from **all accepted V3 entries**, left-join completed practical exit dates, fill only diagnostic interval math for incomplete positions through observation end, and report:

```text
Total_Accepted_Entries
Entries_With_Another_Open_Same_Symbol_Trade
Max_Simultaneous_Signal_Level_Trades
Max_Same_Day_Entries
```

Add a regression with 3 accepted entries but only 2 completed practical trades; assert `Total_Accepted_Entries == 3`.

- [ ] **Step 2: Add exact temporal-gate regression**

Create two years with 20 completed paired trades each. Give setup returns a positive mean and PF >=1.0 while practical `R_Multiple` is negative. Assert `TEMPORAL_ROBUSTNESS` still counts both years.

Year qualification is **only**:

```python
Setup_Completed_Trades >= 20
Setup_Mean_Return > 0
Setup_Return_PF >= 1.0
```

Never add `Practical_Mean_R` to year qualification.

- [ ] **Step 3: Add formal sample-status regression**

With 99 completed paired trades, even if every profitability gate passes:

```text
FINAL_STATUS = INSUFFICIENT_EVIDENCE
```

With >=100 trades, final status is `PASS` only if every locked gate passes; otherwise `FAIL`.

- [ ] **Step 4: Implement exact V3 gate rows**

`v3_validation_gates.csv` rows:

```text
COMPLETED_TRADES              >= 100
SETUP_MEAN_RETURN             > 0
SETUP_RETURN_PF               >= 1.20
PRACTICAL_MEAN_R              >= 0.15
PRACTICAL_R_PF                >= 1.20
TEMPORAL_ROBUSTNESS           >= 2 qualifying years
TOP_FIVE_OUTLIER_ROBUSTNESS   setup mean >0 and setup PF >=1.0 after top-5 removal
LEAVE_ONE_SYMBOL_OUT          every omission setup mean >0 and setup PF >=1.0
POINT_IN_TIME_INTEGRITY       == 0
FINAL_STATUS
```

`point_in_time_violations` is a required keyword-only argument with **no default**.

- [ ] **Step 5: Predeclare diagnostic buckets before historical outcomes are read**

`pullback_diagnostics()` must produce a long-form table with columns:

```text
Dimension,Bucket,Completed_Trades,Setup_Mean_Return,Setup_Return_PF,
Practical_Mean_R,Practical_R_PF
```

Use these fixed explanatory buckets:

```text
Pullback_Age:
  3-4, 5-6, 7-8, 9-10

Pullback_Depth_ATR:
  [0.5,1.0), [1.0,1.5), [1.5,2.0), [2.0,2.5]

Composite_RS:
  [70,80), [80,90), [90,100]

Resumption_Volume_Ratio:
  <0.8, [0.8,1.2), >=1.2, MISSING

Entry_Extension_ATR_vs_Leader:
  <=0, (0,0.25], (0.25,0.5]
```

Breadth regime remains in separate `v3_breadth_summary.csv` using the existing regime labels.

These subgroup outputs are **diagnostic only**. No subgroup gets a pass/fail gate.

- [ ] **Step 6: Run robustness tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py"
```

Expected: PASS.

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: add Strategy V3 robustness gates"
```

---

### Task 7: Wire the historical pipeline, generate evidence-only outputs, and add end-to-end invariants

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/build_v3_features.py`
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/generate_v3_signals.py`
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py`
- Create: `Swing Trading/research/swing/strategy_v3_shallow_pullback/README.md`
- Create: `Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_end_to_end.py`
- Generate all required `output/` artifacts

- [ ] **Step 1: Build one canonical market-session index**

Use the committed Nifty 500 breadth daily `Date` column as the canonical historical session spine for the locked window and pre-window seed boundary. If `2026-08-26` exists in downloaded market data but not the breadth file, append only that date for next-session-entry handling, matching V2's established convention.

Do not derive “next session” separately per symbol.

- [ ] **Step 2: Wire feature generation**

`build_v3_features.py` historical entry point must:

1. load PIT membership;
2. download/build adjusted feature frames;
3. build PIT cross-sectional RS using the official active-universe denominator;
4. write `v3_data_validation.csv` and `v3_universe_rs_audit.csv`;
5. keep feature frames in memory for the signal stage when run in-process, or deterministically rebuild them when scripts run separately.

Do not commit raw daily frames.

- [ ] **Step 3: Wire V3 signal generation**

`generate_v3_signals.py` historical entry point must:

1. obtain ranked feature frames;
2. scan each symbol from the allowed pre-window seed start through `2026-08-25`;
3. keep only candidate `Signal_Date` rows in the primary signal window;
4. build exactly one next-session decision for every qualified signal;
5. run early signal-integrity assertions;
6. write state audit, candidates, accepted entries, and cancellations.

Print deterministic counts:

```text
symbols=<N> candidates=<N> qualified=<N> entries=<N> cancellations=<N>
```

- [ ] **Step 4: Wire completed trade lenses and strict-prior breadth**

`analyze_v3_results.py` must download/rebuild each represented symbol's adjusted price series and simulate both lenses. Keep only paired completed outcomes in setup/practical completed-trade artifacts. Count and report incomplete accepted entries separately.

Attach breadth separately to both completed lens frames using strict-prior timing and then validate equal Entry_ID sets.

- [ ] **Step 5: Run PIT audit before any profitability interpretation**

Call `count_point_in_time_violations(...)`. If non-zero, write the violations CSV and raise immediately. If zero, do not create an empty violations file; instead record PIT gate value `0` in validation gates/report.

- [ ] **Step 6: Generate all summary outputs mechanically**

Write exactly the output set named in the spec, including:

```text
v3_validation_summary.csv
v3_year_summary.csv
v3_outlier_robustness.csv
v3_leave_one_symbol_out.csv
v3_breadth_summary.csv
v3_pullback_diagnostics.csv
v3_overlap_diagnostic.csv
v3_validation_gates.csv
research_report.md
```

- [ ] **Step 7: Make `research_report.md` evidence-only**

Report sections:

1. locked hypothesis and spec path;
2. data/timing convention;
3. download/data audit counts;
4. PIT-RS coverage;
5. pullback-state event counts;
6. candidate rejection/cancellation counts;
7. accepted/completed/incomplete accounting;
8. setup headline metrics;
9. practical headline metrics;
10. calendar-year summary;
11. top-1/3/5 robustness;
12. LOSO robustness;
13. breadth diagnostics;
14. pullback diagnostic buckets;
15. overlap diagnostic;
16. PIT integrity result;
17. precommitted gates;
18. final formal status.

Final sentence must state that the report does not tune V3 or prescribe a follow-up threshold/filter and that Portfolio Advisor retains interpretation.

- [ ] **Step 8: Add an end-to-end synthetic test**

`test_v3_end_to_end.py` must create a small synthetic two-symbol PIT universe and assert through the actual pipeline:

- one valid seed/pullback/resumption becomes a qualified signal;
- immediate-next-session entry is accepted;
- one separate signal is cancelled by the open rule;
- `qualified == accepted + cancelled`;
- setup/practical completed Entry_ID sets match;
- PIT audit returns zero;
- overlap accepted-entry count equals all accepted entries;
- gates accept an explicitly supplied PIT count only.

No network calls in this test; monkeypatch the downloader or pass synthetic frames.

- [ ] **Step 9: Run V3 tests and commit**

From repository root:

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests"
```

Expected: all V3 tests pass.

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: wire Strategy V3 validation pipeline"
```

---

### Task 8: Run the locked historical experiment and regenerate every V3 artifact

**Files:**
- Generate/update: all files under `Swing Trading/research/swing/strategy_v3_shallow_pullback/output/`
- Update generated evidence section only: `Swing Trading/research/swing/strategy_v3_shallow_pullback/README.md`

- [ ] **Step 1: Start from a clean working tree**

```bash
git status --short
```

Expected: no unrelated modifications. If unrelated files are dirty, stop and surface them rather than hiding them in the research commit.

- [ ] **Step 2: Run feature/data audit generation**

```bash
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/build_v3_features.py"
```

Expected: V3 data/RS audits generated with no PIT methodology fallback.

- [ ] **Step 3: Run the V3 state/signal/entry generation**

```bash
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/generate_v3_signals.py"
```

Record the printed symbol/candidate/qualified/entry/cancellation counts. Do not change thresholds based on them.

- [ ] **Step 4: Run locked outcome analysis**

```bash
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py"
```

If PIT audit fails, stop. Do not inspect profitability and then fix PIT issues selectively.

- [ ] **Step 5: Run a mechanical reconciliation script**

Execute from repository root:

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd

out = Path("Swing Trading/research/swing/strategy_v3_shallow_pullback/output")
signals = pd.read_csv(out / "v3_signal_candidates.csv")
entries = pd.read_csv(out / "v3_entries.csv")
cancels = pd.read_csv(out / "v3_entry_cancellations.csv")
setup = pd.read_csv(out / "v3_setup_quality_trades.csv")
practical = pd.read_csv(out / "v3_practical_trades.csv")
overlap = pd.read_csv(out / "v3_overlap_diagnostic.csv")
gates = pd.read_csv(out / "v3_validation_gates.csv")

qualified = signals.loc[signals["Signal_Qualified"].astype(str).str.lower().isin(["true", "1"])]
assert set(qualified["Entry_ID"]) == set(entries["Entry_ID"]) | set(cancels["Entry_ID"])
assert set(entries["Entry_ID"]).isdisjoint(set(cancels["Entry_ID"]))
assert set(setup["Entry_ID"]) == set(practical["Entry_ID"])
assert set(setup["Entry_ID"]).issubset(set(entries["Entry_ID"]))
assert int(overlap.loc[0, "Total_Accepted_Entries"]) == len(entries)
pit = gates.loc[gates["Gate"].eq("POINT_IN_TIME_INTEGRITY"), "Value"].iloc[0]
assert float(pit) == 0.0
status = gates.loc[gates["Gate"].eq("FINAL_STATUS"), "Status"].iloc[0]
print(
    f"qualified={len(qualified)} accepted={len(entries)} cancelled={len(cancels)} "
    f"completed={len(setup)} pit=0 status={status}"
)
PY
```

Expected: all assertions pass and one factual count line prints.

- [ ] **Step 6: Confirm no prohibited artifact or threshold change**

```bash
git status --short
find "Swing Trading/research/swing/strategy_v3_shallow_pullback" -type f -size +5M -print
```

Inspect the diff and ensure:

- no raw Yahoo cache or all-symbol daily cache is added;
- no V2 file changed;
- no V3 threshold/filter differs from the approved spec;
- diagnostic subgroup output did not become entry logic;
- report contains no recommendation to tune V3.

- [ ] **Step 7: Commit regenerated evidence**

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: record Strategy V3 historical validation"
```

---

### Task 9: Run full regression verification and prepare the implementation PR mechanically

**Files:**
- No methodology changes unless tests identify a genuine implementation defect.
- PR body/comment generated from actual artifacts and test output.

- [ ] **Step 1: Run the V3 suite from repository root**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests"
```

Expected: zero failures.

- [ ] **Step 2: Run the complete swing-research regression suite from the canonical package root**

```bash
cd "Swing Trading"
python -m pytest -q research/swing
cd ..
```

Expected: zero failures.

If failures remain, run the **exact same command** on the implementation branch base commit in a temporary worktree. Classify before changing code:

- base passes / V3 branch fails → V3 regression; fix only the cause;
- base and V3 fail identically → surface the pre-existing blocker; do not weaken tests;
- root-CWD only fails but canonical `Swing Trading` CWD passes → document canonical command; do not call it a strategy defect.

- [ ] **Step 3: Verify the implementation diff does not alter prior research**

```bash
git diff --name-only master...HEAD
```

Allowed paths are:

```text
Swing Trading/research/swing/strategy_v3_shallow_pullback/**
```

plus this already-approved V3 plan/spec history if branch ancestry includes them. Any change to V2/T1 code/output requires explicit Portfolio Advisor review before PR creation.

- [ ] **Step 4: Create the implementation PR only after fresh verification**

PR title:

```text
research: validate Strategy V3 shallow-pullback resumption
```

PR body must be populated from actual outputs, not manually remembered counts. It must contain:

```text
Implements #16.

## Scope
- Implements the locked Strategy V3 PIT Nifty 500 RS-leader → shallow-pullback → first-resumption state machine.
- Preserves one-shot next-session entry, structural stop, the two locked exit lenses, PIT audit, diagnostics and precommitted gates.
- Keeps T1 retired and V2 evidence unchanged.
- Does not tune V3 thresholds/filters after outcomes.

## Verification
- Strategy V3 tests: <actual passed count>.
- Full swing research suite: <actual passed count>.
- Audited/usable symbols: <actual>.
- Resumption candidates: <actual>.
- Qualified signals: <actual>.
- Accepted entries: <actual>.
- Completed paired outcomes: <actual>.
- Derived PIT violations: 0.
- Locked validation status: <actual PASS/FAIL/INSUFFICIENT_EVIDENCE>.

Portfolio Advisor retains strategy interpretation.
```

Do not type counts from memory. Read them from pytest output and generated CSVs immediately before `gh pr create`/PR edit.

- [ ] **Step 5: Add a factual completion comment to Issue #16**

Comment only after PR exists. Include PR link, exact generated counts, PIT count, test counts, and formal gate status. Do not interpret the strategy result in the engineering comment.

- [ ] **Step 6: End with a clean working tree**

```bash
git status --short
```

Expected: clean.

---

## Final Research-Integrity Checklist

Before asking Portfolio Advisor to review the implementation PR, verify every item mechanically:

- [ ] Leader seed is exactly a 20-session closing high with equality allowed.
- [ ] Seed eligibility enforces PIT membership, safe RS coverage, ₹10 crore median traded-value liquidity, `Close > SMA50 > SMA200`, and `Composite_RS >=70`.
- [ ] Pre-window seeds are limited to 10 canonical market sessions before 2023-08-01; counted signals remain strictly inside the primary window.
- [ ] Age starts at 1 only on the session after seed.
- [ ] Pullback depth uses original `Leader_Close`, running lowest Low, and original `ATR14_Seed`.
- [ ] `Close < SMA50` invalidation precedes all other state logic.
- [ ] >2.5 ATR depth invalidation precedes new-leader/resumption logic.
- [ ] `Close > Leader_Close` never creates a V3 candidate from the old state.
- [ ] Trigger is exactly `Close > previous High AND Close > SMA20`.
- [ ] Age 1–2 trigger is too short; age 3–10 first trigger is the only candidate attempt.
- [ ] <0.5 ATR first trigger ends the state as too shallow; no waiting for another trigger.
- [ ] Same-bar reseeding is tested after every closure type.
- [ ] Qualified signal requires `Close <= Leader_Close` and all signal PIT/RS/liquidity/trend gates.
- [ ] Exactly one immediate-next-market-session entry is attempted.
- [ ] Entry Open lower/upper bounds use only signal-day SMA20/Leader_Close/ATR known before entry.
- [ ] Stop includes the signal bar's Low and subtracts 0.25 ATR14_signal.
- [ ] Stop-not-below-entry and >2.5 ATR stop distance cancel before entry.
- [ ] Setup lens and practical lens preserve locked SMA20/stop behavior and precedence.
- [ ] Breadth uses strict-prior date and remains diagnostic-only.
- [ ] Volume and all subgroup diagnostics remain diagnostic-only.
- [ ] Qualified signals reconcile exactly to accepted entries plus cancellations.
- [ ] Completed setup/practical Entry_ID sets match.
- [ ] Incomplete accepted entries remain in accepted/overlap accounting.
- [ ] Overlap uses all accepted entries.
- [ ] PIT integrity is derived from artifacts and has no silent default-zero path.
- [ ] Any non-zero PIT count aborts profitability interpretation.
- [ ] Temporal gate does not include Practical_Mean_R.
- [ ] Formal status below 100 completed paired trades is `INSUFFICIENT_EVIDENCE` even if other gates pass.
- [ ] No V3 threshold/filter was changed after historical outcomes were generated.
- [ ] No T1/V2 research file or historical evidence changed.
- [ ] V3 tests and the full `research/swing` suite pass from their canonical commands.
- [ ] No raw Yahoo/all-symbol feature cache is committed.
- [ ] Final report is evidence-only; Portfolio Advisor retains interpretation.

## Execution Handoff

Execute this plan with:

```text
superpowers:executing-plans
```

**Inline execution only. Never use `superpowers:subagent-driven-development`.**

At each task boundary, run the named tests and commit before proceeding. Do not ask the user to choose technical parameters or review research execution details; surface only genuine requirement blockers, environment blockers, or conflicts with the frozen V3 spec.