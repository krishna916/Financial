import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_m1_regime import attach_exact_signal_regime, build_m1_regime


def market_fixture(
    pct_above=50.0,
    denominator=4,
    close=120.0,
    sma50=110.0,
    sma200=100.0,
    old_regime="HOSTILE",
):
    date = pd.Timestamp("2024-01-02")
    membership = pd.DataFrame(
        {
            "Symbol": ["A", "B", "C", "D", "E"],
            "Member_From": pd.to_datetime(["2023-01-01"] * 5),
            "Member_To": pd.to_datetime(["2024-12-31"] * 5),
            "Method": ["POINT_IN_TIME"] * 5,
        }
    )
    breadth = pd.DataFrame(
        {
            "Date": [date],
            "SMA50_Denominator": [denominator],
            "Pct_Above_SMA50": [pct_above],
            "Regime": [old_regime],
            "Momentum_Regime": [old_regime],
            "Universe_Member_Count": [5],
        }
    )
    index_daily = pd.DataFrame(
        {
            "Date": [date],
            "Close": [close],
            "SMA50": [sma50],
            "SMA200": [sma200],
            "Regime": [old_regime],
        }
    )
    return breadth, index_daily, membership


def test_coverage_exactly_point_80_is_safe():
    breadth, index_daily, membership = market_fixture(denominator=4)
    regime, audit = build_m1_regime(breadth, index_daily, membership)
    assert audit.empty
    assert regime.loc[0, "SMA50_Breadth_Coverage"] == 0.8
    assert bool(regime.loc[0, "DATA_SAFE"])


def test_breadth_exactly_50_is_ok():
    breadth, index_daily, membership = market_fixture(pct_above=50.0)
    regime, audit = build_m1_regime(breadth, index_daily, membership)
    assert audit.empty
    assert bool(regime.loc[0, "BREADTH_OK"])
    assert regime.loc[0, "M1_Regime"] == "MOMENTUM_ENABLED"


def test_index_requires_both_close_and_sma50_above_sma200():
    breadth, index_daily, membership = market_fixture(close=120.0, sma50=99.0, sma200=100.0)
    regime, _ = build_m1_regime(breadth, index_daily, membership)
    assert not bool(regime.loc[0, "INDEX_TREND_OK"])
    assert regime.loc[0, "M1_Regime"] == "MOMENTUM_DISABLED"


def test_old_strong_momentum_label_is_ignored():
    breadth, index_daily, membership = market_fixture(
        pct_above=49.0,
        close=99.0,
        sma50=98.0,
        sma200=100.0,
        old_regime="STRONG_MOMENTUM",
    )
    regime, _ = build_m1_regime(breadth, index_daily, membership)
    assert regime.loc[0, "M1_Regime"] == "MOMENTUM_DISABLED"


def test_signal_regime_join_requires_exact_same_date():
    signals = pd.DataFrame(
        {
            "Entry_ID": ["AAA-2024-01-03"],
            "Symbol": ["AAA"],
            "Signal_Date": pd.to_datetime(["2024-01-03"]),
        }
    )
    regime = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-02"]),
            "M1_Regime": ["MOMENTUM_ENABLED"],
        }
    )
    joined, regime_audit, violations = attach_exact_signal_regime(signals, regime)
    assert pd.isna(joined.loc[0, "M1_Regime"])
    assert not bool(regime_audit.loc[0, "Exact_Date_Match"])
    assert "MISSING_EXACT_SIGNAL_REGIME" in violations["Violation"].tolist()


def test_membership_denominator_is_recomputed_from_pit_intervals():
    breadth, index_daily, membership = market_fixture(denominator=4)
    breadth.loc[0, "Universe_Member_Count"] = 4
    _, audit = build_m1_regime(breadth, index_daily, membership)
    assert "BREADTH_PIT_DENOMINATOR_MISMATCH" in audit["Violation"].tolist()
