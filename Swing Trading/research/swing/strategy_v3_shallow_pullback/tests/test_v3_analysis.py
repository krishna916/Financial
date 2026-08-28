import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyze_v3_results import (  # noqa: E402
    attach_prior_breadth,
    count_point_in_time_violations,
    evaluate_gates,
    _analysis_extra_dates,
    leave_one_symbol_out,
    overlap_diagnostic,
    outlier_robustness,
    pullback_diagnostics,
    safe_profit_factor,
    simulate_practical_trade,
    simulate_setup_quality_trade,
    validate_trade_integrity,
    year_summary,
)


def test_analysis_extra_dates_is_empty_for_entries_without_2026_08_26():
    result = _analysis_extra_dates(pd.DataFrame({"Entry_Date": [pd.Timestamp("2024-01-11")]}))
    assert isinstance(result, pd.DatetimeIndex)
    assert result.empty


def setup_entry() -> pd.Series:
    return pd.Series(
        {
            "Entry_ID": "AAA-1",
            "Symbol": "AAA",
            "Entry_Date": pd.Timestamp("2024-01-10"),
            "Entry_Open": 100.0,
            "Structural_Stop": 95.0,
        }
    )


def setup_prices() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-10", "2024-01-11", "2024-01-12"]),
            "Open": [100.0, 101.0, 99.0],
            "High": [102.0, 102.0, 100.0],
            "Low": [99.0, 96.0, 98.0],
            "Close": [101.0, 97.0, 99.0],
            "SMA20": [98.0, 98.0, 98.0],
        }
    )


def test_setup_quality_exits_next_open_after_close_below_sma20():
    result = simulate_setup_quality_trade(setup_entry(), setup_prices())
    assert result["Exit_Signal_Date"] == pd.Timestamp("2024-01-11")
    assert result["Exit_Date"] == pd.Timestamp("2024-01-12")
    assert result["Exit_Price"] == 99.0
    assert result["Exit_Reason"] == "SMA20"


def test_practical_scheduled_sma20_exit_precedes_same_day_stop():
    prices = setup_prices()
    prices.loc[0, "Close"] = 97.0
    prices.loc[1, ["Open", "Low"]] = [90.0, 88.0]
    result = simulate_practical_trade(setup_entry(), prices)
    assert result["Exit_Price"] == 90.0
    assert result["Exit_Reason"] == "SMA20"


def test_practical_gap_stop_exits_at_open_and_can_be_worse_than_minus_one_r():
    prices = setup_prices()
    prices.loc[1, ["Open", "Low", "Close"]] = [90.0, 88.0, 90.0]
    result = simulate_practical_trade(setup_entry(), prices)
    assert result["Exit_Reason"] == "STOP_GAP"
    assert result["Exit_Price"] == 90.0
    assert result["R_Multiple"] == -2.0


def test_practical_intraday_stop_exits_at_fixed_stop():
    prices = setup_prices()
    prices.loc[1, ["Open", "Low", "Close"]] = [100.0, 94.0, 100.0]
    result = simulate_practical_trade(setup_entry(), prices)
    assert result["Exit_Reason"] == "STOP_INTRADAY"
    assert result["Exit_Price"] == 95.0
    assert result["R_Multiple"] == -1.0


def test_safe_profit_factor_handles_wins_losses_and_empty_inputs():
    assert safe_profit_factor(pd.Series([0.1, -0.05])) == 2.0
    assert safe_profit_factor(pd.Series([0.1])) == np.inf
    assert safe_profit_factor(pd.Series([-0.1])) == 0.0
    assert pd.isna(safe_profit_factor(pd.Series(dtype=float)))


def test_breadth_join_forbids_equal_entry_date():
    trades = pd.DataFrame({"Entry_ID": ["A"], "Entry_Date": [pd.Timestamp("2024-01-10")]})
    breadth = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-09", "2024-01-10"]),
            "Regime": ["PRIOR", "EQUAL"] ,
        }
    )
    joined = attach_prior_breadth(trades, breadth)
    assert joined.loc[0, "Breadth_Matched_Date"] == pd.Timestamp("2024-01-09")
    assert joined.loc[0, "Regime"] == "PRIOR"


