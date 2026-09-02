"""Independent RR1 evidence and accounting audit."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from constants import (
    BASE_FRICTION,
    ER60_MAX,
    LIQUIDITY_FLOOR,
    MIN_INITIAL_RR,
    SEVERE_FRICTION,
    SIGNAL_END,
    SIGNAL_START,
    STRESS_FRICTION,
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
    if value is None or pd.isna(value):
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
    range_low = float(prior["Low"].min())
    range_high = float(prior["High"].max())
    range_ok = np.isfinite(range_low) and np.isfinite(range_high) and range_high > range_low
    checks.append(_record(
        entity,
        "UPPER_RANGE_QUALIFICATION",
        range_ok,
        [range_low, range_high],
        "finite Range_High > Range_Low from T-60..T-1",
    ))
    close = aligned["Close"]
    numerator = abs(float(close.iloc[position - 1]) - float(close.iloc[position - 61]))
    denominator = float(close.iloc[position - 61:position].diff().abs().iloc[1:].sum())
    er60 = numerator / denominator if denominator > 0.0 else np.nan
    checks.append(_record(
        entity,
        "UPPER_ER60_QUALIFICATION",
        np.isfinite(er60) and denominator > 0.0 and er60 <= ER60_MAX,
        er60,
        f"ER60 <= {ER60_MAX}",
    ))
    traded_value = aligned["Close"] * aligned["Volume"]
    liquidity = float(traded_value.iloc[position - 20:position].median())
    checks.append(_record(
        entity,
        "UPPER_LIQUIDITY_QUALIFICATION",
        np.isfinite(liquidity) and liquidity >= LIQUIDITY_FLOOR,
        liquidity,
        f">= {LIQUIDITY_FLOOR}",
    ))
    signal_bar = aligned.iloc[position]
    checks.append(_record(entity, "UPPER_SIGNAL",
                          range_ok
                          and float(signal_bar["High"]) > range_high
                          and float(signal_bar["Close"]) < range_high,
                          [signal_bar["High"], signal_bar["Close"]],
                          f"High>{range_high}, Close<{range_high}"))
    expected_entry = _session_after(signal_date, index, 1)
    expected_exit = _session_after(signal_date, index, 16)
    checks.append(_record(entity, "IMMEDIATE_NEXT_SESSION_ENTRY",
                          expected_entry is not None and pd.Timestamp(reference["Entry_Date"]).normalize() == expected_entry,
                          str(pd.Timestamp(reference["Entry_Date"]).date()),
                          str(expected_entry.date()) if expected_entry is not None else "MISSING"))
    entry_bar = aligned.loc[expected_entry] if expected_entry is not None and expected_entry in aligned.index else None
    entry_bar_ok = (
        entry_bar is not None
        and entry_bar[["Open", "High", "Low", "Close"]].notna().all()
    )
    actual_entry_open = float(entry_bar["Open"]) if entry_bar_ok else np.nan
    checks.append(_record(
        entity,
        "UPPER_ENTRY_OPEN_RECOMPUTE",
        entry_bar_ok and _same_number(reference.get("Entry_Open"), actual_entry_open),
        reference.get("Entry_Open"),
        actual_entry_open,
    ))
    checks.append(_record(entity, "SCHEDULED_T16",
                          (expected_exit is None and pd.isna(reference["Scheduled_Exit_Date"]))
                          or (expected_exit is not None
                              and pd.Timestamp(reference["Scheduled_Exit_Date"]).normalize() == expected_exit),
                          str(pd.Timestamp(reference["Scheduled_Exit_Date"]).date()),
                          str(expected_exit.date()) if expected_exit is not None else "MISSING"))
    return checks


def audit_upper_outcome(
    reference: pd.Series,
    outcome: pd.Series,
    raw_prices: pd.DataFrame,
    sessions: pd.DatetimeIndex,
) -> list[dict[str, Any]]:
    """Recompute upper fixed-horizon outcome evidence from raw prices."""

    entity = str(reference["Reference_ID"])
    aligned = _aligned(raw_prices, sessions)
    index = pd.DatetimeIndex(aligned.index)
    signal_date = pd.Timestamp(reference["Signal_Date"]).normalize()
    expected_entry = _session_after(signal_date, index, 1)
    expected_exit = _session_after(signal_date, index, 16)
    checks: list[dict[str, Any]] = []

    entry_bar = aligned.loc[expected_entry] if expected_entry is not None and expected_entry in aligned.index else None
    exit_bar = aligned.loc[expected_exit] if expected_exit is not None and expected_exit in aligned.index else None
    bars_ok = (
        entry_bar is not None
        and exit_bar is not None
        and entry_bar[["Open", "High", "Low", "Close"]].notna().all()
        and exit_bar[["Open", "High", "Low", "Close"]].notna().all()
    )
    expected_entry_open = float(entry_bar["Open"]) if bars_ok else np.nan
    expected_exit_open = float(exit_bar["Open"]) if bars_ok else np.nan
    expected_return = (
        expected_exit_open / expected_entry_open - 1.0
        if bars_ok and expected_entry_open != 0.0
        else np.nan
    )

    checks.extend(
        [
            _record(
                entity,
                "UPPER_OUTCOME_ENTRY_DATE",
                expected_entry is not None
                and pd.Timestamp(outcome["Entry_Date"]).normalize() == expected_entry,
                _date_text(outcome["Entry_Date"]),
                _date_text(expected_entry),
            ),
            _record(
                entity,
                "UPPER_OUTCOME_EXIT_DATE",
                expected_exit is not None
                and pd.Timestamp(outcome["Exit_Date"]).normalize() == expected_exit,
                _date_text(outcome["Exit_Date"]),
                _date_text(expected_exit),
            ),
            _record(
                entity,
                "UPPER_OUTCOME_ENTRY_OPEN",
                bars_ok and _same_number(outcome.get("Entry_Open"), expected_entry_open),
                outcome.get("Entry_Open"),
                expected_entry_open,
            ),
            _record(
                entity,
                "UPPER_OUTCOME_EXIT_OPEN",
                bars_ok and _same_number(outcome.get("Exit_Price"), expected_exit_open),
                outcome.get("Exit_Price"),
                expected_exit_open,
            ),
            _record(
                entity,
                "UPPER_OUTCOME_GROSS_RETURN",
                bars_ok and _same_number(outcome.get("Mirror_Gross_Return_15"), expected_return),
                outcome.get("Mirror_Gross_Return_15"),
                expected_return,
            ),
        ]
    )
    return checks


def audit_cohort_lockout(
    signals: pd.DataFrame,
    accepted: pd.DataFrame,
    cancellations: pd.DataFrame,
    sessions: pd.DatetimeIndex,
    cohort: str,
) -> list[dict[str, Any]]:
    """Replay same-symbol lockouts independently for one signal cohort."""

    if cohort not in {"LOWER", "UPPER"}:
        raise ValueError("cohort must be LOWER or UPPER")

    accepted_by_id = {
        str(row.Signal_ID): row
        for row in accepted.itertuples(index=False)
    }
    cancelled_by_id = {
        str(row.Signal_ID): str(row.Cancellation_Reason)
        for row in cancellations.itertuples(index=False)
    }
    lockout_until: dict[str, pd.Timestamp] = {}
    rows: list[dict[str, Any]] = []
    ordered = signals.copy()
    ordered["Signal_Date"] = pd.to_datetime(ordered["Signal_Date"]).dt.normalize()
    ordered = ordered.sort_values(["Signal_Date", "Symbol", "Signal_ID"])

    for signal in ordered.itertuples(index=False):
        signal_id = str(signal.Signal_ID)
        symbol = str(signal.Symbol)
        signal_date = pd.Timestamp(signal.Signal_Date).normalize()
        active_until = lockout_until.get(symbol)
        inside_lockout = active_until is not None and signal_date < active_until
        accepted_row = accepted_by_id.get(signal_id)
        cancellation_reason = cancelled_by_id.get(signal_id)

        if inside_lockout:
            passed = accepted_row is None and cancellation_reason == "SAME_SYMBOL_LOCKOUT"
            expected = f"cancel SAME_SYMBOL_LOCKOUT before {active_until.date()}"
        else:
            passed = cancellation_reason != "SAME_SYMBOL_LOCKOUT"
            expected = "not cancelled as SAME_SYMBOL_LOCKOUT outside active window"

        rows.append(
            _record(
                f"{cohort}|{signal_id}",
                f"{cohort}_LOCKOUT_REPLAY",
                passed,
                cancellation_reason if accepted_row is None else "ACCEPTED",
                expected,
            )
        )

        if not inside_lockout and accepted_row is not None:
            expected_exit = _session_after(signal_date, sessions, 16)
            stored_exit = getattr(accepted_row, "Scheduled_Exit_Date")
            exit_matches = (
                (expected_exit is None and pd.isna(stored_exit))
                or (
                    expected_exit is not None
                    and not pd.isna(stored_exit)
                    and pd.Timestamp(stored_exit).normalize() == expected_exit
                )
            )
            rows.append(
                _record(
                    f"{cohort}|{signal_id}",
                    f"{cohort}_LOCKOUT_SCHEDULED_T16",
                    exit_matches,
                    _date_text(stored_exit),
                    _date_text(expected_exit),
                )
            )
            lockout_until[symbol] = expected_exit or pd.Timestamp.max

    return rows


def audit_lens_a_outcome(
    entry: pd.Series,
    outcome: pd.Series,
    raw_prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    sessions: pd.DatetimeIndex,
) -> list[dict[str, Any]]:
    """Recompute fixed-horizon stock and benchmark returns from raw Opens."""

    entity = str(entry["Entry_ID"])
    stock = _aligned(raw_prices, sessions)
    benchmark_aligned = _aligned(benchmark, sessions)
    index = pd.DatetimeIndex(stock.index)
    signal_date = pd.Timestamp(entry["Signal_Date"]).normalize()
    expected_entry = _session_after(signal_date, index, 1)
    expected_exit = _session_after(signal_date, index, 16)

    entry_bar = stock.loc[expected_entry] if expected_entry is not None and expected_entry in stock.index else None
    exit_bar = stock.loc[expected_exit] if expected_exit is not None and expected_exit in stock.index else None
    stock_bars_ok = (
        entry_bar is not None
        and exit_bar is not None
        and entry_bar[["Open", "High", "Low", "Close"]].notna().all()
        and exit_bar[["Open", "High", "Low", "Close"]].notna().all()
    )
    expected_entry_open = float(entry_bar["Open"]) if stock_bars_ok else np.nan
    expected_exit_open = float(exit_bar["Open"]) if stock_bars_ok else np.nan
    expected_gross = (
        expected_exit_open / expected_entry_open - 1.0
        if stock_bars_ok and expected_entry_open != 0.0
        else np.nan
    )

    benchmark_bars_ok = (
        expected_entry is not None
        and expected_exit is not None
        and expected_entry in benchmark_aligned.index
        and expected_exit in benchmark_aligned.index
        and benchmark_aligned.loc[expected_entry, "Open"] == benchmark_aligned.loc[expected_entry, "Open"]
        and benchmark_aligned.loc[expected_exit, "Open"] == benchmark_aligned.loc[expected_exit, "Open"]
    )
    benchmark_entry_open = (
        float(benchmark_aligned.loc[expected_entry, "Open"])
        if benchmark_bars_ok
        else np.nan
    )
    benchmark_exit_open = (
        float(benchmark_aligned.loc[expected_exit, "Open"])
        if benchmark_bars_ok
        else np.nan
    )
    expected_benchmark = (
        benchmark_exit_open / benchmark_entry_open - 1.0
        if benchmark_bars_ok and benchmark_entry_open != 0.0
        else np.nan
    )
    expected_base_net = expected_gross - BASE_FRICTION
    expected_stress_net = expected_gross - STRESS_FRICTION
    expected_severe_net = expected_gross - SEVERE_FRICTION
    expected_base_excess = expected_base_net - expected_benchmark

    checks = [
        _record(
            entity,
            "LENS_A_ENTRY_DATE",
            expected_entry is not None
            and pd.Timestamp(outcome["Entry_Date"]).normalize() == expected_entry,
            _date_text(outcome.get("Entry_Date")),
            _date_text(expected_entry),
        ),
        _record(
            entity,
            "LENS_A_EXIT_DATE",
            expected_exit is not None
            and pd.Timestamp(outcome["Exit_Date"]).normalize() == expected_exit,
            _date_text(outcome.get("Exit_Date")),
            _date_text(expected_exit),
        ),
        _record(
            entity,
            "LENS_A_ENTRY_OPEN",
            stock_bars_ok and _same_number(outcome.get("Entry_Open"), expected_entry_open),
            outcome.get("Entry_Open"),
            expected_entry_open,
        ),
        _record(
            entity,
            "LENS_A_EXIT_OPEN",
            stock_bars_ok and _same_number(outcome.get("Exit_Price"), expected_exit_open),
            outcome.get("Exit_Price"),
            expected_exit_open,
        ),
        _record(
            entity,
            "LENS_A_GROSS_RETURN",
            stock_bars_ok and _same_number(outcome.get("Gross_Return"), expected_gross),
            outcome.get("Gross_Return"),
            expected_gross,
        ),
        _record(
            entity,
            "LENS_A_BASE_NET_RETURN",
            stock_bars_ok and _same_number(outcome.get("Base_Net_Return"), expected_base_net),
            outcome.get("Base_Net_Return"),
            expected_base_net,
        ),
        _record(
            entity,
            "LENS_A_STRESS_NET_RETURN",
            stock_bars_ok and _same_number(outcome.get("Stress_Net_Return"), expected_stress_net),
            outcome.get("Stress_Net_Return"),
            expected_stress_net,
        ),
        _record(
            entity,
            "LENS_A_SEVERE_NET_RETURN",
            stock_bars_ok and _same_number(outcome.get("Severe_Net_Return"), expected_severe_net),
            outcome.get("Severe_Net_Return"),
            expected_severe_net,
        ),
        _record(
            entity,
            "LENS_A_BENCHMARK_RETURN",
            benchmark_bars_ok and _same_number(outcome.get("Benchmark_Return"), expected_benchmark),
            outcome.get("Benchmark_Return"),
            expected_benchmark,
        ),
        _record(
            entity,
            "LENS_A_BASE_EXCESS_RETURN",
            stock_bars_ok and benchmark_bars_ok
            and _same_number(outcome.get("Base_Excess_Return"), expected_base_excess),
            outcome.get("Base_Excess_Return"),
            expected_base_excess,
        ),
    ]
    return checks


def _recompute_practical_outcome(
    entry: pd.Series,
    raw_prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    sessions: pd.DatetimeIndex,
) -> dict[str, object] | None:
    """Replay practical execution without calling production simulation code."""

    stock = _aligned(raw_prices, sessions)
    benchmark_aligned = _aligned(benchmark, sessions)
    index = pd.DatetimeIndex(stock.index)
    entry_date = pd.Timestamp(entry["Entry_Date"]).normalize()
    scheduled_value = entry.get("Scheduled_Exit_Date")
    if pd.isna(scheduled_value):
        return None
    scheduled_exit = pd.Timestamp(scheduled_value).normalize()
    if entry_date not in index or scheduled_exit not in index:
        return None
    entry_position = int(index.get_loc(entry_date))
    exit_position = int(index.get_loc(scheduled_exit))
    if exit_position <= entry_position:
        return None

    entry_bar = stock.loc[entry_date]
    if not entry_bar[["Open", "High", "Low", "Close"]].notna().all():
        return None
    entry_open = float(entry_bar["Open"])
    stop = float(entry["Structural_Stop"])
    target = float(entry["Target"])
    initial_risk = float(entry["Initial_Risk"])
    if not all(np.isfinite(value) for value in [entry_open, stop, target, initial_risk]) or initial_risk == 0.0:
        return None

    exit_date: pd.Timestamp | None = None
    exit_price = np.nan
    exit_reason: str | None = None
    ambiguity = False
    for position in range(entry_position, exit_position):
        date = pd.Timestamp(index[position])
        bar = stock.loc[date]
        if not bar[["Open", "High", "Low", "Close"]].notna().all():
            return None
        open_price = float(bar["Open"])
        high = float(bar["High"])
        low = float(bar["Low"])

        if open_price <= stop:
            exit_date = date
            exit_price = open_price
            exit_reason = "GAP_BELOW_STRUCTURAL_STOP" if date != entry_date else "STRUCTURAL_STOP"
            ambiguity = False
            break

        if open_price >= target:
            exit_date = date
            exit_price = open_price
            exit_reason = "GAP_ABOVE_TARGET" if date != entry_date else "TARGET"
            ambiguity = False
            break

        stop_touched = low <= stop
        target_touched = high >= target
        if stop_touched:
            exit_date = date
            exit_price = stop
            exit_reason = "STRUCTURAL_STOP"
            ambiguity = bool(target_touched)
            break

        if target_touched:
            exit_date = date
            exit_price = target
            exit_reason = "MIDPOINT_TARGET"
            ambiguity = False
            break
    else:
        scheduled_bar = stock.loc[scheduled_exit]
        if not scheduled_bar[["Open", "High", "Low", "Close"]].notna().all():
            return None
        exit_date = scheduled_exit
        exit_price = float(scheduled_bar["Open"])
        exit_reason = "TIME_EXIT"
        ambiguity = False

    if exit_date is None or exit_reason is None or not np.isfinite(exit_price):
        return None
    benchmark_entry_bar = benchmark_aligned.loc[entry_date] if entry_date in benchmark_aligned.index else None
    benchmark_exit_bar = benchmark_aligned.loc[exit_date] if exit_date in benchmark_aligned.index else None
    if benchmark_entry_bar is None or benchmark_exit_bar is None:
        return None
    benchmark_entry_open = benchmark_entry_bar["Open"]
    benchmark_exit_open = benchmark_exit_bar["Open"]
    if pd.isna(benchmark_entry_open) or pd.isna(benchmark_exit_open):
        return None
    benchmark_entry_open = float(benchmark_entry_open)
    benchmark_exit_open = float(benchmark_exit_open)
    if not np.isfinite(benchmark_entry_open) or not np.isfinite(benchmark_exit_open) or benchmark_entry_open == 0.0:
        return None

    gross_return = exit_price / entry_open - 1.0
    base_net_return = gross_return - BASE_FRICTION
    stress_net_return = gross_return - STRESS_FRICTION
    severe_net_return = gross_return - SEVERE_FRICTION
    gross_r = (exit_price - entry_open) / initial_risk
    base_net_r = gross_r - BASE_FRICTION * entry_open / initial_risk
    stress_net_r = gross_r - STRESS_FRICTION * entry_open / initial_risk
    severe_net_r = gross_r - SEVERE_FRICTION * entry_open / initial_risk
    benchmark_return = benchmark_exit_open / benchmark_entry_open - 1.0

    return {
        "Entry_ID": entry["Entry_ID"],
        "Symbol": entry["Symbol"],
        "Signal_Date": pd.Timestamp(entry["Signal_Date"]),
        "Entry_Date": entry_date,
        "Exit_Date": exit_date,
        "Entry_Open": entry_open,
        "Exit_Price": exit_price,
        "Exit_Reason": exit_reason,
        "Initial_Risk": initial_risk,
        "Target": target,
        "Structural_Stop": stop,
        "Gross_Return": gross_return,
        "Base_Net_Return": base_net_return,
        "Stress_Net_Return": stress_net_return,
        "Severe_Net_Return": severe_net_return,
        "Gross_R": gross_r,
        "Base_Net_R": base_net_r,
        "Stress_Net_R": stress_net_r,
        "Severe_Net_R": severe_net_r,
        "Benchmark_Return": benchmark_return,
        "Base_Practical_Excess_Return": base_net_return - benchmark_return,
        "Stress_Practical_Excess_Return": stress_net_return - benchmark_return,
        "Severe_Practical_Excess_Return": severe_net_return - benchmark_return,
        "Same_Bar_Stop_Target_Ambiguity": bool(ambiguity),
    }


def audit_practical_outcome(
    entry: pd.Series,
    outcome: pd.Series,
    raw_prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    sessions: pd.DatetimeIndex,
) -> list[dict[str, Any]]:
    """Compare persisted practical execution fields with an independent replay."""

    entity = str(entry["Entry_ID"])
    expected = _recompute_practical_outcome(entry, raw_prices, benchmark, sessions)
    if expected is None:
        return [_record(entity, "PRACTICAL_OUTCOME_RECOMPUTE", False, "unavailable", "complete raw replay")]

    date_fields = ["Entry_Date", "Exit_Date"]
    numeric_fields = [
        "Entry_Open",
        "Exit_Price",
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
    ]
    checks: list[dict[str, Any]] = []
    for field in date_fields:
        checks.append(
            _record(
                entity,
                f"PRACTICAL_{field.upper()}",
                pd.Timestamp(outcome.get(field)).normalize() == pd.Timestamp(expected[field]).normalize(),
                _date_text(outcome.get(field)),
                _date_text(expected[field]),
            )
        )
    checks.extend(
        [
            _record(entity, "PRACTICAL_ENTRY_OPEN", _same_number(outcome.get("Entry_Open"), expected["Entry_Open"]), outcome.get("Entry_Open"), expected["Entry_Open"]),
            _record(entity, "PRACTICAL_EXIT_PRICE", _same_number(outcome.get("Exit_Price"), expected["Exit_Price"]), outcome.get("Exit_Price"), expected["Exit_Price"]),
            _record(entity, "PRACTICAL_EXIT_REASON", outcome.get("Exit_Reason") == expected["Exit_Reason"], outcome.get("Exit_Reason"), expected["Exit_Reason"]),
        ]
    )
    for field in numeric_fields[2:]:
        checks.append(
            _record(
                entity,
                f"PRACTICAL_{field.upper()}",
                _same_number(outcome.get(field), expected[field]),
                outcome.get(field),
                expected[field],
            )
        )
    observed_ambiguity = outcome.get("Same_Bar_Stop_Target_Ambiguity")
    ambiguity_passed = (
        isinstance(observed_ambiguity, (bool, np.bool_))
        and bool(observed_ambiguity) == bool(expected["Same_Bar_Stop_Target_Ambiguity"])
    )
    checks.append(
        _record(
            entity,
            "PRACTICAL_SAME_BAR_AMBIGUITY",
            ambiguity_passed,
            observed_ambiguity,
            expected["Same_Bar_Stop_Target_Ambiguity"],
        )
    )
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
    rows.extend(
        audit_cohort_lockout(
            lower_signals,
            lower_entries,
            lower_cancellations,
            sessions,
            "LOWER",
        )
    )
    rows.extend(
        audit_cohort_lockout(
            upper_signals,
            upper_refs,
            upper_cancellations,
            sessions,
            "UPPER",
        )
    )

    entry_by_id = {
        str(row.Entry_ID): pd.Series(row._asdict())
        for row in lower_entries.itertuples(index=False)
    }
    lens_a_by_id = {
        str(row.Entry_ID): pd.Series(row._asdict())
        for row in lens_a.itertuples(index=False)
    }
    practical_by_id = {
        str(row.Entry_ID): pd.Series(row._asdict())
        for row in practical.itertuples(index=False)
    }
    for entry_id in sorted(set(lens_a_by_id) | set(practical_by_id)):
        entry = entry_by_id.get(entry_id)
        lens_row = lens_a_by_id.get(entry_id)
        practical_row = practical_by_id.get(entry_id)
        if entry is None or lens_row is None or practical_row is None:
            rows.append(
                _record(
                    entry_id,
                    "COMPLETED_LOWER_OUTCOME_EVIDENCE",
                    False,
                    {
                        "entry": entry is not None,
                        "lens_a": lens_row is not None,
                        "practical": practical_row is not None,
                    },
                    "entry + Lens A + practical rows all present",
                )
            )
            continue
        symbol_prices = raw_prices[str(entry["Symbol"])]
        rows.extend(audit_lens_a_outcome(entry, lens_row, symbol_prices, benchmark, sessions))
        rows.extend(audit_practical_outcome(entry, practical_row, symbol_prices, benchmark, sessions))

    reference_by_id = {
        str(row.Reference_ID): pd.Series(row._asdict())
        for row in upper_refs.itertuples(index=False)
    }
    for row in upper_outcomes.itertuples(index=False):
        outcome = pd.Series(row._asdict())
        reference_id = str(outcome["Reference_ID"])
        reference = reference_by_id.get(reference_id)
        if reference is None:
            rows.append(
                _record(
                    reference_id,
                    "COMPLETED_UPPER_OUTCOME_EVIDENCE",
                    False,
                    "missing reference",
                    "accepted upper reference exists",
                )
            )
            continue
        rows.extend(
            audit_upper_outcome(
                reference,
                outcome,
                raw_prices[str(reference["Symbol"])],
                sessions,
            )
        )
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
