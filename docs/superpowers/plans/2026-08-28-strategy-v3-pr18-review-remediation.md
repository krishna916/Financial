# Strategy V3 PR #18 Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the three Portfolio Advisor review findings on PR #18, regenerate Strategy V3 evidence from the corrected head, and replace the current verification claims with fresh mechanically derived evidence.

**Architecture:** Keep the frozen Strategy V3 trading hypothesis unchanged. Repair the impossible regression fixture, strengthen the existing artifact-derived PIT audit so seed-side numeric RS evidence is independently checked, and make the generated report state actual pre-window PIT support. After those correctness fixes pass focused tests, regenerate all historical artifacts, rerun the complete V3 and swing-research suites, reconcile outputs, and update PR #18 mechanically from those fresh files.

**Tech Stack:** Python 3, pandas, numpy, pytest, yfinance, GitHub CLI only for PR metadata/comment updates.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-27-strategy-v3-shallow-pullback-resumption-design.md`

**Original validation plan:** `docs/superpowers/plans/2026-08-27-strategy-v3-shallow-pullback-validation.md`

**Review target:** `https://github.com/krishna916/Financial/pull/18`

## Global Constraints

- Do not change any frozen Strategy V3 threshold, filter, lookback, entry rule, exit rule, stop rule, breadth rule, RS cutoff, signal window, or validation gate.
- Do not use historical outcomes to select a regime, RS band, pullback age/depth, volume bucket, extension bucket, or any other subgroup.
- T1 remains retired and V2 remains closed evidence. Do not modify T1/V2 code or outputs.
- Production `NEW_LEADER_CLOSE` semantics remain strict `Close > Leader_Close`. Equality must not be treated as a new leader.
- Seed-side PIT auditing must independently inspect persisted numeric seed RS coverage and seed Composite_RS; it must not trust only `Seed_RS_Coverage_OK` / `Seed_RS_OK`.
- Pre-window reporting must describe the committed PIT manifest as it exists. Never synthesize or backfill pre-2023-08-01 membership.
- Historical CSV/report files are code-owned and must be regenerated, never hand-edited.
- PR verification claims must come from fresh commands run on the final remediation head.
- No GitHub Actions workflow currently verifies PR #18, so local fresh test output is mandatory evidence.
- Execution mode is inline only.

---

## Files Modified by This Remediation

```text
Swing Trading/research/swing/strategy_v3_shallow_pullback/
├── generate_v3_signals.py
├── analyze_v3_results.py
├── tests/
│   ├── test_v3_signals.py
│   └── test_v3_analysis.py
└── output/
    ├── research_report.md
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
    └── v3_validation_gates.csv
```

Do not add any new strategy-filter artifact.

---

### Task 1: Repair the impossible same-bar reseed fixture and lock the strict boundary

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py`
- Inspect only: `Swing Trading/research/swing/strategy_v3_shallow_pullback/generate_v3_signals.py`

**Production requirement:**

```python
float(row["Close"]) > float(active["Leader_Close"])
```

- [ ] **Step 1: Add a focused equality-boundary regression**

Add:

```python
def test_new_leader_close_requires_strictly_greater_close():
    frame = make_state_frame()
    # Seed row 220 has Leader_Close == 100.0.
    frame.loc[221, ["Close", "High", "Low", "SMA20"]] = [100.0, 100.5, 99.0, 97.0]

    events, candidates = scan_symbol_pullbacks(
        "AAA", frame, pd.DatetimeIndex(frame["Date"])
    )

    same_day = events.loc[
        events["Date"].eq(frame.loc[221, "Date"]), "Event"
    ].tolist()
    assert "NEW_LEADER_CLOSE" not in same_day
    assert candidates.empty
```

- [ ] **Step 2: Run the equality-boundary test**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py::test_new_leader_close_requires_strictly_greater_close"
```

Expected: PASS. If it fails, stop because production semantics no longer match the frozen spec.

