# M1 Regime-Gated Momentum Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one focused, auditable M1 validator that partitions the already-frozen V3 opportunity set by the independently predeclared M1 market regime and mechanically reports `PASS`, `FAIL`, `INSUFFICIENT_EVIDENCE`, or `INVALID_RESEARCH_RUN` without changing V3 or tuning M1 after outcomes.

**Architecture:** Add one new research module under `Swing Trading/research/swing/m1_regime_gated_momentum/`. The module must treat closed V3 artifacts as read-only stock-strategy evidence, recompute only the new M1 regime from existing PIT breadth + Nifty 500 index data, partition frozen V3 signals/entries/outcomes into enabled and disabled cohorts, apply M1 friction/robustness/gates, and write the exact minimum evidence package frozen in the spec. It must not download market data, rebuild V3 signals, modify V3 outputs, create a generic strategy framework, or add dashboards.

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

## File Map — exact minimum evidence package from the approved spec

```text
Swing Trading/research/swing/m1_regime_gated_momentum/
├── README.md
├── load_frozen_sources.py
├── build_m1_regime.py
├── partition_m1_cohorts.py
├── analyze_m1_results.py
├── run_m1_validation.py
├── tests/
│   ├── fixtures.py
│   ├── test_m1_sources.py
│   ├── test_m1_regime.py
│   ├── test_m1_partition.py
│   ├── test_m1_analysis.py
│   └── test_m1_end_to_end.py
└── output/
    ├── m1_data_validation.csv
    ├── m1_regime_daily.csv
    ├── m1_regime_audit.csv
    ├── m1_signal_classification.csv
    ├── m1_enabled_entries.csv
    ├── m1_enabled_cancellations.csv
    ├── m1_disabled_shadow_entries.csv
    ├── m1_disabled_shadow_cancellations.csv
    ├── m1_setup_quality_trades.csv
    ├── m1_practical_trades.csv
    ├── m1_disabled_setup_control.csv
    ├── m1_disabled_practical_control.csv
    ├── m1_validation_summary.csv
    ├── m1_regime_comparison.csv
    ├── m1_temporal_summary.csv
    ├── m1_year_summary.csv
    ├── m1_top_five_robustness.csv
    ├── m1_leave_one_symbol_out.csv
    ├── m1_overlap_capacity_diagnostic.csv
    ├── m1_integrity_audit.csv
    ├── m1_validation_gates.csv
    └── research_report.md
```

Do not create a downloader, feature cache, strategy engine, dashboard, notebook, or generic reusable backtest framework.

---

### Task 1: Load and validate frozen V3 + market source artifacts

**Files:**
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/load_frozen_sources.py`
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/tests/fixtures.py`
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_sources.py`

**Interfaces:**

```python
V3_OUTPUT_ROOT: Path
BREADTH_PATH: Path
INDEX_PATH: Path
MEMBERSHIP_PATH: Path
SECTOR_MAP_PATH: Path

load_required_csv(
    path: Path,
    required_columns: tuple[str, ...],
    parse_dates: tuple[str, ...] = (),
) -> tuple[pd.DataFrame, pd.DataFrame]

load_v3_artifacts(
    v3_output_root: Path = V3_OUTPUT_ROOT,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]

load_market_sources(
    breadth_path: Path = BREADTH_PATH,
    index_path: Path = INDEX_PATH,
    membership_path: Path = MEMBERSHIP_PATH,
    sector_map_path: Path = SECTOR_MAP_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]

validate_frozen_v3_accounting(
    artifacts: dict[str, pd.DataFrame],
) -> pd.DataFrame
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
    "v3_practical_trades.csv": ("Entry_ID", "Symbol", "Signal_Date", "Entry_Date", "Entry_Open", "Structural_Stop", "Initial_Risk", "Exit_Date", "Exit_Price", "R_Multiple", "Holding_Sessions", "Exit_Reason"),
    "v3_validation_gates.csv": ("Gate", "Passed", "Value", "Status"),
}
```

Market sources:

```text
Swing Trading/research/swing/market_breadth/output/nifty500_breadth_daily.csv
Swing Trading/nifty500_regime_daily.csv
Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv
Swing Trading/research/swing/sector_leadership/stock_sector_map.csv  # diagnostic only; partial mapping is acceptable
```

- [ ] **Step 1: Create deterministic frozen-V3 test fixtures**

Put this helper in `tests/fixtures.py`:

```python
from pathlib import Path
import pandas as pd


