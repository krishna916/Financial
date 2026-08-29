"""Compute point-in-time seasonal SUE and the frozen E1 cohorts."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from constants import PRIMARY_END, PRIMARY_START
from build_e1_events import eps_values_match, formal_event_eligibility


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
    if stamp.tz is None:
        return stamp.tz_localize("Asia/Kolkata")
    return stamp.tz_convert("Asia/Kolkata")


def _quarter_index(value: object) -> int | None:
    date = _date(value)
    if pd.isna(date):
        return None
    return int(date.year * 4 + (date.month - 1) // 3)


def _sue_from_changes(current: float, seasonal_changes: pd.Series) -> dict[str, float]:
    """Return the frozen SUE arithmetic for one current seasonal change."""

    values = pd.to_numeric(seasonal_changes, errors="coerce").astype(float)
    if len(values) != 8 or not np.isfinite(values.to_numpy()).all():
        raise ValueError("exactly eight finite seasonal changes are required")
    historical_mean = float(values.mean())
    historical_sd = float(values.std(ddof=1))
    sue = (float(current) - historical_mean) / historical_sd if historical_sd > 0 and np.isfinite(historical_sd) else np.nan
    return {
        "Historical_Mean": historical_mean,
        "Historical_SD": historical_sd,
        "SUE": float(sue),
    }


def _action_factor(action: pd.Series) -> float:
    normalized = pd.to_numeric(action.get("Share_Count_Factor"), errors="coerce")
    if np.isfinite(normalized) and normalized > 0:
        return float(normalized)
    action_type = str(action.get("Action_Type") or "").upper()
    old_shares = pd.to_numeric(action.get("Old_Shares"), errors="coerce")
    new_shares = pd.to_numeric(action.get("New_Shares"), errors="coerce")
    bonus_shares = pd.to_numeric(action.get("Bonus_Shares"), errors="coerce")
    if (
        not np.isfinite(old_shares)
        or not np.isfinite(new_shares)
        or old_shares <= 0
        or new_shares <= 0
    ):
        raise ValueError("EPS_HISTORY_NOT_COMPARABLE")
    if action_type == "BONUS":
        if not np.isfinite(bonus_shares) or bonus_shares <= 0 or abs(new_shares - old_shares - bonus_shares) > 1e-12:
            raise ValueError("EPS_HISTORY_NOT_COMPARABLE")
    elif action_type not in {"SPLIT", "CONSOLIDATION"}:
        raise ValueError("EPS_HISTORY_NOT_COMPARABLE")
    return float(new_shares / old_shares)


def adjust_historical_eps_for_actions(
    eps_history: pd.DataFrame,
    actions: pd.DataFrame,
    event_date: pd.Timestamp,
) -> pd.DataFrame:
    """Adjust pre-action historical per-share EPS using only PIT-known actions."""

    result = eps_history.copy()
    if result.empty or actions is None or actions.empty:
        return result
    required = {"Symbol", "Action_Type", "Ex_Date"}
    missing = required.difference(actions.columns)
    if missing:
        raise ValueError(f"EPS_HISTORY_NOT_COMPARABLE: actions missing {sorted(missing)}")
    result["Fiscal_Period_End"] = result["Fiscal_Period_End"].map(_date)
    result["EPS"] = pd.to_numeric(result["EPS"], errors="coerce")
    event_day = _date(event_date)
    symbols = set(result["Symbol"].astype(str).str.upper())
    relevant = actions.loc[actions["Symbol"].astype(str).str.upper().isin(symbols)].copy()
    relevant["Ex_Date"] = relevant["Ex_Date"].map(_date)
    relevant = relevant.loc[relevant["Ex_Date"].notna() & relevant["Ex_Date"].le(event_day)]
    for _, action in relevant.sort_values("Ex_Date").iterrows():
        action_type = str(action.get("Action_Type") or "").upper()
        if action_type not in {"SPLIT", "BONUS", "CONSOLIDATION"}:
            continue
        factor = _action_factor(action)
        mask = (
            result["Symbol"].astype(str).str.upper().eq(str(action["Symbol"]).upper())
            & result["Fiscal_Period_End"].lt(action["Ex_Date"])
        )
        result.loc[mask, "EPS"] = result.loc[mask, "EPS"] / factor
    return result


def _history_for_event(
    event: pd.Series,
    eps_history: pd.DataFrame,
    actions: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    required = {"Symbol", "Fiscal_Period_End", "Reporting_Basis", "EPS"}
    missing = required.difference(eps_history.columns)
    if missing:
        return pd.DataFrame(), f"MISSING_EPS_COLUMNS:{sorted(missing)}"
    symbol = str(event.get("Symbol") or "").upper().strip()
    basis = str(event.get("Reporting_Basis") or event.get("Selected_Basis") or "").upper().strip()
    current_period = _date(event.get("Fiscal_Period_End"))
    current_public = _timestamp(event.get("Event_Public_Timestamp", event.get("Event_Public_Date")))
    history = eps_history.copy()
    history["Symbol"] = history["Symbol"].astype(str).str.upper().str.strip()
    history["Reporting_Basis"] = history["Reporting_Basis"].fillna("").astype(str).str.upper().str.strip()
    history["Fiscal_Period_End"] = history["Fiscal_Period_End"].map(_date)
    history["EPS"] = pd.to_numeric(history["EPS"], errors="coerce")
    history = history.loc[
        history["Symbol"].eq(symbol)
        & history["Reporting_Basis"].eq(basis)
        & history["Fiscal_Period_End"].notna()
        & history["EPS"].notna()
    ].copy()
    if "Original_or_Revised" in history:
        history = history.loc[history["Original_or_Revised"].fillna("").astype(str).str.upper().eq("ORIGINAL")]
    if "Public_Timestamp" in history:
        history["_Public_Timestamp"] = history["Public_Timestamp"].map(_timestamp)
        future = history.loc[history["_Public_Timestamp"].gt(current_public)]
        history = history.loc[history["_Public_Timestamp"].le(current_public)]
    else:
        future = pd.DataFrame()
    history = history.loc[history["Fiscal_Period_End"].le(current_period)].copy()
    if history.empty:
        return history, "FUTURE_EPS_USED" if not future.empty else "MISSING_CURRENT_EPS"
    history = history.sort_values(["Fiscal_Period_End", "_Public_Timestamp"], kind="stable")
    duplicate_periods = history["Fiscal_Period_End"].duplicated(keep=False)
    if duplicate_periods.any():
        duplicate_values = history.loc[duplicate_periods].groupby("Fiscal_Period_End")["EPS"].agg(["min", "max"])
        if (
            ~duplicate_values.apply(
                lambda row: eps_values_match(row["max"], row["min"]), axis=1
            )
        ).any():
            return pd.DataFrame(), "CROSS_EXCHANGE_EPS_MISMATCH"
        history = history.drop_duplicates("Fiscal_Period_End", keep="first")
    try:
        history = adjust_historical_eps_for_actions(history, actions, _date(event.get("Event_Public_Date", current_public)))
    except ValueError as exc:
        return pd.DataFrame(), str(exc)
    return history, ""


def basis_chain_status(
    symbol: str,
    period_end: pd.Timestamp,
    basis: str,
    event_timestamp: pd.Timestamp,
    eps: pd.DataFrame,
    actions: pd.DataFrame,
) -> tuple[bool, str]:
    """Validate the complete point-in-time comparable SUE chain for one basis."""

    if "Public_Timestamp" not in eps.columns:
        return False, "MISSING_EPS_PUBLIC_TIMESTAMP"
    event = pd.Series(
        {
            "Event_ID": "",
            "Symbol": symbol,
            "Fiscal_Period_End": period_end,
            "Event_Public_Timestamp": event_timestamp,
            "Event_Public_Date": _date(event_timestamp),
            "Reporting_Basis": basis,
        }
    )
    history, reason = _history_for_event(event, eps, actions)
    if history.empty:
        return False, reason or "INSUFFICIENT_EPS_HISTORY"
    current_idx = _quarter_index(period_end)
    if current_idx is None:
        return False, "INVALID_FISCAL_QUARTER"
    by_index = {
        _quarter_index(period): float(value)
        for period, value in zip(history["Fiscal_Period_End"], history["EPS"])
        if _quarter_index(period) is not None
    }
    required_indices = [current_idx - offset for offset in range(0, 13)]
    if any(index not in by_index for index in required_indices):
        return False, "INSUFFICIENT_EPS_HISTORY"
    return True, ""


def compute_sue_for_event(
    event: pd.Series,
    eps_history: pd.DataFrame,
    actions: pd.DataFrame,
) -> tuple[dict[str, object] | None, str]:
    """Compute one event's causal eight-change SUE chain."""

    history, reason = _history_for_event(event, eps_history, actions)
    if history.empty:
        return None, reason or "INSUFFICIENT_EPS_HISTORY"
    current_period = _date(event.get("Fiscal_Period_End"))
    current_idx = _quarter_index(current_period)
    if current_idx is None:
        return None, "INVALID_FISCAL_QUARTER"
    by_index = {
        _quarter_index(period): float(eps)
        for period, eps in zip(history["Fiscal_Period_End"], history["EPS"])
        if _quarter_index(period) is not None
    }
    if current_idx not in by_index:
        return None, "MISSING_CURRENT_EPS"
    required_indices = [current_idx - offset for offset in range(0, 13)]
    missing = [index for index in required_indices if index not in by_index]
    if missing:
        return None, "INSUFFICIENT_EPS_HISTORY"
    current_eps = by_index[current_idx]
    eps_t_minus_4 = by_index[current_idx - 4]
    d_current = current_eps - eps_t_minus_4
    prior_changes = pd.Series(
        [by_index[current_idx - offset] - by_index[current_idx - offset - 4] for offset in range(1, 9)],
        dtype=float,
    )
    arithmetic = _sue_from_changes(d_current, prior_changes)
    if not np.isfinite(arithmetic["Historical_SD"]) or arithmetic["Historical_SD"] <= 0:
        return None, "ZERO_HISTORICAL_SUE_SD"
    row: dict[str, object] = {
        "Event_ID": event.get("Event_ID", ""),
        "Symbol": str(event.get("Symbol", "")).upper(),
        "Fiscal_Period_End": current_period,
        "Event_Public_Date": _date(event.get("Event_Public_Date", event.get("Event_Public_Timestamp"))),
        "Reporting_Basis": str(event.get("Reporting_Basis") or event.get("Selected_Basis") or "").upper(),
        "Current_EPS": current_eps,
        "EPS_t_minus_4": eps_t_minus_4,
        "D_t": d_current,
        **arithmetic,
    }
    for offset in range(1, 9):
        row[f"D_t_minus_{offset}"] = float(prior_changes.iloc[offset - 1])
    row["Cohort"] = classify_sue(float(arithmetic["SUE"]))
    return row, ""


