# Strategy V2 PR #15 Review Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use `subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the five PR #15 review findings without changing any Strategy V2 trading rule, threshold, ranking weight, validation threshold, or result interpretation, then regenerate the historical evidence from the corrected implementation.

**Architecture:** Keep the existing `strategy_v2_quality_base` module. Fix the sample-changing state-machine defect first, then align gate evaluation, derive point-in-time integrity from actual artifacts, reconcile overlap diagnostics to all accepted entries, and reproduce the legacy regression suite correctly. Because the state-machine fix can change the candidate universe, regenerate every committed V2 output after code fixes are complete.

**Tech Stack:** Python 3, pandas, numpy, yfinance, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-26-strategy-v2-quality-base-breakout-design.md`

**Original plan:** `docs/superpowers/plans/2026-08-26-strategy-v2-quality-base-validation.md`

**Issue:** `https://github.com/krishna916/Financial/issues/13`

**PR:** `https://github.com/krishna916/Financial/pull/15`

## Global Constraints

- This work fixes implementation/research-integrity defects only. Do not tune Strategy V2 because the current results are weak.
- Keep `Composite_RS >= 70`, RS weights `30/40/30`, base duration `10..30`, base depth `<=4 ATR`, contraction ratio `<=0.80`, signal/entry extension `<=1 ATR`, stop buffer `0.25 ATR`, maximum stop distance `2.5 ATR`, and every other locked strategy rule unchanged.
- T1 remains retired. Do not reintroduce T1 filters or add breadth, sector-RS, volume, event, or portfolio-capacity gates.
- Do not special-case symbols, years, or trades after seeing regenerated outcomes.
- Any change in candidate/signal/trade counts caused by the reseeding correction is expected evidence. Do not force counts back to the old values.
- Regenerated CSV/report values must come from corrected code, never manual edits.
- Legacy T1 code/tests/data are read-only for this remediation unless a PR-caused regression is proven to originate from a V2 change.
- Execute inline with `superpowers:executing-plans` only.

---

## File Map

Modify as required:

```text
Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py
Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py
Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py
Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py
Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_end_to_end.py
Swing Trading/research/swing/strategy_v2_quality_base/README.md
```

Regenerate every committed file under:

```text
Swing Trading/research/swing/strategy_v2_quality_base/output/
```

---

### Task 1: Restore same-bar reseeding after depth invalidation

**Finding:** Blocking review finding #1.

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py`

**Requirement:** After any old base closes, the same bar must independently be tested as a fresh 63-session-high seed. `DEPTH_INVALIDATED` must not suppress this reseed check.

- [ ] **Step 1: Add the failing regression test**

Add:

```python
def test_depth_invalidation_reseeds_same_bar_when_bar_is_new_63_session_high():
    frame = make_valid_base_frame()
    frame.loc[67, ["High", "Low", "Close"]] = [104.0, 95.0, 99.0]

    audit, candidates = scan_symbol_bases("AAA", frame)

    events = audit.loc[audit["Date"].eq(frame.loc[67, "Date"]), "Event"].tolist()
    assert events == ["FAILED_PROBE", "DEPTH_INVALIDATED", "SEEDED"]

    reseed = audit.loc[
        audit["Date"].eq(frame.loc[67, "Date"])
        & audit["Event"].eq("SEEDED")
    ].iloc[0]
    assert reseed["Base_Age"] == 0
    assert reseed["Original_Pivot"] == 104.0
    assert reseed["Active_Pivot"] == 104.0
    assert candidates.empty
```

Update existing `test_failed_probe_rechecks_depth_using_raised_pivot()` so the expected events on row 67 are:

```python
assert events_on_probe_day == ["FAILED_PROBE", "DEPTH_INVALIDATED", "SEEDED"]
```

- [ ] **Step 2: Verify the new test fails before code change**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py" -k "depth_invalidation or failed_probe"
```

Expected before fix: failure because `SEEDED` is absent after `DEPTH_INVALIDATED`.

