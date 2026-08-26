import math
from pathlib import Path
import sys

import pandas as pd
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from research.swing.stock_rs.build_stock_rs import (  # noqa: E402
    assign_rs_status,
    calculate_returns,
)


BASE_DIR = Path(__file__).resolve().parents[1]


def test_stock_config_is_exact_fixed_twenty_stock_universe():
    df = pd.read_csv(BASE_DIR / "stock_ticker_config.csv", dtype=str)
    assert df.columns.tolist() == ["Symbol", "Yahoo_Ticker"]
    assert len(df) == 20
    assert df["Symbol"].is_unique
    assert df["Yahoo_Ticker"].is_unique
    mapping = dict(zip(df["Symbol"], df["Yahoo_Ticker"]))
    assert mapping["M&M"] == "M&M.NS"
    assert mapping["HDFCBANK"] == "HDFCBANK.NS"
    assert mapping["ULTRACEMCO"] == "ULTRACEMCO.NS"


def test_calculate_returns_uses_exact_adjusted_close_session_shifts():
    df = pd.DataFrame({"Adj_Close": [100.0 + i for i in range(140)]})
    result = calculate_returns(df)
    assert pd.isna(result.loc[20, "Ret21"])
    assert math.isclose(result.loc[21, "Ret21"], 121.0 / 100.0 - 1.0)
    assert math.isclose(result.loc[63, "Ret63"], 163.0 / 100.0 - 1.0)
    assert math.isclose(result.loc[126, "Ret126"], 226.0 / 100.0 - 1.0)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100.0, "PREFERRED"),
        (80.0, "PREFERRED"),
        (79.999, "VALID"),
        (70.0, "VALID"),
        (69.999, "BELOW_VALID"),
        (5.0, "BELOW_VALID"),
    ],
)
def test_assign_rs_status_uses_locked_v1_thresholds(score, expected):
    assert assign_rs_status(score) == expected
