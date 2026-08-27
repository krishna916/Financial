# Strategy V3 Shallow-Pullback Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable historical validator for Strategy V3 and mechanically report whether the precommitted RS-leader shallow-pullback/resumption hypothesis passes, fails, or has insufficient evidence.

**Architecture:** Add one focused V3 research module under `Swing Trading/research/swing/strategy_v3_shallow_pullback/`. Copy V2 data/indicator/RS and generic analysis semantics only where the V3 spec says they are identical; never modify V2 code or evidence. Add a new deterministic leader/pullback state machine, one-shot next-session entry logic, locked setup/practical exits, artifact-derived PIT audit, predeclared diagnostics, robustness gates, and an evidence-only report.

**Tech Stack:** Python 3, pandas, numpy, yfinance, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-27-strategy-v3-shallow-pullback-resumption-design.md`

**Issue:** `https://github.com/krishna916/Financial/issues/16`

## Global Constraints

- T1 remains retired. V2 remains closed research evidence. Do not change any T1/V2 methodology, threshold, code path, output, or historical result for V3.
- V3 is a new strategy family, not a rescue experiment.
- Primary counted resumption-signal window: `2023-08-01` through `2026-08-25` inclusive.
- A leader seed may occur up to exactly 10 **canonical market sessions** before `2023-08-01` only when the committed PIT membership manifest genuinely supports that seed date. Never backfill Aug-1 membership into earlier dates. If the manifest has no active PIT state before Aug 1, no pre-window seed may be created; document that data limitation rather than fabricating one.
- Use `Swing Trading/nifty500_regime_daily.csv` as the canonical session spine because it extends before the primary window. If `2026-08-26` exists in downloaded market data but not this index file, append only that date for the final next-session-entry opportunity.
- Download adjusted Yahoo OHLCV from `2022-01-01` through exclusive `2026-08-27` with `auto_adjust=True`, `actions=False`, `progress=False`. Never mix adjusted/unadjusted prices and never forward-fill OHLCV.
- PIT universe: `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`. Never use current constituents retrospectively.
- Wilder ATR14 exactly as V2: first 14 valid True Range mean, then `((prior_ATR * 13) + current_TR) / 14`.
- RS: 21/63/126-session returns, percentile-ranked across active PIT members, composite weights 30/40/30, `Composite_RS >= 70`.
- RS research-safe coverage: at least 80% of the active PIT Nifty 500 universe has valid 21/63/126 returns.
- Seed and signal date both require active PIT membership, safe RS coverage, `Median_Traded_Value_20 >= 100_000_000`, `Close > SMA50 > SMA200`, and `Composite_RS >= 70`.
- Leader seed: `Close[P] == highest Close over P-19..P`; equality is intentional.
- One active V3 pullback per symbol.
- Pullback age 1 is the first session after seed; valid resumption ages are 3–10 inclusive.
- Depth uses original seed ATR throughout: `(Leader_Close - running lowest Low from pullback session 1 through current bar) / ATR14_Seed`.
- Frozen per-bar ordering: update age/window/low/depth → `Close < SMA50` invalidation → depth `>2.5` invalidation → `Close > Leader_Close` new-leader closure → resumption trigger → age handling → expiry → same-bar reseed attempt.
- Resumption trigger exactly: `Close[t] > High[t-1] AND Close[t] > SMA20[t]`.
- Trigger at age 1–2 closes as `TOO_SHORT_RESUMPTION`.
- First trigger at age 3–10 creates exactly one candidate and closes the state even if later signal gates fail.
- Candidate requires minimum depth `>=0.5`; otherwise rejection `PULLBACK_TOO_SHALLOW` and no later trigger from that leader.
- `Close > Leader_Close` never becomes a V3 candidate from the old state; same bar may independently seed a fresh state.
- No trigger by the end of age 10 closes as `EXPIRED`.
- After **every** closure/invalidation/expiry, execute the same centralized same-bar reseed path. Integration tests must cover every closure where same-bar seed eligibility can logically coexist. `SMA50_INVALIDATED` itself cannot be seed-eligible because `Close < SMA50` contradicts the seed trend gate `Close > SMA50`; test that it closes and does not reseed, while the centralized reseed block remains common to all closures.
- All close-derived context must satisfy `Context_Date < Entry_Date`.
- Exactly one entry opportunity: immediate next canonical market-session Open.
- Entry requires `Entry_Open >= SMA20_signal` and `Entry_Open <= Leader_Close + 0.5*ATR14_signal`.
- Structural stop: running pullback low **through signal bar inclusive** minus `0.25*ATR14_signal`.
- Reject if `Structural_Stop >= Entry_Open` or `Entry_Open - Structural_Stop > 2.5*ATR14_signal`.
- Setup lens: ignore stop; next Open after `Close < SMA20`.
- Practical lens precedence: prior-close SMA20 scheduled exit at current Open → gap stop at Open → intraday stop at fixed stop → schedule next-open exit after `Close < SMA20`.
- No target, breakeven, trailing ATR stop, hard time stop, volume gate, breadth gate, sector-RS gate, RSI/MACD/ADX, candlestick score, Fibonacci geometry, or hindsight event filter.
- Breadth, volume, pullback age/depth, RS bands, and entry extension are diagnostic only.
- No capital occupancy or 3–5-position cap in this signal-level test.
- No threshold/filter tuning after outcomes. Generated outputs must come from code; never hand-edit result CSVs or metrics.
- Luna/Codex produces auditable evidence only. Portfolio Advisor interprets the research.

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
    └── v3_point_in_time_violations.csv  # only when violations exist
