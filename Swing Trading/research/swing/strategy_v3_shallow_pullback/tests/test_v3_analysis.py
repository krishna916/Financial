import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyze_v3_results import (  # noqa: E402
    attach_prior_breadth,
    count_point_in_time_violations,
    safe_profit_factor,
    simulate_practical_trade,
    simulate_setup_quality_trade,
    validate_trade_integrity,
)


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


def test_validate_trade_integrity_rejects_lens_mismatch():
    with pytest.raises(AssertionError, match="Entry_ID"):
        validate_trade_integrity(
            pd.DataFrame({"Entry_ID": ["A"]}),
            pd.DataFrame({"Entry_ID": ["B"]}),
        )
