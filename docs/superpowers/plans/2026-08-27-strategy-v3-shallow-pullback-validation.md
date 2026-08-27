# Strategy V3 Shallow-Pullback Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable historical validator for Strategy V3 and mechanically report whether the precommitted RS-leader shallow-pullback/resumption hypothesis passes, fails, or has insufficient evidence.

**Architecture:** Add one focused V3 research module under `Swing Trading/research/swing/strategy_v3_shallow_pullback/`. Copy V2 data/indicator/RS and generic analysis semantics only where the V3 spec says they are identical; never modify V2 code or evidence. Add a new deterministic leader/pullback state machine, one-shot next-session entry logic, locked setup/practical exits, artifact-derived PIT audit, predeclared diagnostics, robustness gates, and an evidence-only report.

**Tech Stack:** Python 3, pandas, numpy, yfinance, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-27-strategy-v3-shallow-pullback-resumption-design.md`

**Issue:** `https://github.com/krishna916/Financial/issues/16`

## Global Constraints

- T1 remains retired. V2 remains closed research evidence. Do not change any T1/V2 methodology, threshold, code path, output, or historical result for V3.
- Primary counted resumption-signal window: `2023-08-01` through `2026-08-25` inclusive.
- A leader seed may occur up to exactly 10 **canonical market sessions** before `2023-08-01` only when the committed PIT membership manifest genuinely supports that date. Never backfill Aug-1 membership into earlier dates.
- Use `Swing Trading/nifty500_regime_daily.csv` as the canonical market-session spine because it extends before the primary window. If downloaded market data contains `2026-08-26` but the index file does not, append only that date for the final next-session entry opportunity.
- Use PIT membership from `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`.
- Download Yahoo daily OHLCV from `2022-01-01` through exclusive `2026-08-27` with `auto_adjust=True`, `actions=False`, `progress=False`. Never forward-fill OHLCV.
- Wilder ATR14 exactly as V2: first 14 valid True Range mean, then `((prior_ATR * 13) + current_TR) / 14`.
- RS horizons `21/63/126`, weights `0.30/0.40/0.30`, `Composite_RS >= 70`, and research-safe coverage `>= 0.80` of active PIT members.
- Seed and signal dates both require active PIT membership, safe RS coverage, 20-session median traded value `>= 100_000_000`, `Close > SMA50 > SMA200`, and `Composite_RS >= 70`.
- Leader seed is `Close[P] == max(Close[P-19:P])`; equality is intentional.
- One active pullback per symbol. Age 1 is the first session after seed. Valid resumption ages are 3–10 inclusive.
- Depth is `(Leader_Close - running Pullback_Low) / ATR14_Seed`; original seed ATR never changes.
- Frozen per-bar order: update age/window/low/depth → SMA50 invalidation → depth invalidation → new-leader closure → resumption test → age handling → expiry → centralized same-bar reseed attempt.
- Trigger exactly `Close[t] > High[t-1] AND Close[t] > SMA20[t]`.
- Age 1–2 trigger closes `TOO_SHORT_RESUMPTION`.
- First age 3–10 trigger creates exactly one candidate and closes the old state even when another signal gate fails.
- Candidate depth must be `>= 0.5`; otherwise rejection is `PULLBACK_TOO_SHALLOW` and the state ends.
- `Close > Leader_Close` closes `NEW_LEADER_CLOSE` and never becomes a candidate from the old state.
- No trigger through age 10 closes `EXPIRED`.
- Every closure goes through one shared reseed block. Integration-test all closure types where seed eligibility can coexist. `SMA50_INVALIDATED` cannot itself reseed because `Close < SMA50` contradicts seed trend eligibility `Close > SMA50`; test the no-reseed result while preserving the shared block.
- All close-derived context satisfies `Context_Date < Entry_Date`.
- One entry opportunity only: immediate next canonical session Open.
- Entry requires `Entry_Open >= SMA20_signal` and `Entry_Open <= Leader_Close + 0.5*ATR14_signal`.
- Structural stop is running pullback low through signal bar inclusive minus `0.25*ATR14_signal`.
- Reject if stop is not below entry or stop distance exceeds `2.5*ATR14_signal`.
- Setup lens ignores stop and exits next Open after `Close < SMA20`.
- Practical lens precedence: scheduled SMA20 exit at current Open → gap stop at Open → intraday stop at fixed stop → schedule next-open exit after `Close < SMA20`.
- No target, breakeven, trailing ATR stop, hard time stop, volume gate, breadth gate, sector-RS gate, RSI/MACD/ADX, candlestick scoring, Fibonacci geometry, hindsight event filter, or portfolio-capacity rule.
- Breadth, volume, pullback age/depth, RS bands, and entry extension are diagnostic only.
- No threshold/filter tuning after outcomes. Generated result artifacts are code-owned and must not be hand-edited.
- Luna/Codex produces evidence only. Portfolio Advisor interprets the result.

---

## File Map

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
    └── v3_point_in_time_violations.csv  # create only when violations exist
```

Never commit raw Yahoo downloads or a full all-symbol daily feature cache.

---

### Task 1: Reproduce V2 data/indicator/PIT-RS semantics inside V3

**Files:**
- Create: `requirements.txt`
- Create: `build_v3_features.py`
- Create: `tests/test_v3_features.py`

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
rank_point_in_time_rs(feature_frames: dict[str, pd.DataFrame], membership: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]
build_feature_frames(membership: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict[str, str]]
```

