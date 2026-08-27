# Strategy V2 PR #15 Review Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use `subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the five PR #15 review findings without changing any Strategy V2 trading rule, threshold, ranking weight, validation threshold, or result interpretation, then regenerate the historical evidence from the corrected implementation.

**Architecture:** Keep the existing `strategy_v2_quality_base` module and make narrowly scoped corrections in the state machine, gate evaluation, point-in-time audit, overlap diagnostics, and regression verification. Add regression tests before each behavioral fix. Because the reseeding correction can change the candidate universe, rerun the entire historical pipeline and replace all generated V2 outputs mechanically; do not preserve old counts or metrics.

**Tech Stack:** Python 3, pandas, numpy, yfinance, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-26-strategy-v2-quality-base-breakout-design.md`

**Original implementation plan:** `docs/superpowers/plans/2026-08-26-strategy-v2-quality-base-validation.md`

**Issue:** `https://github.com/krishna916/Financial/issues/13`

**PR:** `https://github.com/krishna916/Financial/pull/15`

## Global Constraints

- This work fixes implementation/research-integrity defects only. Do not change Strategy V2 parameters because the existing results are weak.
- Keep `Composite_RS >= 70`, RS weights `30/40/30`, base duration `10..30`, base depth `<=4 ATR`, contraction `<=0.80`, signal/entry extension `<=1 ATR`, stop buffer `0.25 ATR`, max stop distance `2.5 ATR`, and all other locked rules unchanged.
- T1 remains retired. Do not reintroduce T1 filters or add breadth/sector/volume gates.
- Do not add post-result exclusions, special-case symbols, special-case years, or altered thresholds.
- Any change in signal/trade counts after the state-machine correction is expected evidence, not a regression to be forced back to the old counts.
- Regenerated outputs must come from the corrected code. Never edit generated CSV/report numbers manually.
- The final gate logic must match Issue #13 and the original implementation plan exactly.
- Run all implementation steps inline with `superpowers:executing-plans` only.

---

## File Map

Modify:

```text
Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py
Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py
Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py
Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py
Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_end_to_end.py
Swing Trading/research/swing/strategy_v2_quality_base/README.md        # only if verification instructions/count wording needs correction
```

Regenerate every committed file under:

```text
Swing Trading/research/swing/strategy_v2_quality_base/output/
```

Do not modify legacy T1 research code or fixtures merely to make the regression suite pass.

---

### Task 1: Restore mandatory same-bar reseeding after every base closure

**Finding addressed:** Blocking review finding #1.

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py`

**Requirement:** The locked state ordering says that after **any** base close/cancel/invalidation, the same bar is independently tested as a possible fresh 63-session-high seed. The current implementation disables reseeding for `DEPTH_INVALIDATED`; remove that exception.

- [ ] **Step 1: Add a regression test for depth invalidation + same-bar reseed**

Add this test next to the existing failed-probe depth test:

```python
def test_depth_invalidation_can_reseed_on_same_bar_when_it_is_a_new_63_session_high():
    frame = make_valid_base_frame()

    # Base seeded at row 62 with pivot 100 and seed ATR 2.
    # On base session 5, a failed probe at 104 raises the pivot enough that
    # depth becomes (104 - 95) / 2 = 4.5 ATR, so the old base invalidates.
    # High 104 is also the new 63-session high, so the same bar must seed a new base.
    frame.loc[67, ["High", "Low", "Close"]] = [104.0, 95.0, 99.0]

    audit, candidates = scan_symbol_bases("AAA", frame)

    events = audit.loc[audit["Date"] == frame.loc[67, "Date"], "Event"].tolist()
    assert events == ["FAILED_PROBE", "DEPTH_INVALIDATED", "SEEDED"]
    reseed = audit.loc[
        (audit["Date"] == frame.loc[67, "Date"]) & (audit["Event"] == "SEEDED")
    ].iloc[0]
    assert reseed["Base_Age"] == 0
    assert reseed["Original_Pivot"] == 104.0
    assert reseed["Active_Pivot"] == 104.0
    assert candidates.empty
