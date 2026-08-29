from pathlib import Path
import sys

import pandas as pd
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from constants import (
    FIRST_HALF_END,
    PRIMARY_END,
    PRIMARY_START,
    SECOND_HALF_START,
    SOURCE_CUTOFF,
)
from load_e1_inputs import active_members_on, verify_manifest
from run_e1_validation import evaluate_gates, run_validation


def test_frozen_windows_are_exact():
    assert PRIMARY_START == pd.Timestamp("2023-08-01")
    assert PRIMARY_END == pd.Timestamp("2026-06-30")
    assert SOURCE_CUTOFF == pd.Timestamp("2026-08-25")
    assert FIRST_HALF_END == pd.Timestamp("2025-01-14")
    assert SECOND_HALF_START == pd.Timestamp("2025-01-15")


def test_active_members_on_uses_inclusive_membership_boundaries():
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Member_From": [pd.Timestamp("2024-01-02")],
            "Member_To": [pd.Timestamp("2024-01-05")],
        }
    )
    assert active_members_on(membership, pd.Timestamp("2024-01-02"))["Symbol"].tolist() == ["AAA"]
    assert active_members_on(membership, pd.Timestamp("2024-01-05"))["Symbol"].tolist() == ["AAA"]


def test_verify_manifest_rejects_hash_mismatch(tmp_path: Path):
    source = tmp_path / "a.csv"
    source.write_text("x\n1\n", encoding="utf-8")
    manifest = pd.DataFrame(
        [
            {
                "Artifact": "a.csv",
                "SHA256": "0" * 64,
                "Row_Count": 1,
            }
        ]
    )
    audit = verify_manifest(manifest, tmp_path)
    assert "HASH_MISMATCH" in audit["Violation"].tolist()


def test_integrity_failure_beats_every_profitability_gate():
    status, _ = evaluate_gates(
        integrity_count=1,
        technical_coverage=1.0,
        positive_count=500,
        neutral_count=500,
        negative_count=500,
    )
    assert status == "INVALID_RESEARCH_RUN"


def test_insufficient_sample_beats_strategy_fail():
    status, _ = evaluate_gates(
        integrity_count=0,
        technical_coverage=1.0,
        positive_count=299,
        neutral_count=500,
        negative_count=500,
    )
    assert status == "INSUFFICIENT_EVIDENCE"


def test_technical_coverage_boundary_is_frozen():
    below, _ = evaluate_gates(
        integrity_count=0,
        technical_coverage=0.949999,
        positive_count=500,
        neutral_count=500,
        negative_count=500,
    )
    exact, _ = evaluate_gates(
        integrity_count=0,
        technical_coverage=0.95,
        positive_count=500,
        neutral_count=500,
        negative_count=500,
    )
    assert below == "INVALID_RESEARCH_RUN"
    assert exact != "INVALID_RESEARCH_RUN"


def test_formal_validator_is_offline_against_frozen_fixture_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    empty_files = {
        "e1_exchange_filings_snapshot.csv": ["Symbol", "Fiscal_Period_End"],
        "e1_eps_snapshot.csv": ["Symbol", "Fiscal_Period_End", "EPS"],
        "e1_corporate_actions_snapshot.csv": ["Symbol", "Action_Type"],
        "e1_stock_prices_snapshot.csv": ["Symbol", "Date", "Open", "High", "Low", "Close", "Volume"],
        "e1_nifty500_prices_snapshot.csv": ["Date", "Open", "High", "Low", "Close"],
        "e1_source_build_audit.csv": ["Violation", "Detail"],
    }
    manifest_rows = []
    for name, columns in empty_files.items():
        path = input_dir / name
        pd.DataFrame(columns=columns).to_csv(path, index=False)
        manifest_rows.append({
            "Artifact": name,
            "SHA256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
            "Row_Count": 0,
        })
    pd.DataFrame(manifest_rows).to_csv(input_dir / "e1_source_manifest.csv", index=False)
    membership = tmp_path / "membership.csv"
    pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Member_From": ["2020-01-01"],
            "Member_To": ["2026-12-31"],
            "Yahoo_Ticker": ["AAA.NS"],
            "Downloadable": [True],
        }
    ).to_csv(membership, index=False)

    def network_called(*args, **kwargs):
        raise AssertionError("network called")

    monkeypatch.setattr("requests.Session.get", network_called)
    monkeypatch.setattr("requests.get", network_called)
    status, _ = run_validation(input_dir, output_dir, membership_path=membership)
    assert status == "INVALID_RESEARCH_RUN"
    assert (output_dir / "e1_integrity_audit.csv").exists()
    integrity = pd.read_csv(output_dir / "e1_integrity_audit.csv")
    assert not integrity.get("Violation", pd.Series(dtype=str)).eq("MISSING_FINAL_EVIDENCE").any()
    assert (output_dir / "e1_data_validation.csv").exists()
    assert (output_dir / "research_report.md").read_text(encoding="utf-8").strip()