- [ ] **Step 1: Create dependencies**

```text
numpy>=1.24
pandas>=2.0
yfinance>=0.2
pytest>=7.0
```

- [ ] **Step 2: Copy semantics-identical V2 infrastructure**

Use `Swing Trading/research/swing/strategy_v2_quality_base/build_v2_features.py` as the exact source for membership parsing, Yahoo normalization/download, no-forward-fill behavior, True Range/Wilder ATR14, SMA20/50/200, median traded value, returns, PIT active-member resolution, data audit, and cross-sectional percentile RS. Do not modify V2.

- [ ] **Step 3: Extend only the RS ranking date range required by V3**

V2 ranks only its signal window. V3 must rank any genuinely supported pre-window membership date:

```python
membership_start = pd.to_datetime(membership["Member_From"]).min()
ranking_start = min(SIGNAL_START, membership_start)
all_dates = sorted({
    date
    for frame in frames.values()
    for date in frame.loc[frame["Date"].between(ranking_start, SIGNAL_END), "Date"].dropna()
})
```

If the manifest starts on Aug 1, pre-window rows remain ineligible; do not synthesize membership.

- [ ] **Step 4: Add exact deterministic tests**

Create these tests verbatim or with equivalent literal fixtures/assertions:

```python
def test_active_members_on_uses_inclusive_intervals():
    membership = pd.DataFrame({
        "Symbol": ["AAA", "BBB"],
        "Member_From": pd.to_datetime(["2023-08-01", "2023-08-02"]),
        "Member_To": pd.to_datetime(["2023-08-02", "2023-08-03"]),
        "Downloadable": [True, True],
    })
    assert active_members_on(membership, pd.Timestamp("2023-08-01"))["Symbol"].tolist() == ["AAA"]
    assert set(active_members_on(membership, pd.Timestamp("2023-08-02"))["Symbol"]) == {"AAA", "BBB"}


def test_compute_price_features_uses_wilder_atr_and_no_forward_fill():
    frame = pd.DataFrame({
        "Date": pd.date_range("2023-01-01", periods=20),
        "Open": np.full(20, 100.0),
        "High": np.full(20, 101.0),
        "Low": np.full(20, 99.0),
        "Close": np.full(20, 100.0),
        "Volume": np.full(20, 1_000_000.0),
    })
    out = compute_price_features(frame)
    assert out.loc[13, "ATR14"] == 2.0
    assert out.loc[19, "Median_Traded_Value_20"] == 100_000_000.0
    frame.loc[10, "Close"] = np.nan
    assert pd.isna(compute_price_features(frame).loc[10, "Close"])


def test_rs_sixty_percent_coverage_is_unsafe():
    date = pd.Timestamp("2023-08-10")
    membership = pd.DataFrame({
        "Symbol": ["A", "B", "C", "D", "E"],
        "Member_From": pd.to_datetime(["2023-08-01"] * 5),
        "Member_To": pd.to_datetime(["2023-12-31"] * 5),
        "Downloadable": [True] * 5,
    })
    frames = {
        symbol: pd.DataFrame({"Date": [date], "Return21": [float(i)], "Return63": [float(i)], "Return126": [float(i)]})
        for i, symbol in enumerate(["A", "B", "C", "D", "E"], start=1)
    }
    frames["D"].loc[0, "Return126"] = np.nan
    frames["E"].loc[0, "Return63"] = np.nan
    _, audit = rank_point_in_time_rs(frames, membership)
    assert audit.loc[0, "RS_Coverage"] == 0.6
    assert not bool(audit.loc[0, "RS_Research_Safe"])
```

Also add `test_pre_window_rs_requires_actual_pre_window_membership`: synthetic July membership produces July RS; changing `Member_From` to Aug 1 leaves July with no active denominator/eligible RS.

- [ ] **Step 5: Run tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_features.py"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: scaffold Strategy V3 feature infrastructure"
```

---

### Task 2: Implement the deterministic leader/pullback state machine

**Files:**
- Create: `generate_v3_signals.py`
- Create: `tests/test_v3_signals.py`

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

load_canonical_market_sessions(index_path: Path, extra_dates: pd.DatetimeIndex | None = None) -> pd.DatetimeIndex
prewindow_seed_start(canonical_sessions: pd.DatetimeIndex) -> pd.Timestamp
is_leader_seed(frame: pd.DataFrame, index: int) -> bool
seed_eligibility(row: pd.Series) -> tuple[bool, str]
new_state(symbol: str, row: pd.Series, index: int) -> dict[str, object]
build_candidate(symbol: str, row: pd.Series, prior_high: float, active: dict[str, object]) -> dict[str, object]
scan_symbol_pullbacks(symbol: str, frame: pd.DataFrame, canonical_sessions: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]
```

Exact events:

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

- [ ] **Step 1: Implement and test the canonical session spine**

`load_canonical_market_sessions()` reads `Swing Trading/nifty500_regime_daily.csv`, parses/sorts/deduplicates `Date`, and appends supplied `extra_dates` before final sorting.