def write_minimal_v3_package(root: Path) -> None:
    signals = pd.DataFrame([
        {"Entry_ID": "AAA-2024-01-02", "Symbol": "AAA", "Signal_Date": "2024-01-02", "Signal_Qualified": True},
        {"Entry_ID": "BBB-2024-01-03", "Symbol": "BBB", "Signal_Date": "2024-01-03", "Signal_Qualified": True},
        {"Entry_ID": "CCC-2024-01-04", "Symbol": "CCC", "Signal_Date": "2024-01-04", "Signal_Qualified": True},
        {"Entry_ID": "DDD-2024-01-05", "Symbol": "DDD", "Signal_Date": "2024-01-05", "Signal_Qualified": False},
    ])
    entries = pd.DataFrame([
        {"Entry_ID": "AAA-2024-01-02", "Symbol": "AAA", "Signal_Date": "2024-01-02", "Entry_Date": "2024-01-03", "Entry_Open": 100.0, "Structural_Stop": 95.0, "Initial_Risk": 5.0},
        {"Entry_ID": "BBB-2024-01-03", "Symbol": "BBB", "Signal_Date": "2024-01-03", "Entry_Date": "2024-01-04", "Entry_Open": 200.0, "Structural_Stop": 190.0, "Initial_Risk": 10.0},
    ])
    cancellations = pd.DataFrame([
        {"Entry_ID": "CCC-2024-01-04", "Symbol": "CCC", "Signal_Date": "2024-01-04", "Cancellation_Reason": "STOP_TOO_WIDE"},
    ])
    setup = pd.DataFrame([
        {"Entry_ID": "AAA-2024-01-02", "Symbol": "AAA", "Signal_Date": "2024-01-02", "Entry_Date": "2024-01-03", "Entry_Open": 100.0, "Structural_Stop": 95.0, "Initial_Risk": 5.0, "Exit_Date": "2024-01-10", "Exit_Price": 110.0, "Return": 0.10},
    ])
    practical = pd.DataFrame([
        {"Entry_ID": "AAA-2024-01-02", "Symbol": "AAA", "Signal_Date": "2024-01-02", "Entry_Date": "2024-01-03", "Entry_Open": 100.0, "Structural_Stop": 95.0, "Initial_Risk": 5.0, "Exit_Date": "2024-01-10", "Exit_Price": 110.0, "R_Multiple": 2.0, "Holding_Sessions": 5, "Exit_Reason": "SMA20"},
    ])
    gates = pd.DataFrame([
        {"Gate": "POINT_IN_TIME_INTEGRITY", "Passed": True, "Value": 0, "Status": "PASS"},
        {"Gate": "FINAL_STATUS", "Passed": False, "Value": "FAIL", "Status": "FAIL"},
    ])
    frames = {
        "v3_signal_candidates.csv": signals,
        "v3_entries.csv": entries,
        "v3_entry_cancellations.csv": cancellations,
        "v3_setup_quality_trades.csv": setup,
        "v3_practical_trades.csv": practical,
        "v3_validation_gates.csv": gates,
    }
    root.mkdir(parents=True, exist_ok=True)
    for filename, frame in frames.items():
        frame.to_csv(root / filename, index=False)
```

This fixture intentionally includes one accepted-but-incomplete entry (`BBB`) so later partition tests can prove it is never promoted to a completed trade.

- [ ] **Step 2: Write failing artifact-loader tests**

Create these tests in `test_m1_sources.py`:

```python
import pandas as pd
from load_frozen_sources import load_v3_artifacts, validate_frozen_v3_accounting
from fixtures import write_minimal_v3_package


def test_missing_required_v3_artifact_records_integrity_violation(tmp_path):
    write_minimal_v3_package(tmp_path)
    (tmp_path / "v3_entries.csv").unlink()
    _, audit = load_v3_artifacts(tmp_path)
    assert "MISSING_REQUIRED_ARTIFACT" in audit["Violation"].tolist()


def test_missing_required_column_records_integrity_violation(tmp_path):
    write_minimal_v3_package(tmp_path)
    frame = pd.read_csv(tmp_path / "v3_entries.csv").drop(columns=["Initial_Risk"])
    frame.to_csv(tmp_path / "v3_entries.csv", index=False)
    _, audit = load_v3_artifacts(tmp_path)
    assert "INVALID_REQUIRED_ARTIFACT" in audit["Violation"].tolist()


def test_v3_point_in_time_gate_must_already_pass(tmp_path):
    write_minimal_v3_package(tmp_path)
    gates = pd.read_csv(tmp_path / "v3_validation_gates.csv")
    gates.loc[gates["Gate"].eq("POINT_IN_TIME_INTEGRITY"), "Passed"] = False
    gates.to_csv(tmp_path / "v3_validation_gates.csv", index=False)
    artifacts, loader_audit = load_v3_artifacts(tmp_path)
    audit = pd.concat([loader_audit, validate_frozen_v3_accounting(artifacts)], ignore_index=True)
    assert "V3_PIT_INTEGRITY_NOT_CLEAN" in audit["Violation"].tolist()


def test_frozen_v3_accounting_reconciles_qualified_accepted_cancelled_and_completed(tmp_path):
    write_minimal_v3_package(tmp_path)
    artifacts, loader_audit = load_v3_artifacts(tmp_path)
    accounting_audit = validate_frozen_v3_accounting(artifacts)
    assert loader_audit.empty
    assert accounting_audit.empty
```

- [ ] **Step 3: Run tests and verify failure**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_sources.py"
```

Expected: FAIL because loader/validation functions do not exist.

- [ ] **Step 4: Implement minimal source loader and source-integrity audit**

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

`load_market_sources()` returns `(breadth, index_daily, membership, sector_mapping, audit)`. Required market columns are:

```python
BREADTH_COLUMNS = ("Date", "SMA50_Denominator", "Pct_Above_SMA50")
INDEX_COLUMNS = ("Date", "Close", "SMA50", "SMA200")
MEMBERSHIP_COLUMNS = ("Symbol", "Member_From", "Member_To", "Method")
```

Reject membership rows unless `Method == "POINT_IN_TIME"`. Sector mapping is diagnostic only: if the file is absent or lacks `Stock`/`Sector_Key`, return an empty mapping without making the research run invalid.

- [ ] **Step 5: Run tests and make them pass**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_sources.py"
```

Expected: PASS.

- [ ] **Step 6: Commit**

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
build_m1_regime(
    breadth: pd.DataFrame,
    index_daily: pd.DataFrame,
    membership: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]
attach_exact_signal_regime(
    signals: pd.DataFrame,
    regime_daily: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
```

`attach_exact_signal_regime()` returns `(classified_signals, regime_audit, violations)`.

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

`m1_regime_audit.csv` columns:

```text
Entry_ID
Symbol
Signal_Date
Regime_Context_Date
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
Exact_Date_Match
PIT_Denominator_Match
```

- [ ] **Step 1: Write exact threshold/timing tests**

Use this literal fixture and tests in `test_m1_regime.py`:

```python
import pandas as pd
from build_m1_regime import build_m1_regime, attach_exact_signal_regime


def market_fixture(pct_above=50.0, denominator=4, close=120.0, sma50=110.0, sma200=100.0, old_regime="HOSTILE"):
    date = pd.Timestamp("2024-01-02")
    membership = pd.DataFrame({
        "Symbol": ["A", "B", "C", "D", "E"],
        "Member_From": pd.to_datetime(["2023-01-01"] * 5),
        "Member_To": pd.to_datetime(["2024-12-31"] * 5),
        "Method": ["POINT_IN_TIME"] * 5,
    })
    breadth = pd.DataFrame({
        "Date": [date],
        "SMA50_Denominator": [denominator],
        "Pct_Above_SMA50": [pct_above],
        "Regime": [old_regime],
        "Momentum_Regime": [old_regime],
        "Universe_Member_Count": [5],
    })
    index_daily = pd.DataFrame({
        "Date": [date],
        "Close": [close],
        "SMA50": [sma50],
        "SMA200": [sma200],
        "Regime": [old_regime],
    })
    return breadth, index_daily, membership


def test_coverage_exactly_point_80_is_safe():
    breadth, index_daily, membership = market_fixture(denominator=4)
    regime, audit = build_m1_regime(breadth, index_daily, membership)
    assert audit.empty
    assert regime.loc[0, "SMA50_Breadth_Coverage"] == 0.8
    assert bool(regime.loc[0, "DATA_SAFE"])


def test_breadth_exactly_50_is_ok():
    breadth, index_daily, membership = market_fixture(pct_above=50.0)
    regime, audit = build_m1_regime(breadth, index_daily, membership)
    assert audit.empty
    assert bool(regime.loc[0, "BREADTH_OK"])
    assert regime.loc[0, "M1_Regime"] == "MOMENTUM_ENABLED"


def test_index_requires_both_close_and_sma50_above_sma200():
    breadth, index_daily, membership = market_fixture(close=120.0, sma50=99.0, sma200=100.0)
    regime, _ = build_m1_regime(breadth, index_daily, membership)
    assert not bool(regime.loc[0, "INDEX_TREND_OK"])
    assert regime.loc[0, "M1_Regime"] == "MOMENTUM_DISABLED"


def test_old_strong_momentum_label_is_ignored():
    breadth, index_daily, membership = market_fixture(
        pct_above=49.0,
        close=99.0,
        sma50=98.0,
        sma200=100.0,
        old_regime="STRONG_MOMENTUM",
    )
    regime, _ = build_m1_regime(breadth, index_daily, membership)
    assert regime.loc[0, "M1_Regime"] == "MOMENTUM_DISABLED"


def test_signal_regime_join_requires_exact_same_date():
    signals = pd.DataFrame({
        "Entry_ID": ["AAA-2024-01-03"],
        "Symbol": ["AAA"],
        "Signal_Date": pd.to_datetime(["2024-01-03"]),
    })
    regime = pd.DataFrame({
        "Date": pd.to_datetime(["2024-01-02"]),
        "M1_Regime": ["MOMENTUM_ENABLED"],
    })
    joined, regime_audit, violations = attach_exact_signal_regime(signals, regime)
    assert pd.isna(joined.loc[0, "M1_Regime"])
    assert not bool(regime_audit.loc[0, "Exact_Date_Match"])
    assert "MISSING_EXACT_SIGNAL_REGIME" in violations["Violation"].tolist()


def test_membership_denominator_is_recomputed_from_pit_intervals():
    breadth, index_daily, membership = market_fixture(denominator=4)
    breadth.loc[0, "Universe_Member_Count"] = 4
    _, audit = build_m1_regime(breadth, index_daily, membership)
    assert "BREADTH_PIT_DENOMINATOR_MISMATCH" in audit["Violation"].tolist()
```

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
partition_v3_evidence(
    classification: pd.DataFrame,
    artifacts: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]
```

`m1_signal_classification.csv` must retain at least:

```text
Entry_ID,Symbol,Signal_Date,M1_Regime,DATA_SAFE,INDEX_TREND_OK,BREADTH_OK,SMA50_Breadth_Coverage,Pct_Above_SMA50,Nifty500_Close,Nifty500_SMA50,Nifty500_SMA200,V3_Entry_Status,V3_Cancellation_Reason
```

- [ ] **Step 1: Write partition/accounting tests**

Use `write_minimal_v3_package()` from Task 1. Build a literal classification where `AAA` is enabled, `BBB` and `CCC` are disabled:

```python
import pandas as pd
from load_frozen_sources import load_v3_artifacts
from partition_m1_cohorts import partition_v3_evidence
from fixtures import write_minimal_v3_package


def classification_fixture():
    return pd.DataFrame([
        {"Entry_ID": "AAA-2024-01-02", "Symbol": "AAA", "Signal_Date": pd.Timestamp("2024-01-02"), "M1_Regime": "MOMENTUM_ENABLED"},
        {"Entry_ID": "BBB-2024-01-03", "Symbol": "BBB", "Signal_Date": pd.Timestamp("2024-01-03"), "M1_Regime": "MOMENTUM_DISABLED"},
        {"Entry_ID": "CCC-2024-01-04", "Symbol": "CCC", "Signal_Date": pd.Timestamp("2024-01-04"), "M1_Regime": "MOMENTUM_DISABLED"},
    ])


