# M1 Regime-Gated Momentum Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one focused, auditable M1 validator that partitions the already-frozen V3 opportunity set by the independently predeclared M1 market regime and mechanically reports `PASS`, `FAIL`, `INSUFFICIENT_EVIDENCE`, or `INVALID_RESEARCH_RUN` without changing V3 or tuning M1 after outcomes.

**Architecture:** Add one new research module under `Swing Trading/research/swing/m1_regime_gated_momentum/`. The module must treat closed V3 artifacts as read-only stock-strategy evidence, recompute only the new M1 regime from existing PIT breadth + Nifty 500 index data, partition frozen V3 signals/entries/outcomes into enabled and disabled cohorts, apply M1 friction/robustness/gates, and write a concise evidence package. It must not download market data, rebuild V3 signals, modify V3 outputs, create a generic strategy framework, or add dashboards.

**Tech Stack:** Python 3, pandas, numpy, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-29-m1-regime-gated-momentum-resumption-design.md`

**Issue:** `https://github.com/krishna916/Financial/issues/23`

## Global Constraints

- Primary signal window: `2023-08-01` through `2026-08-25` inclusive.
- M1 changes only the market-regime partition; V3 stock setup, accepted/cancelled entry evidence, exits, and gross outcomes are frozen.
- Treat `Swing Trading/research/swing/strategy_v3_shallow_pullback/output/` as read-only.
- Never regenerate V3 from fresh Yahoo data inside M1.
- Never use the old persisted `STRONG_MOMENTUM` / `Momentum_Regime` / `Regime` labels as M1 eligibility.
- M1 `DATA_SAFE`: `SMA50_Denominator / active PIT Nifty500 members >= 0.80`.
- M1 `INDEX_TREND_OK`: `Nifty500 Close > SMA200` **and** `SMA50 > SMA200`.
- M1 `BREADTH_OK`: `Pct_Above_SMA50 >= 50.0`.
- `MOMENTUM_ENABLED = DATA_SAFE AND INDEX_TREND_OK AND BREADTH_OK`; otherwise disabled/cash.
- Regime context must be the exact `Signal_Date`; no backward/forward/as-of regime substitution.
- Disabled signals use frozen V3 accepted/cancelled evidence as the shadow-control entry result; no signal revival.
- Base friction `0.004`; stress friction `0.006`; severe diagnostic `0.008`.
- Sample sufficiency: at least `300` completed paired enabled trades.
- Temporal split by **Signal_Date**: first `2023-08-01..2025-02-11`, second `2025-02-12..2026-08-25`.
- No parameter tuning, rescue filters, alternative breadth thresholds, persistence rules, sector filters, stop changes, exit changes, or year selection after results.
- If M1 passes, stop signal-family research and move to portfolio/execution finalization.
- If M1 fails, close it and move to Candidate 2; do not rescue M1.

## File Map

```text
Swing Trading/research/swing/m1_regime_gated_momentum/
├── README.md
├── load_frozen_sources.py
├── build_m1_regime.py
├── partition_m1_cohorts.py
├── analyze_m1_results.py
├── run_m1_validation.py
├── tests/
│   ├── test_m1_sources.py
│   ├── test_m1_regime.py
│   ├── test_m1_partition.py
│   ├── test_m1_analysis.py
│   └── test_m1_end_to_end.py
└── output/
    ├── m1_source_integrity.csv
    ├── m1_regime_daily.csv
    ├── m1_signal_partition.csv
    ├── m1_enabled_entries.csv
    ├── m1_enabled_cancellations.csv
    ├── m1_disabled_shadow_entries.csv
    ├── m1_disabled_shadow_cancellations.csv
    ├── m1_enabled_setup_trades.csv
    ├── m1_enabled_practical_trades.csv
    ├── m1_disabled_setup_control.csv
    ├── m1_disabled_practical_control.csv
    ├── m1_validation_summary.csv
    ├── m1_regime_comparison.csv
    ├── m1_temporal_summary.csv
    ├── m1_year_summary.csv
    ├── m1_outlier_robustness.csv
    ├── m1_leave_one_symbol_out.csv
    ├── m1_overlap_diagnostic.csv
    ├── m1_integrity_audit.csv
    ├── m1_validation_gates.csv
    └── research_report.md
```

Do not create a downloader, feature cache, strategy engine, dashboard, notebook, or generic reusable backtest framework.