def classify_sue(value: float) -> str:
    """Apply the exact frozen SUE cohort intervals."""

    if not np.isfinite(value):
        raise ValueError("SUE must be finite")
    if value >= 1.0:
        return "POSITIVE_SURPRISE"
    if value >= 0.5:
        return "POSITIVE_BUFFER"
    if value > -0.5:
        return "NEUTRAL_CONTROL"
    if value > -1.0:
        return "NEGATIVE_BUFFER"
    return "NEGATIVE_CONTROL"


def build_sue_events(
    event_master: pd.DataFrame,
    eps_snapshot: pd.DataFrame,
    actions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build EPS-history, finite-SUE, classified-cohort, and SUE-exclusion evidence."""

    successful: list[dict[str, object]] = []
    exclusions: list[dict[str, object]] = []
    for _, event in event_master.iterrows():
        eligible, eligibility_reason = formal_event_eligibility(event)
        if not eligible:
            continue
        row, reason = compute_sue_for_event(event, eps_snapshot, actions)
        if row is not None:
            successful.append(row)
        else:
            exclusions.append(
                {
                    "Event_ID": event.get("Event_ID", ""),
                    "Symbol": str(event.get("Symbol", "")).upper(),
                    "Fiscal_Period_End": _date(event.get("Fiscal_Period_End")),
                    "Event_Public_Date": _date(event.get("Event_Public_Date")),
                    "Reason": reason or "INSUFFICIENT_EPS_HISTORY",
                    "Exclusion_Stage": "SUE",
                }
            )
    history_columns = [
        "Event_ID",
        "Symbol",
        "Fiscal_Period_End",
        "Event_Public_Date",
        "Reporting_Basis",
        "Current_EPS",
        "EPS_t_minus_4",
        "D_t",
        *[f"D_t_minus_{offset}" for offset in range(1, 9)],
        "Historical_Mean",
        "Historical_SD",
        "SUE",
        "Cohort",
    ]
    history = pd.DataFrame(successful, columns=history_columns)
    sue_events = history.copy()
    cohorts = history.copy()
    sue_exclusions = pd.DataFrame(
        exclusions,
        columns=["Event_ID", "Symbol", "Fiscal_Period_End", "Event_Public_Date", "Reason", "Exclusion_Stage"],
    )
    return history, sue_events, cohorts, sue_exclusions


def write_sue_outputs(output_dir: Path, history: pd.DataFrame, sue_events: pd.DataFrame, cohorts: pd.DataFrame) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    history.to_csv(output_dir / "e1_eps_history.csv", index=False, date_format="%Y-%m-%d")
    sue_events.to_csv(output_dir / "e1_sue_events.csv", index=False, date_format="%Y-%m-%d")
    cohorts.to_csv(output_dir / "e1_cohort_classification.csv", index=False, date_format="%Y-%m-%d")