- [ ] **Step 3: Remove `reseed_on_close` suppression**

In `scan_symbol_bases()`, remove the `reseed_on_close` variable and every assignment that sets it to `False`.

The close path must be exactly:

```python
if closed:
    active = None
    if _is_seed(data, index):
        active = _new_base(symbol, data, index)
        _record_event(events, symbol, row, active, "SEEDED")
```

This applies after:

```text
DEPTH_INVALIDATED
TOO_SHORT_BREAKOUT
BREAKOUT_CANDIDATE
EXPIRED
```

The new seed begins at age 0 on the current bar; its base session 1 begins on the next bar.

- [ ] **Step 4: Run signal tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py" "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_signals.py"
git commit -m "fix: restore Strategy V2 same-bar reseeding"
```

---

### Task 2: Align temporal robustness with the precommitted gate

**Finding:** Important review finding #2.

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py`

**Requirement:** A calendar year qualifies only when setup-quality has `>=20` completed trades, positive mean return, and return PF `>=1.0`. Do not require positive practical mean R per year.

- [ ] **Step 1: Add a failing temporal-gate test**

Add:

```python
def test_temporal_gate_uses_only_locked_setup_year_conditions():
    rows = []
    for year in (2023, 2024):
        for index in range(20):
            rows.append(
                {
                    "Entry_ID": f"{year}-{index}",
                    "Symbol": "AAA" if index % 2 == 0 else "BBB",
                    "Entry_Date": pd.Timestamp(year=year, month=1, day=1)
                    + pd.Timedelta(days=index * 7),
                    "Return": 0.02 if index < 15 else -0.01,
                    "Holding_Sessions": 5,
                }
            )

    setup = pd.DataFrame(rows)
    practical = setup.assign(Initial_Risk=1.0, R_Multiple=-0.25)

    result = evaluate_gates(
        setup,
        practical,
        point_in_time_violations=0,
    )
    temporal = result.loc[result["Gate"].eq("TEMPORAL_ROBUSTNESS")].iloc[0]

    assert bool(temporal["Passed"])
    assert int(temporal["Value"]) == 2
```

- [ ] **Step 2: Run focused test**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py" -k "temporal_gate"
```

Expected before fix: FAIL.

- [ ] **Step 3: Remove the unapproved condition**

Replace:

```python
qualifying_years = years.loc[
    (years["Setup_Completed_Trades"] >= 20)
    & (years["Setup_Mean_Return"] > 0)
    & (years["Setup_Return_PF"] >= 1.0)
    & (years["Practical_Mean_R"] > 0)
]
```

with:

```python
qualifying_years = years.loc[
    (years["Setup_Completed_Trades"] >= 20)
    & (years["Setup_Mean_Return"] > 0)
    & (years["Setup_Return_PF"] >= 1.0)
]
```

Do not alter the global practical gates.

- [ ] **Step 4: Run analysis tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py" "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py"
git commit -m "fix: align Strategy V2 temporal gate"
```

---

### Task 3: Derive point-in-time integrity from final artifacts