---

### Task 1: Load and validate frozen V3 + market source artifacts

**Files:**
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/load_frozen_sources.py`
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_sources.py`

**Interfaces:**

```python
V3_OUTPUT_ROOT: Path
BREADTH_PATH: Path
INDEX_PATH: Path
MEMBERSHIP_PATH: Path

load_required_csv(path: Path, required_columns: tuple[str, ...], parse_dates: tuple[str, ...] = ()) -> pd.DataFrame
load_v3_artifacts(v3_output_root: Path = V3_OUTPUT_ROOT) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]
load_market_sources(...) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]
validate_frozen_v3_accounting(artifacts: dict[str, pd.DataFrame]) -> pd.DataFrame
```

Required frozen V3 artifacts:

```text
v3_signal_candidates.csv
v3_entries.csv
v3_entry_cancellations.csv
v3_setup_quality_trades.csv
v3_practical_trades.csv
v3_validation_gates.csv
```

Minimum required columns:

```python
V3_REQUIRED_COLUMNS = {
    "v3_signal_candidates.csv": ("Entry_ID", "Symbol", "Signal_Date", "Signal_Qualified"),
    "v3_entries.csv": ("Entry_ID", "Symbol", "Signal_Date", "Entry_Date", "Entry_Open", "Structural_Stop", "Initial_Risk"),
    "v3_entry_cancellations.csv": ("Entry_ID", "Symbol", "Signal_Date", "Cancellation_Reason"),
    "v3_setup_quality_trades.csv": ("Entry_ID", "Symbol", "Signal_Date", "Entry_Date", "Entry_Open", "Structural_Stop", "Initial_Risk", "Exit_Date", "Exit_Price", "Return"),
    "v3_practical_trades.csv": ("Entry_ID", "Symbol", "Signal_Date", "Entry_Date", "Entry_Open", "Structural_Stop", "Initial_Risk", "Exit_Date", "Exit_Price", "R_Multiple"),
    "v3_validation_gates.csv": ("Gate", "Passed", "Value", "Status"),
}
```

Market sources:

```text
Swing Trading/research/swing/market_breadth/output/nifty500_breadth_daily.csv
Swing Trading/nifty500_regime_daily.csv
Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv
```

- [ ] **Step 1: Write failing artifact-loader tests**

Add tests proving:

```python
def test_missing_required_v3_artifact_records_integrity_violation(tmp_path): ...
def test_missing_required_column_records_integrity_violation(tmp_path): ...
def test_v3_point_in_time_gate_must_already_pass(): ...
def test_frozen_v3_accounting_reconciles_qualified_accepted_cancelled_and_completed(): ...
```

`v3_validation_gates.csv` must contain `POINT_IN_TIME_INTEGRITY` with `Passed=True`. Missing/false is an integrity violation.

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_sources.py"
```

Expected: FAIL because loader/validation functions do not exist.

- [ ] **Step 3: Implement minimal source loader and source-integrity audit**

Use explicit violation rows:

```text
Entry_ID,Symbol,Violation,Observed,Expected
```

At minimum support:

```text
MISSING_REQUIRED_ARTIFACT
INVALID_REQUIRED_ARTIFACT
V3_PIT_INTEGRITY_NOT_CLEAN
V3_QUALIFIED_ACCOUNTING_MISMATCH
V3_COMPLETED_PAIR_MISMATCH
DUPLICATE_ENTRY_ID
```

Qualified V3 signals are rows with `Signal_Qualified == True` after robust bool parsing.

Required source invariants:

```text
qualified Entry_ID count = accepted entries + cancellations
accepted Entry_ID set ∩ cancellation Entry_ID set = empty
setup completed Entry_ID set = practical completed Entry_ID set
completed Entry_ID set ⊆ accepted Entry_ID set
```

Do not interpret M1 performance if source-integrity rows exist.

- [ ] **Step 4: Run tests and make them pass**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_sources.py"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/m1_regime_gated_momentum"
git commit -m "research: load frozen M1 source evidence"
```

---

### Task 2: Recompute the independent M1 regime exactly on signal dates

**Files:**
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/build_m1_regime.py`
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_regime.py`

**Interfaces:**