```

Keep the existing `test_failed_probe_rechecks_depth_using_raised_pivot()` but update its expected same-day event list to include `SEEDED` when the invalidating bar is also a valid 63-session-high seed.

- [ ] **Step 2: Run the focused test and verify it fails before the fix**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py" -k "depth_invalidation or failed_probe"
```

Expected before fix: the new test fails because `SEEDED` is missing after `DEPTH_INVALIDATED`.

- [ ] **Step 3: Remove the reseeding exception from the state machine**

In `scan_symbol_bases()` eliminate `reseed_on_close=False` behavior. The close path must reduce to this invariant:

```python
if closed:
    active = None
    if _is_seed(data, index):
        active = _new_base(symbol, data, index)
        _record_event(events, symbol, row, active, "SEEDED")
```

Do not special-case `DEPTH_INVALIDATED`. This same close/reseed behavior must apply after:

```text
DEPTH_INVALIDATED
TOO_SHORT_BREAKOUT
BREAKOUT_CANDIDATE
EXPIRED
```

A breakout candidate still freezes the old base and may independently seed a new future base from the same bar if the bar is a 63-session high. The new seed does not create a second same-day entry; its base session 1 starts on the next bar.

- [ ] **Step 4: Run all signal tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py"
```

Expected: PASS.

- [ ] **Step 5: Commit the state-machine fix**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py" \
        "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py"
git commit -m "fix: restore Strategy V2 same-bar reseeding"
```

---

### Task 2: Make temporal robustness exactly match the precommitted gate

**Finding addressed:** Important review finding #2.

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py`

**Requirement:** A qualifying calendar year is defined only by the setup-quality lens:

```text
Setup_Completed_Trades >= 20
Setup_Mean_Return > 0
Setup_Return_PF >= 1.0
```

The current additional condition `Practical_Mean_R > 0` was not precommitted and must be removed. The practical lens still has its separate global `PRACTICAL_MEAN_R >= 0.15` and `PRACTICAL_R_PF >= 1.20` gates.

- [ ] **Step 1: Add a regression test proving negative practical R does not alter temporal qualification**

Add a deterministic 40-trade two-year fixture:

```python
def test_temporal_gate_uses_only_locked_setup_quality_year_conditions():
    rows = []
    for year in (2023, 2024):
        for index in range(20):
            rows.append(
                {
                    "Entry_ID": f"{year}-{index}",
                    "Symbol": "AAA" if index % 2 == 0 else "BBB",
                    "Entry_Date": pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(days=index * 7),
                    "Return": 0.02 if index < 15 else -0.01,
                    "Holding_Sessions": 5,
                }
            )
    setup = pd.DataFrame(rows)
    practical = setup.assign(Initial_Risk=1.0, R_Multiple=-0.25)

    gates = evaluate_gates(setup, practical)
    temporal = gates.loc[gates["Gate"] == "TEMPORAL_ROBUSTNESS"].iloc[0]

    assert bool(temporal["Passed"])
    assert temporal["Value"] == 2
```

This test intentionally allows the overall final status to remain `INSUFFICIENT_EVIDENCE` at 40 trades; it validates the temporal row only.

- [ ] **Step 2: Run the focused test and verify failure**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py" -k "temporal_gate"
```

Expected before fix: FAIL because the current code requires positive `Practical_Mean_R` per year.

- [ ] **Step 3: Remove the unapproved practical-year condition**

Change:

```python
qualifying_years = years.loc[
    (years["Setup_Completed_Trades"] >= 20)
    & (years["Setup_Mean_Return"] > 0)
    & (years["Setup_Return_PF"] >= 1.0)
    & (years["Practical_Mean_R"] > 0)
]
```

to exactly:

