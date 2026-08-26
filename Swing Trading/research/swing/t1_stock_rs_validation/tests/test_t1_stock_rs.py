import hashlib
import math
from pathlib import Path
import sys

import pandas as pd
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from research.swing.t1_stock_rs_validation.analyze_t1_stock_rs import (  # noqa: E402
    ALLOWED_RS_STATUSES,
    EXPECTED_T1_SHA256,
    STOCK_RS_PATH,
    T1_TRADES_PATH,
    calculate_profit_factor,
    calculate_trade_metrics,
    load_and_validate_stock_rs,
    load_and_validate_trades,
)


def test_locked_t1_input_is_exact_218_trade_sample():
    raw = T1_TRADES_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_T1_SHA256

    trades = load_and_validate_trades(T1_TRADES_PATH)
    assert len(trades) == 218
    assert trades["Symbol"].nunique() == 20
    assert int((trades["Return_Pct"] > 0).sum()) == 76
    assert math.isclose(float(trades["PnL"].sum()), -4631.32, abs_tol=0.01)
    assert math.isclose(float(trades["Return_Pct"].mean()), -0.0548680341, abs_tol=1e-8)


def test_stock_rs_input_is_research_safe_and_locked():
    rs = load_and_validate_stock_rs(STOCK_RS_PATH)
    assert set(rs["RS_Status"].unique()) <= ALLOWED_RS_STATUSES
    assert (rs["Stock_Count"] == 20).all()
    assert rs["Is_Full_Universe"].all()
    assert rs["Composite_Rank"].between(1, 20).all()
    assert not rs.duplicated(["Date", "Symbol"]).any()


def test_load_and_validate_trades_rejects_duplicate_normalized_trade_key(tmp_path):
    trades = pd.read_csv(T1_TRADES_PATH)
    duplicate = pd.concat([trades, trades.iloc[[0]]], ignore_index=True)
    path = tmp_path / "duplicate.csv"
    duplicate.to_csv(path, index=False)

    with pytest.raises(ValueError, match="duplicate normalized trade keys"):
        load_and_validate_trades(path)


def test_calculate_trade_metrics_uses_locked_definitions():
    trades = pd.DataFrame(
        {
            "Return_Pct": [0.10, 0.05, -0.10, -0.20],
            "PnL": [100.0, 50.0, -40.0, -60.0],
            "Holding_Days": [5, 7, 9, 11],
        }
    )

    result = calculate_trade_metrics(trades)

    assert result["Trades"] == 4
    assert result["Winners"] == 2
    assert result["Losers"] == 2
    assert result["Win_Rate"] == 50.0
    assert result["Mean_Return"] == -0.0375
    assert result["Median_Return"] == -0.025
    assert result["Average_Winner"] == pytest.approx(0.075)
    assert result["Average_Loser"] == pytest.approx(-0.15)
    assert result["Payoff_Ratio"] == pytest.approx(0.5)
    assert result["Return_Profit_Factor"] == pytest.approx(0.5)
    assert result["PnL_Profit_Factor"] == pytest.approx(1.5)
    assert result["Total_PnL"] == pytest.approx(50.0)
    assert result["Median_Holding_Days"] == pytest.approx(8.0)


def test_calculate_profit_factor_handles_locked_edge_behavior():
    assert calculate_profit_factor(pd.Series([2.0, -1.0])) == 2.0
    assert math.isinf(calculate_profit_factor(pd.Series([2.0, 0.0])))
    assert calculate_profit_factor(pd.Series([-2.0, 0.0])) == 0.0
    assert math.isnan(calculate_profit_factor(pd.Series([0.0, 0.0])))