**Finding:** Important review finding #3.

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_end_to_end.py`

**Requirement:** `POINT_IN_TIME_INTEGRITY` must be derived from accepted artifacts. It must not PASS because `evaluate_gates()` silently defaults to zero violations.

- [ ] **Step 1: Add the point-in-time audit function**

Add this interface:

```python
def count_point_in_time_violations(
    signals: pd.DataFrame,
    entries: pd.DataFrame,
    setup: pd.DataFrame,
    practical: pd.DataFrame,
) -> tuple[int, pd.DataFrame]:
```

The returned audit columns are exactly:

```text
Entry_ID,Symbol,Violation
```

Use these violation codes:

```text
ACCEPTED_ENTRY_MISSING_QUALIFIED_SIGNAL
SIGNAL_NOT_BEFORE_ENTRY
SIGNAL_BEFORE_WINDOW
INACTIVE_MEMBER_SIGNAL
UNSAFE_RS_COVERAGE_SIGNAL
RS_BELOW_THRESHOLD_SIGNAL
BREADTH_NOT_STRICT_PRIOR_SETUP
BREADTH_NOT_STRICT_PRIOR_PRACTICAL
LENS_ENTRY_ID_MISMATCH
```

Implement with this deterministic logic:

```python
def _truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def count_point_in_time_violations(
    signals: pd.DataFrame,
    entries: pd.DataFrame,
    setup: pd.DataFrame,
    practical: pd.DataFrame,
) -> tuple[int, pd.DataFrame]:
    columns = ["Entry_ID", "Symbol", "Violation"]
    violations: list[dict[str, object]] = []

    accepted = entries.copy()
    qualified = signals.copy()
    if not qualified.empty and "Signal_Qualified" in qualified.columns:
        qualified = qualified.loc[_truthy(qualified["Signal_Qualified"])].copy()

    qualified_ids = set(qualified.get("Entry_ID", pd.Series(dtype=str)).astype(str))
    for row in accepted.itertuples(index=False):
        entry_id = str(row.Entry_ID)
        symbol = str(getattr(row, "Symbol", ""))
        if entry_id not in qualified_ids:
            violations.append(
                {
                    "Entry_ID": entry_id,
                    "Symbol": symbol,
                    "Violation": "ACCEPTED_ENTRY_MISSING_QUALIFIED_SIGNAL",
                }
            )

    if not accepted.empty and not qualified.empty:
        signal_columns = [
            "Entry_ID",
            "Signal_Date",
            "Membership_OK",
            "RS_Coverage_OK",
            "RS_Coverage",
            "Composite_RS",
        ]
        merged = accepted[["Entry_ID", "Symbol", "Entry_Date"]].merge(
            qualified[signal_columns],
            on="Entry_ID",
            how="inner",
            validate="one_to_one",
        )
        merged["Signal_Date"] = pd.to_datetime(merged["Signal_Date"], errors="coerce")
        merged["Entry_Date"] = pd.to_datetime(merged["Entry_Date"], errors="coerce")
        membership_ok = _truthy(merged["Membership_OK"])
        coverage_ok = _truthy(merged["RS_Coverage_OK"])

        for index, row in merged.iterrows():
            entry_id = str(row["Entry_ID"])
            symbol = str(row["Symbol"])
            if pd.isna(row["Signal_Date"]) or pd.isna(row["Entry_Date"]) or row["Signal_Date"] >= row["Entry_Date"]:
                violations.append({"Entry_ID": entry_id, "Symbol": symbol, "Violation": "SIGNAL_NOT_BEFORE_ENTRY"})
            if pd.notna(row["Signal_Date"]) and row["Signal_Date"] < pd.Timestamp("2023-08-01"):
                violations.append({"Entry_ID": entry_id, "Symbol": symbol, "Violation": "SIGNAL_BEFORE_WINDOW"})
            if not bool(membership_ok.loc[index]):
                violations.append({"Entry_ID": entry_id, "Symbol": symbol, "Violation": "INACTIVE_MEMBER_SIGNAL"})
            coverage = pd.to_numeric(pd.Series([row["RS_Coverage"]]), errors="coerce").iloc[0]
            if not bool(coverage_ok.loc[index]) or pd.isna(coverage) or float(coverage) < 0.80:
                violations.append({"Entry_ID": entry_id, "Symbol": symbol, "Violation": "UNSAFE_RS_COVERAGE_SIGNAL"})
            composite = pd.to_numeric(pd.Series([row["Composite_RS"]]), errors="coerce").iloc[0]
            if pd.isna(composite) or float(composite) < 70.0:
                violations.append({"Entry_ID": entry_id, "Symbol": symbol, "Violation": "RS_BELOW_THRESHOLD_SIGNAL"})

    for frame, code in (
        (setup, "BREADTH_NOT_STRICT_PRIOR_SETUP"),
        (practical, "BREADTH_NOT_STRICT_PRIOR_PRACTICAL"),
    ):
        if frame.empty or "Breadth_Matched_Date" not in frame.columns:
            continue
        check = frame.copy()
        check["Entry_Date"] = pd.to_datetime(check["Entry_Date"], errors="coerce")
        check["Breadth_Matched_Date"] = pd.to_datetime(check["Breadth_Matched_Date"], errors="coerce")
        bad = check.loc[
            check["Breadth_Matched_Date"].notna()
            & (check["Breadth_Matched_Date"] >= check["Entry_Date"])
        ]
        for row in bad.itertuples(index=False):
            violations.append(
                {
                    "Entry_ID": str(row.Entry_ID),
                    "Symbol": str(getattr(row, "Symbol", "")),
                    "Violation": code,
                }
            )

    setup_ids = set(setup.get("Entry_ID", pd.Series(dtype=str)).astype(str))
    practical_ids = set(practical.get("Entry_ID", pd.Series(dtype=str)).astype(str))
    if setup_ids != practical_ids:
        for entry_id in sorted(setup_ids.symmetric_difference(practical_ids)):
            violations.append(
                {
                    "Entry_ID": entry_id,
                    "Symbol": "",
                    "Violation": "LENS_ENTRY_ID_MISMATCH",
                }
            )

    audit = pd.DataFrame(violations, columns=columns)
    return len(audit), audit
