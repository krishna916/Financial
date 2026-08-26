import math
from pathlib import Path
import sys

import pandas as pd
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from research.swing.stock_rs.build_stock_rs import (  # noqa: E402
    assign_rs_status,
    calculate_returns,
    calculate_daily_stock_rs,
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


def _synthetic_stock_rs_rows(date, count=20, offset=0):
    return [
        {
            "Date": pd.Timestamp(date),
            "Symbol": f"S{i:02d}",
            "Yahoo_Ticker": f"S{i:02d}.NS",
            "Close": 100.0,
            "Adj_Close": 100.0,
            "Ret21": float(i + offset),
            "Ret63": float(i + offset),
            "Ret126": float(i + offset),
        }
        for i in range(count)
    ]


def test_daily_rs_percentiles_and_composite_rank_strongest_stock_first():
    result = calculate_daily_stock_rs(
        pd.DataFrame(_synthetic_stock_rs_rows("2026-01-02"))
    )
    strongest = result.loc[result["Symbol"].eq("S19")].iloc[0]
    weakest = result.loc[result["Symbol"].eq("S00")].iloc[0]
    assert len(result) == 20
    assert strongest["RS21_Percentile"] == 100.0
    assert strongest["Composite_RS"] == 100.0
    assert strongest["Composite_Rank"] == 1
    assert strongest["RS_Status"] == "PREFERRED"
    assert weakest["RS21_Percentile"] == 5.0
    assert weakest["Composite_Rank"] == 20
    assert result["Stock_Count"].eq(20).all()
    assert result["Is_Full_Universe"].all()


def test_daily_rs_excludes_dates_without_the_full_twenty_stock_universe():
    rows = _synthetic_stock_rs_rows("2026-01-02")
    rows.extend(_synthetic_stock_rs_rows("2026-01-03", count=19, offset=20))
    result = calculate_daily_stock_rs(pd.DataFrame(rows))
    assert result["Date"].eq(pd.Timestamp("2026-01-02")).all()
    assert len(result) == 20


def test_daily_rs_composite_uses_locked_thirty_forty_thirty_weights():
    result = calculate_daily_stock_rs(
        pd.DataFrame(_synthetic_stock_rs_rows("2026-01-02"))
    )
    target = result.loc[result["Symbol"].eq("S07")].iloc[0]
    expected = (
        0.30 * target["RS21_Percentile"]
        + 0.40 * target["RS63_Percentile"]
        + 0.30 * target["RS126_Percentile"]
    )
    assert target["Composite_RS"] == pytest.approx(expected)
