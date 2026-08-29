import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fixtures import write_minimal_v3_package
from load_frozen_sources import load_v3_artifacts
from partition_m1_cohorts import partition_v3_evidence


def classification_fixture():
    return pd.DataFrame(
        [
            {"Entry_ID": "AAA-2024-01-02", "Symbol": "AAA", "Signal_Date": pd.Timestamp("2024-01-02"), "M1_Regime": "MOMENTUM_ENABLED"},
            {"Entry_ID": "BBB-2024-01-03", "Symbol": "BBB", "Signal_Date": pd.Timestamp("2024-01-03"), "M1_Regime": "MOMENTUM_DISABLED"},
            {"Entry_ID": "CCC-2024-01-04", "Symbol": "CCC", "Signal_Date": pd.Timestamp("2024-01-04"), "M1_Regime": "MOMENTUM_DISABLED"},
        ]
    )


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
