from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_r1_features import compute_r1_features  # noqa: E402
from analyze_r1_results import (  # noqa: E402
    REQUIRED_PRE_ANALYSIS_ARTIFACTS,
    bootstrap_difference_ci,
    bootstrap_mean_ci,
    count_integrity_violations,
    evaluate_gates,
    load_required_artifacts,
    overlap_diagnostics,
    regime_diagnostics,
    run_analysis,
    safe_profit_factor,
    sector_diagnostics,
    simulate_control_outcome,
    simulate_practical_trade,
    simulate_setup_quality_trade,
    forward_open_return,
)


def test_setup_exit_is_t_plus_6_open():
    dates = pd.bdate_range("2024-01-01", periods=7)
    prices = pd.DataFrame(
        {
            "Date": dates,
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
            "High": [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
            "Low": [99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
        }
    )
    entry = pd.Series(
        {
            "Entry_ID": "AAA-2024-01-01",
            "Signal_Date": dates[0],
            "Entry_Date": dates[1],
            "Entry_Open": 101.0,
            "Structural_Stop": 90.0,
        }
    )

    trade = simulate_setup_quality_trade(entry, prices, pd.DatetimeIndex(dates))

    assert trade["Exit_Date"] == dates[6]
    assert trade["Exit_Price"] == pytest.approx(106.0)
    assert trade["Holding_Sessions"] == 5


def test_practical_gap_below_stop_exits_at_actual_open():
    dates = pd.bdate_range("2024-01-01", periods=7)
    prices = pd.DataFrame(
        {
            "Date": dates,
            "Open": [100.0, 100.0, 100.0, 88.0, 100.0, 100.0, 100.0],
            "High": [101.0] * 7,
            "Low": [99.0, 95.0, 95.0, 87.0, 95.0, 95.0, 95.0],
        }
    )
    entry = pd.Series(
        {
            "Entry_ID": "AAA-1",
            "Signal_Date": dates[0],
            "Entry_Date": dates[1],
            "Entry_Open": 100.0,
            "Structural_Stop": 90.0,
        }
    )

    trade = simulate_practical_trade(entry, prices, pd.DatetimeIndex(dates))

    assert trade["Exit_Reason"] == "STOP_GAP"
    assert trade["Exit_Price"] == pytest.approx(88.0)
    assert trade["Gross_R"] == pytest.approx(-1.2)


def test_practical_entry_session_intraday_stop_exits_at_structural_stop():
    dates = pd.bdate_range("2024-01-01", periods=7)
    prices = pd.DataFrame(
        {
            "Date": dates,
            "Open": [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            "High": [101.0] * 7,
            "Low": [99.0, 89.0, 95.0, 95.0, 95.0, 95.0, 95.0],
        }
    )
    entry = pd.Series(
        {
            "Entry_ID": "AAA-1",
            "Signal_Date": dates[0],
            "Entry_Date": dates[1],
            "Entry_Open": 100.0,
            "Structural_Stop": 90.0,
        }
    )

    trade = simulate_practical_trade(entry, prices, pd.DatetimeIndex(dates))

    assert trade["Exit_Reason"] == "STOP_INTRADAY"
    assert trade["Exit_Date"] == dates[1]
    assert trade["Exit_Price"] == pytest.approx(90.0)


def test_practical_later_intraday_stop_precedes_fixed_exit():
    dates = pd.bdate_range("2024-01-01", periods=7)
    prices = pd.DataFrame(
        {
            "Date": dates,
            "Open": [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 106.0],
            "High": [101.0] * 7,
            "Low": [99.0, 95.0, 95.0, 89.0, 95.0, 95.0, 105.0],
        }
    )
    entry = pd.Series(
        {
            "Entry_ID": "AAA-1",
            "Signal_Date": dates[0],
            "Entry_Date": dates[1],
            "Entry_Open": 100.0,
            "Structural_Stop": 90.0,
        }
    )

    trade = simulate_practical_trade(entry, prices, pd.DatetimeIndex(dates))

    assert trade["Exit_Reason"] == "STOP_INTRADAY"
    assert trade["Exit_Date"] == dates[3]
    assert trade["Exit_Price"] == pytest.approx(90.0)


def test_control_outcome_uses_raw_fixed_horizon_without_stop():
    dates = pd.bdate_range("2024-01-01", periods=7)
    prices = pd.DataFrame(
        {
            "Date": dates,
            "Open": [100.0, 100.0, 100.0, 88.0, 100.0, 100.0, 106.0],
            "High": [101.0] * 7,
            "Low": [99.0, 95.0, 95.0, 87.0, 95.0, 95.0, 105.0],
        }
    )
    control = pd.Series(
        {
            "Entry_ID": "AAA-1",
            "Signal_Date": dates[0],
            "Entry_Date": dates[1],
            "Entry_Open": 100.0,
        }
    )

    outcome = simulate_control_outcome(control, prices, pd.DatetimeIndex(dates))

    assert outcome["Exit_Date"] == dates[6]
    assert outcome["Exit_Price"] == pytest.approx(106.0)
    assert outcome["Gross_Return"] == pytest.approx(0.06)
    assert "Structural_Stop" not in outcome


def test_forward_open_return_uses_entry_plus_holding_sessions():
    dates = pd.bdate_range("2024-01-01", periods=8)
    prices = pd.DataFrame({"Date": dates, "Open": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]})

    result = forward_open_return(101.0, dates[0], pd.DatetimeIndex(dates), prices, 5)

    assert result == pytest.approx(106.0 / 101.0 - 1.0)


def test_safe_profit_factor_boundaries():
    assert safe_profit_factor(pd.Series([2.0, -1.0])) == pytest.approx(2.0)
    assert safe_profit_factor(pd.Series([2.0, 1.0])) == np.inf
    assert safe_profit_factor(pd.Series([-2.0, -1.0])) == 0.0


def test_bootstrap_is_deterministic():
    values = pd.Series([0.01, 0.02, -0.01, 0.03])

    assert bootstrap_mean_ci(values) == bootstrap_mean_ci(values)


def test_bootstrap_difference_is_deterministic():
    low = pd.Series([0.03, 0.02, -0.01])
    high = pd.Series([0.01, -0.01, 0.0])

    assert bootstrap_difference_ci(low, high) == bootstrap_difference_ci(low, high)


def _audit_fixture():
    dates = pd.bdate_range("2024-01-01", periods=30)
    close = pd.Series([100.0 + index for index in range(21)] + [70.0] + [71.0] + [72.0] * 7)
    frame = pd.DataFrame(
        {
            "Date": dates,
            "Open": close,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": [1_000_000.0] * 21 + [500_000.0] + [1_000_000.0] * 8,
        }
    )
    features = compute_r1_features(frame)
    signal_date = dates[21]
    signal = features.loc[features["Date"].eq(signal_date)].iloc[0].to_dict()
    signal.update(
        {
            "Signal_ID": "AAA-2024-01-30",
            "Symbol": "AAA",
            "Signal_Date": signal_date,
            "Point_In_Time_Member": True,
            "Data_Eligible": True,
            "Liquidity_OK": True,
            "Cohort": "LOW_VOLUME",
        }
    )
    entry_date = dates[22]
    entry_bar = features.loc[features["Date"].eq(entry_date)].iloc[0]
    structural_stop = float(signal["Low"]) - 0.25 * float(signal["ATR14"])
    entry = pd.DataFrame(
        [
            {
                **signal,
                "Entry_ID": signal["Signal_ID"],
                "Entry_Date": entry_date,
                "Entry_Open": float(entry_bar["Open"]),
                "Structural_Stop": structural_stop,
                "Initial_Risk": float(entry_bar["Open"]) - structural_stop,
                "Scheduled_Exit_Date": dates[27],
            }
        ]
    )
    setup = pd.DataFrame(
        [{"Entry_ID": signal["Signal_ID"], "Symbol": "AAA", "Signal_Date": signal_date}]
    )
    practical = setup.copy()
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Member_From": [dates[0]],
            "Member_To": [dates[-1]],
            "Downloadable": [True],
            "Yahoo_Ticker": ["AAA.NS"],
        }
    )
    return (
        pd.DataFrame([signal]),
        entry,
        pd.DataFrame(columns=["Signal_ID", "Entry_ID", "Symbol", "Cancellation_Reason"]),
        setup,
        practical,
        pd.DataFrame(),
        {"AAA": features},
        membership,
        pd.DatetimeIndex(dates),
    )


