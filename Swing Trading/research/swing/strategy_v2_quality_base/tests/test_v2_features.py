import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_v2_features import (
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
    on_aug_1 = active_members_on(membership, pd.Timestamp("2023-08-01"))
    on_aug_2 = active_members_on(membership, pd.Timestamp("2023-08-02"))
    assert on_aug_1["Symbol"].tolist() == ["AAA"]
    assert set(on_aug_2["Symbol"]) == {"AAA", "BBB"}


def test_compute_price_features_uses_wilder_atr14():
    dates = pd.date_range("2023-01-01", periods=16, freq="D")
    frame = pd.DataFrame(
        {
            "Date": dates,
            "Open": np.full(16, 100.0),
            "High": np.full(16, 101.0),
            "Low": np.full(16, 99.0),
            "Close": np.full(16, 100.0),
            "Volume": np.full(16, 1_000_000.0),
        }
    )
    result = compute_price_features(frame)
    assert result.loc[13, "ATR14"] == 2.0
    assert result.loc[14, "ATR14"] == 2.0


def test_liquidity_is_twenty_session_median_close_times_volume():
    dates = pd.date_range("2023-01-01", periods=20, freq="D")
    frame = pd.DataFrame(
        {
            "Date": dates,
            "Open": np.full(20, 100.0),
            "High": np.full(20, 101.0),
            "Low": np.full(20, 99.0),
            "Close": np.full(20, 100.0),
            "Volume": np.full(20, 1_000_000.0),
        }
    )
    result = compute_price_features(frame)
    assert result.loc[19, "Median_Traded_Value_20"] == 100_000_000.0


def test_compute_price_features_does_not_forward_fill_missing_close():
    dates = pd.date_range("2023-01-01", periods=3, freq="D")
    frame = pd.DataFrame(
        {
            "Date": dates,
            "Open": [100.0, 100.0, 100.0],
            "High": [101.0, 101.0, 101.0],
            "Low": [99.0, 99.0, 99.0],
            "Close": [100.0, np.nan, 100.0],
            "Volume": [1_000_000.0] * 3,
        }
    )
    result = compute_price_features(frame)
    assert pd.isna(result.loc[1, "Close"])


def test_rs_uses_only_active_members_and_locked_weights():
    date = pd.Timestamp("2023-08-10")
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA", "BBB", "CCC", "DDD"],
            "Member_From": pd.to_datetime(["2023-08-01"] * 4),
            "Member_To": pd.to_datetime(["2023-12-31"] * 4),
            "Downloadable": [True] * 4,
        }
    )
    frames = {
        symbol: pd.DataFrame(
            {
                "Date": [date],
                "Close": [100.0],
                "Return21": [float(index)],
                "Return63": [float(index)],
                "Return126": [float(index)],
            }
        )
        for index, symbol in enumerate(["AAA", "BBB", "CCC", "DDD"], start=1)
    }
    ranked, audit = rank_point_in_time_rs(frames, membership)
    assert ranked["DDD"].loc[0, "RS21"] == 100.0
    assert ranked["DDD"].loc[0, "Composite_RS"] == 100.0
    assert audit.loc[0, "RS_Coverage"] == 1.0
    assert bool(audit.loc[0, "RS_Research_Safe"])


def test_unsafe_rs_day_is_not_ranked_when_coverage_is_below_eighty_percent():
    date = pd.Timestamp("2023-08-10")
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA", "BBB", "CCC", "DDD", "EEE"],
            "Member_From": pd.to_datetime(["2023-08-01"] * 5),
            "Member_To": pd.to_datetime(["2023-12-31"] * 5),
            "Downloadable": [True] * 5,
        }
    )
    frames = {}
    for index, symbol in enumerate(["AAA", "BBB", "CCC", "DDD", "EEE"], start=1):
        frames[symbol] = pd.DataFrame(
            {
                "Date": [date],
                "Close": [100.0],
                "Return21": [float(index) if index <= 3 else np.nan],
                "Return63": [float(index) if index <= 3 else np.nan],
                "Return126": [float(index) if index <= 3 else np.nan],
            }
        )
    ranked, audit = rank_point_in_time_rs(frames, membership)
    assert audit.loc[0, "RS_Coverage"] == 0.6
    assert not bool(audit.loc[0, "RS_Research_Safe"])
    assert ranked["AAA"].loc[0, "RS21"] != ranked["AAA"].loc[0, "RS21"]


def test_rs_excludes_member_that_starts_after_ranked_date():
    date = pd.Timestamp("2023-08-10")
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA", "BBB"],
            "Member_From": pd.to_datetime(["2023-08-01", "2023-08-11"]),
            "Member_To": pd.to_datetime(["2023-12-31", "2023-12-31"]),
            "Downloadable": [True, True],
        }
    )
    frames = {
        symbol: pd.DataFrame(
            {
                "Date": [date],
                "Close": [100.0],
                "Return21": [float(index)],
                "Return63": [float(index)],
                "Return126": [float(index)],
            }
        )
        for index, symbol in enumerate(["AAA", "BBB"], start=1)
    }
    ranked, audit = rank_point_in_time_rs(frames, membership)
    assert audit.loc[0, "Active_Member_Count"] == 1
    assert not bool(ranked["BBB"].loc[0, "Point_In_Time_Member"])
    assert pd.isna(ranked["BBB"].loc[0, "Composite_RS"])
