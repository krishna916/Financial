from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_rr1_integrity import (  # noqa: E402
    audit_cohort_lockout,
    audit_lower_entry,
    audit_upper_outcome,
    audit_upper_reference,
)


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


def valid_upper_case():
    sessions = pd.bdate_range("2024-01-01", periods=80)
    close = np.array([105.0 + (i % 2) for i in range(len(sessions))], dtype=float)
    high = np.full(len(sessions), 110.0)
    low = np.full(len(sessions), 100.0)
    open_ = close.copy()
    volume = np.full(len(sessions), 2_000_000.0)
    signal_position = 61
    high[signal_position] = 111.0
    close[signal_position] = 105.0

    prices = pd.DataFrame(
        {
            "Date": sessions,
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
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
    reference = pd.Series(
        {
            "Reference_ID": "REFERENCE|UPPER|AAA|fixture",
            "Signal_ID": "UPPER|AAA|fixture",
            "Symbol": "AAA",
            "Signal_Date": sessions[signal_position],
            "Entry_Date": sessions[signal_position + 1],
            "Entry_Open": float(open_[signal_position + 1]),
            "Scheduled_Exit_Date": sessions[signal_position + 16],
        }
    )
    return reference, prices, membership, sessions


def _failed_checks(rows):
    return {row["Check"] for row in rows if not row["Passed"]}


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


def test_upper_audit_rejects_non_range_structure():
    reference, prices, membership, sessions = valid_upper_case()
    signal_pos = sessions.get_loc(reference.Signal_Date)
    prices.loc[signal_pos - 60 : signal_pos - 1, "Low"] = 110.0
    rows = audit_upper_reference(reference, prices, membership, sessions)
    assert "UPPER_RANGE_QUALIFICATION" in _failed_checks(rows)


def test_upper_audit_rejects_er60_above_threshold():
    reference, prices, membership, sessions = valid_upper_case()
    signal_pos = sessions.get_loc(reference.Signal_Date)
    prices.loc[signal_pos - 61 : signal_pos - 1, "Close"] = np.linspace(
        100.0, 160.0, 61
    )
    rows = audit_upper_reference(reference, prices, membership, sessions)
    assert "UPPER_ER60_QUALIFICATION" in _failed_checks(rows)


def test_upper_audit_rejects_insufficient_liquidity():
    reference, prices, membership, sessions = valid_upper_case()
    signal_pos = sessions.get_loc(reference.Signal_Date)
    prices.loc[signal_pos - 20 : signal_pos - 1, "Volume"] = 1_000.0
    rows = audit_upper_reference(reference, prices, membership, sessions)
    assert "UPPER_LIQUIDITY_QUALIFICATION" in _failed_checks(rows)


def test_upper_audit_rejects_wrong_next_session_entry_open():
    reference, prices, membership, sessions = valid_upper_case()
    reference["Entry_Open"] = float(reference["Entry_Open"]) + 1.0

    rows = audit_upper_reference(reference, prices, membership, sessions)

    assert "UPPER_ENTRY_OPEN_RECOMPUTE" in _failed_checks(rows)


def valid_upper_outcome_case():
    reference, prices, membership, sessions = valid_upper_case()
    exit_date = sessions[sessions.get_loc(reference.Signal_Date) + 16]
    actual_entry_open = float(
        prices.loc[prices.Date.eq(reference.Entry_Date), "Open"].iloc[0]
    )
    actual_exit_open = float(
        prices.loc[prices.Date.eq(exit_date), "Open"].iloc[0]
    )
    outcome = pd.Series(
        {
            "Reference_ID": reference["Reference_ID"],
            "Signal_ID": reference["Signal_ID"],
            "Symbol": reference["Symbol"],
            "Signal_Date": reference["Signal_Date"],
            "Entry_Date": reference["Entry_Date"],
            "Exit_Date": exit_date,
            "Entry_Open": actual_entry_open,
            "Exit_Price": actual_exit_open,
            "Mirror_Gross_Return_15": actual_exit_open / actual_entry_open - 1.0,
        }
    )
    return reference, outcome, prices, sessions


def test_upper_outcome_audit_rejects_corrupted_mirror_return():
    reference, outcome, prices, sessions = valid_upper_outcome_case()
    outcome["Mirror_Gross_Return_15"] = float(outcome["Mirror_Gross_Return_15"]) + 0.01

    rows = audit_upper_outcome(reference, outcome, prices, sessions)

    assert "UPPER_OUTCOME_GROSS_RETURN" in _failed_checks(rows)


def test_lockout_audit_rejects_second_accepted_lower_inside_t16():
    sessions = pd.bdate_range("2024-01-01", periods=40)
    signals = pd.DataFrame(
        [
            {"Signal_ID": "LOWER|AAA|1", "Symbol": "AAA", "Signal_Date": sessions[0]},
            {"Signal_ID": "LOWER|AAA|2", "Symbol": "AAA", "Signal_Date": sessions[5]},
        ]
    )
    accepted = pd.DataFrame(
        [
            {
                "Signal_ID": "LOWER|AAA|1",
                "Symbol": "AAA",
                "Signal_Date": sessions[0],
                "Scheduled_Exit_Date": sessions[16],
            },
            {
                "Signal_ID": "LOWER|AAA|2",
                "Symbol": "AAA",
                "Signal_Date": sessions[5],
                "Scheduled_Exit_Date": sessions[21],
            },
        ]
    )
    cancellations = pd.DataFrame(
        columns=["Signal_ID", "Symbol", "Signal_Date", "Cancellation_Reason"]
    )

    rows = audit_cohort_lockout(signals, accepted, cancellations, sessions, "LOWER")

    assert "LOWER_LOCKOUT_REPLAY" in _failed_checks(rows)


def test_lockout_audit_requires_same_symbol_lockout_reason_inside_window():
    sessions = pd.bdate_range("2024-01-01", periods=40)
    signals = pd.DataFrame(
        [
            {"Signal_ID": "UPPER|AAA|1", "Symbol": "AAA", "Signal_Date": sessions[0]},
            {"Signal_ID": "UPPER|AAA|2", "Symbol": "AAA", "Signal_Date": sessions[5]},
        ]
    )
    accepted = pd.DataFrame(
        [
            {
                "Signal_ID": "UPPER|AAA|1",
                "Symbol": "AAA",
                "Signal_Date": sessions[0],
                "Scheduled_Exit_Date": sessions[16],
            }
        ]
    )
    cancellations = pd.DataFrame(
        [
            {
                "Signal_ID": "UPPER|AAA|2",
                "Symbol": "AAA",
                "Signal_Date": sessions[5],
                "Cancellation_Reason": "MISSING_NEXT_SESSION_BAR",
            }
        ]
    )

    rows = audit_cohort_lockout(signals, accepted, cancellations, sessions, "UPPER")

    assert "UPPER_LOCKOUT_REPLAY" in _failed_checks(rows)


def test_lockout_audit_allows_new_signal_on_scheduled_t16():
    sessions = pd.bdate_range("2024-01-01", periods=40)
    signals = pd.DataFrame(
        [
            {"Signal_ID": "LOWER|AAA|1", "Symbol": "AAA", "Signal_Date": sessions[0]},
            {"Signal_ID": "LOWER|AAA|2", "Symbol": "AAA", "Signal_Date": sessions[16]},
        ]
    )
    accepted = pd.DataFrame(
        [
            {
                "Signal_ID": "LOWER|AAA|1",
                "Symbol": "AAA",
                "Signal_Date": sessions[0],
                "Scheduled_Exit_Date": sessions[16],
            },
            {
                "Signal_ID": "LOWER|AAA|2",
                "Symbol": "AAA",
                "Signal_Date": sessions[16],
                "Scheduled_Exit_Date": sessions[32],
            },
        ]
    )
    cancellations = pd.DataFrame(
        columns=["Signal_ID", "Symbol", "Signal_Date", "Cancellation_Reason"]
    )

    rows = audit_cohort_lockout(signals, accepted, cancellations, sessions, "LOWER")

    assert all(row["Passed"] for row in rows)