```

Do not commit raw Yahoo downloads or a giant all-symbol daily feature cache.

---

### Task 1: Reproduce V2 data/indicator/PIT-RS semantics inside V3

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

- [ ] **Step 1: Create minimal dependencies**

```text
numpy>=1.24
pandas>=2.0
yfinance>=0.2
pytest>=7.0
```

- [ ] **Step 2: Copy only semantics-identical infrastructure from V2**

Use `Swing Trading/research/swing/strategy_v2_quality_base/build_v2_features.py` as the source for membership loading, one-ticker adjusted download, price normalization, no-forward-fill behavior, True Range/Wilder ATR14, SMA20/50/200, traded-value median, 21/63/126 returns, PIT membership expansion, data audit, and cross-sectional percentile RS.

Do not import V2 output files and do not edit V2.

- [ ] **Step 3: Expand the RS ranking date range only as required for valid pre-window seeds**

V2 ranks only inside its signal window. V3 must rank every date from the **earliest actual PIT membership date available in the manifest** through `SIGNAL_END` so a genuinely supported pre-window seed can have PIT RS. Use:

```python
membership_start = pd.to_datetime(membership["Member_From"]).min()
ranking_start = min(SIGNAL_START, membership_start)
```

and collect ranking dates with:

```python
frame["Date"].between(ranking_start, SIGNAL_END)
```

If the manifest starts on `2023-08-01`, ranking naturally starts there; do not fabricate pre-window membership/RS.

- [ ] **Step 4: Write deterministic feature/RS tests**

Create `test_v3_features.py` with:

```python
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_v3_features import active_members_on, compute_price_features, rank_point_in_time_rs


def test_active_members_on_uses_inclusive_intervals():
    m = pd.DataFrame({
        "Symbol": ["AAA", "BBB"],
        "Member_From": pd.to_datetime(["2023-08-01", "2023-08-02"]),
        "Member_To": pd.to_datetime(["2023-08-02", "2023-08-03"]),
        "Downloadable": [True, True],
    })
    assert active_members_on(m, pd.Timestamp("2023-08-01"))["Symbol"].tolist() == ["AAA"]
    assert set(active_members_on(m, pd.Timestamp("2023-08-02"))["Symbol"]) == {"AAA", "BBB"}


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
    missing = compute_price_features(frame)
    assert pd.isna(missing.loc[10, "Close"])