```python
qualifying_years = years.loc[
    (years["Setup_Completed_Trades"] >= 20)
    & (years["Setup_Mean_Return"] > 0)
    & (years["Setup_Return_PF"] >= 1.0)
]
```

Do not alter any other gate.

- [ ] **Step 4: Run analysis tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py" \
        "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py"
git commit -m "fix: align Strategy V2 temporal gate"
```

---

### Task 3: Derive point-in-time violation count from artifacts instead of defaulting to zero

**Finding addressed:** Important review finding #3.

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_end_to_end.py`

**Requirement:** `POINT_IN_TIME_INTEGRITY` must be computed from the final signal/entry/trade artifacts. It must never PASS merely because a function default argument is zero.

- [ ] **Step 1: Add a pure audit function with exact violation categories**

Add this public interface:

```python
def count_point_in_time_violations(
    signals: pd.DataFrame,
    entries: pd.DataFrame,
    setup: pd.DataFrame,
    practical: pd.DataFrame,
) -> tuple[int, pd.DataFrame]:
    ...
```

Return total violation count plus one compact row per violation with columns:

```text
Entry_ID,Symbol,Violation
```

Count these violations only for qualified/accepted research records:

```text
SIGNAL_NOT_BEFORE_ENTRY
SIGNAL_BEFORE_WINDOW
INACTIVE_MEMBER_SIGNAL
UNSAFE_RS_COVERAGE_SIGNAL
RS_BELOW_THRESHOLD_SIGNAL
BREADTH_NOT_STRICT_PRIOR_SETUP
BREADTH_NOT_STRICT_PRIOR_PRACTICAL
LENS_ENTRY_ID_MISMATCH
```

Definitions:

```python
Signal_Date >= Entry_Date                                  -> SIGNAL_NOT_BEFORE_ENTRY
Signal_Date < pd.Timestamp("2023-08-01")                  -> SIGNAL_BEFORE_WINDOW
Membership_OK is not True                                  -> INACTIVE_MEMBER_SIGNAL
RS_Coverage_OK is not True or RS_Coverage < 0.80          -> UNSAFE_RS_COVERAGE_SIGNAL
Composite_RS < 70                                          -> RS_BELOW_THRESHOLD_SIGNAL
Breadth_Matched_Date >= Entry_Date in setup                -> BREADTH_NOT_STRICT_PRIOR_SETUP
Breadth_Matched_Date >= Entry_Date in practical            -> BREADTH_NOT_STRICT_PRIOR_PRACTICAL
set(setup.Entry_ID) != set(practical.Entry_ID)             -> LENS_ENTRY_ID_MISMATCH
```

Only accepted `Entry_ID`s should be evaluated for signal/entry timing conditions. Join `entries` back to `signals` by `Entry_ID`; a missing qualified signal backing an accepted entry is also `LENS_ENTRY_ID_MISMATCH`-class research corruption and should raise from the existing integrity validator before gate calculation.

- [ ] **Step 2: Add explicit tests**

Add:

```python
def test_point_in_time_audit_reports_zero_for_valid_artifacts():
    signals = pd.DataFrame([{
        "Entry_ID": "AAA-1",
        "Symbol": "AAA",
        "Signal_Date": pd.Timestamp("2024-01-10"),
        "Signal_Qualified": True,
        "Membership_OK": True,
        "RS_Coverage_OK": True,
        "RS_Coverage": 0.95,
        "Composite_RS": 80.0,
    }])
    entries = pd.DataFrame([{
        "Entry_ID": "AAA-1",
        "Symbol": "AAA",
        "Signal_Date": pd.Timestamp("2024-01-10"),
        "Entry_Date": pd.Timestamp("2024-01-11"),
    }])
    setup = pd.DataFrame([{
        "Entry_ID": "AAA-1",
        "Symbol": "AAA",
        "Entry_Date": pd.Timestamp("2024-01-11"),
        "Breadth_Matched_Date": pd.Timestamp("2024-01-10"),
    }])
    practical = setup.copy()

    count, audit = count_point_in_time_violations(signals, entries, setup, practical)
    assert count == 0
    assert audit.empty
```

