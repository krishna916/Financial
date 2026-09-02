from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generate_rr1_signals import (  # noqa: E402
    build_lower_entries,
    build_upper_references,
    is_lower_signal,
    is_upper_signal,
    qualify_range_row,
    session_after,
)


def base_row(**overrides: object) -> pd.Series:
    row = {
        "Date": pd.Timestamp("2024-01-10"),
        "Symbol": "AAA",
        "Yahoo_Ticker": "AAA.NS",
        "Point_In_Time_Member": True,
        "Exact_Prehistory_61": True,
        "Range_Low": 100.0,
        "Range_High": 110.0,
        "Range_Mid": 105.0,
        "ER60": 0.20,
        "ER60_Denominator": 10.0,
        "Prior20_Median_Traded_Value": 100_000_000.0,
        "Open": 101.0,
        "High": 103.0,
        "Low": 99.0,
        "Close": 101.0,
        "Volume": 2_000_000.0,
        "ATR14": 4.0,
    }
    row.update(overrides)
    return pd.Series(row)


def lower_signal(
    signal_date: pd.Timestamp | None = None,
    signal_id: str = "LOWER|AAA|2024-01-10",
    **overrides: object,
) -> dict[str, object]:
    values = {
        "Date": signal_date or pd.Timestamp("2024-01-10"),
        "Low": 95.0,
        "Close": 101.0,
        "Range_Mid": 110.0,
        "ATR14": 4.0,
    }
    values.update(overrides)
    row = base_row(**values).to_dict()
    row["Signal_ID"] = signal_id
    row["Signal_Date"] = row.pop("Date")
    return row


def make_prices(sessions: pd.DatetimeIndex, entry_open: float = 99.0) -> pd.DataFrame:
    close = np.full(len(sessions), 101.0)
    frame = pd.DataFrame(
        {
            "Date": sessions,
            "Open": np.full(len(sessions), entry_open),
            "High": np.full(len(sessions), 103.0),
            "Low": np.full(len(sessions), 99.0),
            "Close": close,
            "Volume": np.full(len(sessions), 2_000_000.0),
        }
    )
    return frame


def test_er60_boundary_is_inclusive():
    row = base_row(ER60=0.25)
    ok, reason = qualify_range_row(row)
    assert ok is True
    assert reason == "QUALIFIED_RANGE"


def test_lower_signal_requires_strict_sweep_and_strict_reclaim():
    assert is_lower_signal(base_row(Low=99.99, Range_Low=100.0, Close=100.01)) is True
    assert is_lower_signal(base_row(Low=100.0, Range_Low=100.0, Close=100.01)) is False
    assert is_lower_signal(base_row(Low=99.99, Range_Low=100.0, Close=100.0)) is False


def test_upper_mirror_requires_strict_sweep_and_strict_rejection():
    assert is_upper_signal(base_row(High=110.01, Range_High=110.0, Close=109.99)) is True
    assert is_upper_signal(base_row(High=110.0, Range_High=110.0, Close=109.99)) is False
    assert is_upper_signal(base_row(High=110.01, Range_High=110.0, Close=110.0)) is False


def test_volume_momentum_and_regime_fields_do_not_change_signal():
    a = base_row(
        Low=99.0,
        Range_Low=100.0,
        Close=101.0,
        Volume_Ratio=0.2,
        RS_Percentile=5.0,
        Regime="HOSTILE",
    )
    b = a.copy()
    b["Volume_Ratio"] = 4.0
    b["RS_Percentile"] = 99.0
    b["Regime"] = "STRONG_MOMENTUM"
    assert is_lower_signal(a) is True
    assert is_lower_signal(b) is True


def test_initial_rr_boundary_is_inclusive():
    signal = lower_signal(Low=95.0, ATR14=4.0, Range_Mid=110.0, Close=101.0)
    sessions = pd.bdate_range("2024-01-10", periods=20)
    signal["Signal_Date"] = sessions[0]
    prices = make_prices(sessions, entry_open=99.33333333333333)
    entries, cancellations = build_lower_entries(
        pd.DataFrame([signal]), {"AAA": prices}, sessions
    )
    assert cancellations.empty
    assert entries.iloc[0]["Initial_RR"] == pytest.approx(2.0)


def test_lower_signal_on_scheduled_t16_session_is_allowed():
    sessions = pd.bdate_range("2024-01-01", periods=40)
    first = lower_signal(signal_date=sessions[0], signal_id="LOWER|AAA|1")
    second = lower_signal(signal_date=sessions[16], signal_id="LOWER|AAA|2")
    entries, cancellations = build_lower_entries(
        pd.DataFrame([first, second]), {"AAA": make_prices(sessions)}, sessions
    )
    assert entries["Signal_ID"].tolist() == ["LOWER|AAA|1", "LOWER|AAA|2"]
    assert cancellations.empty


def test_lower_signal_before_scheduled_t16_is_cancelled_by_lockout():
    sessions = pd.bdate_range("2024-01-01", periods=40)
    first = lower_signal(signal_date=sessions[0], signal_id="LOWER|AAA|1")
    second = lower_signal(signal_date=sessions[5], signal_id="LOWER|AAA|2")
    entries, cancellations = build_lower_entries(
        pd.DataFrame([first, second]), {"AAA": make_prices(sessions)}, sessions
    )
    assert len(entries) == 1
    assert cancellations.iloc[0]["Cancellation_Reason"] == "SAME_SYMBOL_LOCKOUT"


def test_upper_lockout_does_not_suppress_lower_signal():
    sessions = pd.bdate_range("2024-01-01", periods=40)
    upper = pd.DataFrame(
        [{
            "Signal_ID": "UPPER|AAA|1",
            "Symbol": "AAA",
            "Signal_Date": sessions[0],
        }]
    )
    lower = pd.DataFrame([lower_signal(signal_date=sessions[0])])
    upper_refs, upper_cancellations = build_upper_references(
        upper, {"AAA": make_prices(sessions)}, sessions
    )
    entries, lower_cancellations = build_lower_entries(
        lower, {"AAA": make_prices(sessions)}, sessions
    )
    assert len(upper_refs) == 1
    assert upper_cancellations.empty
    assert len(entries) == 1
    assert lower_cancellations.empty


def test_qualified_lower_equals_entries_plus_cancellations():
    sessions = pd.bdate_range("2024-01-01", periods=40)
    signals = pd.DataFrame(
        [
            lower_signal(signal_date=sessions[0], signal_id="LOWER|AAA|1"),
            lower_signal(signal_date=sessions[5], signal_id="LOWER|AAA|2"),
        ]
    )
    entries, cancellations = build_lower_entries(
        signals, {"AAA": make_prices(sessions)}, sessions
    )
    assert len(signals) == len(entries) + len(cancellations)
    assert set(entries["Signal_ID"]).isdisjoint(set(cancellations["Signal_ID"]))


def test_session_after_uses_canonical_session_steps():
    sessions = pd.bdate_range("2024-01-01", periods=3)
    assert session_after(sessions[0], sessions, 1) == sessions[1]
    assert session_after(sessions[0], sessions, 3) is None