def test_rs_uses_locked_weights_and_marks_sixty_percent_coverage_unsafe():
    d = pd.Timestamp("2023-08-10")
    m = pd.DataFrame({
        "Symbol": ["A", "B", "C", "D", "E"],
        "Member_From": pd.to_datetime(["2023-08-01"] * 5),
        "Member_To": pd.to_datetime(["2023-12-31"] * 5),
        "Downloadable": [True] * 5,
    })
    frames = {
        s: pd.DataFrame({"Date": [d], "Return21": [float(i)], "Return63": [float(i)], "Return126": [float(i)]})
        for i, s in enumerate(["A", "B", "C", "D", "E"], start=1)
    }
    ranked, audit = rank_point_in_time_rs(frames, m)
    assert ranked["E"].loc[0, "Composite_RS"] == 100.0
    assert audit.loc[0, "RS_Coverage"] == 1.0
    frames["D"].loc[0, "Return126"] = np.nan
    frames["E"].loc[0, "Return63"] = np.nan
    _, unsafe = rank_point_in_time_rs(frames, m)
    assert unsafe.loc[0, "RS_Coverage"] == 0.6
    assert not bool(unsafe.loc[0, "RS_Research_Safe"])
```

Also add a membership-change test proving a symbol whose `Member_From` is tomorrow is excluded from today's denominator/rank, and a synthetic pre-window membership test proving a genuinely active July date receives RS values.

- [ ] **Step 5: Run focused tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_features.py"
```

Expected: PASS.

- [ ] **Step 6: Emit V3-prefixed data/RS audits and commit**

Generate only:

```text
output/v3_data_validation.csv
output/v3_universe_rs_audit.csv
```

Then:

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: scaffold Strategy V3 feature infrastructure"
```

---

### Task 2: Implement the deterministic leader/pullback state machine

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

load_canonical_market_sessions(index_path: Path, extra_dates: pd.DatetimeIndex | None = None) -> pd.DatetimeIndex
is_leader_seed(frame: pd.DataFrame, index: int) -> bool
seed_eligibility(row: pd.Series) -> tuple[bool, str]
prewindow_seed_start(canonical_sessions: pd.DatetimeIndex) -> pd.Timestamp
scan_symbol_pullbacks(
    symbol: str,
    frame: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]
```

Exact state events:

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

- [ ] **Step 1: Load the canonical session spine from the long index history**

`load_canonical_market_sessions()` reads `Swing Trading/nifty500_regime_daily.csv`, parses/deduplicates/sorts `Date`, and optionally appends supplied extra dates. Do **not** use `market_breadth/output/nifty500_breadth_daily.csv` for the pre-window boundary because that file begins at the research window.

`prewindow_seed_start()` finds the first canonical session `>= 2023-08-01` and returns the session at exactly `position - 10`. Raise if fewer than 10 earlier canonical sessions exist.

Add an exact test using 15 business dates around Aug 1 and assert the returned date is the 10th canonical session before the first Aug-1-or-later session.

- [ ] **Step 2: Write seed tests before implementation**

Use a synthetic frame with at least 220 bars so SMA200 and the 20-session leader rule are real. Assert:

```python
def test_leader_seed_is_twenty_session_closing_high_with_equality_allowed():
    ...
    assert is_leader_seed(frame, seed_index)
```

`seed_eligibility()` must fail independently for:

```text
NOT_POINT_IN_TIME_MEMBER
RS_COVERAGE_UNSAFE
LIQUIDITY_FAIL
TREND_FAIL
RS_FAIL
```

Trend is exactly `Close > SMA50 > SMA200`; RS exactly `Composite_RS >=70`.

- [ ] **Step 3: Run seed tests and verify failure**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py" -k "leader_seed or seed_eligibility or prewindow"
```

Expected: import/function failures.

- [ ] **Step 4: Implement seed rules**

```python
def is_leader_seed(frame: pd.DataFrame, index: int) -> bool:
    if index < 19 or pd.isna(frame.loc[index, "Close"]):
        return False
    window = pd.to_numeric(frame.loc[index-19:index, "Close"], errors="coerce")
    return bool(window.notna().all() and float(frame.loc[index, "Close"]) == float(window.max()))
