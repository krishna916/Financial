# PR #36 E1 Primary-Candidate Stage B Performance Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.**

**Goal:** Make Stage B finish by running expensive 13-quarter reporting-basis/SUE preparation only for genuine primary-window event candidates, while keeping historical EPS available as lookup history and preserving all frozen E1 semantics.

**Architecture:** Keep the existing frozen filings/EPS/actions and price snapshots. In `build_event_master()`, do cheap event-date/PIT/timeliness filtering before `select_reporting_basis()` so 2020-history and forward-only filing rows are never sent through repeated 13-quarter basis checks. Build the next-quarter early-exit calendar separately from raw original filings, because those later result dates are lifecycle triggers only and do not need SUE/basis validation. Then remove the already-identified duplicate analysis recomputation and run the unchanged formal validator to `FINAL_STATUS`.

**Tech Stack:** Python 3, pandas, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-29-e1-positive-earnings-surprise-drift-design.md`

## Global Constraints

- Performance-only change. Do not change E1 dates, SUE formula/history, basis priority, cohort thresholds, 40-session hold, friction, benchmark, controls, robustness gates, or status precedence.
- Keep the full historical EPS snapshot. History rows are lookup inputs; they are not formal event candidates.
- Primary event window remains `2023-08-01..2026-06-30` inclusive.
- Later original quarterly result dates through the frozen source cutoff remain available only for `EXIT_NEXT_EARNINGS_EVENT` detection.
- Do not refetch Stage A inputs or prices.
- Do not add caches/databases/parallel frameworks/profiling infrastructure.
- Stop once the unchanged validator produces the fresh authoritative `FINAL_STATUS`.

---

### Task 1: Filter to cheap primary candidates before 13-quarter basis checks

**Files:**
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_events.py`
- Test: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_events.py`

**Add helper:**

```python
def partition_primary_candidates(
    first_public: pd.DataFrame,
    membership: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return rows needing expensive basis checks and cheap primary exclusions."""
```

Required behavior:

```text
first_public original/deduplicated filings
-> discard history-only / forward-only rows from formal event processing
-> for rows whose public date is inside PRIMARY_START..PRIMARY_END:
     compute PIT membership and timeliness cheaply
-> PIT+timely rows => basis_candidates
-> PIT/timeliness failures => explicit exclusions without any 13-quarter basis check
```

The helper must not inspect EPS values, returns, prices, or SUE.

Change `build_event_master()` order from:

```text
select_first_public_filings(all rows)
-> select_reporting_basis(all first-public rows)
-> determine primary eligibility
```

to:

```text
select_first_public_filings(all rows)
-> partition_primary_candidates(...)
-> select_reporting_basis(basis_candidates only, full EPS history, actions)
-> build formal event master + explicit cheap exclusions
```

The **full `eps` DataFrame still goes into `select_reporting_basis()`** so each candidate can inspect its historical `t-12..t` chain.

- [ ] **Write regression proving historical rows never invoke basis-chain checks**

Monkeypatch `compute_e1_sue.basis_chain_status` with a recording function. Build a fixture containing:

```text
AAA historical event: public 2022-08-10
AAA primary event:    public 2024-08-10
AAA forward event:    public 2026-07-10
```

Assert the recorder sees only the 2024 primary event.

- [ ] **Write regression proving late/PIT-inactive primary-window rows remain explicit exclusions**

Use two primary-window rows:

```text
LATE -> Timely_Result false
OFFINDEX -> PIT membership false
```

Assert neither invokes `basis_chain_status`, and exclusions contain exactly:

```text
LATE_RESULT
PIT_MEMBERSHIP_NOT_ACTIVE
```

- [ ] **Write equivalence regression for a valid primary event**

Use the existing complete consolidated/standalone fixture and assert the selected basis and resulting formal event fields remain identical to the frozen behavior.

- [ ] **Implement minimal filtering and run tests**

```bash
cd "Swing Trading"
python -m pytest -q \
  research/swing/e1_positive_earnings_surprise_drift/tests/test_events.py \
  research/swing/e1_positive_earnings_surprise_drift/tests/test_sue.py
```

- [ ] **Commit**

```bash
git add research/swing/e1_positive_earnings_surprise_drift/build_e1_events.py \
        research/swing/e1_positive_earnings_surprise_drift/tests/test_events.py
git commit -m "perf: limit E1 basis checks to primary candidates"
```

---

### Task 2: Separate the cheap quarterly-result exit calendar from the formal event master

**Files:**
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_events.py`
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/run_e1_validation.py`
- Test: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_events.py`
- Test: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_trades.py`

**Add helper:**

```python
def build_quarterly_exit_event_calendar(
    filings: pd.DataFrame,
    symbols: set[str],
) -> pd.DataFrame:
    """Earliest original publication for each distinct symbol/fiscal quarter."""
```

Exact output columns:

```python
[
    "Symbol",
    "Fiscal_Period_End",
    "Event_Public_Timestamp",
    "Original_or_Revised",
]
```

Exact rules:

```text
- only requested symbols
- ORIGINAL rows only
- quarterly result rows only when Quarterly_or_Annual is available
- public timestamp <= SOURCE_CUTOFF
- for duplicate NSE/BSE/basis rows of the same Symbol + Fiscal_Period_End,
  keep the earliest public timestamp
- no reporting-basis selection
- no EPS/SUE calculation
```

After Stage B computes `classified`, derive:

```python
trade_symbols = set(
    classified.loc[
        classified["Cohort"].isin(PRIMARY_PRICE_COHORTS), "Symbol"
    ].astype(str)
)
exit_calendar = build_quarterly_exit_event_calendar(
    loaded["e1_exchange_filings_snapshot.csv"], trade_symbols
)
```

Pass `exit_calendar`, not `event_master`, as `all_original_events` to `build_primary_trades()`.

- [ ] **Write regression: a later late/unscored quarter still causes early exit**

The next quarter must trigger `EXIT_NEXT_EARNINGS_EVENT` even though it is not a formal E1 event and never underwent basis/SUE checks.

- [ ] **Write regression: duplicate exchange/basis filings collapse to one quarterly lifecycle event**

Assert one `Symbol + Fiscal_Period_End` row with the earliest original timestamp.

- [ ] **Implement and run focused tests**

```bash
cd "Swing Trading"
python -m pytest -q \
  research/swing/e1_positive_earnings_surprise_drift/tests/test_events.py \
  research/swing/e1_positive_earnings_surprise_drift/tests/test_trades.py \
  research/swing/e1_positive_earnings_surprise_drift/tests/test_end_to_end.py
```

- [ ] **Commit**

```bash
git add research/swing/e1_positive_earnings_surprise_drift/build_e1_events.py \
        research/swing/e1_positive_earnings_surprise_drift/run_e1_validation.py \
        research/swing/e1_positive_earnings_surprise_drift/tests
git commit -m "perf: separate E1 lifecycle event calendar"
```

---

### Task 3: Remove duplicate analysis work and run the formal experiment to completion

**Files:**
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/run_e1_validation.py`
- Test: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_end_to_end.py`

Replace eager-default calls such as:

```python
analysis.get("e1_leave_one_symbol_out.csv", leave_one_symbol_out(positive))
```

with direct access to the outputs already produced by `write_analysis_outputs()`:

```python
temporal = analysis["e1_temporal_summary.csv"]
year_loo = analysis["e1_leave_one_year_out.csv"]
top_five = analysis["e1_top_five_robustness.csv"]
loso = analysis["e1_leave_one_symbol_out.csv"]
```

Do the same for every analysis artifact already guaranteed by `write_analysis_outputs()`; do not recompute it as a default argument.

- [ ] **Add regression proving robustness functions are called once**

Monkeypatch the relevant analysis functions/call boundary with counters and assert one formal validation run does not perform a second leave-one-symbol/year/top-five computation after `write_analysis_outputs()` returns.

- [ ] **Run fresh test suites**

```bash
cd "Swing Trading"
python -m pytest -q research/swing/e1_positive_earnings_surprise_drift/tests
python -m pytest -q research/swing
```

- [ ] **Run Stage B against the already-frozen completed Stage A input package**

```bash
python research/swing/e1_positive_earnings_surprise_drift/run_e1_validation.py
```

Do not rerun Stage A unless manifest verification says the frozen input package itself is invalid.

- [ ] **Read only the formal authority**

```text
research/swing/e1_positive_earnings_surprise_drift/output/e1_validation_gates.csv
-> FINAL_STATUS
```

Also report:

```text
Technical EPS coverage
completed Positive / Neutral / Negative counts
FIRST / SECOND positive counts
base positive mean / median / PF / excess
stress positive mean / PF / excess
FINAL_STATUS
```

- [ ] **Do not tune or add another optimization after seeing results**

If the validator completes, stop. The next decision is based on `FINAL_STATUS`, not on further engineering.

- [ ] **Commit fresh evidence and update PR #36**

```bash
git add research/swing/e1_positive_earnings_surprise_drift
git commit -m "research: complete E1 frozen validation"
```

---

## Completion Gate

```text
[ ] 13-quarter basis checks run only for primary-window PIT+timely candidate events.
[ ] Historical EPS remains available for candidate t-12..t lookup.
[ ] Later quarterly result dates remain available for early-exit detection without SUE processing.
[ ] No E1 methodology/gate changed.
[ ] No Stage A refetch performed unless frozen manifest is invalid.
[ ] Duplicate analysis recomputation removed.
[ ] Fresh tests pass.
[ ] Stage B completes.
[ ] e1_validation_gates.csv contains a fresh FINAL_STATUS.
[ ] Stop.
```