def test_partition_preserves_frozen_v3_accepted_and_cancelled_sets(tmp_path):
    write_minimal_v3_package(tmp_path)
    artifacts, audit = load_v3_artifacts(tmp_path)
    assert audit.empty
    cohorts, partition_audit = partition_v3_evidence(classification_fixture(), artifacts)
    assert partition_audit.empty
    accepted = set(cohorts["enabled_entries"]["Entry_ID"]) | set(cohorts["disabled_shadow_entries"]["Entry_ID"])
    cancelled = set(cohorts["enabled_cancellations"]["Entry_ID"]) | set(cohorts["disabled_shadow_cancellations"]["Entry_ID"])
    assert accepted == {"AAA-2024-01-02", "BBB-2024-01-03"}
    assert cancelled == {"CCC-2024-01-04"}


def test_disabled_control_uses_frozen_v3_cancellation_instead_of_creating_trade(tmp_path):
    write_minimal_v3_package(tmp_path)
    artifacts, _ = load_v3_artifacts(tmp_path)
    cohorts, _ = partition_v3_evidence(classification_fixture(), artifacts)
    assert "CCC-2024-01-04" not in set(cohorts["disabled_shadow_entries"]["Entry_ID"])
    row = cohorts["disabled_shadow_cancellations"].set_index("Entry_ID").loc["CCC-2024-01-04"]
    assert row["Cancellation_Reason"] == "STOP_TOO_WIDE"


def test_completed_enabled_plus_disabled_equals_frozen_completed_sample(tmp_path):
    write_minimal_v3_package(tmp_path)
    artifacts, _ = load_v3_artifacts(tmp_path)
    cohorts, _ = partition_v3_evidence(classification_fixture(), artifacts)
    enabled = set(cohorts["enabled_practical"]["Entry_ID"])
    disabled = set(cohorts["disabled_practical"]["Entry_ID"])
    frozen = set(artifacts["v3_practical_trades.csv"]["Entry_ID"])
    assert enabled.isdisjoint(disabled)
    assert enabled | disabled == frozen


def test_incomplete_accepted_entry_is_not_promoted_to_completed_control(tmp_path):
    write_minimal_v3_package(tmp_path)
    artifacts, _ = load_v3_artifacts(tmp_path)
    cohorts, _ = partition_v3_evidence(classification_fixture(), artifacts)
    assert "BBB-2024-01-03" in set(cohorts["disabled_shadow_entries"]["Entry_ID"])
    assert "BBB-2024-01-03" not in set(cohorts["disabled_practical"]["Entry_ID"])


def test_duplicate_regime_classification_is_integrity_violation(tmp_path):
    write_minimal_v3_package(tmp_path)
    artifacts, _ = load_v3_artifacts(tmp_path)
    classification = pd.concat([classification_fixture(), classification_fixture().iloc[[0]]], ignore_index=True)
    _, audit = partition_v3_evidence(classification, artifacts)
    assert "DUPLICATE_REGIME_CLASSIFICATION" in audit["Violation"].tolist()
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

Output mapping:

```text
enabled_entries                -> m1_enabled_entries.csv
enabled_cancellations          -> m1_enabled_cancellations.csv
disabled_shadow_entries        -> m1_disabled_shadow_entries.csv
disabled_shadow_cancellations  -> m1_disabled_shadow_cancellations.csv
enabled_setup                  -> m1_setup_quality_trades.csv
enabled_practical              -> m1_practical_trades.csv
disabled_setup                 -> m1_disabled_setup_control.csv
disabled_practical             -> m1_disabled_practical_control.csv
```

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
add_setup_friction(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]
add_practical_friction(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]
summarize_setup(trades: pd.DataFrame, prefix: str) -> dict[str, float]
summarize_practical(trades: pd.DataFrame, prefix: str) -> dict[str, float]
regime_comparison(enabled: pd.DataFrame, disabled: pd.DataFrame) -> pd.DataFrame
temporal_summary(enabled_practical: pd.DataFrame) -> pd.DataFrame
year_summary(enabled_practical: pd.DataFrame) -> pd.DataFrame
```

- [ ] **Step 1: Write arithmetic and metric tests**

Use these literal tests:

```python
import numpy as np
import pandas as pd
import pytest
from analyze_m1_results import (
    add_setup_friction,
    add_practical_friction,
    safe_profit_factor,
    temporal_summary,
    regime_comparison,
)


def test_setup_friction_is_gross_return_minus_round_trip_cost():
    trades = pd.DataFrame([{"Entry_ID": "A", "Return": 0.02}])
    out, audit = add_setup_friction(trades)
    assert audit.empty
    assert out.loc[0, "Base_Net_Return"] == pytest.approx(0.016)
    assert out.loc[0, "Stress_Net_Return"] == pytest.approx(0.014)
    assert out.loc[0, "Severe_Net_Return"] == pytest.approx(0.012)


def test_practical_net_r_uses_entry_price_cost_over_initial_risk():
    trades = pd.DataFrame([{
        "Entry_ID": "A",
        "Entry_Open": 100.0,
        "Structural_Stop": 95.0,
        "Initial_Risk": 5.0,
        "Exit_Price": 110.0,
        "R_Multiple": 2.0,
    }])
    out, audit = add_practical_friction(trades)
    assert audit.empty
    assert out.loc[0, "Base_Net_R"] == pytest.approx((10.0 - 0.4) / 5.0)
    assert out.loc[0, "Stress_Net_R"] == pytest.approx((10.0 - 0.6) / 5.0)