def test_integrity_audit_recomputes_persisted_shock_score():
    args = list(_audit_fixture())
    args[0].loc[0, "Shock_Score"] = 0.0

    count, audit = count_integrity_violations(*args)

    assert count >= 1
    assert "SHOCK_SCORE_MISMATCH" in audit["Violation"].tolist()


def test_integrity_audit_recomputes_persisted_prior_volume():
    args = list(_audit_fixture())
    args[0].loc[0, "Prior20_Median_Volume"] = 1.0

    count, audit = count_integrity_violations(*args)

    assert count >= 1
    assert "PRIOR_VOLUME_MISMATCH" in audit["Violation"].tolist()


def _control_audit_fixture():
    dates = pd.bdate_range("2024-01-01", periods=30)
    close = pd.Series([100.0 + index for index in range(21)] + [70.0] + [71.0] + [72.0] * 7)
    frame = pd.DataFrame(
        {
            "Date": dates,
            "Open": close,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": [1_000_000.0] * 21 + [2_000_000.0] + [1_000_000.0] * 8,
        }
    )
    features = compute_r1_features(frame)
    signal_date = dates[21]
    signal = features.loc[features["Date"].eq(signal_date)].iloc[0].to_dict()
    signal.update(
        {
            "Signal_ID": "AAA-2024-01-30",
            "Symbol": "AAA",
            "Signal_Date": signal_date,
            "Point_In_Time_Member": True,
            "Data_Eligible": True,
            "Liquidity_OK": True,
            "Cohort": "HIGH_VOLUME",
        }
    )
    control = pd.DataFrame(
        [
            {
                "Entry_ID": signal["Signal_ID"],
                "Symbol": "AAA",
                "Signal_Date": signal_date,
                "Entry_Date": dates[22],
                "Entry_Open": float(features.loc[features["Date"].eq(dates[22]), "Open"].iloc[0]),
                "Exit_Date": dates[27],
                "Exit_Price": float(features.loc[features["Date"].eq(dates[27]), "Open"].iloc[0]),
                "Holding_Sessions": 5,
                "Gross_Return": 0.0,
                "Exit_Reason": "FIXED_HORIZON",
            }
        ]
    )
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Member_From": [dates[0]],
            "Member_To": [dates[-1]],
            "Downloadable": [True],
            "Yahoo_Ticker": ["AAA.NS"],
        }
    )
    return (
        pd.DataFrame([signal]),
        pd.DataFrame(
            columns=["Signal_ID", "Entry_ID", "Symbol", "Signal_Date", "Scheduled_Exit_Date"]
        ),
        pd.DataFrame(columns=["Signal_ID", "Entry_ID", "Symbol", "Cancellation_Reason"]),
        pd.DataFrame(),
        pd.DataFrame(),
        control,
        {"AAA": features},
        membership,
        pd.DatetimeIndex(dates),
    )


