# PR #39 RR1 Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the three verified RR1 review defects—upper-mirror audit incompleteness, incorrect range-qualified reporting, and invalid paired bootstrap logic—without changing any frozen RR1 strategy rule, then rerun the exact experiment and republish the evidence package.

**Architecture:** Keep all eligibility, signal, entry, stop, target, lockout, holding-period, friction and gate semantics unchanged. Strengthen only the independent audit/reporting layers: make the upper mirror audit independently recompute the same range/ER/liquidity qualification used by the lower cohort, report the qualified-range funnel from the existing candidate table correctly, and bootstrap the lower-minus-upper mean difference as two independent cohorts rather than artificial row pairs. Finish by rerunning the unchanged RR1 validation and accepting whatever formal verdict the frozen gates produce.

**Tech Stack:** Python 3, pandas, numpy, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-31-rr1-objective-range-sweep-reversion-design.md`

**Original implementation plan:** `Swing Trading/docs/superpowers/plans/2026-08-31-rr1-objective-range-sweep-reversion-validation.md`

**PR:** https://github.com/krishna916/Financial/pull/39

**Review:** PR review `#5080626465`

## Global Constraints

- This is a **research-integrity/reporting remediation only**.
- Do not change `RANGE_LOOKBACK = 60`.
- Do not change `ER60_MAX = 0.25`.
- Do not change the ₹10 crore prior-20 median traded-value floor.
- Do not change lower signal `Low[T] < Range_Low` and `Close[T] > Range_Low`.
- Do not change upper mirror `High[T] > Range_High` and `Close[T] < Range_High`.
- Do not add/remove RSI, SMA, RS, sector, breadth, regime, volume, shock, candlestick, event/news, or gap filters.
- Do not change the `0.25 * ATR14` structural-stop buffer.
- Do not change the pre-signal midpoint target.
- Do not change `Initial_RR >= 2.0`.
- Do not change next-canonical-session Open execution.
- Do not change the cohort-local same-symbol lockout through scheduled `T+16 Open`.
- Do not change the 15-complete-session Lens A/Lens B horizon.
- Do not change base/stress/severe friction `0.004 / 0.006 / 0.008`.
- Do not change temporal split, sample sufficiency thresholds, or any PASS/FAIL gate.
- Do not tune the strategy in response to the current `FAIL` result.
- No Candidate 4 work, no new strategy family, no dashboard/platform refactor.
- Keep focused RR1 verification as the module gate; repository-wide collection has pre-existing unrelated import/test-namespace failures documented in PR #39.

## Files Expected to Change

```text
Swing Trading/research/swing/rr1_range_sweep_reversion/
├── audit_rr1_integrity.py
├── analyze_rr1_results.py
├── run_rr1_validation.py
├── tests/
│   ├── test_rr1_integrity.py
│   ├── test_rr1_analysis.py
│   └── test_rr1_end_to_end.py
└── output/
    ├── rr1_validation_summary.csv
    ├── rr1_bootstrap_summary.csv
    ├── rr1_integrity_audit.csv
    ├── rr1_validation_gates.csv
    ├── research_report.md
    └── other regenerated frozen-run evidence files
```

Do **not** change `constants.py`, `build_rr1_features.py`, `generate_rr1_signals.py`, or `simulate_rr1_outcomes.py` unless a test proves a remediation cannot be implemented without touching them. If such a need appears, stop and re-evaluate before changing methodology-bearing code.

---

### Task 1: Complete the upper-mirror independent integrity audit

**Files:**
- Modify: `Swing Trading/research/swing/rr1_range_sweep_reversion/audit_rr1_integrity.py`
- Modify: `Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_integrity.py`

**Interfaces:**
- Existing: `audit_upper_reference(reference, raw_prices, membership, sessions) -> list[dict[str, Any]]`
- No new eligibility helper may call `generate_rr1_signals.qualify_range_row`; the audit must remain independent.

- [ ] **Step 1: Add a deterministic valid upper-mirror fixture**

Add a helper that creates 80 canonical sessions where the prior 60 sessions are range-bound, liquid, and low-efficiency, and signal day sweeps above the prior high then closes back below it:

```python
def valid_upper_case():
    sessions = pd.bdate_range("2024-01-01", periods=80)
    close = np.array([105.0 + (i % 2) for i in range(len(sessions))], dtype=float)
    high = np.full(len(sessions), 110.0)
    low = np.full(len(sessions), 100.0)
    open_ = close.copy()
    volume = np.full(len(sessions), 2_000_000.0)
    signal_position = 61
    high[signal_position] = 111.0
    close[signal_position] = 105.0

    prices = pd.DataFrame({
        "Date": sessions,
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })
    membership = pd.DataFrame({
        "Symbol": ["AAA"],
        "Member_From": [sessions[0]],
        "Member_To": [sessions[-1]],
        "Downloadable": [True],
        "Yahoo_Ticker": ["AAA.NS"],
    })
    reference = pd.Series({
        "Reference_ID": "REFERENCE|UPPER|AAA|fixture",
        "Signal_ID": "UPPER|AAA|fixture",
        "Symbol": "AAA",
        "Signal_Date": sessions[signal_position],
        "Entry_Date": sessions[signal_position + 1],
        "Entry_Open": float(open_[signal_position + 1]),
        "Scheduled_Exit_Date": sessions[signal_position + 16],
    })
    return reference, prices, membership, sessions
```

- [ ] **Step 2: Write RED tests for the three missing audit dimensions**

```python
def _failed_checks(rows):
    return {row["Check"] for row in rows if not row["Passed"]}


def test_upper_audit_rejects_non_range_structure():
    reference, prices, membership, sessions = valid_upper_case()
    signal_pos = sessions.get_loc(reference.Signal_Date)
    prices.loc[signal_pos - 60:signal_pos - 1, "Low"] = 110.0
    rows = audit_upper_reference(reference, prices, membership, sessions)
    assert "UPPER_RANGE_QUALIFICATION" in _failed_checks(rows)


def test_upper_audit_rejects_er60_above_threshold():
    reference, prices, membership, sessions = valid_upper_case()
    signal_pos = sessions.get_loc(reference.Signal_Date)
    prices.loc[signal_pos - 61:signal_pos - 1, "Close"] = np.linspace(100.0, 160.0, 61)
    rows = audit_upper_reference(reference, prices, membership, sessions)
    assert "UPPER_ER60_QUALIFICATION" in _failed_checks(rows)


def test_upper_audit_rejects_insufficient_liquidity():
    reference, prices, membership, sessions = valid_upper_case()
    signal_pos = sessions.get_loc(reference.Signal_Date)
    prices.loc[signal_pos - 20:signal_pos - 1, "Volume"] = 1_000.0
    rows = audit_upper_reference(reference, prices, membership, sessions)
    assert "UPPER_LIQUIDITY_QUALIFICATION" in _failed_checks(rows)
```

- [ ] **Step 3: Run the three tests and verify RED**

```bash
python -m pytest -q \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_integrity.py::test_upper_audit_rejects_non_range_structure" \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_integrity.py::test_upper_audit_rejects_er60_above_threshold" \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_integrity.py::test_upper_audit_rejects_insufficient_liquidity"
```

Expected: FAIL because `audit_upper_reference()` does not yet emit those checks.

- [ ] **Step 4: Independently recompute upper range, ER60, and liquidity**

Inside `audit_upper_reference()` after exact-history validation and before timing checks, recompute from `aligned` only:

```python
prior = aligned.iloc[position - 60:position]
range_low = float(prior["Low"].min())
range_high = float(prior["High"].max())
range_ok = np.isfinite(range_low) and np.isfinite(range_high) and range_high > range_low
checks.append(_record(
    entity,
    "UPPER_RANGE_QUALIFICATION",
    range_ok,
    [range_low, range_high],
    "finite Range_High > Range_Low from T-60..T-1",
))

close = aligned["Close"]
numerator = abs(float(close.iloc[position - 1]) - float(close.iloc[position - 61]))
denominator = float(close.iloc[position - 61:position].diff().abs().iloc[1:].sum())
er60 = numerator / denominator if denominator > 0.0 else np.nan
checks.append(_record(
    entity,
    "UPPER_ER60_QUALIFICATION",
    np.isfinite(er60) and denominator > 0.0 and er60 <= ER60_MAX,
    er60,
    f"ER60 <= {ER60_MAX}",
))

traded_value = aligned["Close"] * aligned["Volume"]
liquidity = float(traded_value.iloc[position - 20:position].median())
checks.append(_record(
    entity,
    "UPPER_LIQUIDITY_QUALIFICATION",
    np.isfinite(liquidity) and liquidity >= LIQUIDITY_FLOOR,
    liquidity,
    f">= {LIQUIDITY_FLOOR}",
))
```

