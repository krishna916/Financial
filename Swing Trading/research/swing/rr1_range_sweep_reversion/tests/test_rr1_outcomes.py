from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulate_rr1_outcomes import (  # noqa: E402
    build_outcomes,
    simulate_lens_a,
    simulate_practical,
)


def make_entry(
    signal_date: pd.Timestamp = pd.Timestamp("2024-01-01"),
    entry_date: pd.Timestamp = pd.Timestamp("2024-01-02"),
    scheduled_exit: pd.Timestamp = pd.Timestamp("2024-01-24"),
    entry_open: float = 100.0,
    stop: float = 95.0,
    target: float = 110.0,
) -> pd.Series:
    return pd.Series(
        {
            "Entry_ID": "ENTRY|LOWER|AAA|2024-01-01",
            "Signal_ID": "LOWER|AAA|2024-01-01",
            "Symbol": "AAA",
            "Signal_Date": signal_date,
            "Entry_Date": entry_date,
            "Entry_Open": entry_open,
            "Target": target,
            "Structural_Stop": stop,
            "Initial_Risk": entry_open - stop,
            "Initial_RR": (target - entry_open) / (entry_open - stop),
            "Scheduled_Exit_Date": scheduled_exit,
        }
    )


def make_bars(
    dates: pd.DatetimeIndex,
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    closes: list[float] | None = None,
) -> pd.DataFrame:
    n = len(dates)
    opens = opens or [100.0] * n
    highs = highs or [105.0] * n
    lows = lows or [99.0] * n
    closes = closes or opens
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": [2_000_000.0] * n,
        }
    )


def make_benchmark(dates: pd.DatetimeIndex) -> pd.DataFrame:
    return make_bars(dates, opens=[200.0] * len(dates))


def test_lens_a_exits_at_t16_open():
    sessions = pd.bdate_range("2024-01-01", periods=20)
    entry = make_entry(
        signal_date=sessions[0], entry_date=sessions[1], scheduled_exit=sessions[16]
    )
    prices = make_bars(sessions, opens=list(range(100, 120)))
    result = simulate_lens_a(entry, prices, make_benchmark(sessions), sessions)
    assert result["Exit_Date"] == sessions[16]
    assert result["Exit_Price"] == pytest.approx(
        prices.loc[prices.Date == sessions[16], "Open"].iloc[0]
    )


def test_early_practical_exit_is_still_incomplete_if_t16_lens_a_bar_missing():
    sessions = pd.bdate_range("2024-01-01", periods=16)
    entry = make_entry(
        signal_date=sessions[0],
        entry_date=sessions[1],
        scheduled_exit=pd.Timestamp("2024-01-23"),
    )
    prices = make_bars(sessions, highs=[101.0] * 16, lows=[94.0] + [99.0] * 15)
    lens_a = simulate_lens_a(entry, prices, make_benchmark(sessions), sessions)
    assert lens_a is None


def test_same_bar_stop_and_target_scores_stop_first():
    sessions = pd.bdate_range("2024-01-01", periods=3)
    entry = make_entry(
        signal_date=sessions[0], entry_date=sessions[1], scheduled_exit=sessions[2]
    )
    prices = make_bars(
        sessions,
        opens=[100.0, 100.0, 100.0],
        highs=[105.0, 111.0, 105.0],
        lows=[99.0, 94.0, 99.0],
        closes=[100.0, 105.0, 100.0],
    )
    result = simulate_practical(entry, prices, make_benchmark(sessions), sessions)
    assert result["Exit_Reason"] == "STRUCTURAL_STOP"
    assert result["Exit_Price"] == pytest.approx(95.0)


def test_gap_below_stop_exits_at_open_not_stop():
    sessions = pd.bdate_range("2024-01-01", periods=4)
    entry = make_entry(
        signal_date=sessions[0], entry_date=sessions[1], scheduled_exit=sessions[3]
    )
    prices = make_bars(
        sessions,
        opens=[100.0, 100.0, 92.0, 100.0],
        highs=[105.0, 105.0, 96.0, 105.0],
        lows=[99.0, 99.0, 90.0, 99.0],
        closes=[100.0, 100.0, 94.0, 100.0],
    )
    result = simulate_practical(entry, prices, make_benchmark(sessions), sessions)
    assert result["Exit_Reason"] == "GAP_BELOW_STRUCTURAL_STOP"
    assert result["Exit_Price"] == pytest.approx(92.0)


def test_gap_above_target_exits_at_open():
    sessions = pd.bdate_range("2024-01-01", periods=4)
    entry = make_entry(
        signal_date=sessions[0], entry_date=sessions[1], scheduled_exit=sessions[3]
    )
    prices = make_bars(
        sessions,
        opens=[100.0, 100.0, 113.0, 100.0],
        highs=[105.0, 105.0, 114.0, 105.0],
        lows=[99.0, 99.0, 112.0, 99.0],
        closes=[100.0, 100.0, 113.5, 100.0],
    )
    result = simulate_practical(entry, prices, make_benchmark(sessions), sessions)
    assert result["Exit_Reason"] == "GAP_ABOVE_TARGET"
    assert result["Exit_Price"] == pytest.approx(113.0)


def test_build_outcomes_keeps_lens_a_and_practical_ids_paired():
    sessions = pd.bdate_range("2024-01-01", periods=20)
    entry = make_entry(
        signal_date=sessions[0], entry_date=sessions[1], scheduled_exit=sessions[16]
    )
    prices = make_bars(sessions, opens=[100.0] * 20)
    lens_a, practical, upper, diagnostics = build_outcomes(
        pd.DataFrame([entry]),
        pd.DataFrame(),
        {"AAA": prices},
        make_benchmark(sessions),
        sessions,
    )
    assert set(lens_a["Entry_ID"]) == set(practical["Entry_ID"])
    assert upper.empty
    assert diagnostics["Primary_Complete"].all()
