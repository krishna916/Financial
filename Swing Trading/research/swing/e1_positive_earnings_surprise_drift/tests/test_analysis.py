from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from analyze_e1_results import (  # noqa: E402
    leave_one_symbol_out,
    return_profit_factor,
    temporal_summary,
    top_five_robustness,
)


def _trades() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Event_ID": ["a", "b", "c", "d", "e", "f"],
            "Symbol": ["AAA", "AAA", "BBB", "BBB", "CCC", "CCC"],
            "Event_Public_Date": pd.to_datetime(
                ["2025-01-14", "2025-01-15", "2024-02-01", "2024-03-01", "2024-04-01", "2024-05-01"]
            ),
            "Gross_Return": [0.20, 0.10, 0.05, -0.02, 0.03, -0.01],
            "Base_Net_Return": [0.196, 0.096, 0.046, -0.024, 0.026, -0.014],
            "Stress_Net_Return": [0.194, 0.094, 0.044, -0.026, 0.024, -0.016],
            "Severe_Net_Return": [0.192, 0.092, 0.042, -0.028, 0.022, -0.018],
            "Benchmark_Return": [0.01] * 6,
            "Base_Net_Excess_Return": [0.186, 0.086, 0.036, -0.034, 0.016, -0.024],
            "Stress_Net_Excess_Return": [0.184, 0.084, 0.034, -0.036, 0.014, -0.026],
            "Entry_Date": pd.date_range("2025-02-01", periods=6, freq="B"),
            "Exit_Date": pd.date_range("2025-03-01", periods=6, freq="B"),
        }
    )


def test_return_profit_factor_is_sum_wins_over_absolute_sum_losses():
    values = pd.Series([0.10, 0.05, -0.03, -0.02])
    assert return_profit_factor(values) == pytest.approx(3.0)


def test_return_profit_factor_zero_loss_behavior_is_deterministic():
    assert return_profit_factor(pd.Series([0.1, 0.0])) == float("inf")
    assert pd.isna(return_profit_factor(pd.Series([0.0, 0.0])))


def test_temporal_split_uses_event_public_date_boundaries():
    result = temporal_summary(_trades())
    assert result.set_index("Period").loc["FIRST", "Completed_Count"] == 5
    assert result.set_index("Period").loc["SECOND", "Completed_Count"] == 1


def test_top_five_uses_gross_returns_and_loso_covers_every_symbol():
    trades = _trades()
    top = top_five_robustness(trades)
    assert top.iloc[0]["Removed_Count"] == 5
    assert top.iloc[0]["Remaining_Count"] == 1
    loso = leave_one_symbol_out(trades)
    assert loso["Symbol_Removed"].tolist() == ["AAA", "BBB", "CCC"]
    assert set(loso["Mandatory_Gate"].unique()) == {True}
