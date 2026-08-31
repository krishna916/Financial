from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from build_e1_trades import (  # noqa: E402
    build_trade_for_event,
    canonical_sessions,
    next_distinct_quarterly_result,
    next_session_after,
    scheduled_exit_session,
)
from build_e1_events import build_quarterly_exit_event_calendar  # noqa: E402


def test_canonical_sessions_accepts_schema_empty_market_input():
    assert canonical_sessions(pd.DataFrame()).empty


def test_entry_is_immediate_next_session_and_exit_is_after_40_complete_sessions():
    sessions = pd.bdate_range("2024-01-01", periods=50)
    entry = next_session_after(sessions[0], sessions)
    assert entry == sessions[1]
    assert scheduled_exit_session(entry, sessions, 40) == sessions[41]


def _prices(open_values: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=len(open_values))
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": open_values,
            "High": [value + 2.0 for value in open_values],
            "Low": [value - 2.0 for value in open_values],
            "Close": open_values,
            "Volume": [1000.0] * len(open_values),
        }
    )


def _event(public_timestamp: str = "2024-01-01 10:00:00+05:30") -> pd.Series:
    return pd.Series(
        {
            "Event_ID": "AAA-20231231-CONSOLIDATED",
            "Symbol": "AAA",
            "SUE": 1.5,
            "Cohort": "POSITIVE_SURPRISE",
            "Event_Public_Date": pd.Timestamp("2024-01-01"),
            "Event_Public_Timestamp": pd.Timestamp(public_timestamp),
        }
    )


def test_large_positive_entry_gap_does_not_cancel_trade():
    stock = _prices([100.0] + [120.0] + [121.0] * 40 + [122.0])
    index = stock[["Date", "Open", "High", "Low", "Close"]].assign(Open=100.0)
    trade, reason = build_trade_for_event(_event(), stock, index, pd.DataFrame())
    assert reason == ""
    assert trade is not None
    assert trade["Entry_Open"] == 120.0
    assert trade["Entry_Gap"] > 0.19


def test_next_quarterly_result_truncates_even_when_late_and_unusable():
    stock = _prices([100.0] + [101.0] * 12 + [102.0] * 40)
    index = stock[["Date", "Open", "High", "Low", "Close"]].assign(Open=100.0)
    next_event = pd.Series(
        {
            "Event_ID": "AAA-20240331-CONSOLIDATED",
            "Symbol": "AAA",
            "Fiscal_Period_End": pd.Timestamp("2024-03-31"),
            "Event_Public_Timestamp": pd.Timestamp("2024-01-10 10:00:00+05:30"),
            "Original_or_Revised": "ORIGINAL",
            "Timely_Result": False,
            "EPS_Source_Status": "UNRESOLVED",
        }
    )
    trade, reason = build_trade_for_event(
        _event(), stock, index, pd.DataFrame([_event(), next_event])
    )
    assert reason == ""
    assert trade is not None
    assert trade["Exit_Reason"] == "EXIT_NEXT_EARNINGS_EVENT"
    assert trade["Exit_Date"] == pd.Timestamp("2024-01-11")
    assert trade["Holding_Sessions"] == 7


def test_exit_calendar_truncates_for_late_unscored_quarter_without_basis_or_sue():
    stock = _prices([100.0] + [101.0] * 12 + [102.0] * 87)
    index = stock[["Date", "Open", "High", "Low", "Close"]].assign(Open=100.0)
    filings = pd.DataFrame(
        [
            {
                "Symbol": "AAA",
                "Fiscal_Period_End": "2023-12-31",
                "Fiscal_Quarter": "Q4",
                "Public_Timestamp": "2024-04-10 10:00:00+05:30",
                "Original_or_Revised": "ORIGINAL",
                "Quarterly_or_Annual": "QUARTERLY",
            },
        ]
    )
    exit_calendar = build_quarterly_exit_event_calendar(filings, {"AAA"})
    event = _event("2024-03-01 10:00:00+05:30")
    event["Event_Public_Date"] = pd.Timestamp("2024-03-01")

    trade, reason = build_trade_for_event(
        event, stock, index, exit_calendar
    )

    assert reason == ""
    assert trade is not None
    assert trade["Exit_Reason"] == "EXIT_NEXT_EARNINGS_EVENT"
    assert trade["Exit_Date"] == pd.Timestamp("2024-04-11")


def test_next_distinct_quarterly_result_ignores_same_event_and_revisions():
    events = pd.DataFrame(
        [
            {
                "Symbol": "AAA",
                "Fiscal_Period_End": pd.Timestamp("2023-12-31"),
                "Event_Public_Timestamp": pd.Timestamp("2024-01-02", tz="Asia/Kolkata"),
                "Original_or_Revised": "ORIGINAL",
            },
            {
                "Symbol": "AAA",
                "Fiscal_Period_End": pd.Timestamp("2023-12-31"),
                "Event_Public_Timestamp": pd.Timestamp("2024-01-03", tz="Asia/Kolkata"),
                "Original_or_Revised": "REVISED",
            },
            {
                "Symbol": "AAA",
                "Fiscal_Period_End": pd.Timestamp("2024-03-31"),
                "Event_Public_Timestamp": pd.Timestamp("2024-05-01", tz="Asia/Kolkata"),
                "Original_or_Revised": "ORIGINAL",
            },
        ]
    )
    result = next_distinct_quarterly_result(
        "AAA", pd.Timestamp("2024-01-02", tz="Asia/Kolkata"), events
    )
    assert result is not None
    assert result["Fiscal_Period_End"] == pd.Timestamp("2024-03-31")


def _market_frame(dates: pd.DatetimeIndex, open_value: float = 100.0) -> pd.DataFrame:
    values = [open_value] * len(dates)
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": values,
            "High": [value + 2.0 for value in values],
            "Low": [value - 2.0 for value in values],
            "Close": values,
            "Volume": [1000.0] * len(values),
        }
    )


def test_missing_stock_bar_on_immediate_canonical_entry_session_cancels():
    sessions = pd.bdate_range("2024-01-01", periods=45)
    stock = _market_frame(sessions.delete(1))
    index = _market_frame(sessions).drop(columns=["Volume"])

    trade, reason = build_trade_for_event(_event(), stock, index, pd.DataFrame())

    assert trade is None
    assert reason == "NO_VALID_NEXT_SESSION_OPEN"


def test_holding_period_uses_canonical_sessions_when_stock_bar_is_missing():
    sessions = pd.bdate_range("2024-01-01", periods=50)
    stock = _market_frame(sessions.delete(10))
    index = _market_frame(sessions).drop(columns=["Volume"])

    trade, reason = build_trade_for_event(_event(), stock, index, pd.DataFrame())

    assert reason == ""
    assert trade is not None
    assert trade["Exit_Date"] == sessions[41]
    assert trade["Holding_Sessions"] == 40


def test_missing_stock_bar_on_exact_canonical_exit_cancels():
    sessions = pd.bdate_range("2024-01-01", periods=50)
    stock = _market_frame(sessions.delete(41))
    index = _market_frame(sessions).drop(columns=["Volume"])

    trade, reason = build_trade_for_event(_event(), stock, index, pd.DataFrame())

    assert trade is None
    assert reason == "NO_VALID_EXIT_OPEN"
