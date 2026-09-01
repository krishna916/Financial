"""Generate RR1 range candidates, signal cohorts, and executable references."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from build_rr1_features import (
    build_feature_frames,
    canonical_sessions,
    load_membership,
    load_nifty500_benchmark,
)
from constants import (
    DOWNLOAD_END_EXCLUSIVE,
    DOWNLOAD_START,
    ER60_MAX,
    LIQUIDITY_FLOOR,
    MEMBERSHIP_PATH,
    MIN_INITIAL_RR,
    SIGNAL_END,
    SIGNAL_START,
    STOP_ATR_BUFFER,
)

SIGNAL_COLUMNS = [
    "Signal_ID",
    "Symbol",
    "Signal_Date",
    "Yahoo_Ticker",
    "Range_Low",
    "Range_High",
    "Range_Mid",
    "ER60",
    "Prior20_Median_Traded_Value",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "ATR14",
    "Point_In_Time_Member",
    "Exact_Prehistory_61",
]
CANDIDATE_COLUMNS = [
    "Symbol",
    "Signal_Date",
    "Yahoo_Ticker",
    "Point_In_Time_Member",
    "Exact_Prehistory_61",
    "Range_Low",
    "Range_High",
    "Range_Mid",
    "ER60",
    "ER60_Denominator",
    "Prior20_Median_Traded_Value",
    "Liquidity_OK",
    "ER60_OK",
    "Lower_Signal",
    "Upper_Signal",
    "Range_Eligibility_Reason",
]
ENTRY_COLUMNS = [
    "Entry_ID",
    "Signal_ID",
    "Symbol",
    "Signal_Date",
    "Entry_Date",
    "Entry_Open",
    "Range_Low",
    "Range_High",
    "Target",
    "ATR14_Signal",
    "Structural_Stop",
    "Initial_Risk",
    "Reward",
    "Initial_RR",
    "Scheduled_Exit_Date",
]
ENTRY_CANCELLATION_COLUMNS = [
    "Signal_ID",
    "Symbol",
    "Signal_Date",
    "Cancellation_Reason",
]
REFERENCE_COLUMNS = [
    "Reference_ID",
    "Signal_ID",
    "Symbol",
    "Signal_Date",
    "Entry_Date",
    "Entry_Open",
    "Scheduled_Exit_Date",
]


def _finite(value: object) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _truthy(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def qualify_range_row(row: pd.Series) -> tuple[bool, str]:
    """Apply only RR1's frozen PIT, history, range, ER and liquidity rules."""

    date = pd.Timestamp(row.get("Date"))
    if not (SIGNAL_START <= date <= SIGNAL_END):
        return False, "OUTSIDE_SIGNAL_WINDOW"
    if not _truthy(row.get("Point_In_Time_Member")):
        return False, "NOT_POINT_IN_TIME_MEMBER"
    if not _truthy(row.get("Exact_Prehistory_61")):
        return False, "MISSING_EXACT_PREHISTORY"
    if not (
        _finite(row.get("Range_Low"))
        and _finite(row.get("Range_High"))
        and float(row["Range_High"]) > float(row["Range_Low"])
    ):
        return False, "INVALID_RANGE"
    if not (
        _finite(row.get("ER60_Denominator"))
        and float(row["ER60_Denominator"]) > 0.0
        and _finite(row.get("ER60"))
    ):
        return False, "INVALID_ER60"
    if float(row["ER60"]) > ER60_MAX:
        return False, "ER60_ABOVE_MAX"
    if not _finite(row.get("Prior20_Median_Traded_Value")):
        return False, "INVALID_LIQUIDITY"
    if float(row["Prior20_Median_Traded_Value"]) < LIQUIDITY_FLOOR:
        return False, "LOW_LIQUIDITY"
    return True, "QUALIFIED_RANGE"


def is_lower_signal(row: pd.Series) -> bool:
    return bool(
        _finite(row.get("Low"))
        and _finite(row.get("Range_Low"))
        and _finite(row.get("Close"))
        and float(row["Low"]) < float(row["Range_Low"])
        and float(row["Close"]) > float(row["Range_Low"])
    )