Then keep the upper signal check against the independently recomputed `range_high`:

```python
upper_signal = (
    range_ok
    and float(signal_bar["High"]) > range_high
    and float(signal_bar["Close"]) < range_high
)
```

- [ ] **Step 5: Verify GREEN and existing integrity tests**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_integrity.py"
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/audit_rr1_integrity.py" \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_integrity.py"
git commit -m "research: complete RR1 upper mirror integrity audit"
```

---

### Task 2: Correct the range-qualified funnel/reporting count

**Files:**
- Modify: `Swing Trading/research/swing/rr1_range_sweep_reversion/run_rr1_validation.py`
- Modify: `Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_end_to_end.py`

**Interfaces:**
- Add: `_range_qualified_count(candidates: pd.DataFrame) -> int`
- Existing `rr1_range_candidates.csv` remains the broader candidate/funnel table and retains `Range_Eligibility_Reason`.

- [ ] **Step 1: Write a RED unit test for the reporting helper**

```python
def test_range_qualified_count_uses_only_qualified_rows():
    candidates = pd.DataFrame({
        "Range_Eligibility_Reason": [
            "QUALIFIED_RANGE",
            "ER60_ABOVE_MAX",
            "LOW_LIQUIDITY",
            "QUALIFIED_RANGE",
        ]
    })
    assert _range_qualified_count(candidates) == 2
```

Import `_range_qualified_count` from `run_rr1_validation` in the test module.

- [ ] **Step 2: Run RED test**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_end_to_end.py::test_range_qualified_count_uses_only_qualified_rows"
```

Expected: FAIL because the helper does not exist.

- [ ] **Step 3: Implement the single-source reporting helper**

```python
def _range_qualified_count(candidates: pd.DataFrame) -> int:
    if "Range_Eligibility_Reason" not in candidates.columns:
        raise ValueError("candidates missing Range_Eligibility_Reason")
    return int(candidates["Range_Eligibility_Reason"].astype(str).eq("QUALIFIED_RANGE").sum())
```

In `run_validation()` compute once:

```python
range_qualified_count = _range_qualified_count(candidates)
```

Pass that exact value to `_analysis_evidence(...)` and write it into `rr1_validation_summary.csv`:

```python
{"Metric": "Range_Qualified_Sessions", "Value": range_qualified_count}
```

Do not change signal qualification or the contents of `lower_signals` / `upper_signals`.

- [ ] **Step 4: Add an end-to-end assertion that reporting matches the candidate reasons**

In the existing injected-data end-to-end test, after the run:

```python
candidates = pd.read_csv(output_dir / "rr1_range_candidates.csv")
summary = pd.read_csv(output_dir / "rr1_validation_summary.csv")
reported = int(summary.loc[
    summary["Metric"].eq("Range_Qualified_Sessions"), "Value"
].iloc[0])
expected = int(candidates["Range_Eligibility_Reason"].eq("QUALIFIED_RANGE").sum())
assert reported == expected
```