And one mutation test:

```python
def test_point_in_time_audit_detects_same_day_signal_entry_and_equal_day_breadth():
    # Start from the valid fixture above, then mutate Entry_Date to Signal_Date
    # and Breadth_Matched_Date to Entry_Date.
    count, audit = count_point_in_time_violations(signals, entries, setup, practical)
    assert count > 0
    assert "SIGNAL_NOT_BEFORE_ENTRY" in set(audit["Violation"])
    assert "BREADTH_NOT_STRICT_PRIOR_SETUP" in set(audit["Violation"])
```

- [ ] **Step 3: Remove the implicit zero default from final analysis flow**

It is acceptable for `evaluate_gates(..., point_in_time_violations: int)` to remain a pure gate function, but the parameter must become required:

```python
def evaluate_gates(
    setup: pd.DataFrame,
    practical: pd.DataFrame,
    *,
    point_in_time_violations: int,
) -> pd.DataFrame:
```

Update every test call to pass an explicit number.

In `__main__`, after breadth attachment and integrity validation:

```python
point_in_time_violations, pit_audit = count_point_in_time_violations(
    candidates,
    entries,
    setup,
    practical,
)
gates = evaluate_gates(
    setup,
    practical,
    point_in_time_violations=point_in_time_violations,
)
```

Do not add a new committed PIT CSV unless needed for a non-zero failure. For normal zero-violation runs, reporting the derived count in `v2_validation_gates.csv` is sufficient. If `point_in_time_violations > 0`, write `v2_point_in_time_violations.csv` and fail the research-integrity execution before interpreting profitability.

- [ ] **Step 4: Strengthen the end-to-end test**

In the existing pure-flow test, call `count_point_in_time_violations(...)` after breadth attachment and assert:

```python
assert point_in_time_violations == 0
```

- [ ] **Step 5: Run V2 tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py" \
        "Swing Trading/research/swing/strategy_v2_quality_base/tests"
git commit -m "fix: derive Strategy V2 point-in-time gate"
```

---

### Task 4: Make overlap diagnostics use all accepted entries, including incomplete outcomes

**Finding addressed:** Moderate review finding #5.

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py`

**Requirement:** `Total_Accepted_Entries` must equal the number of rows in `v2_entries.csv`, not only completed practical outcomes. Incomplete accepted trades must remain represented in overlap diagnostics.

- [ ] **Step 1: Replace the overlap interface**

Change:

```python
overlap_diagnostic(practical: pd.DataFrame) -> pd.DataFrame
```

to:

```python
overlap_diagnostic(
    entries: pd.DataFrame,
    practical: pd.DataFrame,
) -> pd.DataFrame
```

Implementation rules:

1. Start from every accepted entry in `entries`.
2. Left-join only `Entry_ID, Exit_Date` from completed practical trades.
3. Define an observation-end date as:

```python
observation_end = max(
    entries["Entry_Date"].max(),
    practical["Exit_Date"].max() if not practical.empty else entries["Entry_Date"].max(),
)
```

4. For accepted entries without a completed practical outcome, set `Effective_Exit_Date = observation_end` for diagnostic overlap counting only. Do not manufacture a return or completed trade.
5. Compute all four existing output columns from the full accepted-entry table:

```text
Total_Accepted_Entries
Entries_With_Another_Open_Same_Symbol_Trade
Max_Simultaneous_Signal_Level_Trades
Max_Same_Day_Entries
```

- [ ] **Step 2: Add a regression test with an incomplete accepted entry**

