"""Analyze Strategy V3 entries with locked exits, diagnostics, and gates."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from build_v3_features import MIN_RS_COVERAGE, active_members_on
from generate_v3_signals import (
    MIN_COMPOSITE_RS,
    _next_session,
    prewindow_seed_start,
)


SIGNAL_START = pd.Timestamp("2023-08-01")
SIGNAL_END = pd.Timestamp("2026-08-25")


def _finite(value: object) -> bool:
    try:
        return bool(pd.notna(value) and np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _truthy(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _truthy_series(series: pd.Series) -> pd.Series:
    return series.map(_truthy)


def _prices_for_trade(prices: pd.DataFrame) -> pd.DataFrame:
    required = {"Date", "Open", "High", "Low", "Close", "SMA20"}
    missing = required.difference(prices.columns)
    if missing:
        raise ValueError(f"trade prices missing columns: {sorted(missing)}")
    result = prices.copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
    if getattr(result["Date"].dt, "tz", None) is not None:
        result["Date"] = result["Date"].dt.tz_localize(None)
    if result["Date"].isna().any() or result["Date"].duplicated().any():
        raise ValueError("trade prices contain invalid or duplicate dates")
    return result.sort_values("Date").reset_index(drop=True)


def _result_base(entry_row: pd.Series, exit_row: pd.Series, exit_reason: str) -> dict[str, object]:
    entry_open = float(entry_row["Entry_Open"])
    exit_price = float(exit_row["Open"])
    result = entry_row.to_dict()
    result.update(
        {
            "Exit_Date": pd.Timestamp(exit_row["Date"]),
            "Exit_Price": exit_price,
            "Exit_Reason": exit_reason,
            "Return": (exit_price - entry_open) / entry_open,
        }
    )
    return result


def simulate_setup_quality_trade(entry_row: pd.Series, prices: pd.DataFrame) -> dict[str, object] | None:
    """Exit at the next open after the first close below SMA20."""

    data = _prices_for_trade(prices)
    entry_date = pd.Timestamp(entry_row["Entry_Date"])
    positions = np.flatnonzero(data["Date"].eq(entry_date))
    if len(positions) == 0 or not _finite(entry_row.get("Entry_Open", np.nan)):
        return None
    entry_index = int(positions[0])
    for index in range(entry_index, len(data)):
        close = data.loc[index, "Close"]
        sma20 = data.loc[index, "SMA20"]
        if _finite(close) and _finite(sma20) and float(close) < float(sma20):
            if index + 1 >= len(data) or not _finite(data.loc[index + 1, "Open"]):
                return None
            result = _result_base(entry_row, data.loc[index + 1], "SMA20")
            result["Exit_Signal_Date"] = pd.Timestamp(data.loc[index, "Date"])
            result["Holding_Sessions"] = index + 1 - entry_index
            return result
    return None


def simulate_practical_trade(entry_row: pd.Series, prices: pd.DataFrame) -> dict[str, object] | None:
    """Apply scheduled SMA20 exit before the fixed structural stop."""

    data = _prices_for_trade(prices)
    entry_date = pd.Timestamp(entry_row["Entry_Date"])
    positions = np.flatnonzero(data["Date"].eq(entry_date))
    stop = entry_row.get("Structural_Stop", np.nan)
    entry_open = entry_row.get("Entry_Open", np.nan)
    if len(positions) == 0 or not _finite(stop) or not _finite(entry_open):
        return None
    entry_index = int(positions[0])
    scheduled_sma20_exit = False
    exit_signal_date: pd.Timestamp | None = None
    for index in range(entry_index, len(data)):
        row = data.loc[index]
        if scheduled_sma20_exit:
            if not _finite(row["Open"]):
                return None
            result = _result_base(entry_row, row, "SMA20")
            result["Exit_Signal_Date"] = exit_signal_date
            result["Initial_Risk"] = float(entry_open) - float(stop)
            result["R_Multiple"] = (result["Exit_Price"] - float(entry_open)) / result["Initial_Risk"]
            result["Holding_Sessions"] = index - entry_index
            return result
        if not _finite(row["Open"]) or not _finite(row["Low"]):
            return None
        if float(row["Open"]) <= float(stop):
            result = _result_base(entry_row, row, "STOP_GAP")
            result["Initial_Risk"] = float(entry_open) - float(stop)
            result["R_Multiple"] = (result["Exit_Price"] - float(entry_open)) / result["Initial_Risk"]
            result["Holding_Sessions"] = index - entry_index
            return result
        if float(row["Low"]) <= float(stop):
            result = _result_base(entry_row, row, "STOP_INTRADAY")
            result["Exit_Price"] = float(stop)
            result["Return"] = (result["Exit_Price"] - float(entry_open)) / float(entry_open)
            result["Initial_Risk"] = float(entry_open) - float(stop)
            result["R_Multiple"] = (result["Exit_Price"] - float(entry_open)) / result["Initial_Risk"]
            result["Holding_Sessions"] = index - entry_index
            return result
        if _finite(row["Close"]) and _finite(row["SMA20"]) and float(row["Close"]) < float(row["SMA20"]):
            scheduled_sma20_exit = True
            exit_signal_date = pd.Timestamp(row["Date"])
    return None


def safe_profit_factor(values: pd.Series) -> float:
    """Return profit factor with explicit no-win/no-loss behavior."""

    numeric = pd.to_numeric(values, errors="coerce").dropna()
    positive = float(numeric.loc[numeric > 0].sum())
    negative = float(numeric.loc[numeric < 0].sum())
    if positive and not negative:
        return np.inf
    if negative and not positive:
        return 0.0
    if not positive and not negative:
        return np.nan
    return positive / abs(negative)


def attach_prior_breadth(trades: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame:
    """Attach the latest breadth row strictly before each entry date."""

    if trades.empty:
        return trades.copy()
    if "Entry_Date" not in trades or "Date" not in breadth:
        raise ValueError("trades need Entry_Date and breadth needs Date")
    left = trades.copy()
    right = breadth.copy()
    left["Entry_Date"] = pd.to_datetime(left["Entry_Date"], errors="coerce")
    right["Date"] = pd.to_datetime(right["Date"], errors="coerce")
    if left["Entry_Date"].isna().any() or right["Date"].isna().any():
        raise ValueError("breadth join contains invalid dates")
    left["_original_order"] = np.arange(len(left))
    right = right.rename(columns={"Date": "Breadth_Matched_Date"})
    joined = pd.merge_asof(
        left.sort_values("Entry_Date"),
        right.sort_values("Breadth_Matched_Date"),
        left_on="Entry_Date",
        right_on="Breadth_Matched_Date",
        direction="backward",
        allow_exact_matches=False,
    )
    matched = joined["Breadth_Matched_Date"].notna()
    if (joined.loc[matched, "Breadth_Matched_Date"] >= joined.loc[matched, "Entry_Date"]).any():
        raise AssertionError("breadth match is not strictly before entry")
    return joined.sort_values("_original_order").drop(columns="_original_order").reset_index(drop=True)


def validate_trade_integrity(setup: pd.DataFrame, practical: pd.DataFrame) -> None:
    """Reject mismatched lens samples and non-strict breadth timing."""

    setup_ids = set(setup.get("Entry_ID", pd.Series(dtype=str)).astype(str))
    practical_ids = set(practical.get("Entry_ID", pd.Series(dtype=str)).astype(str))
    if setup_ids != practical_ids:
        raise AssertionError("setup/practical accepted Entry_ID sets differ")
    for trades in (setup, practical):
        if trades.empty or "Breadth_Matched_Date" not in trades.columns:
            continue
        entry_dates = pd.to_datetime(trades["Entry_Date"], errors="raise")
        breadth_dates = pd.to_datetime(trades["Breadth_Matched_Date"], errors="coerce")
        matched = breadth_dates.notna()
        if (breadth_dates.loc[matched] >= entry_dates.loc[matched]).any():
            raise AssertionError("breadth context is not strictly prior to entry")


def _membership_is_active(membership: pd.DataFrame, symbol: str, date: object) -> bool:
    try:
        day = pd.Timestamp(date)
    except (TypeError, ValueError):
        return False
    if pd.isna(day):
        return False
    active = active_members_on(membership, day)
    return symbol in set(active["Symbol"].astype(str))


def _append_violation(
    violations: list[dict[str, object]],
    entry_id: object,
    symbol: object,
    code: str,
) -> None:
    violations.append(
        {
            "Entry_ID": str(entry_id),
            "Symbol": str(symbol),
            "Violation": code,
        }
    )


def count_point_in_time_violations(
    signals: pd.DataFrame,
    entries: pd.DataFrame,
    setup: pd.DataFrame,
    practical: pd.DataFrame,
    membership: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex,
) -> tuple[int, pd.DataFrame]:
    """Derive all PIT violations from signal, entry, outcome, and manifest artifacts."""

    violations: list[dict[str, object]] = []
    qualified = signals.loc[
        signals.get("Signal_Qualified", pd.Series(False, index=signals.index)).map(_truthy)
    ].copy()
    qualified_ids = set(qualified.get("Entry_ID", pd.Series(dtype=str)).astype(str))
    for _, entry in entries.iterrows():
        entry_id = str(entry.get("Entry_ID", ""))
        if entry_id not in qualified_ids:
            _append_violation(
                violations,
                entry_id,
                entry.get("Symbol", ""),
                "ACCEPTED_ENTRY_MISSING_QUALIFIED_SIGNAL",
            )

    try:
        seed_start = prewindow_seed_start(canonical_sessions)
    except ValueError:
        seed_start = None
    sessions = pd.DatetimeIndex(pd.to_datetime(canonical_sessions, errors="coerce"))
    sessions = sessions.dropna().drop_duplicates().sort_values()

    for _, signal in qualified.iterrows():
        entry_id = signal.get("Entry_ID", "")
        symbol = signal.get("Symbol", "")
        leader_date = pd.to_datetime(signal.get("Leader_Date"), errors="coerce")
        signal_date = pd.to_datetime(signal.get("Signal_Date"), errors="coerce")
        if pd.isna(leader_date) or pd.isna(signal_date) or leader_date >= signal_date:
            _append_violation(violations, entry_id, symbol, "LEADER_NOT_BEFORE_SIGNAL")
        if pd.isna(signal_date) or not SIGNAL_START <= signal_date <= SIGNAL_END:
            _append_violation(violations, entry_id, symbol, "SIGNAL_OUTSIDE_PRIMARY_WINDOW")
        if pd.notna(leader_date) and leader_date < SIGNAL_START and (seed_start is None or leader_date < seed_start):
            _append_violation(violations, entry_id, symbol, "PREWINDOW_SEED_TOO_EARLY")
        if not _membership_is_active(membership, str(symbol), leader_date):
            _append_violation(violations, entry_id, symbol, "SEED_INACTIVE_MEMBER")
        if not _membership_is_active(membership, str(symbol), signal_date):
            _append_violation(violations, entry_id, symbol, "SIGNAL_INACTIVE_MEMBER")
        if "Seed_RS_Coverage_OK" in signal.index and not _truthy(signal["Seed_RS_Coverage_OK"]):
            _append_violation(violations, entry_id, symbol, "SEED_RS_COVERAGE_UNSAFE")
        if "Signal_RS_Coverage_OK" in signal.index and not _truthy(signal["Signal_RS_Coverage_OK"]):
            _append_violation(violations, entry_id, symbol, "SIGNAL_RS_COVERAGE_UNSAFE")
        if "RS_Coverage" in signal.index:
            coverage = pd.to_numeric(pd.Series([signal["RS_Coverage"]]), errors="coerce").iloc[0]
            if pd.isna(coverage) or float(coverage) < MIN_RS_COVERAGE:
                _append_violation(violations, entry_id, symbol, "SIGNAL_RS_COVERAGE_UNSAFE")
        if "Seed_RS_OK" in signal.index and not _truthy(signal["Seed_RS_OK"]):
            _append_violation(violations, entry_id, symbol, "SEED_RS_BELOW_THRESHOLD")
        composite = pd.to_numeric(pd.Series([signal.get("Composite_RS", np.nan)]), errors="coerce").iloc[0]
        if pd.isna(composite) or float(composite) < MIN_COMPOSITE_RS:
            _append_violation(violations, entry_id, symbol, "SIGNAL_RS_BELOW_THRESHOLD")

    if not entries.empty and not qualified.empty:
        required = ["Entry_ID", "Symbol", "Leader_Date", "Signal_Date"]
        signal_columns = [column for column in required if column in qualified.columns]
        merged = entries.merge(
            qualified[signal_columns],
            on=["Entry_ID", "Symbol"],
            how="inner",
            suffixes=("_entry", "_signal"),
            validate="one_to_one",
        )
        for _, row in merged.iterrows():
            entry_id = row["Entry_ID"]
            symbol = row["Symbol"]
            signal_date = pd.to_datetime(row.get("Signal_Date_signal"), errors="coerce")
            entry_date = pd.to_datetime(row.get("Entry_Date"), errors="coerce")
            if pd.isna(signal_date) or pd.isna(entry_date) or signal_date >= entry_date:
                _append_violation(violations, entry_id, symbol, "SIGNAL_NOT_BEFORE_ENTRY")
            if pd.notna(signal_date) and pd.notna(entry_date) and _next_session(signal_date, sessions) != entry_date:
                _append_violation(violations, entry_id, symbol, "ENTRY_NOT_IMMEDIATE_NEXT_SESSION")

    for frame, code in (
        (setup, "BREADTH_NOT_STRICT_PRIOR_SETUP"),
        (practical, "BREADTH_NOT_STRICT_PRIOR_PRACTICAL"),
    ):
        if frame.empty or "Breadth_Matched_Date" not in frame.columns:
            continue
        entry_dates = pd.to_datetime(frame["Entry_Date"], errors="coerce")
        breadth_dates = pd.to_datetime(frame["Breadth_Matched_Date"], errors="coerce")
        bad = breadth_dates.notna() & (breadth_dates >= entry_dates)
        for _, row in frame.loc[bad].iterrows():
            _append_violation(violations, row.get("Entry_ID", ""), row.get("Symbol", ""), code)

    setup_ids = set(setup.get("Entry_ID", pd.Series(dtype=str)).astype(str))
    practical_ids = set(practical.get("Entry_ID", pd.Series(dtype=str)).astype(str))
    for entry_id in sorted(setup_ids.symmetric_difference(practical_ids)):
        _append_violation(violations, entry_id, "", "LENS_ENTRY_ID_MISMATCH")

    audit = pd.DataFrame(violations, columns=["Entry_ID", "Symbol", "Violation"])
    return len(audit), audit


def summarize_lens(trades: pd.DataFrame, lens: str) -> dict[str, object]:
    """Summarize one completed trade lens."""

    if lens not in {"setup", "practical"}:
        raise ValueError("lens must be setup or practical")
    returns = pd.to_numeric(trades.get("Return", pd.Series(dtype=float)), errors="coerce")
    r_values = pd.to_numeric(trades.get("R_Multiple", pd.Series(dtype=float)), errors="coerce")
    holding = pd.to_numeric(trades.get("Holding_Sessions", pd.Series(dtype=float)), errors="coerce")
    measure = returns if lens == "setup" else r_values
    return {
        "Completed_Trades": int(measure.notna().sum()),
        "Winners": int((measure > 0).sum()),
        "Losers": int((measure < 0).sum()),
        "Win_Rate": float((measure > 0).mean()) if len(measure) else np.nan,
        "Mean_Return": float(returns.mean()) if returns.notna().any() else np.nan,
        "Median_Return": float(returns.median()) if returns.notna().any() else np.nan,
        "Return_PF": safe_profit_factor(returns),
        "Mean_R": float(r_values.mean()) if r_values.notna().any() else np.nan,
        "Median_R": float(r_values.median()) if r_values.notna().any() else np.nan,
        "R_PF": safe_profit_factor(r_values),
        "Median_Holding_Sessions": float(holding.median()) if holding.notna().any() else np.nan,
    }


def _paired_trades(setup: pd.DataFrame, practical: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ids = set(setup.get("Entry_ID", pd.Series(dtype=str)).astype(str)) & set(
        practical.get("Entry_ID", pd.Series(dtype=str)).astype(str)
    )
    return (
        setup.loc[setup["Entry_ID"].astype(str).isin(ids)].copy() if "Entry_ID" in setup else setup.copy(),
        practical.loc[practical["Entry_ID"].astype(str).isin(ids)].copy()
        if "Entry_ID" in practical
        else practical.copy(),
    )


def year_summary(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame:
    setup, practical = _paired_trades(setup, practical)
    setup_dates = pd.to_datetime(setup.get("Entry_Date", pd.Series(dtype="datetime64[ns]")), errors="coerce")
    practical_dates = pd.to_datetime(practical.get("Entry_Date", pd.Series(dtype="datetime64[ns]")), errors="coerce")
    years = sorted(set(setup_dates.dropna().dt.year) | set(practical_dates.dropna().dt.year))
    rows: list[dict[str, object]] = []
    for year in years:
        setup_year = setup.loc[setup_dates.dt.year.eq(year)]
        practical_year = practical.loc[practical_dates.dt.year.eq(year)]
        setup_metrics = summarize_lens(setup_year, "setup")
        practical_metrics = summarize_lens(practical_year, "practical")
        rows.append(
            {
                "Entry_Year": int(year),
                **{f"Setup_{key}": value for key, value in setup_metrics.items()},
                **{f"Practical_{key}": value for key, value in practical_metrics.items()},
            }
        )
    return pd.DataFrame(rows)


def outlier_robustness(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame:
    setup, practical = _paired_trades(setup, practical)
    columns = [
        "Removed_Top_N",
        "Removed_Entry_IDs",
        "Removed_Symbols",
        "Remaining_Entry_Count",
        "Setup_Mean_Return",
        "Setup_Return_PF",
        "Practical_Mean_R",
        "Practical_R_PF",
    ]
    if setup.empty:
        return pd.DataFrame(columns=columns)
    ranked = setup.sort_values(["Return", "Entry_ID"], ascending=[False, True]).reset_index(drop=True)
    rows: list[dict[str, object]] = []
    for count in (1, 3, 5):
        removed = ranked.head(count)
        remaining_ids = set(ranked.iloc[count:]["Entry_ID"].astype(str))
        setup_remaining = setup.loc[setup["Entry_ID"].astype(str).isin(remaining_ids)]
        practical_remaining = practical.loc[practical["Entry_ID"].astype(str).isin(remaining_ids)]
        setup_metrics = summarize_lens(setup_remaining, "setup")
        practical_metrics = summarize_lens(practical_remaining, "practical")
        rows.append(
            {
                "Removed_Top_N": count,
                "Removed_Entry_IDs": ";".join(removed["Entry_ID"].astype(str)),
                "Removed_Symbols": ";".join(removed.get("Symbol", pd.Series(dtype=str)).astype(str)),
                "Remaining_Entry_Count": len(remaining_ids),
                "Setup_Mean_Return": setup_metrics["Mean_Return"],
                "Setup_Return_PF": setup_metrics["Return_PF"],
                "Practical_Mean_R": practical_metrics["Mean_R"],
                "Practical_R_PF": practical_metrics["R_PF"],
            }
        )
    return pd.DataFrame(rows, columns=columns)


def leave_one_symbol_out(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame:
    setup, practical = _paired_trades(setup, practical)
    symbols = sorted(set(setup.get("Symbol", pd.Series(dtype=str)).dropna().astype(str)))
    rows: list[dict[str, object]] = []
    for symbol in symbols:
        setup_remaining = setup.loc[setup["Symbol"].astype(str) != symbol]
        practical_remaining = practical.loc[practical["Symbol"].astype(str) != symbol]
        setup_metrics = summarize_lens(setup_remaining, "setup")
        practical_metrics = summarize_lens(practical_remaining, "practical")
        rows.append(
            {
                "Omitted_Symbol": symbol,
                "Remaining_Entry_Count": len(setup_remaining),
                "Setup_Mean_Return": setup_metrics["Mean_Return"],
                "Setup_Return_PF": setup_metrics["Return_PF"],
                "Practical_Mean_R": practical_metrics["Mean_R"],
                "Practical_R_PF": practical_metrics["R_PF"],
            }
        )
    return pd.DataFrame(rows)


def overlap_diagnostic(entries: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame:
    """Measure overlap across every accepted entry, including incomplete positions."""

    if entries.empty:
        return pd.DataFrame(
            [
                {
                    "Total_Accepted_Entries": 0,
                    "Entries_With_Another_Open_Same_Symbol_Trade": 0,
                    "Max_Simultaneous_Signal_Level_Trades": 0,
                    "Max_Same_Day_Entries": 0,
                }
            ]
        )
    data = entries[["Entry_ID", "Symbol", "Entry_Date"]].copy()
    data["Entry_ID"] = data["Entry_ID"].astype(str)
    data["Entry_Date"] = pd.to_datetime(data["Entry_Date"], errors="raise")
    if practical.empty:
        exits = pd.DataFrame(columns=["Entry_ID", "Exit_Date"])
    else:
        exits = practical[["Entry_ID", "Exit_Date"]].copy()
        exits["Entry_ID"] = exits["Entry_ID"].astype(str)
        exits["Exit_Date"] = pd.to_datetime(exits["Exit_Date"], errors="raise")
    data = data.merge(exits, on="Entry_ID", how="left", validate="one_to_one")
    latest_entry = data["Entry_Date"].max()
    latest_exit = exits["Exit_Date"].max() if not exits.empty else latest_entry
    observation_end = max(latest_entry, latest_exit)
    data["Effective_Exit_Date"] = data["Exit_Date"].fillna(observation_end)
    overlap_count = 0
    max_simultaneous = 0
    for _, current in data.iterrows():
        others = data.loc[
            (data["Symbol"] == current["Symbol"])
            & (data["Entry_ID"] != current["Entry_ID"])
            & (data["Entry_Date"] <= current["Entry_Date"])
            & (data["Effective_Exit_Date"] >= current["Entry_Date"])
        ]
        overlap_count += int(not others.empty)
    for date in sorted(set(data["Entry_Date"])):
        open_at_date = data.loc[
            (data["Entry_Date"] <= date) & (data["Effective_Exit_Date"] >= date)
        ]
        max_simultaneous = max(max_simultaneous, len(open_at_date))
    return pd.DataFrame(
        [
            {
                "Total_Accepted_Entries": len(data),
                "Entries_With_Another_Open_Same_Symbol_Trade": overlap_count,
                "Max_Simultaneous_Signal_Level_Trades": max_simultaneous,
                "Max_Same_Day_Entries": int(data["Entry_Date"].value_counts().max()),
            }
        ]
    )


def _bucket_value(dimension: str, row: pd.Series) -> str | None:
    value_name = {
        "Pullback_Age": "Pullback_Age",
        "Pullback_Depth_ATR": "Pullback_Depth_ATR",
        "Composite_RS": "Composite_RS",
        "Resumption_Volume_Ratio": "Resumption_Volume_Ratio",
        "Entry_Extension_ATR_vs_Leader": "Entry_Extension_ATR_vs_Leader",
    }[dimension]
    value = row.get(value_name, np.nan)
    if dimension == "Resumption_Volume_Ratio" and not _finite(value):
        return "MISSING"
    if not _finite(value):
        return None
    number = float(value)
    if dimension == "Pullback_Age":
        return next((bucket for bucket, low, high in [("3-4", 3, 4), ("5-6", 5, 6), ("7-8", 7, 8), ("9-10", 9, 10)] if low <= number <= high), None)
    if dimension == "Pullback_Depth_ATR":
        if 0.5 <= number < 1.0:
            return "[0.5,1.0)"
        if 1.0 <= number < 1.5:
            return "[1.0,1.5)"
        if 1.5 <= number < 2.0:
            return "[1.5,2.0)"
        if 2.0 <= number <= 2.5:
            return "[2.0,2.5]"
    if dimension == "Composite_RS":
        if 70 <= number < 80:
            return "[70,80)"
        if 80 <= number < 90:
            return "[80,90)"
        if 90 <= number <= 100:
            return "[90,100]"
    if dimension == "Resumption_Volume_Ratio":
        if number < 0.8:
            return "<0.8"
        if number < 1.2:
            return "[0.8,1.2)"
        return ">=1.2"
    if dimension == "Entry_Extension_ATR_vs_Leader":
        if number <= 0:
            return "<=0"
        if number <= 0.25:
            return "(0,0.25]"
        if number <= 0.5:
            return "(0.25,0.5]"
    return None


def pullback_diagnostics(entries: pd.DataFrame, setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame:
    """Summarize fixed diagnostic buckets without turning them into gates."""

    paired_setup, paired_practical = _paired_trades(setup, practical)
    if paired_setup.empty:
        paired = pd.DataFrame()
    else:
        metadata = entries.copy()
        metadata["Entry_ID"] = metadata["Entry_ID"].astype(str)
        paired = paired_setup.copy()
        paired["Entry_ID"] = paired["Entry_ID"].astype(str)
        for column in [
            "Pullback_Age",
            "Pullback_Depth_ATR",
            "Composite_RS",
            "Resumption_Volume_Ratio",
            "Entry_Open",
            "Leader_Close",
            "ATR14_Signal",
        ]:
            if column not in paired.columns and column in metadata.columns:
                paired = paired.merge(metadata[["Entry_ID", column]], on="Entry_ID", how="left", validate="one_to_one")
        paired["Entry_Extension_ATR_vs_Leader"] = (
            pd.to_numeric(paired.get("Entry_Open"), errors="coerce")
            - pd.to_numeric(paired.get("Leader_Close"), errors="coerce")
        ) / pd.to_numeric(paired.get("ATR14_Signal"), errors="coerce")
        practical_by_id = paired_practical.set_index(paired_practical["Entry_ID"].astype(str))
        paired["_Practical_R"] = paired["Entry_ID"].map(
            pd.to_numeric(practical_by_id["R_Multiple"], errors="coerce")
        )

    fixed = {
        "Pullback_Age": ["3-4", "5-6", "7-8", "9-10"],
        "Pullback_Depth_ATR": ["[0.5,1.0)", "[1.0,1.5)", "[1.5,2.0)", "[2.0,2.5]"],
        "Composite_RS": ["[70,80)", "[80,90)", "[90,100]"],
        "Resumption_Volume_Ratio": ["<0.8", "[0.8,1.2)", ">=1.2", "MISSING"],
        "Entry_Extension_ATR_vs_Leader": ["<=0", "(0,0.25]", "(0.25,0.5]"],
    }
    rows: list[dict[str, object]] = []
    for dimension, buckets in fixed.items():
        for bucket in buckets:
            if paired.empty:
                selected = paired
            else:
                mask = paired.apply(lambda row: _bucket_value(dimension, row) == bucket, axis=1)
                selected = paired.loc[mask]
            practical_selected = paired_practical.loc[
                paired_practical["Entry_ID"].astype(str).isin(set(selected["Entry_ID"].astype(str)))
            ] if not selected.empty else paired_practical.iloc[0:0]
            setup_metrics = summarize_lens(selected, "setup")
            practical_metrics = summarize_lens(practical_selected, "practical")
            rows.append(
                {
                    "Dimension": dimension,
                    "Bucket": bucket,
                    "Completed_Trades": setup_metrics["Completed_Trades"],
                    "Setup_Mean_Return": setup_metrics["Mean_Return"],
                    "Setup_Return_PF": setup_metrics["Return_PF"],
                    "Practical_Mean_R": practical_metrics["Mean_R"],
                    "Practical_R_PF": practical_metrics["R_PF"],
                }
            )
    return pd.DataFrame(rows)


def evaluate_gates(
    setup: pd.DataFrame,
    practical: pd.DataFrame,
    *,
    point_in_time_violations: int,
) -> pd.DataFrame:
    """Evaluate the precommitted V3 gates without optimizing any threshold."""

    setup, practical = _paired_trades(setup, practical)
    setup_metrics = summarize_lens(setup, "setup")
    practical_metrics = summarize_lens(practical, "practical")
    years = year_summary(setup, practical)
    qualifying_years = (
        years.loc[
            (years["Setup_Completed_Trades"] >= 20)
            & (years["Setup_Mean_Return"] > 0)
            & (years["Setup_Return_PF"] >= 1.0)
        ]
        if not years.empty
        else pd.DataFrame()
    )
    outliers = outlier_robustness(setup, practical)
    leave_out = leave_one_symbol_out(setup, practical)
    top_five = outliers.loc[outliers["Removed_Top_N"].eq(5)] if not outliers.empty else pd.DataFrame()
    rows = [
        {"Gate": "COMPLETED_TRADES", "Passed": len(setup) >= 100, "Value": len(setup)},
        {"Gate": "SETUP_MEAN_RETURN", "Passed": bool(setup_metrics["Mean_Return"] > 0), "Value": setup_metrics["Mean_Return"]},
        {"Gate": "SETUP_RETURN_PF", "Passed": bool(setup_metrics["Return_PF"] >= 1.20), "Value": setup_metrics["Return_PF"]},
        {"Gate": "PRACTICAL_MEAN_R", "Passed": bool(practical_metrics["Mean_R"] >= 0.15), "Value": practical_metrics["Mean_R"]},
        {"Gate": "PRACTICAL_R_PF", "Passed": bool(practical_metrics["R_PF"] >= 1.20), "Value": practical_metrics["R_PF"]},
        {"Gate": "TEMPORAL_ROBUSTNESS", "Passed": len(qualifying_years) >= 2, "Value": len(qualifying_years)},
        {
            "Gate": "TOP_FIVE_OUTLIER_ROBUSTNESS",
            "Passed": bool(
                not top_five.empty
                and top_five.iloc[0]["Setup_Mean_Return"] > 0
                and top_five.iloc[0]["Setup_Return_PF"] >= 1.0
            ),
            "Value": "top5",
        },
        {
            "Gate": "LEAVE_ONE_SYMBOL_OUT",
            "Passed": bool(
                not leave_out.empty
                and (leave_out["Setup_Mean_Return"] > 0).all()
                and (leave_out["Setup_Return_PF"] >= 1.0).all()
            ),
            "Value": len(leave_out),
        },
        {
            "Gate": "POINT_IN_TIME_INTEGRITY",
            "Passed": point_in_time_violations == 0,
            "Value": point_in_time_violations,
        },
    ]
    all_passed = all(bool(row["Passed"]) for row in rows)
    status = "INSUFFICIENT_EVIDENCE" if len(setup) < 100 else ("PASS" if all_passed else "FAIL")
    rows.append({"Gate": "FINAL_STATUS", "Passed": status == "PASS", "Value": status, "Status": status})
    result = pd.DataFrame(rows)
    result["Status"] = result.get("Status", result["Passed"].map(lambda value: "PASS" if value else "FAIL"))
    result.loc[result["Gate"] != "FINAL_STATUS", "Status"] = result.loc[
        result["Gate"] != "FINAL_STATUS", "Passed"
    ].map(lambda value: "PASS" if value else "FAIL")
    return result