```

A seed is eligible only when its date is not earlier than `prewindow_seed_start`, not later than `SIGNAL_END`, and all seed gates pass. Membership/RS before Aug 1 is whatever the committed manifest actually says; empty membership means ineligible.

- [ ] **Step 5: Write state-ordering regressions**

Deterministically test all required behaviors:

1. age 1 starts on the first session after seed;
2. depth uses `Leader_Close`, running lowest Low, original `ATR14_Seed`;
3. `Close < SMA50` closes `SMA50_INVALIDATED` before other logic;
4. depth `>2.5` closes `DEPTH_INVALIDATED` before new-leader/resumption logic;
5. `Close > Leader_Close` closes `NEW_LEADER_CLOSE` without candidate;
6. trigger at age 1 or 2 closes `TOO_SHORT_RESUMPTION`;
7. trigger at age 3 creates a candidate;
8. trigger at age 10 creates a candidate;
9. no trigger through age 10 closes `EXPIRED`;
10. first trigger below 0.5 depth records `PULLBACK_TOO_SHALLOW`, writes one rejected candidate, and ends the old state;
11. first trigger closes state even when a separate signal gate fails;
12. same-bar reseed works for closure types where eligibility can coexist (`DEPTH_INVALIDATED`, `NEW_LEADER_CLOSE`, `TOO_SHORT_RESUMPTION`, `PULLBACK_TOO_SHALLOW`, `RESUMPTION_CANDIDATE`, `EXPIRED` when synthetically constructed as seed-eligible);
13. `SMA50_INVALIDATED` closes without reseed because the same bar cannot satisfy `Close > SMA50` seed eligibility.

For a same-bar new-leader case assert exact event order:

```python
events = audit.loc[audit["Date"].eq(target_date), "Event"].tolist()
assert events == ["NEW_LEADER_CLOSE", "SEEDED"]
```

- [ ] **Step 6: Implement one centralized closure/reseed block**

After age/window/low/depth update, use exactly:

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
        record("PULLBACK_TOO_SHALLOW" if depth < MIN_PULLBACK_DEPTH_ATR else "RESUMPTION_CANDIDATE")
        candidates.append(candidate)
        closed = True
    elif age >= MAX_PULLBACK_AGE:
        record("EXPIRED")
        closed = True

if closed:
    active = None
    if seed_date_allowed(current_date, canonical_sessions) and is_leader_seed(data, index):
        ok, _ = seed_eligibility(row)
        if ok:
            active = new_state(...)
            record("SEEDED")
```

Never introduce per-event reseed branches.

- [ ] **Step 7: Test primary-window accounting**

A supported leader seed exactly 10 canonical sessions before Aug 1 may produce an in-window signal. A technically valid signal dated Jul 31 must be excluded from counted `v3_signal_candidates.csv` output.

- [ ] **Step 8: Run state tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py"
```

Expected: PASS.

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: add Strategy V3 pullback state machine"
```

---

### Task 3: Build candidate qualification, one-shot entries, and structural stops

**Files:**
- Modify: `generate_v3_signals.py`
- Modify: `tests/test_v3_signals.py`
- Generate: `output/v3_pullback_state_audit.csv`, `v3_signal_candidates.csv`, `v3_entries.csv`, `v3_entry_cancellations.csv`

**Interfaces:**

```python
build_entries(
    signals: pd.DataFrame,
    price_frames: dict[str, pd.DataFrame],
    canonical_sessions: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]

validate_signal_integrity(
    signals: pd.DataFrame,
    entries: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex,
) -> None
```

Each candidate must carry:

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

- [ ] **Step 1: Add signal-gate mutation tests**

A candidate qualifies only when signal membership/RS coverage/liquidity/trend/RS are valid, age is 3–10, depth is 0.5–2.5, trigger is true, and `Close <= Leader_Close`. Mutate each gate independently and assert `Signal_Qualified=False` plus the exact rejection code.

Add a test where signal-day `Composite_RS=69.9`: exactly one rejected candidate appears and no later trigger from that leader is allowed.

- [ ] **Step 2: Record volume as diagnostic only**

```python
Resumption_Volume_Ratio = signal_volume / median(last_20_session_volumes_including_signal)
```

If unavailable, `NaN`. Never reference this value in qualification.

- [ ] **Step 3: Add exact next-session tests**

For a Jan-10 signal and canonical sessions Jan 10/11/12, test:

```text
accepted Jan-11 entry
MISSING_NEXT_SESSION
MISSING_NEXT_SESSION_BAR
OPEN_BELOW_SMA20_SIGNAL
OPEN_ABOVE_EXTENSION_LIMIT
```

A Jan-11 failure must never be retried on Jan 12.

