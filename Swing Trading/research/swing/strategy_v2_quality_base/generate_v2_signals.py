"""Generate Strategy V2 base-state candidates and one-shot next-session entries."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from build_v2_features import LIQUIDITY_FLOOR, MIN_RS_COVERAGE


MAX_BASE_AGE = 30
MIN_BASE_AGE = 10
MAX_BASE_DEPTH_ATR = 4.0
MAX_CONTRACTION_RATIO = 0.80
MAX_EXTENSION_ATR = 1.0
MAX_STOP_DISTANCE_ATR = 2.5
STOP_BUFFER_ATR = 0.25

STATE_COLUMNS = [
    "Symbol",
    "Date",
    "Base_ID",
    "Seed_Date",
    "Base_Age",
    "Event",
    "Original_Pivot",
    "Active_Pivot",
    "New_Pivot",
    "Base_Low",
    "Base_Depth_ATR",
    "High",
    "Low",
    "Close",
]

SIGNAL_COLUMNS = [
    "Entry_ID",
    "Symbol",
    "Seed_Date",
    "Signal_Date",
    "Base_Age",
    "Original_Pivot",
    "Active_Pivot",
    "ATR14_Seed",
    "ATR14_Signal",
    "Base_Low",
    "Base_Depth_ATR",
    "Initial_TR_Mean",
    "Final_TR_Mean",
    "Contraction_Ratio",
    "Final_5_Prebreakout_Low",
    "Close",
    "SMA50",
    "SMA200",
    "Median_Traded_Value_20",
    "RS21",
    "RS63",
    "RS126",
    "Composite_RS",
    "RS_Coverage",
    "Breakout_Volume_Ratio",
    "Signal_Extension_ATR",
    "Membership_OK",
    "RS_Coverage_OK",
    "Liquidity_OK",
    "Trend_OK",
    "RS_OK",
    "Contraction_OK",
    "Extension_OK",
    "Signal_Qualified",
    "Signal_Rejection_Reason",
]


def _finite(value: object) -> bool:
    try:
        return bool(pd.notna(value) and np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _frame_for_scan(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"Date", "High", "Low", "Close", "ATR14", "True_Range"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"signal frame missing columns: {sorted(missing)}")
    result = frame.copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
    if getattr(result["Date"].dt, "tz", None) is not None:
        result["Date"] = result["Date"].dt.tz_localize(None)
    if result["Date"].isna().any():
        raise ValueError("signal frame contains invalid dates")
    if result["Date"].duplicated().any():
        raise ValueError("signal frame contains duplicate dates")
    return result.sort_values("Date").reset_index(drop=True)


def _is_seed(frame: pd.DataFrame, index: int) -> bool:
    if index < 62 or not _finite(frame.loc[index, "High"]):
        return False
    window = pd.to_numeric(frame.loc[index - 62 : index, "High"], errors="coerce")
    if window.isna().any():
        return False
    return bool(frame.loc[index, "High"] == window.max())


def _depth(active: dict[str, object]) -> float:
    pivot = float(active["Active_Pivot"])
    base_low = float(active["Base_Low"])
    atr_seed = float(active["ATR14_Seed"])
    if not np.isfinite(atr_seed) or atr_seed <= 0:
        return np.nan
    return (pivot - base_low) / atr_seed


def _record_event(
    events: list[dict[str, object]],
    symbol: str,
    row: pd.Series,
    active: dict[str, object],
    event: str,
    new_pivot: object = np.nan,
) -> None:
    events.append(
        {
            "Symbol": symbol,
            "Date": row["Date"],
            "Base_ID": active["Base_ID"],
            "Seed_Date": active["Seed_Date"],
            "Base_Age": active["Age"],
            "Event": event,
            "Original_Pivot": active["Original_Pivot"],
            "Active_Pivot": active["Active_Pivot"],
            "New_Pivot": new_pivot,
            "Base_Low": active["Base_Low"],
            "Base_Depth_ATR": _depth(active),
            "High": row.get("High", np.nan),
            "Low": row.get("Low", np.nan),
            "Close": row.get("Close", np.nan),
        }
    )


def _volume_ratio(frame: pd.DataFrame, index: int, row: pd.Series) -> float:
    if _finite(row.get("Breakout_Volume_Ratio", np.nan)):
        return float(row["Breakout_Volume_Ratio"])
    volume = pd.to_numeric(frame.loc[:index, "Volume"], errors="coerce") if "Volume" in frame else pd.Series(dtype=float)
    median = volume.tail(20).median()
    if not _finite(row.get("Volume", np.nan)) or not _finite(median) or median == 0:
        return np.nan
    return float(row["Volume"] / median)


def _candidate_from_breakout(
    symbol: str,
    frame: pd.DataFrame,
    index: int,
    active: dict[str, object],
) -> dict[str, object]:
    row = frame.loc[index]
    base_indices = list(active["Base_Indices"])
    prebreakout_indices = base_indices[:-1]
    initial_tr = pd.to_numeric(frame.loc[base_indices[:5], "True_Range"], errors="coerce")
    final_indices = prebreakout_indices[-5:]
    final_tr = pd.to_numeric(frame.loc[final_indices, "True_Range"], errors="coerce")
    initial_mean = float(initial_tr.mean()) if len(initial_tr) == 5 and initial_tr.notna().all() else np.nan
    final_mean = float(final_tr.mean()) if len(final_tr) == 5 and final_tr.notna().all() else np.nan
    contraction = final_mean / initial_mean if _finite(initial_mean) and initial_mean > 0 else np.nan
    atr_signal = row.get("ATR14", np.nan)
    active_pivot = float(active["Active_Pivot"])
    close = row.get("Close", np.nan)
    extension = (float(close) - active_pivot) / float(atr_signal) if _finite(close) and _finite(atr_signal) and float(atr_signal) > 0 else np.nan
    base_depth = _depth(active)
    final_low = pd.to_numeric(frame.loc[final_indices, "Low"], errors="coerce")
    final_five_low = float(final_low.min()) if len(final_low) == 5 and final_low.notna().all() else np.nan
    membership_ok = bool(row.get("Point_In_Time_Member", False))
    coverage = row.get("RS_Coverage", np.nan)
    rs_safe = bool(row.get("RS_Research_Safe", False))
    coverage_ok = rs_safe and _finite(coverage) and float(coverage) >= MIN_RS_COVERAGE
    liquidity = row.get("Median_Traded_Value_20", np.nan)
    liquidity_ok = _finite(liquidity) and float(liquidity) >= LIQUIDITY_FLOOR
    sma50 = row.get("SMA50", np.nan)
    sma200 = row.get("SMA200", np.nan)
    trend_ok = _finite(close) and _finite(sma50) and _finite(sma200) and float(close) > float(sma50) and float(sma50) > float(sma200)
    composite = row.get("Composite_RS", np.nan)
    rs_ok = _finite(composite) and float(composite) >= 70.0
    contraction_ok = _finite(contraction) and contraction <= MAX_CONTRACTION_RATIO
    extension_ok = _finite(extension) and extension <= MAX_EXTENSION_ATR
    gates = {
        "Membership_OK": membership_ok,
        "RS_Coverage_OK": coverage_ok,
        "Liquidity_OK": liquidity_ok,
        "Trend_OK": trend_ok,
        "RS_OK": rs_ok,
        "Contraction_OK": contraction_ok,
        "Extension_OK": extension_ok,
    }
    reason_codes = [
        ("NOT_POINT_IN_TIME_MEMBER", not membership_ok),
        ("RS_COVERAGE_UNSAFE", not coverage_ok),
        ("LIQUIDITY_FAIL", not liquidity_ok),
        ("TREND_FAIL", not trend_ok),
        ("RS_FAIL", not rs_ok),
        ("CONTRACTION_FAIL", not contraction_ok),
        ("SIGNAL_EXTENDED", not extension_ok),
    ]
    reasons = ";".join(code for code, failed in reason_codes if failed)
    candidate = {
        "Entry_ID": f"{symbol}-{pd.Timestamp(row['Date']).date().isoformat()}",
        "Symbol": symbol,
        "Seed_Date": active["Seed_Date"],
        "Signal_Date": row["Date"],
        "Base_Age": active["Age"],
        "Original_Pivot": active["Original_Pivot"],
        "Active_Pivot": active_pivot,
        "ATR14_Seed": active["ATR14_Seed"],
        "ATR14_Signal": atr_signal,
        "Base_Low": active["Base_Low"],
        "Base_Depth_ATR": base_depth,
        "Initial_TR_Mean": initial_mean,
        "Final_TR_Mean": final_mean,
        "Contraction_Ratio": contraction,
        "Final_5_Prebreakout_Low": final_five_low,
        "Close": close,
        "SMA50": sma50,
        "SMA200": sma200,
        "Median_Traded_Value_20": liquidity,
        "RS21": row.get("RS21", np.nan),
        "RS63": row.get("RS63", np.nan),
        "RS126": row.get("RS126", np.nan),
        "Composite_RS": composite,
        "RS_Coverage": coverage,
        "Breakout_Volume_Ratio": _volume_ratio(frame, index, row),
        "Signal_Extension_ATR": extension,
        **gates,
        "Signal_Qualified": not reasons,
        "Signal_Rejection_Reason": reasons,
    }
    return {column: candidate.get(column, np.nan) for column in SIGNAL_COLUMNS}


def _new_base(symbol: str, frame: pd.DataFrame, index: int) -> dict[str, object]:
    row = frame.loc[index]
    base_id = f"{symbol}-{pd.Timestamp(row['Date']).date().isoformat()}"
    return {
        "Base_ID": base_id,
        "Seed_Date": row["Date"],
        "Seed_Index": index,
        "Age": 0,
        "Original_Pivot": row["High"],
        "Active_Pivot": row["High"],
        "ATR14_Seed": row.get("ATR14", np.nan),
        "Base_Low": np.inf,
        "Base_Indices": [],
    }


def scan_symbol_bases(symbol: str, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Scan one symbol using the locked pivot/base state ordering."""

    data = _frame_for_scan(frame)
    events: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    active: dict[str, object] | None = None
    for index, row in data.iterrows():
        if active is None:
            if _is_seed(data, index):
                active = _new_base(symbol, data, index)
                _record_event(events, symbol, row, active, "SEEDED")
            continue

        active["Age"] = int(active["Age"]) + 1
        active["Base_Indices"].append(index)
        active["Base_Low"] = min(float(active["Base_Low"]), float(row["Low"])) if _finite(row["Low"]) else active["Base_Low"]
        closed = False
        close = row.get("Close", np.nan)
        high = row.get("High", np.nan)
        if _finite(close) and float(close) > float(active["Active_Pivot"]):
            depth = _depth(active)
            if not _finite(depth) or depth > MAX_BASE_DEPTH_ATR:
                _record_event(events, symbol, row, active, "DEPTH_INVALIDATED")
                closed = True
            elif int(active["Age"]) < MIN_BASE_AGE:
                _record_event(events, symbol, row, active, "TOO_SHORT_BREAKOUT")
                closed = True
            else:
                _record_event(events, symbol, row, active, "BREAKOUT_CANDIDATE")
                candidates.append(_candidate_from_breakout(symbol, data, index, active))
                closed = True
        elif (
            _finite(high)
            and _finite(close)
            and float(high) > float(active["Active_Pivot"])
            and float(close) <= float(active["Active_Pivot"])
        ):
            new_pivot = float(high)
            _record_event(events, symbol, row, active, "FAILED_PROBE", new_pivot)
            active["Active_Pivot"] = new_pivot
            depth = _depth(active)
            if not _finite(depth) or depth > MAX_BASE_DEPTH_ATR:
                _record_event(events, symbol, row, active, "DEPTH_INVALIDATED")
                closed = True
        else:
            depth = _depth(active)
            if not _finite(depth) or depth > MAX_BASE_DEPTH_ATR:
                _record_event(events, symbol, row, active, "DEPTH_INVALIDATED")
                closed = True

        if not closed and int(active["Age"]) >= MAX_BASE_AGE:
            _record_event(events, symbol, row, active, "EXPIRED")
            closed = True
        if closed:
            active = None
            if _is_seed(data, index):
                active = _new_base(symbol, data, index)
                _record_event(events, symbol, row, active, "SEEDED")

    state_audit = pd.DataFrame(events, columns=STATE_COLUMNS)
    breakout_candidates = pd.DataFrame(candidates, columns=SIGNAL_COLUMNS)
    return state_audit, breakout_candidates