def test_control_audit_catches_non_member_on_signal_date():
    args = list(_control_audit_fixture())
    args[7] = args[7].copy()
    args[7]["Member_To"] = [pd.Timestamp(args[0].iloc[0]["Signal_Date"]) - pd.Timedelta(days=1)]

    count, audit = count_integrity_violations(*args)

    assert count >= 1
    assert "CONTROL_PIT_MEMBERSHIP_VIOLATION" in audit["Violation"].tolist()


@pytest.mark.parametrize(
    ("column", "violation"),
    [
        ("Sigma20", "CONTROL_SIGMA20_MISMATCH"),
        ("Shock_Score", "CONTROL_SHOCK_SCORE_MISMATCH"),
        ("Prior20_Median_Volume", "CONTROL_PRIOR_VOLUME_MISMATCH"),
        ("Volume_Ratio", "CONTROL_VOLUME_RATIO_MISMATCH"),
        ("Prior20_Median_Traded_Value", "CONTROL_PRIOR_TRADED_VALUE_MISMATCH"),
    ],
)
def test_control_audit_recomputes_persisted_threshold_evidence(column, violation):
    args = list(_control_audit_fixture())
    args[0] = args[0].copy()
    args[0].loc[0, column] = float(args[0].loc[0, column]) + 1.0

    count, audit = count_integrity_violations(*args)

    assert count >= 1
    assert violation in audit["Violation"].tolist()