```

- [ ] **Step 2: Add zero-violation test**

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

- [ ] **Step 3: Add mutation test**

```python
def test_point_in_time_audit_detects_same_day_signal_and_breadth():
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
        "Entry_Date": pd.Timestamp("2024-01-10"),
    }])
    setup = pd.DataFrame([{
        "Entry_ID": "AAA-1",
        "Symbol": "AAA",
        "Entry_Date": pd.Timestamp("2024-01-10"),
        "Breadth_Matched_Date": pd.Timestamp("2024-01-10"),
    }])
    practical = setup.copy()

    count, audit = count_point_in_time_violations(signals, entries, setup, practical)
    assert count >= 3
    assert "SIGNAL_NOT_BEFORE_ENTRY" in set(audit["Violation"])
    assert "BREADTH_NOT_STRICT_PRIOR_SETUP" in set(audit["Violation"])
    assert "BREADTH_NOT_STRICT_PRIOR_PRACTICAL" in set(audit["Violation"])
```

- [ ] **Step 4: Make the gate parameter mandatory**

Change the signature to:

```python
def evaluate_gates(
    setup: pd.DataFrame,
    practical: pd.DataFrame,
    *,
    point_in_time_violations: int,
) -> pd.DataFrame:
```

Remove the default `= 0`. Update every existing unit-test call to pass `point_in_time_violations=0` unless the test intentionally supplies violations.

- [ ] **Step 5: Wire the derived count into historical analysis**

After breadth attachment and `validate_trade_integrity()`:

```python
point_in_time_violations, pit_audit = count_point_in_time_violations(
    candidates,
    entries,
    setup,
    practical,
)
if point_in_time_violations:
    pit_audit.to_csv(
        output_dir / "v2_point_in_time_violations.csv",
        index=False,
    )
    raise AssertionError(
        f"point-in-time integrity violations: {point_in_time_violations}"
    )

gates = evaluate_gates(
    setup,
    practical,
    point_in_time_violations=point_in_time_violations,
)
```

A zero-violation run does not commit `v2_point_in_time_violations.csv`.

- [ ] **Step 6: Strengthen end-to-end test**

Import `count_point_in_time_violations`. After attaching breadth to both synthetic trade lenses, call it with the synthetic candidate/entry/trade frames and assert:

```python
assert point_in_time_violations == 0
assert pit_audit.empty
```

- [ ] **Step 7: Run V2 tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests"
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py" "Swing Trading/research/swing/strategy_v2_quality_base/tests"
git commit -m "fix: derive Strategy V2 point-in-time gate"
```

---

