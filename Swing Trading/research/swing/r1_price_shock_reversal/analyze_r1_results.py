"""Simulate and analyse the fixed-horizon R1 reversal experiment."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from build_r1_features import build_feature_frames, load_membership
from generate_r1_signals import build_control_entries, load_canonical_market_sessions, next_session


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
    feature_frames, validation = build_feature_frames(membership)
    validation.to_csv(output_dir / "r1_data_validation.csv", index=False)
    entries = _read_csv_or_empty(
        output_dir / "r1_entries.csv", ["Signal_Date", "Entry_Date", "Scheduled_Exit_Date"]
    )
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
    setup.to_csv(output_dir / "r1_setup_quality_trades.csv", index=False, date_format="%Y-%m-%d")
    practical.to_csv(output_dir / "r1_practical_trades.csv", index=False, date_format="%Y-%m-%d")
    controls.to_csv(output_dir / "r1_control_outcomes.csv", index=False, date_format="%Y-%m-%d")
    pd.DataFrame(forward_rows).to_csv(
        output_dir / "r1_forward_diagnostics.csv", index=False, date_format="%Y-%m-%d"
    )
    pd.DataFrame([summarize_lens(setup, "setup"), summarize_lens(practical, "practical")]).to_csv(
        output_dir / "r1_validation_summary.csv", index=False
    )
    temporal_summary(setup).to_csv(
        output_dir / "r1_temporal_summary.csv", index=False, date_format="%Y-%m-%d"
    )
    outlier_robustness(setup).to_csv(output_dir / "r1_outlier_robustness.csv", index=False)
    leave_one_symbol_out(setup).to_csv(output_dir / "r1_leave_one_symbol_out.csv", index=False)
    control_comparison(setup, controls).to_csv(output_dir / "r1_control_comparison.csv", index=False)
    bootstrap_summary(setup, practical, controls).to_csv(
        output_dir / "r1_bootstrap_summary.csv", index=False
    )
    print(
        f"paired_setup={len(setup)} paired_practical={len(practical)} "
        f"control_outcomes={len(controls)} forward_rows={len(forward_rows)}"
    )
