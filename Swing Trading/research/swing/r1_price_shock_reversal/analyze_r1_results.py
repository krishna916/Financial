"""Simulate and analyse the fixed-horizon R1 reversal experiment."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from build_r1_features import (
    LIQUIDITY_FLOOR,
    SIGNAL_END,
    SIGNAL_START,
    active_members_on,
    build_feature_frames,
    load_runtime_feature_cache,
    load_membership,
    save_runtime_feature_cache,
)
from generate_r1_signals import (
    HIGH_VOLUME_MIN,
    STOP_BUFFER_ATR,
    build_control_entries,
    load_canonical_market_sessions,
    next_session,
)


BASE_FRICTION = 0.004
STRESS_FRICTION = 0.006
SEVERE_FRICTION = 0.008
BOOTSTRAP_SEED = 20260828
BOOTSTRAP_RESAMPLES = 10_000


def _finite(value: object) -> bool:
    try:
        return bool(pd.notna(value) and np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _clean_sessions(values: pd.DatetimeIndex | object) -> pd.DatetimeIndex:
    sessions = pd.DatetimeIndex(pd.to_datetime(values, errors="coerce"))
    if sessions.tz is not None:
        sessions = sessions.tz_localize(None)
    return sessions.dropna().drop_duplicates().sort_values()


def _prices_for_trade(prices: pd.DataFrame) -> pd.DataFrame:
    if "Date" not in prices.columns:
        raise ValueError("price frame missing Date")
    result = prices.copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
    if getattr(result["Date"].dt, "tz", None) is not None:
        result["Date"] = result["Date"].dt.tz_localize(None)
    if result["Date"].isna().any() or result["Date"].duplicated().any():
        raise ValueError("price frame contains invalid or duplicate dates")
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.sort_values("Date").reset_index(drop=True)


def _row_on_date(prices: pd.DataFrame, date: pd.Timestamp) -> pd.Series | None:
    rows = prices.loc[prices["Date"].eq(date)]
    return rows.iloc[0] if len(rows) == 1 else None


def _session_position(date: pd.Timestamp, sessions: pd.DatetimeIndex) -> int | None:
    positions = np.flatnonzero(_clean_sessions(sessions) == pd.Timestamp(date))
    return int(positions[0]) if len(positions) == 1 else None


def _friction_fields(trade: dict[str, object]) -> dict[str, object]:
    gross_return = float(trade["Gross_Return"])
    entry_open = float(trade["Entry_Open"])
    exit_price = float(trade["Exit_Price"])
    initial_risk = trade.get("Initial_Risk")
    result = {
        "Base_Net_Return": gross_return - BASE_FRICTION,
        "Stress_Net_Return": gross_return - STRESS_FRICTION,
        "Severe_Net_Return": gross_return - SEVERE_FRICTION,
    }
    if _finite(initial_risk) and float(initial_risk) > 0:
        risk = float(initial_risk)
        result.update(
            {
                "Base_Net_R": ((exit_price - entry_open) - BASE_FRICTION * entry_open) / risk,
                "Stress_Net_R": ((exit_price - entry_open) - STRESS_FRICTION * entry_open) / risk,
                "Severe_Net_R": ((exit_price - entry_open) - SEVERE_FRICTION * entry_open) / risk,
            }
        )
    return result


def _entry_context(entry_row: pd.Series) -> dict[str, object]:
    signal_date = pd.Timestamp(entry_row["Signal_Date"])
    entry_date = pd.Timestamp(entry_row["Entry_Date"])
    entry_open = float(entry_row["Entry_Open"])
    entry_id = str(entry_row["Entry_ID"])
    symbol = entry_row.get("Symbol", entry_id.split("-", 1)[0])
    return {
        "Entry_ID": entry_id,
        "Symbol": str(symbol),
        "Signal_Date": signal_date,
        "Entry_Date": entry_date,
        "Entry_Open": entry_open,
    }


def simulate_setup_quality_trade(
    entry_row: pd.Series,
    prices: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex,
) -> dict[str, object] | None:
    """Simulate T+1 Open to T+6 Open without stop mechanics."""

    sessions = _clean_sessions(canonical_sessions)
    entry_position = _session_position(pd.Timestamp(entry_row["Entry_Date"]), sessions)
    exit_date = next_session(pd.Timestamp(entry_row["Signal_Date"]), sessions, 6)
    exit_position = _session_position(exit_date, sessions) if exit_date is not None else None
    if entry_position is None or exit_position is None or exit_position - entry_position != 5:
        return None
    frame = _prices_for_trade(prices)
    entry_bar = _row_on_date(frame, pd.Timestamp(entry_row["Entry_Date"]))
    exit_bar = _row_on_date(frame, pd.Timestamp(exit_date))
    if entry_bar is None or exit_bar is None or not _finite(exit_bar.get("Open", np.nan)):
        return None
    entry_open = float(entry_row["Entry_Open"])
    exit_price = float(exit_bar["Open"])
    trade = {
        **_entry_context(entry_row),
        "Scheduled_Exit_Date": exit_date,
        "Exit_Date": exit_date,
        "Exit_Price": exit_price,
        "Exit_Reason": "FIXED_HORIZON",
        "Holding_Sessions": exit_position - entry_position,
        "Gross_Return": exit_price / entry_open - 1.0,
    }
    trade["Gross_R"] = np.nan
    trade.update(_friction_fields(trade))
    return trade


def simulate_practical_trade(
    entry_row: pd.Series,
    prices: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex,
) -> dict[str, object] | None:
    """Apply the fixed structural stop through the fifth holding session."""

    sessions = _clean_sessions(canonical_sessions)
    entry_date = pd.Timestamp(entry_row["Entry_Date"])
    entry_position = _session_position(entry_date, sessions)
    exit_date = next_session(pd.Timestamp(entry_row["Signal_Date"]), sessions, 6)
    exit_position = _session_position(exit_date, sessions) if exit_date is not None else None
    if entry_position is None or exit_position is None or exit_position - entry_position != 5:
        return None
    frame = _prices_for_trade(prices)
    structural_stop = float(entry_row["Structural_Stop"])
    entry_open = float(entry_row["Entry_Open"])
    initial_risk = entry_open - structural_stop
    if not _finite(structural_stop) or not _finite(entry_open) or initial_risk <= 0:
        return None

    exit_price: float | None = None
    exit_reason = ""
    exit_session: pd.Timestamp | None = None
    for position in range(entry_position, exit_position):
        date = pd.Timestamp(sessions[position])
        bar = _row_on_date(frame, date)
        if bar is None or not _finite(bar.get("Open", np.nan)) or not _finite(bar.get("Low", np.nan)):
            return None
        open_price = float(bar["Open"])
        low_price = float(bar["Low"])
        if open_price <= structural_stop:
            exit_price, exit_reason, exit_session = open_price, "STOP_GAP", date
            break
        if low_price <= structural_stop:
            exit_price, exit_reason, exit_session = structural_stop, "STOP_INTRADAY", date
            break
    if exit_price is None:
        exit_bar = _row_on_date(frame, pd.Timestamp(exit_date))
        if exit_bar is None or not _finite(exit_bar.get("Open", np.nan)):
            return None
        exit_price = float(exit_bar["Open"])
        exit_reason = "FIXED_HORIZON"
        exit_session = pd.Timestamp(exit_date)
    trade = {
        **_entry_context(entry_row),
        "Structural_Stop": structural_stop,
        "Initial_Risk": initial_risk,
        "Scheduled_Exit_Date": exit_date,
        "Exit_Date": exit_session,
        "Exit_Price": exit_price,
        "Exit_Reason": exit_reason,
        "Holding_Sessions": _session_position(exit_session, sessions) - entry_position,
        "Gross_Return": exit_price / entry_open - 1.0,
        "Gross_R": (exit_price - entry_open) / initial_risk,
    }
    trade.update(_friction_fields(trade))
    return trade


def simulate_control_outcome(
    control_row: pd.Series,
    prices: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex,
) -> dict[str, object] | None:
    """Simulate a raw high-volume control from next Open to T+6 Open."""

    sessions = _clean_sessions(canonical_sessions)
    entry_position = _session_position(pd.Timestamp(control_row["Entry_Date"]), sessions)
    exit_date = next_session(pd.Timestamp(control_row["Signal_Date"]), sessions, 6)
    exit_position = _session_position(exit_date, sessions) if exit_date is not None else None
    if entry_position is None or exit_position is None or exit_position - entry_position != 5:
        return None
    frame = _prices_for_trade(prices)
    exit_bar = _row_on_date(frame, pd.Timestamp(exit_date))
    if exit_bar is None or not _finite(exit_bar.get("Open", np.nan)):
        return None
    entry_open = float(control_row["Entry_Open"])
    exit_price = float(exit_bar["Open"])
    entry_id = str(control_row["Entry_ID"])
    return {
        "Entry_ID": entry_id,
        "Symbol": str(control_row.get("Symbol", entry_id.split("-", 1)[0])),
        "Signal_Date": pd.Timestamp(control_row["Signal_Date"]),
        "Entry_Date": pd.Timestamp(control_row["Entry_Date"]),
        "Entry_Open": entry_open,
        "Exit_Date": pd.Timestamp(exit_date),
        "Exit_Price": exit_price,
        "Holding_Sessions": exit_position - entry_position,
        "Gross_Return": exit_price / entry_open - 1.0,
        "Exit_Reason": "FIXED_HORIZON",
    }


def forward_open_return(
    entry_open: float,
    signal_date: pd.Timestamp,
    canonical_sessions: pd.DatetimeIndex,
    prices: pd.DataFrame,
    holding_sessions: int,
) -> float:
    """Return from immediate next Open to the Open after N holding sessions."""

    if holding_sessions < 1:
        raise ValueError("holding_sessions must be positive")
    exit_date = next_session(signal_date, canonical_sessions, holding_sessions + 1)
    if exit_date is None:
        return float("nan")
    exit_bar = _row_on_date(_prices_for_trade(prices), pd.Timestamp(exit_date))
    if exit_bar is None or not _finite(exit_bar.get("Open", np.nan)):
        return float("nan")
    if not _finite(entry_open) or float(entry_open) == 0:
        return float("nan")
    return float(exit_bar["Open"]) / float(entry_open) - 1.0


def _finite_values(values: pd.Series | object) -> np.ndarray:
    numeric = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    return numeric[np.isfinite(numeric)]


def safe_profit_factor(values: pd.Series) -> float:
    """Return positive-sum divided by absolute negative-sum, including infinity."""

    numeric = _finite_values(values)
    gains = float(numeric[numeric > 0].sum())
    losses = float(-numeric[numeric < 0].sum())
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return gains / losses


def bootstrap_mean_ci(
    values: pd.Series,
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> tuple[float, float]:
    """Return a deterministic percentile bootstrap CI for a mean."""

    numeric = _finite_values(values)
    if len(numeric) == 0:
        return float("nan"), float("nan")
    if resamples <= 0:
        raise ValueError("resamples must be positive")
    rng = np.random.default_rng(seed)
    means = np.empty(resamples, dtype=float)
    chunk_size = 256
    for start in range(0, resamples, chunk_size):
        stop = min(start + chunk_size, resamples)
        indices = rng.integers(0, len(numeric), size=(stop - start, len(numeric)))
        means[start:stop] = numeric[indices].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def bootstrap_difference_ci(
    low: pd.Series,
    high: pd.Series,
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> tuple[float, float]:
    """Return a deterministic independent-resampling CI for low-minus-high means."""

    low_values = _finite_values(low)
    high_values = _finite_values(high)
    if len(low_values) == 0 or len(high_values) == 0:
        return float("nan"), float("nan")
    if resamples <= 0:
        raise ValueError("resamples must be positive")
    rng = np.random.default_rng(seed)
    differences = np.empty(resamples, dtype=float)
    chunk_size = 128
    for start in range(0, resamples, chunk_size):
        stop = min(start + chunk_size, resamples)
        low_indices = rng.integers(0, len(low_values), size=(stop - start, len(low_values)))
        high_indices = rng.integers(0, len(high_values), size=(stop - start, len(high_values)))
        differences[start:stop] = (
            low_values[low_indices].mean(axis=1) - high_values[high_indices].mean(axis=1)
        )
    return float(np.percentile(differences, 2.5)), float(np.percentile(differences, 97.5))


def summarize_lens(trades: pd.DataFrame, lens: str) -> dict[str, object]:
    """Summarize a completed setup or practical result frame."""

    if lens == "setup":
        gross_column = "Gross_Return"
        gross_label = "Gross_Return"
        practical = False
    elif lens == "practical":
        gross_column = "Gross_R"
        gross_label = "Gross_R"
        practical = True
    else:
        raise ValueError("lens must be setup or practical")
    numeric = _finite_values(trades.get(gross_column, pd.Series(dtype=float)))
    summary: dict[str, object] = {
        "Lens": lens,
        "Completed_Trades": int(len(numeric)),
        "Winners": int((numeric > 0).sum()),
        "Losers": int((numeric < 0).sum()),
        "Win_Rate": float((numeric > 0).mean()) if len(numeric) else np.nan,
        f"{gross_label}_Mean": float(numeric.mean()) if len(numeric) else np.nan,
        f"{gross_label}_Median": float(np.median(numeric)) if len(numeric) else np.nan,
        f"{gross_label}_PF": safe_profit_factor(pd.Series(numeric)),
    }
    if practical:
        for prefix, column in (
            ("Base", "Base_Net_R"),
            ("Stress", "Stress_Net_R"),
            ("Severe", "Severe_Net_R"),
        ):
            values = _finite_values(trades.get(column, pd.Series(dtype=float)))
            summary[f"{prefix}_Net_Mean_R"] = float(values.mean()) if len(values) else np.nan
            summary[f"{prefix}_Net_R_PF"] = safe_profit_factor(pd.Series(values))
    else:
        for prefix in ("Base", "Stress", "Severe"):
            column = f"{prefix}_Net_Return"
            values = _finite_values(trades.get(column, pd.Series(dtype=float)))
            summary[f"{prefix}_Net_Mean_Return"] = float(values.mean()) if len(values) else np.nan
            summary[f"{prefix}_Net_Return_PF"] = safe_profit_factor(pd.Series(values))
    return summary


def temporal_summary(setup: pd.DataFrame) -> pd.DataFrame:
    """Summarize the frozen first/second calendar halves."""

    periods = (
        ("FIRST_HALF", pd.Timestamp("2023-08-01"), pd.Timestamp("2025-02-11")),
        ("SECOND_HALF", pd.Timestamp("2025-02-12"), pd.Timestamp("2026-08-25")),
    )
    rows: list[dict[str, object]] = []
    dates = pd.to_datetime(setup.get("Signal_Date", pd.Series(dtype="datetime64[ns]")), errors="coerce")
    for label, start, end in periods:
        subset = setup.loc[dates.between(start, end)]
        values = _finite_values(subset.get("Base_Net_Return", pd.Series(dtype=float)))
        rows.append(
            {
                "Period": label,
                "Signal_Start": start,
                "Signal_End": end,
                "Completed_Trades": len(values),
                "Base_Net_Mean_Return": float(values.mean()) if len(values) else np.nan,
                "Base_Net_Return_PF": safe_profit_factor(pd.Series(values)),
            }
        )
    return pd.DataFrame(rows)


def outlier_robustness(setup: pd.DataFrame) -> pd.DataFrame:
    """Remove the five largest gross setup winners and recompute base metrics."""

    ordered = setup.sort_values("Gross_Return", ascending=False).reset_index(drop=True)
    remaining = ordered.iloc[5:].copy()
    values = _finite_values(remaining.get("Base_Net_Return", pd.Series(dtype=float)))
    return pd.DataFrame(
        [
            {
                "Analysis": "TOP_FIVE_GROSS_WINNERS_REMOVED",
                "Removed_Trades": min(5, len(ordered)),
                "Remaining_Trades": len(values),
                "Base_Net_Mean_Return": float(values.mean()) if len(values) else np.nan,
                "Base_Net_Return_PF": safe_profit_factor(pd.Series(values)),
            }
        ]
    )


def leave_one_symbol_out(setup: pd.DataFrame) -> pd.DataFrame:
    """Recompute base setup metrics after omitting each represented symbol."""

    rows: list[dict[str, object]] = []
    for symbol in sorted(setup.get("Symbol", pd.Series(dtype=str)).dropna().astype(str).unique()):
        subset = setup.loc[setup["Symbol"].astype(str).ne(symbol)]
        values = _finite_values(subset.get("Base_Net_Return", pd.Series(dtype=float)))
        rows.append(
            {
                "Omitted_Symbol": symbol,
                "Remaining_Trades": len(values),
                "Base_Net_Mean_Return": float(values.mean()) if len(values) else np.nan,
                "Base_Net_Return_PF": safe_profit_factor(pd.Series(values)),
            }
        )
    return pd.DataFrame(rows)


def control_comparison(setup: pd.DataFrame, controls: pd.DataFrame) -> pd.DataFrame:
    """Compare low-volume setup returns with raw high-volume controls."""

    low = _finite_values(setup.get("Gross_Return", pd.Series(dtype=float)))
    high = _finite_values(controls.get("Gross_Return", pd.Series(dtype=float)))
    return pd.DataFrame(
        [
            {
                "Low_Volume_Trades": len(low),
                "High_Volume_Trades": len(high),
                "Low_Volume_Gross_Mean_Return": float(low.mean()) if len(low) else np.nan,
                "High_Volume_Gross_Mean_Return": float(high.mean()) if len(high) else np.nan,
                "Low_Volume_Gross_PF": safe_profit_factor(pd.Series(low)),
                "High_Volume_Gross_PF": safe_profit_factor(pd.Series(high)),
                "Low_Mean_Exceeds_High": bool(len(low) and len(high) and low.mean() > high.mean()),
                "Low_PF_Exceeds_High": bool(
                    len(low) and len(high) and safe_profit_factor(pd.Series(low)) > safe_profit_factor(pd.Series(high))
                ),
            }
        ]
    )


def bootstrap_summary(
    setup: pd.DataFrame,
    practical: pd.DataFrame,
    controls: pd.DataFrame,
) -> pd.DataFrame:
    """Persist the four required deterministic bootstrap intervals."""

    low = _finite_values(setup.get("Gross_Return", pd.Series(dtype=float)))
    high = _finite_values(controls.get("Gross_Return", pd.Series(dtype=float)))
    metrics = [
        ("GROSS_SETUP_MEAN_RETURN", setup.get("Gross_Return", pd.Series(dtype=float)), np.mean),
        ("BASE_NET_SETUP_MEAN_RETURN", setup.get("Base_Net_Return", pd.Series(dtype=float)), np.mean),
        ("BASE_NET_PRACTICAL_MEAN_R", practical.get("Base_Net_R", pd.Series(dtype=float)), np.mean),
    ]
    rows: list[dict[str, object]] = []
    for label, values, _ in metrics:
        numeric = _finite_values(values)
        lower, upper = bootstrap_mean_ci(pd.Series(numeric))
        rows.append(
            {
                "Metric": label,
                "Estimate": float(numeric.mean()) if len(numeric) else np.nan,
                "CI_Lower": lower,
                "CI_Upper": upper,
                "Seed": BOOTSTRAP_SEED,
                "Resamples": BOOTSTRAP_RESAMPLES,
                "Confidence": 0.95,
            }
        )
    lower, upper = bootstrap_difference_ci(pd.Series(low), pd.Series(high))
    rows.append(
        {
            "Metric": "LOW_MINUS_HIGH_GROSS_MEAN_RETURN",
            "Estimate": float(low.mean() - high.mean()) if len(low) and len(high) else np.nan,
            "CI_Lower": lower,
            "CI_Upper": upper,
            "Seed": BOOTSTRAP_SEED,
            "Resamples": BOOTSTRAP_RESAMPLES,
            "Confidence": 0.95,
        }
    )
    return pd.DataFrame(rows)


def _audit_violation(
    rows: list[dict[str, object]],
    entry_id: object,
    symbol: object,
    violation: str,
    observed: object = "",
    expected: object = "",
) -> None:
    rows.append(
        {
            "Entry_ID": str(entry_id) if entry_id is not None else "",
            "Symbol": str(symbol) if symbol is not None else "",
            "Violation": violation,
            "Observed": observed,
            "Expected": expected,
        }
    )


def _persisted_date(value: object) -> pd.Timestamp | None:
    if value is None or pd.isna(value) or str(value).strip() in {"", "NaT", "nan"}:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    timestamp = pd.Timestamp(parsed)
    return timestamp.tz_localize(None) if timestamp.tzinfo is not None else timestamp


def _signal_lookup(signals: pd.DataFrame) -> dict[str, pd.Series]:
    if signals.empty or "Signal_ID" not in signals.columns:
        return {}
    return {str(row["Signal_ID"]): row for _, row in signals.iterrows()}


def _audit_low_entry(
    entry: pd.Series,
    signal: pd.Series | None,
    feature_frames: dict[str, pd.DataFrame],
    membership: pd.DataFrame,
    sessions: pd.DatetimeIndex,
    rows: list[dict[str, object]],
) -> None:
    entry_id = entry.get("Entry_ID", "")
    symbol = str(entry.get("Symbol", signal.get("Symbol", "") if signal is not None else ""))
    signal_date = _persisted_date(entry.get("Signal_Date"))
    entry_date = _persisted_date(entry.get("Entry_Date"))
    if signal_date is None or entry_date is None:
        _audit_violation(rows, entry_id, symbol, "INVALID_ENTRY_DATES")
        return
    if not signal_date < entry_date:
        _audit_violation(rows, entry_id, symbol, "SIGNAL_NOT_BEFORE_ENTRY", signal_date, "Signal_Date < Entry_Date")
    if not SIGNAL_START <= signal_date <= SIGNAL_END:
        _audit_violation(rows, entry_id, symbol, "SIGNAL_OUTSIDE_WINDOW", signal_date, f"{SIGNAL_START}..{SIGNAL_END}")
    active_symbols = set(active_members_on(membership, signal_date)["Symbol"].astype(str))
    if symbol not in active_symbols:
        _audit_violation(rows, entry_id, symbol, "PIT_MEMBERSHIP_VIOLATION", False, True)
    expected_entry_date = next_session(signal_date, sessions)
    if expected_entry_date != entry_date:
        _audit_violation(rows, entry_id, symbol, "IMMEDIATE_NEXT_SESSION_MISMATCH", entry_date, expected_entry_date)

    frame = feature_frames.get(symbol)
    if frame is None:
        _audit_violation(rows, entry_id, symbol, "MISSING_FEATURE_FRAME")
        return
    try:
        prices = _prices_for_trade(frame)
    except ValueError as exc:
        _audit_violation(rows, entry_id, symbol, "INVALID_FEATURE_FRAME", str(exc))
        return
    signal_rows = prices.loc[prices["Date"].eq(signal_date)]
    if len(signal_rows) != 1:
        _audit_violation(rows, entry_id, symbol, "MISSING_SIGNAL_BAR", len(signal_rows), 1)
        return
    source = signal_rows.iloc[0]
    position = int(signal_rows.index[0])
    close = pd.to_numeric(prices["Close"], errors="coerce")
    returns = close.pct_change(fill_method=None)
    prior_returns = returns.iloc[position - 20 : position]
    if len(prior_returns) != 20 or not np.isfinite(prior_returns.to_numpy(dtype=float)).all():
        _audit_violation(rows, entry_id, symbol, "PRIOR_RETURNS_INVALID", len(prior_returns), 20)
    else:
        sigma = float(prior_returns.std(ddof=1))
        persisted_sigma = float(signal.get("Sigma20", np.nan)) if _finite(signal.get("Sigma20")) else np.nan
        if not np.isclose(persisted_sigma, sigma, rtol=1e-9, atol=1e-12):
            _audit_violation(rows, entry_id, symbol, "SIGMA20_MISMATCH", persisted_sigma, sigma)
        signal_return = float(close.iloc[position] / close.iloc[position - 1] - 1.0)
        persisted_return = float(signal.get("Return", np.nan)) if _finite(signal.get("Return")) else np.nan
        if not np.isclose(persisted_return, signal_return, rtol=1e-9, atol=1e-12):
            _audit_violation(rows, entry_id, symbol, "SIGNAL_RETURN_MISMATCH", persisted_return, signal_return)
        expected_shock = signal_return / sigma if sigma > 0 else np.nan
        persisted_shock = float(signal.get("Shock_Score", np.nan)) if _finite(signal.get("Shock_Score")) else np.nan
        if not np.isclose(persisted_shock, expected_shock, rtol=1e-9, atol=1e-12):
            _audit_violation(rows, entry_id, symbol, "SHOCK_SCORE_MISMATCH", persisted_shock, expected_shock)
        if not np.isfinite(persisted_shock) or persisted_shock > -2.0:
            _audit_violation(rows, entry_id, symbol, "SHOCK_THRESHOLD_VIOLATION", persisted_shock, "<= -2.0")

    prior_volume = pd.to_numeric(prices["Volume"], errors="coerce").iloc[position - 20 : position]
    if len(prior_volume) != 20 or not np.isfinite(prior_volume.to_numpy(dtype=float)).all():
        _audit_violation(rows, entry_id, symbol, "PRIOR_VOLUME_INVALID", len(prior_volume), 20)
    else:
        expected_median_volume = float(prior_volume.median())
        persisted_median_volume = float(signal.get("Prior20_Median_Volume", np.nan)) if _finite(signal.get("Prior20_Median_Volume")) else np.nan
        if not np.isclose(persisted_median_volume, expected_median_volume, rtol=1e-9, atol=1e-12):
            _audit_violation(rows, entry_id, symbol, "PRIOR_VOLUME_MISMATCH", persisted_median_volume, expected_median_volume)
        expected_ratio = float(prices.iloc[position]["Volume"]) / expected_median_volume
        persisted_ratio = float(signal.get("Volume_Ratio", np.nan)) if _finite(signal.get("Volume_Ratio")) else np.nan
        if not np.isclose(persisted_ratio, expected_ratio, rtol=1e-9, atol=1e-12):
            _audit_violation(rows, entry_id, symbol, "VOLUME_RATIO_MISMATCH", persisted_ratio, expected_ratio)
        if not np.isfinite(persisted_ratio) or persisted_ratio > 1.0:
            _audit_violation(rows, entry_id, symbol, "LOW_VOLUME_THRESHOLD_VIOLATION", persisted_ratio, "<= 1.0")

    traded_value = close * pd.to_numeric(prices["Volume"], errors="coerce")
    prior_traded_value = traded_value.iloc[position - 20 : position]
    if len(prior_traded_value) != 20 or not np.isfinite(prior_traded_value.to_numpy(dtype=float)).all():
        _audit_violation(rows, entry_id, symbol, "PRIOR_TRADED_VALUE_INVALID", len(prior_traded_value), 20)
    else:
        expected_value = float(prior_traded_value.median())
        persisted_value = float(signal.get("Prior20_Median_Traded_Value", np.nan)) if _finite(signal.get("Prior20_Median_Traded_Value")) else np.nan
        if not np.isclose(persisted_value, expected_value, rtol=1e-9, atol=1e-12):
            _audit_violation(rows, entry_id, symbol, "PRIOR_TRADED_VALUE_MISMATCH", persisted_value, expected_value)
        if not np.isfinite(persisted_value) or persisted_value < LIQUIDITY_FLOOR:
            _audit_violation(rows, entry_id, symbol, "LIQUIDITY_FLOOR_VIOLATION", persisted_value, LIQUIDITY_FLOOR)

    atr = source.get("ATR14", np.nan)
    shock_low = source.get("Low", np.nan)
    persisted_stop = float(entry.get("Structural_Stop", np.nan)) if _finite(entry.get("Structural_Stop")) else np.nan
    expected_stop = float(shock_low) - STOP_BUFFER_ATR * float(atr) if _finite(shock_low) and _finite(atr) else np.nan
    if not np.isclose(persisted_stop, expected_stop, rtol=1e-9, atol=1e-12):
        _audit_violation(rows, entry_id, symbol, "STRUCTURAL_STOP_MISMATCH", persisted_stop, expected_stop)
    if not _finite(entry.get("Entry_Open")) or float(entry["Entry_Open"]) <= persisted_stop:
        _audit_violation(rows, entry_id, symbol, "ENTRY_NOT_ABOVE_STRUCTURAL_STOP", entry.get("Entry_Open"), persisted_stop)

    expected_exit = next_session(signal_date, sessions, 6)
    persisted_exit = _persisted_date(entry.get("Scheduled_Exit_Date"))
    if expected_exit is not None and persisted_exit != expected_exit:
        _audit_violation(rows, entry_id, symbol, "SCHEDULED_EXIT_MISMATCH", persisted_exit, expected_exit)


def count_integrity_violations(
    signals: pd.DataFrame,
    entries: pd.DataFrame,
    cancellations: pd.DataFrame,
    setup: pd.DataFrame,
    practical: pd.DataFrame,
    controls: pd.DataFrame,
    feature_frames: dict[str, pd.DataFrame],
    membership: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex,
) -> tuple[int, pd.DataFrame]:
    """Recompute persisted R1 evidence and return deduplicated violations."""

    rows: list[dict[str, object]] = []
    sessions = _clean_sessions(canonical_sessions)
    low_signals = signals
    if "Cohort" in signals.columns:
        low_signals = signals.loc[signals["Cohort"].eq("LOW_VOLUME")]
    signal_lookup = _signal_lookup(low_signals)
    all_signal_lookup = _signal_lookup(signals)
    for _, entry in entries.iterrows():
        signal_id = str(entry.get("Signal_ID", entry.get("Entry_ID", "")))
        signal = signal_lookup.get(signal_id)
        if signal is None:
            _audit_violation(rows, entry.get("Entry_ID", signal_id), entry.get("Symbol", ""), "ENTRY_WITHOUT_QUALIFIED_SIGNAL")
        _audit_low_entry(entry, signal, feature_frames, membership, sessions, rows)

    qualified_ids = set(signal_lookup)
    accepted_ids = entries.get("Signal_ID", pd.Series(dtype=str)).astype(str).tolist()
    cancelled_ids = cancellations.get("Signal_ID", pd.Series(dtype=str)).astype(str).tolist()
    outcome_ids = accepted_ids + cancelled_ids
    if len(outcome_ids) != len(set(outcome_ids)) or set(outcome_ids) != qualified_ids:
        _audit_violation(rows, "", "", "ACCOUNTING_MISMATCH", len(outcome_ids), len(qualified_ids))
    if len(set(setup.get("Entry_ID", pd.Series(dtype=str)).astype(str))) != len(
        set(practical.get("Entry_ID", pd.Series(dtype=str)).astype(str))
    ) or set(setup.get("Entry_ID", pd.Series(dtype=str)).astype(str)) != set(
        practical.get("Entry_ID", pd.Series(dtype=str)).astype(str)
    ):
        _audit_violation(rows, "", "", "PAIRED_ENTRY_ID_MISMATCH")

    accepted_sorted = entries.sort_values(["Symbol", "Signal_Date"]) if not entries.empty else entries
    for symbol, group in accepted_sorted.groupby("Symbol", sort=False):
        previous_exit: pd.Timestamp | None = None
        for _, entry in group.iterrows():
            signal_date = _persisted_date(entry.get("Signal_Date"))
            if previous_exit is not None and signal_date is not None and signal_date < previous_exit:
                _audit_violation(rows, entry.get("Entry_ID", ""), symbol, "LOW_VOLUME_LOCKOUT_VIOLATION")
            previous_exit = _persisted_date(entry.get("Scheduled_Exit_Date")) or pd.Timestamp.max

    control_rows = []
    for _, control in controls.iterrows():
        control_id = str(control.get("Entry_ID", ""))
        source = all_signal_lookup.get(control_id)
        symbol = str(control.get("Symbol", source.get("Symbol", "") if source is not None else ""))
        if source is None:
            _audit_violation(rows, control_id, symbol, "CONTROL_WITHOUT_SIGNAL")
            continue
        shock = source.get("Shock_Score", np.nan)
        ratio = source.get("Volume_Ratio", np.nan)
        if not _finite(shock) or float(shock) > -2.0:
            _audit_violation(rows, control_id, symbol, "CONTROL_SHOCK_THRESHOLD_VIOLATION", shock, "<= -2.0")
        if not _finite(ratio) or float(ratio) < HIGH_VOLUME_MIN:
            _audit_violation(rows, control_id, symbol, "CONTROL_VOLUME_THRESHOLD_VIOLATION", ratio, ">= 1.5")
        signal_date = _persisted_date(control.get("Signal_Date"))
        entry_date = _persisted_date(control.get("Entry_Date"))
        if signal_date is None or entry_date is None or next_session(signal_date, sessions) != entry_date:
            _audit_violation(rows, control_id, symbol, "CONTROL_ENTRY_TIMING_MISMATCH")
        expected_exit = next_session(signal_date, sessions, 6) if signal_date is not None else None
        if expected_exit is not None and _persisted_date(control.get("Exit_Date")) != expected_exit:
            _audit_violation(rows, control_id, symbol, "CONTROL_EXIT_TIMING_MISMATCH")
        control_rows.append((symbol, signal_date, expected_exit, control_id))
    for symbol in sorted({row[0] for row in control_rows}):
        prior_exit: pd.Timestamp | None = None
        for row_symbol, signal_date, expected_exit, control_id in sorted(
            [row for row in control_rows if row[0] == symbol], key=lambda item: item[1] or pd.Timestamp.min
        ):
            if prior_exit is not None and signal_date is not None and signal_date < prior_exit:
                _audit_violation(rows, control_id, symbol, "CONTROL_LOCKOUT_VIOLATION")
            prior_exit = expected_exit or pd.Timestamp.max

    audit = pd.DataFrame(rows, columns=["Entry_ID", "Symbol", "Violation", "Observed", "Expected"])
    if not audit.empty:
        audit = audit.drop_duplicates(["Entry_ID", "Symbol", "Violation"]).sort_values(
            ["Entry_ID", "Symbol", "Violation"]
        ).reset_index(drop=True)
    return len(audit), audit


def overlap_diagnostics(entries: pd.DataFrame, canonical_sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """Report signal-level lifecycle overlap and same-day capacity diagnostics."""

    sessions = _clean_sessions(canonical_sessions)
    intervals: list[tuple[str, int, int]] = []
    for _, entry in entries.iterrows():
        start = _session_position(_persisted_date(entry.get("Entry_Date")), sessions) if _persisted_date(entry.get("Entry_Date")) is not None else None
        scheduled_exit = _persisted_date(entry.get("Scheduled_Exit_Date"))
        end = _session_position(scheduled_exit, sessions) if scheduled_exit is not None else len(sessions)
        if start is not None and end is not None and end > start:
            intervals.append((str(entry.get("Entry_ID", "")), start, end))
    counts = np.zeros(len(sessions), dtype=int)
    for _, start, end in intervals:
        counts[start:end] += 1
    overlapping_ids: set[str] = set()
    for index, (entry_id, start, end) in enumerate(intervals):
        if any(
            other_start < end and start < other_end
            for other_index, (_, other_start, other_end) in enumerate(intervals)
            if other_index != index
        ):
            overlapping_ids.add(entry_id)
    same_day = entries.get("Entry_Date", pd.Series(dtype="datetime64[ns]")).map(_persisted_date).dropna().value_counts()
    return pd.DataFrame(
        [
            {
                "Accepted_Entries": len(entries),
                "Max_Simultaneous_Trades": int(counts.max()) if len(counts) else 0,
                "Average_Simultaneous_Trades": float(counts[counts > 0].mean()) if (counts > 0).any() else 0.0,
                "Max_Same_Day_Entries": int(same_day.max()) if not same_day.empty else 0,
                "Overlapping_Entries": len(overlapping_ids),
                "Overlap_Percentage": len(overlapping_ids) / len(intervals) if intervals else 0.0,
                "Same_Day_Entry_Counts": json.dumps({str(key.date()): int(value) for key, value in same_day.items()}),
            }
        ]
    )


def _greater_than(value: object, threshold: float) -> bool:
    return _finite(value) and float(value) > threshold


def _greater_or_equal(value: object, threshold: float) -> bool:
    return _finite(value) and float(value) >= threshold


def _gate_row(
    gate: str,
    observed: object,
    threshold: object,
    passed: bool,
) -> dict[str, object]:
    return {
        "Gate": gate,
        "Observed": observed,
        "Threshold": threshold,
        "Pass": bool(passed),
        "Mandatory": True,
    }


def evaluate_gates(
    metrics: dict[str, object],
    temporal: pd.DataFrame,
    outlier: pd.DataFrame,
    loso: pd.DataFrame,
    control: pd.DataFrame,
    completed_count: int,
    integrity_violations: int,
) -> tuple[str, pd.DataFrame]:
    """Evaluate R1's frozen gates with invalid/insufficient precedence."""

    control_row = control.iloc[0].to_dict() if not control.empty else {}
    low_mean = control_row.get("Low_Volume_Gross_Mean_Return", np.nan)
    high_mean = control_row.get("High_Volume_Gross_Mean_Return", np.nan)
    low_pf = control_row.get("Low_Volume_Gross_PF", np.nan)
    high_pf = control_row.get("High_Volume_Gross_PF", np.nan)
    control_mean_pass = _finite(low_mean) and _finite(high_mean) and float(low_mean) > float(high_mean)
    control_pf_pass = _finite(low_pf) and _finite(high_pf) and float(low_pf) > float(high_pf)
    rows = [
        _gate_row("SAMPLE_SUFFICIENCY", completed_count, ">= 300", completed_count >= 300),
        _gate_row("GROSS_SETUP_MEAN", metrics.get("Gross_Return_Mean", np.nan), "> 0", _greater_than(metrics.get("Gross_Return_Mean"), 0.0)),
        _gate_row("BASE_NET_SETUP_MEAN", metrics.get("Base_Net_Mean_Return", np.nan), ">= 0.002", _greater_or_equal(metrics.get("Base_Net_Mean_Return"), 0.002)),
        _gate_row("BASE_NET_SETUP_PF", metrics.get("Base_Net_Return_PF", np.nan), ">= 1.20", _greater_or_equal(metrics.get("Base_Net_Return_PF"), 1.20)),
        _gate_row("STRESS_NET_SETUP_MEAN", metrics.get("Stress_Net_Mean_Return", np.nan), "> 0", _greater_than(metrics.get("Stress_Net_Mean_Return"), 0.0)),
        _gate_row("STRESS_NET_SETUP_PF", metrics.get("Stress_Net_Return_PF", np.nan), "> 1.00", _greater_than(metrics.get("Stress_Net_Return_PF"), 1.0)),
        _gate_row("BASE_PRACTICAL_MEAN_R", metrics.get("Base_Net_Mean_R", np.nan), ">= 0.15", _greater_or_equal(metrics.get("Base_Net_Mean_R"), 0.15)),
        _gate_row("BASE_PRACTICAL_R_PF", metrics.get("Base_Net_R_PF", np.nan), ">= 1.20", _greater_or_equal(metrics.get("Base_Net_R_PF"), 1.20)),
        _gate_row(
            "CONTROL_GROSS_MEAN",
            low_mean,
            "> high-volume mean",
            control_mean_pass,
        ),
        _gate_row(
            "CONTROL_GROSS_PF",
            low_pf,
            "> high-volume PF",
            control_pf_pass,
        ),
    ]
    temporal_by_period = {
        str(row["Period"]): row
        for _, row in temporal.iterrows()
        if "Period" in row.index
    }
    for period in ("FIRST_HALF", "SECOND_HALF"):
        row = temporal_by_period.get(period, {})
        rows.extend(
            [
                _gate_row(
                    f"TEMPORAL_{period}_MEAN",
                    row.get("Base_Net_Mean_Return", np.nan),
                    "> 0",
                    _greater_than(row.get("Base_Net_Mean_Return"), 0.0),
                ),
                _gate_row(
                    f"TEMPORAL_{period}_PF",
                    row.get("Base_Net_Return_PF", np.nan),
                    "> 1.0",
                    _greater_than(row.get("Base_Net_Return_PF"), 1.0),
                ),
            ]
        )
    outlier_row = outlier.iloc[0] if not outlier.empty else pd.Series(dtype=object)
    rows.extend(
        [
            _gate_row(
                "TOP_FIVE_REMOVED_MEAN",
                outlier_row.get("Base_Net_Mean_Return", np.nan),
                "> 0",
                _greater_than(outlier_row.get("Base_Net_Mean_Return"), 0.0),
            ),
            _gate_row(
                "TOP_FIVE_REMOVED_PF",
                outlier_row.get("Base_Net_Return_PF", np.nan),
                "> 1.0",
                _greater_than(outlier_row.get("Base_Net_Return_PF"), 1.0),
            ),
        ]
    )
    loso_mean_pass = not loso.empty and bool(loso["Base_Net_Mean_Return"].map(lambda value: _greater_than(value, 0.0)).all())
    loso_pf_pass = not loso.empty and bool(loso["Base_Net_Return_PF"].map(lambda value: _greater_than(value, 1.0)).all())
    rows.extend(
        [
            _gate_row("LOSO_ALL_MEAN", loso["Base_Net_Mean_Return"].min() if not loso.empty else np.nan, "> 0 for every symbol", loso_mean_pass),
            _gate_row("LOSO_ALL_PF", loso["Base_Net_Return_PF"].min() if not loso.empty else np.nan, "> 1.0 for every symbol", loso_pf_pass),
            _gate_row("INTEGRITY_ZERO", integrity_violations, "== 0", integrity_violations == 0),
        ]
    )
    gates = pd.DataFrame(rows)
    if integrity_violations > 0:
        status = "INVALID_RESEARCH_RUN"
    elif completed_count < 300:
        status = "INSUFFICIENT_EVIDENCE"
    elif bool(gates["Pass"].all()):
        status = "PASS"
    else:
        status = "FAIL"
    return status, gates


