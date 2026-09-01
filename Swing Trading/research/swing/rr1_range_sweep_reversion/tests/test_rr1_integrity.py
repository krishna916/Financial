from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_rr1_integrity import audit_lower_entry, audit_upper_reference  # noqa: E402


def valid_lower_case():
    sessions = pd.bdate_range("2024-01-01", periods=80)
    close = np.full(len(sessions), 105.0)
    high = np.full(len(sessions), 120.0)
    low = np.full(len(sessions), 100.0)
    open_ = np.full(len(sessions), 105.0)
    signal_position = 61
    low[signal_position] = 99.0
    close[signal_position] = 105.0
    open_[signal_position + 1] = 101.0
    prices = pd.DataFrame(
        {
            "Date": sessions,
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": np.full(len(sessions), 2_000_000.0),
        }
    )
    signal_date = sessions[signal_position]
    entry_date = sessions[signal_position + 1]
    scheduled_exit = sessions[signal_position + 16]
    entry = pd.Series(
        {
            "Entry_ID": "ENTRY|LOWER|AAA|2024-03-27",
            "Signal_ID": "LOWER|AAA|2024-03-27",
            "Symbol": "AAA",
            "Signal_Date": signal_date,
            "Entry_Date": entry_date,
            "Entry_Open": 101.0,
            "Range_Low": 100.0,
            "Range_High": 120.0,
            "Target": 110.0,
            "ATR14_Signal": 4.0,
            "Structural_Stop": 98.0,
            "Initial_Risk": 3.0,
            "Reward": 9.0,
            "Initial_RR": 3.0,
            "Scheduled_Exit_Date": scheduled_exit,
        }
    )
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Member_From": [sessions[0]],
            "Member_To": [sessions[-1]],
            "Downloadable": [True],
            "Yahoo_Ticker": ["AAA.NS"],
        }
    )
    benchmark = prices.assign(Open=200.0)
    return entry, prices, membership, benchmark, sessions


def test_audit_catches_range_low_using_signal_day():
    entry, prices, membership, benchmark, sessions = valid_lower_case()
    entry["Range_Low"] = prices.loc[
        prices.Date == entry.Signal_Date, "Low"
    ].iloc[0]
    failures = audit_lower_entry(entry, prices, membership, benchmark, sessions)
    assert any(x["Check"] == "RANGE_LOW_RECOMPUTE" and not x["Passed"] for x in failures)


def test_audit_catches_non_immediate_entry_date():
    entry, prices, membership, benchmark, sessions = valid_lower_case()
    entry["Entry_Date"] = sessions[sessions.get_loc(entry.Signal_Date) + 2]
    failures = audit_lower_entry(entry, prices, membership, benchmark, sessions)
    assert any(
        x["Check"] == "IMMEDIATE_NEXT_SESSION_ENTRY" and not x["Passed"]
        for x in failures
    )


def test_audit_accepts_upper_reference_without_available_t16():
    sessions = pd.bdate_range("2024-01-01", periods=80)
    signal_position = 70
    prices = pd.DataFrame(
        {
            "Date": sessions,
            "Open": np.full(len(sessions), 105.0),
            "High": np.full(len(sessions), 120.0),
            "Low": np.full(len(sessions), 100.0),
            "Close": np.full(len(sessions), 105.0),
            "Volume": np.full(len(sessions), 2_000_000.0),
        }
    )
    prices.loc[signal_position, "High"] = 121.0
    signal_date = sessions[signal_position]
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Member_From": [sessions[0]],
            "Member_To": [sessions[-1]],
            "Downloadable": [True],
            "Yahoo_Ticker": ["AAA.NS"],
        }
    )
    reference = pd.Series(
        {
            "Reference_ID": "REFERENCE|UPPER|AAA|2024-04-08",
            "Signal_ID": "UPPER|AAA|2024-04-08",
            "Symbol": "AAA",
            "Signal_Date": signal_date,
            "Entry_Date": sessions[signal_position + 1],
            "Entry_Open": 105.0,
            "Scheduled_Exit_Date": pd.NaT,
        }
    )

    failures = audit_upper_reference(reference, prices, membership, sessions)

    assert not any(
        x["Check"] == "SCHEDULED_T16" and not x["Passed"] for x in failures
    )
