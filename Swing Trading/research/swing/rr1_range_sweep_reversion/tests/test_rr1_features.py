from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_rr1_features import (
    active_members_on,
    canonical_sessions,
    compute_rr1_features,
    wilder_atr,
)
from constants import (
    BASE_FRICTION,
    ER60_MAX,
    HOLDING_SESSIONS,
    LIQUIDITY_FLOOR,
    MIN_INITIAL_RR,
    RANGE_LOOKBACK,
    SIGNAL_END,
    SIGNAL_START,
    STOP_ATR_BUFFER,
)


def test_frozen_rr1_constants():
    assert SIGNAL_START == pd.Timestamp("2023-08-01")
    assert SIGNAL_END == pd.Timestamp("2026-08-25")
    assert RANGE_LOOKBACK == 60
    assert ER60_MAX == 0.25
    assert LIQUIDITY_FLOOR == 100_000_000.0
    assert STOP_ATR_BUFFER == 0.25
    assert MIN_INITIAL_RR == 2.0
    assert HOLDING_SESSIONS == 15
    assert BASE_FRICTION == 0.004


def test_active_members_on_is_inclusive():
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Member_From": [pd.Timestamp("2024-01-02")],
            "Member_To": [pd.Timestamp("2024-01-05")],
            "Downloadable": [True],
            "Yahoo_Ticker": ["AAA.NS"],
        }
    )
    assert active_members_on(membership, pd.Timestamp("2024-01-02"))["Symbol"].tolist() == [
        "AAA"
    ]
    assert active_members_on(membership, pd.Timestamp("2024-01-05"))["Symbol"].tolist() == [
        "AAA"
    ]


def test_canonical_sessions_use_sorted_unique_benchmark_dates():
    benchmark = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-03", "2024-01-02", "2024-01-03"]),
            "Open": [101.0, 100.0, 101.0],
        }
    )
    assert canonical_sessions(benchmark).tolist() == [
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-01-03"),
    ]


def make_valid_price_frame(sessions: pd.DatetimeIndex) -> pd.DataFrame:
    close = pd.Series(np.linspace(100.0, 102.0, len(sessions)))
    return pd.DataFrame(
        {
            "Date": sessions,
            "Open": close,
            "High": close + 2.0,
            "Low": close - 2.0,
            "Close": close,
            "Volume": 2_000_000.0,
        }
    )


def test_range_er_and_liquidity_exclude_signal_day():
    sessions = pd.bdate_range("2024-01-01", periods=70)
    close = pd.Series([100.0 + (i % 4) for i in range(70)])
    high = close + 2.0
    low = close - 2.0
    volume = pd.Series([2_000_000.0] * 69 + [100_000_000.0])
    frame = pd.DataFrame(
        {
            "Date": sessions,
            "Open": close,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }
    )

    out = compute_rr1_features(frame, pd.DatetimeIndex(sessions))
    row = out.iloc[-1]

    assert row["Range_Low"] == pytest.approx(low.iloc[-61:-1].min())
    assert row["Range_High"] == pytest.approx(high.iloc[-61:-1].max())
    assert row["Range_Mid"] == pytest.approx(
        (row["Range_Low"] + row["Range_High"]) / 2.0
    )

    expected_num = abs(close.iloc[-2] - close.iloc[-62])
    expected_den = close.diff().abs().iloc[-61:-1].sum()
    assert row["ER60"] == pytest.approx(expected_num / expected_den)

    expected_traded = (close * volume).iloc[-21:-1].median()
    assert row["Prior20_Median_Traded_Value"] == pytest.approx(expected_traded)


def test_exact_prehistory_fails_when_one_canonical_bar_is_missing():
    sessions = pd.bdate_range("2024-01-01", periods=70)
    frame = make_valid_price_frame(sessions)
    frame = frame[frame["Date"] != sessions[-20]]

    out = compute_rr1_features(frame, pd.DatetimeIndex(sessions))
    signal_row = out.loc[out["Date"] == sessions[-1]].iloc[0]
    assert bool(signal_row["Exact_Prehistory_61"]) is False


def test_wilder_atr_uses_mean_then_recursive_update():
    true_range = pd.Series([2.0] * 14 + [4.0])

    result = wilder_atr(true_range)

    assert result.iloc[13] == pytest.approx(2.0)
    assert result.iloc[14] == pytest.approx((2.0 * 13 + 4.0) / 14)