```python
def test_overlap_diagnostic_counts_incomplete_accepted_entries():
    entries = pd.DataFrame(
        {
            "Entry_ID": ["A", "B", "C"],
            "Symbol": ["AAA", "BBB", "CCC"],
            "Entry_Date": pd.to_datetime(["2026-08-20", "2026-08-21", "2026-08-26"]),
        }
    )
    practical = pd.DataFrame(
        {
            "Entry_ID": ["A", "B"],
            "Symbol": ["AAA", "BBB"],
            "Entry_Date": pd.to_datetime(["2026-08-20", "2026-08-21"]),
            "Exit_Date": pd.to_datetime(["2026-08-25", "2026-08-25"]),
        }
    )

    result = overlap_diagnostic(entries, practical).iloc[0]
    assert result["Total_Accepted_Entries"] == 3
    assert result["Max_Same_Day_Entries"] == 1
```

- [ ] **Step 3: Update analysis call site**

Use:

```python
overlap = overlap_diagnostic(entries, practical)
```

The headline report must then reconcile:

```text
accepted entries in section 6 == Total_Accepted_Entries in overlap diagnostic
```

- [ ] **Step 4: Run analysis tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py" \
        "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py"
git commit -m "fix: reconcile Strategy V2 overlap counts"
```

---

### Task 5: Reproduce and resolve the legacy regression-suite claim without touching legacy methodology

**Finding addressed:** Important review finding #4.

**Files:**
- Modify V2 files only if V2 import/path behavior causes the failures.
- Modify `Swing Trading/research/swing/strategy_v2_quality_base/README.md` only if the canonical regression command needs correction/clarification.
- Do **not** modify legacy T1 tests, data, or research code unless a demonstrable pre-existing repository defect is independently proven and documented outside this PR.

**Known fact:** `Swing Trading/research/swing/stock_rs/output/stock_rs_daily.csv` is tracked at PR #15's base commit. Do not describe its absence as a pre-existing base condition without reproducing why it is absent in the execution checkout.

- [ ] **Step 1: Verify the tracked legacy fixture before running tests**

From repository root:

```bash
git ls-files --error-unmatch "Swing Trading/research/swing/stock_rs/output/stock_rs_daily.csv"
git status --short -- "Swing Trading/research/swing/stock_rs/output/stock_rs_daily.csv"
```

Expected:

```text
git ls-files succeeds
git status shows no deletion/modification
```

Then verify the file exists in the working tree with Python so the command is platform-neutral:

```bash
python -c "from pathlib import Path; p=Path(r'Swing Trading/research/swing/stock_rs/output/stock_rs_daily.csv'); print(p.exists(), p.stat().st_size if p.exists() else -1)"
```

Expected: `True` and non-zero size.

If the file is tracked but missing locally, restore it from the PR branch HEAD without changing history:

```bash
git restore -- "Swing Trading/research/swing/stock_rs/output/stock_rs_daily.csv"
```

Then repeat the existence check.

- [ ] **Step 2: Run the legacy suite from its correct package root**

The legacy tests import modules as `research.*`, so run:

```bash
cd "Swing Trading"
python -m pytest -q research/swing
cd ..
```

Do not use a root-level command that changes Python package resolution and then label resulting failures as legacy defects.

- [ ] **Step 3: If any failures remain, classify them before editing**

For every failing test, record:

```text
exact test node id
exception type/message
whether the same test fails at base SHA 0ca28d4e1175eee4181af23656230051b26bf276
whether any PR #15 changed file is in the traceback
```

Use a temporary clean comparison checkout/worktree only if needed. Do not change strategy code based on assumptions.

Classification rules:

```text
Fails on base and PR identically -> pre-existing; document exact evidence, do not fix here.
Passes on base, fails on PR       -> PR regression; fix the V2 change causing it.
Only fails under wrong cwd/import -> verification-command defect; correct command/docs.
Missing tracked fixture locally   -> checkout/environment defect; restore fixture and rerun.
```

- [ ] **Step 4: Require clean V2 + regression verification before completion**

Run:

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests"
cd "Swing Trading"
python -m pytest -q research/swing
cd ..
```