### Task 4: Reconcile overlap diagnostics to all accepted entries

**Finding:** Moderate review finding #5.

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py`
- Modify: `Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py`

**Requirement:** `Total_Accepted_Entries` must equal rows in `v2_entries.csv`, including accepted entries whose outcomes are incomplete at the data boundary.

- [ ] **Step 1: Change the overlap interface**

Use:

```python
def overlap_diagnostic(
    entries: pd.DataFrame,
    practical: pd.DataFrame,
) -> pd.DataFrame:
```

- [ ] **Step 2: Add regression test**

```python
def test_overlap_diagnostic_counts_incomplete_accepted_entries():
    entries = pd.DataFrame({
        "Entry_ID": ["A", "B", "C"],
        "Symbol": ["AAA", "BBB", "CCC"],
        "Entry_Date": pd.to_datetime(["2026-08-20", "2026-08-21", "2026-08-26"]),
    })
    practical = pd.DataFrame({
        "Entry_ID": ["A", "B"],
        "Symbol": ["AAA", "BBB"],
        "Entry_Date": pd.to_datetime(["2026-08-20", "2026-08-21"]),
        "Exit_Date": pd.to_datetime(["2026-08-25", "2026-08-25"]),
    })

    row = overlap_diagnostic(entries, practical).iloc[0]
    assert row["Total_Accepted_Entries"] == 3
    assert row["Max_Same_Day_Entries"] == 1
```

- [ ] **Step 3: Implement exact interval construction**

Inside `overlap_diagnostic()`:

```python
data = entries[["Entry_ID", "Symbol", "Entry_Date"]].copy()
data["Entry_Date"] = pd.to_datetime(data["Entry_Date"], errors="raise")

exits = (
    practical[["Entry_ID", "Exit_Date"]].copy()
    if not practical.empty
    else pd.DataFrame(columns=["Entry_ID", "Exit_Date"])
)
if not exits.empty:
    exits["Exit_Date"] = pd.to_datetime(exits["Exit_Date"], errors="raise")

data = data.merge(exits, on="Entry_ID", how="left", validate="one_to_one")
latest_entry = data["Entry_Date"].max()
latest_exit = exits["Exit_Date"].max() if not exits.empty else latest_entry
observation_end = max(latest_entry, latest_exit)
data["Effective_Exit_Date"] = data["Exit_Date"].fillna(observation_end)
```

Use `Effective_Exit_Date` for same-symbol and simultaneous-open interval calculations. Use every accepted `Entry_Date` for same-day-entry counts. Do not create a return/R multiple for incomplete trades.

- [ ] **Step 4: Update call site**

Replace:

```python
overlap = overlap_diagnostic(practical)
```

with:

```python
overlap = overlap_diagnostic(entries, practical)
```

- [ ] **Step 5: Run analysis tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py" "Swing Trading/research/swing/strategy_v2_quality_base/tests/test_v2_analysis.py"
git commit -m "fix: reconcile Strategy V2 overlap counts"
```

---

### Task 5: Reproduce the legacy regression suite correctly

**Finding:** Important review finding #4.

**Files:**
- Modify V2 files only if a V2 change is proven to cause the regression.
- Modify `Swing Trading/research/swing/strategy_v2_quality_base/README.md` if verification instructions need correction.
- Do not weaken legacy tests or modify legacy research outputs to make this PR green.

**Known repository fact:** `Swing Trading/research/swing/stock_rs/output/stock_rs_daily.csv` is tracked at PR #15 base SHA `0ca28d4e1175eee4181af23656230051b26bf276`.

- [ ] **Step 1: Verify the tracked fixture**

From repository root:

```bash
git ls-files --error-unmatch "Swing Trading/research/swing/stock_rs/output/stock_rs_daily.csv"
git status --short -- "Swing Trading/research/swing/stock_rs/output/stock_rs_daily.csv"
python -c "from pathlib import Path; p=Path(r'Swing Trading/research/swing/stock_rs/output/stock_rs_daily.csv'); print(p.exists(), p.stat().st_size if p.exists() else -1)"
```