def is_upper_signal(row: pd.Series) -> bool:
    return bool(
        _finite(row.get("High"))
        and _finite(row.get("Range_High"))
        and _finite(row.get("Close"))
        and float(row["High"]) > float(row["Range_High"])
        and float(row["Close"]) < float(row["Range_High"])
    )


def _signal_row(row: pd.Series, symbol: str, direction: str) -> dict[str, object]:
    signal_date = pd.Timestamp(row["Date"])
    result = {column: row.get(column, np.nan) for column in SIGNAL_COLUMNS}
    result.update(
        {
            "Signal_ID": f"{direction}|{symbol}|{signal_date.date().isoformat()}",
            "Symbol": symbol,
            "Signal_Date": signal_date,
            "Yahoo_Ticker": row.get("Yahoo_Ticker", ""),
            "Point_In_Time_Member": _truthy(row.get("Point_In_Time_Member")),
            "Exact_Prehistory_61": _truthy(row.get("Exact_Prehistory_61")),
        }
    )
    return result


def build_signal_tables(
    feature_frames: dict[str, pd.DataFrame], membership: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build the candidate funnel and the lower/upper qualified signal tables."""

    del membership  # PIT status is attached by the feature builder and is audited later.
    candidates: list[dict[str, object]] = []
    lower: list[dict[str, object]] = []
    upper: list[dict[str, object]] = []
    for symbol in sorted(feature_frames):
        frame = feature_frames[symbol].copy()
        frame["Date"] = pd.to_datetime(frame["Date"]).dt.normalize()
        frame = frame.sort_values("Date")
        for _, row in frame.iterrows():
            date = pd.Timestamp(row["Date"])
            if not (SIGNAL_START <= date <= SIGNAL_END):
                continue
            if not _truthy(row.get("Point_In_Time_Member")):
                continue
            base_candidate = (
                _truthy(row.get("Exact_Prehistory_61"))
                and _finite(row.get("Range_Low"))
                and _finite(row.get("Range_High"))
                and float(row["Range_High"]) > float(row["Range_Low"])
                and _finite(row.get("ER60_Denominator"))
                and float(row["ER60_Denominator"]) > 0.0
                and _finite(row.get("ER60"))
                and _finite(row.get("Prior20_Median_Traded_Value"))
            )
            if not base_candidate:
                continue
            ok, reason = qualify_range_row(row)
            lower_signal = bool(ok and is_lower_signal(row))
            upper_signal = bool(ok and is_upper_signal(row))
            candidates.append(
                {
                    "Symbol": symbol,
                    "Signal_Date": date,
                    "Yahoo_Ticker": row.get("Yahoo_Ticker", ""),
                    "Point_In_Time_Member": True,
                    "Exact_Prehistory_61": True,
                    "Range_Low": row["Range_Low"],
                    "Range_High": row["Range_High"],
                    "Range_Mid": row["Range_Mid"],
                    "ER60": row["ER60"],
                    "ER60_Denominator": row["ER60_Denominator"],
                    "Prior20_Median_Traded_Value": row["Prior20_Median_Traded_Value"],
                    "Liquidity_OK": bool(
                        float(row["Prior20_Median_Traded_Value"]) >= LIQUIDITY_FLOOR
                    ),
                    "ER60_OK": bool(float(row["ER60"]) <= ER60_MAX),
                    "Lower_Signal": lower_signal,
                    "Upper_Signal": upper_signal,
                    "Range_Eligibility_Reason": reason,
                }
            )
            if lower_signal:
                lower.append(_signal_row(row, symbol, "LOWER"))
            if upper_signal:
                upper.append(_signal_row(row, symbol, "UPPER"))
    return (
        pd.DataFrame(candidates, columns=CANDIDATE_COLUMNS),
        pd.DataFrame(lower, columns=SIGNAL_COLUMNS),
        pd.DataFrame(upper, columns=SIGNAL_COLUMNS),
    )


def session_after(
    date: pd.Timestamp, sessions: pd.DatetimeIndex, steps: int
) -> pd.Timestamp | None:
    if steps < 0:
        raise ValueError("steps must be non-negative")
    index = pd.DatetimeIndex(pd.to_datetime(sessions)).normalize().drop_duplicates().sort_values()
    day = pd.Timestamp(date).normalize()
    if day not in index:
        return None
    position = index.get_loc(day)
    if isinstance(position, slice):
        position = position.start
    target = int(position) + steps
    return pd.Timestamp(index[target]) if target < len(index) else None


def _price_for_date(
    feature_frames: dict[str, pd.DataFrame], symbol: str, date: pd.Timestamp
) -> pd.Series | None:
    frame = feature_frames.get(symbol)
    if frame is None or frame.empty:
        return None
    dates = pd.to_datetime(frame["Date"]).dt.normalize()
    matches = frame.loc[dates.eq(pd.Timestamp(date).normalize())]
    return matches.iloc[0] if len(matches) else None


def _has_bar(row: pd.Series | None) -> bool:
    return row is not None and row[["Open", "High", "Low", "Close"]].notna().all()


def _lower_cancellation(signal: pd.Series, reason: str) -> dict[str, object]:
    return {
        "Signal_ID": signal["Signal_ID"],
        "Symbol": signal["Symbol"],
        "Signal_Date": pd.Timestamp(signal["Signal_Date"]),
        "Cancellation_Reason": reason,
    }


def build_lower_entries(
    signals: pd.DataFrame,
    feature_frames: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    entries: list[dict[str, object]] = []
    cancellations: list[dict[str, object]] = []
    lockout_until: dict[str, pd.Timestamp] = {}
    ordered = signals.sort_values(["Signal_Date", "Symbol", "Signal_ID"]).reset_index(drop=True)
    for _, signal in ordered.iterrows():
        symbol = str(signal["Symbol"])
        signal_date = pd.Timestamp(signal["Signal_Date"]).normalize()
        if signal_date < lockout_until.get(symbol, pd.Timestamp.min):
            cancellations.append(_lower_cancellation(signal, "SAME_SYMBOL_LOCKOUT"))
            continue
        target = float(signal.get("Range_Mid", np.nan))
        signal_close = float(signal.get("Close", np.nan))
        if _finite(signal_close) and _finite(target) and signal_close >= target:
            cancellations.append(
                _lower_cancellation(signal, "SIGNAL_ALREADY_AT_OR_ABOVE_TARGET")
            )
            continue
        entry_date = session_after(signal_date, sessions, 1)
        if entry_date is None:
            cancellations.append(_lower_cancellation(signal, "MISSING_NEXT_SESSION"))
            continue
        next_bar = _price_for_date(feature_frames, symbol, entry_date)
        if not _has_bar(next_bar):
            cancellations.append(_lower_cancellation(signal, "MISSING_NEXT_SESSION_BAR"))
            continue
        atr = float(signal.get("ATR14", np.nan))
        low = float(signal.get("Low", np.nan))
        structural_stop = low - STOP_ATR_BUFFER * atr
        entry_open = float(next_bar["Open"])
        if _finite(structural_stop) and entry_open <= structural_stop:
            cancellations.append(
                _lower_cancellation(signal, "OPEN_AT_OR_BELOW_STRUCTURAL_STOP")
            )
            continue
        if _finite(target) and entry_open >= target:
            cancellations.append(_lower_cancellation(signal, "OPEN_AT_OR_ABOVE_TARGET"))
            continue
        initial_risk = entry_open - structural_stop
        reward = target - entry_open
        initial_rr = reward / initial_risk if initial_risk > 0.0 else np.nan
        if not (
            _finite(initial_risk)
            and _finite(reward)
            and initial_risk > 0.0
            and reward > 0.0
            and _finite(initial_rr)
            and initial_rr >= MIN_INITIAL_RR
        ):
            cancellations.append(_lower_cancellation(signal, "INSUFFICIENT_REWARD_RISK"))
            continue
        scheduled_exit = session_after(signal_date, sessions, 16)
        lockout_until[symbol] = scheduled_exit or pd.Timestamp.max
        entries.append(
            {
                "Entry_ID": f"ENTRY|{signal['Signal_ID']}",
                "Signal_ID": signal["Signal_ID"],
                "Symbol": symbol,
                "Signal_Date": signal_date,
                "Entry_Date": entry_date,
                "Entry_Open": entry_open,
                "Range_Low": signal["Range_Low"],
                "Range_High": signal["Range_High"],
                "Target": target,
                "ATR14_Signal": atr,
                "Structural_Stop": structural_stop,
                "Initial_Risk": initial_risk,
                "Reward": reward,
                "Initial_RR": initial_rr,
                "Scheduled_Exit_Date": scheduled_exit,
            }
        )
    return (
        pd.DataFrame(entries, columns=ENTRY_COLUMNS),
        pd.DataFrame(cancellations, columns=ENTRY_CANCELLATION_COLUMNS),
    )


def build_upper_references(
    signals: pd.DataFrame,
    feature_frames: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    references: list[dict[str, object]] = []
    cancellations: list[dict[str, object]] = []
    lockout_until: dict[str, pd.Timestamp] = {}
    ordered = signals.sort_values(["Signal_Date", "Symbol", "Signal_ID"]).reset_index(drop=True)
    for _, signal in ordered.iterrows():
        symbol = str(signal["Symbol"])
        signal_date = pd.Timestamp(signal["Signal_Date"]).normalize()
        if signal_date < lockout_until.get(symbol, pd.Timestamp.min):
            cancellations.append(_lower_cancellation(signal, "SAME_SYMBOL_LOCKOUT"))
            continue
        entry_date = session_after(signal_date, sessions, 1)
        if entry_date is None:
            cancellations.append(_lower_cancellation(signal, "MISSING_NEXT_SESSION"))
            continue
        next_bar = _price_for_date(feature_frames, symbol, entry_date)
        if not _has_bar(next_bar):
            cancellations.append(_lower_cancellation(signal, "MISSING_NEXT_SESSION_BAR"))
            continue
        scheduled_exit = session_after(signal_date, sessions, 16)
        lockout_until[symbol] = scheduled_exit or pd.Timestamp.max
        references.append(
            {
                "Reference_ID": f"REFERENCE|{signal['Signal_ID']}",
                "Signal_ID": signal["Signal_ID"],
                "Symbol": symbol,
                "Signal_Date": signal_date,
                "Entry_Date": entry_date,
                "Entry_Open": float(next_bar["Open"]),
                "Scheduled_Exit_Date": scheduled_exit,
            }
        )
    return (
        pd.DataFrame(references, columns=REFERENCE_COLUMNS),
        pd.DataFrame(cancellations, columns=ENTRY_CANCELLATION_COLUMNS),
    )


def main() -> None:
    root = Path(__file__).resolve().parents[4]
    module_dir = Path(__file__).resolve().parent
    output_dir = module_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    membership = load_membership(
        root / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv"
    )
    benchmark = load_nifty500_benchmark(DOWNLOAD_START, DOWNLOAD_END_EXCLUSIVE)
    feature_frames, validation = build_feature_frames(membership, benchmark)
    sessions = canonical_sessions(benchmark)
    candidates, lower, upper = build_signal_tables(feature_frames, membership)
    entries, lower_cancellations = build_lower_entries(lower, feature_frames, sessions)
    references, upper_cancellations = build_upper_references(upper, feature_frames, sessions)
    validation.to_csv(output_dir / "rr1_data_validation.csv", index=False)
    candidates.to_csv(output_dir / "rr1_range_candidates.csv", index=False)
    lower.to_csv(output_dir / "rr1_lower_signals.csv", index=False)
    upper.to_csv(output_dir / "rr1_upper_signals.csv", index=False)
    entries.to_csv(output_dir / "rr1_lower_entries.csv", index=False)
    lower_cancellations.to_csv(output_dir / "rr1_lower_entry_cancellations.csv", index=False)
    references.to_csv(output_dir / "rr1_upper_references.csv", index=False)
    upper_cancellations.to_csv(output_dir / "rr1_upper_cancellations.csv", index=False)
    print(f"Generated {len(lower)} lower and {len(upper)} upper signals")


if __name__ == "__main__":
    main()