def test_initial_risk_mismatch_is_integrity_violation():
    trades = pd.DataFrame([{
        "Entry_ID": "A",
        "Entry_Open": 100.0,
        "Structural_Stop": 95.0,
        "Initial_Risk": 4.0,
        "Exit_Price": 110.0,
        "R_Multiple": 2.0,
    }])
    _, audit = add_practical_friction(trades)
    assert "INITIAL_RISK_MISMATCH" in audit["Violation"].tolist()


def test_gross_r_mismatch_is_integrity_violation():
    trades = pd.DataFrame([{
        "Entry_ID": "A",
        "Entry_Open": 100.0,
        "Structural_Stop": 95.0,
        "Initial_Risk": 5.0,
        "Exit_Price": 110.0,
        "R_Multiple": 1.5,
    }])
    _, audit = add_practical_friction(trades)
    assert "GROSS_R_MISMATCH" in audit["Violation"].tolist()


def test_profit_factor_boundaries():
    assert safe_profit_factor(pd.Series([2.0, -1.0])) == pytest.approx(2.0)
    assert safe_profit_factor(pd.Series([2.0, 1.0])) == np.inf
    assert safe_profit_factor(pd.Series([-2.0, -1.0])) == 0.0


def test_temporal_split_uses_signal_date_not_entry_date():
    trades = pd.DataFrame([
        {"Entry_ID": "A", "Signal_Date": "2025-02-11", "Entry_Date": "2025-02-12", "Base_Net_R": 1.0},
        {"Entry_ID": "B", "Signal_Date": "2025-02-12", "Entry_Date": "2025-02-13", "Base_Net_R": -0.5},
    ])
    out = temporal_summary(trades)
    counts = dict(zip(out["Period"], out["Completed_Trades"]))
    assert counts["FIRST_HALF"] == 1
    assert counts["SECOND_HALF"] == 1


def test_enabled_and_disabled_receive_identical_comparison_formula():
    enabled = pd.DataFrame({"Base_Net_R": [1.0, -0.2]})
    disabled = pd.DataFrame({"Base_Net_R": [0.1, -0.2]})
    out = regime_comparison(enabled, disabled).iloc[0]
    assert bool(out["Enabled_Beats_Disabled_Mean"])
    assert bool(out["Enabled_Beats_Disabled_R_PF"])
```

Use `np.isclose(..., rtol=1e-9, atol=1e-12)` inside implementation for persisted-vs-recomputed numeric evidence.

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_analysis.py" -k "friction or temporal or profit or comparison"
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

- [ ] **Step 4: Produce base summary/comparison/temporal/year functions**

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

Temporal halves use `Signal_Date` exactly. Calendar-year summaries use `Signal_Date.dt.year` and are diagnostic only.

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

### Task 5: Add robustness, spec-required diagnostics, frozen gates and status precedence

**Files:**
- Modify: `Swing Trading/research/swing/m1_regime_gated_momentum/analyze_m1_results.py`
- Modify: `Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_analysis.py`

**Interfaces:**

```python
top_five_robustness(enabled_practical: pd.DataFrame) -> pd.DataFrame
leave_one_symbol_out(enabled_practical: pd.DataFrame) -> pd.DataFrame

overlap_capacity_diagnostic(
    enabled_classification: pd.DataFrame,
    enabled_entries: pd.DataFrame,
    enabled_practical: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex,
    sector_mapping: pd.DataFrame,
) -> pd.DataFrame

evaluate_gates(
    setup_metrics: dict[str, float],
    practical_metrics: dict[str, float],
    comparison: pd.DataFrame,
    temporal: pd.DataFrame,
    top_five: pd.DataFrame,
    loso: pd.DataFrame,
    completed_enabled: int,
    integrity_violations: int,
) -> tuple[str, pd.DataFrame]
```

- [ ] **Step 1: Write robustness/status tests**

Use these literal fixtures/assertions:

```python
import pandas as pd
from analyze_m1_results import (
    top_five_robustness,
    leave_one_symbol_out,
    overlap_capacity_diagnostic,
    evaluate_gates,
)


def passing_inputs(integrity_violations=0, completed_enabled=300):
    setup = {"Base_Mean_Net_Return": 0.01, "Base_Net_Return_PF": 1.5}
    practical = {
        "Base_Mean_Net_R": 0.25,
        "Base_Net_R_PF": 1.5,
        "Stress_Mean_Net_R": 0.10,
        "Stress_Net_R_PF": 1.2,
    }
    comparison = pd.DataFrame([{
        "Enabled_Completed": completed_enabled,
        "Disabled_Completed": 50,
        "Enabled_Base_Mean_Net_R": 0.25,
        "Disabled_Base_Mean_Net_R": 0.05,
        "Enabled_Base_R_PF": 1.5,
        "Disabled_Base_R_PF": 1.05,
        "Enabled_Beats_Disabled_Mean": True,
        "Enabled_Beats_Disabled_R_PF": True,
    }])
    temporal = pd.DataFrame([
        {"Period": "FIRST_HALF", "Mean_Base_Net_R": 0.1, "Base_R_PF": 1.1},
        {"Period": "SECOND_HALF", "Mean_Base_Net_R": 0.1, "Base_R_PF": 1.1},
    ])
    top_five = pd.DataFrame([{"Remaining_Mean_Base_Net_R": 0.1, "Remaining_Base_R_PF": 1.1}])
    loso = pd.DataFrame([
        {"Omitted_Symbol": "AAA", "Mean_Base_Net_R": 0.1, "Base_R_PF": 1.1},
        {"Omitted_Symbol": "BBB", "Mean_Base_Net_R": 0.1, "Base_R_PF": 1.1},
    ])
    return setup, practical, comparison, temporal, top_five, loso, completed_enabled, integrity_violations


