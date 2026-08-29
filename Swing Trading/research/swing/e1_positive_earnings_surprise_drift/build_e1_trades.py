"""Construct identical signal-level E1 stock and benchmark trade outcomes."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from constants import BASE_FRICTION, SEVERE_FRICTION, STRESS_FRICTION


TRADE_OUTPUT_COLUMNS = [
    "Event_ID", "Symbol", "Cohort", "SUE", "Event_Public_Date", "Entry_Date", "Entry_Open",
    "Exit_Date", "Exit_Open", "Exit_Reason", "Holding_Sessions", "Gross_Return",
    "Base_Net_Return", "Stress_Net_Return", "Severe_Net_Return", "Nifty500_Entry_Open",
    "Nifty500_Exit_Open", "Benchmark_Return", "Base_Net_Excess_Return",
    "Stress_Net_Excess_Return", "Previous_Close", "Entry_Gap", "MAE", "MFE",
    "Max_Trade_Drawdown",
]


def _date(value: object) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    stamp = pd.Timestamp(parsed)
    if stamp.tz is not None:
        stamp = stamp.tz_convert("Asia/Kolkata").tz_localize(None)
    return stamp.normalize()


def _timestamp(value: object) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    stamp = pd.Timestamp(parsed)
    return stamp.tz_localize("Asia/Kolkata") if stamp.tz is None else stamp.tz_convert("Asia/Kolkata")


def _sessions(frame: pd.DataFrame) -> pd.DatetimeIndex:
    if frame is None or "Date" not in frame.columns:
        return pd.DatetimeIndex([])
    dates = pd.DatetimeIndex(pd.to_datetime(frame["Date"], errors="coerce"))
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    dates = dates[~dates.isna()].normalize()
    return pd.DatetimeIndex(sorted(set(dates)))


def canonical_sessions(index_prices: pd.DataFrame) -> pd.DatetimeIndex:
    """Return the frozen benchmark session calendar used for all trade timing."""

    return _sessions(index_prices)


def next_session_after(date: pd.Timestamp, sessions: pd.DatetimeIndex) -> pd.Timestamp | None:
    """Return the first canonical session strictly after a public date."""

    days = pd.DatetimeIndex(sessions).normalize().sort_values().unique()
    day = _date(date)
    if pd.isna(day):
        return None
    position = int(days.searchsorted(day, side="right"))
    return days[position] if position < len(days) else None


def scheduled_exit_session(
    entry_date: pd.Timestamp,
    sessions: pd.DatetimeIndex,
    completed_sessions: int = 40,
) -> pd.Timestamp | None:
    """Return the session-41 open after 40 complete sessions including entry."""

    days = pd.DatetimeIndex(sessions).normalize().sort_values().unique()
    entry = _date(entry_date)
    if pd.isna(entry) or completed_sessions < 1:
        return None
    position = int(days.searchsorted(entry, side="left"))
    if position >= len(days) or days[position] != entry:
        return None
    exit_position = position + completed_sessions
    return days[exit_position] if exit_position < len(days) else None


def next_distinct_quarterly_result(
    symbol: str,
    after_timestamp: pd.Timestamp,
    all_original_events: pd.DataFrame,
) -> pd.Series | None:
    """Find the next original result for a different fiscal period."""

    required = {"Symbol", "Fiscal_Period_End", "Event_Public_Timestamp", "Original_or_Revised"}
    if all_original_events.empty or not required.issubset(all_original_events.columns):
        return None
    after = _timestamp(after_timestamp)
    frame = all_original_events.copy()
    frame["Symbol"] = frame["Symbol"].astype(str).str.upper().str.strip()
    frame["Fiscal_Period_End"] = frame["Fiscal_Period_End"].map(_date)
    frame["_Timestamp"] = frame["Event_Public_Timestamp"].map(_timestamp)
    frame = frame.loc[
        frame["Symbol"].eq(str(symbol).upper().strip())
        & frame["Original_or_Revised"].astype(str).str.upper().eq("ORIGINAL")
        & frame["_Timestamp"].gt(after)
    ].sort_values(["_Timestamp", "Fiscal_Period_End"], kind="stable")
    seen_periods: set[pd.Timestamp] = set()
    for _, row in frame.iterrows():
        period = row["Fiscal_Period_End"]
        if period in seen_periods:
            continue
        seen_periods.add(period)
        return row
    return None


def _row_on_date(frame: pd.DataFrame, date: pd.Timestamp) -> pd.Series | None:
    dates = pd.to_datetime(frame["Date"], errors="coerce")
    if getattr(dates.dt, "tz", None) is not None:
        dates = dates.dt.tz_localize(None)
    matches = frame.loc[dates.dt.normalize().eq(_date(date))]
    return matches.iloc[0] if len(matches) else None


def _finite_open(row: pd.Series | None) -> float | None:
    if row is None:
        return None
    value = pd.to_numeric(row.get("Open"), errors="coerce")
    return float(value) if pd.notna(value) and np.isfinite(value) and value > 0 else None


def build_trade_for_event(
    event: pd.Series,
    stock_prices: pd.DataFrame,
    index_prices: pd.DataFrame,
    all_original_events: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex | None = None,
) -> tuple[dict[str, object] | None, str]:
    """Build one completed trade using the same lifecycle for every cohort."""

    if stock_prices.empty or index_prices.empty:
        return None, "NO_VALID_NEXT_SESSION_OPEN"
    stock = stock_prices.copy()
    stock["Date"] = stock["Date"].map(_date)
    stock = stock.sort_values("Date").drop_duplicates("Date", keep="first")
    index = index_prices.copy()
    index["Date"] = index["Date"].map(_date)
    index = index.sort_values("Date").drop_duplicates("Date", keep="first")
    sessions = (
        pd.DatetimeIndex(canonical_sessions).normalize().sort_values().unique()
        if canonical_sessions is not None
        else _sessions(index)
    )
    if len(sessions) == 0:
        return None, "NO_VALID_NEXT_SESSION_OPEN"
    event_date = _date(event.get("Event_Public_Date", event.get("Event_Public_Timestamp")))
    entry_date = next_session_after(event_date, sessions)
    if entry_date is None:
        return None, "NO_VALID_NEXT_SESSION_OPEN"
    entry_row = _row_on_date(stock, entry_date)
    entry_open = _finite_open(entry_row)
    if entry_open is None:
        return None, "NO_VALID_NEXT_SESSION_OPEN"
    scheduled_exit = scheduled_exit_session(entry_date, sessions, 40)
    if scheduled_exit is None:
        return None, "INSUFFICIENT_PRICE_HISTORY"
    event_timestamp = _timestamp(event.get("Event_Public_Timestamp", event_date))
    next_event = next_distinct_quarterly_result(str(event.get("Symbol", "")), event_timestamp, all_original_events)
    exit_date = scheduled_exit
    exit_reason = "EXIT_40_SESSION_SCHEDULED"
    if next_event is not None:
        next_event_session = next_session_after(next_event.get("Event_Public_Timestamp"), sessions)
        if next_event_session is not None and next_event_session <= scheduled_exit:
            exit_date = next_event_session
            exit_reason = "EXIT_NEXT_EARNINGS_EVENT"
    exit_row = _row_on_date(stock, exit_date)
    exit_open = _finite_open(exit_row)
    if exit_open is None:
        return None, "NO_VALID_EXIT_OPEN"

    index_entry = _row_on_date(index, entry_date)
    index_exit = _row_on_date(index, exit_date)
    nifty_entry_open = _finite_open(index_entry)
    nifty_exit_open = _finite_open(index_exit)
    if nifty_entry_open is None or nifty_exit_open is None:
        return None, "BENCHMARK_DATE_MISMATCH"

    entry_position = int(sessions.get_loc(entry_date))
    exit_position = int(sessions.get_loc(exit_date))
    holding_sessions = exit_position - entry_position
    held = stock.loc[stock["Date"].ge(entry_date) & stock["Date"].lt(exit_date)].copy()
    high = pd.to_numeric(held.get("High", pd.Series(dtype=float)), errors="coerce")
    low = pd.to_numeric(held.get("Low", pd.Series(dtype=float)), errors="coerce")
    pre_entry = stock.loc[stock["Date"].lt(entry_date)].tail(1)
    previous_close = (
        float(pd.to_numeric(pre_entry.iloc[0].get("Close"), errors="coerce"))
        if len(pre_entry) and pd.notna(pd.to_numeric(pre_entry.iloc[0].get("Close"), errors="coerce"))
        else np.nan
    )
    gross = exit_open / entry_open - 1.0
    benchmark = nifty_exit_open / nifty_entry_open - 1.0
    return {
        "Event_ID": event.get("Event_ID", ""),
        "Symbol": str(event.get("Symbol", "")).upper(),
        "Cohort": event.get("Cohort", ""),
        "SUE": event.get("SUE", np.nan),
        "Event_Public_Date": event_date,
        "Entry_Date": entry_date,
        "Entry_Open": entry_open,
        "Exit_Date": exit_date,
        "Exit_Open": exit_open,
        "Exit_Reason": exit_reason,
        "Holding_Sessions": holding_sessions,
        "Gross_Return": gross,
        "Base_Net_Return": gross - BASE_FRICTION,
        "Stress_Net_Return": gross - STRESS_FRICTION,
        "Severe_Net_Return": gross - SEVERE_FRICTION,
        "Nifty500_Entry_Open": nifty_entry_open,
        "Nifty500_Exit_Open": nifty_exit_open,
        "Benchmark_Return": benchmark,
        "Base_Net_Excess_Return": gross - BASE_FRICTION - benchmark,
        "Stress_Net_Excess_Return": gross - STRESS_FRICTION - benchmark,
        "Previous_Close": previous_close,
        "Entry_Gap": entry_open / previous_close - 1.0 if np.isfinite(previous_close) and previous_close > 0 else np.nan,
        "MAE": float((low / entry_open - 1.0).min()) if low.notna().any() else np.nan,
        "MFE": float((high / entry_open - 1.0).max()) if high.notna().any() else np.nan,
        "Max_Trade_Drawdown": float((low / entry_open - 1.0).min()) if low.notna().any() else np.nan,
    }, ""


def build_primary_trades(
    classified_events: pd.DataFrame,
    stock_prices: pd.DataFrame,
    index_prices: pd.DataFrame,
    all_original_events: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Build all primary cohort outputs through the shared trade function."""

    outputs: dict[str, list[dict[str, object]]] = {
        "POSITIVE_SURPRISE": [],
        "NEUTRAL_CONTROL": [],
        "NEGATIVE_CONTROL": [],
    }
    cancellations: list[dict[str, object]] = []
    calendar = canonical_sessions(index_prices)
    for _, event in classified_events.iterrows():
        cohort = str(event.get("Cohort", ""))
        if cohort not in outputs:
            continue
        symbol_prices = stock_prices.loc[
            stock_prices["Symbol"].astype(str).str.upper().eq(str(event.get("Symbol", "")).upper())
        ] if "Symbol" in stock_prices else stock_prices
        trade, reason = build_trade_for_event(
            event,
            symbol_prices,
            index_prices,
            all_original_events,
            canonical_sessions=calendar,
        )
        if trade is None:
            cancellations.append({"Event_ID": event.get("Event_ID", ""), "Symbol": event.get("Symbol", ""), "Cohort": cohort, "Reason": reason})
        else:
            outputs[cohort].append(trade)
    frames = {cohort: pd.DataFrame(rows) for cohort, rows in outputs.items()}
    return frames, pd.DataFrame(cancellations, columns=["Event_ID", "Symbol", "Cohort", "Reason"])


def write_trade_outputs(output_dir: Path, frames: dict[str, pd.DataFrame]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    names = {
        "POSITIVE_SURPRISE": "e1_positive_trades.csv",
        "NEUTRAL_CONTROL": "e1_neutral_control.csv",
        "NEGATIVE_CONTROL": "e1_negative_control.csv",
    }
    for cohort, name in names.items():
        frame = frames.get(cohort, pd.DataFrame()).reindex(columns=TRADE_OUTPUT_COLUMNS)
        frame.to_csv(output_dir / name, index=False, date_format="%Y-%m-%d")
