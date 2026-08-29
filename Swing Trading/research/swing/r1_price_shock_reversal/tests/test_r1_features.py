from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_r1_features as features  # noqa: E402
from build_r1_features import (  # noqa: E402
    active_members_on,
    compute_r1_features,
    download_adjusted_ohlcv,
    load_membership,
    wilder_atr,
)


def test_prior_20_windows_exclude_signal_day():
    dates = pd.bdate_range("2024-01-01", periods=30)
    close = pd.Series(
        [
            100,
            102,
            101,
            103,
            102,
            104,
            103,
            105,
            104,
            106,
            105,
            107,
            106,
            108,
            107,
            109,
            108,
            110,
            109,
            111,
            110,
            112,
            111,
            113,
            112,
            114,
            113,
            115,
            114,
            90,
        ],
        dtype=float,
    )
    volume = pd.Series([100.0] * 29 + [10_000.0])
    frame = pd.DataFrame(
        {
            "Date": dates,
            "Open": close,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": volume,
        }
    )

    result = compute_r1_features(frame)
    row = result.iloc[-1]
    returns = close.pct_change()

    assert row["Sigma20"] == pytest.approx(returns.iloc[-21:-1].std(ddof=1))
    assert row["Prior20_Median_Volume"] == pytest.approx(volume.iloc[-21:-1].median())
    traded = close * volume
    assert row["Prior20_Median_Traded_Value"] == pytest.approx(
        traded.iloc[-21:-1].median()
    )
    assert row["Return"] == pytest.approx(close.iloc[-1] / close.iloc[-2] - 1.0)
    assert row["Shock_Score"] == pytest.approx(row["Return"] / row["Sigma20"])


def test_active_members_on_uses_inclusive_boundaries():
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


def test_load_membership_rejects_overlapping_intervals(tmp_path):
    path = tmp_path / "membership.csv"
    pd.DataFrame(
        {
            "Symbol": ["AAA", "AAA"],
            "Member_From": ["2024-01-01", "2024-01-05"],
            "Member_To": ["2024-01-05", "2024-01-10"],
            "Downloadable": ["True", "True"],
            "Yahoo_Ticker": ["AAA.NS", "AAA.NS"],
        }
    ).to_csv(path, index=False)

    with pytest.raises(ValueError, match="overlap"):
        load_membership(path)


def test_download_adjusted_ohlcv_rejects_duplicate_dates(monkeypatch):
    def fake_download(**kwargs):
        return pd.DataFrame(
            {
                "Date": [pd.Timestamp("2024-01-02")] * 2,
                "Open": [100.0, 100.0],
                "High": [101.0, 101.0],
                "Low": [99.0, 99.0],
                "Close": [100.0, 100.0],
                "Volume": [1_000_000.0, 1_000_000.0],
            }
        )

    monkeypatch.setattr(features.yf, "download", fake_download)
    with pytest.raises(ValueError, match="duplicate dates"):
        download_adjusted_ohlcv("AAA.NS", "2024-01-01", "2024-01-05")


def test_wilder_atr_uses_mean_then_recursive_update():
    true_range = pd.Series([2.0] * 14 + [4.0])

    result = wilder_atr(true_range)

    assert result.iloc[13] == pytest.approx(2.0)
    assert result.iloc[14] == pytest.approx((2.0 * 13 + 4.0) / 14)


def test_compute_r1_features_rejects_duplicate_dates():
    frame = pd.DataFrame(
        {
            "Date": ["2024-01-01", "2024-01-01"],
            "Open": [100.0, 100.0],
            "High": [101.0, 101.0],
            "Low": [99.0, 99.0],
            "Close": [100.0, 100.0],
            "Volume": [1_000_000.0, 1_000_000.0],
        }
    )

    with pytest.raises(ValueError, match="duplicate dates"):
        compute_r1_features(frame)


def test_compute_r1_features_preserves_missing_price_values_without_forward_fill():
    dates = pd.bdate_range("2024-01-01", periods=16)
    frame = pd.DataFrame(
        {
            "Date": dates,
            "Open": np.full(len(dates), 100.0),
            "High": np.full(len(dates), 101.0),
            "Low": np.full(len(dates), 99.0),
            "Close": np.full(len(dates), 100.0),
            "Volume": np.full(len(dates), 1_000_000.0),
        }
    )
    frame.loc[4, "Close"] = np.nan

    result = compute_r1_features(frame)

    assert pd.isna(result.loc[4, "Close"])
    assert pd.isna(result.loc[4, "Return"])