Expected for PR completion: both commands PASS unless a base-SHA comparison proves a truly pre-existing failure. If a pre-existing failure is proven, PR body must name the exact failing node IDs and base-SHA reproduction; generic statements such as "file absent in base checkout" are not sufficient.

- [ ] **Step 5: Commit only if a V2/docs correction was required**

Example if only README verification text changes:

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base/README.md"
git commit -m "docs: correct Strategy V2 regression verification"
```

---

### Task 6: Regenerate the complete historical evidence from corrected code

**Files:**
- Regenerate: every committed file in `Swing Trading/research/swing/strategy_v2_quality_base/output/`
- Modify: `README.md` only if factual counts/commands are stated there and changed.

**Requirement:** Task 1 can change the base/candidate universe. Therefore **all previous historical counts and metrics are stale after the fix**, including the current 250 qualified signals, 90 accepted entries, 85 completed paired trades, and `INSUFFICIENT_EVIDENCE` output. Do not assume any of them remain true.

- [ ] **Step 1: Run the full pipeline in locked order**

From repository root:

```bash
python "Swing Trading/research/swing/strategy_v2_quality_base/build_v2_features.py"
python "Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py"
python "Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py"
```

Do not alter thresholds after seeing regenerated results.

- [ ] **Step 2: Verify cross-output reconciliation mechanically**

Run a short Python audit from repository root:

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd

out = Path('Swing Trading/research/swing/strategy_v2_quality_base/output')
signals = pd.read_csv(out / 'v2_signal_candidates.csv')
entries = pd.read_csv(out / 'v2_entries.csv')
cancel = pd.read_csv(out / 'v2_entry_cancellations.csv')
setup = pd.read_csv(out / 'v2_setup_quality_trades.csv')
practical = pd.read_csv(out / 'v2_practical_trades.csv')
overlap = pd.read_csv(out / 'v2_overlap_diagnostic.csv')
gates = pd.read_csv(out / 'v2_validation_gates.csv')

qualified = int(signals['Signal_Qualified'].astype(str).str.lower().eq('true').sum())
assert qualified == len(entries) + len(cancel), (qualified, len(entries), len(cancel))
assert set(setup['Entry_ID']) == set(practical['Entry_ID'])
assert set(setup['Entry_ID']).issubset(set(entries['Entry_ID']))
assert int(overlap.loc[0, 'Total_Accepted_Entries']) == len(entries)
pit = gates.loc[gates['Gate'].eq('POINT_IN_TIME_INTEGRITY')].iloc[0]
assert int(float(pit['Value'])) == 0
print({
    'qualified_signals': qualified,
    'accepted_entries': len(entries),
    'cancellations': len(cancel),
    'completed_paired': len(setup),
    'final_status': gates.loc[gates['Gate'].eq('FINAL_STATUS'), 'Status'].iloc[0],
})
PY
```

If the shell does not support heredoc syntax, put the exact snippet in a temporary local file and run it; do not commit the temporary file.

- [ ] **Step 3: Check the research report is evidence-only**

Confirm it contains:

```text
new regenerated base/signal/entry/completed counts
new setup-quality metrics
new practical metrics
new year summary
new outlier robustness
new leave-one-symbol-out robustness
new breadth diagnostics
reconciled overlap count
explicit derived POINT_IN_TIME_INTEGRITY count
mechanical final PASS/FAIL/INSUFFICIENT_EVIDENCE
```

It must still end with exactly:

> This report supplies locked evidence only. It does not tune Strategy V2 or prescribe a follow-up change. Portfolio Advisor retains the strategy decision.

