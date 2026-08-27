import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyze_v2_results import (  # noqa: E402
    attach_prior_breadth,
    evaluate_gates,
    breadth_summary,
    safe_profit_factor,
    simulate_practical_trade,
    simulate_setup_quality_trade,
)


def test_practical_gap_below_stop_exits_at_open_and_can_be_worse_than_minus_one_r():
    entry = pd.Series(
        {
            "Entry_ID": "AAA-1",
            "Entry_Date": pd.Timestamp("2023-08-10"),
            "Entry_Open": 100.0,
            "Structural_Stop": 95.0,
        }
    )
    prices = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-08-10", "2023-08-11"]),
            "Open": [100.0, 90.0],
            "High": [102.0, 92.0],
            "Low": [99.0, 88.0],
            "Close": [101.0, 91.0],
            "SMA20": [98.0, 98.0],
        }
    )
    result = simulate_practical_trade(entry, prices)
    assert result["Exit_Date"] == pd.Timestamp("2023-08-11")
    assert result["Exit_Price"] == 90.0
    assert result["Exit_Reason"] == "STOP_GAP"
    assert result["R_Multiple"] == -2.0


def test_practical_intraday_touch_exits_at_stop():
    entry = pd.Series(
        {
            "Entry_ID": "AAA-1",
            "Entry_Date": pd.Timestamp("2023-08-10"),
            "Entry_Open": 100.0,
            "Structural_Stop": 95.0,
        }
    )
    prices = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-08-10"]),
            "Open": [100.0],
            "High": [101.0],
            "Low": [94.0],
            "Close": [96.0],
            "SMA20": [90.0],
        }
    )
    result = simulate_practical_trade(entry, prices)
    assert result["Exit_Price"] == 95.0
    assert result["Exit_Reason"] == "STOP_INTRADAY"
    assert result["R_Multiple"] == -1.0


def test_setup_quality_exits_next_open_after_close_below_sma20():
    entry = pd.Series(
        {
            "Entry_ID": "AAA-1",
            "Entry_Date": pd.Timestamp("2023-08-10"),
            "Entry_Open": 100.0,
            "Structural_Stop": 95.0,
        }
    )
    prices = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-08-10", "2023-08-11", "2023-08-14"]),
            "Open": [100.0, 101.0, 99.0],
            "High": [102.0, 102.0, 100.0],
            "Low": [99.0, 96.0, 98.0],
            "Close": [101.0, 97.0, 99.0],
            "SMA20": [98.0, 98.0, 98.0],
        }
    )
    result = simulate_setup_quality_trade(entry, prices)
    assert result["Exit_Signal_Date"] == pd.Timestamp("2023-08-11")
    assert result["Exit_Date"] == pd.Timestamp("2023-08-14")
    assert result["Exit_Price"] == 99.0


def test_scheduled_sma20_exit_precedes_same_day_stop_logic():
    entry = pd.Series(
        {
            "Entry_ID": "AAA-1",
            "Entry_Date": pd.Timestamp("2023-08-10"),
            "Entry_Open": 100.0,
            "Structural_Stop": 95.0,
        }
    )
    prices = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-08-10", "2023-08-11"]),
            "Open": [100.0, 90.0],
            "High": [101.0, 92.0],
            "Low": [99.0, 88.0],
            "Close": [97.0, 91.0],
            "SMA20": [98.0, 98.0],
        }
    )
    result = simulate_practical_trade(entry, prices)
    assert result["Exit_Date"] == pd.Timestamp("2023-08-11")
    assert result["Exit_Price"] == 90.0
    assert result["Exit_Reason"] == "SMA20"


def test_safe_profit_factor_handles_wins_losses_and_empty_inputs():
    assert safe_profit_factor(pd.Series([0.5, -0.25])) == 2.0
    assert safe_profit_factor(pd.Series([0.5, 0.25])) == np.inf
    assert safe_profit_factor(pd.Series([-0.5, -0.25])) == 0.0
    assert pd.isna(safe_profit_factor(pd.Series([], dtype=float)))


def test_breadth_join_forbids_equal_entry_date():
    trades = pd.DataFrame(
        {
            "Entry_ID": ["A"],
            "Entry_Date": pd.to_datetime(["2023-08-10"]),
        }
    )
    breadth = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-08-09", "2023-08-10"]),
            "Regime": ["NORMAL", "HOSTILE"],
        }
    )
    joined = attach_prior_breadth(trades, breadth)
    assert joined.loc[0, "Breadth_Matched_Date"] == pd.Timestamp("2023-08-09")
    assert joined.loc[0, "Regime"] == "NORMAL"
    assert joined.loc[0, "Breadth_Matched_Date"] < joined.loc[0, "Entry_Date"]


def test_breadth_summary_has_one_row_per_regime():
    setup = pd.DataFrame(
        {
            "Entry_ID": ["A", "B"],
            "Symbol": ["AAA", "AAA"],
            "Entry_Date": pd.to_datetime(["2023-08-10", "2023-08-11"]),
            "Regime": ["NORMAL", "NORMAL"],
            "Return": [0.1, -0.05],
            "Holding_Sessions": [3, 4],
        }
    )
    practical = setup.assign(Initial_Risk=1.0, R_Multiple=[0.2, -0.1])
    summary = breadth_summary(setup, practical)
    assert summary["Regime"].tolist() == ["NORMAL"]


def _synthetic_trades(count: int, return_value: float = 0.01) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2023-01-01", periods=count, freq="7D")
    setup = pd.DataFrame(
        {
            "Entry_ID": [f"A-{i}" for i in range(count)],
            "Symbol": ["AAA" if i % 2 == 0 else "BBB" for i in range(count)],
            "Entry_Date": dates,
            "Return": [return_value] * count,
            "Holding_Sessions": [5] * count,
        }
    )
    practical = setup.assign(
        Initial_Risk=1.0,
        R_Multiple=[0.2] * count,
    )
    return setup, practical


def test_evaluate_gates_is_insufficient_at_ninety_nine_completed_trades():
    setup, practical = _synthetic_trades(99)
    result = evaluate_gates(setup, practical)
    assert result.loc[result["Gate"] == "FINAL_STATUS", "Status"].iloc[0] == "INSUFFICIENT_EVIDENCE"


def test_evaluate_gates_cannot_pass_when_a_locked_gate_is_false():
    setup, practical = _synthetic_trades(100, return_value=-0.01)
    result = evaluate_gates(setup, practical)
    assert not bool(result.loc[result["Gate"] == "SETUP_MEAN_RETURN", "Passed"].iloc[0])
    assert result.loc[result["Gate"] == "FINAL_STATUS", "Status"].iloc[0] == "FAIL"


def test_temporal_gate_uses_only_locked_setup_year_conditions():
    rows = []
    for year in (2023, 2024):
        for index in range(20):
            rows.append(
                {
                    "Entry_ID": f"{year}-{index}",
                    "Symbol": "AAA" if index % 2 == 0 else "BBB",
                    "Entry_Date": pd.Timestamp(year=year, month=1, day=1)
                    + pd.Timedelta(days=index * 7),
                    "Return": 0.02 if index < 15 else -0.01,
                    "Holding_Sessions": 5,
                }
            )

    setup = pd.DataFrame(rows)
    practical = setup.assign(Initial_Risk=1.0, R_Multiple=-0.25)

    result = evaluate_gates(
        setup,
        practical,
        point_in_time_violations=0,
    )
    temporal = result.loc[result["Gate"].eq("TEMPORAL_ROBUSTNESS")].iloc[0]

    assert bool(temporal["Passed"])
    assert int(temporal["Value"]) == 2
