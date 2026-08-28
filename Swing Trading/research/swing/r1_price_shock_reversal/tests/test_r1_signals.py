from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generate_r1_signals import (  # noqa: E402
    build_control_entries,
    build_low_volume_entries,
    classify_shock_row,
)


def test_shock_and_volume_boundaries_are_exact():
    assert classify_shock_row(pd.Series({"Shock_Score": -2.0, "Volume_Ratio": 1.0})) == "LOW_VOLUME"
    assert classify_shock_row(pd.Series({"Shock_Score": -2.0, "Volume_Ratio": 1.0001})) == "MIDDLE_VOLUME"
    assert classify_shock_row(pd.Series({"Shock_Score": -2.0, "Volume_Ratio": 1.5})) == "HIGH_VOLUME"
    assert classify_shock_row(pd.Series({"Shock_Score": -1.9999, "Volume_Ratio": 1.0})) == "NOT_ELIGIBLE_SHOCK"


def test_second_signal_before_unlock_is_cancelled_as_lockout():
    sessions = pd.bdate_range("2024-01-01", periods=12)
    signals = pd.DataFrame(
        [
            {
                "Signal_ID": "AAA-1",
                "Symbol": "AAA",
                "Signal_Date": sessions[0],
                "Low": 95.0,
                "ATR14_Signal": 4.0,
            },
            {
                "Signal_ID": "AAA-2",
                "Symbol": "AAA",
                "Signal_Date": sessions[3],
                "Low": 96.0,
                "ATR14_Signal": 4.0,
            },
        ]
    )
    prices = pd.DataFrame({"Date": sessions, "Open": [100.0] * 12})
    entries, cancellations = build_low_volume_entries(
        signals,
        {"AAA": prices},
        pd.DatetimeIndex(sessions),
    )

    assert entries["Signal_ID"].tolist() == ["AAA-1"]
    row = cancellations.loc[cancellations["Signal_ID"].eq("AAA-2")].iloc[0]
    assert row["Cancellation_Reason"] == "SAME_SYMBOL_LOCKOUT"


def test_entry_open_equal_to_structural_stop_is_cancelled():
    sessions = pd.bdate_range("2024-01-01", periods=8)
    signals = pd.DataFrame(
        [
            {
                "Signal_ID": "AAA-1",
                "Symbol": "AAA",
                "Signal_Date": sessions[0],
                "Low": 95.0,
                "ATR14_Signal": 4.0,
            }
        ]
    )
    prices = pd.DataFrame({"Date": sessions, "Open": [100.0, 94.0] + [100.0] * 6})
    entries, cancellations = build_low_volume_entries(
        signals,
        {"AAA": prices},
        pd.DatetimeIndex(sessions),
    )

    assert entries.empty
    assert cancellations.iloc[0]["Cancellation_Reason"] == "OPEN_BELOW_STRUCTURAL_STOP"


def test_control_entries_have_independent_lockout_and_no_structural_stop():
    sessions = pd.bdate_range("2024-01-01", periods=12)
    signals = pd.DataFrame(
        [
            {
                "Signal_ID": "AAA-1",
                "Symbol": "AAA",
                "Signal_Date": sessions[0],
                "Shock_Score": -2.5,
                "Volume_Ratio": 1.5,
                "Point_In_Time_Member": True,
                "Liquidity_OK": True,
                "Data_Eligible": True,
            },
            {
                "Signal_ID": "AAA-2",
                "Symbol": "AAA",
                "Signal_Date": sessions[3],
                "Shock_Score": -2.5,
                "Volume_Ratio": 1.5,
                "Point_In_Time_Member": True,
                "Liquidity_OK": True,
                "Data_Eligible": True,
            },
        ]
    )
    prices = pd.DataFrame({"Date": sessions, "Open": [100.0] * 12})

    controls = build_control_entries(
        signals,
        {"AAA": prices},
        pd.DatetimeIndex(sessions),
    )

    assert controls["Signal_ID"].tolist() == ["AAA-1"]
    assert "Structural_Stop" not in controls.columns

