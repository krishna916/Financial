from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_r1_features import compute_r1_features  # noqa: E402
from analyze_r1_results import (  # noqa: E402
    bootstrap_difference_ci,
    bootstrap_mean_ci,
    count_integrity_violations,
    evaluate_gates,
    overlap_diagnostics,
    safe_profit_factor,
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
