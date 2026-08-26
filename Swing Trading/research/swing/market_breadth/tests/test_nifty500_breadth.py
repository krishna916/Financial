from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


MODULE_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(MODULE_ROOT))

import build_nifty500_breadth as breadth  # noqa: E402


def test_membership_intervals_are_non_overlapping_and_inclusive() -> None:
    membership = pd.DataFrame(
        [
            ["AAA", "2023-01-01", "2023-01-03", "POINT_IN_TIME"],
            ["AAA", "2023-01-04", "2023-01-05", "POINT_IN_TIME"],
        ],
        columns=["Symbol", "Member_From", "Member_To", "Method"],
    )

    breadth.validate_membership_intervals(membership)
    assert len(breadth.members_on_date(membership, date(2023, 1, 3))) == 1
    assert len(breadth.members_on_date(membership, date(2023, 1, 4))) == 1


def test_overlapping_membership_intervals_are_rejected() -> None:
    membership = pd.DataFrame(
        [
            ["AAA", "2023-01-01", "2023-01-03", "POINT_IN_TIME"],
            ["AAA", "2023-01-03", "2023-01-05", "POINT_IN_TIME"],
        ],
        columns=["Symbol", "Member_From", "Member_To", "Method"],
    )

    with pytest.raises(ValueError, match="overlap"):
        breadth.validate_membership_intervals(membership)


def test_stock_smas_require_full_windows() -> None:
    history = pd.DataFrame({"Adj_Close": np.arange(1, 202, dtype=float)})

    result = breadth.calculate_stock_smas(history)

    assert result.loc[48, "SMA50"] != result.loc[48, "SMA50"]
    assert result.loc[49, "SMA50"] == pytest.approx(25.5)
    assert result.loc[198, "SMA200"] != result.loc[198, "SMA200"]
    assert result.loc[199, "SMA200"] == pytest.approx(100.5)


def test_normalization_preserves_missing_dates_and_rejects_duplicates() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2023-01-01", "2023-01-03"],
            "Close": [100.0, 102.0],
            "Adj Close": [99.0, 101.0],
        }
    )

    normalized = breadth.normalize_stock_history(raw, "AAA", "AAA.NS")

    assert normalized["Date"].tolist() == [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-03")]
    assert len(normalized) == 2
    duplicate = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate"):
        breadth.normalize_stock_history(duplicate, "AAA", "AAA.NS")


def test_daily_breadth_uses_membership_and_data_denominators_exactly() -> None:
    membership = pd.DataFrame(
        [
            ["AAA", "2023-01-01", "2023-01-05", "POINT_IN_TIME"],
            ["BBB", "2023-01-03", "2023-01-05", "POINT_IN_TIME"],
        ],
        columns=["Symbol", "Member_From", "Member_To", "Method"],
    )
    history = pd.DataFrame(
        [
            ["AAA", "2023-01-01", 100.0, 90.0, 95.0],
            ["AAA", "2023-01-02", 100.0, 90.0, 95.0],
            ["AAA", "2023-01-03", 100.0, 90.0, 95.0],
            ["BBB", "2023-01-03", 80.0, 90.0, 90.0],
        ],
        columns=["Symbol", "Date", "Adj_Close", "SMA50", "SMA200"],
    )

    result = breadth.calculate_daily_breadth(membership, history, date(2023, 1, 1), date(2023, 1, 3))

    jan_1 = result.loc[result["Date"] == pd.Timestamp("2023-01-01")].iloc[0]
    jan_3 = result.loc[result["Date"] == pd.Timestamp("2023-01-03")].iloc[0]
    assert jan_1["Member_Count"] == 1
    assert jan_1["SMA50_Denominator"] == 1
    assert jan_1["Pct_Above_SMA50"] == pytest.approx(100.0)
    assert jan_3["Member_Count"] == 2
    assert jan_3["SMA50_Denominator"] == 2
    assert jan_3["Pct_Above_SMA50"] == pytest.approx(50.0)


@pytest.mark.parametrize(
    ("close", "sma200", "pct50", "pct200", "expected"),
    [
        (100.0, 100.0, 100.0, 100.0, "HOSTILE"),
        (101.0, 100.0, 60.0, 60.0, "STRONG_MOMENTUM"),
        (101.0, 100.0, 59.999, 100.0, "NORMAL"),
    ],
)
def test_locked_regime_boundaries(close: float, sma200: float, pct50: float, pct200: float, expected: str) -> None:
    row = pd.Series(
        {
            "Nifty500_Close": close,
            "Nifty500_SMA200": sma200,
            "Pct_Above_SMA50": pct50,
            "Pct_Above_SMA200": pct200,
        }
    )

    assert breadth.classify_momentum_regime(row) == expected


def test_breadth_module_does_not_load_trade_or_signal_inputs() -> None:
    source = (MODULE_ROOT / "build_nifty500_breadth.py").read_text(encoding="utf-8")
    for forbidden in ("t1_trades.csv", "Return_Pct", "PnL", "Holding_Days", "stock_rs", "sector_rs"):
        assert forbidden not in source