- [ ] **Step 3: Fix only the bad matrix fixture**

In `test_same_bar_reseed_runs_after_compatible_closures()`, replace:

```python
"NEW_LEADER_CLOSE": {
    221: {"Close": 100.0, "High": 100.5, "Low": 99.0}
},
```

with:

```python
"NEW_LEADER_CLOSE": {
    221: {"Close": 100.2, "High": 100.5, "Low": 99.0}
},
```

Do not modify production `>` to `>=`.

- [ ] **Step 4: Run the same-bar reseed matrix**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py::test_same_bar_reseed_runs_after_compatible_closures"
```

Expected: PASS.

- [ ] **Step 5: Run the complete signal test file**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py"
```

Expected: zero failures.

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py"
git commit -m "test: fix Strategy V3 new-leader reseed fixture"
```

---

### Task 2: Persist numeric seed RS evidence and independently audit it

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/generate_v3_signals.py`
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py`
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py`
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py`

The active state already stores:

```text
Seed_RS_Coverage
Seed_Composite_RS
```

The signal artifact must carry those values forward.

- [ ] **Step 1: Add a failing candidate-schema regression**

In `test_v3_signals.py` add:

```python
def test_candidate_persists_numeric_seed_rs_evidence():
    frame = make_state_frame()
    state = new_state("AAA", frame.loc[220], 220)
    state["Age"] = 3
    state["Pullback_Low"] = 98.0

    row = frame.loc[223].copy()
    row["Date"] = pd.Timestamp("2024-01-10")
    row["Close"] = 99.0
    row["SMA20"] = 97.0
    row["Composite_RS"] = 82.0

    candidate = build_candidate("AAA", row, 98.5, state)

    assert candidate["Seed_RS_Coverage"] == pytest.approx(1.0)
    assert candidate["Seed_Composite_RS"] == pytest.approx(80.0)
```

- [ ] **Step 2: Verify the new test is red on the current implementation**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py::test_candidate_persists_numeric_seed_rs_evidence"
```

Expected before implementation: FAIL because the candidate omits one or both fields.

- [ ] **Step 3: Extend `SIGNAL_COLUMNS` and `build_candidate()`**

Add these fields before the seed boolean fields:

```python
"Seed_RS_Coverage",
"Seed_Composite_RS",
```

Add to the candidate dictionary:

```python
"Seed_RS_Coverage": active.get("Seed_RS_Coverage", np.nan),
"Seed_Composite_RS": active.get("Seed_Composite_RS", np.nan),
```

Do not derive them from signal-day RS values.

- [ ] **Step 4: Verify candidate persistence is green**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py::test_candidate_persists_numeric_seed_rs_evidence"
```

Expected: PASS.

- [ ] **Step 5: Extend `_pit_fixture()` with valid numeric seed evidence**

In `test_v3_analysis.py`, add to the signal dictionary:

```python
"Seed_RS_Coverage": 1.0,
"Seed_Composite_RS": 80.0,
```

- [ ] **Step 6: Add two red tests that keep booleans true while corrupting numeric seed evidence**

```python
def test_pit_audit_checks_numeric_seed_rs_coverage_even_when_boolean_is_true():
    signals, entries, setup, practical, membership, sessions = _pit_fixture()
    signals.loc[0, "Seed_RS_Coverage_OK"] = True
    signals.loc[0, "Seed_RS_Coverage"] = 0.79

    count, audit = count_point_in_time_violations(
        signals, entries, setup, practical, membership, sessions
    )

    assert count > 0
    assert "SEED_RS_COVERAGE_UNSAFE" in set(audit["Violation"])


