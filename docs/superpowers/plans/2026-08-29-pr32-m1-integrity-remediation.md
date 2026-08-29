# PR #32 M1 Integrity Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the two blocking research-integrity gaps found in PR #32 without changing the frozen M1 strategy, then rerun the exact validation and confirm the formal result remains mechanically derived from the approved design.

**Architecture:** Make two narrow changes in `run_m1_validation.py`: (1) explicitly audit every qualified V3 `Signal_Date` against the frozen `2023-08-01..2026-08-25` primary window and feed violations into the existing integrity/status pipeline; (2) treat `research_report.md` as a required non-empty final evidence artifact in `_final_package_issues()`. Add deterministic tests that fail before each fix and prove the full `INVALID_RESEARCH_RUN` precedence through `run_validation()`. Do not touch regime rules, V3 partitioning, friction, gates, thresholds, stops, exits, or post-result interpretation.

**Tech Stack:** Python 3, pandas, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-29-m1-regime-gated-momentum-resumption-design.md`

**PR:** `https://github.com/krishna916/Financial/pull/32`

## Global Constraints

- Frozen M1 primary signal window is `2023-08-01` through `2026-08-25` inclusive.
- Any qualified V3 signal outside that window is a mandatory research-integrity violation and forces `INVALID_RESEARCH_RUN`; do not silently filter or clip it.
- `research_report.md` is part of the approved minimum evidence package and must exist, be readable UTF-8 text, and contain non-whitespace content.
- Final evidence-package defects are integrity defects and must force `INVALID_RESEARCH_RUN` through the existing status precedence.
- M1 strategy logic must remain unchanged: 80% breadth coverage, Nifty 500 `Close > SMA200`, Nifty 500 `SMA50 > SMA200`, `Pct_Above_SMA50 >= 50%`, frozen V3 stock setup/entry/exit evidence, 0.40%/0.60%/0.80% friction, and all existing gates.
- Do not modify anything under `Swing Trading/research/swing/strategy_v3_shallow_pullback/`.
- Do not add rescue logic or change the current formal M1 `FAIL` criteria/results to make the strategy pass.
- If the integrity fixes do not alter the source cohort, the regenerated M1 economics should remain unchanged; investigate any unexpected metric change as an implementation/integrity issue only.

## File Map

**Modify only:**

```text
Swing Trading/research/swing/m1_regime_gated_momentum/run_m1_validation.py
Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_end_to_end.py
Swing Trading/research/swing/m1_regime_gated_momentum/output/*   # regenerate only after tests pass
```

Do not create a new research module, downloader, framework, dashboard, strategy variant, or new signal output.

---

### Task 1: Enforce the frozen primary signal window as a mandatory integrity check

**Files:**
- Modify: `Swing Trading/research/swing/m1_regime_gated_momentum/run_m1_validation.py`
- Modify: `Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_end_to_end.py`

**Interfaces:**

Add this helper beside the existing audit helpers in `run_m1_validation.py`:

```python
def _signal_window_audit(qualified: pd.DataFrame) -> pd.DataFrame:
    """Return one integrity row for every qualified signal outside the frozen M1 window."""
```

The helper must return the same six-column tagged audit schema used by the runner:

```text
Entry_ID,Symbol,Violation,Observed,Expected,Source
```

Use exactly this violation name:

```text
SIGNAL_DATE_OUTSIDE_PRIMARY_WINDOW
```

- [ ] **Step 1: Add a deterministic helper-level failing test**

In `test_m1_end_to_end.py`, import `_signal_window_audit`, then add:

```python
def test_signal_window_audit_rejects_dates_outside_frozen_primary_window():
    qualified = pd.DataFrame(
        [
            {
                "Entry_ID": "BEFORE-2023-07-31",
                "Symbol": "BEFORE",
                "Signal_Date": pd.Timestamp("2023-07-31"),
            },
            {
                "Entry_ID": "START-2023-08-01",
                "Symbol": "START",
                "Signal_Date": pd.Timestamp("2023-08-01"),
            },
            {
                "Entry_ID": "END-2026-08-25",
                "Symbol": "END",
                "Signal_Date": pd.Timestamp("2026-08-25"),
            },
            {
                "Entry_ID": "AFTER-2026-08-26",
                "Symbol": "AFTER",
                "Signal_Date": pd.Timestamp("2026-08-26"),
            },
        ]
    )

    audit = _signal_window_audit(qualified)

    assert set(audit["Entry_ID"]) == {
        "BEFORE-2023-07-31",
        "AFTER-2026-08-26",
    }
    assert set(audit["Violation"]) == {"SIGNAL_DATE_OUTSIDE_PRIMARY_WINDOW"}
    assert set(audit["Source"]) == {"signal_window"}
    assert set(audit["Expected"]) == {"2023-08-01 <= Signal_Date <= 2026-08-25"}
```