- [ ] **Step 5: Verify Task 2 GREEN**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_end_to_end.py"
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/run_rr1_validation.py" \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_end_to_end.py"
git commit -m "research: fix RR1 range-qualified funnel reporting"
```

---

### Task 3: Replace artificial paired bootstrap with independent two-cohort resampling

**Files:**
- Modify: `Swing Trading/research/swing/rr1_range_sweep_reversion/analyze_rr1_results.py`
- Modify: `Swing Trading/research/swing/rr1_range_sweep_reversion/run_rr1_validation.py`
- Modify: `Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_analysis.py`

**Interfaces:**
- Add: `bootstrap_mean_difference_ci(lower, upper, seed=BOOTSTRAP_SEED, resamples=BOOTSTRAP_RESAMPLES) -> tuple[float, float]`
- Existing `bootstrap_mean_ci()` remains for one-sample metrics.

- [ ] **Step 1: Write a RED deterministic bootstrap-difference test**

```python
def test_bootstrap_mean_difference_resamples_independent_cohorts():
    lower = np.array([0.10, 0.20, 0.30])
    upper = np.array([-0.20, -0.10])

    observed = bootstrap_mean_difference_ci(lower, upper, seed=7, resamples=500)

    rng = np.random.default_rng(7)
    diffs = np.empty(500)
    for i in range(500):
        lower_star = rng.choice(lower, size=len(lower), replace=True)
        upper_star = rng.choice(upper, size=len(upper), replace=True)
        diffs[i] = lower_star.mean() - upper_star.mean()
    expected = tuple(np.quantile(diffs, [0.025, 0.975]))

    assert observed == pytest.approx(expected)
```

- [ ] **Step 2: Run RED test**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_analysis.py::test_bootstrap_mean_difference_resamples_independent_cohorts"
```

Expected: FAIL because the helper does not exist.

- [ ] **Step 3: Implement independent bootstrap difference**

```python
def bootstrap_mean_difference_ci(
    lower: np.ndarray | Iterable[object],
    upper: np.ndarray | Iterable[object],
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> tuple[float, float]:
    lower_x = _numeric(lower)
    upper_x = _numeric(upper)
    lower_x = lower_x[np.isfinite(lower_x)]
    upper_x = upper_x[np.isfinite(upper_x)]
    if len(lower_x) == 0 or len(upper_x) == 0:
        return float("nan"), float("nan")

    rng = np.random.default_rng(seed)
    differences = np.empty(resamples, dtype=float)
    for index in range(resamples):
        lower_star = rng.choice(lower_x, size=len(lower_x), replace=True)
        upper_star = rng.choice(upper_x, size=len(upper_x), replace=True)
        differences[index] = lower_star.mean() - upper_star.mean()
    return tuple(np.quantile(differences, [0.025, 0.975]))
```

- [ ] **Step 4: Replace the current row-wise lower-minus-upper bootstrap path**

In `_bootstrap_summary()` remove this logic entirely:

```python
n = min(len(lens_a), len(upper))
lens_a["Gross_Return"].iloc[:n].to_numpy() - upper["Mirror_Gross_Return_15"].iloc[:n].to_numpy()
```

Instead append the lower-vs-upper metric separately and compute its CI using the new helper:

```python
lower_values = pd.to_numeric(lens_a["Gross_Return"], errors="coerce").dropna().to_numpy()
upper_values = pd.to_numeric(upper["Mirror_Gross_Return_15"], errors="coerce").dropna().to_numpy()
ci_low, ci_high = bootstrap_mean_difference_ci(
    lower_values,
    upper_values,
    seed=BOOTSTRAP_SEED + 4,
    resamples=BOOTSTRAP_RESAMPLES,
)
rows.append({
    "Metric": "LOWER_MINUS_UPPER_GROSS_15_RETURN",
    "Count": f"lower={len(lower_values)};upper={len(upper_values)}",
    "Mean": float(lower_values.mean() - upper_values.mean())
        if len(lower_values) and len(upper_values) else np.nan,
    "CI_Lower_95": ci_low,
    "CI_Upper_95": ci_high,
    "Seed": BOOTSTRAP_SEED + 4,
    "Resamples": BOOTSTRAP_RESAMPLES,
})
```

If the current `Count` column is expected to stay numeric by downstream consumers, use two explicit columns instead:

```text
Lower_Count
Upper_Count
```

and populate `Count` with `len(lower_values) + len(upper_values)` only for backward compatibility. Pick one schema and update the test/report consistently; do not encode false matched-pair semantics.

- [ ] **Step 5: Add a regression assertion that unequal cohort lengths are retained**

