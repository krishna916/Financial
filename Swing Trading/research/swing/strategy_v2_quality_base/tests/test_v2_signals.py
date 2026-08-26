import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generate_v2_signals import (  # noqa: E402
    build_entries,
    scan_symbol_bases,
    validate_signal_integrity,
)


def make_valid_base_frame() -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=73, freq="D")
    rows = []
    for i, date in enumerate(dates):
        if i < 62:
            high, low, close, tr = 90.0, 88.0, 89.0, 2.0
        elif i == 62:
            high, low, close, tr = 100.0, 98.0, 99.0, 2.0
        elif 63 <= i <= 67:
            high, low, close, tr = 99.0, 95.0, 98.0, 4.0
        elif 68 <= i <= 71:
            high, low, close, tr = 99.0, 97.0, 98.5, 2.0
        else:
            high, low, close, tr = 102.0, 98.0, 101.0, 4.0
        rows.append(
            {
                "Date": date,
                "Open": close,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": 2_000_000.0,
                "True_Range": tr,
                "ATR14": 2.0,
                "SMA20": 95.0,
                "SMA50": 95.0,
                "SMA200": 90.0,
                "Median_Traded_Value_20": 200_000_000.0,
                "RS21": 80.0,
                "RS63": 80.0,
                "RS126": 80.0,
                "Composite_RS": 80.0,
                "RS_Coverage": 1.0,
                "RS_Research_Safe": True,
                "Point_In_Time_Member": True,
                "Breakout_Volume_Ratio": 1.0,
            }
        )
    return pd.DataFrame(rows)


def test_valid_breakout_occurs_on_base_session_ten():
    audit, candidates = scan_symbol_bases("AAA", make_valid_base_frame())
    assert len(candidates) == 1
    row = candidates.iloc[0]
    assert row["Base_Age"] == 10
    assert row["Active_Pivot"] == 100.0
    assert row["Contraction_Ratio"] == 0.6
    assert bool(row["Signal_Qualified"])
    assert "BREAKOUT_CANDIDATE" in set(audit["Event"])


def test_failed_probe_raises_pivot_without_resetting_age():
    frame = make_valid_base_frame()
    frame.loc[67, ["High", "Close"]] = [101.0, 99.0]
    frame.loc[72, ["High", "Close"]] = [103.0, 102.0]
    audit, candidates = scan_symbol_bases("AAA", frame)
    probe = audit[audit["Event"] == "FAILED_PROBE"].iloc[0]
    assert probe["Base_Age"] == 5
    assert probe["New_Pivot"] == 101.0
    assert candidates.iloc[0]["Base_Age"] == 10
    assert candidates.iloc[0]["Active_Pivot"] == 101.0


def test_failed_probe_rechecks_depth_using_raised_pivot():
    frame = make_valid_base_frame()
    frame.loc[67, ["High", "Low", "Close"]] = [104.0, 95.0, 99.0]
    audit, candidates = scan_symbol_bases("AAA", frame)
    events_on_probe_day = audit.loc[
        audit["Date"] == frame.loc[67, "Date"], "Event"
    ].tolist()
    assert events_on_probe_day == ["FAILED_PROBE", "DEPTH_INVALIDATED"]
    assert len(candidates) == 0


def test_breakout_before_ten_sessions_is_too_short():
    frame = make_valid_base_frame()
    frame.loc[71, ["High", "Close"]] = [101.0, 101.0]
    audit, candidates = scan_symbol_bases("AAA", frame)
    assert candidates.empty
    assert "TOO_SHORT_BREAKOUT" in set(audit["Event"])


