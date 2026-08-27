"""Generate Strategy V3 leader/pullback candidates and one-shot entries."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from build_v3_features import LIQUIDITY_FLOOR, MIN_RS_COVERAGE


SIGNAL_START = pd.Timestamp("2023-08-01")
SIGNAL_END = pd.Timestamp("2026-08-25")
MIN_PULLBACK_AGE = 3
MAX_PULLBACK_AGE = 10
MIN_PULLBACK_DEPTH_ATR = 0.5
MAX_PULLBACK_DEPTH_ATR = 2.5
MIN_COMPOSITE_RS = 70.0
MAX_ENTRY_EXTENSION_ATR = 0.5
STOP_BUFFER_ATR = 0.25
MAX_STOP_DISTANCE_ATR = 2.5

STATE_COLUMNS = [
    "Symbol",
    "Date",
    "State_ID",
    "Event",
    "Leader_Date",
    "Age",
    "Leader_Close",
    "ATR14_Seed",
    "Pullback_Low",
    "Pullback_Depth_ATR",
    "Prior_High",
    "High",
    "Low",
    "Close",
    "SMA20",
    "SMA50",
    "SMA200",
]

SIGNAL_COLUMNS = [
    "Entry_ID",
    "Symbol",
    "Leader_Date",
    "Signal_Date",
    "Pullback_Age",
    "Leader_Close",
    "ATR14_Seed",
    "ATR14_Signal",
    "Pullback_Low",
    "Pullback_Depth_ATR",
    "Close",
    "Prior_High",
    "SMA20",
    "SMA50",
    "SMA200",
    "Median_Traded_Value_20",
    "RS21",
    "RS63",
    "RS126",
    "Composite_RS",
    "RS_Coverage",
    "Resumption_Volume_Ratio",
    "Seed_Membership_OK",
    "Seed_RS_Coverage_OK",
    "Seed_Liquidity_OK",
    "Seed_Trend_OK",
    "Seed_RS_OK",
    "Signal_Membership_OK",
    "Signal_RS_Coverage_OK",
    "Signal_Liquidity_OK",
    "Signal_Trend_OK",
    "Signal_RS_OK",
    "Age_OK",
    "Depth_OK",
    "Resumption_OK",
    "Not_New_Leader_OK",
    "Signal_Qualified",
    "Signal_Rejection_Reason",
]


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


def _clean_sessions(values: pd.DatetimeIndex | object) -> pd.DatetimeIndex:
    sessions = pd.DatetimeIndex(pd.to_datetime(values, errors="coerce"))
    if sessions.tz is not None:
        sessions = sessions.tz_localize(None)
    return sessions.dropna().drop_duplicates().sort_values()


def load_canonical_market_sessions(
    index_path: Path,
    extra_dates: pd.DatetimeIndex | None = None,
) -> pd.DatetimeIndex:
    """Read the canonical market-session spine and optionally append dates."""

    index = pd.read_csv(index_path)
    if "Date" not in index.columns:
        raise ValueError("canonical session file must contain Date")
    values = pd.DatetimeIndex(pd.to_datetime(index["Date"], errors="coerce"))
    if extra_dates is not None:
        values = values.append(pd.DatetimeIndex(pd.to_datetime(extra_dates, errors="coerce")))
    return _clean_sessions(values)


def prewindow_seed_start(canonical_sessions: pd.DatetimeIndex) -> pd.Timestamp:
    sessions = _clean_sessions(canonical_sessions)
    pos = int(sessions.searchsorted(SIGNAL_START, side="left"))
    if pos < 10:
        raise ValueError("fewer than 10 canonical sessions before SIGNAL_START")
    return pd.Timestamp(sessions[pos - 10])


def _frame_for_scan(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"Date", "High", "Low", "Close", "ATR14", "SMA20", "SMA50", "SMA200"}
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


def is_leader_seed(frame: pd.DataFrame, index: int) -> bool:
    if index < 19 or pd.isna(frame.loc[index, "Close"]):
        return False
    window = pd.to_numeric(frame.loc[index - 19 : index, "Close"], errors="coerce")
    return bool(window.notna().all() and float(frame.loc[index, "Close"]) == float(window.max()))


def seed_eligibility(row: pd.Series) -> tuple[bool, str]:
    if not _truthy(row.get("Point_In_Time_Member", False)):
        return False, "NOT_POINT_IN_TIME_MEMBER"
    coverage = row.get("RS_Coverage", np.nan)
    if not _truthy(row.get("RS_Research_Safe", False)) or not _finite(coverage) or float(coverage) < MIN_RS_COVERAGE:
        return False, "RS_COVERAGE_UNSAFE"
    liquidity = row.get("Median_Traded_Value_20", np.nan)
    if not _finite(liquidity) or float(liquidity) < LIQUIDITY_FLOOR:
        return False, "LIQUIDITY_FAIL"
    close = row.get("Close", np.nan)
    sma50 = row.get("SMA50", np.nan)
    sma200 = row.get("SMA200", np.nan)
    if not (_finite(close) and _finite(sma50) and _finite(sma200) and float(close) > float(sma50) > float(sma200)):
        return False, "TREND_FAIL"
    composite = row.get("Composite_RS", np.nan)
    if not _finite(composite) or float(composite) < MIN_COMPOSITE_RS:
        return False, "RS_FAIL"
    return True, ""


def new_state(symbol: str, row: pd.Series, index: int) -> dict[str, object]:
    seed_ok, _ = seed_eligibility(row)
    if not seed_ok:
        raise ValueError("cannot create a state from an ineligible seed")
    date = pd.Timestamp(row["Date"])
    return {
        "State_ID": f"{symbol}-{date.date().isoformat()}",
        "Symbol": symbol,
        "Leader_Date": date,
        "Leader_Index": index,
        "Leader_Close": row.get("Close", np.nan),
        "ATR14_Seed": row.get("ATR14", np.nan),
        "Age": 0,
        "Pullback_Low": np.inf,
        "Pullback_Indices": [],
        "Seed_Membership_OK": _truthy(row.get("Point_In_Time_Member", False)),
        "Seed_RS_Coverage_OK": _truthy(row.get("RS_Research_Safe", False))
        and _finite(row.get("RS_Coverage", np.nan))
        and float(row.get("RS_Coverage")) >= MIN_RS_COVERAGE,
        "Seed_Liquidity_OK": _finite(row.get("Median_Traded_Value_20", np.nan))
        and float(row.get("Median_Traded_Value_20")) >= LIQUIDITY_FLOOR,
        "Seed_Trend_OK": _trend_ok(row),
        "Seed_RS_OK": _finite(row.get("Composite_RS", np.nan))
        and float(row.get("Composite_RS")) >= MIN_COMPOSITE_RS,
        "Seed_RS_Coverage": row.get("RS_Coverage", np.nan),
        "Seed_Composite_RS": row.get("Composite_RS", np.nan),
    }


def _trend_ok(row: pd.Series) -> bool:
    close = row.get("Close", np.nan)
    sma50 = row.get("SMA50", np.nan)
    sma200 = row.get("SMA200", np.nan)
    return bool(_finite(close) and _finite(sma50) and _finite(sma200) and float(close) > float(sma50) > float(sma200))


def _state_depth(active: dict[str, object]) -> float:
    atr_seed = float(active["ATR14_Seed"])
    low = float(active["Pullback_Low"])
    if not np.isfinite(atr_seed) or atr_seed <= 0 or not np.isfinite(low):
        return np.nan
    return (float(active["Leader_Close"]) - low) / atr_seed


def _record_event(
    events: list[dict[str, object]],
    symbol: str,
    row: pd.Series,
    active: dict[str, object],
    event: str,
    prior_high: object = np.nan,
) -> None:
    events.append(
        {
            "Symbol": symbol,
            "Date": row["Date"],
            "State_ID": active["State_ID"],
            "Event": event,
            "Leader_Date": active["Leader_Date"],
            "Age": active["Age"],
            "Leader_Close": active["Leader_Close"],
            "ATR14_Seed": active["ATR14_Seed"],
            "Pullback_Low": active["Pullback_Low"],
            "Pullback_Depth_ATR": _state_depth(active),
            "Prior_High": prior_high,
            "High": row.get("High", np.nan),
            "Low": row.get("Low", np.nan),
            "Close": row.get("Close", np.nan),
            "SMA20": row.get("SMA20", np.nan),
            "SMA50": row.get("SMA50", np.nan),
            "SMA200": row.get("SMA200", np.nan),
        }
    )


def _volume_ratio(frame: pd.DataFrame, index: int, row: pd.Series) -> float:
    if "Volume" not in frame:
        return np.nan
    volume = pd.to_numeric(frame.loc[:index, "Volume"], errors="coerce").tail(20)
    median = volume.median()
    if not _finite(row.get("Volume", np.nan)) or not _finite(median) or float(median) == 0:
        return np.nan
    return float(row["Volume"]) / float(median)


def _signal_gate_values(candidate: dict[str, object]) -> dict[str, object]:
    reasons: list[str] = []
    checks = [
        ("NOT_POINT_IN_TIME_MEMBER", not bool(candidate["Signal_Membership_OK"])),
        ("RS_COVERAGE_UNSAFE", not bool(candidate["Signal_RS_Coverage_OK"])),
        ("LIQUIDITY_FAIL", not bool(candidate["Signal_Liquidity_OK"])),
        ("TREND_FAIL", not bool(candidate["Signal_Trend_OK"])),
        ("RS_FAIL", not bool(candidate["Signal_RS_OK"])),
        ("AGE_FAIL", not bool(candidate["Age_OK"])),
        (
            "PULLBACK_TOO_SHALLOW",
            not bool(candidate["Depth_OK"]) and float(candidate["Pullback_Depth_ATR"]) < MIN_PULLBACK_DEPTH_ATR,
        ),
        (
            "DEPTH_FAIL",
            not bool(candidate["Depth_OK"]) and float(candidate["Pullback_Depth_ATR"]) >= MIN_PULLBACK_DEPTH_ATR,
        ),
        ("RESUMPTION_FAIL", not bool(candidate["Resumption_OK"])),
        ("NEW_LEADER_FAIL", not bool(candidate["Not_New_Leader_OK"])),
    ]
    reasons.extend(code for code, failed in checks if failed)
    candidate["Signal_Qualified"] = not reasons
    candidate["Signal_Rejection_Reason"] = ";".join(reasons)
    return candidate


def qualify_candidate(candidate: dict[str, object] | pd.Series) -> dict[str, object]:
    """Evaluate the frozen signal-date gates without using diagnostic fields."""

    result = dict(candidate)
    result.setdefault("Signal_Membership_OK", _truthy(result.get("Point_In_Time_Member", False)))
    result.setdefault(
        "Signal_RS_Coverage_OK",
        _truthy(result.get("RS_Research_Safe", False))
        and _finite(result.get("RS_Coverage", np.nan))
        and float(result.get("RS_Coverage")) >= MIN_RS_COVERAGE,
    )
    result.setdefault(
        "Signal_Liquidity_OK",
        _finite(result.get("Median_Traded_Value_20", np.nan))
        and float(result.get("Median_Traded_Value_20")) >= LIQUIDITY_FLOOR,
    )
    result.setdefault("Signal_Trend_OK", _trend_ok(pd.Series(result)))
    result.setdefault(
        "Signal_RS_OK",
        _finite(result.get("Composite_RS", np.nan))
        and float(result.get("Composite_RS")) >= MIN_COMPOSITE_RS,
    )
    age = result.get("Pullback_Age", np.nan)
    depth = result.get("Pullback_Depth_ATR", np.nan)
    result.setdefault("Age_OK", _finite(age) and MIN_PULLBACK_AGE <= int(age) <= MAX_PULLBACK_AGE)
    result.setdefault("Depth_OK", _finite(depth) and MIN_PULLBACK_DEPTH_ATR <= float(depth) <= MAX_PULLBACK_DEPTH_ATR)
    result.setdefault(
        "Resumption_OK",
        _finite(result.get("Close", np.nan))
        and _finite(result.get("Prior_High", np.nan))
        and _finite(result.get("SMA20", np.nan))
        and float(result["Close"]) > float(result["Prior_High"])
        and float(result["Close"]) > float(result["SMA20"]),
    )
    result.setdefault(
        "Not_New_Leader_OK",
        _finite(result.get("Close", np.nan))
        and _finite(result.get("Leader_Close", np.nan))
        and float(result["Close"]) <= float(result["Leader_Close"]),
    )
    return _signal_gate_values(result)


def build_candidate(
    symbol: str,
    row: pd.Series,
    prior_high: float,
    active: dict[str, object],
) -> dict[str, object]:
    """Build and qualify the first resumption candidate from an active state."""

    signal_date = pd.Timestamp(row["Date"])
    candidate: dict[str, object] = {
        "Entry_ID": f"{symbol}-{signal_date.date().isoformat()}",
        "Symbol": symbol,
        "Leader_Date": active["Leader_Date"],
        "Signal_Date": signal_date,
        "Pullback_Age": int(active["Age"]),
        "Leader_Close": active["Leader_Close"],
        "ATR14_Seed": active["ATR14_Seed"],
        "ATR14_Signal": row.get("ATR14", np.nan),
        "Pullback_Low": active["Pullback_Low"],
        "Pullback_Depth_ATR": _state_depth(active),
        "Close": row.get("Close", np.nan),
        "Prior_High": prior_high,
        "SMA20": row.get("SMA20", np.nan),
        "SMA50": row.get("SMA50", np.nan),
        "SMA200": row.get("SMA200", np.nan),
        "Median_Traded_Value_20": row.get("Median_Traded_Value_20", np.nan),
        "RS21": row.get("RS21", np.nan),
        "RS63": row.get("RS63", np.nan),
        "RS126": row.get("RS126", np.nan),
        "Composite_RS": row.get("Composite_RS", np.nan),
        "RS_Coverage": row.get("RS_Coverage", np.nan),
        "Resumption_Volume_Ratio": np.nan,
        "Seed_Membership_OK": active["Seed_Membership_OK"],
        "Seed_RS_Coverage_OK": active["Seed_RS_Coverage_OK"],
        "Seed_Liquidity_OK": active["Seed_Liquidity_OK"],
        "Seed_Trend_OK": active["Seed_Trend_OK"],
        "Seed_RS_OK": active["Seed_RS_OK"],
        "Signal_Membership_OK": _truthy(row.get("Point_In_Time_Member", False)),
        "Signal_RS_Coverage_OK": _truthy(row.get("RS_Research_Safe", False))
        and _finite(row.get("RS_Coverage", np.nan))
        and float(row.get("RS_Coverage")) >= MIN_RS_COVERAGE,
        "Signal_Liquidity_OK": _finite(row.get("Median_Traded_Value_20", np.nan))
        and float(row.get("Median_Traded_Value_20")) >= LIQUIDITY_FLOOR,
        "Signal_Trend_OK": _trend_ok(row),
        "Signal_RS_OK": _finite(row.get("Composite_RS", np.nan))
        and float(row.get("Composite_RS")) >= MIN_COMPOSITE_RS,
        "Age_OK": MIN_PULLBACK_AGE <= int(active["Age"]) <= MAX_PULLBACK_AGE,
        "Depth_OK": _finite(_state_depth(active))
        and MIN_PULLBACK_DEPTH_ATR <= _state_depth(active) <= MAX_PULLBACK_DEPTH_ATR,
        "Resumption_OK": _finite(row.get("Close", np.nan))
        and _finite(prior_high)
        and _finite(row.get("SMA20", np.nan))
        and float(row["Close"]) > float(prior_high)
        and float(row["Close"]) > float(row["SMA20"]),
        "Not_New_Leader_OK": _finite(row.get("Close", np.nan))
        and _finite(active.get("Leader_Close", np.nan))
        and float(row["Close"]) <= float(active["Leader_Close"]),
    }
    return _signal_gate_values(candidate)


def _seed_date_allowed(date: pd.Timestamp, sessions: pd.DatetimeIndex) -> bool:
    return date in sessions and date >= prewindow_seed_start(sessions)


def scan_symbol_pullbacks(
    symbol: str,
    frame: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Scan one symbol using the locked V3 state-machine ordering."""

    data = _frame_for_scan(frame)
    sessions = _clean_sessions(canonical_sessions)
    data = data.loc[data["Date"].isin(sessions)].reset_index(drop=True)
    events: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    active: dict[str, object] | None = None

    for index, row in data.iterrows():
        if active is None:
            if _seed_date_allowed(pd.Timestamp(row["Date"]), sessions) and is_leader_seed(data, index):
                seed_ok, _ = seed_eligibility(row)
                if seed_ok:
                    active = new_state(symbol, row, index)
                    _record_event(events, symbol, row, active, "SEEDED")
            continue

        active["Age"] = int(active["Age"]) + 1
        active["Pullback_Indices"].append(index)
        if _finite(row.get("Low", np.nan)):
            active["Pullback_Low"] = min(float(active["Pullback_Low"]), float(row["Low"]))
        depth = _state_depth(active)
        prior_high = data.loc[index - 1, "High"] if index > 0 else np.nan
        closed = False

        if _finite(row.get("Close", np.nan)) and _finite(row.get("SMA50", np.nan)) and float(row["Close"]) < float(row["SMA50"]):
            _record_event(events, symbol, row, active, "SMA50_INVALIDATED", prior_high)
            closed = True
        elif not _finite(depth) or depth > MAX_PULLBACK_DEPTH_ATR:
            _record_event(events, symbol, row, active, "DEPTH_INVALIDATED", prior_high)
            closed = True
        elif _finite(row.get("Close", np.nan)) and float(row["Close"]) > float(active["Leader_Close"]):
            _record_event(events, symbol, row, active, "NEW_LEADER_CLOSE", prior_high)
            closed = True
        else:
            resumes = (
                _finite(row.get("Close", np.nan))
                and _finite(prior_high)
                and _finite(row.get("SMA20", np.nan))
                and float(row["Close"]) > float(prior_high)
                and float(row["Close"]) > float(row["SMA20"])
            )
            if resumes and int(active["Age"]) <= 2:
                _record_event(events, symbol, row, active, "TOO_SHORT_RESUMPTION", prior_high)
                closed = True
            elif resumes and MIN_PULLBACK_AGE <= int(active["Age"]) <= MAX_PULLBACK_AGE:
                candidate = build_candidate(symbol, row, float(prior_high), active)
                event = (
                    "PULLBACK_TOO_SHALLOW"
                    if float(candidate["Pullback_Depth_ATR"]) < MIN_PULLBACK_DEPTH_ATR
                    else "RESUMPTION_CANDIDATE"
                )
                _record_event(events, symbol, row, active, event, prior_high)
                candidate["Resumption_Volume_Ratio"] = _volume_ratio(data, index, row)
                if SIGNAL_START <= pd.Timestamp(row["Date"]) <= SIGNAL_END:
                    candidates.append(candidate)
                closed = True
            elif int(active["Age"]) >= MAX_PULLBACK_AGE:
                _record_event(events, symbol, row, active, "EXPIRED", prior_high)
                closed = True
            else:
                _record_event(events, symbol, row, active, "ACTIVE", prior_high)

        if closed:
            active = None
            if _seed_date_allowed(pd.Timestamp(row["Date"]), sessions) and is_leader_seed(data, index):
                seed_ok, _ = seed_eligibility(row)
                if seed_ok:
                    active = new_state(symbol, row, index)
                    _record_event(events, symbol, row, active, "SEEDED")

    state_audit = pd.DataFrame(events, columns=STATE_COLUMNS)
    signal_candidates = pd.DataFrame(candidates, columns=SIGNAL_COLUMNS)
    return state_audit, signal_candidates


