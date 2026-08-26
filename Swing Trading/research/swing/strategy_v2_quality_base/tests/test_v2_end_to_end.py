import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyze_v2_results import (  # noqa: E402
    attach_prior_breadth,
    simulate_practical_trade,
    simulate_setup_quality_trade,
)
from build_v2_features import compute_price_features, rank_point_in_time_rs  # noqa: E402
from generate_v2_signals import build_entries, scan_symbol_bases  # noqa: E402


def _raw_base_frame() -> pd.DataFrame:
    dates = pd.date_range("2023-08-01", periods=73, freq="D")
    rows = []
    for i, date in enumerate(dates):
        if i < 62:
            high, low, close = 90.0, 88.0, 89.0
        elif i == 62:
            high, low, close = 100.0, 98.0, 99.0
        elif 63 <= i <= 67:
            high, low, close = 99.0, 95.0, 98.0
        elif 68 <= i <= 71:
            high, low, close = 99.0, 97.0, 98.5
        else:
            high, low, close = 102.0, 98.0, 101.0
        rows.append(
            {
                "Date": date,
                "Open": close,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": 2_000_000.0,
            }
        )
    return pd.DataFrame(rows)


def _prepared_frames() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA", "BBB", "CCC", "DDD", "EEE"],
            "Member_From": pd.to_datetime(["2022-12-01"] * 5),
            "Member_To": pd.to_datetime(["2023-12-31"] * 5),
            "Downloadable": [True] * 5,
        }
    )
    aaa = compute_price_features(_raw_base_frame())
    aaa["True_Range"] = [2.0] * 63 + [4.0] * 5 + [2.0] * 4 + [4.0]
    aaa["ATR14"] = 2.0
    aaa.loc[72, "ATR14"] = 4.0
    aaa["SMA20"] = 95.0
    aaa["SMA50"] = 95.0
    aaa["SMA200"] = 90.0
    aaa["Median_Traded_Value_20"] = 200_000_000.0
    frames = {"AAA": aaa}
    for index, symbol in enumerate(["BBB", "CCC", "DDD", "EEE"], start=1):
        other = aaa.copy()
        other["High"] = 50.0
        other["Low"] = 48.0
        other["Close"] = 49.0
        other["Open"] = 49.0
        other["Return21"] = float(5 - index)
        other["Return63"] = float(5 - index)
        other["Return126"] = float(5 - index)
        frames[symbol] = other
    returns = [5.0, 4.0, 3.0, 2.0, 1.0]
    for symbol, value in zip(frames, returns):
        frames[symbol].loc[72, ["Return21", "Return63", "Return126"]] = value
    return frames, membership


def test_strategy_v2_pure_flow_preserves_timing_and_breadth_integrity():
    frames, membership = _prepared_frames()
    ranked, _ = rank_point_in_time_rs(frames, membership)
    audit, candidates = scan_symbol_bases("AAA", ranked["AAA"])
    signal = candidates.loc[candidates["Signal_Qualified"]].copy()
    signal_date = signal.iloc[0]["Signal_Date"]
    entry_date = signal_date + pd.Timedelta(days=1)
    entry_prices = {
        "AAA": pd.DataFrame(
            {
                "Date": [entry_date],
                "Open": [101.0],
                "High": [103.0],
                "Low": [100.0],
                "Close": [102.0],
            }
        )
    }
    accepted_entries, cancellations = build_entries(
        signal,
        entry_prices,
        pd.DatetimeIndex([signal_date, entry_date]),
    )
    assert len(accepted_entries) == 1
    assert accepted_entries.iloc[0]["Symbol"] == "AAA"
    assert accepted_entries.iloc[0]["Entry_Date"] > accepted_entries.iloc[0]["Signal_Date"]
    trade_prices = pd.DataFrame(
        {
            "Date": pd.to_datetime([entry_date, entry_date + pd.Timedelta(days=1), entry_date + pd.Timedelta(days=2)]),
            "Open": [101.0, 103.0, 99.0],
            "High": [103.0, 104.0, 100.0],
            "Low": [100.0, 101.0, 98.0],
            "Close": [102.0, 96.0, 99.0],
            "SMA20": [95.0, 98.0, 98.0],
        }
    )
    setup_trade = simulate_setup_quality_trade(accepted_entries.iloc[0], trade_prices)
    practical_trade = simulate_practical_trade(accepted_entries.iloc[0], trade_prices)
    assert setup_trade["Entry_ID"] == practical_trade["Entry_ID"]
    breadth = pd.DataFrame(
        {
            "Date": pd.to_datetime([entry_date - pd.Timedelta(days=1), entry_date]),
            "Regime": ["NORMAL", "HOSTILE"],
        }
    )
    joined = attach_prior_breadth(pd.DataFrame([setup_trade]), breadth)
    assert joined.iloc[0]["Breadth_Matched_Date"] < joined.iloc[0]["Entry_Date"]
    assert cancellations.empty
    assert "BREAKOUT_CANDIDATE" in set(audit["Event"])


def test_strategy_v2_rejects_noncontracting_and_too_short_mutations():
    frames, _ = _prepared_frames()
    ranked, _ = rank_point_in_time_rs(frames, _prepared_frames()[1])
    noncontracting = ranked["AAA"].copy()
    noncontracting.loc[68:71, "True_Range"] = 4.0
    _, candidates = scan_symbol_bases("AAA", noncontracting)
    assert int(candidates["Signal_Qualified"].sum()) == 0
    too_short = ranked["AAA"].copy()
    too_short.loc[71, ["High", "Close"]] = [101.0, 101.0]
    _, candidates = scan_symbol_bases("AAA", too_short)
    assert candidates.empty