`prewindow_seed_start()`:

```python
def prewindow_seed_start(canonical_sessions: pd.DatetimeIndex) -> pd.Timestamp:
    sessions = pd.DatetimeIndex(pd.to_datetime(canonical_sessions)).dropna().drop_duplicates().sort_values()
    pos = int(sessions.searchsorted(SIGNAL_START, side="left"))
    if pos < 10:
        raise ValueError("fewer than 10 canonical sessions before SIGNAL_START")
    return pd.Timestamp(sessions[pos - 10])
```

Test with `pd.bdate_range("2023-07-17", "2023-08-04")`; compute `pos` in the test independently and assert returned date equals `sessions[pos-10]`.

- [ ] **Step 2: Add a reusable literal state-test frame**

In `test_v3_signals.py`:

```python
def make_state_frame() -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=235)
    close = np.linspace(80.0, 99.0, len(dates))
    frame = pd.DataFrame({
        "Date": dates,
        "Open": close,
        "High": close + 0.5,
        "Low": close - 0.5,
        "Close": close,
        "Volume": np.full(len(dates), 2_000_000.0),
        "True_Range": np.full(len(dates), 2.0),
        "ATR14": np.full(len(dates), 2.0),
        "SMA20": close - 2.0,
        "SMA50": close - 4.0,
        "SMA200": close - 8.0,
        "Median_Traded_Value_20": np.full(len(dates), 200_000_000.0),
        "RS21": np.full(len(dates), 80.0),
        "RS63": np.full(len(dates), 80.0),
        "RS126": np.full(len(dates), 80.0),
        "Composite_RS": np.full(len(dates), 80.0),
        "RS_Coverage": np.full(len(dates), 1.0),
        "RS_Research_Safe": np.full(len(dates), True),
        "Point_In_Time_Member": np.full(len(dates), True),
    })
    seed = 220
    frame.loc[seed-19:seed, "Close"] = np.linspace(95.0, 100.0, 20)
    frame.loc[seed-19:seed, "High"] = frame.loc[seed-19:seed, "Close"] + 0.5
    frame.loc[seed-19:seed, "Low"] = frame.loc[seed-19:seed, "Close"] - 0.5
    frame.loc[seed, ["Open", "High", "Low", "Close", "ATR14"]] = [99.5, 100.5, 99.0, 100.0, 2.0]
    return frame
```

Every state test uses `seed = 220` and mutates only rows `221..230`.

- [ ] **Step 3: Test seed eligibility**

`is_leader_seed(frame, 220)` must be true. `seed_eligibility()` failure codes are exactly:

```text
NOT_POINT_IN_TIME_MEMBER
RS_COVERAGE_UNSAFE
LIQUIDITY_FAIL
TREND_FAIL
RS_FAIL
```

Create one valid `pd.Series` and five mutations; assert the corresponding exact code appears.

- [ ] **Step 4: Implement seed helpers**

```python
def is_leader_seed(frame: pd.DataFrame, index: int) -> bool:
    if index < 19 or pd.isna(frame.loc[index, "Close"]):
        return False
    window = pd.to_numeric(frame.loc[index-19:index, "Close"], errors="coerce")
    return bool(window.notna().all() and float(frame.loc[index, "Close"]) == float(window.max()))
```

`new_state()` stores `Leader_Date`, `Leader_Close`, `ATR14_Seed`, age `0`, `Pullback_Low=np.inf`, empty pullback indices, and seed PIT/RS/liquidity/trend fields needed later by the audit.

- [ ] **Step 5: Add exact state-regression matrix**

Use this table literally; mutate the specified row(s) and assert the exact result:

| Test | Mutation after seed 220 | Expected |
| --- | --- | --- |
| age1 | row221 Close=99, High=99.5, Low=98.5 | first active event row has age 1 |
| depth | row221 Low=96 | depth `(100-96)/2 == 2.0` |
| SMA50 precedence | row221 SMA50=99, Close=98, Low=93 | event `SMA50_INVALIDATED`, no candidate |
| depth precedence | row221 Low=94, Close=99 | event `DEPTH_INVALIDATED`, no candidate |
| new leader | row221 Close=100.2, High=100.4, Low=99.4 | events `NEW_LEADER_CLOSE`, then `SEEDED` if seed eligibility remains valid |
| too short | row221 High=99, row222 High=98.5 and Close=99.2 with prior High 98.5, SMA20=97 | `TOO_SHORT_RESUMPTION` at age 2 |
| valid age3 | rows221-222 lows 98/97.5; row223 prior High from row222=98.5, Close=99, SMA20=97 | one candidate age 3 |
| valid age10 | rows221-229 Close below each prior High; row230 Close above row229 High and SMA20 | one candidate age 10 |
| expiry | rows221-230 never satisfy trigger | `EXPIRED` at age 10 |
| too shallow | rows221-223 lows all >=99.2; row223 triggers | one rejected candidate, event `PULLBACK_TOO_SHALLOW` |
| signal gate fails | valid age3 trigger but row223 Composite_RS=69.9 | one rejected candidate, no later old-state candidate |

