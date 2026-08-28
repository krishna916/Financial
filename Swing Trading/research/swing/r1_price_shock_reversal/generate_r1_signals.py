"""Generate the frozen R1 shock cohorts and immediate-next-open entries."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from build_r1_features import (
    LIQUIDITY_FLOOR,
    SIGNAL_END,
    SIGNAL_START,
    active_members_on,
    build_feature_frames,
    load_membership,
)


SHOCK_THRESHOLD = -2.0
LOW_VOLUME_MAX = 1.0
HIGH_VOLUME_MIN = 1.5
STOP_BUFFER_ATR = 0.25

ENTRY_CANCELLATION_REASONS = (
    "SAME_SYMBOL_LOCKOUT",
    "MISSING_NEXT_SESSION",
    "MISSING_NEXT_SESSION_BAR",
    "OPEN_BELOW_STRUCTURAL_STOP",
)

CANDIDATE_COLUMNS = [
    "Signal_ID",
    "Symbol",
    "Signal_Date",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "Return",
    "Sigma20",
    "Shock_Score",
    "Prior20_Median_Volume",
    "Volume_Ratio",
    "Prior20_Median_Traded_Value",
    "ATR14_Signal",
    "Point_In_Time_Member",
    "Cohort",
    "Data_Eligible",
    "Liquidity_OK",
]


def _finite(value: object) -> bool:
    try:
        return bool(pd.notna(value) and np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _truthy(value: object, default: bool = False) -> bool:
    if value is None or pd.isna(value):
        return default
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
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
    """Read the canonical session spine and append explicitly supplied sessions."""

    index = pd.read_csv(index_path)
    if "Date" not in index.columns:
        raise ValueError("canonical session file must contain Date")
    values = pd.DatetimeIndex(pd.to_datetime(index["Date"], errors="coerce"))
    if extra_dates is not None:
        values = values.append(_clean_sessions(extra_dates))
    return _clean_sessions(values)


def next_session(
    date: pd.Timestamp,
    sessions: pd.DatetimeIndex,
    steps: int = 1,
) -> pd.Timestamp | None:
    """Return the canonical session ``steps`` positions after ``date``."""

    if steps < 1:
        raise ValueError("steps must be positive")
    cleaned = _clean_sessions(sessions)
    day = pd.Timestamp(date)
    positions = np.flatnonzero(cleaned == day)
    if len(positions) != 1:
        return None
    position = int(positions[0]) + steps
    if position >= len(cleaned):
        return None
    return pd.Timestamp(cleaned[position])


def classify_shock_row(row: pd.Series) -> str:
    """Classify a negative shock into the frozen volume cohorts."""

    shock = row.get("Shock_Score", np.nan)
    volume_ratio = row.get("Volume_Ratio", np.nan)
    if not _finite(shock) or float(shock) > SHOCK_THRESHOLD:
        return "NOT_ELIGIBLE_SHOCK"
    if not _finite(volume_ratio):
        return "NOT_ELIGIBLE_VOLUME"
    if float(volume_ratio) <= LOW_VOLUME_MAX:
        return "LOW_VOLUME"
    if float(volume_ratio) >= HIGH_VOLUME_MIN:
        return "HIGH_VOLUME"
    return "MIDDLE_VOLUME"


def qualify_low_volume_signal(row: pd.Series) -> tuple[bool, str]:
    """Apply only the frozen PIT, data, shock, liquidity, and low-volume rules."""

    try:
        signal_date = pd.Timestamp(row["Signal_Date"])
    except (KeyError, TypeError, ValueError):
        return False, "INVALID_SIGNAL_DATE"
    if not SIGNAL_START <= signal_date <= SIGNAL_END:
        return False, "OUTSIDE_SIGNAL_WINDOW"
    if "Point_In_Time_Member" in row.index and not _truthy(row["Point_In_Time_Member"]):
        return False, "NOT_PIT_MEMBER"
    if "Data_Eligible" in row.index and not _truthy(row["Data_Eligible"]):
        return False, "DATA_NOT_ELIGIBLE"
    sigma = row.get("Sigma20", np.nan)
    if not _finite(sigma) or float(sigma) <= 0:
        return False, "INVALID_SIGMA20"
    if not _finite(row.get("Shock_Score", np.nan)) or float(row["Shock_Score"]) > SHOCK_THRESHOLD:
        return False, "SHOCK_THRESHOLD_NOT_MET"
    prior_volume = row.get("Prior20_Median_Volume", np.nan)
    if not _finite(prior_volume) or float(prior_volume) <= 0:
        return False, "INVALID_PRIOR_VOLUME_BASELINE"
    volume_ratio = row.get("Volume_Ratio", np.nan)
    if not _finite(volume_ratio) or float(volume_ratio) > LOW_VOLUME_MAX:
        return False, "VOLUME_THRESHOLD_NOT_MET"
    prior_value = row.get("Prior20_Median_Traded_Value", np.nan)
    if not _finite(prior_value) or float(prior_value) < LIQUIDITY_FLOOR:
        return False, "LIQUIDITY_FLOOR_NOT_MET"
    atr = row.get("ATR14_Signal", row.get("ATR14", np.nan))
    if not _finite(atr) or float(atr) <= 0:
        return False, "INVALID_ATR14"
    return True, ""


def _qualify_control_signal(row: pd.Series) -> tuple[bool, str]:
    """Apply the common rules and high-volume control boundary, without ATR."""

    ok, reason = qualify_low_volume_signal(row)
    if reason == "VOLUME_THRESHOLD_NOT_MET":
        if not _finite(row.get("Volume_Ratio", np.nan)) or float(row["Volume_Ratio"]) < HIGH_VOLUME_MIN:
            return False, "VOLUME_THRESHOLD_NOT_MET"
        ok, reason = _common_signal_qualification(row)
    elif reason == "INVALID_ATR14":
        ok, reason = _common_signal_qualification(row)
    return ok and float(row.get("Volume_Ratio", np.nan)) >= HIGH_VOLUME_MIN, (
        "" if ok else reason
    )


def _common_signal_qualification(row: pd.Series) -> tuple[bool, str]:
    try:
        signal_date = pd.Timestamp(row["Signal_Date"])
    except (KeyError, TypeError, ValueError):
        return False, "INVALID_SIGNAL_DATE"
    if not SIGNAL_START <= signal_date <= SIGNAL_END:
        return False, "OUTSIDE_SIGNAL_WINDOW"
    if "Point_In_Time_Member" in row.index and not _truthy(row["Point_In_Time_Member"]):
        return False, "NOT_PIT_MEMBER"
    if "Data_Eligible" in row.index and not _truthy(row["Data_Eligible"]):
        return False, "DATA_NOT_ELIGIBLE"
    if not _finite(row.get("Sigma20", np.nan)) or float(row["Sigma20"]) <= 0:
        return False, "INVALID_SIGMA20"
    if not _finite(row.get("Shock_Score", np.nan)) or float(row["Shock_Score"]) > SHOCK_THRESHOLD:
        return False, "SHOCK_THRESHOLD_NOT_MET"
    if not _finite(row.get("Prior20_Median_Volume", np.nan)) or float(row["Prior20_Median_Volume"]) <= 0:
        return False, "INVALID_PRIOR_VOLUME_BASELINE"
    if not _finite(row.get("Volume_Ratio", np.nan)):
        return False, "INVALID_VOLUME_RATIO"
    if not _finite(row.get("Prior20_Median_Traded_Value", np.nan)) or float(row["Prior20_Median_Traded_Value"]) < LIQUIDITY_FLOOR:
        return False, "LIQUIDITY_FLOOR_NOT_MET"
    return True, ""


def _bar_on_date(prices: pd.DataFrame, date: pd.Timestamp) -> pd.Series | None:
    if "Date" not in prices.columns:
        return None
    frame = prices.copy()
    dates = pd.to_datetime(frame["Date"], errors="coerce")
    if getattr(dates.dt, "tz", None) is not None:
        dates = dates.dt.tz_localize(None)
    rows = frame.loc[dates.eq(date)]
    if len(rows) != 1:
        return None
    return rows.iloc[0]


def _qualified_rows(signals: pd.DataFrame, cohort: str) -> pd.DataFrame:
    if signals.empty:
        return signals.copy()
    frame = signals.copy()
    if "Cohort" in frame.columns:
        frame = frame.loc[frame["Cohort"].eq(cohort)]
    if "Signal_Qualified" in frame.columns:
        frame = frame.loc[frame["Signal_Qualified"].map(_truthy)]
    return frame.sort_values(["Signal_Date", "Symbol", "Signal_ID"]).reset_index(drop=True)


def _entry_id(signal: pd.Series) -> str:
    signal_id = signal.get("Signal_ID")
    if signal_id is not None and not pd.isna(signal_id):
        return str(signal_id)
    return f"{signal['Symbol']}-{pd.Timestamp(signal['Signal_Date']).date().isoformat()}"


def build_low_volume_entries(
    signals: pd.DataFrame,
    feature_frames: dict[str, pd.DataFrame],
    canonical_sessions: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build accepted low-volume entries and every entry-stage cancellation."""

    accepted: list[dict[str, object]] = []
    cancellations: list[dict[str, object]] = []
    locked_until: dict[str, pd.Timestamp] = {}
    qualified = _qualified_rows(signals, "LOW_VOLUME")
    for _, signal in qualified.iterrows():
        symbol = str(signal["Symbol"])
        signal_date = pd.Timestamp(signal["Signal_Date"])
        entry_id = _entry_id(signal)
        common = {
            "Entry_ID": entry_id,
            "Signal_ID": signal.get("Signal_ID", entry_id),
            "Symbol": symbol,
            "Signal_Date": signal_date,
        }
        unlock = locked_until.get(symbol)
        if unlock is not None and signal_date < unlock:
            cancellations.append({**common, "Cancellation_Reason": "SAME_SYMBOL_LOCKOUT"})
            continue
        entry_date = next_session(signal_date, canonical_sessions)
        if entry_date is None:
            cancellations.append({**common, "Cancellation_Reason": "MISSING_NEXT_SESSION"})
            continue
        prices = feature_frames.get(symbol)
        bar = _bar_on_date(prices, entry_date) if prices is not None else None
        if bar is None or not _finite(bar.get("Open", np.nan)):
            cancellations.append(
                {**common, "Next_Session_Date": entry_date, "Cancellation_Reason": "MISSING_NEXT_SESSION_BAR"}
            )
            continue
        atr = signal.get("ATR14_Signal", signal.get("ATR14", np.nan))
        shock_low = signal.get("Low", np.nan)
        structural_stop = (
            float(shock_low) - STOP_BUFFER_ATR * float(atr)
            if _finite(shock_low) and _finite(atr) and float(atr) > 0
            else np.nan
        )
        entry_open = float(bar["Open"])
        if not _finite(structural_stop) or entry_open <= structural_stop:
            cancellations.append(
                {
                    **common,
                    "Next_Session_Date": entry_date,
                    "Entry_Open": entry_open,
                    "Structural_Stop": structural_stop,
                    "Cancellation_Reason": "OPEN_BELOW_STRUCTURAL_STOP",
                }
            )
            continue
        scheduled_exit = next_session(signal_date, canonical_sessions, 6)
        lockout_until = scheduled_exit if scheduled_exit is not None else pd.Timestamp.max
        locked_until[symbol] = lockout_until
        accepted.append(
            {
                **signal.to_dict(),
                "Entry_ID": entry_id,
                "Entry_Date": entry_date,
                "Entry_Open": entry_open,
                "Structural_Stop": structural_stop,
                "Initial_Risk": entry_open - structural_stop,
                "Scheduled_Exit_Date": scheduled_exit,
            }
        )
    accepted_frame = pd.DataFrame(accepted)
    cancellations_frame = pd.DataFrame(cancellations)
    if not accepted_frame.empty:
        accepted_frame = accepted_frame.sort_values(["Entry_Date", "Symbol", "Entry_ID"]).reset_index(drop=True)
    if not cancellations_frame.empty:
        cancellations_frame = cancellations_frame.sort_values(["Signal_Date", "Symbol", "Entry_ID"]).reset_index(drop=True)
    return accepted_frame, cancellations_frame