- [ ] **Step 4: Add exact stop tests**

```python
Structural_Stop = Pullback_Low - 0.25 * ATR14_Signal
Initial_Risk = Entry_Open - Structural_Stop
```

Test cancellations:

```text
STOP_NOT_BELOW_ENTRY
STOP_TOO_WIDE
```

- [ ] **Step 5: Implement fixed entry-decision precedence**

For each qualified signal: immediate canonical next date → require symbol bar → read Open → lower-bound check → upper-extension check → compute stop → stop-below-entry check → stop-width check → accept.

Do not use entry-day Close/High/Low/RS/breadth to justify entry.

- [ ] **Step 6: Add early signal integrity assertions**

Accepted entries must be backed by qualified signals, satisfy `Leader_Date < Signal_Date < Entry_Date`, signal date inside the primary window, immediate-next canonical session, entry Open bounds, and stop sanity.

- [ ] **Step 7: Run tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py"
```

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: add Strategy V3 signals and entries"
```

---

### Task 4: Implement the two locked exit lenses

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

- [ ] **Step 1: Copy V2's semantics-identical helpers into V3**

Copy normalization, safe profit factor, setup SMA20 next-open exit, practical fixed-stop/SMA20 precedence, and lens summary logic from V2. Do not import/mutate V2 outputs.

- [ ] **Step 2: Add exact exit regressions**

Tests must prove:

```text
setup: Close<SMA20 on Jan11 -> exit Jan12 Open
practical: previously scheduled SMA20 exit wins over same-day stop logic
practical: Open<=stop exits at Open and may be worse than -1R
practical: Low<=stop exits at fixed stop exactly -1R when no gap
```

No target, time exit, breakeven move, or trailing stop may appear.

- [ ] **Step 3: Preserve V3 entry metadata for diagnostics**

Completed trade rows must retain at least:

```text
Entry_ID,Symbol,Entry_Date,Entry_Open,Leader_Date,Leader_Close,
Signal_Date,ATR14_Signal,Pullback_Age,Pullback_Depth_ATR,
Composite_RS,Resumption_Volume_Ratio
```

alongside exit/outcome fields. This allows diagnostics to be generated from actual completed Entry_IDs without outcome-dependent re-selection.

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py" -k "setup or practical or profit_factor"
```

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: add Strategy V3 exit lenses"
```

---

### Task 5: Add strict-prior breadth, artifact-derived PIT audit, and accounting invariants

**Files:**
- Modify: `analyze_v3_results.py`
- Modify: `tests/test_v3_analysis.py`
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
    canonical_sessions: pd.DatetimeIndex,
) -> tuple[int, pd.DataFrame]
```

PIT violation codes:

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

- [ ] **Step 1: Copy strict-prior breadth semantics**

Use `pd.merge_asof(... direction="backward", allow_exact_matches=False)` and assert `Breadth_Matched_Date < Entry_Date`. Regression: entry Jan 10 with breadth Jan 9 and Jan 10 must attach Jan 9.

- [ ] **Step 2: Add zero-violation and mutation tests**

Valid fixture:

```text
Leader_Date 2024-01-05
Signal_Date 2024-01-10
Entry_Date 2024-01-11
seed/signal PIT active
seed/signal RS safe and Composite_RS=80
breadth strictly before entry
setup/practical Entry_ID sets equal
```

Assert zero violations. Then mutate separately and assert exact codes for: leader==signal, signal==entry, signal outside window, seed >10 canonical sessions before Aug1, inactive seed/signal membership, unsafe seed/signal RS, seed/signal RS=69.9, delayed entry, breadth==entry, and lens Entry_ID mismatch.

- [ ] **Step 3: PIT audit must use actual artifacts and manifest**

Membership checks resolve `Leader_Date` and `Signal_Date` against the committed interval manifest. Pre-window boundary uses the canonical index-session spine. No function or gate may silently default PIT violations to zero.

- [ ] **Step 4: Abort before profitability interpretation on PIT failure**

```python
pit_count, pit_audit = count_point_in_time_violations(...)
if pit_count:
    pit_audit.to_csv(output_dir / "v3_point_in_time_violations.csv", index=False)
    raise AssertionError(f"point-in-time integrity violations: {pit_count}")
