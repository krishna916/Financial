import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fixtures import write_minimal_v3_package
from load_frozen_sources import load_v3_artifacts, validate_frozen_v3_accounting


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
    audit = pd.concat(
        [loader_audit, validate_frozen_v3_accounting(artifacts)], ignore_index=True
    )
    assert "V3_PIT_INTEGRITY_NOT_CLEAN" in audit["Violation"].tolist()


def test_frozen_v3_accounting_reconciles_qualified_accepted_cancelled_and_completed(tmp_path):
    write_minimal_v3_package(tmp_path)
    artifacts, loader_audit = load_v3_artifacts(tmp_path)
    accounting_audit = validate_frozen_v3_accounting(artifacts)
    assert loader_audit.empty
    assert accounting_audit.empty