Expected:

```text
git ls-files exits 0
git status reports no deletion/modification
Python prints True and a positive byte size
```

If it is tracked but missing locally:

```bash
git restore -- "Swing Trading/research/swing/stock_rs/output/stock_rs_daily.csv"
```

Then rerun the checks.

- [ ] **Step 2: Run the suite from the correct package root**

```bash
cd "Swing Trading"
python -m pytest -q research/swing
cd ..
```

The legacy suite imports `research.*`; this is the canonical invocation.

- [ ] **Step 3: If failures remain, compare against the PR base**

Create a temporary clean worktree:

```bash
git worktree add ../financial-pr15-base 0ca28d4e1175eee4181af23656230051b26bf276
```

Bash execution:

```bash
cd "../financial-pr15-base/Swing Trading"
python -m pytest -q research/swing
cd ../../Financial
git worktree remove ../financial-pr15-base
```

PowerShell execution:

```powershell
Set-Location "../financial-pr15-base/Swing Trading"
python -m pytest -q research/swing
Set-Location "../../Financial"
git worktree remove ../financial-pr15-base
```

Classification is fixed:

```text
Passes on base, fails on PR -> PR regression; fix the V2-caused defect and add a regression test.
Fails identically on base and PR -> stop and report the exact node IDs/errors before claiming PR completion.
Fails only from repository root but passes from Swing Trading -> verification-command defect; correct README/PR wording.
Tracked fixture missing only locally -> checkout/environment defect; restore and rerun.
```

Do not modify legacy methodology/tests to silence a failure.

- [ ] **Step 4: Require clean verification before proceeding**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests"
cd "Swing Trading"
python -m pytest -q research/swing
cd ..
```

Expected: both PASS. If base and PR both fail identically, stop this plan at Task 5 and surface the proven repository blocker instead of claiming completion.

- [ ] **Step 5: Commit only if code/docs changed**

If README verification text changes:

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base/README.md"
git commit -m "docs: correct Strategy V2 regression verification"
```

If a V2 code change was required, commit that V2 fix with its regression test using a message naming the defect.

---

### Task 6: Regenerate all historical evidence from corrected code

**Files:**
- Regenerate: every file in `Swing Trading/research/swing/strategy_v2_quality_base/output/`

**Requirement:** The old `250 qualified / 90 accepted / 85 completed` counts and old final status are stale after Task 1. Do not preserve or target them.

- [ ] **Step 1: Run the full pipeline**

```bash
python "Swing Trading/research/swing/strategy_v2_quality_base/build_v2_features.py"
python "Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py"
python "Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py"
```

Do not alter any strategy or validation threshold after seeing regenerated output.

- [ ] **Step 2: Reconcile generated artifacts**

```bash
python -c "from pathlib import Path; import pandas as pd; out=Path(r'Swing Trading/research/swing/strategy_v2_quality_base/output'); s=pd.read_csv(out/'v2_signal_candidates.csv'); e=pd.read_csv(out/'v2_entries.csv'); c=pd.read_csv(out/'v2_entry_cancellations.csv'); q=int(s['Signal_Qualified'].astype(str).str.lower().eq('true').sum()); a=pd.read_csv(out/'v2_setup_quality_trades.csv'); p=pd.read_csv(out/'v2_practical_trades.csv'); o=pd.read_csv(out/'v2_overlap_diagnostic.csv'); g=pd.read_csv(out/'v2_validation_gates.csv'); assert q==len(e)+len(c),(q,len(e),len(c)); assert set(a['Entry_ID'])==set(p['Entry_ID']); assert set(a['Entry_ID']).issubset(set(e['Entry_ID'])); assert int(o.loc[0,'Total_Accepted_Entries'])==len(e); pit=g.loc[g['Gate'].eq('POINT_IN_TIME_INTEGRITY')].iloc[0]; assert int(float(pit['Value']))==0; print({'qualified':q,'accepted':len(e),'cancelled':len(c),'completed':len(a),'status':g.loc[g['Gate'].eq('FINAL_STATUS'),'Status'].iloc[0]})"
```