def calendar_year_summary(setup: pd.DataFrame) -> pd.DataFrame:
    """Produce calendar-year setup diagnostics without making them gates."""

    if setup.empty:
        return pd.DataFrame(
            columns=["Year", "Completed_Trades", "Gross_Mean_Return", "Base_Net_Mean_Return", "Base_Net_Return_PF"]
        )
    frame = setup.copy()
    frame["Year"] = pd.to_datetime(frame["Signal_Date"], errors="coerce").dt.year
    rows: list[dict[str, object]] = []
    for year, group in frame.groupby("Year", sort=True):
        values = _finite_values(group["Base_Net_Return"])
        rows.append(
            {
                "Year": int(year),
                "Completed_Trades": len(values),
                "Gross_Mean_Return": float(_finite_values(group["Gross_Return"]).mean()),
                "Base_Net_Mean_Return": float(values.mean()) if len(values) else np.nan,
                "Base_Net_Return_PF": safe_profit_factor(pd.Series(values)),
            }
        )
    return pd.DataFrame(rows)


def forward_diagnostic_summary(forward: pd.DataFrame) -> pd.DataFrame:
    if forward.empty:
        return pd.DataFrame(columns=["Holding_Sessions", "Observations", "Mean_Return", "Median_Return"])
    rows = []
    for horizon, group in forward.groupby("Holding_Sessions", sort=True):
        values = _finite_values(group["Forward_Return"])
        rows.append(
            {
                "Holding_Sessions": int(horizon),
                "Observations": len(values),
                "Mean_Return": float(values.mean()) if len(values) else np.nan,
                "Median_Return": float(np.median(values)) if len(values) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _report_table(frame: pd.DataFrame) -> str:
    return frame.to_string(index=False) if not frame.empty else "(none)"


def write_evidence_report(
    path: Path,
    validation: pd.DataFrame,
    candidates: pd.DataFrame,
    low_signals: pd.DataFrame,
    high_signals: pd.DataFrame,
    entries: pd.DataFrame,
    cancellations: pd.DataFrame,
    setup: pd.DataFrame,
    practical: pd.DataFrame,
    controls: pd.DataFrame,
    forward: pd.DataFrame,
    summary: pd.DataFrame,
    temporal: pd.DataFrame,
    outlier: pd.DataFrame,
    loso: pd.DataFrame,
    control: pd.DataFrame,
    bootstrap: pd.DataFrame,
    overlap: pd.DataFrame,
    pit_audit: pd.DataFrame,
    gates: pd.DataFrame,
    status: str,
) -> None:
    """Write a factual evidence report; no optimization recommendation is emitted."""

    usable = (
        int(
            validation["Usable"].map(
                lambda value: value
                if isinstance(value, (bool, np.bool_))
                else str(value).strip().lower() in {"true", "1", "yes", "y"}
            ).sum()
        )
        if not validation.empty
        else 0
    )
    failed = int(validation["Download_Error"].fillna("").ne("").sum()) if not validation.empty else 0
    cancellation_counts = (
        cancellations["Cancellation_Reason"].value_counts().to_dict()
        if "Cancellation_Reason" in cancellations.columns
        else {}
    )
    candidates_by_cohort = candidates.get("Cohort", pd.Series(dtype=str)).value_counts().to_dict()
    incomplete = len(entries) - len(setup)
    year = calendar_year_summary(setup)
    forward_summary = forward_diagnostic_summary(forward)
    summary_text = _report_table(summary)
    path.write_text(
        "\n".join(
            [
                "# R1 Short-Term Price-Shock Reversal — Historical Evidence",
                "",
                f"Formal status: `{status}`",
                "",
                "This report records the frozen R1 experiment mechanically. It is evidence only; no post-hoc filter, threshold, subgroup rescue, or strategy recommendation is generated here.",
                "",
                "## Frozen methodology",
                "",
                "Point-in-time Nifty 500 membership; signal window 2023-08-01 through 2026-08-25; prior-20 sample volatility (ddof=1), prior-20 median volume and traded value; Shock_Score <= -2.0; low-volume ratio <= 1.0; high-volume control ratio >= 1.5; immediate next-session Open entry; structural stop at shock-day Low - 0.25 ATR14; T+6 Open exit; five-session horizon; base/stress/severe friction 0.40%/0.60%/0.80%; bootstrap 10,000 resamples with seed 20260828.",
                "",
                "## Data coverage",
                "",
                f"Manifest symbols: {len(validation)}; usable/downloaded symbols: {usable}; visible download failures: {failed}.",
                "",
                "## Cohorts and accounting",
                "",
                f"All Shock_Score <= -2 candidates: {len(candidates)}; cohort counts: {candidates_by_cohort}.",
                f"Qualified low-volume signals: {len(low_signals)}; accepted entries: {len(entries)}; incomplete accepted entries: {incomplete}; cancellations: {len(cancellations)}.",
                f"Cancellation reasons: {cancellation_counts}.",
                f"High-volume control signals: {len(high_signals)}; completed raw control outcomes: {len(controls)}.",
                "",
                "## Setup and practical outcomes",
                "",
                summary_text,
                "",
                "## High-volume falsification comparison",
                "",
                _report_table(control),
                "",
                "## Temporal robustness",
                "",
                _report_table(temporal),
                "",
                "## Calendar-year diagnostics",
                "",
                _report_table(year),
                "",
                "## Outlier and leave-one-symbol-out diagnostics",
                "",
                _report_table(outlier),
                "",
                _report_table(loso),
                "",
                "## Forward-return diagnostics",
                "",
                _report_table(forward_summary),
                "",
                "## Bootstrap intervals",
                "",
                _report_table(bootstrap),
                "",
                "## Overlap/capacity diagnostics",
                "",
                _report_table(overlap),
                "",
                "## Point-in-time and integrity audit",
                "",
                f"Persisted audit violation rows: {len(pit_audit)}. Numeric comparisons use np.isclose(rtol=1e-9, atol=1e-12); dates and integers use exact equality.",
                "",
                "## Mandatory validation gates",
                "",
                _report_table(gates),
                "",
                "## Artifact inventory",
                "",
                "The accompanying CSV artifacts contain feature validation, shock cohorts, entries/cancellations, setup/practical/control outcomes, forward diagnostics, validation metrics, temporal/outlier/LOSO/control/bootstrap summaries, overlap diagnostics, PIT audit, and this report.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _read_csv_or_empty(path: Path, parse_dates: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=parse_dates or [])


def _paired_lenses(
    entries: pd.DataFrame,
    feature_frames: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    setup_rows: list[dict[str, object]] = []
    practical_rows: list[dict[str, object]] = []
    for _, entry in entries.iterrows():
        prices = feature_frames.get(str(entry["Symbol"]))
        if prices is None:
            continue
        setup = simulate_setup_quality_trade(entry, prices, sessions)
        practical = simulate_practical_trade(entry, prices, sessions)
        if setup is not None and practical is not None:
            setup_rows.append(setup)
            practical_rows.append(practical)
    setup = pd.DataFrame(setup_rows)
    practical = pd.DataFrame(practical_rows)
    if set(setup.get("Entry_ID", pd.Series(dtype=str))) != set(
        practical.get("Entry_ID", pd.Series(dtype=str))
    ):
        raise AssertionError("setup and practical completed Entry_ID sets differ")
    return setup, practical


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[4]
    module_dir = Path(__file__).resolve().parent
    output_dir = module_dir / "output"
    membership = load_membership(
        root / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv"
    )
    cached = load_runtime_feature_cache(membership)
    if cached is None:
        feature_frames, validation = build_feature_frames(membership)
        save_runtime_feature_cache(membership, feature_frames, validation)
    else:
        feature_frames, validation = cached
    validation.to_csv(output_dir / "r1_data_validation.csv", index=False)
    candidates = _read_csv_or_empty(output_dir / "r1_shock_candidates.csv", ["Signal_Date"])
    entries = _read_csv_or_empty(
        output_dir / "r1_entries.csv", ["Signal_Date", "Entry_Date", "Scheduled_Exit_Date"]
    )
    cancellations = _read_csv_or_empty(
        output_dir / "r1_entry_cancellations.csv", ["Signal_Date", "Next_Session_Date"]
    )
    low_signals = _read_csv_or_empty(output_dir / "r1_low_volume_signals.csv", ["Signal_Date"])
    high_signals = _read_csv_or_empty(output_dir / "r1_high_volume_control_signals.csv", ["Signal_Date"])
    extra_dates = pd.DatetimeIndex(
        [
            max(
                (pd.Timestamp(frame["Date"].max()) for frame in feature_frames.values() if not frame.empty),
                default=pd.Timestamp("2026-08-25"),
            )
        ]
    )
    sessions = load_canonical_market_sessions(
        root / "Swing Trading/nifty500_regime_daily.csv", extra_dates
    )
    setup, practical = _paired_lenses(entries, feature_frames, sessions)
    control_entries = build_control_entries(high_signals, feature_frames, sessions)
    control_rows = []
    for _, control in control_entries.iterrows():
        result = simulate_control_outcome(control, feature_frames[str(control["Symbol"])], sessions)
        if result is not None:
            control_rows.append(result)
    controls = pd.DataFrame(control_rows)
    audit_count, pit_audit = count_integrity_violations(
        pd.concat([low_signals, high_signals], ignore_index=True),
        entries,
        cancellations,
        setup,
        practical,
        controls,
        feature_frames,
        membership,
        sessions,
    )
    forward_rows: list[dict[str, object]] = []
    for _, entry in entries.iterrows():
        prices = feature_frames.get(str(entry["Symbol"]))
        if prices is None:
            continue
        for holding_sessions in (1, 3, 5, 10, 20):
            value = forward_open_return(
                float(entry["Entry_Open"]),
                pd.Timestamp(entry["Signal_Date"]),
                sessions,
                prices,
                holding_sessions,
            )
            if np.isfinite(value):
                forward_rows.append(
                    {
                        "Entry_ID": entry["Entry_ID"],
                        "Symbol": entry["Symbol"],
                        "Signal_Date": entry["Signal_Date"],
                        "Entry_Date": entry["Entry_Date"],
                        "Holding_Sessions": holding_sessions,
                        "Forward_Return": value,
                    }
                )
    forward = pd.DataFrame(forward_rows)
    setup_metrics = summarize_lens(setup, "setup")
    practical_metrics = summarize_lens(practical, "practical")
    summary = pd.DataFrame([setup_metrics, practical_metrics])
    temporal = temporal_summary(setup)
    outlier = outlier_robustness(setup)
    loso = leave_one_symbol_out(setup)
    control = control_comparison(setup, controls)
    bootstrap = bootstrap_summary(setup, practical, controls)
    overlap = overlap_diagnostics(entries, sessions)
    status, gates = evaluate_gates(
        {**setup_metrics, **practical_metrics},
        temporal,
        outlier,
        loso,
        control,
        len(setup),
        audit_count,
    )
    setup.to_csv(output_dir / "r1_setup_quality_trades.csv", index=False, date_format="%Y-%m-%d")
    practical.to_csv(output_dir / "r1_practical_trades.csv", index=False, date_format="%Y-%m-%d")
    controls.to_csv(output_dir / "r1_control_outcomes.csv", index=False, date_format="%Y-%m-%d")
    forward.to_csv(
        output_dir / "r1_forward_diagnostics.csv", index=False, date_format="%Y-%m-%d"
    )
    summary.to_csv(
        output_dir / "r1_validation_summary.csv", index=False
    )
    temporal.to_csv(
        output_dir / "r1_temporal_summary.csv", index=False, date_format="%Y-%m-%d"
    )
    outlier.to_csv(output_dir / "r1_outlier_robustness.csv", index=False)
    loso.to_csv(output_dir / "r1_leave_one_symbol_out.csv", index=False)
    control.to_csv(output_dir / "r1_control_comparison.csv", index=False)
    bootstrap.to_csv(output_dir / "r1_bootstrap_summary.csv", index=False)
    pit_audit.to_csv(output_dir / "r1_pit_audit.csv", index=False)
    overlap.to_csv(output_dir / "r1_overlap_diagnostic.csv", index=False)
    gates.to_csv(output_dir / "r1_validation_gates.csv", index=False)
    write_evidence_report(
        output_dir / "research_report.md",
        validation,
        candidates,
        low_signals,
        high_signals,
        entries,
        cancellations,
        setup,
        practical,
        controls,
        forward,
        summary,
        temporal,
        outlier,
        loso,
        control,
        bootstrap,
        overlap,
        pit_audit,
        gates,
        status,
    )
    print(
        f"paired_setup={len(setup)} paired_practical={len(practical)} "
        f"control_outcomes={len(controls)} forward_rows={len(forward_rows)} "
        f"integrity_violations={audit_count} status={status}"
    )
