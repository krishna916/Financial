"""Independent RR1 evidence and accounting audit."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from constants import (
    ER60_MAX,
    LIQUIDITY_FLOOR,
    MIN_INITIAL_RR,
    SIGNAL_END,
    SIGNAL_START,
    STOP_ATR_BUFFER,
)

AUDIT_COLUMNS = ["Entity", "Check", "Passed", "Observed", "Expected"]


def _normalise(raw: pd.DataFrame) -> pd.DataFrame:
    required = {"Date", "Open", "High", "Low", "Close", "Volume"}
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(f"raw prices missing columns: {sorted(missing)}")
    frame = raw.loc[:, sorted(required)].copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    if getattr(frame["Date"].dt, "tz", None) is not None:
        frame["Date"] = frame["Date"].dt.tz_localize(None)
    frame["Date"] = frame["Date"].dt.normalize()
    if frame["Date"].isna().any() or frame["Date"].duplicated().any():
        raise ValueError("raw prices contain invalid or duplicate dates")
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values("Date").set_index("Date")


def _aligned(raw: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    index = pd.DatetimeIndex(pd.to_datetime(sessions)).normalize()
    return _normalise(raw).reindex(index)


def _session_after(
    date: pd.Timestamp, sessions: pd.DatetimeIndex, steps: int
) -> pd.Timestamp | None:
    index = pd.DatetimeIndex(pd.to_datetime(sessions)).normalize().drop_duplicates().sort_values()
    day = pd.Timestamp(date).normalize()
    if day not in index:
        return None
    position = index.get_loc(day)
    target = int(position) + steps
    return pd.Timestamp(index[target]) if target < len(index) else None


def _wilder(values: pd.Series, period: int = 14) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    result = np.full(len(numeric), np.nan)
    observed: list[float] = []
    previous: float | None = None
    for index, value in enumerate(numeric):
        if not np.isfinite(value):
            continue
        if previous is None:
            observed.append(float(value))
            if len(observed) == period:
                previous = float(np.mean(observed))
                result[index] = previous
        else:
            previous = ((previous * (period - 1)) + float(value)) / period
            result[index] = previous
    return pd.Series(result, index=values.index)


def _same_number(observed: object, expected: object) -> bool:
    try:
        return bool(np.isclose(float(observed), float(expected), rtol=1e-9, atol=1e-12))
    except (TypeError, ValueError):
        return False


def _record(entity: str, check: str, passed: bool, observed: Any, expected: Any) -> dict[str, Any]:
    return {
        "Entity": entity,
        "Check": check,
        "Passed": bool(passed),
        "Observed": observed,
        "Expected": expected,
    }


def _date_text(value: object) -> str:
    if pd.isna(value):
        return "MISSING"
    return str(pd.Timestamp(value).date())


def _membership_on(membership: pd.DataFrame, symbol: str, date: pd.Timestamp) -> bool:
    rows = membership.loc[membership["Symbol"].astype(str).eq(symbol)]
    starts = pd.to_datetime(rows["Member_From"]).dt.normalize()
    ends = pd.to_datetime(rows["Member_To"]).dt.normalize()
    day = pd.Timestamp(date).normalize()
    return bool((starts.le(day) & ends.ge(day)).any())


def audit_lower_entry(
    entry: pd.Series,
    raw_prices: pd.DataFrame,
    membership: pd.DataFrame,
    benchmark: pd.DataFrame,
    sessions: pd.DatetimeIndex,
) -> list[dict[str, Any]]:
    """Recompute lower-entry evidence without calling RR1 eligibility functions."""

    entity = str(entry.get("Entry_ID", entry.get("Signal_ID", "LOWER")))
    signal_date = pd.Timestamp(entry["Signal_Date"]).normalize()
    aligned = _aligned(raw_prices, sessions)
    index = pd.DatetimeIndex(aligned.index)
    checks: list[dict[str, Any]] = []
    signal_present = signal_date in index
    checks.append(
        _record(entity, "SIGNAL_WINDOW", SIGNAL_START <= signal_date <= SIGNAL_END,
                signal_date.date().isoformat(), f"{SIGNAL_START.date()}..{SIGNAL_END.date()}")
    )
    checks.append(
        _record(entity, "PIT_MEMBERSHIP", _membership_on(membership, str(entry["Symbol"]), signal_date),
                str(entry["Symbol"]), "active on Signal_Date")
    )
    position = int(index.get_loc(signal_date)) if signal_present else -1
    history = (
        aligned.iloc[position - 61:position + 1]
        if position >= 61
        else aligned.iloc[0:0]
    )
    exact = len(history) == 62 and history[["Open", "High", "Low", "Close"]].notna().all().all()
    checks.append(_record(entity, "EXACT_PREHISTORY_61", exact, int(exact), 1))
    if position < 61:
        return checks

    prior = aligned.iloc[position - 60:position]
    range_low = float(prior["Low"].min())
    range_high = float(prior["High"].max())
    range_mid = (range_low + range_high) / 2.0
    checks.extend(
        [
            _record(entity, "RANGE_LOW_RECOMPUTE", _same_number(entry["Range_Low"], range_low),
                    entry.get("Range_Low"), range_low),
            _record(entity, "RANGE_HIGH_RECOMPUTE", _same_number(entry["Range_High"], range_high),
                    entry.get("Range_High"), range_high),
            _record(entity, "RANGE_MID_RECOMPUTE", _same_number(entry["Target"], range_mid),
                    entry.get("Target"), range_mid),
        ]
    )
    close = aligned["Close"]
    numerator = abs(float(close.iloc[position - 1]) - float(close.iloc[position - 61]))
    denominator = float(
        close.iloc[position - 61:position].diff().abs().iloc[1:].sum()
    )
    er = numerator / denominator if denominator > 0.0 else np.nan
    er_observed = entry.get("ER60", er)
    checks.append(_record(
        entity,
        "ER60_RECOMPUTE",
        _same_number(er_observed, er) and np.isfinite(er) and er <= ER60_MAX,
        er_observed,
        er,
    ))
    traded = aligned["Close"] * aligned["Volume"]
    liquidity = float(traded.iloc[position - 20:position].median())
    checks.append(_record(entity, "LIQUIDITY_RECOMPUTE",
                          _same_number(entry.get("Prior20_Median_Traded_Value", liquidity), liquidity)
                          and liquidity >= LIQUIDITY_FLOOR,
                          entry.get("Prior20_Median_Traded_Value"), liquidity))
    signal_bar = aligned.iloc[position]
    lower = float(signal_bar["Low"]) < range_low and float(signal_bar["Close"]) > range_low
    checks.append(_record(entity, "LOWER_SIGNAL", lower, lower, True))

    previous_close = aligned["Close"].shift(1)
    tr = pd.concat(
        [
            aligned["High"] - aligned["Low"],
            (aligned["High"] - previous_close).abs(),
            (aligned["Low"] - previous_close).abs(),
        ], axis=1,
    ).max(axis=1, skipna=True)
    atr = float(_wilder(tr).iloc[position])
    stop = float(signal_bar["Low"]) - STOP_ATR_BUFFER * atr
    checks.extend(
        [
            _record(entity, "ATR14_RECOMPUTE", _same_number(entry.get("ATR14_Signal"), atr),
                    entry.get("ATR14_Signal"), atr),
            _record(entity, "STRUCTURAL_STOP_RECOMPUTE",
                    _same_number(entry.get("Structural_Stop"), stop), entry.get("Structural_Stop"), stop),
        ]
    )
    expected_entry_date = _session_after(signal_date, index, 1)
    checks.append(_record(entity, "IMMEDIATE_NEXT_SESSION_ENTRY",
                          expected_entry_date is not None
                          and pd.Timestamp(entry["Entry_Date"]).normalize() == expected_entry_date,
                          _date_text(entry["Entry_Date"]),
                          str(expected_entry_date.date()) if expected_entry_date is not None else "MISSING"))
    entry_date = pd.Timestamp(entry["Entry_Date"]).normalize()
    entry_bar = aligned.loc[entry_date] if entry_date in aligned.index else None
    entry_bar_ok = entry_bar is not None and entry_bar[["Open", "High", "Low", "Close"]].notna().all()
    actual_entry_open = float(entry_bar["Open"]) if entry_bar_ok else np.nan
    checks.append(_record(entity, "ENTRY_OPEN_RECOMPUTE",
                          entry_bar_ok and _same_number(entry.get("Entry_Open"), actual_entry_open),
                          entry.get("Entry_Open"), actual_entry_open))
    target = float(entry.get("Target", np.nan))
    entry_open = float(entry.get("Entry_Open", np.nan))
    risk = entry_open - stop
    reward = target - entry_open
    initial_rr = reward / risk if risk > 0.0 else np.nan
    checks.extend(
        [
            _record(entity, "SIGNAL_BELOW_TARGET", float(signal_bar["Close"]) < target,
                    signal_bar["Close"], f"< {target}"),
            _record(entity, "ENTRY_BOUNDS", stop < entry_open < target,
                    entry_open, f"{stop} < Entry_Open < {target}"),
            _record(entity, "INITIAL_RISK_RECOMPUTE", _same_number(entry.get("Initial_Risk"), risk),
                    entry.get("Initial_Risk"), risk),
            _record(entity, "REWARD_RECOMPUTE", _same_number(entry.get("Reward"), reward),
                    entry.get("Reward"), reward),
            _record(entity, "INITIAL_RR_RECOMPUTE",
                    _same_number(entry.get("Initial_RR"), initial_rr) and initial_rr >= MIN_INITIAL_RR,
                    entry.get("Initial_RR"), initial_rr),
        ]
    )
    expected_exit = _session_after(signal_date, index, 16)
    checks.append(_record(entity, "SCHEDULED_T16",
                          (expected_exit is None and pd.isna(entry["Scheduled_Exit_Date"]))
                          or (expected_exit is not None
                              and pd.Timestamp(entry["Scheduled_Exit_Date"]).normalize() == expected_exit),
                          _date_text(entry["Scheduled_Exit_Date"]),
                          str(expected_exit.date()) if expected_exit is not None else "MISSING"))
    benchmark_aligned = _aligned(benchmark, sessions)
    benchmark_dates_ok = True if expected_exit is None else (
        entry_date in benchmark_aligned.index
        and expected_exit in benchmark_aligned.index
        and pd.notna(benchmark_aligned.loc[entry_date, "Open"])
        and pd.notna(benchmark_aligned.loc[expected_exit, "Open"])
    )
    checks.append(_record(entity, "BENCHMARK_EVIDENCE", benchmark_dates_ok,
                          str(entry_date.date()), str(expected_exit.date()) if expected_exit is not None else "MISSING"))
    return checks


def audit_upper_reference(
    reference: pd.Series,
    raw_prices: pd.DataFrame,
    membership: pd.DataFrame,
    sessions: pd.DatetimeIndex,
) -> list[dict[str, Any]]:
    entity = str(reference.get("Reference_ID", reference.get("Signal_ID", "UPPER")))
    aligned = _aligned(raw_prices, sessions)
    signal_date = pd.Timestamp(reference["Signal_Date"]).normalize()
    index = pd.DatetimeIndex(aligned.index)
    checks: list[dict[str, Any]] = [
        _record(entity, "SIGNAL_WINDOW", SIGNAL_START <= signal_date <= SIGNAL_END,
                signal_date.date().isoformat(), f"{SIGNAL_START.date()}..{SIGNAL_END.date()}"),
        _record(entity, "PIT_MEMBERSHIP", _membership_on(membership, str(reference["Symbol"]), signal_date),
                str(reference["Symbol"]), "active on Signal_Date"),
    ]
    if signal_date not in index:
        checks.append(_record(entity, "EXACT_PREHISTORY_61", False, 0, 1))
        return checks
    position = int(index.get_loc(signal_date))
    history = aligned.iloc[max(0, position - 61):position + 1]
    checks.append(_record(entity, "EXACT_PREHISTORY_61",
                          len(history) == 62 and history[["Open", "High", "Low", "Close"]].notna().all().all(),
                          len(history), 62))
    if position < 61:
        return checks
    prior = aligned.iloc[position - 60:position]
    high = float(prior["High"].max())
    signal_bar = aligned.iloc[position]
    checks.append(_record(entity, "UPPER_SIGNAL",
                          float(signal_bar["High"]) > high and float(signal_bar["Close"]) < high,
                          [signal_bar["High"], signal_bar["Close"]], f"High>{high}, Close<{high}"))
    expected_entry = _session_after(signal_date, index, 1)
    expected_exit = _session_after(signal_date, index, 16)
    checks.append(_record(entity, "IMMEDIATE_NEXT_SESSION_ENTRY",
                          expected_entry is not None and pd.Timestamp(reference["Entry_Date"]).normalize() == expected_entry,
                          str(pd.Timestamp(reference["Entry_Date"]).date()),
                          str(expected_entry.date()) if expected_entry is not None else "MISSING"))
    checks.append(_record(entity, "SCHEDULED_T16",
                          expected_exit is not None and pd.Timestamp(reference["Scheduled_Exit_Date"]).normalize() == expected_exit,
                          str(pd.Timestamp(reference["Scheduled_Exit_Date"]).date()),
                          str(expected_exit.date()) if expected_exit is not None else "MISSING"))
    return checks


def accounting_invariants(
    lower_signals: pd.DataFrame,
    lower_entries: pd.DataFrame,
    lower_cancellations: pd.DataFrame,
    lens_a: pd.DataFrame,
    practical: pd.DataFrame,
    upper_signals: pd.DataFrame,
    upper_refs: pd.DataFrame,
    upper_cancellations: pd.DataFrame,
    upper_outcomes: pd.DataFrame,
    diagnostics: pd.DataFrame,
) -> dict[str, bool]:
    lower_incomplete = int(
        ((diagnostics.get("Entry_ID", pd.Series(dtype=str)).astype(str).ne(""))
         & ~diagnostics.get("Primary_Complete", pd.Series(dtype=bool)).astype(bool)).sum()
    )
    upper_incomplete = int(
        ((diagnostics.get("Reference_ID", pd.Series(dtype=str)).astype(str).ne(""))
         & ~diagnostics.get("Primary_Complete", pd.Series(dtype=bool)).astype(bool)).sum()
    )
    lower_ids = lower_signals.get("Signal_ID", pd.Series(dtype=str))
    upper_ids = upper_signals.get("Signal_ID", pd.Series(dtype=str))
    lower_accounting = len(lower_ids) == len(lower_entries) + len(lower_cancellations)
    upper_accounting = len(upper_ids) == len(upper_refs) + len(upper_cancellations)
    return {
        "LOWER_SIGNAL_ACCOUNTING": lower_accounting
        and len(set(lower_ids)) == len(lower_ids)
        and len(set(lower_entries.get("Signal_ID", pd.Series(dtype=str)))
                | set(lower_cancellations.get("Signal_ID", pd.Series(dtype=str)))) == len(lower_ids),
        "LOWER_ACCEPTED_ACCOUNTING": len(lower_entries) == len(lens_a) + lower_incomplete,
        "UPPER_SIGNAL_ACCOUNTING": upper_accounting
        and len(set(upper_ids)) == len(upper_ids)
        and len(set(upper_refs.get("Signal_ID", pd.Series(dtype=str)))
                | set(upper_cancellations.get("Signal_ID", pd.Series(dtype=str)))) == len(upper_ids),
        "UPPER_ACCEPTED_ACCOUNTING": len(upper_refs) == len(upper_outcomes) + upper_incomplete,
        "PAIRED_IDS_MATCH": set(lens_a.get("Entry_ID", pd.Series(dtype=str)))
        == set(practical.get("Entry_ID", pd.Series(dtype=str))),
    }


def run_integrity_audit(
    lower_entries: pd.DataFrame,
    upper_refs: pd.DataFrame,
    lower_signals: pd.DataFrame,
    upper_signals: pd.DataFrame,
    lower_cancellations: pd.DataFrame,
    upper_cancellations: pd.DataFrame,
    lens_a: pd.DataFrame,
    practical: pd.DataFrame,
    upper_outcomes: pd.DataFrame,
    diagnostics: pd.DataFrame,
    raw_prices: dict[str, pd.DataFrame],
    membership: pd.DataFrame,
    benchmark: pd.DataFrame,
    sessions: pd.DatetimeIndex,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, entry in lower_entries.iterrows():
        rows.extend(audit_lower_entry(entry, raw_prices[str(entry["Symbol"])], membership, benchmark, sessions))
    for _, reference in upper_refs.iterrows():
        rows.extend(audit_upper_reference(reference, raw_prices[str(reference["Symbol"])], membership, sessions))
    for name, passed in accounting_invariants(
        lower_signals, lower_entries, lower_cancellations, lens_a, practical,
        upper_signals, upper_refs, upper_cancellations, upper_outcomes, diagnostics,
    ).items():
        rows.append(_record("GLOBAL", name, passed, passed, True))
    if not lens_a.empty and not practical.empty:
        rows.append(_record("GLOBAL", "LENS_A_LENS_B_COMPLETED_IDS",
                            set(lens_a["Entry_ID"]) == set(practical["Entry_ID"]),
                            sorted(lens_a["Entry_ID"]), sorted(practical["Entry_ID"])))
    return pd.DataFrame(rows, columns=AUDIT_COLUMNS)