Expected: no assertion failure and factual regenerated counts/status printed.

- [ ] **Step 3: Verify report content**

`output/research_report.md` must contain regenerated:

```text
usable/audited symbol counts
base-event counts
qualified signals
accepted entries
incomplete outcomes
setup-quality metrics
practical metrics
year summary
top-1/3/5 robustness
leave-one-symbol-out robustness
breadth diagnostics
overlap diagnostics
derived point-in-time integrity count
mechanical final PASS/FAIL/INSUFFICIENT_EVIDENCE
```

It must still end exactly with:

> This report supplies locked evidence only. It does not tune Strategy V2 or prescribe a follow-up change. Portfolio Advisor retains the strategy decision.

- [ ] **Step 4: Run final tests after regeneration**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests"
cd "Swing Trading"
python -m pytest -q research/swing
cd ..
```

Expected: both PASS.

- [ ] **Step 5: Check scope**

```bash
git status --short
git diff --stat master...HEAD
```

Allowed:

```text
V2 code/tests/README
V2 compact generated evidence
this remediation plan
```

Forbidden:

```text
raw Yahoo OHLCV cache
full all-symbol feature cache
strategy threshold changes
legacy test weakening
legacy methodology changes
result-driven exclusions
```

- [ ] **Step 6: Commit regenerated outputs**

```bash
git add "Swing Trading/research/swing/strategy_v2_quality_base"
git commit -m "research: regenerate corrected Strategy V2 evidence"
```

---

### Task 7: Update PR #15 mechanically from regenerated evidence

**Files:**
- Create temporarily and do not commit: `.pr15_update.py`

- [ ] **Step 1: Create the temporary PR metadata updater**

Create `.pr15_update.py` at repository root with exactly:

```python
from pathlib import Path
import re
import subprocess
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "Swing Trading/research/swing/strategy_v2_quality_base/output"


def run_tests(args: list[str], cwd: Path | None = None) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *args],
        cwd=cwd or ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    if result.returncode != 0:
        raise SystemExit(output)
    match = re.search(r"(\d+) passed", output)
    if not match:
        raise SystemExit(f"could not parse pytest pass count:\n{output}")
    return int(match.group(1)), output


v2_passed, _ = run_tests(
    ["Swing Trading/research/swing/strategy_v2_quality_base/tests"]
)
legacy_passed, _ = run_tests(
    ["research/swing"],
    cwd=ROOT / "Swing Trading",
)

validation = pd.read_csv(OUT / "v2_data_validation.csv")
signals = pd.read_csv(OUT / "v2_signal_candidates.csv")
entries = pd.read_csv(OUT / "v2_entries.csv")
setup = pd.read_csv(OUT / "v2_setup_quality_trades.csv")
gates = pd.read_csv(OUT / "v2_validation_gates.csv")

usable = int(validation["Usable"].astype(str).str.lower().eq("true").sum())
audited = len(validation)
qualified = int(signals["Signal_Qualified"].astype(str).str.lower().eq("true").sum())
accepted = len(entries)
completed = len(setup)
pit = int(float(gates.loc[gates["Gate"].eq("POINT_IN_TIME_INTEGRITY"), "Value"].iloc[0]))
status = str(gates.loc[gates["Gate"].eq("FINAL_STATUS"), "Status"].iloc[0])

if pit != 0:
    raise SystemExit(f"refusing PR update with point-in-time violations={pit}")