def _next_session(signal_date: pd.Timestamp, market_sessions: pd.DatetimeIndex) -> pd.Timestamp | None:
    sessions = _clean_sessions(market_sessions)
    positions = np.flatnonzero(sessions == pd.Timestamp(signal_date))
    if len(positions) == 0 or positions[0] + 1 >= len(sessions):
        return None
    return pd.Timestamp(sessions[positions[0] + 1])


def build_entries(
    signals: pd.DataFrame,
    price_frames: dict[str, pd.DataFrame],
    canonical_sessions: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create exactly one immediate-next-session opportunity per qualified signal."""

    accepted: list[dict[str, object]] = []
    cancellations: list[dict[str, object]] = []
    if signals.empty:
        return pd.DataFrame(), pd.DataFrame()
    qualified = signals.loc[
        signals.get("Signal_Qualified", pd.Series(False, index=signals.index)).map(_truthy)
    ]
    for _, signal in qualified.iterrows():
        symbol = str(signal["Symbol"])
        signal_date = pd.Timestamp(signal["Signal_Date"])
        entry_id = str(signal.get("Entry_ID") or f"{symbol}-{signal_date.date().isoformat()}")
        next_date = _next_session(signal_date, canonical_sessions)
        common = {
            "Entry_ID": entry_id,
            "Symbol": symbol,
            "Signal_Date": signal_date,
            "Next_Session_Date": next_date,
        }
        if next_date is None:
            cancellations.append({**common, "Cancellation_Reason": "MISSING_NEXT_SESSION"})
            continue
        prices = price_frames.get(symbol)
        if prices is None or "Date" not in prices.columns:
            cancellations.append({**common, "Cancellation_Reason": "MISSING_NEXT_SESSION_BAR"})
            continue
        dates = pd.to_datetime(prices["Date"], errors="coerce")
        if getattr(dates.dt, "tz", None) is not None:
            dates = dates.dt.tz_localize(None)
        bars = prices.loc[dates.eq(next_date)]
        if len(bars) != 1 or not _finite(bars.iloc[0].get("Open", np.nan)):
            cancellations.append({**common, "Cancellation_Reason": "MISSING_NEXT_SESSION_BAR"})
            continue
        bar = bars.iloc[0]
        entry_open = float(bar["Open"])
        sma20 = signal.get("SMA20", np.nan)
        leader_close = signal.get("Leader_Close", np.nan)
        atr = signal.get("ATR14_Signal", np.nan)
        pullback_low = signal.get("Pullback_Low", np.nan)
        structural_stop = (
            float(pullback_low) - STOP_BUFFER_ATR * float(atr)
            if _finite(pullback_low) and _finite(atr) and float(atr) > 0
            else np.nan
        )
        reason: str | None = None
        if not _finite(sma20) or entry_open < float(sma20):
            reason = "OPEN_BELOW_SMA20_SIGNAL"
        elif (
            not _finite(atr)
            or float(atr) <= 0
            or not _finite(leader_close)
            or entry_open > float(leader_close) + MAX_ENTRY_EXTENSION_ATR * float(atr)
        ):
            reason = "OPEN_ABOVE_EXTENSION_LIMIT"
        elif not _finite(structural_stop) or structural_stop >= entry_open:
            reason = "STOP_NOT_BELOW_ENTRY"
        elif entry_open - structural_stop > MAX_STOP_DISTANCE_ATR * float(atr):
            reason = "STOP_TOO_WIDE"
        if reason is not None:
            cancellations.append(
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
    cancellations_frame = pd.DataFrame(cancellations)
    if not accepted_frame.empty:
        accepted_frame = accepted_frame.sort_values(["Entry_Date", "Symbol", "Entry_ID"]).reset_index(drop=True)
    if not cancellations_frame.empty:
        cancellations_frame = cancellations_frame.sort_values(["Signal_Date", "Symbol", "Entry_ID"]).reset_index(drop=True)
    return accepted_frame, cancellations_frame


def validate_signal_integrity(
    signals: pd.DataFrame,
    entries: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex,
) -> None:
    """Reject timing and entry-bound violations before outcome analysis."""

    qualified = signals.loc[
        signals.get("Signal_Qualified", pd.Series(False, index=signals.index)).map(_truthy)
    ].copy()
    if not qualified.empty:
        dates = pd.to_datetime(qualified["Signal_Date"], errors="raise")
        if (~dates.between(SIGNAL_START, SIGNAL_END)).any():
            raise AssertionError("qualified signal is outside the locked signal window")
        if "Signal_RS_Coverage_OK" in qualified and (~qualified["Signal_RS_Coverage_OK"].map(_truthy)).any():
            raise AssertionError("qualified signal has unsafe RS coverage")
        if "Signal_Membership_OK" in qualified and (~qualified["Signal_Membership_OK"].map(_truthy)).any():
            raise AssertionError("qualified signal is not an active point-in-time member")
        if "Composite_RS" in qualified and (pd.to_numeric(qualified["Composite_RS"], errors="coerce") < MIN_COMPOSITE_RS).any():
            raise AssertionError("qualified signal is below the Composite_RS threshold")
        if "Pullback_Age" in qualified and (~pd.to_numeric(qualified["Pullback_Age"], errors="coerce").between(MIN_PULLBACK_AGE, MAX_PULLBACK_AGE)).any():
            raise AssertionError("qualified signal has an invalid pullback age")
        if "Pullback_Depth_ATR" in qualified and (~pd.to_numeric(qualified["Pullback_Depth_ATR"], errors="coerce").between(MIN_PULLBACK_DEPTH_ATR, MAX_PULLBACK_DEPTH_ATR)).any():
            raise AssertionError("qualified signal has an invalid pullback depth")
    if entries.empty:
        return
    qualified_ids = set(qualified["Entry_ID"].astype(str))
    if not set(entries["Entry_ID"].astype(str)).issubset(qualified_ids):
        raise AssertionError("accepted entry is not backed by a qualified signal")
    sessions = _clean_sessions(canonical_sessions)
    for _, entry in entries.iterrows():
        leader_date = pd.Timestamp(entry["Leader_Date"])
        signal_date = pd.Timestamp(entry["Signal_Date"])
        entry_date = pd.Timestamp(entry["Entry_Date"])
        if not leader_date < signal_date < entry_date:
            raise AssertionError("entry dates violate Leader_Date < Signal_Date < Entry_Date")
        if not SIGNAL_START <= signal_date <= SIGNAL_END:
            raise AssertionError("accepted signal is outside the locked signal window")
        if _next_session(signal_date, sessions) != entry_date:
            raise AssertionError("accepted entry is not on the immediate next market session")
        atr = float(entry["ATR14_Signal"])
        if not (
            float(entry["Entry_Open"]) >= float(entry["SMA20"])
            and float(entry["Entry_Open"]) <= float(entry["Leader_Close"]) + MAX_ENTRY_EXTENSION_ATR * atr
        ):
            raise AssertionError("accepted entry is outside the signal-known open bounds")
        if not float(entry["Structural_Stop"]) < float(entry["Entry_Open"]):
            raise AssertionError("structural stop is not below entry")
        if float(entry["Entry_Open"]) - float(entry["Structural_Stop"]) > MAX_STOP_DISTANCE_ATR * atr:
            raise AssertionError("structural stop is too wide")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[4]
    module_dir = Path(__file__).resolve().parent
    membership_path = root / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv"
    index_path = root / "Swing Trading/nifty500_regime_daily.csv"
    output_dir = module_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    from build_v3_features import build_feature_frames, load_membership, rank_point_in_time_rs

    membership = load_membership(membership_path)
    frames, validation, errors = build_feature_frames(membership)
    ranked, rs_audit = rank_point_in_time_rs(frames, membership)
    market_dates = pd.DatetimeIndex(
        sorted({date for frame in ranked.values() for date in pd.to_datetime(frame["Date"]).dropna()})
    )
    extra = pd.DatetimeIndex([pd.Timestamp("2026-08-26")]) if pd.Timestamp("2026-08-26") in market_dates else None
    sessions = load_canonical_market_sessions(index_path, extra)
    state_frames = []
    candidate_frames = []
    for symbol, frame in ranked.items():
        state, candidate = scan_symbol_pullbacks(symbol, frame, sessions)
        state_frames.append(state)
        candidate_frames.append(candidate)
    states = pd.concat(state_frames, ignore_index=True) if state_frames else pd.DataFrame(columns=STATE_COLUMNS)
    signals = pd.concat(candidate_frames, ignore_index=True) if candidate_frames else pd.DataFrame(columns=SIGNAL_COLUMNS)
    accepted, cancellations = build_entries(signals, ranked, sessions)
    validate_signal_integrity(signals, accepted, sessions)
    validation.to_csv(output_dir / "v3_data_validation.csv", index=False)
    rs_audit.to_csv(output_dir / "v3_universe_rs_audit.csv", index=False, date_format="%Y-%m-%d")
    states.to_csv(output_dir / "v3_pullback_state_audit.csv", index=False, date_format="%Y-%m-%d")
    signals.to_csv(output_dir / "v3_signal_candidates.csv", index=False, date_format="%Y-%m-%d")
    accepted.to_csv(output_dir / "v3_entries.csv", index=False, date_format="%Y-%m-%d")
    cancellations.to_csv(output_dir / "v3_entry_cancellations.csv", index=False, date_format="%Y-%m-%d")
    print(
        f"symbols={len(ranked)} candidates={len(signals)} "
        f"qualified={int(signals['Signal_Qualified'].sum()) if not signals.empty else 0} "
        f"entries={len(accepted)} cancellations={len(cancellations)}"
    )
    if errors:
        print(f"download failures={len(errors)}")
