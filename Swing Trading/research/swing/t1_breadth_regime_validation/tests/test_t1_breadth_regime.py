from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest


MODULE_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(MODULE_ROOT))

import analyze_t1_breadth_regime as analysis  # noqa: E402


def test_strict_breadth_join_never_matches_entry_day() -> None:
    trades = pd.DataFrame(
        {
            "Entry_Date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Symbol": ["AAA", "AAA", "AAA"],
            "Trade_Id": [1, 2, 3],
        }
    )
    breadth = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-01-01", "2023-01-02"]),
            "Coverage_OK": [True, True],
            "Regime": ["NORMAL", "STRONG_MOMENTUM"],
        }
    )

    joined = analysis.asof_join_breadth(trades, breadth)

    assert pd.isna(joined.loc[0, "Breadth_Matched_Date"])
    assert joined.loc[1, "Breadth_Matched_Date"] == pd.Timestamp("2023-01-01")
    assert joined.loc[2, "Breadth_Matched_Date"] == pd.Timestamp("2023-01-02")
    matched = joined.dropna(subset=["Breadth_Matched_Date"])
    assert (matched["Breadth_Matched_Date"] < matched["Entry_Date"]).all()


def test_trade_metrics_use_both_return_and_rupee_profit_factors() -> None:
    trades = pd.DataFrame(
        {
            "Return_Pct": [1.0, -0.5, 2.0],
            "PnL": [10.0, -5.0, 20.0],
            "Holding_Days": [5, 7, 9],
        }
    )

    metrics = analysis.calculate_trade_metrics(trades)

    assert metrics["Trades"] == 3
    assert metrics["Winners"] == 2
    assert metrics["Losers"] == 1
    assert metrics["Return_Profit_Factor"] == pytest.approx(6.0)
    assert metrics["PnL_Profit_Factor"] == pytest.approx(6.0)
    assert metrics["Total_PnL"] == pytest.approx(25.0)


def test_locked_binary_regime_groups_are_exact() -> None:
    trades = pd.DataFrame({"Regime": ["STRONG_MOMENTUM", "NORMAL", "HOSTILE"]})

    grouped = analysis.add_regime_groups(trades)

    assert grouped["Strong_Group"].tolist() == ["STRONG_MOMENTUM", "NON_STRONG", "NON_STRONG"]
    assert grouped["Hostile_Group"].tolist() == ["NON_HOSTILE", "NON_HOSTILE", "HOSTILE"]


def test_episode_diagnostic_reports_fragmentation_without_filtering() -> None:
    daily = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"]),
            "Regime": ["STRONG_MOMENTUM", "STRONG_MOMENTUM", "NORMAL", "STRONG_MOMENTUM"],
        }
    )

    episodes = analysis.build_episode_summary(daily)

    assert episodes["Episode_Number"].tolist() == [1, 2]
    assert episodes["Episode_Length_Sessions"].tolist() == [2, 1]
    assert episodes["Episode_Length_Sessions"].median() == pytest.approx(1.5)


def test_fixed_t1_input_stays_locked() -> None:
    trades = analysis.load_and_validate_trades()

    assert len(trades) == 218
    assert trades["Symbol"].nunique() == 20
    assert int((trades["Return_Pct"] > 0).sum()) == 76
    assert trades["PnL"].sum() == pytest.approx(-4631.32)