body = f"""Implements #13.

## Scope

- Implements the locked Strategy V2 point-in-time Nifty 500 RS, quality-base state machine, breakout/entry mechanics, structural stop, two exit lenses, diagnostics, robustness checks, and precommitted gates.
- Includes the Portfolio Advisor PR-review corrections for same-bar reseeding, exact temporal-gate semantics, derived point-in-time integrity, regression verification, and accepted-entry overlap reconciliation.
- Keeps Strategy V2 methodology frozen; no threshold/filter was tuned after observing outcomes.

## Verification

- Strategy V2 tests: {v2_passed} passed.
- Full swing research suite from `Swing Trading`: {legacy_passed} passed.
- Historical data: {usable}/{audited} audited symbols usable.
- Qualified signals: {qualified}.
- Accepted entries: {accepted}.
- Completed paired outcomes: {completed}.
- Derived point-in-time violations: {pit}.
- Locked validation status: {status}.

Portfolio Advisor retains strategy interpretation.
"""

comment = f"""Implemented the Portfolio Advisor review remediation plan.

- Restored same-bar reseeding after depth invalidation and added regression coverage.
- Aligned temporal robustness with the exact precommitted setup-quality year gate.
- Derived point-in-time violation count from final accepted artifacts instead of defaulting it to zero.
- Reproduced the legacy suite from the correct package root and corrected the verification result/wording.
- Reconciled overlap diagnostics to all accepted entries, including incomplete outcomes.

Regenerated historical evidence: qualified signals = {qualified}, accepted entries = {accepted}, completed paired outcomes = {completed}, point-in-time violations = {pit}, final status = {status}.

No Strategy V2 threshold/filter was changed in response to results. Portfolio Advisor retains strategy interpretation.
"""

subprocess.run(
    ["gh", "pr", "edit", "15", "--body", body],
    cwd=ROOT,
    check=True,
)
subprocess.run(
    ["gh", "pr", "comment", "15", "--body", comment],
    cwd=ROOT,
    check=True,
)
```

- [ ] **Step 2: Run the updater**

```bash
python .pr15_update.py
```

Expected:

```text
Both test suites pass.
Point-in-time violations equal zero.
PR #15 body is replaced with factual regenerated verification.
PR #15 receives one factual remediation comment.
```

If `gh` is not authenticated, stop and report that execution blocker rather than manually inventing/transcribing counts.

- [ ] **Step 3: Remove the temporary updater and verify clean tree**

```bash
python -c "from pathlib import Path; Path('.pr15_update.py').unlink()"
git status --short
```

Expected: clean working tree.

Then provide PR #15 URL and latest head SHA for Portfolio Advisor review.

---

## Final Verification Checklist

- [ ] Same-bar reseeding occurs after `DEPTH_INVALIDATED` whenever `_is_seed()` is true.
- [ ] Failed probes still update pivot first and re-check depth with the raised pivot.
- [ ] Temporal robustness uses only `Setup_Completed_Trades`, `Setup_Mean_Return`, and `Setup_Return_PF` year conditions.
- [ ] `evaluate_gates()` requires an explicit point-in-time violation count.
- [ ] Historical point-in-time violation count is derived from artifacts and equals zero before gate interpretation.
- [ ] Breadth remains strict-prior and diagnostic-only.
- [ ] Overlap `Total_Accepted_Entries` equals `v2_entries.csv` row count.
- [ ] Incomplete accepted outcomes remain in overlap diagnostics but not completed-trade metrics.
- [ ] The tracked legacy stock-RS fixture is verified before any missing-file claim.
- [ ] Legacy tests are invoked from `Swing Trading` so `research.*` imports resolve correctly.
- [ ] No legacy tests/methodology are weakened.
- [ ] Full V2 history is regenerated after the state-machine correction.
- [ ] Old 250/90/85 counts are not manually preserved.
- [ ] All locked Strategy V2 thresholds remain unchanged.
- [ ] V2 tests pass.
- [ ] Full swing research suite passes.
- [ ] Research report remains evidence-only.
- [ ] No raw market-data cache is committed.

## Execution Handoff

Execute with **`superpowers:executing-plans` in inline mode only**. Follow the tasks in order, keep test-before-fix discipline, and do not invoke `subagent-driven-development`. Do not optimize Strategy V2 after the corrected historical result is known.