def test_pit_audit_checks_numeric_seed_composite_rs_even_when_boolean_is_true():
    signals, entries, setup, practical, membership, sessions = _pit_fixture()
    signals.loc[0, "Seed_RS_OK"] = True
    signals.loc[0, "Seed_Composite_RS"] = 69.9

    count, audit = count_point_in_time_violations(
        signals, entries, setup, practical, membership, sessions
    )

    assert count > 0
    assert "SEED_RS_BELOW_THRESHOLD" in set(audit["Violation"])
```

- [ ] **Step 7: Verify both numeric-audit tests are red**

```bash
python -m pytest -q \
  "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py::test_pit_audit_checks_numeric_seed_rs_coverage_even_when_boolean_is_true" \
  "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py::test_pit_audit_checks_numeric_seed_composite_rs_even_when_boolean_is_true"
```

Expected before audit implementation: FAIL.

- [ ] **Step 8: Add independent numeric checks inside `count_point_in_time_violations()`**

Immediately after the existing seed boolean checks add:

```python
seed_coverage = pd.to_numeric(
    pd.Series([signal.get("Seed_RS_Coverage", np.nan)]),
    errors="coerce",
).iloc[0]
if pd.isna(seed_coverage) or float(seed_coverage) < MIN_RS_COVERAGE:
    _append_violation(
        violations,
        entry_id,
        symbol,
        "SEED_RS_COVERAGE_UNSAFE",
    )

seed_composite = pd.to_numeric(
    pd.Series([signal.get("Seed_Composite_RS", np.nan)]),
    errors="coerce",
).iloc[0]
if pd.isna(seed_composite) or float(seed_composite) < MIN_COMPOSITE_RS:
    _append_violation(
        violations,
        entry_id,
        symbol,
        "SEED_RS_BELOW_THRESHOLD",
    )
```

Before returning the audit, deduplicate identical violations:

```python
audit = pd.DataFrame(
    violations,
    columns=["Entry_ID", "Symbol", "Violation"],
).drop_duplicates(
    subset=["Entry_ID", "Symbol", "Violation"]
).reset_index(drop=True)
return len(audit), audit
```

- [ ] **Step 9: Run the complete PIT-focused analysis tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py" -k "point_in_time or pit_audit"
```

Expected: zero failures.

- [ ] **Step 10: Run complete signal + analysis test files**

```bash
python -m pytest -q \
  "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py" \
  "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py"
```

Expected: zero failures.

- [ ] **Step 11: Commit**

```bash
git add \
  "Swing Trading/research/swing/strategy_v3_shallow_pullback/generate_v3_signals.py" \
  "Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py" \
  "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_signals.py" \
  "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py"
git commit -m "research: strengthen Strategy V3 seed PIT audit"
```

---

### Task 3: Report actual pre-window PIT support and actual pre-window seeds

**Files:**
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py`
- Modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py`

**New interface:**

```python
def prewindow_pit_support_summary(
    membership: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex,
    states: pd.DataFrame,
) -> dict[str, object]:
    ...
```

Return keys exactly:

```text
Prewindow_Start
Prewindow_End
Prewindow_Canonical_Sessions
Sessions_With_PIT_Membership
Support_Status
Actual_Prewindow_Seed_Events
```

`Support_Status` must be `NONE`, `PARTIAL`, or `FULL`.

- [ ] **Step 1: Add deterministic support-summary tests**

Add:

```python
def _prewindow_sessions() -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.bdate_range("2023-07-18", "2023-08-02"))


def test_prewindow_support_summary_reports_none_when_manifest_starts_at_signal_window():
    sessions = _prewindow_sessions()
    membership = pd.DataFrame({
        "Symbol": ["AAA"],
        "Member_From": [pd.Timestamp("2023-08-01")],
        "Member_To": [pd.Timestamp("2024-01-01")],
        "Downloadable": [True],
    })
    states = pd.DataFrame(columns=["Date", "Event"])

    result = prewindow_pit_support_summary(membership, sessions, states)

    assert result["Prewindow_Canonical_Sessions"] == 10
    assert result["Sessions_With_PIT_Membership"] == 0
    assert result["Support_Status"] == "NONE"
    assert result["Actual_Prewindow_Seed_Events"] == 0


def test_prewindow_support_summary_reports_full_and_counts_seed_events():
    sessions = _prewindow_sessions()
    start = prewindow_seed_start(sessions)
    membership = pd.DataFrame({
        "Symbol": ["AAA"],
        "Member_From": [start],
        "Member_To": [pd.Timestamp("2024-01-01")],
        "Downloadable": [True],
    })
    states = pd.DataFrame({
        "Date": [start, pd.Timestamp("2023-08-01")],
        "Event": ["SEEDED", "SEEDED"],
    })

    result = prewindow_pit_support_summary(membership, sessions, states)

    assert result["Sessions_With_PIT_Membership"] == 10
    assert result["Support_Status"] == "FULL"
    assert result["Actual_Prewindow_Seed_Events"] == 1


def test_prewindow_support_summary_reports_partial_support():
    sessions = _prewindow_sessions()
    start = prewindow_seed_start(sessions)
    window = sessions[(sessions >= start) & (sessions < SIGNAL_START)]
    membership = pd.DataFrame({
        "Symbol": ["AAA"],
        "Member_From": [pd.Timestamp(window[5])],
        "Member_To": [pd.Timestamp("2024-01-01")],
        "Downloadable": [True],
    })
    states = pd.DataFrame(columns=["Date", "Event"])

    result = prewindow_pit_support_summary(membership, sessions, states)

    assert result["Sessions_With_PIT_Membership"] == 5
    assert result["Support_Status"] == "PARTIAL"
```

- [ ] **Step 2: Verify the support-summary tests are red**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py" -k "prewindow_support_summary"
```

Expected before implementation: FAIL because the helper does not exist.

- [ ] **Step 3: Implement the helper exactly**

```python
def prewindow_pit_support_summary(
    membership: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex,
    states: pd.DataFrame,
) -> dict[str, object]:
    sessions = pd.DatetimeIndex(
        pd.to_datetime(canonical_sessions, errors="coerce")
    ).dropna().drop_duplicates().sort_values()
    start = prewindow_seed_start(sessions)
    window = sessions[(sessions >= start) & (sessions < SIGNAL_START)]
    if len(window) != 10:
        raise AssertionError(
            f"expected 10 canonical pre-window sessions, got {len(window)}"
        )

    supported = sum(
        not active_members_on(membership, pd.Timestamp(date)).empty
        for date in window
    )
    if supported == 0:
        status = "NONE"
    elif supported == len(window):
        status = "FULL"
    else:
        status = "PARTIAL"

    if states.empty or "Date" not in states.columns or "Event" not in states.columns:
        seed_events = 0
    else:
        state_dates = pd.to_datetime(states["Date"], errors="coerce")
        seed_events = int(
            (
                states["Event"].astype(str).eq("SEEDED")
                & state_dates.ge(start)
                & state_dates.lt(SIGNAL_START)
            ).sum()
        )

    return {
        "Prewindow_Start": pd.Timestamp(window.min()),
        "Prewindow_End": pd.Timestamp(window.max()),
        "Prewindow_Canonical_Sessions": len(window),
        "Sessions_With_PIT_Membership": int(supported),
        "Support_Status": status,
        "Actual_Prewindow_Seed_Events": seed_events,
    }
```

This function measures support only; it never creates membership.

- [ ] **Step 4: Run support-summary tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py" -k "prewindow_support_summary"
```

Expected: PASS.

- [ ] **Step 5: Make `write_evidence_report()` accept the summary**

Add keyword-only parameter:

```python
prewindow_support: dict[str, object],
```

In report section 2 emit these lines:

```python
f"Pre-window seed boundary: {pd.Timestamp(prewindow_support['Prewindow_Start']).date()} "
f"through {pd.Timestamp(prewindow_support['Prewindow_End']).date()} "
f"({prewindow_support['Prewindow_Canonical_Sessions']} canonical sessions).",

f"PIT membership support in that boundary: "
f"{prewindow_support['Sessions_With_PIT_Membership']}/"
f"{prewindow_support['Prewindow_Canonical_Sessions']} sessions; "
f"status={prewindow_support['Support_Status']}.",

f"Actual pre-window SEEDED events in this run: "
f"{prewindow_support['Actual_Prewindow_Seed_Events']}.",

"Unsupported pre-window dates are never backfilled with 2023-08-01 membership.",
```

- [ ] **Step 6: Wire the summary into historical analysis**

After canonical sessions are built:

```python
prewindow_support = prewindow_pit_support_summary(
    membership,
    sessions,
    states,
)
```

Pass it to `write_evidence_report()`.

- [ ] **Step 7: Add a report-text regression**

Create a tiny report fixture using a temporary output directory and a supplied support summary with `Support_Status="NONE"`. Assert the generated text contains:

```python
assert "Pre-window seed boundary:" in text
assert "PIT membership support in that boundary:" in text
assert "status=NONE" in text
assert "Actual pre-window SEEDED events in this run:" in text
assert "never backfilled" in text
```

- [ ] **Step 8: Run complete analysis tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py"
```

Expected: zero failures.

- [ ] **Step 9: Commit**

```bash
git add \
  "Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py" \
  "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests/test_v3_analysis.py"
git commit -m "research: report Strategy V3 prewindow PIT support"
```

---

### Task 4: Regenerate all historical V3 evidence after correctness fixes

**Files:**
- Regenerate every code-owned artifact under `Swing Trading/research/swing/strategy_v3_shallow_pullback/output/`.

- [ ] **Step 1: Confirm no unrelated changes**

```bash
git status --short
```

Only remediation files should be modified before generation.

- [ ] **Step 2: Rebuild feature/RS audits**

```bash
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/build_v3_features.py"
```

Do not alter parameters after inspecting output.

- [ ] **Step 3: Regenerate state, candidates, entries and cancellations**

```bash
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/generate_v3_signals.py"
```

- [ ] **Step 4: Regenerate completed outcomes, PIT audit, diagnostics, gates and report**

```bash
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py"
```

If the strengthened numeric seed audit reports a nonzero PIT count, stop. Do not change thresholds to force zero.

- [ ] **Step 5: Verify numeric seed evidence exists for every candidate row**

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd

path = Path("Swing Trading/research/swing/strategy_v3_shallow_pullback/output/v3_signal_candidates.csv")
signals = pd.read_csv(path)
for column in ("Seed_RS_Coverage", "Seed_Composite_RS"):
    assert column in signals.columns, column
    assert signals[column].notna().all(), f"missing {column}"
print("numeric seed evidence complete")
PY
```

- [ ] **Step 6: Verify the generated report contains actual pre-window evidence**

```bash
python - <<'PY'
from pathlib import Path
text = Path("Swing Trading/research/swing/strategy_v3_shallow_pullback/output/research_report.md").read_text(encoding="utf-8")
for phrase in (
    "Pre-window seed boundary:",
    "PIT membership support in that boundary:",
    "Actual pre-window SEEDED events in this run:",
    "never backfilled",
):
    assert phrase in text, phrase
print("prewindow evidence present")
PY
```