For same-bar reseeding, construct eligible 20-session closing-high bars for `DEPTH_INVALIDATED`, `NEW_LEADER_CLOSE`, `TOO_SHORT_RESUMPTION`, `PULLBACK_TOO_SHALLOW`, `RESUMPTION_CANDIDATE`, and `EXPIRED` and assert closure event followed by `SEEDED` on the same date. For `SMA50_INVALIDATED`, assert closure with no `SEEDED` because seed trend eligibility is impossible on that same bar.

- [ ] **Step 6: Implement the frozen loop without per-event reseed branches**

Use this exact structure:

```python
closed = False

if float(row["Close"]) < float(row["SMA50"]):
    record_event("SMA50_INVALIDATED")
    closed = True
elif depth > MAX_PULLBACK_DEPTH_ATR:
    record_event("DEPTH_INVALIDATED")
    closed = True
elif float(row["Close"]) > float(active["Leader_Close"]):
    record_event("NEW_LEADER_CLOSE")
    closed = True
else:
    resumes = float(row["Close"]) > float(prior_high) and float(row["Close"]) > float(row["SMA20"])
    if resumes and int(active["Age"]) <= 2:
        record_event("TOO_SHORT_RESUMPTION")
        closed = True
    elif resumes and MIN_PULLBACK_AGE <= int(active["Age"]) <= MAX_PULLBACK_AGE:
        candidate = build_candidate(symbol, row, float(prior_high), active)
        event = "PULLBACK_TOO_SHALLOW" if float(candidate["Pullback_Depth_ATR"]) < MIN_PULLBACK_DEPTH_ATR else "RESUMPTION_CANDIDATE"
        record_event(event)
        candidates.append(candidate)
        closed = True
    elif int(active["Age"]) >= MAX_PULLBACK_AGE:
        record_event("EXPIRED")
        closed = True

if closed:
    active = None
    if seed_date_allowed(pd.Timestamp(row["Date"]), canonical_sessions) and is_leader_seed(data, index):
        seed_ok, _ = seed_eligibility(row)
        if seed_ok:
            active = new_state(symbol, row, index)
            record_event("SEEDED")
```

- [ ] **Step 7: Test the primary-window boundary**

A synthetic manifest that is genuinely active 10 canonical sessions before Aug 1 may seed there and generate an Aug-1-or-later signal. A candidate whose `Signal_Date=2023-07-31` is excluded from counted candidate output.

- [ ] **Step 8: Run and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py"
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: add Strategy V3 pullback state machine"
```

---

### Task 3: Candidate qualification, one-shot entries, and structural stops

**Files:**
- Modify: `generate_v3_signals.py`
- Modify: `tests/test_v3_signals.py`

**Interfaces:**

```python
build_entries(signals: pd.DataFrame, price_frames: dict[str, pd.DataFrame], canonical_sessions: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]
validate_signal_integrity(signals: pd.DataFrame, entries: pd.DataFrame, canonical_sessions: pd.DatetimeIndex) -> None
```

Candidate columns must include:

```text
Entry_ID,Symbol,Leader_Date,Signal_Date,Pullback_Age,Leader_Close,
ATR14_Seed,ATR14_Signal,Pullback_Low,Pullback_Depth_ATR,Close,Prior_High,
SMA20,SMA50,SMA200,Median_Traded_Value_20,RS21,RS63,RS126,
Composite_RS,RS_Coverage,Resumption_Volume_Ratio,
Seed_Membership_OK,Seed_RS_Coverage_OK,Seed_Liquidity_OK,Seed_Trend_OK,Seed_RS_OK,
Signal_Membership_OK,Signal_RS_Coverage_OK,Signal_Liquidity_OK,Signal_Trend_OK,Signal_RS_OK,
Age_OK,Depth_OK,Resumption_OK,Not_New_Leader_OK,Signal_Qualified,Signal_Rejection_Reason
```

- [ ] **Step 1: Implement signal qualification with exact rejection codes**

Signal rejection codes:

```text
NOT_POINT_IN_TIME_MEMBER
RS_COVERAGE_UNSAFE
LIQUIDITY_FAIL
TREND_FAIL
RS_FAIL
AGE_FAIL
PULLBACK_TOO_SHALLOW
DEPTH_FAIL
RESUMPTION_FAIL
NEW_LEADER_FAIL
```

A valid candidate requires active signal membership, safe RS, liquidity floor, `Close>SMA50>SMA200`, RS>=70, age 3–10, depth 0.5–2.5, trigger true, and `Close<=Leader_Close`.

- [ ] **Step 2: Add candidate mutation tests**

Build one valid candidate fixture with literal values:

```python
valid = {
    "Entry_ID": "AAA-2024-01-10",
    "Symbol": "AAA",
    "Leader_Date": pd.Timestamp("2024-01-05"),
    "Signal_Date": pd.Timestamp("2024-01-10"),
    "Pullback_Age": 3,
    "Leader_Close": 100.0,
    "ATR14_Seed": 2.0,
    "ATR14_Signal": 2.0,
    "Pullback_Low": 98.0,
    "Pullback_Depth_ATR": 1.0,
    "Close": 99.5,
    "Prior_High": 99.0,
    "SMA20": 98.0,
    "SMA50": 95.0,
    "SMA200": 90.0,
    "Median_Traded_Value_20": 200_000_000.0,
    "Composite_RS": 80.0,
    "RS_Coverage": 1.0,
}
```

Mutate each gate independently and assert the exact code and `Signal_Qualified=False`. Include `Composite_RS=69.9`, age 2/11, depth 0.49/2.51, and Close 100.01.

- [ ] **Step 3: Record diagnostic volume only**

```python
Resumption_Volume_Ratio = signal_volume / median(last_20_session_volumes_including_signal)
```

If unavailable, store `NaN`. Never reference it in qualification.

- [ ] **Step 4: Add exact entry fixture/tests**

Use:

```python
signal = pd.DataFrame([{
    "Entry_ID": "AAA-2024-01-10",
    "Symbol": "AAA",
    "Signal_Date": pd.Timestamp("2024-01-10"),
    "Leader_Date": pd.Timestamp("2024-01-05"),
    "Leader_Close": 100.0,
    "SMA20": 98.0,
    "ATR14_Signal": 4.0,
    "Pullback_Low": 96.0,
    "Signal_Qualified": True,
}])
sessions = pd.DatetimeIndex(pd.to_datetime(["2024-01-10", "2024-01-11", "2024-01-12"]))
```

Test Jan-11 Open 99 accepted with stop `95.0`; Open 97.5 -> `OPEN_BELOW_SMA20_SIGNAL`; Open 102.1 -> `OPEN_ABOVE_EXTENSION_LIMIT`; missing Jan-11 symbol bar -> `MISSING_NEXT_SESSION_BAR`; no following canonical date -> `MISSING_NEXT_SESSION`. Assert no Jan-12 retry.

For stop tests, mutate `Pullback_Low` so stop is at/above entry -> `STOP_NOT_BELOW_ENTRY`, and so `Entry_Open-Stop > 2.5*ATR14_Signal` -> `STOP_TOO_WIDE`.

- [ ] **Step 5: Implement fixed decision precedence**

Immediate next canonical date → exact symbol bar → Open lower bound → Open upper bound → stop calculation → stop below entry → stop width → accept. Entry-day Close/High/Low/RS/breadth are never consulted.

- [ ] **Step 6: Add early integrity assertions**

Accepted entry must have a qualified signal, `Leader_Date<Signal_Date<Entry_Date`, primary-window signal, immediate-next session, Open bounds satisfied, stop below entry and within max distance.

- [ ] **Step 7: Run and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py"
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: add Strategy V3 signals and entries"
```