def test_breakout_at_session_thirty_is_valid():
    frame = make_valid_base_frame()
    extra_dates = pd.date_range(frame["Date"].iloc[-1] + pd.Timedelta(days=1), periods=20)
    extra = frame.iloc[[-1] * len(extra_dates)].copy().reset_index(drop=True)
    extra["Date"] = extra_dates
    extra["High"] = 99.0
    extra["Low"] = 97.0
    extra["Close"] = 98.5
    extra["Open"] = 98.5
    extra["True_Range"] = 2.0
    frame = pd.concat([frame, extra], ignore_index=True)
    frame.loc[72, ["High", "Close"]] = [99.0, 98.5]
    frame.loc[92, ["High", "Close"]] = [102.0, 101.0]
    audit, candidates = scan_symbol_bases("AAA", frame)
    assert candidates.iloc[0]["Base_Age"] == 30
    assert "BREAKOUT_CANDIDATE" in set(audit["Event"])


def test_base_expires_after_session_thirty_without_breakout():
    frame = make_valid_base_frame()
    extra_dates = pd.date_range(frame["Date"].iloc[-1] + pd.Timedelta(days=1), periods=20)
    extra = frame.iloc[[-1] * len(extra_dates)].copy().reset_index(drop=True)
    extra["Date"] = extra_dates
    extra["High"] = 99.0
    extra["Low"] = 97.0
    extra["Close"] = 98.5
    extra["Open"] = 98.5
    extra["True_Range"] = 2.0
    frame = pd.concat([frame, extra], ignore_index=True)
    frame.loc[72, ["High", "Close"]] = [99.0, 98.5]
    audit, candidates = scan_symbol_bases("AAA", frame)
    assert candidates.empty
    assert "EXPIRED" in set(audit["Event"])


def test_too_short_breakout_can_seed_a_new_base_on_the_same_bar():
    frame = make_valid_base_frame()
    frame.loc[71, ["High", "Close"]] = [110.0, 101.0]
    audit, candidates = scan_symbol_bases("AAA", frame)
    events = audit.loc[audit["Date"] == frame.loc[71, "Date"], "Event"].tolist()
    assert events == ["TOO_SHORT_BREAKOUT", "SEEDED"]
    assert candidates.empty


def test_entry_uses_only_immediate_next_market_session():
    signals = pd.DataFrame(
        [
            {
                "Entry_ID": "AAA-2023-08-10",
                "Symbol": "AAA",
                "Signal_Date": pd.Timestamp("2023-08-10"),
                "Active_Pivot": 100.0,
                "ATR14_Signal": 4.0,
                "Final_5_Prebreakout_Low": 98.0,
                "Signal_Qualified": True,
            }
        ]
    )
    prices = {
        "AAA": pd.DataFrame(
            {
                "Date": pd.to_datetime(["2023-08-11", "2023-08-14"]),
                "Open": [101.0, 102.0],
                "High": [103.0, 104.0],
                "Low": [99.0, 100.0],
                "Close": [102.0, 103.0],
            }
        )
    }
    sessions = pd.DatetimeIndex(
        pd.to_datetime(["2023-08-10", "2023-08-11", "2023-08-14"])
    )
    accepted, cancelled = build_entries(signals, prices, sessions)
    assert cancelled.empty
    assert accepted.iloc[0]["Entry_Date"] == pd.Timestamp("2023-08-11")
    assert accepted.iloc[0]["Entry_Open"] == 101.0
    assert accepted.iloc[0]["Structural_Stop"] == 97.0


def test_missing_immediate_symbol_bar_cancels_instead_of_delaying():
    signals = pd.DataFrame(
        [
            {
                "Entry_ID": "AAA-2023-08-10",
                "Symbol": "AAA",
                "Signal_Date": pd.Timestamp("2023-08-10"),
                "Active_Pivot": 100.0,
                "ATR14_Signal": 4.0,
                "Final_5_Prebreakout_Low": 98.0,
                "Signal_Qualified": True,
            }
        ]
    )
    prices = {
        "AAA": pd.DataFrame(
            {
                "Date": pd.to_datetime(["2023-08-14"]),
                "Open": [101.0],
                "High": [103.0],
                "Low": [99.0],
                "Close": [102.0],
            }
        )
    }
    sessions = pd.DatetimeIndex(
        pd.to_datetime(["2023-08-10", "2023-08-11", "2023-08-14"])
    )
    accepted, cancelled = build_entries(signals, prices, sessions)
    assert accepted.empty
    assert cancelled.iloc[0]["Cancellation_Reason"] == "MISSING_NEXT_SESSION_BAR"