def _write_required_artifacts(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, specification in REQUIRED_PRE_ANALYSIS_ARTIFACTS.items():
        pd.DataFrame(columns=specification["columns"]).to_csv(output_dir / filename, index=False)


def test_missing_required_entries_artifact_is_invalid(tmp_path):
    _write_required_artifacts(tmp_path)
    (tmp_path / "r1_entries.csv").unlink()

    status, _ = run_analysis(
        tmp_path,
        {},
        pd.DataFrame(columns=["Symbol", "Member_From", "Member_To"]),
        pd.bdate_range("2024-01-01", periods=10),
    )

    assert status == "INVALID_RESEARCH_RUN"
    _, artifact_audit = load_required_artifacts(tmp_path)
    row = artifact_audit.loc[artifact_audit["Violation"].eq("MISSING_REQUIRED_ARTIFACT")].iloc[0]
    assert row["Observed"].endswith("r1_entries.csv")


def test_malformed_required_artifact_is_invalid(tmp_path):
    _write_required_artifacts(tmp_path)
    pd.DataFrame({"wrong": ["column"]}).to_csv(tmp_path / "r1_entries.csv", index=False)

    status, _ = run_analysis(
        tmp_path,
        {},
        pd.DataFrame(columns=["Symbol", "Member_From", "Member_To"]),
        pd.bdate_range("2024-01-01", periods=10),
    )

    assert status == "INVALID_RESEARCH_RUN"
    _, artifact_audit = load_required_artifacts(tmp_path)
    assert "INVALID_REQUIRED_ARTIFACT" in artifact_audit["Violation"].tolist()


def test_valid_artifact_losing_strategy_remains_fail(tmp_path):
    _write_required_artifacts(tmp_path)

    _, artifact_audit = load_required_artifacts(tmp_path)
    args = list(_passing_gate_inputs(integrity_violations=len(artifact_audit)))
    args[0]["Gross_Return_Mean"] = -0.001
    status, _ = evaluate_gates(*args)

    assert len(artifact_audit) == 0
    assert status == "FAIL"


def test_overlap_diagnostics_reports_open_lifecycle_overlap():
    dates = pd.bdate_range("2024-01-01", periods=10)
    entries = pd.DataFrame(
        [
            {"Entry_ID": "AAA-1", "Symbol": "AAA", "Entry_Date": dates[1], "Scheduled_Exit_Date": dates[6]},
            {"Entry_ID": "BBB-1", "Symbol": "BBB", "Entry_Date": dates[2], "Scheduled_Exit_Date": dates[7]},
        ]
    )

    result = overlap_diagnostics(entries, pd.DatetimeIndex(dates))

    row = result.iloc[0]
    assert row["Accepted_Entries"] == 2
    assert row["Max_Simultaneous_Trades"] == 2
    assert row["Overlapping_Entries"] == 2
    assert row["Max_Same_Day_Entries"] == 1


def test_overlap_diagnostics_uses_exact_one_percent_risk_weight():
    dates = pd.bdate_range("2024-01-01", periods=10)
    entries = pd.DataFrame(
        [
            {
                "Entry_ID": "AAA-1",
                "Symbol": "AAA",
                "Entry_Date": dates[1],
                "Scheduled_Exit_Date": dates[6],
                "Entry_Open": 100.0,
                "Initial_Risk": 5.0,
            }
        ]
    )

    result = overlap_diagnostics(entries, pd.DatetimeIndex(dates))

    row = result.iloc[0]
    assert row["Median_Implied_Position_Weight"] == pytest.approx(0.2)
    assert row["Max_Implied_Position_Weight"] == pytest.approx(0.2)
    assert row["Max_Simultaneous_Implied_Gross_Capital"] == pytest.approx(0.2)


def test_sector_diagnostics_keeps_unmapped_symbols_out_of_mapped_concentration():
    entries = pd.DataFrame(
        [
            {"Entry_ID": "AAA-1", "Symbol": "AAA"},
            {"Entry_ID": "BBB-1", "Symbol": "BBB"},
        ]
    )
    mapping = pd.DataFrame({"Stock": ["AAA"], "Sector_Key": ["BANK"]})

    result = sector_diagnostics(entries, mapping)

    assert result.loc[result["Metric"].eq("MAPPED_ACCEPTED_ENTRIES"), "Value"].iloc[0] == 1
    assert result.loc[result["Metric"].eq("UNMAPPED_ACCEPTED_ENTRIES"), "Value"].iloc[0] == 1
    assert result.loc[result["Metric"].eq("MAPPING_COVERAGE_PERCENT"), "Value"].iloc[0] == pytest.approx(50.0)
    assert result.loc[result["Metric"].eq("MAPPED_ENTRY_COUNT"), "Sector_Key"].tolist() == ["BANK"]
    assert result.loc[result["Metric"].eq("UNMAPPED_ENTRY_COUNT"), "Sector_Key"].tolist() == ["UNMAPPED"]


def test_regime_diagnostics_uses_signal_date_without_future_lookup():
    signal_date = pd.Timestamp("2024-01-02")
    setup = pd.DataFrame(
        [
            {
                "Entry_ID": "AAA-1",
                "Signal_Date": signal_date,
                "Gross_Return": 0.02,
                "Base_Net_Return": 0.01,
            }
        ]
    )
    regime = pd.DataFrame(
        {
            "Date": [signal_date + pd.Timedelta(days=1)],
            "Regime": ["RISK_ON"],
        }
    )

    result = regime_diagnostics(setup, regime)

    risk_on = result.loc[result["Regime"].eq("RISK_ON")].iloc[0]
    assert risk_on["Completed_Trades"] == 0


def test_diagnostics_do_not_change_mandatory_gate_rows():
    args = _passing_gate_inputs()
    before_status, before_gates = evaluate_gates(*args)
    entries = pd.DataFrame(
        [
            {
                "Entry_ID": "AAA-1",
                "Symbol": "AAA",
                "Entry_Date": pd.Timestamp("2024-01-02"),
                "Scheduled_Exit_Date": pd.Timestamp("2024-01-09"),
                "Entry_Open": 100.0,
                "Initial_Risk": 5.0,
            }
        ]
    )
    overlap_diagnostics(entries, pd.bdate_range("2024-01-01", periods=10))
    sector_diagnostics(entries, pd.DataFrame({"Stock": ["AAA"], "Sector_Key": ["BANK"]}))
    regime_diagnostics(
        pd.DataFrame(
            [
                {
                    "Entry_ID": "AAA-1",
                    "Signal_Date": pd.Timestamp("2024-01-01"),
                    "Gross_Return": 0.02,
                    "Base_Net_Return": 0.01,
                }
            ]
        ),
        pd.DataFrame({"Date": [pd.Timestamp("2024-01-01")], "Regime": ["RISK_ON"]}),
    )
    after_status, after_gates = evaluate_gates(*args)

    assert before_status == after_status
    pd.testing.assert_frame_equal(before_gates, after_gates)


def _passing_gate_inputs(completed_count=300, integrity_violations=0):
    metrics = {
        "Gross_Return_Mean": 0.01,
        "Base_Net_Mean_Return": 0.002,
        "Base_Net_Return_PF": 1.20,
        "Stress_Net_Mean_Return": 0.001,
        "Stress_Net_Return_PF": 1.01,
        "Base_Net_Mean_R": 0.15,
        "Base_Net_R_PF": 1.20,
    }
    temporal = pd.DataFrame(
        {
            "Period": ["FIRST_HALF", "SECOND_HALF"],
            "Base_Net_Mean_Return": [0.001, 0.001],
            "Base_Net_Return_PF": [1.01, 1.01],
        }
    )
    outlier = pd.DataFrame(
        [{"Base_Net_Mean_Return": 0.001, "Base_Net_Return_PF": 1.01}]
    )
    loso = pd.DataFrame(
        [{"Omitted_Symbol": "AAA", "Base_Net_Mean_Return": 0.001, "Base_Net_Return_PF": 1.01}]
    )
    control = pd.DataFrame(
        [
            {
                "Low_Volume_Gross_Mean_Return": 0.02,
                "High_Volume_Gross_Mean_Return": 0.01,
                "Low_Volume_Gross_PF": 2.0,
                "High_Volume_Gross_PF": 1.0,
            }
        ]
    )
    return (
        metrics,
        temporal,
        outlier,
        loso,
        control,
        completed_count,
        integrity_violations,
    )


def test_integrity_failure_has_invalid_status_precedence():
    status, _ = evaluate_gates(*_passing_gate_inputs(integrity_violations=1))

    assert status == "INVALID_RESEARCH_RUN"


def test_sample_count_299_has_insufficient_evidence_status():
    status, _ = evaluate_gates(*_passing_gate_inputs(completed_count=299))

    assert status == "INSUFFICIENT_EVIDENCE"


def test_exact_setup_mean_and_pf_boundaries_pass():
    status, gates = evaluate_gates(*_passing_gate_inputs())

    assert status == "PASS"
    assert bool(gates.loc[gates["Gate"].eq("BASE_NET_SETUP_MEAN"), "Pass"].iloc[0])
    assert bool(gates.loc[gates["Gate"].eq("BASE_NET_SETUP_PF"), "Pass"].iloc[0])


def test_exact_stress_zero_boundary_fails():
    args = list(_passing_gate_inputs())
    args[0]["Stress_Net_Mean_Return"] = 0.0

    status, gates = evaluate_gates(*args)

    assert status == "FAIL"
    assert not bool(gates.loc[gates["Gate"].eq("STRESS_NET_SETUP_MEAN"), "Pass"].iloc[0])


def test_exact_practical_boundaries_pass():
    status, gates = evaluate_gates(*_passing_gate_inputs())

    assert status == "PASS"
    assert bool(gates.loc[gates["Gate"].eq("BASE_PRACTICAL_MEAN_R"), "Pass"].iloc[0])
    assert bool(gates.loc[gates["Gate"].eq("BASE_PRACTICAL_R_PF"), "Pass"].iloc[0])