---

### Task 4: Locked exit lenses

**Files:**
- Create: `analyze_v3_results.py`
- Create: `tests/test_v3_analysis.py`

**Interfaces:**

```python
simulate_setup_quality_trade(entry_row: pd.Series, prices: pd.DataFrame) -> dict[str, object] | None
simulate_practical_trade(entry_row: pd.Series, prices: pd.DataFrame) -> dict[str, object] | None
safe_profit_factor(values: pd.Series) -> float
summarize_lens(trades: pd.DataFrame, lens: str) -> dict[str, object]
```

- [ ] **Step 1: Copy V2 semantics-identical analysis helpers**

Copy price normalization, profit factor, setup exit, practical fixed-stop/SMA20 precedence, and headline summary logic from V2. Do not import/mutate V2 outputs.

- [ ] **Step 2: Add literal exit tests**

Setup fixture:

```python
entry = pd.Series({"Entry_ID":"AAA-1","Symbol":"AAA","Entry_Date":pd.Timestamp("2024-01-10"),"Entry_Open":100.0,"Structural_Stop":95.0})
prices = pd.DataFrame({
    "Date": pd.to_datetime(["2024-01-10","2024-01-11","2024-01-12"]),
    "Open": [100.0,101.0,99.0],
    "High": [102.0,102.0,100.0],
    "Low": [99.0,96.0,98.0],
    "Close": [101.0,97.0,99.0],
    "SMA20": [98.0,98.0,98.0],
})
```

Assert setup signal Jan11, exit Jan12 Open 99. For practical scheduled-exit precedence, use Jan10 Close 97<SMA20 98 and Jan11 Open 90 with Low 88; assert exit reason `SMA20`, not stop. Add a separate gap-stop test with no prior SMA20 signal and Open 90 vs stop95 -> `STOP_GAP`, R=-2. Add intraday Low94 vs stop95 with Open100 -> `STOP_INTRADAY`, R=-1.

- [ ] **Step 3: Preserve V3 metadata on completed rows**

Completed rows retain `Leader_Date`, `Leader_Close`, `Signal_Date`, `ATR14_Signal`, `Pullback_Age`, `Pullback_Depth_ATR`, `Composite_RS`, and `Resumption_Volume_Ratio` from the accepted entry.

