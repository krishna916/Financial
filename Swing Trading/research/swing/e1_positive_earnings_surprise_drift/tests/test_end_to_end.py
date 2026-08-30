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
from build_e1_events import build_event_master
from compute_e1_sue import build_sue_events
from load_e1_inputs import active_members_on, verify_manifest
from run_e1_validation import (
    _price_requirement_set_issues,
    build_integrity_audit,
    evaluate_gates,
    run_validation,
)
import build_e1_source_snapshot as source_snapshot  # noqa: E402


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


def test_price_requirement_set_match_and_mismatch_are_audited():
    classified = pd.DataFrame(
        {
            "Event_ID": ["E1", "E2", "BUFFER"],
            "Cohort": ["POSITIVE_SURPRISE", "NEGATIVE_CONTROL", "POSITIVE_BUFFER"],
        }
    )
    matching = pd.DataFrame({"Event_ID": ["E1", "E2"]})
    mismatching = pd.DataFrame({"Event_ID": ["E1", "EXTRA"]})

    assert _price_requirement_set_issues(classified, matching) == []
    issues = _price_requirement_set_issues(classified, mismatching)
    assert issues == [
        {
            "Check": "PRICE_REQUIREMENTS",
            "Violation": "PRICE_REQUIREMENT_SET_MISMATCH",
            "Count": 2,
            "Detail": "E2|EXTRA",
        }
    ]
    audit = build_integrity_audit(price_requirement_issues=issues)
    assert audit.to_dict("records") == issues


@pytest.mark.parametrize(
    ("requirement_ids", "expected_status", "expected_mismatch"),
    [([], "INVALID_RESEARCH_RUN", True), (["E1"], "INSUFFICIENT_EVIDENCE", False)],
)
def test_formal_validator_enforces_frozen_price_requirement_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    requirement_ids: list[str],
    expected_status: str,
    expected_mismatch: bool,
):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    empty_files = {
        "e1_exchange_filings_snapshot.csv": ["Symbol", "Fiscal_Period_End"],
        "e1_eps_snapshot.csv": ["Symbol", "Fiscal_Period_End", "EPS"],
        "e1_corporate_actions_snapshot.csv": ["Symbol", "Action_Type"],
        "e1_stock_prices_snapshot.csv": ["Symbol", "Date", "Open", "High", "Low", "Close", "Volume"],
        "e1_nifty500_prices_snapshot.csv": ["Date", "Open", "High", "Low", "Close"],
        "e1_price_identity_audit.csv": ["Research_Symbol", "Provider_Ticker", "Violation"],
        "e1_source_build_audit.csv": ["Violation", "Detail"],
    }
    manifest_rows = []
    for name, columns in empty_files.items():
        path = input_dir / name
        pd.DataFrame(columns=columns).to_csv(path, index=False)
        manifest_rows.append(
            {
                "Artifact": name,
                "SHA256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
                "Row_Count": 0,
            }
        )
    requirements = pd.DataFrame(
        [
            {
                "Event_ID": event_id,
                "Symbol": "AAA",
                "Cohort": "POSITIVE_SURPRISE",
                "SUE": 1.0,
                "Event_Public_Date": "2024-08-10",
                "Fiscal_Period_End": "2024-06-30",
            }
            for event_id in requirement_ids
        ],
        columns=["Event_ID", "Symbol", "Cohort", "SUE", "Event_Public_Date", "Fiscal_Period_End"],
    )
    requirement_path = input_dir / "e1_price_requirements.csv"
    requirements.to_csv(requirement_path, index=False)
    manifest_rows.append(
        {
            "Artifact": requirement_path.name,
            "SHA256": __import__("hashlib").sha256(requirement_path.read_bytes()).hexdigest(),
            "Row_Count": len(requirements),
        }
    )
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

    event_master = pd.DataFrame(
        {
            "Event_ID": ["E1"],
            "Symbol": ["AAA"],
            "Event_Public_Date": ["2024-08-10"],
            "Primary_Event": [True],
        }
    )
    classified = pd.DataFrame(
        {
            "Event_ID": ["E1"],
            "Symbol": ["AAA"],
            "Cohort": ["POSITIVE_SURPRISE"],
            "SUE": [1.0],
            "Event_Public_Date": ["2024-08-10"],
            "Fiscal_Period_End": ["2024-06-30"],
        }
    )
    coverage = pd.DataFrame(
        [{"Technical_EPS_Candidates": 1, "Resolved_EPS_Candidates": 1, "Machine_Readable_EPS_Resolution": 1.0}]
    )
    monkeypatch.setattr(
        "run_e1_validation.build_event_master",
        lambda filings, eps, membership, actions: (
            event_master,
            pd.DataFrame(columns=["Event_ID", "Reason"]),
            coverage,
            pd.DataFrame(),
        ),
    )
    monkeypatch.setattr(
        "run_e1_validation.build_sue_events",
        lambda events, eps, actions: (
            pd.DataFrame(),
            classified,
            classified,
            pd.DataFrame(columns=["Event_ID", "Reason"]),
        ),
    )
    monkeypatch.setattr(
        "run_e1_validation.build_primary_trades",
        lambda classified_events, stock_prices, index_prices, all_original_events: (
            {
                "POSITIVE_SURPRISE": pd.DataFrame(),
                "NEUTRAL_CONTROL": pd.DataFrame(),
                "NEGATIVE_CONTROL": pd.DataFrame(),
            },
            pd.DataFrame(columns=["Event_ID", "Symbol", "Cohort", "Reason"]),
        ),
    )

    status, _ = run_validation(input_dir, output_dir, membership_path=membership)

    assert status == expected_status
    integrity = pd.read_csv(output_dir / "e1_integrity_audit.csv")
    mismatch = integrity.loc[
        integrity["Violation"].eq("PRICE_REQUIREMENT_SET_MISMATCH")
    ]
    assert bool(not mismatch.empty) is expected_mismatch