- [ ] **Step 4: Run all final tests after regeneration**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests"
cd "Swing Trading"
python -m pytest -q research/swing
cd ..
```

Expected: PASS, subject only to a specifically proven base-SHA legacy failure from Task 5.

- [ ] **Step 5: Verify no raw cache or unrelated change is staged**

```bash
git status --short
git diff --stat master...HEAD
```

Allowed scope:

```text
V2 code/tests/README
V2 generated compact evidence
this remediation plan
```

No raw Yahoo OHLCV cache, giant all-symbol feature matrix, strategy-threshold change, or legacy methodology modification.

- [ ] **Step 6: Commit regenerated evidence**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: regenerate corrected Strategy V2 evidence"
```

---

### Task 7: Update PR #15 verification statement and close review findings

**Files:** None required unless PR body is maintained from a file.

- [ ] **Step 1: Update PR #15 body with factual regenerated verification**

Replace stale counts with the newly generated values. The verification section must state:

```text
V2 test count and pass result
full legacy swing-suite result using the correct package-root command
usable/audited symbol counts
qualified signal count
accepted entry count
completed paired outcome count
point-in-time violation count derived from artifacts
mechanical final status
explicit statement that no threshold/filter was tuned after observing outcomes
```

If any proven base-SHA legacy failure remains, list exact test node IDs and base-SHA reproduction evidence.

- [ ] **Step 2: Add one PR comment summarizing the five fixes**

Use a compact factual comment:

```text
Implemented the Portfolio Advisor review remediation plan:

1. restored same-bar reseeding after depth invalidation and added regression coverage;
2. aligned temporal robustness with the exact precommitted setup-quality year gate;
3. derived point-in-time violation count from final artifacts instead of defaulting to zero;
4. reproduced the legacy suite from the correct package root and corrected the verification claim/result;
5. made overlap diagnostics reconcile to all accepted entries, including incomplete outcomes.

Full historical evidence was regenerated from the corrected state machine. No Strategy V2 threshold/filter was changed in response to results.
```

Do not add a strategy recommendation. Portfolio Advisor will interpret the corrected evidence after review.

- [ ] **Step 3: Final verification before claiming completion**

```bash
git status --short
```

Expected: clean working tree.

Then provide the updated PR URL and latest head SHA for Portfolio Advisor review.

---

## Final Verification Checklist

Before declaring the remediation complete:

- [ ] Same-bar reseeding occurs after `DEPTH_INVALIDATED` when `_is_seed()` is true.
- [ ] Existing failed-probe depth logic still rechecks depth using the raised pivot immediately.
- [ ] Temporal robustness uses only the three locked setup-quality year conditions.
- [ ] `evaluate_gates()` cannot obtain a point-in-time PASS from an omitted/default zero argument.
- [ ] Point-in-time violation count is derived from final accepted artifacts and strict-prior breadth joins.
- [ ] `Total_Accepted_Entries` in overlap diagnostics equals rows in `v2_entries.csv`.
- [ ] Incomplete accepted outcomes are represented in overlap diagnostics but are not counted as completed trades.
- [ ] The tracked legacy stock-RS fixture is verified before claiming it is absent.
- [ ] Legacy tests are run from `Swing Trading` so `research.*` imports resolve as designed.
- [ ] No legacy methodology/tests are weakened to make the suite green.
- [ ] Full historical V2 outputs are regenerated after the state-machine correction.
- [ ] Old 250/90/85 counts are not preserved manually.
- [ ] All Strategy V2 thresholds remain unchanged.
- [ ] V2 tests pass.
- [ ] Legacy swing tests pass, or any remaining failure is independently reproduced at the PR base SHA and documented precisely.
- [ ] `POINT_IN_TIME_INTEGRITY` reports a derived value of zero before profitability interpretation.
- [ ] Research report remains evidence-only.
- [ ] No raw market-data cache is committed.

## Execution Handoff

Execute with **`superpowers:executing-plans` in inline mode only**. Work task-by-task and keep the test-before-fix order. Do not invoke `subagent-driven-development`. Do not optimize Strategy V2 after regenerated results are known.