def _pit_fixture():
    signal = {
        "Entry_ID": "AAA-2024-01-10",
        "Symbol": "AAA",
        "Leader_Date": pd.Timestamp("2024-01-05"),
        "Signal_Date": pd.Timestamp("2024-01-10"),
        "Signal_Qualified": True,
        "Seed_RS_Coverage_OK": True,
        "Seed_RS_OK": True,
        "Signal_RS_Coverage_OK": True,
        "Composite_RS": 80.0,
        "RS_Coverage": 1.0,
        "Seed_RS_Coverage": 1.0,
        "Seed_Composite_RS": 80.0,
    }
    entry = {
        **signal,
        "Entry_Date": pd.Timestamp("2024-01-11"),
        "Entry_Open": 99.0,
        "Structural_Stop": 95.0,
    }
    trade = {
        **entry,
        "Breadth_Matched_Date": pd.Timestamp("2024-01-10"),
        "Return": 0.01,
        "R_Multiple": 0.2,
    }
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Member_From": [pd.Timestamp("2023-01-01")],
            "Member_To": [pd.Timestamp("2025-01-01")],
            "Downloadable": [True],
        }
    )
    sessions = pd.bdate_range("2023-07-03", "2024-01-12")
    return (
        pd.DataFrame([signal]),
        pd.DataFrame([entry]),
        pd.DataFrame([trade]),
        pd.DataFrame([trade]),
        membership,
        pd.DatetimeIndex(sessions),
    )


def test_point_in_time_audit_reports_zero_for_valid_artifacts():
    signals, entries, setup, practical, membership, sessions = _pit_fixture()
    count, audit = count_point_in_time_violations(
        signals, entries, setup, practical, membership, sessions
    )
    assert count == 0
    assert audit.empty


@pytest.mark.parametrize(
    ("target", "column", "value", "expected"),
    [
        ("signal", "Leader_Date", pd.Timestamp("2024-01-10"), "LEADER_NOT_BEFORE_SIGNAL"),
        ("entry", "Entry_Date", pd.Timestamp("2024-01-10"), "SIGNAL_NOT_BEFORE_ENTRY"),
        ("signal", "Signal_Date", pd.Timestamp("2023-07-31"), "SIGNAL_OUTSIDE_PRIMARY_WINDOW"),
        ("signal", "Leader_Date", pd.Timestamp("2023-07-17"), "PREWINDOW_SEED_TOO_EARLY"),
        ("setup", "Breadth_Matched_Date", pd.Timestamp("2024-01-11"), "BREADTH_NOT_STRICT_PRIOR_SETUP"),
    ],
)
def test_point_in_time_audit_detects_timing_mutations(target, column, value, expected):
    signals, entries, setup, practical, membership, sessions = _pit_fixture()
    artifacts = {"signal": signals, "entry": entries, "setup": setup, "practical": practical}
    artifacts[target].loc[0, column] = value
    count, audit = count_point_in_time_violations(
        signals, entries, setup, practical, membership, sessions
    )
    assert count > 0
    assert expected in set(audit["Violation"])


def test_point_in_time_audit_detects_membership_rs_and_lens_mutations():
    mutations = [
        ("SEED_INACTIVE_MEMBER", "membership", "Member_From", pd.Timestamp("2024-01-06")),
        ("SIGNAL_INACTIVE_MEMBER", "membership", "Member_To", pd.Timestamp("2024-01-09")),
        ("SEED_RS_COVERAGE_UNSAFE", "signal", "Seed_RS_Coverage_OK", False),
        ("SIGNAL_RS_COVERAGE_UNSAFE", "signal", "Signal_RS_Coverage_OK", False),
        ("SEED_RS_BELOW_THRESHOLD", "signal", "Seed_RS_OK", False),
        ("SIGNAL_RS_BELOW_THRESHOLD", "signal", "Composite_RS", 69.9),
    ]
    for expected, target, column, value in mutations:
        signals, entries, setup, practical, membership, sessions = _pit_fixture()
        if target == "signal":
            signals.loc[0, column] = value
        else:
            membership.loc[0, column] = value
        count, audit = count_point_in_time_violations(
            signals, entries, setup, practical, membership, sessions
        )
        assert count > 0
        assert expected in set(audit["Violation"]), expected

    signals, entries, setup, practical, membership, sessions = _pit_fixture()
    entries.loc[0, "Entry_Date"] = pd.Timestamp("2024-01-12")
    count, audit = count_point_in_time_violations(
        signals, entries, setup, practical, membership, sessions
    )
    assert "ENTRY_NOT_IMMEDIATE_NEXT_SESSION" in set(audit["Violation"])

    signals, entries, setup, practical, membership, sessions = _pit_fixture()
    practical = practical.iloc[0:0].copy()
    count, audit = count_point_in_time_violations(
        signals, entries, setup, practical, membership, sessions
    )
    assert "LENS_ENTRY_ID_MISMATCH" in set(audit["Violation"])


def test_pit_audit_checks_numeric_seed_rs_coverage_even_when_boolean_is_true():
    signals, entries, setup, practical, membership, sessions = _pit_fixture()
    signals.loc[0, "Seed_RS_Coverage_OK"] = True
    signals.loc[0, "Seed_RS_Coverage"] = 0.79

    count, audit = count_point_in_time_violations(
        signals, entries, setup, practical, membership, sessions
    )

    assert count > 0
    assert "SEED_RS_COVERAGE_UNSAFE" in set(audit["Violation"])


