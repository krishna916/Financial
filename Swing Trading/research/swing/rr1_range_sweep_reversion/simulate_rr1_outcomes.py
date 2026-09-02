"""Simulate RR1's paired fixed-horizon and practical outcomes."""

from __future__ import annotations

import numpy as np
import pandas as pd

from constants import BASE_FRICTION, SEVERE_FRICTION, STRESS_FRICTION
from generate_rr1_signals import session_after

LENS_A_COLUMNS = [
    "Entry_ID",
    "Symbol",
    "Signal_Date",
    "Entry_Date",
    "Exit_Date",
    "Entry_Open",
    "Exit_Price",
    "Gross_Return",
    "Base_Net_Return",
    "Stress_Net_Return",
    "Severe_Net_Return",
    "Benchmark_Return",
    "Base_Excess_Return",
]
PRACTICAL_COLUMNS = [
    "Entry_ID",
    "Symbol",
    "Signal_Date",
    "Entry_Date",
    "Exit_Date",
    "Entry_Open",
    "Exit_Price",
    "Exit_Reason",
    "Initial_Risk",
    "Target",
    "Structural_Stop",
    "Gross_Return",
    "Base_Net_Return",
    "Stress_Net_Return",
    "Severe_Net_Return",
    "Gross_R",
    "Base_Net_R",
    "Stress_Net_R",
    "Severe_Net_R",
    "Benchmark_Return",
    "Base_Practical_Excess_Return",
    "Stress_Practical_Excess_Return",
    "Severe_Practical_Excess_Return",
    "Same_Bar_Stop_Target_Ambiguity",
]
UPPER_COLUMNS = [
    "Reference_ID",
    "Signal_ID",
    "Symbol",
    "Signal_Date",
    "Entry_Date",
    "Exit_Date",
    "Entry_Open",
    "Exit_Price",
    "Mirror_Gross_Return_15",
]
DIAGNOSTIC_COLUMNS = [
    "Entry_ID",
    "Reference_ID",
    "Symbol",
    "Signal_Date",
    "Primary_Complete",
    "Completion_Reason",
    "Forward_3_Return",
    "Forward_5_Return",
    "Forward_10_Return",
    "Forward_15_Return",
    "Forward_20_Return",
    "MFE",
    "MAE",
    "Exit_Reason",
    "Exit_Date",
    "Same_Bar_Stop_Target_Ambiguity",
]


def _price_index(prices: pd.DataFrame) -> pd.DataFrame:
    if "Date" not in prices.columns:
        raise ValueError("prices must contain Date")
    frame = prices.copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    if getattr(frame["Date"].dt, "tz", None) is not None:
        frame["Date"] = frame["Date"].dt.tz_localize(None)
    frame["Date"] = frame["Date"].dt.normalize()
    if frame["Date"].isna().any() or frame["Date"].duplicated().any():
        raise ValueError("prices contain invalid or duplicate dates")
    for column in ["Open", "High", "Low", "Close"]:
        if column not in frame.columns:
            raise ValueError(f"prices missing {column}")
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.set_index("Date").sort_index()