```python
MIN_BREADTH_COVERAGE = 0.80
MIN_PCT_ABOVE_SMA50 = 50.0

active_member_count_on(membership: pd.DataFrame, date: pd.Timestamp) -> int
build_m1_regime(breadth: pd.DataFrame, index_daily: pd.DataFrame, membership: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]
attach_exact_signal_regime(signals: pd.DataFrame, regime_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]
```

`m1_regime_daily.csv` columns:

```text
Date
Active_PIT_Member_Count
SMA50_Denominator
SMA50_Breadth_Coverage
Pct_Above_SMA50
Nifty500_Close
Nifty500_SMA50
Nifty500_SMA200
DATA_SAFE
INDEX_TREND_OK
BREADTH_OK
M1_Regime
```

- [ ] **Step 1: Write exact threshold/timing tests**

Add deterministic tests:

```python
def test_coverage_exactly_point_80_is_safe(): ...
def test_breadth_exactly_50_is_ok(): ...
def test_index_requires_both_close_and_sma50_above_sma200(): ...
def test_old_strong_momentum_label_is_ignored(): ...
def test_signal_regime_join_requires_exact_same_date(): ...
def test_membership_denominator_is_recomputed_from_pit_intervals(): ...
```

The old-label trap test must deliberately set source `Regime="STRONG_MOMENTUM"` while M1 conditions are false and assert `M1_Regime == "MOMENTUM_DISABLED"`.

The exact-date test must prove a missing same-day regime row produces an integrity violation rather than using prior/future data.

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_regime.py"
```

- [ ] **Step 3: Implement the frozen rule**

```python
coverage = sma50_denominator / active_member_count

data_safe = coverage >= 0.80
index_trend_ok = close > sma200 and sma50 > sma200
breadth_ok = pct_above_sma50 >= 50.0
m1_regime = "MOMENTUM_ENABLED" if data_safe and index_trend_ok and breadth_ok else "MOMENTUM_DISABLED"
```

Use `Close`, `SMA50`, `SMA200` from `Swing Trading/nifty500_regime_daily.csv`; do not use the old index `Regime` field.

Cross-check `Active_PIT_Member_Count` against breadth `Universe_Member_Count`/`Member_Count` where available. Mismatch is `BREADTH_PIT_DENOMINATOR_MISMATCH`.

- [ ] **Step 4: Run tests and make them pass**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_regime.py"
```

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/m1_regime_gated_momentum"
git commit -m "research: compute predeclared M1 market regime"
```

---

### Task 3: Partition frozen V3 evidence into enabled and disabled cohorts

**Files:**
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/partition_m1_cohorts.py`
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_partition.py`

**Interfaces:**

```python
partition_signals(qualified_signals: pd.DataFrame, signal_regime: pd.DataFrame) -> pd.DataFrame
partition_v3_evidence(partition: pd.DataFrame, artifacts: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]
```

`m1_signal_partition.csv` must retain at least:

```text
Entry_ID,Symbol,Signal_Date,M1_Regime,DATA_SAFE,INDEX_TREND_OK,BREADTH_OK,SMA50_Breadth_Coverage,Pct_Above_SMA50,Nifty500_Close,Nifty500_SMA50,Nifty500_SMA200,V3_Entry_Status,V3_Cancellation_Reason
```

- [ ] **Step 1: Write partition/accounting tests**

Add tests proving:

```python
def test_every_qualified_signal_is_partitioned_exactly_once(): ...
def test_enabled_and_disabled_sets_do_not_overlap(): ...
def test_partition_preserves_frozen_v3_accepted_and_cancelled_sets(): ...
def test_disabled_control_uses_frozen_v3_cancellation_instead_of_creating_trade(): ...
def test_completed_enabled_plus_disabled_equals_frozen_completed_sample(): ...
def test_incomplete_accepted_entry_is_not_promoted_to_completed_control(): ...
```

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_partition.py"
```

- [ ] **Step 3: Implement exact artifact partitioning**

Rules:

```text
qualified signal + enabled + V3 accepted -> enabled entry
qualified signal + enabled + V3 cancelled -> enabled cancellation
qualified signal + disabled + V3 accepted -> disabled shadow entry
qualified signal + disabled + V3 cancelled -> disabled shadow cancellation
```

Completed outcomes are selected only from frozen V3 setup/practical files by `Entry_ID`.

Required invariants after partition:

```text
enabled qualified + disabled qualified = frozen qualified
enabled accepted ∪ disabled shadow accepted = frozen accepted
enabled cancelled ∪ disabled shadow cancelled = frozen cancelled
enabled completed ∪ disabled completed = frozen completed
```

All unions must be disjoint and exact.

- [ ] **Step 4: Run tests and make them pass**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_partition.py"
```

- [ ] **Step 5: Commit**

```bash
git add "Swing Trading/research/swing/m1_regime_gated_momentum"
git commit -m "research: partition frozen V3 evidence by M1 regime"
```

---

### Task 4: Apply friction and compute enabled/control metrics

**Files:**
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/analyze_m1_results.py`
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_analysis.py`

**Interfaces:**

```python
BASE_FRICTION = 0.004
STRESS_FRICTION = 0.006
SEVERE_FRICTION = 0.008
FIRST_HALF_END = pd.Timestamp("2025-02-11")
SECOND_HALF_START = pd.Timestamp("2025-02-12")

safe_profit_factor(values: pd.Series) -> float
add_setup_friction(trades: pd.DataFrame) -> pd.DataFrame
add_practical_friction(trades: pd.DataFrame) -> pd.DataFrame
summarize_setup(trades: pd.DataFrame, prefix: str) -> dict[str, float]
summarize_practical(trades: pd.DataFrame, prefix: str) -> dict[str, float]
regime_comparison(enabled: pd.DataFrame, disabled: pd.DataFrame) -> pd.DataFrame
temporal_summary(enabled_practical: pd.DataFrame) -> pd.DataFrame
year_summary(enabled_practical: pd.DataFrame) -> pd.DataFrame
```

- [ ] **Step 1: Write arithmetic and metric tests**

Use literal fixtures to prove:

```python
def test_setup_friction_is_gross_return_minus_round_trip_cost(): ...
def test_practical_net_r_uses_entry_price_cost_over_initial_risk(): ...
def test_initial_risk_is_recomputed_and_matches_frozen_value(): ...
def test_gross_r_recomputes_to_frozen_r_multiple(): ...
def test_profit_factor_handles_no_loss_and_no_win_cases(): ...
def test_temporal_split_uses_signal_date_not_entry_date(): ...
def test_enabled_and_disabled_receive_identical_friction_formula(): ...
```

Use `np.isclose(..., rtol=1e-9, atol=1e-12)` for persisted-vs-recomputed numeric evidence.

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_analysis.py" -k "friction or temporal or profit"
```

- [ ] **Step 3: Implement frozen friction fields**

Setup:

```python
Base_Net_Return = Return - 0.004
Stress_Net_Return = Return - 0.006
Severe_Net_Return = Return - 0.008
```

Practical:

```python
Initial_Risk_Recomputed = Entry_Open - Structural_Stop
Gross_R_Recomputed = (Exit_Price - Entry_Open) / Initial_Risk_Recomputed
Base_Net_R = ((Exit_Price - Entry_Open) - 0.004 * Entry_Open) / Initial_Risk_Recomputed
Stress_Net_R = ((Exit_Price - Entry_Open) - 0.006 * Entry_Open) / Initial_Risk_Recomputed
Severe_Net_R = ((Exit_Price - Entry_Open) - 0.008 * Entry_Open) / Initial_Risk_Recomputed
```

Mismatch against frozen `Initial_Risk` or `R_Multiple` is an integrity violation, not a silent overwrite.

- [ ] **Step 4: Produce base summary/comparison/temporal/year functions and tests**

Required comparison fields:

```text
Enabled_Completed
Disabled_Completed
Enabled_Base_Mean_Net_R
Disabled_Base_Mean_Net_R
Enabled_Base_R_PF
Disabled_Base_R_PF
Enabled_Beats_Disabled_Mean
Enabled_Beats_Disabled_R_PF
```

Temporal halves use `Signal_Date` exactly.

- [ ] **Step 5: Run tests and make them pass**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_analysis.py"
```

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/m1_regime_gated_momentum"
git commit -m "research: calculate M1 friction and cohort metrics"
```

---

### Task 5: Add robustness, overlap diagnostics, frozen gates and status precedence

**Files:**
- Modify: `Swing Trading/research/swing/m1_regime_gated_momentum/analyze_m1_results.py`
- Modify: `Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_analysis.py`

**Interfaces:**