def test_sample_below_300_is_insufficient():
    status, _ = evaluate_gates(*passing_inputs(completed_enabled=299))
    assert status == "INSUFFICIENT_EVIDENCE"


def test_any_integrity_violation_overrides_insufficient_and_fail():
    status, _ = evaluate_gates(*passing_inputs(integrity_violations=1, completed_enabled=10))
    assert status == "INVALID_RESEARCH_RUN"


def test_all_mandatory_gates_pass_returns_pass():
    status, gates = evaluate_gates(*passing_inputs())
    assert status == "PASS"
    assert gates.loc[gates["Mandatory"], "Pass"].all()


def test_valid_sufficient_single_gate_failure_returns_fail():
    args = list(passing_inputs())
    args[1] = dict(args[1])
    args[1]["Base_Mean_Net_R"] = 0.14
    status, _ = evaluate_gates(*args)
    assert status == "FAIL"


def test_top_five_removes_largest_gross_r_not_net_r():
    trades = pd.DataFrame({
        "Entry_ID": list("ABCDEFG"),
        "R_Multiple": [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, -1.0],
        "Base_Net_R": [-5.0, 8.0, 7.0, 6.0, 5.0, 4.0, -1.0],
    })
    out = top_five_robustness(trades)
    removed = set(out.loc[0, "Removed_Entry_IDs"].split(";"))
    assert removed == set("ABCDE")


def test_loso_reports_every_symbol():
    trades = pd.DataFrame({
        "Symbol": ["AAA", "AAA", "BBB"],
        "Base_Net_R": [1.0, -0.2, 0.5],
    })
    out = leave_one_symbol_out(trades)
    assert set(out["Omitted_Symbol"]) == {"AAA", "BBB"}
```

Add an exact 1%-risk diagnostic test:

```python
def test_overlap_capacity_uses_exact_one_percent_risk_weight_and_partial_sector_mapping():
    classification = pd.DataFrame({
        "Entry_ID": ["A", "B"],
        "Symbol": ["AAA", "BBB"],
        "Signal_Date": pd.to_datetime(["2024-01-02", "2024-01-02"]),
    })
    entries = pd.DataFrame({
        "Entry_ID": ["A", "B"],
        "Symbol": ["AAA", "BBB"],
        "Entry_Date": pd.to_datetime(["2024-01-03", "2024-01-03"]),
        "Entry_Open": [100.0, 200.0],
        "Initial_Risk": [5.0, 20.0],
    })
    practical = pd.DataFrame({
        "Entry_ID": ["A", "B"],
        "Entry_Date": pd.to_datetime(["2024-01-03", "2024-01-03"]),
        "Exit_Date": pd.to_datetime(["2024-01-05", "2024-01-04"]),
    })
    sector_mapping = pd.DataFrame({"Stock": ["AAA"], "Sector_Key": ["IT"]})
    sessions = pd.DatetimeIndex(pd.to_datetime(["2024-01-03", "2024-01-04", "2024-01-05"]))
    out = overlap_capacity_diagnostic(classification, entries, practical, sessions, sector_mapping)
    metrics = out.set_index(["Metric", "Dimension"])["Value"]
    assert float(metrics.loc[("MEDIAN_IMPLIED_POSITION_WEIGHT", "")]) == 0.15
    assert float(metrics.loc[("MAPPED_ACCEPTED_ENTRIES", "")]) == 1.0
    assert float(metrics.loc[("UNMAPPED_ACCEPTED_ENTRIES", "")]) == 1.0
    assert float(metrics.loc[("SECTOR_ENTRY_COUNT", "IT")]) == 1.0
```

The two implied weights are `0.01/(5/100)=0.20` and `0.01/(20/200)=0.10`; median is `0.15`.

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

`evaluate_gates()` must not accept overlap/capacity/sector diagnostics as arguments. Add a test asserting the gate-name set contains none of `SECTOR`, `CAPACITY`, `SIMULTANEOUS`, `SAME_DAY`, or `RS_BAND`.

- [ ] **Step 3: Implement top-five and LOSO exactly**

Top-five ranking column is frozen gross `R_Multiple` / recomputed gross R.

LOSO loops every symbol present in the enabled completed practical sample and calculates base-net mean R + base-net R-PF after omitting all that symbol's trades.

- [ ] **Step 4: Implement the spec-required diagnostics without gating**

`m1_overlap_capacity_diagnostic.csv` uses long-form columns:

```text
Metric,Dimension,Value
```

Report at minimum:

```text
ENABLED_ACCEPTED_ENTRIES
ENABLED_COMPLETED_TRADES
ENABLED_INCOMPLETE_ACCEPTED
MAX_SIMULTANEOUS_COMPLETED_LIFECYCLES
SIMULTANEOUS_LIFECYCLE_COVERAGE_PERCENT
MAX_SAME_DAY_ENABLED_QUALIFIED_SIGNALS
MAX_SAME_DAY_ENABLED_ACCEPTED_ENTRIES
SAME_DAY_ENABLED_QUALIFIED_DISTRIBUTION_JSON
MEDIAN_INITIAL_RISK_FRACTION
MEDIAN_IMPLIED_POSITION_WEIGHT
MAX_IMPLIED_POSITION_WEIGHT
MAPPED_ACCEPTED_ENTRIES
UNMAPPED_ACCEPTED_ENTRIES
MAPPING_COVERAGE_PERCENT
SECTOR_ENTRY_COUNT,<Sector_Key>,<count>  # one row per mapped sector
```

For simultaneous-lifecycle calculation, use completed practical outcomes with known `Entry_Date` and `Exit_Date`; count active sessions from `Entry_Date` through the canonical session immediately before `Exit_Date`. If `Entry_Date == Exit_Date`, count that entry session once. Report coverage so incomplete accepted entries are not silently ignored.

For sector concentration, use only symbols present in the existing `stock_sector_map.csv`; do not infer or invent sectors for unmapped symbols.

Also persist/report the spec diagnostics already present in enabled trade/classification files: win rate, gross/net return/R distributions, holding sessions, exit-reason distribution, breadth, index distance from SMA200, Composite RS, pullback age/depth, and entry extension. These are report summaries only and never eligibility/gate inputs.

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

### Task 6: Build the one-command evidence run, exact spec outputs, report, and regression verification

**Files:**
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/run_m1_validation.py`
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/README.md`
- Create: `Swing Trading/research/swing/m1_regime_gated_momentum/tests/test_m1_end_to_end.py`
- Generate: every `output/` artifact listed in the File Map

**Interfaces:**

```python
run_validation(
    v3_output_root: Path = V3_OUTPUT_ROOT,
    breadth_path: Path = BREADTH_PATH,
    index_path: Path = INDEX_PATH,
    membership_path: Path = MEMBERSHIP_PATH,
    sector_map_path: Path = SECTOR_MAP_PATH,
    output_dir: Path = OUTPUT_ROOT,
) -> tuple[str, pd.DataFrame]