def _session_index(sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(pd.to_datetime(sessions)).normalize()
    return index.drop_duplicates().sort_values()


def _bar(frame: pd.DataFrame, date: pd.Timestamp) -> pd.Series | None:
    day = pd.Timestamp(date).normalize()
    if day not in frame.index:
        return None
    value = frame.loc[day]
    if isinstance(value, pd.DataFrame):
        value = value.iloc[0]
    return value


def _complete_bar(bar: pd.Series | None) -> bool:
    return bar is not None and bar[["Open", "High", "Low", "Close"]].notna().all()


def _benchmark_return(
    benchmark: pd.DataFrame, entry_date: pd.Timestamp, exit_date: pd.Timestamp
) -> float | None:
    frame = _price_index(benchmark)
    entry = _bar(frame, entry_date)
    exit_ = _bar(frame, exit_date)
    if not (_complete_bar(entry) and _complete_bar(exit_)):
        return None
    entry_open = float(entry["Open"])
    exit_open = float(exit_["Open"])
    if not np.isfinite(entry_open) or not np.isfinite(exit_open) or entry_open == 0.0:
        return None
    return exit_open / entry_open - 1.0


def _return_fields(
    entry_open: float, exit_price: float, benchmark_return: float
) -> dict[str, float]:
    gross = exit_price / entry_open - 1.0
    return {
        "Gross_Return": gross,
        "Base_Net_Return": gross - BASE_FRICTION,
        "Stress_Net_Return": gross - STRESS_FRICTION,
        "Severe_Net_Return": gross - SEVERE_FRICTION,
        "Benchmark_Return": benchmark_return,
        "Base_Excess_Return": gross - BASE_FRICTION - benchmark_return,
    }


def simulate_lens_a(
    entry: pd.Series,
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    sessions: pd.DatetimeIndex,
) -> dict[str, object] | None:
    """Evaluate an accepted entry from T+1 Open to the scheduled T+16 Open."""

    stock = _price_index(prices)
    index = _session_index(sessions)
    entry_date = pd.Timestamp(entry["Entry_Date"]).normalize()
    scheduled_value = entry["Scheduled_Exit_Date"]
    if pd.isna(scheduled_value):
        return None
    exit_date = pd.Timestamp(scheduled_value).normalize()
    entry_bar = _bar(stock, entry_date)
    exit_bar = _bar(stock, exit_date)
    if not (_complete_bar(entry_bar) and _complete_bar(exit_bar)):
        return None
    if entry_date not in index or exit_date not in index:
        return None
    entry_open = float(entry["Entry_Open"])
    exit_price = float(exit_bar["Open"])
    if not np.isfinite(entry_open) or not np.isfinite(exit_price) or entry_open == 0.0:
        return None
    benchmark_return = _benchmark_return(benchmark, entry_date, exit_date)
    if benchmark_return is None:
        return None
    result = {
        "Entry_ID": entry["Entry_ID"],
        "Symbol": entry["Symbol"],
        "Signal_Date": pd.Timestamp(entry["Signal_Date"]),
        "Entry_Date": entry_date,
        "Exit_Date": exit_date,
        "Entry_Open": entry_open,
        "Exit_Price": exit_price,
    }
    result.update(_return_fields(entry_open, exit_price, benchmark_return))
    return result


def _practical_result(
    entry: pd.Series,
    exit_date: pd.Timestamp,
    exit_price: float,
    exit_reason: str,
    benchmark_return: float,
    ambiguity: bool,
) -> dict[str, object]:
    entry_open = float(entry["Entry_Open"])
    initial_risk = float(entry["Initial_Risk"])
    target = float(entry["Target"])
    stop = float(entry["Structural_Stop"])
    returns = _return_fields(entry_open, exit_price, benchmark_return)
    gross_r = (exit_price - entry_open) / initial_risk
    result: dict[str, object] = {
        "Entry_ID": entry["Entry_ID"],
        "Symbol": entry["Symbol"],
        "Signal_Date": pd.Timestamp(entry["Signal_Date"]),
        "Entry_Date": pd.Timestamp(entry["Entry_Date"]).normalize(),
        "Exit_Date": pd.Timestamp(exit_date).normalize(),
        "Entry_Open": entry_open,
        "Exit_Price": exit_price,
        "Exit_Reason": exit_reason,
        "Initial_Risk": initial_risk,
        "Target": target,
        "Structural_Stop": stop,
        "Gross_R": gross_r,
        "Stress_Net_R": gross_r - STRESS_FRICTION * entry_open / initial_risk,
        "Severe_Net_R": gross_r - SEVERE_FRICTION * entry_open / initial_risk,
        "Same_Bar_Stop_Target_Ambiguity": bool(ambiguity),
    }
    result.update(returns)
    result["Base_Net_R"] = gross_r - BASE_FRICTION * entry_open / initial_risk
    result["Base_Practical_Excess_Return"] = (
        float(result["Base_Net_Return"]) - benchmark_return
    )
    result["Stress_Practical_Excess_Return"] = (
        float(result["Stress_Net_Return"]) - benchmark_return
    )
    result["Severe_Practical_Excess_Return"] = (
        float(result["Severe_Net_Return"]) - benchmark_return
    )
    return result


def simulate_practical(
    entry: pd.Series,
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    sessions: pd.DatetimeIndex,
) -> dict[str, object] | None:
    """Evaluate stop/target/time-exit execution with frozen precedence."""

    stock = _price_index(prices)
    index = _session_index(sessions)
    entry_date = pd.Timestamp(entry["Entry_Date"]).normalize()
    scheduled_value = entry["Scheduled_Exit_Date"]
    if pd.isna(scheduled_value):
        return None
    scheduled_exit = pd.Timestamp(scheduled_value).normalize()
    if entry_date not in index or scheduled_exit not in index:
        return None
    entry_position = int(index.get_loc(entry_date))
    exit_position = int(index.get_loc(scheduled_exit))
    if exit_position <= entry_position:
        return None
    stop = float(entry["Structural_Stop"])
    target = float(entry["Target"])
    for position in range(entry_position, exit_position):
        date = pd.Timestamp(index[position])
        bar = _bar(stock, date)
        if not _complete_bar(bar):
            return None
        open_price = float(bar["Open"])
        high = float(bar["High"])
        low = float(bar["Low"])
        if open_price <= stop:
            reason = "GAP_BELOW_STRUCTURAL_STOP" if position > entry_position else "STRUCTURAL_STOP"
            benchmark_return = _benchmark_return(benchmark, entry_date, date)
            return (
                _practical_result(entry, date, open_price, reason, benchmark_return, False)
                if benchmark_return is not None
                else None
            )
        if open_price >= target:
            reason = "GAP_ABOVE_TARGET" if position > entry_position else "TARGET"
            benchmark_return = _benchmark_return(benchmark, entry_date, date)
            return (
                _practical_result(entry, date, open_price, reason, benchmark_return, False)
                if benchmark_return is not None
                else None
            )
        stop_touched = low <= stop
        target_touched = high >= target
        if stop_touched:
            benchmark_return = _benchmark_return(benchmark, entry_date, date)
            return (
                _practical_result(
                    entry, date, stop, "STRUCTURAL_STOP", benchmark_return,
                    stop_touched and target_touched,
                )
                if benchmark_return is not None
                else None
            )
        if target_touched:
            benchmark_return = _benchmark_return(benchmark, entry_date, date)
            return (
                _practical_result(
                    entry, date, target, "MIDPOINT_TARGET", benchmark_return, False
                )
                if benchmark_return is not None
                else None
            )
    exit_bar = _bar(stock, scheduled_exit)
    if not _complete_bar(exit_bar):
        return None
    exit_price = float(exit_bar["Open"])
    benchmark_return = _benchmark_return(benchmark, entry_date, scheduled_exit)
    if benchmark_return is None:
        return None
    return _practical_result(
        entry, scheduled_exit, exit_price, "TIME_EXIT", benchmark_return, False
    )


def simulate_upper(
    reference: pd.Series,
    prices: pd.DataFrame,
    sessions: pd.DatetimeIndex,
) -> dict[str, object] | None:
    stock = _price_index(prices)
    index = _session_index(sessions)
    entry_date = pd.Timestamp(reference["Entry_Date"]).normalize()
    scheduled_value = reference["Scheduled_Exit_Date"]
    if pd.isna(scheduled_value):
        return None
    exit_date = pd.Timestamp(scheduled_value).normalize()
    entry_bar = _bar(stock, entry_date)
    exit_bar = _bar(stock, exit_date)
    if not (_complete_bar(entry_bar) and _complete_bar(exit_bar)):
        return None
    if entry_date not in index or exit_date not in index:
        return None
    entry_open = float(reference["Entry_Open"])
    exit_price = float(exit_bar["Open"])
    if not np.isfinite(entry_open) or not np.isfinite(exit_price) or entry_open == 0.0:
        return None
    return {
        "Reference_ID": reference["Reference_ID"],
        "Signal_ID": reference["Signal_ID"],
        "Symbol": reference["Symbol"],
        "Signal_Date": pd.Timestamp(reference["Signal_Date"]),
        "Entry_Date": entry_date,
        "Exit_Date": exit_date,
        "Entry_Open": entry_open,
        "Exit_Price": exit_price,
        "Mirror_Gross_Return_15": exit_price / entry_open - 1.0,
    }


def _forward_diagnostic(
    entry: pd.Series,
    practical: dict[str, object],
    prices: pd.DataFrame,
    sessions: pd.DatetimeIndex,
) -> dict[str, object]:
    stock = _price_index(prices)
    index = _session_index(sessions)
    entry_date = pd.Timestamp(entry["Entry_Date"]).normalize()
    entry_open = float(entry["Entry_Open"])
    result: dict[str, object] = {
        "Entry_ID": entry["Entry_ID"],
        "Reference_ID": "",
        "Symbol": entry["Symbol"],
        "Signal_Date": pd.Timestamp(entry["Signal_Date"]),
        "Primary_Complete": True,
        "Completion_Reason": "COMPLETE",
        "Exit_Reason": practical["Exit_Reason"],
        "Exit_Date": practical["Exit_Date"],
        "Same_Bar_Stop_Target_Ambiguity": practical[
            "Same_Bar_Stop_Target_Ambiguity"
        ],
    }
    for horizon in [3, 5, 10, 15, 20]:
        date = session_after(entry_date, index, horizon)
        bar = _bar(stock, date) if date is not None else None
        result[f"Forward_{horizon}_Return"] = (
            float(bar["Open"]) / entry_open - 1.0 if _complete_bar(bar) else np.nan
        )
    end_date = pd.Timestamp(entry["Scheduled_Exit_Date"]).normalize()
    holding_dates = index[(index >= entry_date) & (index < end_date)]
    bars = stock.reindex(holding_dates)
    result["MFE"] = bars["High"].max() / entry_open - 1.0
    result["MAE"] = bars["Low"].min() / entry_open - 1.0
    return result


def build_outcomes(
    entries: pd.DataFrame,
    upper_refs: pd.DataFrame,
    feature_frames: dict[str, pd.DataFrame],
    benchmark: pd.DataFrame,
    sessions: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lens_a_rows: list[dict[str, object]] = []
    practical_rows: list[dict[str, object]] = []
    upper_rows: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    for _, entry in entries.iterrows():
        prices = feature_frames.get(str(entry["Symbol"]))
        if prices is None:
            lens_a = None
            practical = None
        else:
            lens_a = simulate_lens_a(entry, prices, benchmark, sessions)
            practical = simulate_practical(entry, prices, benchmark, sessions)
        if lens_a is not None and practical is not None:
            lens_a_rows.append(lens_a)
            practical_rows.append(practical)
            diagnostics.append(_forward_diagnostic(entry, practical, prices, sessions))
        else:
            diagnostics.append(
                {
                    "Entry_ID": entry["Entry_ID"],
                    "Reference_ID": "",
                    "Symbol": entry["Symbol"],
                    "Signal_Date": pd.Timestamp(entry["Signal_Date"]),
                    "Primary_Complete": False,
                    "Completion_Reason": "MISSING_PAIRED_EVIDENCE",
                    "Forward_3_Return": np.nan,
                    "Forward_5_Return": np.nan,
                    "Forward_10_Return": np.nan,
                    "Forward_15_Return": np.nan,
                    "Forward_20_Return": np.nan,
                    "MFE": np.nan,
                    "MAE": np.nan,
                    "Exit_Reason": practical.get("Exit_Reason", "") if practical else "",
                    "Exit_Date": practical.get("Exit_Date", pd.NaT) if practical else pd.NaT,
                    "Same_Bar_Stop_Target_Ambiguity": (
                        practical.get("Same_Bar_Stop_Target_Ambiguity", False)
                        if practical
                        else False
                    ),
                }
            )
    for _, reference in upper_refs.iterrows():
        prices = feature_frames.get(str(reference["Symbol"]))
        outcome = simulate_upper(reference, prices, sessions) if prices is not None else None
        if outcome is not None:
            upper_rows.append(outcome)
        else:
            diagnostics.append(
                {
                    "Entry_ID": "",
                    "Reference_ID": reference["Reference_ID"],
                    "Symbol": reference["Symbol"],
                    "Signal_Date": pd.Timestamp(reference["Signal_Date"]),
                    "Primary_Complete": False,
                    "Completion_Reason": "MISSING_UPPER_EVIDENCE",
                    "Forward_3_Return": np.nan,
                    "Forward_5_Return": np.nan,
                    "Forward_10_Return": np.nan,
                    "Forward_15_Return": np.nan,
                    "Forward_20_Return": np.nan,
                    "MFE": np.nan,
                    "MAE": np.nan,
                    "Exit_Reason": "",
                    "Exit_Date": pd.NaT,
                    "Same_Bar_Stop_Target_Ambiguity": False,
                }
            )
    return (
        pd.DataFrame(lens_a_rows, columns=LENS_A_COLUMNS),
        pd.DataFrame(practical_rows, columns=PRACTICAL_COLUMNS),
        pd.DataFrame(upper_rows, columns=UPPER_COLUMNS),
        pd.DataFrame(diagnostics, columns=DIAGNOSTIC_COLUMNS),
    )