```python
top_five_robustness(enabled_practical: pd.DataFrame) -> pd.DataFrame
leave_one_symbol_out(enabled_practical: pd.DataFrame) -> pd.DataFrame
overlap_diagnostic(enabled_entries: pd.DataFrame, enabled_practical: pd.DataFrame) -> pd.DataFrame
evaluate_gates(...) -> tuple[str, pd.DataFrame]
```

- [ ] **Step 1: Write robustness/status tests**

Add tests proving:

```python
def test_top_five_removes_largest_gross_r_not_net_r(): ...
def test_loso_requires_every_omitted_symbol_sample_to_remain_positive(): ...
def test_sample_below_300_is_insufficient(): ...
def test_any_integrity_violation_overrides_insufficient_and_fail(): ...
def test_all_mandatory_gates_pass_returns_pass(): ...
def test_valid_sufficient_single_gate_failure_returns_fail(): ...
def test_diagnostics_do_not_create_mandatory_gate_rows(): ...
```

- [ ] **Step 2: Implement frozen mandatory gate table**

Use these exact gates:

```text
INTEGRITY_ZERO                       == 0
SAMPLE_SUFFICIENCY                   >= 300
BASE_SETUP_MEAN                      > 0
BASE_SETUP_PF                        >= 1.20
BASE_PRACTICAL_MEAN_R                >= 0.15
BASE_PRACTICAL_R_PF                  >= 1.20
STRESS_PRACTICAL_MEAN_R              > 0
STRESS_PRACTICAL_R_PF                > 1.00
REGIME_MEAN_DISCRIMINATION           enabled > disabled
REGIME_RPF_DISCRIMINATION            enabled > disabled
TEMPORAL_FIRST_MEAN_R                > 0
TEMPORAL_FIRST_R_PF                  > 1.00
TEMPORAL_SECOND_MEAN_R               > 0
TEMPORAL_SECOND_R_PF                 > 1.00
TOP_FIVE_REMOVED_MEAN_R              > 0
TOP_FIVE_REMOVED_R_PF                > 1.00
LOSO_ALL_MEAN_R                      > 0 for every symbol omission
LOSO_ALL_R_PF                        > 1.00 for every symbol omission
```

Status precedence:

```text
if integrity violations > 0:
    INVALID_RESEARCH_RUN
elif completed enabled paired trades < 300 or disabled comparison unavailable:
    INSUFFICIENT_EVIDENCE
elif every mandatory strategy gate passes:
    PASS
else:
    FAIL
```

- [ ] **Step 3: Implement top-five and LOSO exactly**

Top-five ranking column is frozen gross `R_Multiple` / recomputed gross R.

LOSO loops every symbol present in the enabled completed practical sample and calculates base-net mean R + base-net R-PF after omitting all that symbol's trades.

- [ ] **Step 4: Implement minimal overlap diagnostic**

Diagnostic only; do not gate M1 on portfolio capacity yet.

Report at minimum:

```text
Enabled_Accepted_Entries
Enabled_Completed_Trades
Max_Same_Day_Entries
Average_Same_Day_Entries_On_Active_Days
Median_Initial_Risk_Fraction
Median_Implied_Position_Weight_At_1Pct_Risk
Max_Implied_Position_Weight_At_1Pct_Risk
```

Where:

```python
Risk_Fraction = Initial_Risk / Entry_Open
Implied_Position_Weight = 0.01 / Risk_Fraction
```

No cap, ranking, or portfolio selection is introduced here.

- [ ] **Step 5: Run tests and make them pass**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_analysis.py"
```

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/m1_regime_gated_momentum"
git commit -m "research: add frozen M1 validation gates"
```

---

### Task 6: Build the one-command evidence run, report, and regression verification