```python
def test_bootstrap_summary_keeps_full_unequal_lower_and_upper_samples():
    lens_a = pd.DataFrame({"Gross_Return": [0.1, 0.2, 0.3]})
    practical = pd.DataFrame({"Base_Net_R": [0.1], "Base_Practical_Excess_Return": [0.01]})
    upper = pd.DataFrame({"Mirror_Gross_Return_15": [-0.1, -0.2]})

    summary = _bootstrap_summary(lens_a, practical, upper)
    row = summary.loc[summary["Metric"].eq("LOWER_MINUS_UPPER_GROSS_15_RETURN")].iloc[0]
    assert row["Mean"] == pytest.approx(0.2 - (-0.15))
```

If `_bootstrap_summary` stays private in `run_rr1_validation.py`, place this test in `test_rr1_end_to_end.py` and import it there. Do not duplicate production bootstrap math in a second implementation.

- [ ] **Step 6: Verify Task 3 GREEN**

```bash
python -m pytest -q \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_analysis.py" \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_end_to_end.py"
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/analyze_rr1_results.py" \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/run_rr1_validation.py" \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_analysis.py" \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_end_to_end.py"
git commit -m "research: fix RR1 independent-cohort bootstrap"
```

---

### Task 4: Run the complete focused RR1 verification before touching formal evidence

**Files:**
- No production changes expected.

- [ ] **Step 1: Run the entire focused RR1 suite**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests"
```

Expected: zero failures. Record the exact pass count in the PR comment; do not reuse the old `34 passed` claim if the new tests change the count.

- [ ] **Step 2: Review the diff for forbidden methodology changes**

```bash
git diff master...HEAD -- \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/constants.py" \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/build_rr1_features.py" \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/generate_rr1_signals.py" \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/simulate_rr1_outcomes.py"
```

Expected for this remediation: no new changes to these methodology-bearing files beyond what was already present in PR #39 before remediation. If any new change appears, inspect it and revert unless strictly required by a failing remediation test.

- [ ] **Step 3: Confirm frozen constants remain exact**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests/test_rr1_features.py::test_frozen_rr1_constants"
```

Expected: PASS.

---

### Task 5: Rerun the exact frozen RR1 experiment and republish evidence

**Files:**
- Regenerate: `Swing Trading/research/swing/rr1_range_sweep_reversion/output/*`
- Modify only if regenerated automatically: `research_report.md` and CSV evidence artifacts.

- [ ] **Step 1: Run the unchanged formal validator**

From repository root:

```bash
python "Swing Trading/research/swing/rr1_range_sweep_reversion/run_rr1_validation.py"
```

Interpretation rules:

```text
INVALID_RESEARCH_RUN -> stop; do not interpret profitability
INSUFFICIENT_EVIDENCE -> stop at that formal verdict
PASS -> accept PASS; do not add filters
FAIL -> accept FAIL; do not rescue
```

Do **not** code an assertion that the result must remain `FAIL`; the frozen gate engine decides the status from the corrected evidence.

- [ ] **Step 2: Verify the corrected audit evidence**

```bash
python - <<'PY'
import pandas as pd
p = "Swing Trading/research/swing/rr1_range_sweep_reversion/output/rr1_integrity_audit.csv"
df = pd.read_csv(p)
print("rows", len(df))
print("failures", int((~df["Passed"].astype(bool)).sum()))
print(sorted(set(df.loc[df["Entity"].astype(str).str.startswith("REFERENCE|UPPER"), "Check"])))
PY
```

Expected:
- `failures == 0` for an interpretable run;
- upper-reference checks include `UPPER_RANGE_QUALIFICATION`, `UPPER_ER60_QUALIFICATION`, and `UPPER_LIQUIDITY_QUALIFICATION`.

- [ ] **Step 3: Verify the corrected range-qualified summary**

```bash
python - <<'PY'
import pandas as pd
base = "Swing Trading/research/swing/rr1_range_sweep_reversion/output"
c = pd.read_csv(f"{base}/rr1_range_candidates.csv")
s = pd.read_csv(f"{base}/rr1_validation_summary.csv")
expected = int(c["Range_Eligibility_Reason"].eq("QUALIFIED_RANGE").sum())
reported = int(float(s.loc[s["Metric"].eq("Range_Qualified_Sessions"), "Value"].iloc[0]))
print("expected", expected, "reported", reported)
assert reported == expected
PY
```