write_research_report(
    path: Path,
    status: str,
    evidence: dict[str, object],
) -> None
```

- [ ] **Step 1: Write synthetic end-to-end status-precedence tests**

Do not make these tests depend on the real repository data. Reuse `write_minimal_v3_package()` and write market CSVs into `tmp_path`.

Create this helper in `test_m1_end_to_end.py`:

```python
from pathlib import Path
import pandas as pd


def write_market_package(root: Path) -> tuple[Path, Path, Path, Path]:
    breadth_path = root / "breadth.csv"
    index_path = root / "index.csv"
    membership_path = root / "membership.csv"
    sector_path = root / "sector.csv"
    dates = ["2024-01-02", "2024-01-03", "2024-01-04"]
    pd.DataFrame({
        "Date": dates,
        "SMA50_Denominator": [3, 3, 3],
        "Pct_Above_SMA50": [100.0, 100.0, 100.0],
        "Universe_Member_Count": [3, 3, 3],
        "Regime": ["HOSTILE", "HOSTILE", "HOSTILE"],
    }).to_csv(breadth_path, index=False)
    pd.DataFrame({
        "Date": dates,
        "Close": [120.0, 121.0, 122.0],
        "SMA50": [110.0, 110.0, 110.0],
        "SMA200": [100.0, 100.0, 100.0],
        "Regime": ["RISK_OFF", "RISK_OFF", "RISK_OFF"],
    }).to_csv(index_path, index=False)
    pd.DataFrame({
        "Symbol": ["AAA", "BBB", "CCC"],
        "Member_From": ["2023-01-01"] * 3,
        "Member_To": ["2024-12-31"] * 3,
        "Method": ["POINT_IN_TIME"] * 3,
    }).to_csv(membership_path, index=False)
    pd.DataFrame({"Stock": ["AAA"], "Sector_Key": ["IT"]}).to_csv(sector_path, index=False)
    return breadth_path, index_path, membership_path, sector_path
```

Then write:

```python
def test_end_to_end_missing_source_is_invalid(tmp_path):
    v3_root = tmp_path / "v3"
    write_minimal_v3_package(v3_root)
    (v3_root / "v3_entries.csv").unlink()
    breadth, index_daily, membership, sector = write_market_package(tmp_path)
    status, _ = run_validation(v3_root, breadth, index_daily, membership, sector, tmp_path / "out")
    assert status == "INVALID_RESEARCH_RUN"


def test_end_to_end_fixture_with_fewer_than_300_enabled_trades_is_insufficient(tmp_path):
    v3_root = tmp_path / "v3"
    write_minimal_v3_package(v3_root)
    breadth, index_daily, membership, sector = write_market_package(tmp_path)
    status, _ = run_validation(v3_root, breadth, index_daily, membership, sector, tmp_path / "out")
    assert status == "INSUFFICIENT_EVIDENCE"