def _next_session(signal_date: pd.Timestamp, market_sessions: pd.DatetimeIndex) -> pd.Timestamp | None:
    sessions = pd.DatetimeIndex(pd.to_datetime(market_sessions, errors="coerce"))
    if sessions.tz is not None:
        sessions = sessions.tz_localize(None)
    sessions = sessions.dropna().drop_duplicates().sort_values()
    positions = np.flatnonzero(sessions == signal_date)
    if len(positions) == 0 or positions[0] + 1 >= len(sessions):
        return None
    return pd.Timestamp(sessions[positions[0] + 1])


def build_entries(
    signals: pd.DataFrame,
    price_frames: dict[str, pd.DataFrame],
    market_sessions: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create exactly one entry opportunity for each qualified signal."""

    accepted: list[dict[str, object]] = []
    cancelled: list[dict[str, object]] = []
    if signals.empty:
        return pd.DataFrame(), pd.DataFrame()
    for _, signal in signals.loc[
        signals.get("Signal_Qualified", pd.Series(True, index=signals.index)).fillna(False).astype(bool)
    ].iterrows():
        symbol = str(signal["Symbol"])
        signal_date = pd.Timestamp(signal["Signal_Date"])
        entry_id = signal.get("Entry_ID") or f"{symbol}-{signal_date.date().isoformat()}"
        next_date = _next_session(signal_date, market_sessions)
        common = {
            "Entry_ID": entry_id,
            "Symbol": symbol,
            "Signal_Date": signal_date,
            "Next_Session_Date": next_date,
        }
        if next_date is None:
            cancelled.append({**common, "Cancellation_Reason": "MISSING_NEXT_SESSION"})
            continue
        price_frame = price_frames.get(symbol)
        if price_frame is None or "Date" not in price_frame.columns:
            cancelled.append({**common, "Cancellation_Reason": "MISSING_NEXT_SESSION_BAR"})
            continue
        dates = pd.to_datetime(price_frame["Date"], errors="coerce")
        if getattr(dates.dt, "tz", None) is not None:
            dates = dates.dt.tz_localize(None)
        bar = price_frame.loc[dates.eq(next_date)]
        if bar.empty or len(bar) > 1 or not _finite(bar.iloc[0].get("Open", np.nan)):
            cancelled.append({**common, "Cancellation_Reason": "MISSING_NEXT_SESSION_BAR"})
            continue
        bar = bar.iloc[0]
        entry_open = float(bar["Open"])
        pivot = float(signal["Active_Pivot"])
        atr = float(signal["ATR14_Signal"])
        final_low = float(signal["Final_5_Prebreakout_Low"])
        structural_stop = final_low - STOP_BUFFER_ATR * atr if np.isfinite(final_low) and np.isfinite(atr) else np.nan
        reason = None
        if entry_open < pivot:
            reason = "OPEN_BELOW_PIVOT"
        elif not np.isfinite(atr) or atr <= 0 or entry_open > pivot + MAX_EXTENSION_ATR * atr:
            reason = "OPEN_ABOVE_EXTENSION_LIMIT"
        elif not np.isfinite(structural_stop) or structural_stop >= entry_open:
            reason = "STOP_NOT_BELOW_ENTRY"
        elif entry_open - structural_stop > MAX_STOP_DISTANCE_ATR * atr:
            reason = "STOP_TOO_WIDE"
        if reason is not None:
            cancelled.append(
                {
                    **common,
                    "Entry_Open": entry_open,
                    "Structural_Stop": structural_stop,
                    "Cancellation_Reason": reason,
                }
            )
            continue
        accepted.append(
            {
                **signal.to_dict(),
                "Entry_ID": entry_id,
                "Entry_Date": next_date,
                "Entry_Open": entry_open,
                "Structural_Stop": structural_stop,
                "Initial_Risk": entry_open - structural_stop,
            }
        )
    accepted_frame = pd.DataFrame(accepted)
    cancelled_frame = pd.DataFrame(cancelled)
    if not accepted_frame.empty:
        accepted_frame = accepted_frame.sort_values(["Entry_Date", "Symbol", "Entry_ID"]).reset_index(drop=True)
    if not cancelled_frame.empty:
        cancelled_frame = cancelled_frame.sort_values(["Signal_Date", "Symbol", "Entry_ID"]).reset_index(drop=True)
    return accepted_frame, cancelled_frame


def validate_signal_integrity(
    signals: pd.DataFrame,
    entries: pd.DataFrame,
    market_sessions: pd.DatetimeIndex,
) -> None:
    """Reject research-integrity violations before any outcome analysis."""

    qualified = signals.loc[signals.get("Signal_Qualified", pd.Series(dtype=bool)).fillna(False).astype(bool)]
    if not qualified.empty:
        if (qualified["Signal_Date"] < pd.Timestamp("2023-08-01")).any():
            raise AssertionError("qualified signal occurs before the locked signal window")
        if (qualified["RS_Coverage"] < MIN_RS_COVERAGE).any():
            raise AssertionError("qualified signal has unsafe RS coverage")
        if (~qualified["Membership_OK"].astype(bool)).any():
            raise AssertionError("qualified signal is not an active point-in-time member")
        if (qualified["Composite_RS"] < 70.0).any():
            raise AssertionError("qualified signal is below the Composite_RS threshold")
        if ~qualified["Base_Age"].between(10, 30).all():
            raise AssertionError("qualified signal has an invalid base age")
        if (qualified["Contraction_Ratio"] > MAX_CONTRACTION_RATIO).any():
            raise AssertionError("qualified signal fails the contraction limit")
        if (qualified["Signal_Extension_ATR"] > MAX_EXTENSION_ATR).any():
            raise AssertionError("qualified signal exceeds the extension limit")
    if entries.empty:
        return
    qualified_ids = set(qualified["Entry_ID"])
    if not set(entries["Entry_ID"]).issubset(qualified_ids):
        raise AssertionError("accepted entry is not backed by a qualified signal")
    sessions = pd.DatetimeIndex(pd.to_datetime(market_sessions)).drop_duplicates().sort_values()
    for _, entry in entries.iterrows():
        next_date = _next_session(pd.Timestamp(entry["Signal_Date"]), sessions)
        if next_date is None or pd.Timestamp(entry["Entry_Date"]) != next_date:
            raise AssertionError("accepted entry is not on the immediate next market session")
        if not (
            float(entry["Entry_Open"]) >= float(entry["Active_Pivot"])
            and float(entry["Entry_Open"]) <= float(entry["Active_Pivot"]) + float(entry["ATR14_Signal"])
        ):
            raise AssertionError("accepted entry is outside the pivot-to-one-ATR range")
        if not float(entry["Structural_Stop"]) < float(entry["Entry_Open"]):
            raise AssertionError("structural stop is not below entry")
        if float(entry["Entry_Open"]) - float(entry["Structural_Stop"]) > MAX_STOP_DISTANCE_ATR * float(entry["ATR14_Signal"]):
            raise AssertionError("structural stop is too wide")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[4]
    module_dir = Path(__file__).resolve().parent
    membership_path = root / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv"
    breadth_path = root / "Swing Trading/research/swing/market_breadth/output/nifty500_breadth_daily.csv"
    output_dir = module_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    from build_v2_features import build_feature_frames, load_membership, rank_point_in_time_rs

    membership = load_membership(membership_path)
    frames, validation, errors = build_feature_frames(membership)
    ranked, rs_audit = rank_point_in_time_rs(frames, membership)
    state_frames = []
    candidates = []
    for symbol, frame in ranked.items():
        state, signal = scan_symbol_bases(symbol, frame)
        state_frames.append(state)
        candidates.append(signal)
    states = pd.concat(state_frames, ignore_index=True) if state_frames else pd.DataFrame(columns=STATE_COLUMNS)
    signals = pd.concat(candidates, ignore_index=True) if candidates else pd.DataFrame(columns=SIGNAL_COLUMNS)
    signals = signals.loc[
        signals["Signal_Date"].between(pd.Timestamp("2023-08-01"), pd.Timestamp("2026-08-25"))
    ].copy()
    breadth = pd.read_csv(breadth_path, parse_dates=["Date"])
    sessions = pd.DatetimeIndex(pd.to_datetime(breadth["Date"]))
    market_data_dates = pd.DatetimeIndex(
        sorted({date for frame in ranked.values() for date in pd.to_datetime(frame["Date"]).dropna()})
    )
    if pd.Timestamp("2026-08-26") in market_data_dates and pd.Timestamp("2026-08-26") not in sessions:
        sessions = sessions.append(pd.DatetimeIndex([pd.Timestamp("2026-08-26")])).drop_duplicates().sort_values()
    accepted, cancelled = build_entries(signals, ranked, sessions)
    validate_signal_integrity(signals, accepted, sessions)
    validation.to_csv(output_dir / "v2_data_validation.csv", index=False)
    rs_audit.to_csv(output_dir / "v2_universe_rs_audit.csv", index=False, date_format="%Y-%m-%d")
    states.to_csv(output_dir / "v2_base_state_audit.csv", index=False, date_format="%Y-%m-%d")
    signals.to_csv(output_dir / "v2_signal_candidates.csv", index=False, date_format="%Y-%m-%d")
    accepted.to_csv(output_dir / "v2_entries.csv", index=False, date_format="%Y-%m-%d")
    cancelled.to_csv(output_dir / "v2_entry_cancellations.csv", index=False, date_format="%Y-%m-%d")
    print(f"symbols={len(ranked)} candidates={len(signals)} entries={len(accepted)} cancellations={len(cancelled)}")
    if errors:
        print(f"download failures={len(errors)}")