```

Do not create an empty violations file when count is zero.

- [ ] **Step 5: Add exact accounting assertions**

```python
qualified_ids = set(signals.loc[signals["Signal_Qualified"], "Entry_ID"])
accepted_ids = set(entries["Entry_ID"])
cancelled_ids = set(cancellations["Entry_ID"])
assert qualified_ids == accepted_ids | cancelled_ids
assert accepted_ids.isdisjoint(cancelled_ids)
assert set(setup["Entry_ID"]) == set(practical["Entry_ID"])
assert set(setup["Entry_ID"]).issubset(accepted_ids)
```

Incomplete accepted entries remain visible in accepted-entry and overlap artifacts.

- [ ] **Step 6: Run tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py" -k "breadth or point_in_time or integrity or mismatch"
```

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: add Strategy V3 PIT integrity audit"
```

---

### Task 6: Add robustness gates, overlap, and predeclared diagnostics

**Files:**
- Modify: `analyze_v3_results.py`
- Modify: `tests/test_v3_analysis.py`

**Interfaces:**

```python
year_summary(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
outlier_robustness(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
leave_one_symbol_out(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
overlap_diagnostic(entries: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame
pullback_diagnostics(
    entries: pd.DataFrame,
    setup: pd.DataFrame,
    practical: pd.DataFrame,
) -> pd.DataFrame
evaluate_gates(
    setup: pd.DataFrame,
    practical: pd.DataFrame,
    *,
    point_in_time_violations: int,
) -> pd.DataFrame
```

- [ ] **Step 1: Reuse V2 generic robustness semantics unchanged**

Copy paired-lens handling, year summary, top-1/3/5 winner removal, LOSO, and all-accepted-entry overlap logic where semantics match.

Overlap starts from **all accepted entries**, left-joins completed practical `Exit_Date`, extends only diagnostic interval math for incomplete positions through observation end, and reports:

```text
Total_Accepted_Entries
Entries_With_Another_Open_Same_Symbol_Trade
Max_Simultaneous_Signal_Level_Trades
Max_Same_Day_Entries
```

Regression: 3 accepted but only 2 completed -> `Total_Accepted_Entries == 3`.

- [ ] **Step 2: Add exact temporal-gate regression**

Two years, 20 paired trades each, setup mean positive and setup PF>=1.0, practical R negative. Assert both years qualify. Year qualification is only:

```python
Setup_Completed_Trades >= 20
Setup_Mean_Return > 0
Setup_Return_PF >= 1.0
```

Never add practical R to year qualification.

- [ ] **Step 3: Add formal sample-status regression**

99 completed paired trades -> `FINAL_STATUS=INSUFFICIENT_EVIDENCE` even if all profitability gates pass. At >=100, final `PASS` only if every locked gate passes; otherwise `FAIL`.

- [ ] **Step 4: Implement exact gate rows**

```text
COMPLETED_TRADES              >=100
SETUP_MEAN_RETURN             >0
SETUP_RETURN_PF               >=1.20
PRACTICAL_MEAN_R              >=0.15
PRACTICAL_R_PF                >=1.20
TEMPORAL_ROBUSTNESS           >=2 qualifying years
TOP_FIVE_OUTLIER_ROBUSTNESS   setup mean>0 and setup PF>=1.0 after top5 removal
LEAVE_ONE_SYMBOL_OUT          every omission setup mean>0 and setup PF>=1.0
POINT_IN_TIME_INTEGRITY       ==0
FINAL_STATUS
```

`point_in_time_violations` is keyword-only and has **no default**.

- [ ] **Step 5: Implement fixed diagnostic buckets before historical outcomes are loaded**

`pullback_diagnostics()` inner-joins completed Entry_IDs to accepted-entry metadata and outputs:

```text
Dimension,Bucket,Completed_Trades,Setup_Mean_Return,Setup_Return_PF,
Practical_Mean_R,Practical_R_PF
```

Fixed buckets:

```text
Pullback_Age: 3-4 | 5-6 | 7-8 | 9-10
Pullback_Depth_ATR: [0.5,1.0) | [1.0,1.5) | [1.5,2.0) | [2.0,2.5]
Composite_RS: [70,80) | [80,90) | [90,100]
Resumption_Volume_Ratio: <0.8 | [0.8,1.2) | >=1.2 | MISSING
Entry_Extension_ATR_vs_Leader = (Entry_Open-Leader_Close)/ATR14_Signal:
  <=0 | (0,0.25] | (0.25,0.5]
```

Breadth regime remains separate in `v3_breadth_summary.csv`. No diagnostic bucket receives a validation gate.

- [ ] **Step 6: Run tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py"
```

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: add Strategy V3 robustness gates"
```

---

### Task 7: Wire the historical pipeline, evidence-only report, and end-to-end invariants

**Files:**
- Modify: all three V3 Python modules
- Create: `README.md`
- Create: `tests/test_v3_end_to_end.py`
- Generate all required outputs

- [ ] **Step 1: Build canonical sessions from the long Nifty 500 index history**

Use `Swing Trading/nifty500_regime_daily.csv` dates for pre-window boundary and immediate-next-session mapping. If downloaded market data contains `2026-08-26` and the index history does not, append only that date. Breadth data is used only for strict-prior breadth context, never as the canonical pre-window session spine.

- [ ] **Step 2: Wire feature and signal generation**

`build_v3_features.py`: load manifest -> adjusted feature frames -> PIT RS -> V3 data/RS audits.

`generate_v3_signals.py`: rebuild/obtain ranked frames -> scan eligible dates -> retain only primary-window candidate signals -> one next-session decision per qualified signal -> early integrity assertions -> write state/candidate/entry/cancellation artifacts.

Print:

```text
symbols=<N> candidates=<N> qualified=<N> entries=<N> cancellations=<N>
```

- [ ] **Step 3: Wire completed outcome analysis**

Rebuild adjusted prices for represented symbols, simulate both lenses, retain paired completed Entry_IDs, count incomplete accepted entries separately, attach strict-prior breadth, validate lens equality, run PIT audit, then generate robustness/diagnostics/gates.

- [ ] **Step 4: Generate all required artifacts mechanically**

Create every file required by the spec, including `v3_pullback_diagnostics.csv`, `v3_overlap_diagnostic.csv`, `v3_validation_gates.csv`, and conditional PIT violation output.

- [ ] **Step 5: Make `research_report.md` evidence-only**

Required sections:

1. locked hypothesis/spec;
2. data/timing conventions and whether PIT membership actually supports any pre-window seed dates;
3. data audit counts;
4. RS coverage;
5. state-event counts;
6. candidate rejection and entry-cancellation counts;
7. accepted/completed/incomplete reconciliation;
8. setup metrics;
9. practical metrics;
10. year summary;
11. top-1/3/5 robustness;
12. LOSO;
13. breadth diagnostics;
14. pullback diagnostics;
15. overlap;
16. PIT integrity;
17. locked gates;
18. final status.

End with: the report does not tune V3 or prescribe a follow-up threshold/filter; Portfolio Advisor retains interpretation.

- [ ] **Step 6: Add a no-network synthetic end-to-end test**

Synthetic two-symbol universe must prove:

```text
one valid seed/pullback/resumption -> qualified signal -> accepted next-open entry
one qualified signal -> entry cancellation
qualified == accepted + cancelled
setup/practical completed Entry_ID sets match
PIT count == 0
overlap accepted count == all accepted entries
gates require explicit PIT count
```

Monkeypatch downloader or pass synthetic frames; no network calls.

- [ ] **Step 7: Run V3 tests and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests"
```

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: wire Strategy V3 validation pipeline"
```

---

### Task 8: Run the locked historical experiment and reconcile every artifact

- [ ] **Step 1: Confirm clean tree**

```bash
git status --short
```

No unrelated modifications may be swept into the research commit.

- [ ] **Step 2: Generate features/RS audits**

```bash
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/build_v3_features.py"
```

- [ ] **Step 3: Generate state/signals/entries**

```bash
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/generate_v3_signals.py"
```

Record counts only; do not alter thresholds.

- [ ] **Step 4: Run outcome analysis**

```bash
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py"
```

Any PIT failure stops interpretation.

- [ ] **Step 5: Run mechanical reconciliation**

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

- [ ] **Step 6: Audit diff for prohibited changes/artifacts**

```bash
git status --short
find "Swing Trading/research/swing/strategy_v3_shallow_pullback" -type f -size +5M -print
```

Verify: no raw Yahoo/all-symbol cache, no V2/T1 file changes, no threshold changes, diagnostics never became filters, report contains no post-result tuning recommendation.

- [ ] **Step 7: Commit evidence**

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback"
git commit -m "research: record Strategy V3 historical validation"
```

---

### Task 9: Fresh regression verification and implementation PR

- [ ] **Step 1: Run fresh V3 tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests"
```

Expected: zero failures.

- [ ] **Step 2: Run full swing-research suite from canonical package root**

```bash
cd "Swing Trading"
python -m pytest -q research/swing
cd ..
```

Expected: zero failures.

If failures remain, run the **same command** on the implementation branch base commit in a temporary worktree. Base pass / V3 fail = V3 regression. Same failure on both = surface blocker. Never weaken legacy tests.

- [ ] **Step 3: Verify implementation diff scope**

```bash
git diff --name-only master...HEAD
```

Expected implementation paths: `Swing Trading/research/swing/strategy_v3_shallow_pullback/**` only, apart from already-approved spec/plan ancestry. Any T1/V2 change requires Portfolio Advisor review.

- [ ] **Step 4: Create PR from actual outputs, never remembered counts**

Title:

```text
research: validate Strategy V3 shallow-pullback resumption
```

Body template populated immediately from pytest output and CSVs:

```text
Implements #16.

## Scope
- Implements the locked Strategy V3 PIT Nifty 500 RS-leader → shallow-pullback → first-resumption state machine.
- Preserves one-shot next-session entry, structural stop, two locked exit lenses, PIT audit, diagnostics and precommitted gates.
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

Do not type values from memory; parse actual artifacts/test output before creating or editing the PR.

- [ ] **Step 5: Comment on Issue #16 only after PR exists**

Include PR link, exact counts, PIT count, fresh test counts, and formal status. Engineering comment remains evidence-only.

- [ ] **Step 6: End clean**

```bash
git status --short
```

Expected: clean.

---

## Final Research-Integrity Checklist

- [ ] 20-session closing-high seed with equality allowed.
- [ ] Seed PIT membership/RS safety/liquidity/trend/RS gates exact.
- [ ] Pre-window seeds use long canonical index-session spine and only genuine manifest-supported PIT dates; no backfill.
- [ ] RS ranking covers genuine pre-window membership dates when they exist.
- [ ] Age/depth/state ordering exact.
- [ ] Same-bar reseed path centralized; every logically compatible closure has regression coverage.
- [ ] Trigger exactly `Close > previous High AND Close > SMA20`.
- [ ] First trigger only; ages 1–2 too short; ages 3–10 candidate; <0.5 depth ends setup.
- [ ] `Close > Leader_Close` never candidate from old state.
- [ ] One immediate-next-session entry only.
- [ ] Entry bounds and structural stop use signal-known data only.
- [ ] Setup/practical exits preserve locked precedence.
- [ ] Breadth strict-prior and diagnostic-only; volume/subgroups diagnostic-only.
- [ ] Qualified == accepted + cancelled; accepted/cancelled disjoint.
- [ ] Completed setup/practical Entry_ID sets equal.
- [ ] Incomplete accepted entries retained in overlap accounting.
- [ ] PIT count derived from artifacts with no default-zero path; nonzero aborts interpretation.
- [ ] Temporal gate excludes Practical_Mean_R.
- [ ] Below 100 completed paired trades -> `INSUFFICIENT_EVIDENCE`.
- [ ] No result-driven threshold/filter changes.
- [ ] No T1/V2 evidence changes.
- [ ] V3 tests and full `research/swing` suite pass freshly.
- [ ] No raw Yahoo/all-symbol feature cache committed.
- [ ] Final report evidence-only; Portfolio Advisor retains interpretation.

## Execution Handoff

Execute with:

```text
superpowers:executing-plans
```

**Inline execution only. Never use `superpowers:subagent-driven-development`.**

At each task boundary, run the named tests and commit before proceeding. Do not ask the user to choose technical parameters or review research execution details; surface only genuine requirement blockers, environment blockers, or conflicts with the frozen V3 spec.