def build_control_entries(
    signals: pd.DataFrame,
    feature_frames: dict[str, pd.DataFrame],
    canonical_sessions: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Build independent high-volume control entries without stop mechanics."""

    accepted: list[dict[str, object]] = []
    locked_until: dict[str, pd.Timestamp] = {}
    qualified = _qualified_rows(signals, "HIGH_VOLUME")
    for _, signal in qualified.iterrows():
        symbol = str(signal["Symbol"])
        signal_date = pd.Timestamp(signal["Signal_Date"])
        unlock = locked_until.get(symbol)
        if unlock is not None and signal_date < unlock:
            continue
        entry_date = next_session(signal_date, canonical_sessions)
        if entry_date is None:
            continue
        prices = feature_frames.get(symbol)
        bar = _bar_on_date(prices, entry_date) if prices is not None else None
        if bar is None or not _finite(bar.get("Open", np.nan)):
            continue
        scheduled_exit = next_session(signal_date, canonical_sessions, 6)
        locked_until[symbol] = scheduled_exit if scheduled_exit is not None else pd.Timestamp.max
        accepted.append(
            {
                **signal.to_dict(),
                "Entry_ID": _entry_id(signal),
                "Entry_Date": entry_date,
                "Entry_Open": float(bar["Open"]),
                "Scheduled_Exit_Date": scheduled_exit,
            }
        )
    result = pd.DataFrame(accepted)
    if not result.empty:
        result = result.sort_values(["Entry_Date", "Symbol", "Entry_ID"]).reset_index(drop=True)
    return result


def _build_shock_candidates(
    feature_frames: dict[str, pd.DataFrame],
    membership: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for symbol, frame in sorted(feature_frames.items()):
        if frame.empty:
            continue
        active = frame.get("Point_In_Time_Member")
        if active is None:
            active = frame["Date"].map(
                lambda date: not active_members_on(membership, pd.Timestamp(date))
                .loc[lambda values: values["Symbol"].eq(symbol)]
                .empty
            )
        for _, source in frame.loc[
            frame["Date"].between(SIGNAL_START, SIGNAL_END)
            & frame["Shock_Score"].map(_finite)
            & (pd.to_numeric(frame["Shock_Score"], errors="coerce") <= SHOCK_THRESHOLD)
        ].iterrows():
            point_in_time = bool(active.loc[source.name])
            row = {
                "Signal_ID": f"{symbol}-{pd.Timestamp(source['Date']).date().isoformat()}",
                "Symbol": symbol,
                "Signal_Date": pd.Timestamp(source["Date"]),
                "Open": source.get("Open", np.nan),
                "High": source.get("High", np.nan),
                "Low": source.get("Low", np.nan),
                "Close": source.get("Close", np.nan),
                "Volume": source.get("Volume", np.nan),
                "Return": source.get("Return", np.nan),
                "Sigma20": source.get("Sigma20", np.nan),
                "Shock_Score": source.get("Shock_Score", np.nan),
                "Prior20_Median_Volume": source.get("Prior20_Median_Volume", np.nan),
                "Volume_Ratio": source.get("Volume_Ratio", np.nan),
                "Prior20_Median_Traded_Value": source.get("Prior20_Median_Traded_Value", np.nan),
                "ATR14_Signal": source.get("ATR14", np.nan),
                "Point_In_Time_Member": point_in_time,
            }
            row["Cohort"] = classify_shock_row(pd.Series(row))
            row["Data_Eligible"] = bool(
                _finite(row["Sigma20"])
                and float(row["Sigma20"]) > 0
                and _finite(row["Prior20_Median_Volume"])
                and float(row["Prior20_Median_Volume"]) > 0
                and _finite(row["Volume_Ratio"])
                and _finite(row["Prior20_Median_Traded_Value"])
            )
            row["Liquidity_OK"] = bool(
                _finite(row["Prior20_Median_Traded_Value"])
                and float(row["Prior20_Median_Traded_Value"]) >= LIQUIDITY_FLOOR
            )
            rows.append(row)
    if not rows:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    return pd.DataFrame(rows).sort_values(["Signal_Date", "Symbol"]).reset_index(drop=True)


def _write_frame(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, date_format="%Y-%m-%d")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[4]
    module_dir = Path(__file__).resolve().parent
    output_dir = module_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    membership = load_membership(
        root / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv"
    )
    feature_frames, validation = build_feature_frames(membership)
    validation.to_csv(output_dir / "r1_data_validation.csv", index=False)
    candidates = _build_shock_candidates(feature_frames, membership)
    low_rows = []
    high_rows = []
    for _, row in candidates.iterrows():
        if row["Cohort"] == "LOW_VOLUME":
            ok, _ = qualify_low_volume_signal(row)
            if ok:
                low_rows.append(row.to_dict())
        elif row["Cohort"] == "HIGH_VOLUME":
            ok, _ = _qualify_control_signal(row)
            if ok:
                high_rows.append(row.to_dict())
    low_signals = pd.DataFrame(low_rows, columns=CANDIDATE_COLUMNS)
    high_signals = pd.DataFrame(high_rows, columns=CANDIDATE_COLUMNS)
    extra_dates = pd.DatetimeIndex(
        [
            max(
                (pd.Timestamp(frame["Date"].max()) for frame in feature_frames.values() if not frame.empty),
                default=SIGNAL_END,
            )
        ]
    )
    sessions = load_canonical_market_sessions(
        root / "Swing Trading/nifty500_regime_daily.csv",
        extra_dates=extra_dates,
    )
    entries, cancellations = build_low_volume_entries(low_signals, feature_frames, sessions)
    controls = build_control_entries(high_signals, feature_frames, sessions)
    if len(low_signals) != len(entries) + len(cancellations):
        raise AssertionError("qualified R1 signals do not reconcile to entries and cancellations")
    low_ids = low_signals["Signal_ID"].astype(str)
    outcome_ids = pd.concat(
        [entries.get("Signal_ID", pd.Series(dtype=str)), cancellations.get("Signal_ID", pd.Series(dtype=str))]
    ).astype(str)
    if len(outcome_ids) != len(outcome_ids.unique()) or set(low_ids) != set(outcome_ids):
        raise AssertionError("every qualified R1 signal must have exactly one entry outcome")
    _write_frame(candidates, output_dir / "r1_shock_candidates.csv")
    _write_frame(low_signals, output_dir / "r1_low_volume_signals.csv")
    _write_frame(high_signals, output_dir / "r1_high_volume_control_signals.csv")
    _write_frame(entries, output_dir / "r1_entries.csv")
    _write_frame(cancellations, output_dir / "r1_entry_cancellations.csv")
    print(
        f"symbols={len(feature_frames)} shocks={len(candidates)} low={len(low_signals)} "
        f"high={len(high_signals)} entries={len(entries)} cancellations={len(cancellations)} "
        f"control_entries={len(controls)}"
    )