- [ ] **Step 4: Run and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py" -k "setup or practical or profit_factor"
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: add Strategy V3 exit lenses"
```

---

### Task 5: Strict-prior breadth, artifact-derived PIT audit, and accounting invariants

**Files:**
- Modify: `analyze_v3_results.py`
- Modify: `tests/test_v3_analysis.py`

**Interfaces:**

```python
attach_prior_breadth(trades: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame
validate_trade_integrity(setup: pd.DataFrame, practical: pd.DataFrame) -> None
count_point_in_time_violations(signals: pd.DataFrame, entries: pd.DataFrame, setup: pd.DataFrame, practical: pd.DataFrame, membership: pd.DataFrame, canonical_sessions: pd.DatetimeIndex) -> tuple[int, pd.DataFrame]
```

Exact PIT violation codes:

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

- [ ] **Step 1: Add breadth regression**

Trade entry Jan10, breadth rows Jan9 and Jan10. Use `pd.merge_asof(direction="backward", allow_exact_matches=False)` and assert Jan9 is matched.

- [ ] **Step 2: Add zero-PIT fixture and one mutation per code family**

Base fixture: Leader Jan5, Signal Jan10, Entry Jan11, both membership dates active, both RS-safe, both Composite_RS80, breadth Jan10 strictly before Jan11, equal lens Entry_ID sets. Assert zero violations.

Then create separate test mutations: Leader==Signal; Signal==Entry; Signal Jul31; pre-window leader 11 canonical sessions before Aug1; inactive seed; inactive signal; unsafe seed RS; unsafe signal RS; seed RS69.9; signal RS69.9; delayed entry; breadth==entry; lens mismatch. Assert the corresponding exact code exists.

- [ ] **Step 3: Implement PIT audit with no default-zero path**

Resolve membership on Leader_Date and Signal_Date against the manifest. Use canonical index-session positions for pre-window/next-session tests. `evaluate_gates` later receives PIT count explicitly and has no default.

- [ ] **Step 4: Abort before profitability interpretation**

```python
pit_count, pit_audit = count_point_in_time_violations(signals, entries, setup, practical, membership, canonical_sessions)
if pit_count:
    pit_audit.to_csv(output_dir / "v3_point_in_time_violations.csv", index=False)
    raise AssertionError(f"point-in-time integrity violations: {pit_count}")
```

Do not create an empty violations file on zero.

- [ ] **Step 5: Add accounting assertions**

```python
qualified_ids = set(signals.loc[signals["Signal_Qualified"].astype(bool), "Entry_ID"])
accepted_ids = set(entries["Entry_ID"])
cancelled_ids = set(cancellations["Entry_ID"])
assert qualified_ids == accepted_ids | cancelled_ids
assert accepted_ids.isdisjoint(cancelled_ids)
assert set(setup["Entry_ID"]) == set(practical["Entry_ID"])
assert set(setup["Entry_ID"]).issubset(accepted_ids)
```

- [ ] **Step 6: Run and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py" -k "breadth or point_in_time or integrity or mismatch"
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: add Strategy V3 PIT integrity audit"
```

---

### Task 6: Robustness gates, overlap, and predeclared diagnostics

**Interfaces:**

```python
year_summary(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
outlier_robustness(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
leave_one_symbol_out(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
overlap_diagnostic(entries: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
pullback_diagnostics(entries: pd.DataFrame, setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
evaluate_gates(setup: pd.DataFrame, practical: pd.DataFrame, *, point_in_time_violations: int) -> pd.DataFrame
```

- [ ] **Step 1: Copy V2 generic robustness functions where semantics are identical**

Use paired completed Entry_IDs, V2 year/outlier/LOSO math, and all-accepted-entry overlap logic. Regression: 3 accepted entries with only 2 completed practical exits must report `Total_Accepted_Entries=3`.

- [ ] **Step 2: Add exact temporal-gate test**

Create 40 setup rows: 20 in 2023 and 20 in 2024, each year with 15 returns `+0.02` and 5 returns `-0.01`. Practical R for all rows is `-0.25`. Assert `TEMPORAL_ROBUSTNESS` has Value `2` and Passed true. Do not include practical R in year qualification.

- [ ] **Step 3: Add exact sample-status test**

Generate 99 positive paired trades. Assert `FINAL_STATUS=INSUFFICIENT_EVIDENCE`. Generate 100 negative setup trades. Assert `FINAL_STATUS=FAIL`.

- [ ] **Step 4: Implement gate rows exactly**

```text
COMPLETED_TRADES              >=100
SETUP_MEAN_RETURN             >0
SETUP_RETURN_PF               >=1.20
PRACTICAL_MEAN_R              >=0.15
PRACTICAL_R_PF                >=1.20
TEMPORAL_ROBUSTNESS           >=2 qualifying years
TOP_FIVE_OUTLIER_ROBUSTNESS   setup mean>0 and setup PF>=1.0 after top5 winner removal
LEAVE_ONE_SYMBOL_OUT          every omission setup mean>0 and setup PF>=1.0
POINT_IN_TIME_INTEGRITY       ==0
FINAL_STATUS
```

- [ ] **Step 5: Implement fixed diagnostic buckets before historical outcomes are loaded**

`v3_pullback_diagnostics.csv` long-form columns:

```text
Dimension,Bucket,Completed_Trades,Setup_Mean_Return,Setup_Return_PF,Practical_Mean_R,Practical_R_PF
```

Fixed buckets:

```text
Pullback_Age: 3-4 | 5-6 | 7-8 | 9-10
Pullback_Depth_ATR: [0.5,1.0) | [1.0,1.5) | [1.5,2.0) | [2.0,2.5]
Composite_RS: [70,80) | [80,90) | [90,100]
Resumption_Volume_Ratio: <0.8 | [0.8,1.2) | >=1.2 | MISSING
Entry_Extension_ATR_vs_Leader=(Entry_Open-Leader_Close)/ATR14_Signal: <=0 | (0,0.25] | (0.25,0.5]
```

No diagnostic bucket receives a gate.

- [ ] **Step 6: Run and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py"
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: add Strategy V3 robustness gates"
```

---

### Task 7: Wire historical pipeline, evidence report, and end-to-end test

**Files:**
- Modify: all three V3 modules
- Create: `README.md`
- Create: `tests/test_v3_end_to_end.py`
- Generate all required outputs

- [ ] **Step 1: Use the long Nifty 500 index history for canonical sessions**

Canonical session dates come from `Swing Trading/nifty500_regime_daily.csv`; breadth daily is used only for strict-prior breadth context. Append 2026-08-26 only if it exists in downloaded market data and is absent from the index spine.

- [ ] **Step 2: Wire feature/signal scripts**

`build_v3_features.py`: manifest → adjusted frames → indicators → PIT RS → `v3_data_validation.csv` + `v3_universe_rs_audit.csv`.

`generate_v3_signals.py`: rebuild ranked frames → state scan → primary-window candidate filter → entries/cancellations → early integrity assertions → state/candidate/entry artifacts. Print `symbols`, `candidates`, `qualified`, `entries`, `cancellations` counts.

- [ ] **Step 3: Wire analysis script**

Rebuild represented-symbol prices → simulate both lenses → retain paired completed Entry_IDs → count incomplete accepted entries → strict-prior breadth → equal-lens validation → artifact PIT audit → robustness/diagnostics/gates → report.

- [ ] **Step 4: Generate the complete required output set**

Generate every output named in the File Map. `v3_point_in_time_violations.csv` exists only on failure.

- [ ] **Step 5: Generate evidence-only report**

Sections: hypothesis/spec; data/timing and pre-window PIT support; audit counts; RS coverage; state events; rejection/cancellation counts; accepted/completed/incomplete accounting; setup metrics; practical metrics; years; outliers; LOSO; breadth; pullback diagnostics; overlap; PIT; gates; final status. End with: `This report does not tune Strategy V3 or prescribe a follow-up threshold/filter. Portfolio Advisor retains strategy interpretation.`

- [ ] **Step 6: Add a no-network end-to-end test**

Synthetic two-symbol frames must produce: one accepted qualified signal, one cancelled qualified signal, exact `qualified=accepted+cancelled`, equal completed lens Entry_IDs, PIT count zero, overlap accepted count equal all accepted entries, and explicit PIT argument to gates. Monkeypatch downloader so test makes zero network calls.

- [ ] **Step 7: Run and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests"
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: wire Strategy V3 validation pipeline"
```

---

### Task 8: Run the locked historical experiment and reconcile artifacts

- [ ] **Step 1: Require a clean tree**

```bash
git status --short
```

Stop on unrelated modifications.

- [ ] **Step 2: Generate all historical stages**

```bash
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/build_v3_features.py"
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/generate_v3_signals.py"
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py"
```

Do not alter thresholds after seeing counts or outcomes. PIT failure stops the analysis.

- [ ] **Step 3: Run mechanical reconciliation**

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
qmask = signals["Signal_Qualified"].astype(str).str.lower().isin(["true", "1"])
qualified = signals.loc[qmask]
assert set(qualified["Entry_ID"]) == set(entries["Entry_ID"]) | set(cancels["Entry_ID"])
assert set(entries["Entry_ID"]).isdisjoint(set(cancels["Entry_ID"]))
assert set(setup["Entry_ID"]) == set(practical["Entry_ID"])
assert set(setup["Entry_ID"]).issubset(set(entries["Entry_ID"]))
assert int(overlap.loc[0, "Total_Accepted_Entries"]) == len(entries)
pit = gates.loc[gates["Gate"].eq("POINT_IN_TIME_INTEGRITY"), "Value"].iloc[0]
assert float(pit) == 0.0
status = gates.loc[gates["Gate"].eq("FINAL_STATUS"), "Status"].iloc[0]
print(f"qualified={len(qualified)} accepted={len(entries)} cancelled={len(cancels)} completed={len(setup)} pit=0 status={status}")
PY
```

- [ ] **Step 4: Audit prohibited changes/artifacts**

```bash
git status --short
find "Swing Trading/research/swing/strategy_v3_shallow_pullback" -type f -size +5M -print
git diff --name-only master...HEAD
```

No raw cache, no T1/V2 research change, no post-result threshold/filter change, no diagnostic promoted to gate.

- [ ] **Step 5: Commit evidence**

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: record Strategy V3 historical validation"
```

---

### Task 9: Fresh verification and mechanically generated implementation PR

- [ ] **Step 1: Capture fresh V3 test evidence**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests" | tee /tmp/v3-tests.txt
```

Require exit code zero.

- [ ] **Step 2: Capture fresh full-suite evidence**

```bash
cd "Swing Trading"
python -m pytest -q research/swing | tee /tmp/swing-tests.txt
cd ..
```

Require exit code zero. If failure exists, run the exact same command on branch base in a temporary worktree before classifying it.

- [ ] **Step 3: Create the PR with a deterministic metadata script**

Create temporary file `.v3_pr_create.py` in repo root, do **not** commit it:

```python
from pathlib import Path
import re
import subprocess
import pandas as pd

ROOT = Path.cwd()
OUT = ROOT / "Swing Trading/research/swing/strategy_v3_shallow_pullback/output"


def passed_count(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    matches = re.findall(r"(\d+) passed", text)
    if not matches:
        raise SystemExit(f"could not parse passed count from {path}")
    return int(matches[-1])

v3_tests = passed_count(Path("/tmp/v3-tests.txt"))
swing_tests = passed_count(Path("/tmp/swing-tests.txt"))
validation = pd.read_csv(OUT / "v3_data_validation.csv")
signals = pd.read_csv(OUT / "v3_signal_candidates.csv")
entries = pd.read_csv(OUT / "v3_entries.csv")
setup = pd.read_csv(OUT / "v3_setup_quality_trades.csv")
gates = pd.read_csv(OUT / "v3_validation_gates.csv")
qualified = signals["Signal_Qualified"].astype(str).str.lower().isin(["true", "1"]).sum()
pit = float(gates.loc[gates["Gate"].eq("POINT_IN_TIME_INTEGRITY"), "Value"].iloc[0])
if pit != 0.0:
    raise SystemExit(f"refusing PR creation with PIT violations={pit}")
status = gates.loc[gates["Gate"].eq("FINAL_STATUS"), "Status"].iloc[0]
usable = int(validation["Usable"].astype(str).str.lower().isin(["true", "1"]).sum())

body = f"""Implements #16.

## Scope
- Implements the locked Strategy V3 PIT Nifty 500 RS-leader → shallow-pullback → first-resumption state machine.
- Preserves one-shot next-session entry, structural stop, two locked exit lenses, PIT audit, diagnostics and precommitted gates.
- Keeps T1 retired and V2 evidence unchanged.
- Does not tune V3 thresholds/filters after outcomes.

## Verification
- Strategy V3 tests: {v3_tests} passed.
- Full swing research suite: {swing_tests} passed.
- Historical data: {usable}/{len(validation)} audited symbols usable.
- Resumption candidates: {len(signals)}.
- Qualified signals: {int(qualified)}.
- Accepted entries: {len(entries)}.
- Completed paired outcomes: {len(setup)}.
- Derived point-in-time violations: 0.
- Locked validation status: {status}.

Portfolio Advisor retains strategy interpretation.
"""

subprocess.run([
    "gh", "pr", "create",
    "--title", "research: validate Strategy V3 shallow-pullback resumption",
    "--body", body,
], check=True)
```

Run:

```bash
python .v3_pr_create.py
rm .v3_pr_create.py
```

If `gh` is not authenticated, stop and report the environment blocker; do not invent counts or manually reconstruct the PR body.

- [ ] **Step 4: Comment on Issue #16 from actual PR/artifacts**

Use `gh pr view --json url --jq .url` to obtain the PR URL. Reuse the same parsed counts from artifacts/test logs and add an evidence-only completion comment to Issue #16. No strategy interpretation in the engineering comment.

- [ ] **Step 5: End clean**

```bash
git status --short
```

Expected: clean.

---

## Final Research-Integrity Checklist

- [ ] Seed is exactly 20-session closing high with equality allowed.
- [ ] Seed and signal PIT/RS/liquidity/trend gates are exact.
- [ ] Pre-window session boundary uses the long Nifty 500 index history; pre-window PIT is never backfilled.
- [ ] V3 RS ranking covers genuinely supported pre-window dates when available.
- [ ] Age/depth/state ordering is exact.
- [ ] One centralized same-bar reseed path; logically compatible closure types have regression coverage.
- [ ] Trigger exactly `Close > previous High AND Close > SMA20`.
- [ ] First trigger only; age1–2 too short; age3–10 candidate; <0.5 depth ends setup.
- [ ] `Close > Leader_Close` never candidate from old state.
- [ ] Exactly one immediate-next-session entry.
- [ ] Entry bounds and stop use only signal-known data.
- [ ] Exit lenses preserve locked precedence.
- [ ] Breadth strict-prior and diagnostic-only; volume/subgroups diagnostic-only.
- [ ] Qualified = accepted + cancelled; accepted/cancelled disjoint.
- [ ] Completed lens Entry_ID sets equal.
- [ ] Incomplete accepted entries retained in overlap accounting.
- [ ] PIT derived from artifacts, no default-zero path, nonzero aborts interpretation.
- [ ] Temporal gate excludes Practical_Mean_R.
- [ ] Below 100 completed paired trades gives `INSUFFICIENT_EVIDENCE`.
- [ ] No result-driven threshold/filter changes.
- [ ] No T1/V2 evidence changes.
- [ ] V3 and full swing suites pass freshly.
- [ ] No raw Yahoo/all-symbol cache committed.
- [ ] Report evidence-only; Portfolio Advisor retains interpretation.

## Execution Handoff

Execute with:

```text
superpowers:executing-plans
```

**Inline execution only. Never use `superpowers:subagent-driven-development`.**

At every task boundary, run the named tests and commit before continuing. Do not ask the user to choose technical parameters or review research execution details; surface only genuine requirements/environment blockers or conflicts with the frozen spec.