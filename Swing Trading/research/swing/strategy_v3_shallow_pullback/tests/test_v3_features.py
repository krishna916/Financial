import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_v3_features as features  # noqa: E402
from build_v3_features import (  # noqa: E402
    active_members_on,
    compute_price_features,
    rank_point_in_time_rs,
)


def test_active_members_on_uses_inclusive_intervals():
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA", "BBB"],
            "Member_From": pd.to_datetime(["2023-08-01", "2023-08-02"]),
            "Member_To": pd.to_datetime(["2023-08-02", "2023-08-03"]),
            "Downloadable": [True, True],
        }
    )
    assert active_members_on(membership, pd.Timestamp("2023-08-01"))["Symbol"].tolist() == ["AAA"]
    assert set(active_members_on(membership, pd.Timestamp("2023-08-02"))["Symbol"]) == {"AAA", "BBB"}


def test_compute_price_features_uses_wilder_atr_and_no_forward_fill():
    frame = pd.DataFrame(
        {
            "Date": pd.date_range("2023-01-01", periods=20),
            "Open": np.full(20, 100.0),
            "High": np.full(20, 101.0),
            "Low": np.full(20, 99.0),
            "Close": np.full(20, 100.0),
            "Volume": np.full(20, 1_000_000.0),
        }
    )
    out = compute_price_features(frame)
    assert out.loc[13, "ATR14"] == 2.0
    assert out.loc[19, "Median_Traded_Value_20"] == 100_000_000.0
    frame.loc[10, "Close"] = np.nan
    assert pd.isna(compute_price_features(frame).loc[10, "Close"])


def test_rs_sixty_percent_coverage_is_unsafe():
    date = pd.Timestamp("2023-08-10")
    membership = pd.DataFrame(
        {
            "Symbol": ["A", "B", "C", "D", "E"],
            "Member_From": pd.to_datetime(["2023-08-01"] * 5),
            "Member_To": pd.to_datetime(["2023-12-31"] * 5),
            "Downloadable": [True] * 5,
        }
    )
    frames = {
        symbol: pd.DataFrame(
            {
                "Date": [date],
                "Return21": [float(i)],
                "Return63": [float(i)],
                "Return126": [float(i)],
            }
        )
        for i, symbol in enumerate(["A", "B", "C", "D", "E"], start=1)
    }
    frames["D"].loc[0, "Return126"] = np.nan
    frames["E"].loc[0, "Return63"] = np.nan
    _, audit = rank_point_in_time_rs(frames, membership)
    assert audit.loc[0, "RS_Coverage"] == 0.6
    assert not bool(audit.loc[0, "RS_Research_Safe"])


def test_pre_window_rs_requires_actual_pre_window_membership():
    july = pd.Timestamp("2023-07-31")
    frames = {
        "A": pd.DataFrame(
            {
                "Date": [july],
                "Return21": [1.0],
                "Return63": [1.0],
                "Return126": [1.0],
            }
        ),
        "B": pd.DataFrame(
            {
                "Date": [july],
                "Return21": [2.0],
                "Return63": [2.0],
                "Return126": [2.0],
            }
        ),
    }
    membership = pd.DataFrame(
        {
            "Symbol": ["A", "B"],
            "Member_From": pd.to_datetime(["2023-07-01", "2023-07-01"]),
            "Member_To": pd.to_datetime(["2023-08-31", "2023-08-31"]),
            "Downloadable": [True, True],
        }
    )
    _, july_audit = rank_point_in_time_rs(frames, membership)
    assert july_audit["Date"].tolist() == [july]
    membership.loc[:, "Member_From"] = pd.Timestamp("2023-08-01")
    _, no_july_audit = rank_point_in_time_rs(frames, membership)
    assert no_july_audit.empty


def test_download_adjusted_ohlcv_uses_bounded_provider_timeout(monkeypatch):
    calls = {}

    def fake_download(**kwargs):
        calls.update(kwargs)
        return pd.DataFrame(
            {
                "Date": [pd.Timestamp("2023-01-03")],
                "Open": [100.0],
                "High": [101.0],
                "Low": [99.0],
                "Close": [100.0],
                "Volume": [1_000_000.0],
            }
        )

    monkeypatch.setattr(features.yf, "download", fake_download)
    features.download_adjusted_ohlcv("AAA.NS", "2023-01-01", "2023-01-05")
    assert calls["timeout"] == 30
