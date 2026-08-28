from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyze_r1_results import (  # noqa: E402
    bootstrap_difference_ci,
    bootstrap_mean_ci,
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
