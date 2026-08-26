from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from research.swing.t1_sector_validation.analyze_t1_sector_leadership import (
    _validate_joined_input,
    asof_join_sector_leadership,
    calculate_profit_factor,
    calculate_trade_metrics,
    classify_binary_groups,
    load_and_validate_mapping,
    load_and_validate_sector_data,
    load_and_validate_trades,
    prepare_full_universe_sector_data,
)


def test_prepare_full_universe_sector_data_keeps_only_eleven_sector_rows():
    source = pd.DataFrame(
        {
            "Date": ["2026-01-02", "2026-01-02"],
            "Sector_Key": ["BANK", "IT"],
            "Sector_Count": [11, 2],
            "Is_Full_Universe": [True, False],
            "Composite_RS": [80.0, 90.0],
            "Composite_Rank": [2, 1],
            "Leadership_Bucket": ["LEADING", "LEADING"],
        }
    )

    result = prepare_full_universe_sector_data(source)

    assert result["Sector_Key"].tolist() == ["BANK"]
    assert result["Sector_Count"].eq(11).all()


def test_asof_join_sector_leadership_never_uses_a_future_row():
    trades = pd.DataFrame(
        {
            "Symbol": ["HDFCBANK"],
            "Entry_Date": ["2026-01-04"],
            "Sector_Key": ["BANK"],
        }
    )
    sectors = pd.DataFrame(
        {
            "Date": ["2026-01-02", "2026-01-05"],
            "Sector_Key": ["BANK", "BANK"],
            "Sector_Count": [11, 11],
            "Composite_RS": [70.0, 95.0],
            "Composite_Rank": [4, 1],
            "Leadership_Bucket": ["ACCEPTABLE", "LEADING"],
        }
    )

    result = asof_join_sector_leadership(trades, sectors)

    assert result.loc[0, "Sector_Matched_Date"] == pd.Timestamp("2026-01-02")
    assert result.loc[0, "Leadership_Bucket"] == "ACCEPTABLE"


def test_asof_join_sector_leadership_exports_calendar_lag():
    trades = pd.DataFrame(
        {
            "Symbol": ["HDFCBANK"],
            "Entry_Date": ["2026-01-04"],
            "Sector_Key": ["BANK"],
        }
    )
    sectors = pd.DataFrame(
        {
            "Date": ["2026-01-02"],
            "Sector_Key": ["BANK"],
            "Sector_Count": [11],
            "Composite_RS": [70.0],
            "Composite_Rank": [4],
            "Leadership_Bucket": ["ACCEPTABLE"],
        }
    )

    result = asof_join_sector_leadership(trades, sectors)

    assert result.loc[0, "Sector_Date_Lag_Days"] == 2
    assert result.loc[0, "Sector_Date_Lag_Days"] >= 0


def test_calculate_profit_factor_handles_gain_loss_edge_cases():
    assert calculate_profit_factor(pd.Series([2.0, -1.0])) == 2.0
    assert math.isinf(calculate_profit_factor(pd.Series([2.0, 0.0])))
    assert calculate_profit_factor(pd.Series([-2.0, 0.0])) == 0.0
    assert math.isnan(calculate_profit_factor(pd.Series([0.0, 0.0])))


def test_calculate_trade_metrics_reports_declared_return_and_pnl_metrics():
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
    assert result["Win_Rate"] == 0.5
    assert result["Mean_Return"] == -0.0375
    assert result["Median_Return"] == -0.025
    assert result["Average_Winner"] == pytest.approx(0.075)
    assert result["Average_Loser"] == pytest.approx(-0.15)
    assert result["Payoff_Ratio"] == pytest.approx(0.5)
    assert result["Return_Profit_Factor"] == pytest.approx(0.5)
    assert result["PnL_Profit_Factor"] == pytest.approx(1.5)
    assert result["Total_PnL"] == pytest.approx(50.0)
    assert result["Median_Holding_Days"] == pytest.approx(8.0)


def test_loaders_accept_only_the_locked_repository_inputs():
    trades = load_and_validate_trades()
    mapping = load_and_validate_mapping()
    sector = load_and_validate_sector_data()

    assert len(trades) == 218
    assert dict(zip(mapping["Stock"], mapping["Sector_Key"]))["M&M"] == "AUTO"
    assert set(sector["Leadership_Bucket"]) == {
        "LEADING",
        "ACCEPTABLE",
        "WEAK",
        "LAGGING",
    }


def test_classify_binary_groups_uses_only_the_three_locked_partitions():
    joined = pd.DataFrame(
        {"Leadership_Bucket": ["LEADING", "ACCEPTABLE", "WEAK", "LAGGING"]}
    )

    result = classify_binary_groups(joined)

    assert result["Leading_Group"].tolist() == [
        "LEADING",
        "NON_LEADING",
        "NON_LEADING",
        "NON_LEADING",
    ]
    assert result["Top_Half_Group"].tolist() == [
        "TOP_HALF",
        "TOP_HALF",
        "LOWER_HALF",
        "LOWER_HALF",
    ]
    assert result["Lagging_Group"].tolist() == [
        "NON_LAGGING",
        "NON_LAGGING",
        "NON_LAGGING",
        "LAGGING",
    ]


def test_validate_joined_input_reports_return_reconciliation_and_long_lags():
    trades = pd.DataFrame(
        {
            "Symbol": ["HDFCBANK", "SBIN"],
            "Return_Pct": [10.0, -2.0],
            "PnL": [5.0, -1.0],
        }
    )
    joined = pd.DataFrame(
        {
            "Symbol": ["HDFCBANK", "SBIN"],
            "Entry_Date": pd.to_datetime(["2026-01-09", "2026-01-09"]),
            "Sector_Matched_Date": pd.to_datetime(["2026-01-01", "2026-01-09"]),
            "Sector_Date_Lag_Days": [8, 0],
            "Sector_Count": [11, 11],
            "Leadership_Bucket": ["LEADING", "LAGGING"],
            "Return_Pct": [10.0, -2.0],
            "PnL": [5.0, -1.0],
        }
    )

    result = _validate_joined_input(trades, joined)

    assert result["Return_Reconciles"] is True
    assert result["Sector_Lag_Over_7_Days_Trade_Count"] == 1
    assert result["Sector_Lag_Over_7_Days_Trades"] == "HDFCBANK/2026-01-09/2026-01-01/8d"