- [ ] **Step 2: Run the single test and verify it fails**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_end_to_end.py::test_signal_window_audit_rejects_dates_outside_frozen_primary_window"
```

Expected: FAIL because `_signal_window_audit` does not exist.

- [ ] **Step 3: Implement the minimal window audit**

Add exactly this behavior in `run_m1_validation.py`:

```python
def _signal_window_audit(qualified: pd.DataFrame) -> pd.DataFrame:
    if qualified.empty:
        return _empty_audit()

    rows: list[dict[str, object]] = []
    signal_dates = pd.to_datetime(qualified.get("Signal_Date"), errors="coerce")
    outside = signal_dates.lt(PRIMARY_START) | signal_dates.gt(PRIMARY_END)

    for index in qualified.index[outside.fillna(False)]:
        row = qualified.loc[index]
        rows.append(
            {
                "Entry_ID": row.get("Entry_ID", ""),
                "Symbol": row.get("Symbol", ""),
                "Violation": "SIGNAL_DATE_OUTSIDE_PRIMARY_WINDOW",
                "Observed": str(signal_dates.loc[index].date()),
                "Expected": "2023-08-01 <= Signal_Date <= 2026-08-25",
            }
        )

    return _audit_rows(rows, "signal_window")
```

Do not filter `qualified`. The exact frozen V3 set must continue through the pipeline so the run becomes invalid rather than silently changing the sample.

- [ ] **Step 4: Wire the audit into status precedence**

Immediately after:

```python
qualified = _qualified_signals(...)
```

compute:

```python
signal_window_audit = _signal_window_audit(qualified)
```

Then include `signal_window_audit` directly in `_merge_audits(...)` when constructing `all_integrity`:

```python
all_integrity = _merge_audits(
    ...,
    signal_window_audit,
    ...,
)
```

Because `evaluate_gates()` already gives integrity precedence, no new status logic is allowed.

- [ ] **Step 5: Add one pipeline-level precedence test without fabricating 300 trades**

Extend `write_market_package()` so it accepts an optional `dates` list while preserving its current default:

```python
def write_market_package(
    root: Path,
    dates: list[str] | None = None,
) -> tuple[Path, Path, Path, Path]:
    dates = dates or ["2024-01-02", "2024-01-03", "2024-01-04"]
    ...
```

For the test, start from `write_minimal_v3_package(v3_root)`, then replace the accepted `AAA` signal date consistently across the frozen fixture files so source accounting remains valid:

```python
def test_end_to_end_out_of_window_qualified_signal_forces_invalid(tmp_path):
    v3_root = tmp_path / "v3"
    write_minimal_v3_package(v3_root)

    replacements = {
        "v3_signal_candidates.csv": ["Signal_Date"],
        "v3_entries.csv": ["Signal_Date"],
        "v3_setup_quality_trades.csv": ["Signal_Date"],
        "v3_practical_trades.csv": ["Signal_Date"],
    }
    for filename, columns in replacements.items():
        path = v3_root / filename
        frame = pd.read_csv(path)
        mask = frame["Entry_ID"].eq("AAA-2024-01-02")
        for column in columns:
            frame.loc[mask, column] = "2023-07-31"
        frame.to_csv(path, index=False)

    breadth, index_daily, membership, sector = write_market_package(
        tmp_path,
        dates=["2023-07-31", "2024-01-03", "2024-01-04"],
    )

    status, _ = run_validation(
        v3_root,
        breadth,
        index_daily,
        membership,
        sector,
        tmp_path / "out",
    )

    audit = pd.read_csv(tmp_path / "out" / "m1_integrity_audit.csv")
    assert status == "INVALID_RESEARCH_RUN"
    assert "SIGNAL_DATE_OUTSIDE_PRIMARY_WINDOW" in audit["Violation"].tolist()
```

When making `write_market_package()` accept arbitrary dates, size its literal columns from `len(dates)` so all arrays remain equal length. Keep the same enabled market values for every supplied date.

- [ ] **Step 6: Run focused tests and verify they pass**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_end_to_end.py" -k "signal_window or out_of_window"
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add \
  "Swing Trading/research/swing/m1_regime_gated_momentum/run_m1_validation.py" \
  "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_end_to_end.py"
git commit -m "research: enforce frozen M1 signal window"
```

---

### Task 2: Make `research_report.md` a real required final-evidence artifact

**Files:**
- Modify: `Swing Trading/research/swing/m1_regime_gated_momentum/run_m1_validation.py`
- Modify: `Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_end_to_end.py`