Expected: assertion passes.

- [ ] **Step 4: Verify bootstrap evidence no longer implies matched pairs**

Inspect:

```bash
python - <<'PY'
import pandas as pd
p = "Swing Trading/research/swing/rr1_range_sweep_reversion/output/rr1_bootstrap_summary.csv"
df = pd.read_csv(p)
print(df.loc[df["Metric"].eq("LOWER_MINUS_UPPER_GROSS_15_RETURN")].to_string(index=False))
PY
```

Confirm the mean equals `mean(all completed lower gross returns) - mean(all completed upper gross returns)` and the CI comes from independent resampling of each full cohort.

- [ ] **Step 5: Verify formal gate/status artifacts are internally consistent**

```bash
python - <<'PY'
import pandas as pd
base = "Swing Trading/research/swing/rr1_range_sweep_reversion/output"
gates = pd.read_csv(f"{base}/rr1_validation_gates.csv")
summary = pd.read_csv(f"{base}/rr1_validation_summary.csv")
status = summary.loc[summary["Metric"].eq("FINAL_STATUS"), "Value"].iloc[0]
print("FINAL_STATUS:", status)
print(gates.to_string(index=False))
assert status in {"PASS", "FAIL", "INSUFFICIENT_EVIDENCE", "INVALID_RESEARCH_RUN"}
PY
```

If `RESEARCH_VALIDITY=False`, formal status must be `INVALID_RESEARCH_RUN`. If validity passes but sample sufficiency fails, status must be `INSUFFICIENT_EVIDENCE`.

- [ ] **Step 6: Rerun focused tests after evidence publication**

```bash
python -m pytest -q "Swing Trading/research/swing/rr1_range_sweep_reversion/tests"
```

Expected: zero failures.

- [ ] **Step 7: Commit regenerated evidence**

```bash
git add \
  "Swing Trading/research/swing/rr1_range_sweep_reversion/output"
git commit -m "research: republish corrected RR1 validation evidence"
```

---

### Task 6: Update PR #39 with verification evidence

**Files:**
- GitHub PR comment only.

- [ ] **Step 1: Post a concise remediation summary to PR #39**

Include:

```text
Implemented review remediation plan:
- upper mirror audit independently recomputes range/ER60/liquidity;
- Range_Qualified_Sessions now counts only QUALIFIED_RANGE rows;
- lower-minus-upper bootstrap uses independent full-cohort resampling;
- no RR1 strategy parameter/filter/gate changed.

Verification:
- focused RR1 pytest: <fresh exact count> passed
- integrity audit: <fresh row count>, 0 failures (if valid)
- FINAL_STATUS: <fresh formal result>
```

Also link this plan file.

- [ ] **Step 2: Do not merge as part of plan execution**

Stop after pushing the fixes/evidence and updating the PR. A fresh review should decide merge readiness.

---

## Self-Review Checklist

Before declaring the remediation complete, verify all are true:

```text
[ ] Upper mirror audit independently checks PIT, exact history, valid range, ER60 <= 0.25,
    liquidity >= ₹10 crore, upper sweep/rejection, next-session timing, lockout/accounting,
    and T+16 timing.
[ ] Range_Qualified_Sessions equals rows whose Range_Eligibility_Reason == QUALIFIED_RANGE.
[ ] Lower/upper signal-generation logic is unchanged.
[ ] Lower/upper trade/reference accounting logic is unchanged.
[ ] Bootstrap lower-minus-upper CI uses independent resampling, not row pairing/truncation.
[ ] All frozen constants and gates are unchanged.
[ ] Focused RR1 tests pass with fresh evidence.
[ ] Formal validator reruns once unchanged after fixes.
[ ] Corrected evidence is committed.
[ ] PR receives the fresh test count, audit result, formal verdict, and plan link.
[ ] No post-result strategy rescue was introduced.
```

Execution must be inline with `superpowers:executing-plans`.