def test_insufficient_sample_beats_strategy_fail():
    status, _ = evaluate_gates(
        integrity_count=0,
        technical_coverage=1.0,
        positive_count=299,
        neutral_count=500,
        negative_count=500,
    )
    assert status == "INSUFFICIENT_EVIDENCE"


def test_temporal_sample_insufficiency_precedes_strategy_fail():
    temporal = pd.DataFrame(
        [
            {"Period": "FIRST", "Completed_Count": 99},
            {"Period": "SECOND", "Completed_Count": 100},
        ]
    )
    status, _ = evaluate_gates(
        temporal=temporal,
        integrity_count=0,
        technical_coverage=1.0,
        positive_count=500,
        neutral_count=500,
        negative_count=500,
    )
    assert status == "INSUFFICIENT_EVIDENCE"

    temporal.loc[0, "Completed_Count"] = 100
    temporal.loc[1, "Completed_Count"] = 99
    status, _ = evaluate_gates(
        temporal=temporal,
        integrity_count=0,
        technical_coverage=1.0,
        positive_count=500,
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


def test_late_result_is_excluded_from_sue_and_trades():
    period_ends = pd.period_range("2021Q2", "2024Q2", freq="Q").to_timestamp(how="end").normalize()
    public_timestamp = "2024-08-20 10:00:00+05:30"
    filing = {
        "Symbol": "AAA",
        "Exchange": "NSE",
        "Feed": "legacy",
        "Fiscal_Period_End": period_ends[-1],
        "Fiscal_Quarter": "Q1",
        "Reporting_Basis": "CONSOLIDATED",
        "Quarterly_or_Annual": "QUARTERLY",
        "Original_or_Revised": "ORIGINAL",
        "Public_Timestamp": public_timestamp,
        "Source_URL": "https://example.test/late-result",
        "Source_Record_ID": "late-result",
        "Machine_Readable_URL": "https://example.test/late-result.xml",
    }
    filings = pd.DataFrame([filing])
    eps = pd.DataFrame(
        [
            {
                **filing,
                "Fiscal_Period_End": period_end,
                "Public_Timestamp": "2024-08-19 10:00:00+05:30",
                "Source_Record_ID": f"eps-{index}",
                "EPS": value,
                "EPS_Source_Resolved": True,
            }
            for index, (period_end, value) in enumerate(
                zip(period_ends, [1.0, 2.0, 4.0, 7.0, 11.0, 16.0, 22.0, 29.0, 37.0, 46.0, 56.0, 67.0, 79.0])
            )
        ]
    )
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Member_From": ["2020-01-01"],
            "Member_To": ["2026-12-31"],
        }
    )

    event_master, event_exclusions, _, _ = build_event_master(filings, eps, membership)
    sue_result = build_sue_events(event_master, eps, pd.DataFrame())
    sue_events = sue_result[1]
    classified = sue_result[2]
    event_id = event_master.loc[0, "Event_ID"]

    assert not bool(event_master.loc[0, "Primary_Event"])
    assert "LATE_RESULT" in event_exclusions["Reason"].tolist()
    assert event_id not in set(sue_events["Event_ID"])
    assert event_id not in set(classified["Event_ID"])


def test_formal_event_accounting_reconciles_to_sue_outcome_or_exclusion():
    event_id = "AAA-20240630-CONSOLIDATED"
    event_master = pd.DataFrame(
        [
            {
                "Event_ID": event_id,
                "Symbol": "AAA",
                "Event_Public_Date": pd.Timestamp("2024-08-10"),
                "Primary_Event": True,
            }
        ]
    )
    sue_exclusions = pd.DataFrame(
        [
            {
                "Event_ID": event_id,
                "Reason": "MISSING_CURRENT_EPS",
                "Exclusion_Stage": "SUE",
            }
        ]
    )

    audit = build_integrity_audit(
        event_master=event_master,
        sue_events=pd.DataFrame(columns=["Event_ID", "Cohort"]),
        event_exclusions=pd.DataFrame(columns=["Event_ID", "Reason"]),
        sue_exclusions=sue_exclusions,
    )

    assert not audit["Violation"].isin(
        ["FORMAL_EVENT_UNACCOUNTED", "FORMAL_EVENT_DOUBLE_ACCOUNTED"]
    ).any()


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
        "e1_price_identity_audit.csv": ["Research_Symbol", "Provider_Ticker", "Violation"],
        "e1_price_requirements.csv": ["Event_ID", "Symbol", "Cohort"],
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
    monkeypatch.setattr(source_snapshot, "download_adjusted_prices", network_called)
    monkeypatch.setattr(source_snapshot, "resolve_price_identity", network_called)
    status, _ = run_validation(input_dir, output_dir, membership_path=membership)
    assert status == "INVALID_RESEARCH_RUN"
    assert (output_dir / "e1_price_identity_audit.csv").exists() is False
    assert (output_dir / "e1_integrity_audit.csv").exists()
    integrity = pd.read_csv(output_dir / "e1_integrity_audit.csv")
    assert not integrity.get("Violation", pd.Series(dtype=str)).eq("MISSING_FINAL_EVIDENCE").any()
    assert (output_dir / "e1_data_validation.csv").exists()
    assert (output_dir / "research_report.md").read_text(encoding="utf-8").strip()