- [ ] **Step 7: Reconcile all accounting and PIT gates**

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
pit = float(gates.loc[gates["Gate"].eq("POINT_IN_TIME_INTEGRITY"), "Value"].iloc[0])
assert pit == 0.0, pit
status = gates.loc[gates["Gate"].eq("FINAL_STATUS"), "Status"].iloc[0]
print(
    f"qualified={len(qualified)} accepted={len(entries)} "
    f"cancelled={len(cancels)} completed={len(setup)} pit=0 status={status}"
)
PY
```

- [ ] **Step 8: Inspect the generated diff without interpreting/tuning it**

```bash
git diff --stat
git diff -- "Swing Trading/research/swing/strategy_v3_shallow_pullback/output/v3_validation_gates.csv"
git diff -- "Swing Trading/research/swing/strategy_v3_shallow_pullback/output/research_report.md"
```

Only mechanically generated schema/evidence/report differences are acceptable.

- [ ] **Step 9: Commit regenerated evidence**

```bash
git add "Swing Trading/research/swing/strategy_v3_shallow_pullback/output"
git commit -m "research: regenerate Strategy V3 evidence after review fixes"
```

---

### Task 5: Run fresh verification on the final remediation head

**Files:**
- No repository changes expected.

Use repo-root log files so the same metadata script works on Bash and PowerShell. Remove the logs before finishing; never commit them.

- [ ] **Step 1: Run complete V3 tests and capture output**

Bash:

```bash
set -o pipefail
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests" | tee pr18-v3-tests.txt
```

PowerShell:

```powershell
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests" 2>&1 | Tee-Object -FilePath "pr18-v3-tests.txt"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

Require exit code 0.

- [ ] **Step 2: Run the complete canonical swing-research suite and capture output**

Bash:

```bash
set -o pipefail
(
  cd "Swing Trading"
  python -m pytest -q research/swing
) | tee pr18-swing-tests.txt
```

PowerShell:

```powershell
Push-Location "Swing Trading"
python -m pytest -q research/swing 2>&1 | Tee-Object -FilePath "..\pr18-swing-tests.txt"
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { exit $code }
```

Require exit code 0.

- [ ] **Step 3: If the full suite fails, compare with the exact PR base before changing any legacy test**

Base SHA:

```text
d8e8ea37a7bb490f9410ad8fe3276e63ca3be62a
```

Create a temporary worktree at that SHA and run the same `cd "Swing Trading" && python -m pytest -q research/swing` command. Base-pass/current-fail means V3 introduced a regression. The same failure on both means surface the existing blocker; do not weaken legacy tests.

- [ ] **Step 4: Parse test logs mechanically**

```bash
python - <<'PY'
from pathlib import Path
import re

for path in (Path("pr18-v3-tests.txt"), Path("pr18-swing-tests.txt")):
    text = path.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(r"(\d+) passed", text)
    assert matches, f"no passed count in {path}"
    assert not re.search(r"\b\d+ failed\b", text), f"failures present in {path}"
    print(path.name, int(matches[-1]))
PY
```

- [ ] **Step 5: Verify diff scope**

```bash
git diff --name-only d8e8ea37a7bb490f9410ad8fe3276e63ca3be62a...HEAD
```

Only V3 files plus this remediation plan may differ from the PR base.

- [ ] **Step 6: Verify working tree contains only temporary logs**

```bash
git status --short
```

Expected untracked files only:

```text
?? pr18-v3-tests.txt
?? pr18-swing-tests.txt
```

If anything else is modified/untracked, resolve it before PR metadata update.

---

### Task 6: Update PR #18 mechanically from fresh logs/artifacts and post remediation evidence

**Files:**
- Create temporarily, then delete without committing: `.pr18_remediation_metadata.py`

- [ ] **Step 1: Create the deterministic PR metadata script**

Create `.pr18_remediation_metadata.py` with exactly:

```python
from pathlib import Path
import re
import subprocess
import pandas as pd

ROOT = Path.cwd()
OUT = ROOT / "Swing Trading/research/swing/strategy_v3_shallow_pullback/output"


def passed_count(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(r"(\d+) passed", text)
    if not matches:
        raise SystemExit(f"could not parse passed count from {path}")
    if re.search(r"\b\d+ failed\b", text):
        raise SystemExit(f"test failures present in {path}")
    return int(matches[-1])


v3_tests = passed_count(ROOT / "pr18-v3-tests.txt")
swing_tests = passed_count(ROOT / "pr18-swing-tests.txt")
validation = pd.read_csv(OUT / "v3_data_validation.csv")
rs = pd.read_csv(OUT / "v3_universe_rs_audit.csv")
signals = pd.read_csv(OUT / "v3_signal_candidates.csv")
entries = pd.read_csv(OUT / "v3_entries.csv")
cancels = pd.read_csv(OUT / "v3_entry_cancellations.csv")
setup = pd.read_csv(OUT / "v3_setup_quality_trades.csv")
gates = pd.read_csv(OUT / "v3_validation_gates.csv")
report = (OUT / "research_report.md").read_text(encoding="utf-8")

for column in ("Seed_RS_Coverage", "Seed_Composite_RS"):
    if column not in signals.columns or signals[column].isna().any():
        raise SystemExit(f"candidate numeric seed evidence invalid: {column}")

for phrase in (
    "Pre-window seed boundary:",
    "PIT membership support in that boundary:",
    "Actual pre-window SEEDED events in this run:",
):
    if phrase not in report:
        raise SystemExit(f"report evidence missing: {phrase}")

qualified_mask = signals["Signal_Qualified"].astype(str).str.lower().isin(["true", "1"])
qualified = int(qualified_mask.sum())
usable = int(validation["Usable"].astype(str).str.lower().isin(["true", "1"]).sum())
pit = float(gates.loc[gates["Gate"].eq("POINT_IN_TIME_INTEGRITY"), "Value"].iloc[0])
status = str(gates.loc[gates["Gate"].eq("FINAL_STATUS"), "Status"].iloc[0])
if pit != 0.0:
    raise SystemExit(f"refusing PR update with PIT violations={pit}")
if qualified != len(entries) + len(cancels):
    raise SystemExit("qualified/accepted/cancelled accounting mismatch")

body = f"""## Summary

Implements the locked Strategy V3 shallow-pullback resumption validation plan for issue #16.

- Adds adjusted-OHLCV feature construction, PIT membership/RS audits, and a canonical market-session spine.
- Adds the deterministic leader → 3–10 session shallow pullback → resumption state machine, next-session entries, cancellation audit, and locked setup-quality/practical exit lenses.
- Adds PIT integrity checks, temporal/outlier/leave-one-symbol-out robustness, breadth and overlap diagnostics, tests, and committed historical evidence.
- PR #18 remediation strengthens independent numeric seed RS auditing and explicit pre-window PIT evidence reporting without changing the frozen strategy.

## Validation

- Strategy V3 tests: {v3_tests} passed.
- Full `research/swing` suite: {swing_tests} passed.
- Historical artifacts: {usable}/{len(validation)} usable symbols; {len(rs)} RS audit dates; {len(signals)} candidates; {qualified} qualified; {len(entries)} accepted; {len(cancels)} cancelled; {len(setup)} completed paired outcomes.
- Qualified reconciliation: {qualified} = {len(entries)} + {len(cancels)}; accepted/cancelled IDs are disjoint by the generated reconciliation step.
- Point-in-time integrity: 0 violations, including independent numeric seed RS coverage and seed Composite_RS checks.
- `research_report.md` explicitly records actual ten-session pre-window PIT membership support and actual pre-window SEEDED count.

## Frozen-gate result

The generated frozen validation status is `{status}`. No Strategy V3 thresholds, filters, rank cutoffs, lookbacks, entry/exit rules, diagnostic subgroup gates, or exclusions were tuned after outcomes.

The committed report leaves strategy interpretation and follow-up decisions to the Portfolio Advisor.
"""

comment = f"""PR #18 review remediation completed.

Addressed:
1. repaired the impossible `NEW_LEADER_CLOSE` same-bar reseed fixture while preserving strict `Close > Leader_Close` production semantics;
2. persisted `Seed_RS_Coverage` and `Seed_Composite_RS` into candidate artifacts and made the PIT audit independently verify both numeric values;
3. `research_report.md` now states actual ten-session pre-window PIT support and actual pre-window `SEEDED` count.

Fresh verification:
- V3 suite: {v3_tests} passed.
- full `research/swing` suite: {swing_tests} passed.
- qualified/accepted/cancelled/completed: {qualified}/{len(entries)}/{len(cancels)}/{len(setup)}.
- PIT violations: 0.
- frozen final status: {status}.

No Strategy V3 thresholds, filters, lookbacks, entry/exit rules, diagnostics-to-gates, or validation gates were changed.
"""

subprocess.run(
    ["gh", "pr", "edit", "18", "--body", body],
    check=True,
)
subprocess.run(
    ["gh", "pr", "comment", "18", "--body", comment],
    check=True,
)
```