**Interfaces:**

Keep `FINAL_REQUIRED_COLUMNS` for CSV schema verification and add a separate explicit text-artifact constant:

```python
FINAL_REQUIRED_TEXT_FILES = ("research_report.md",)
```

`_final_package_issues(output_dir: Path) -> list[dict[str, object]]` remains the single final-package verifier.

- [ ] **Step 1: Write failing verifier tests for missing and blank reports**

Import `_final_package_issues` and `OUTPUT_FILES` in `test_m1_end_to_end.py`.

Add this local helper to create the smallest structurally readable final package:

```python
def write_minimal_final_package(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    from run_m1_validation import FINAL_REQUIRED_COLUMNS

    for filename, columns in FINAL_REQUIRED_COLUMNS.items():
        pd.DataFrame([{column: "x" for column in columns}]).to_csv(
            output_dir / filename,
            index=False,
        )
```

Then add:

```python
def test_final_package_verifier_rejects_missing_research_report(tmp_path):
    out = tmp_path / "out"
    write_minimal_final_package(out)

    issues = _final_package_issues(out)

    assert any(
        row["Violation"] == "MISSING_FINAL_EVIDENCE"
        and row["Observed"] == "research_report.md"
        for row in issues
    )


def test_final_package_verifier_rejects_blank_research_report(tmp_path):
    out = tmp_path / "out"
    write_minimal_final_package(out)
    (out / "research_report.md").write_text("   \n", encoding="utf-8")

    issues = _final_package_issues(out)

    assert any(
        row["Violation"] == "INVALID_FINAL_EVIDENCE"
        and "research_report.md" in str(row["Observed"])
        for row in issues
    )
```

- [ ] **Step 2: Run the two tests and verify they fail**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_end_to_end.py" -k "missing_research_report or blank_research_report"
```

Expected: FAIL because the report is currently not iterated by `_final_package_issues()`.

- [ ] **Step 3: Implement explicit text-artifact verification**

Near `FINAL_REQUIRED_COLUMNS`, add:

```python
FINAL_REQUIRED_TEXT_FILES = ("research_report.md",)
```

At the start of `_final_package_issues()`, before the CSV loop, add:

```python
for filename in FINAL_REQUIRED_TEXT_FILES:
    path = output_dir / filename
    if not path.exists():
        issues.append(
            {
                "Entry_ID": "",
                "Symbol": "",
                "Violation": "MISSING_FINAL_EVIDENCE",
                "Observed": filename,
                "Expected": "readable non-empty UTF-8 text file",
            }
        )
        continue

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        issues.append(
            {
                "Entry_ID": "",
                "Symbol": "",
                "Violation": "INVALID_FINAL_EVIDENCE",
                "Observed": f"{filename}: {exc}",
                "Expected": "readable non-empty UTF-8 text file",
            }
        )
        continue

    if not content.strip():
        issues.append(
            {
                "Entry_ID": "",
                "Symbol": "",
                "Violation": "INVALID_FINAL_EVIDENCE",
                "Observed": f"{filename}: blank content",
                "Expected": "readable non-empty UTF-8 text file",
            }
        )
```

Leave the existing CSV verification loop unchanged except remove its dead `if filename == "research_report.md"` branch, because `research_report.md` is not and should not be part of `FINAL_REQUIRED_COLUMNS`.

- [ ] **Step 4: Add one end-to-end precedence test using monkeypatch**

The pipeline normally writes a valid report, so explicitly simulate report corruption after the first write rather than changing production orchestration.

Use pytest's `monkeypatch` to replace `write_research_report` with a writer that creates blank content:

```python
def test_end_to_end_blank_required_report_forces_invalid(tmp_path, monkeypatch):
    import run_m1_validation as runner

    v3_root = tmp_path / "v3"
    write_minimal_v3_package(v3_root)
    breadth, index_daily, membership, sector = write_market_package(tmp_path)

    def write_blank_report(path, status, evidence):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n", encoding="utf-8")

    monkeypatch.setattr(runner, "write_research_report", write_blank_report)

    status, _ = runner.run_validation(
        v3_root,
        breadth,
        index_daily,
        membership,
        sector,
        tmp_path / "out",
    )

    audit = pd.read_csv(tmp_path / "out" / "m1_integrity_audit.csv")
    assert status == "INVALID_RESEARCH_RUN"
    assert "INVALID_FINAL_EVIDENCE" in audit["Violation"].tolist()
```

This test proves the final-package issue is actually merged into integrity and not merely detected by a standalone helper.

- [ ] **Step 5: Run focused report-package tests**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_end_to_end.py" -k "research_report or required_report"
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add \
  "Swing Trading/research/swing/m1_regime_gated_momentum/run_m1_validation.py" \
  "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_end_to_end.py"
git commit -m "research: validate required M1 report evidence"
```