```

For `FAIL` and `PASS` precedence, use `evaluate_gates()` unit tests from Task 5 rather than fabricating 300 CSV trades. End-to-end here proves orchestration, missing-source invalidation, exact-date regime coverage, and insufficient-sample behavior.

- [ ] **Step 2: Implement orchestration in this exact order**

```text
1. load frozen V3 sources
2. validate frozen V3 source accounting/PIT gate
3. load breadth/index/membership/optional-sector sources
4. build independent M1 daily regime
5. exact-date attach regime to all frozen qualified V3 signals and create m1_regime_audit
6. create m1_signal_classification and partition accepted/cancelled/completed evidence
7. recompute friction and numeric-integrity checks
8. calculate enabled/control metrics
9. calculate temporal/year/top-five/LOSO/diagnostic evidence
10. merge all integrity rows
11. evaluate frozen gates/status
12. write exact minimum evidence package + research_report.md
13. verify every final required output exists/readable/schema-valid
14. if final package verification adds violations, rewrite integrity/gates/report as INVALID_RESEARCH_RUN
```

Do not short-circuit output writing on invalid runs: write enough evidence to show why the run is invalid.

`m1_data_validation.csv` uses columns `Metric,Value,Pass` and must include at least:

```text
V3_QUALIFIED_SIGNALS
V3_ACCEPTED_ENTRIES
V3_CANCELLED_ENTRIES
V3_COMPLETED_PAIRED
V3_POINT_IN_TIME_INTEGRITY
BREADTH_SOURCE_ROWS
INDEX_SOURCE_ROWS
MEMBERSHIP_INTERVAL_ROWS
QUALIFIED_SIGNALS_WITH_EXACT_REGIME
FINAL_REQUIRED_EVIDENCE_PACKAGE
```

- [ ] **Step 3: Implement final required-output verification**

Missing/unreadable/required-column failure emits `MISSING_FINAL_EVIDENCE` or `INVALID_FINAL_EVIDENCE` and forces `INVALID_RESEARCH_RUN`.

Required minimum columns:

```python
FINAL_REQUIRED_COLUMNS = {
    "m1_data_validation.csv": ("Metric", "Value", "Pass"),
    "m1_regime_daily.csv": ("Date", "M1_Regime"),
    "m1_regime_audit.csv": ("Entry_ID", "Signal_Date", "Regime_Context_Date", "M1_Regime", "Exact_Date_Match"),
    "m1_signal_classification.csv": ("Entry_ID", "M1_Regime", "V3_Entry_Status"),
    "m1_enabled_entries.csv": ("Entry_ID",),
    "m1_enabled_cancellations.csv": ("Entry_ID",),
    "m1_disabled_shadow_entries.csv": ("Entry_ID",),
    "m1_disabled_shadow_cancellations.csv": ("Entry_ID",),
    "m1_setup_quality_trades.csv": ("Entry_ID", "Base_Net_Return"),
    "m1_practical_trades.csv": ("Entry_ID", "Base_Net_R"),
    "m1_disabled_setup_control.csv": ("Entry_ID", "Base_Net_Return"),
    "m1_disabled_practical_control.csv": ("Entry_ID", "Base_Net_R"),
    "m1_validation_summary.csv": ("Metric", "Value"),
    "m1_regime_comparison.csv": ("Enabled_Base_Mean_Net_R", "Disabled_Base_Mean_Net_R"),
    "m1_temporal_summary.csv": ("Period",),
    "m1_year_summary.csv": ("Signal_Year",),
    "m1_top_five_robustness.csv": ("Remaining_Mean_Base_Net_R", "Remaining_Base_R_PF"),
    "m1_leave_one_symbol_out.csv": ("Omitted_Symbol",),
    "m1_overlap_capacity_diagnostic.csv": ("Metric", "Dimension", "Value"),
    "m1_integrity_audit.csv": ("Violation",),
    "m1_validation_gates.csv": ("Gate", "Pass", "Mandatory"),
}
```

`research_report.md` must exist and be non-empty. CSV writers must preserve required headers even when a cohort is empty.

- [ ] **Step 4: Keep the report decision-focused and spec-complete**

`research_report.md` must conclude with exactly these sections:

```text
1. Frozen M1 hypothesis and rules
2. Source-artifact and PIT coverage/integrity
3. M1 regime distribution
4. Signal/cohort accounting
5. Base setup-quality results
6. Base practical results
7. Stress/severe friction results
8. Enabled-vs-disabled regime comparison
9. Temporal halves
10. Calendar-year diagnostics
11. Top-five-winner robustness
12. Leave-one-symbol-out robustness
13. Overlap/capacity diagnostics including clustering, partial-sector coverage and 1%-risk sizing
14. Integrity audit
15. Mandatory gate table
16. One formal final status and explicit next action
```

Next action text is frozen:

```text
PASS -> portfolio/execution validation
FAIL -> close M1 and proceed to Candidate 2
INSUFFICIENT_EVIDENCE -> do not loosen M1; proceed to Candidate 2
INVALID_RESEARCH_RUN -> fix only research integrity and rerun unchanged
```

Do not include rescue suggestions or alternate thresholds.

- [ ] **Step 5: Run focused M1 tests**

```bash
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests"
```

Expected: zero failures.

- [ ] **Step 6: Run V3 regression tests**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests"
```

Expected: zero failures.

- [ ] **Step 7: Prove V3 evidence was not modified**

Before and after the M1 run:

```bash
git status --short -- "Swing Trading/research/swing/strategy_v3_shallow_pullback"
```

Expected: no output.

Also inspect the implementation diff and confirm no files under the V3 module were changed.

- [ ] **Step 8: Run the complete research regression suite**

```bash
python -m pytest -q research/swing
```

If repository test discovery requires the `Swing Trading/...` path form in the executor's environment, use the existing repository convention and report the exact command actually run.

Expected: zero failures except already-known non-failing pytest-cache permission warnings.

- [ ] **Step 9: Generate the real frozen M1 evidence exactly once**

```bash
python "Swing Trading/research/swing/m1_regime_gated_momentum/run_m1_validation.py"
```

Do not inspect intermediate profitability and then change methodology before the final run.

- [ ] **Step 10: Mechanically verify final accounting**

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
no old Regime/Momentum_Regime field participates in eligibility
```

- [ ] **Step 11: Commit the completed validator + generated evidence**

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
- diagnostic regime/clustering/sector-mapping/capital coverage;
- final formal M1 status;
- paths to `m1_validation_gates.csv` and `research_report.md`;
- whether any V3 file changed (expected: **no**).

If the status is `FAIL` or `INSUFFICIENT_EVIDENCE`, do **not** propose a rescue. If `PASS`, do **not** start Candidate 2; hand off to Portfolio Advisor for portfolio/execution finalization.