def _entry_signal(entry_open: float, stop_low: float = 98.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Entry_ID": "AAA-2023-08-10",
                "Symbol": "AAA",
                "Signal_Date": pd.Timestamp("2023-08-10"),
                "Active_Pivot": 100.0,
                "ATR14_Signal": 4.0,
                "Final_5_Prebreakout_Low": stop_low,
                "Signal_Qualified": True,
            }
        ]
    )


def _entry_prices(open_price: float) -> dict[str, pd.DataFrame]:
    return {
        "AAA": pd.DataFrame(
            {
                "Date": pd.to_datetime(["2023-08-11"]),
                "Open": [open_price],
                "High": [open_price + 2.0],
                "Low": [open_price - 2.0],
                "Close": [open_price + 1.0],
            }
        )
    }


def test_entry_cancellation_reason_is_open_below_pivot():
    _, cancelled = build_entries(
        _entry_signal(99.0), _entry_prices(99.0), pd.to_datetime(["2023-08-10", "2023-08-11"])
    )
    assert cancelled.iloc[0]["Cancellation_Reason"] == "OPEN_BELOW_PIVOT"


def test_entry_cancellation_reason_is_open_above_extension_limit():
    _, cancelled = build_entries(
        _entry_signal(105.0), _entry_prices(105.0), pd.to_datetime(["2023-08-10", "2023-08-11"])
    )
    assert cancelled.iloc[0]["Cancellation_Reason"] == "OPEN_ABOVE_EXTENSION_LIMIT"


def test_entry_cancellation_reason_is_stop_not_below_entry():
    _, cancelled = build_entries(
        _entry_signal(101.0, stop_low=102.0),
        _entry_prices(101.0),
        pd.to_datetime(["2023-08-10", "2023-08-11"]),
    )
    assert cancelled.iloc[0]["Cancellation_Reason"] == "STOP_NOT_BELOW_ENTRY"


def test_entry_cancellation_reason_is_stop_too_wide():
    _, cancelled = build_entries(
        _entry_signal(101.0, stop_low=80.0),
        _entry_prices(101.0),
        pd.to_datetime(["2023-08-10", "2023-08-11"]),
    )
    assert cancelled.iloc[0]["Cancellation_Reason"] == "STOP_TOO_WIDE"


def test_signal_integrity_rejects_delayed_entry():
    signals = pd.DataFrame(
        [
            {
                "Entry_ID": "AAA-2023-08-10",
                "Symbol": "AAA",
                "Signal_Date": pd.Timestamp("2023-08-10"),
                "Active_Pivot": 100.0,
                "ATR14_Signal": 4.0,
                "Final_5_Prebreakout_Low": 98.0,
                "Signal_Qualified": True,
                "Membership_OK": True,
                "RS_Coverage": 1.0,
                "Composite_RS": 80.0,
                "Base_Age": 10,
                "Contraction_Ratio": 0.6,
                "Signal_Extension_ATR": 0.5,
            }
        ]
    )
    entries = pd.DataFrame(
        [
            {
                "Entry_ID": "AAA-2023-08-10",
                "Signal_Date": pd.Timestamp("2023-08-10"),
                "Entry_Date": pd.Timestamp("2023-08-14"),
                "Entry_Open": 101.0,
                "Active_Pivot": 100.0,
                "ATR14_Signal": 4.0,
                "Structural_Stop": 97.0,
            }
        ]
    )
    with pytest.raises(AssertionError, match="immediate next"):
        validate_signal_integrity(
            signals, entries, pd.to_datetime(["2023-08-10", "2023-08-11", "2023-08-14"])
        )