**Files:**
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/run_m1_validation.py`
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/README.md`
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_end_to_end.py`
- Generate: all `output/` artifacts listed in the File Map

**Interfaces:**

```python
run_validation() -> tuple[str, pd.DataFrame]
write_research_report(...) -> None
```

- [ ] **Step 1: Write synthetic end-to-end tests**

At minimum:

```python
def test_end_to_end_missing_source_is_invalid(tmp_path): ...
def test_end_to_end_valid_insufficient_sample_is_insufficient(tmp_path): ...
def test_end_to_end_valid_sufficient_losing_sample_is_fail(tmp_path): ...
def test_end_to_end_valid_all_gates_pass_is_pass(tmp_path): ...
```

The synthetic tests must not read live/network data.

- [ ] **Step 2: Implement orchestration in this exact order**

```text
1. load frozen V3 sources
2. validate frozen V3 source accounting/PIT gate
3. load breadth/index/membership sources
4. build independent M1 daily regime
5. exact-date attach regime to all frozen qualified V3 signals
6. partition accepted/cancelled/completed evidence
7. recompute friction and integrity checks
8. calculate enabled/control metrics
9. calculate temporal/year/top-five/LOSO/overlap evidence
10. merge all integrity rows
11. evaluate frozen gates/status
12. write every required CSV + research_report.md
13. verify final required output package exists/readable
14. if final package verification adds violations, rewrite audit/gates/report as INVALID_RESEARCH_RUN
```

- [ ] **Step 3: Keep the report decision-focused**

`research_report.md` must contain only:

```text
1. Frozen hypothesis and regime rule
2. Frozen V3 source-evidence provenance/accounting
3. Regime coverage: enabled vs disabled days/signals
4. Enabled accepted/cancelled/completed counts
5. Disabled shadow accepted/cancelled/completed counts
6. Base/stress/severe setup + practical metrics
7. Enabled-vs-disabled discrimination
8. Fixed temporal halves + calendar-year diagnostics
9. Top-five and LOSO robustness
10. Overlap/capital diagnostic
11. Integrity audit count
12. Mandatory gate table
13. Formal final status
14. Explicit next action:
    PASS -> portfolio/execution validation
    FAIL -> close M1, Candidate 2
    INSUFFICIENT -> close/no loosening, Candidate 2
    INVALID -> fix only research integrity and rerun
```

Do not include rescue suggestions or alternate thresholds.

- [ ] **Step 4: Run focused M1 tests**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests"
```

Expected: zero failures.

- [ ] **Step 5: Run V3 regression tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests"
```

Expected: zero failures.

- [ ] **Step 6: Prove V3 evidence was not modified**

Before and after the M1 run:

```bash
git status --short -- "Swing Trading/research/swing/strategy_v3_shallow_pullback"
```

Expected: no output.

Also inspect the implementation diff and confirm no files under the V3 module were changed.

- [ ] **Step 7: Run the complete research regression suite**

```bash
python -m pytest -q research/swing
```

If repository test discovery requires the `Swing Trading/...` path form in the executor's environment, use the existing repository convention and report the exact command actually run.

Expected: zero failures except already-known non-failing pytest-cache permission warnings.

- [ ] **Step 8: Generate the real frozen M1 evidence exactly once**

```bash
python "Swing Trading/research/swing/m1_regime_gated_momentum/run_m1_validation.py"
```

Do not inspect intermediate profitability and then change methodology before the final run.

- [ ] **Step 9: Mechanically verify final accounting**

Check and record:

```text
frozen qualified = enabled qualified + disabled qualified
frozen accepted = enabled accepted + disabled shadow accepted
frozen cancelled = enabled cancelled + disabled shadow cancelled
frozen completed = enabled completed + disabled completed
enabled setup completed Entry_ID set = enabled practical completed Entry_ID set
disabled setup completed Entry_ID set = disabled practical completed Entry_ID set
integrity violations = 0 for any valid interpreted run
all gate thresholds exactly match the spec
```

- [ ] **Step 10: Commit the completed validator + generated evidence**

```bash
git add "Swing Trading/research/swing/m1_regime_gated_momentum"
git commit -m "research: validate M1 regime-gated momentum"
```

### Final implementation handoff

Report only:

- implementation commit SHA(s);
- exact test commands and pass counts;
- frozen V3 qualified/accepted/cancelled/completed counts and whether partition reconciled exactly;
- M1 enabled/disabled signal and completed counts;
- integrity violation count;
- base/stress practical metrics;
- enabled-vs-disabled comparison;
- temporal/top-five/LOSO gate results;
- final formal M1 status;
- paths to `m1_validation_gates.csv` and `research_report.md`;
- whether any V3 file changed (expected: **no**).

If the status is `FAIL` or `INSUFFICIENT_EVIDENCE`, do **not** propose a rescue. If `PASS`, do **not** start Candidate 2; hand off to Portfolio Advisor for portfolio/execution finalization.