def test_pit_audit_checks_numeric_seed_composite_rs_even_when_boolean_is_true():
    signals, entries, setup, practical, membership, sessions = _pit_fixture()
    signals.loc[0, "Seed_RS_OK"] = True
    signals.loc[0, "Seed_Composite_RS"] = 69.9

    count, audit = count_point_in_time_violations(
        signals, entries, setup, practical, membership, sessions
    )

    assert count > 0
    assert "SEED_RS_BELOW_THRESHOLD" in set(audit["Violation"])


def test_validate_trade_integrity_rejects_lens_mismatch():
    with pytest.raises(AssertionError, match="Entry_ID"):
        validate_trade_integrity(
            pd.DataFrame({"Entry_ID": ["A"]}),
            pd.DataFrame({"Entry_ID": ["B"]}),
        )


def _trade_rows(count: int, *, return_value: float = 0.02, r_value: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    setup = pd.DataFrame(
        {
            "Entry_ID": [f"A-{index}" for index in range(count)],
            "Symbol": [f"S{index % 5}" for index in range(count)],
            "Entry_Date": pd.date_range("2023-01-01", periods=count, freq="D"),
            "Return": [return_value] * count,
        }
    )
    practical = setup.assign(R_Multiple=r_value)
    return setup, practical


def test_overlap_diagnostic_counts_all_accepted_entries_including_incomplete():
    entries = pd.DataFrame(
        {
            "Entry_ID": ["A", "B", "C"],
            "Symbol": ["AAA", "AAA", "BBB"],
            "Entry_Date": pd.to_datetime(["2024-01-10", "2024-01-11", "2024-01-11"]),
        }
    )
    practical = pd.DataFrame(
        {
            "Entry_ID": ["A", "B"],
            "Exit_Date": pd.to_datetime(["2024-01-12", "2024-01-13"]),
        }
    )
    result = overlap_diagnostic(entries, practical).iloc[0]
    assert result["Total_Accepted_Entries"] == 3
    assert result["Max_Simultaneous_Signal_Level_Trades"] >= 2


def test_temporal_gate_uses_only_locked_setup_year_conditions():
    setup_2023, practical_2023 = _trade_rows(20)
    setup_2024, practical_2024 = _trade_rows(20)
    setup_2024["Entry_Date"] = pd.date_range("2024-01-01", periods=20, freq="D")
    setup = pd.concat([setup_2023, setup_2024], ignore_index=True)
    setup.loc[setup.groupby(setup["Entry_Date"].dt.year).cumcount() >= 15, "Return"] = -0.01
    practical = pd.concat([practical_2023, practical_2024], ignore_index=True)
    practical["Entry_Date"] = setup["Entry_Date"]
    practical["R_Multiple"] = -0.25
    gates = evaluate_gates(setup, practical, point_in_time_violations=0)
    temporal = gates.loc[gates["Gate"].eq("TEMPORAL_ROBUSTNESS")].iloc[0]
    assert temporal["Value"] == 2
    assert bool(temporal["Passed"])


def test_final_status_is_insufficient_below_one_hundred_and_fail_at_one_hundred_negative():
    setup, practical = _trade_rows(99)
    gates = evaluate_gates(setup, practical, point_in_time_violations=0)
    assert gates.loc[gates["Gate"].eq("FINAL_STATUS"), "Status"].iloc[0] == "INSUFFICIENT_EVIDENCE"
    setup, practical = _trade_rows(100, return_value=-0.01, r_value=-0.25)
    gates = evaluate_gates(setup, practical, point_in_time_violations=0)
    assert gates.loc[gates["Gate"].eq("FINAL_STATUS"), "Status"].iloc[0] == "FAIL"


def test_pullback_diagnostics_use_fixed_buckets_without_gate_columns():
    entries = pd.DataFrame(
        {
            "Entry_ID": ["A", "B"],
            "Pullback_Age": [3, 10],
            "Pullback_Depth_ATR": [0.75, 2.5],
            "Composite_RS": [75.0, 95.0],
            "Resumption_Volume_Ratio": [0.7, np.nan],
            "Entry_Open": [100.0, 101.0],
            "Leader_Close": [100.0, 100.0],
            "ATR14_Signal": [4.0, 4.0],
        }
    )
    setup = entries.assign(Return=[0.02, -0.01])
    practical = entries.assign(R_Multiple=[0.2, -0.5])
    diagnostics = pullback_diagnostics(entries, setup, practical)
    assert set(diagnostics["Dimension"]) == {
        "Pullback_Age",
        "Pullback_Depth_ATR",
        "Composite_RS",
        "Resumption_Volume_Ratio",
        "Entry_Extension_ATR_vs_Leader",
    }
    assert "Gate" not in diagnostics.columns