---

### Task 3: Regression-test and regenerate the frozen M1 evidence unchanged

**Files:**
- Regenerate: `Swing Trading/research/swing/m1_regime_gated_momentum/output/*`
- Do not modify: `Swing Trading/research/swing/strategy_v3_shallow_pullback/**`

- [ ] **Step 1: Run the complete focused M1 tests**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests"
```

Expected: zero failures. Report the exact pass count.

- [ ] **Step 2: Run frozen V3 regressions**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests"
```

Expected: zero failures. Report the exact pass count.

- [ ] **Step 3: Run the full swing-research regression suite**

Use the repository's working path convention. Prefer:

```bash
python -m pytest -q "Swing Trading/research/swing"
```

If the repository's established command is `python -m pytest -q research/swing`, use that instead and report the exact command. Expected: zero failures apart from the already-known non-failing pytest-cache permission warning, if it still appears.

- [ ] **Step 4: Prove V3 remains untouched before the real rerun**

```bash
git status --short -- "Swing Trading/research/swing/strategy_v3_shallow_pullback"
```

Expected: no output.

- [ ] **Step 5: Run the real frozen M1 validator exactly once**

```bash
python "Swing Trading/research/swing/m1_regime_gated_momentum/run_m1_validation.py"
```

Do not inspect intermediate profitability and change methodology. This rerun is only to regenerate evidence after integrity-harness fixes.

- [ ] **Step 6: Verify the two corrected integrity requirements on real evidence**

Run:

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd

root = Path("Swing Trading/research/swing/m1_regime_gated_momentum/output")
classification = pd.read_csv(root / "m1_signal_classification.csv", parse_dates=["Signal_Date"])
audit = pd.read_csv(root / "m1_integrity_audit.csv")
report = root / "research_report.md"

assert classification["Signal_Date"].between("2023-08-01", "2026-08-25", inclusive="both").all()
assert report.exists()
assert report.read_text(encoding="utf-8").strip()
assert audit.empty
print("M1 integrity remediation checks: PASS")
PY
```

Expected: prints `M1 integrity remediation checks: PASS`.

- [ ] **Step 7: Verify the strategy result was not rescued or altered**

Read:

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd

root = Path("Swing Trading/research/swing/m1_regime_gated_momentum/output")
gates = pd.read_csv(root / "m1_validation_gates.csv")
comparison = pd.read_csv(root / "m1_regime_comparison.csv")
temporal = pd.read_csv(root / "m1_temporal_summary.csv")

status = gates.loc[gates["Gate"].eq("FINAL_STATUS"), "Value"].iloc[0]
assert status == "FAIL"
assert int(gates.loc[gates["Gate"].eq("SAMPLE_SUFFICIENCY"), "Value"].iloc[0]) == 825
print(gates.to_string(index=False))
print(comparison.to_string(index=False))
print(temporal.to_string(index=False))
PY
```

Expected on the current frozen source cohort: formal status remains `FAIL` and enabled completed count remains `825`. The previously committed economics were approximately base practical mean `-0.014416R`, base R-PF `0.975019`, stress mean `-0.057846R`, stress R-PF `0.905144`, first-half mean `+0.053281R`, and second-half mean `-0.334567R`.

If any of these economics change materially after only the two integrity fixes, stop and investigate the implementation/data path. **Do not change M1 strategy parameters or gates.**

- [ ] **Step 8: Prove V3 remains untouched after the rerun**

```bash
git status --short -- "Swing Trading/research/swing/strategy_v3_shallow_pullback"
```

Expected: no output.

- [ ] **Step 9: Commit regenerated evidence**

```bash
git add \
  "Swing Trading/research/swing/m1_regime_gated_momentum/output" \
  "Swing Trading/research/swing/m1_regime_gated_momentum/run_m1_validation.py" \
  "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_end_to_end.py"
git commit -m "research: remediate M1 validation integrity"
```

### Final implementation handoff

Report only:

- remediation commit SHA(s);
- exact test commands and pass counts;
- confirmation that `SIGNAL_DATE_OUTSIDE_PRIMARY_WINDOW` is enforced through `INVALID_RESEARCH_RUN` precedence;
- confirmation that missing/blank/unreadable `research_report.md` is enforced through final-package integrity;
- real-run integrity violation count;
- enabled completed count;
- base/stress practical metrics;
- formal M1 status;
- whether V3 changed (expected: **no**).

Do not propose a strategy rescue. Once these two blockers are fixed and the frozen rerun remains valid, PR #32 can be re-reviewed for merge.