- [ ] **Step 2: Run the metadata script**

```bash
python .pr18_remediation_metadata.py
```

If GitHub CLI is not authenticated, stop and report that environment blocker. Do not manually reconstruct test counts from memory.

- [ ] **Step 3: Delete all temporary files**

Bash:

```bash
rm .pr18_remediation_metadata.py pr18-v3-tests.txt pr18-swing-tests.txt
```

PowerShell:

```powershell
Remove-Item .pr18_remediation_metadata.py, pr18-v3-tests.txt, pr18-swing-tests.txt
```

- [ ] **Step 4: Verify clean tree**

```bash
git status --short
```

Expected: no output.

- [ ] **Step 5: Stop for Portfolio Advisor re-review**

Do not merge PR #18. The Portfolio Advisor will independently re-read the final head, tests, and regenerated evidence.

---

## Final Remediation Checklist

- [ ] Production `NEW_LEADER_CLOSE` remains strict `Close > Leader_Close`.
- [ ] Equality has an explicit no-new-leader regression.
- [ ] Same-bar reseed matrix uses `Close=100.2` for the `NEW_LEADER_CLOSE` case.
- [ ] `Seed_RS_Coverage` is persisted in candidate artifacts.
- [ ] `Seed_Composite_RS` is persisted in candidate artifacts.
- [ ] PIT audit independently checks numeric seed coverage against `0.80`.
- [ ] PIT audit independently checks numeric seed Composite_RS against `70`.
- [ ] Numeric PIT regressions keep boolean flags true and still detect invalid numeric evidence.
- [ ] Identical PIT violations are deduplicated before counting.
- [ ] Report states the exact ten canonical pre-window sessions.
- [ ] Report states how many of those sessions have real PIT membership.
- [ ] Report labels support as `NONE`, `PARTIAL`, or `FULL`.
- [ ] Report states actual pre-window `SEEDED` count.
- [ ] Unsupported pre-window dates are never backfilled.
- [ ] Historical artifacts are regenerated from code.
- [ ] Qualified = accepted + cancelled and accepted/cancelled sets are disjoint.
- [ ] Setup/practical completed Entry_ID sets remain identical.
- [ ] Overlap still counts all accepted entries.
- [ ] Derived PIT violations are zero before profitability interpretation.
- [ ] Frozen final status is accepted mechanically regardless of PASS/FAIL outcome.
- [ ] Complete V3 suite passes freshly on the final remediation head.
- [ ] Complete `research/swing` suite passes freshly on the final remediation head.
- [ ] PR body and comment are generated from fresh logs/artifacts.
- [ ] No T1/V2 files changed.
- [ ] No outcome-driven V3 tuning occurred.

## Execution Handoff

Execute with:

```text
superpowers:executing-plans
```

**Inline execution only. Never use `superpowers:subagent-driven-development`.**

Work task-by-task, run the named tests at each boundary, commit each logical fix separately, regenerate historical evidence only after correctness tests are green, update PR #18 mechanically from fresh logs/artifacts, and stop for Portfolio Advisor re-review.