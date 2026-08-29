"""Calculate frozen M1 friction, metrics, robustness, diagnostics, and gates."""

from __future__ import annotations

import json
from typing import Iterable

import numpy as np
import pandas as pd


BASE_FRICTION = 0.004
STRESS_FRICTION = 0.006
SEVERE_FRICTION = 0.008
FIRST_HALF_END = pd.Timestamp("2025-02-11")
SECOND_HALF_START = pd.Timestamp("2025-02-12")
SIGNAL_START = pd.Timestamp("2023-08-01")
SIGNAL_END = pd.Timestamp("2026-08-25")
AUDIT_COLUMNS = ("Entry_ID", "Symbol", "Violation", "Observed", "Expected")


def _audit(
    violation: str,
    *,
    entry_id: object = "",
    symbol: object = "",
    observed: object = "",
    expected: object = "",
) -> dict[str, object]:
    return {
        "Entry_ID": "" if pd.isna(entry_id) else str(entry_id),
        "Symbol": "" if pd.isna(symbol) else str(symbol),
        "Violation": violation,
        "Observed": observed,
        "Expected": expected,
    }


def _audit_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=AUDIT_COLUMNS)


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame.get(column, pd.Series(np.nan, index=frame.index)), errors="coerce")


def _ensure_columns(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column not in result:
            result[column] = pd.Series(dtype=float if column != "Entry_ID" else str)
    return result


def safe_profit_factor(values: pd.Series) -> float:
    """Return PF with explicit no-win/no-loss semantics."""

    numeric = pd.to_numeric(values, errors="coerce").dropna()
    positive = float(numeric.loc[numeric > 0].sum())
    negative = float(numeric.loc[numeric < 0].sum())
    if positive and not negative:
        return np.inf
    if negative and not positive:
        return 0.0
    if not positive and not negative:
        return np.nan
    return positive / abs(negative)


def add_setup_friction(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the locked round-trip setup-return friction values."""

    result = _ensure_columns(
        trades,
        ("Entry_ID", "Return", "Base_Net_Return", "Stress_Net_Return", "Severe_Net_Return"),
    )
    gross = _numeric(result, "Return")
    rows: list[dict[str, object]] = []
    for index, value in gross.items():
        if pd.isna(value):
            rows.append(
                _audit(
                    "INVALID_SETUP_RETURN",
                    entry_id=result.loc[index, "Entry_ID"],
                    observed=result.loc[index, "Return"],
                    expected="finite gross Return",
                )
            )
    result["Base_Net_Return"] = gross - BASE_FRICTION
    result["Stress_Net_Return"] = gross - STRESS_FRICTION
    result["Severe_Net_Return"] = gross - SEVERE_FRICTION
    return result, _audit_frame(rows)


def add_practical_friction(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply locked practical friction using entry-price cost over recomputed risk."""

    required = (
        "Entry_ID",
        "Entry_Open",
        "Structural_Stop",
        "Initial_Risk",
        "Exit_Price",
        "R_Multiple",
        "Base_Net_R",
        "Stress_Net_R",
        "Severe_Net_R",
    )
    result = _ensure_columns(trades, required)
    entry_open = _numeric(result, "Entry_Open")
    stop = _numeric(result, "Structural_Stop")
    frozen_risk = _numeric(result, "Initial_Risk")
    exit_price = _numeric(result, "Exit_Price")
    frozen_r = _numeric(result, "R_Multiple")
    recomputed_risk = entry_open - stop
    gross_r = (exit_price - entry_open) / recomputed_risk
    rows: list[dict[str, object]] = []
    for index in result.index:
        entry_id = result.loc[index, "Entry_ID"]
        if pd.isna(recomputed_risk.loc[index]) or recomputed_risk.loc[index] <= 0:
            rows.append(
                _audit(
                    "INVALID_INITIAL_RISK",
                    entry_id=entry_id,
                    observed=recomputed_risk.loc[index],
                    expected="Entry_Open - Structural_Stop > 0",
                )
            )
            continue
        if pd.isna(frozen_risk.loc[index]) or not np.isclose(
            frozen_risk.loc[index], recomputed_risk.loc[index], rtol=1e-9, atol=1e-12
        ):
            rows.append(
                _audit(
                    "INITIAL_RISK_MISMATCH",
                    entry_id=entry_id,
                    observed=frozen_risk.loc[index],
                    expected=float(recomputed_risk.loc[index]),
                )
            )
        if pd.isna(frozen_r.loc[index]) or not np.isclose(
            frozen_r.loc[index], gross_r.loc[index], rtol=1e-9, atol=1e-12
        ):
            rows.append(
                _audit(
                    "GROSS_R_MISMATCH",
                    entry_id=entry_id,
                    observed=frozen_r.loc[index],
                    expected=float(gross_r.loc[index]),
                )
            )
        if pd.isna(exit_price.loc[index]) or pd.isna(entry_open.loc[index]):
            rows.append(
                _audit(
                    "INVALID_PRACTICAL_PRICE",
                    entry_id=entry_id,
                    observed="missing Entry_Open or Exit_Price",
                    expected="finite prices",
                )
            )

    result["Initial_Risk_Recomputed"] = recomputed_risk
    result["Gross_R_Recomputed"] = gross_r
    result["Base_Net_R"] = ((exit_price - entry_open) - BASE_FRICTION * entry_open) / recomputed_risk
    result["Stress_Net_R"] = ((exit_price - entry_open) - STRESS_FRICTION * entry_open) / recomputed_risk
    result["Severe_Net_R"] = ((exit_price - entry_open) - SEVERE_FRICTION * entry_open) / recomputed_risk
    return result, _audit_frame(rows)


def _metric_prefix(prefix: str, name: str) -> str:
    return f"{prefix}{name}" if prefix else name


def _summary_values(values: pd.Series) -> tuple[int, float, float, float, float]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    return (
        int(len(numeric)),
        float(numeric.mean()) if not numeric.empty else np.nan,
        float(numeric.median()) if not numeric.empty else np.nan,
        float((numeric > 0).mean()) if not numeric.empty else np.nan,
        safe_profit_factor(numeric),
    )


def summarize_setup(trades: pd.DataFrame, prefix: str) -> dict[str, float]:
    base = _summary_values(trades.get("Base_Net_Return", pd.Series(dtype=float)))
    stress = _summary_values(trades.get("Stress_Net_Return", pd.Series(dtype=float)))
    severe = _summary_values(trades.get("Severe_Net_Return", pd.Series(dtype=float)))
    return {
        _metric_prefix(prefix, "Completed_Trades"): float(base[0]),
        _metric_prefix(prefix, "Base_Mean_Net_Return"): base[1],
        _metric_prefix(prefix, "Base_Median_Net_Return"): base[2],
        _metric_prefix(prefix, "Base_Win_Rate"): base[3],
        _metric_prefix(prefix, "Base_Net_Return_PF"): base[4],
        _metric_prefix(prefix, "Stress_Mean_Net_Return"): stress[1],
        _metric_prefix(prefix, "Stress_Net_Return_PF"): stress[4],
        _metric_prefix(prefix, "Severe_Mean_Net_Return"): severe[1],
        _metric_prefix(prefix, "Severe_Net_Return_PF"): severe[4],
    }


def summarize_practical(trades: pd.DataFrame, prefix: str) -> dict[str, float]:
    base = _summary_values(trades.get("Base_Net_R", pd.Series(dtype=float)))
    stress = _summary_values(trades.get("Stress_Net_R", pd.Series(dtype=float)))
    severe = _summary_values(trades.get("Severe_Net_R", pd.Series(dtype=float)))
    gross = _summary_values(trades.get("R_Multiple", pd.Series(dtype=float)))
    holding = pd.to_numeric(trades.get("Holding_Sessions", pd.Series(dtype=float)), errors="coerce").dropna()
    return {
        _metric_prefix(prefix, "Completed_Trades"): float(base[0]),
        _metric_prefix(prefix, "Base_Mean_Net_R"): base[1],
        _metric_prefix(prefix, "Base_Median_Net_R"): base[2],
        _metric_prefix(prefix, "Base_Win_Rate"): base[3],
        _metric_prefix(prefix, "Base_Net_R_PF"): base[4],
        _metric_prefix(prefix, "Stress_Mean_Net_R"): stress[1],
        _metric_prefix(prefix, "Stress_Net_R_PF"): stress[4],
        _metric_prefix(prefix, "Severe_Mean_Net_R"): severe[1],
        _metric_prefix(prefix, "Severe_Net_R_PF"): severe[4],
        _metric_prefix(prefix, "Gross_Mean_R"): gross[1],
        _metric_prefix(prefix, "Gross_R_PF"): gross[4],
        _metric_prefix(prefix, "Median_Holding_Sessions"): float(holding.median()) if not holding.empty else np.nan,
    }


def regime_comparison(enabled: pd.DataFrame, disabled: pd.DataFrame) -> pd.DataFrame:
    enabled_metrics = summarize_practical(enabled, "Enabled_")
    disabled_metrics = summarize_practical(disabled, "Disabled_")
    enabled_mean = enabled_metrics["Enabled_Base_Mean_Net_R"]
    disabled_mean = disabled_metrics["Disabled_Base_Mean_Net_R"]
    enabled_pf = enabled_metrics["Enabled_Base_Net_R_PF"]
    disabled_pf = disabled_metrics["Disabled_Base_Net_R_PF"]
    row = {
        "Enabled_Completed": enabled_metrics["Enabled_Completed_Trades"],
        "Disabled_Completed": disabled_metrics["Disabled_Completed_Trades"],
        "Enabled_Base_Mean_Net_R": enabled_mean,
        "Disabled_Base_Mean_Net_R": disabled_mean,
        "Enabled_Base_R_PF": enabled_pf,
        "Disabled_Base_R_PF": disabled_pf,
        "Enabled_Beats_Disabled_Mean": bool(pd.notna(enabled_mean) and pd.notna(disabled_mean) and enabled_mean > disabled_mean),
        "Enabled_Beats_Disabled_R_PF": bool(pd.notna(enabled_pf) and pd.notna(disabled_pf) and enabled_pf > disabled_pf),
    }
    return pd.DataFrame([row])


def _period_for_date(date: pd.Timestamp) -> str | None:
    if pd.isna(date):
        return None
    if SIGNAL_START <= date <= FIRST_HALF_END:
        return "FIRST_HALF"
    if SECOND_HALF_START <= date <= SIGNAL_END:
        return "SECOND_HALF"
    return None


def _summary_frame(trades: pd.DataFrame, group_column: str, groups: list[object]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for group in groups:
        selected = trades.loc[trades[group_column].eq(group)]
        values = pd.to_numeric(selected.get("Base_Net_R", pd.Series(dtype=float)), errors="coerce").dropna()
        rows.append(
            {
                group_column: group,
                "Completed_Trades": int(len(values)),
                "Mean_Base_Net_R": float(values.mean()) if not values.empty else np.nan,
                "Base_R_PF": safe_profit_factor(values),
                "Winners": int((values > 0).sum()),
                "Win_Rate": float((values > 0).mean()) if not values.empty else np.nan,
            }
        )
    return pd.DataFrame(rows)


def temporal_summary(enabled_practical: pd.DataFrame) -> pd.DataFrame:
    frame = enabled_practical.copy()
    frame["Signal_Date"] = pd.to_datetime(frame.get("Signal_Date"), errors="coerce")
    frame["Period"] = frame["Signal_Date"].map(_period_for_date)
    return _summary_frame(frame, "Period", ["FIRST_HALF", "SECOND_HALF"])


def year_summary(enabled_practical: pd.DataFrame) -> pd.DataFrame:
    frame = enabled_practical.copy()
    frame["Signal_Date"] = pd.to_datetime(frame.get("Signal_Date"), errors="coerce")
    frame["Signal_Year"] = frame["Signal_Date"].dt.year.astype("Int64")
    years = sorted(frame["Signal_Year"].dropna().astype(int).unique().tolist())
    return _summary_frame(frame, "Signal_Year", years)


def top_five_robustness(enabled_practical: pd.DataFrame) -> pd.DataFrame:
    columns = ["Removed_Entry_IDs", "Remaining_Completed", "Remaining_Mean_Base_Net_R", "Remaining_Base_R_PF"]
    if enabled_practical.empty:
        return pd.DataFrame([{column: ("" if column == "Removed_Entry_IDs" else np.nan) for column in columns}])
    frame = enabled_practical.copy()
    rank = pd.to_numeric(frame.get("R_Multiple", frame.get("Gross_R_Recomputed")), errors="coerce")
    frame["_gross_rank"] = rank
    frame["_entry_sort"] = frame.get("Entry_ID", pd.Series(index=frame.index, dtype=str)).astype(str)
    removed = frame.sort_values(["_gross_rank", "_entry_sort"], ascending=[False, True], na_position="last").head(5)
    remaining = frame.loc[~frame.index.isin(removed.index)]
    values = pd.to_numeric(remaining.get("Base_Net_R", pd.Series(dtype=float)), errors="coerce").dropna()
    return pd.DataFrame(
        [
            {
                "Removed_Entry_IDs": ";".join(removed.get("Entry_ID", pd.Series(dtype=str)).astype(str)),
                "Remaining_Completed": int(len(values)),
                "Remaining_Mean_Base_Net_R": float(values.mean()) if not values.empty else np.nan,
                "Remaining_Base_R_PF": safe_profit_factor(values),
            }
        ]
    )


def leave_one_symbol_out(enabled_practical: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    symbols = sorted(enabled_practical.get("Symbol", pd.Series(dtype=str)).dropna().astype(str).unique())
    for symbol in symbols:
        remaining = enabled_practical.loc[enabled_practical["Symbol"].astype(str).ne(symbol)]
        values = pd.to_numeric(remaining.get("Base_Net_R", pd.Series(dtype=float)), errors="coerce").dropna()
        rows.append(
            {
                "Omitted_Symbol": symbol,
                "Remaining_Completed": int(len(values)),
                "Mean_Base_Net_R": float(values.mean()) if not values.empty else np.nan,
                "Base_R_PF": safe_profit_factor(values),
            }
        )
    return pd.DataFrame(rows, columns=["Omitted_Symbol", "Remaining_Completed", "Mean_Base_Net_R", "Base_R_PF"])


def _metric_rows(metrics: dict[str, object]) -> list[dict[str, object]]:
    return [
        {"Metric": key, "Dimension": "", "Value": value}
        for key, value in metrics.items()
    ]


def overlap_capacity_diagnostic(
    enabled_classification: pd.DataFrame,
    enabled_entries: pd.DataFrame,
    enabled_practical: pd.DataFrame,
    canonical_sessions: pd.DatetimeIndex,
    sector_mapping: pd.DataFrame,
) -> pd.DataFrame:
    """Report overlap/capacity evidence without feeding it into any gate."""

    accepted_ids = set(enabled_entries.get("Entry_ID", pd.Series(dtype=str)).dropna().astype(str))
    completed_ids = set(enabled_practical.get("Entry_ID", pd.Series(dtype=str)).dropna().astype(str))
    classification = enabled_classification.copy()
    entries = enabled_entries.copy()
    practical = enabled_practical.copy()
    if "Signal_Date" in classification:
        classification["Signal_Date"] = pd.to_datetime(classification["Signal_Date"], errors="coerce")
    for frame in (entries, practical):
        for column in ("Entry_Date", "Exit_Date"):
            if column in frame:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")

    session_index = pd.DatetimeIndex(pd.to_datetime(canonical_sessions, errors="coerce"))
    session_index = session_index.dropna().drop_duplicates().sort_values()
    simultaneous_counts: list[int] = []
    known_lifecycles = 0
    for _, row in practical.iterrows():
        entry_date = row.get("Entry_Date")
        exit_date = row.get("Exit_Date")
        if pd.isna(entry_date) or pd.isna(exit_date):
            continue
        known_lifecycles += 1
        if entry_date == exit_date:
            active_sessions = session_index[session_index.eq(entry_date)]
        else:
            active_sessions = session_index[(session_index >= entry_date) & (session_index < exit_date)]
        simultaneous_counts.extend(active_sessions.tolist())
    session_counts = pd.Series(simultaneous_counts).value_counts() if simultaneous_counts else pd.Series(dtype=int)
    max_simultaneous = int(session_counts.max()) if not session_counts.empty else 0
    completed_count = len(completed_ids)

    qualified_counts = (
        classification.groupby("Signal_Date").size()
        if "Signal_Date" in classification and not classification.empty
        else pd.Series(dtype=int)
    )
    accepted_entry_dates = (
        entries.groupby("Entry_Date").size()
        if "Entry_Date" in entries and not entries.empty
        else pd.Series(dtype=int)
    )
    qualified_distribution = (
        {str(int(count)): int((qualified_counts == count).sum()) for count in sorted(qualified_counts.unique())}
        if not qualified_counts.empty
        else {}
    )

    risk = _numeric(entries, "Initial_Risk")
    entry_open = _numeric(entries, "Entry_Open")
    risk_fraction = risk / entry_open
    implied_weight = 0.01 / risk_fraction

    mapping = sector_mapping.copy()
    if {"Stock", "Sector_Key"}.issubset(mapping.columns):
        mapping = mapping.drop_duplicates("Stock").set_index("Stock")
        mapped_mask = entries.get("Symbol", pd.Series(dtype=str)).astype(str).isin(mapping.index.astype(str))
        mapped_entries = entries.loc[mapped_mask].copy()
        mapped_entries["Sector_Key"] = mapped_entries["Symbol"].astype(str).map(
            {str(index): value for index, value in mapping["Sector_Key"].items()}
        )
    else:
        mapped_entries = entries.iloc[0:0].copy()
        mapped_mask = pd.Series(False, index=entries.index)

    metrics = {
        "ENABLED_ACCEPTED_ENTRIES": float(len(accepted_ids)),
        "ENABLED_COMPLETED_TRADES": float(completed_count),
        "ENABLED_INCOMPLETE_ACCEPTED": float(len(accepted_ids - completed_ids)),
        "MAX_SIMULTANEOUS_COMPLETED_LIFECYCLES": float(max_simultaneous),
        "SIMULTANEOUS_LIFECYCLE_COVERAGE_PERCENT": float(100.0 * known_lifecycles / completed_count) if completed_count else np.nan,
        "MAX_SAME_DAY_ENABLED_QUALIFIED_SIGNALS": float(qualified_counts.max()) if not qualified_counts.empty else 0.0,
        "MAX_SAME_DAY_ENABLED_ACCEPTED_ENTRIES": float(accepted_entry_dates.max()) if not accepted_entry_dates.empty else 0.0,
        "SAME_DAY_ENABLED_QUALIFIED_DISTRIBUTION_JSON": json.dumps(qualified_distribution, sort_keys=True),
        "MEDIAN_INITIAL_RISK_FRACTION": float(risk_fraction.median()) if risk_fraction.notna().any() else np.nan,
        "MEDIAN_IMPLIED_POSITION_WEIGHT": float(implied_weight.median()) if implied_weight.notna().any() else np.nan,
        "MAX_IMPLIED_POSITION_WEIGHT": float(implied_weight.max()) if implied_weight.notna().any() else np.nan,
        "MAPPED_ACCEPTED_ENTRIES": float(mapped_mask.sum()),
        "UNMAPPED_ACCEPTED_ENTRIES": float((~mapped_mask).sum()),
        "MAPPING_COVERAGE_PERCENT": float(100.0 * mapped_mask.mean()) if len(mapped_mask) else np.nan,
    }
    rows = _metric_rows(metrics)
    if not mapped_entries.empty:
        for sector, count in mapped_entries["Sector_Key"].astype(str).value_counts().sort_index().items():
            rows.append({"Metric": "SECTOR_ENTRY_COUNT", "Dimension": sector, "Value": float(count)})
    return pd.DataFrame(rows, columns=["Metric", "Dimension", "Value"])


def _value_from_frame(frame: pd.DataFrame, column: str) -> object:
    if frame.empty or column not in frame.columns:
        return np.nan
    return frame.iloc[0].get(column, np.nan)


def _available(value: object) -> bool:
    return pd.notna(value)


def evaluate_gates(
    setup_metrics: dict[str, float],
    practical_metrics: dict[str, float],
    comparison: pd.DataFrame,
    temporal: pd.DataFrame,
    top_five: pd.DataFrame,
    loso: pd.DataFrame,
    completed_enabled: int,
    integrity_violations: int,
) -> tuple[str, pd.DataFrame]:
    """Evaluate only the predeclared strategy gates in their frozen order."""

    comparison_available = (
        not comparison.empty
        and all(
            _available(_value_from_frame(comparison, column))
            for column in (
                "Enabled_Base_Mean_Net_R",
                "Disabled_Base_Mean_Net_R",
                "Enabled_Base_R_PF",
                "Disabled_Base_R_PF",
            )
        )
    )
    first = temporal.loc[temporal.get("Period", pd.Series(dtype=str)).eq("FIRST_HALF")] if not temporal.empty else pd.DataFrame()
    second = temporal.loc[temporal.get("Period", pd.Series(dtype=str)).eq("SECOND_HALF")] if not temporal.empty else pd.DataFrame()
    top = top_five.iloc[0] if not top_five.empty else pd.Series(dtype=object)

    checks: list[tuple[str, bool, object, str]] = [
        ("INTEGRITY_ZERO", integrity_violations == 0, integrity_violations, "== 0"),
        ("SAMPLE_SUFFICIENCY", completed_enabled >= 300, completed_enabled, ">= 300"),
        ("BASE_SETUP_MEAN", setup_metrics.get("Base_Mean_Net_Return", np.nan) > 0, setup_metrics.get("Base_Mean_Net_Return", np.nan), "> 0"),
        ("BASE_SETUP_PF", setup_metrics.get("Base_Net_Return_PF", np.nan) >= 1.20, setup_metrics.get("Base_Net_Return_PF", np.nan), ">= 1.20"),
        ("BASE_PRACTICAL_MEAN_R", practical_metrics.get("Base_Mean_Net_R", np.nan) >= 0.15, practical_metrics.get("Base_Mean_Net_R", np.nan), ">= 0.15"),
        ("BASE_PRACTICAL_R_PF", practical_metrics.get("Base_Net_R_PF", np.nan) >= 1.20, practical_metrics.get("Base_Net_R_PF", np.nan), ">= 1.20"),
        ("STRESS_PRACTICAL_MEAN_R", practical_metrics.get("Stress_Mean_Net_R", np.nan) > 0, practical_metrics.get("Stress_Mean_Net_R", np.nan), "> 0"),
        ("STRESS_PRACTICAL_R_PF", practical_metrics.get("Stress_Net_R_PF", np.nan) > 1.00, practical_metrics.get("Stress_Net_R_PF", np.nan), "> 1.00"),
        ("REGIME_MEAN_DISCRIMINATION", bool(_value_from_frame(comparison, "Enabled_Beats_Disabled_Mean")) if comparison_available else False, _value_from_frame(comparison, "Enabled_Base_Mean_Net_R"), "enabled > disabled"),
        ("REGIME_RPF_DISCRIMINATION", bool(_value_from_frame(comparison, "Enabled_Beats_Disabled_R_PF")) if comparison_available else False, _value_from_frame(comparison, "Enabled_Base_R_PF"), "enabled > disabled"),
        ("TEMPORAL_FIRST_MEAN_R", bool(not first.empty and first.iloc[0].get("Mean_Base_Net_R", np.nan) > 0), _value_from_frame(first, "Mean_Base_Net_R"), "> 0"),
        ("TEMPORAL_FIRST_R_PF", bool(not first.empty and first.iloc[0].get("Base_R_PF", np.nan) > 1.00), _value_from_frame(first, "Base_R_PF"), "> 1.00"),
        ("TEMPORAL_SECOND_MEAN_R", bool(not second.empty and second.iloc[0].get("Mean_Base_Net_R", np.nan) > 0), _value_from_frame(second, "Mean_Base_Net_R"), "> 0"),
        ("TEMPORAL_SECOND_R_PF", bool(not second.empty and second.iloc[0].get("Base_R_PF", np.nan) > 1.00), _value_from_frame(second, "Base_R_PF"), "> 1.00"),
        ("TOP_FIVE_REMOVED_MEAN_R", bool(not top.empty and top.get("Remaining_Mean_Base_Net_R", np.nan) > 0), top.get("Remaining_Mean_Base_Net_R", np.nan), "> 0"),
        ("TOP_FIVE_REMOVED_R_PF", bool(not top.empty and top.get("Remaining_Base_R_PF", np.nan) > 1.00), top.get("Remaining_Base_R_PF", np.nan), "> 1.00"),
        ("LOSO_ALL_MEAN_R", bool(not loso.empty and pd.to_numeric(loso.get("Mean_Base_Net_R"), errors="coerce").gt(0).all()), len(loso), "> 0 for every omission"),
        ("LOSO_ALL_R_PF", bool(not loso.empty and pd.to_numeric(loso.get("Base_R_PF"), errors="coerce").gt(1.00).all()), len(loso), "> 1.00 for every omission"),
    ]
    rows = [
        {
            "Gate": gate,
            "Pass": bool(passed) if pd.notna(passed) else False,
            "Mandatory": True,
            "Value": value,
            "Threshold": threshold,
            "Status": "PASS" if bool(passed) else "FAIL",
        }
        for gate, passed, value, threshold in checks
    ]
    strategy_gates_pass = all(row["Pass"] for row in rows[1:])
    if integrity_violations > 0:
        status = "INVALID_RESEARCH_RUN"
    elif completed_enabled < 300 or not comparison_available:
        status = "INSUFFICIENT_EVIDENCE"
    elif strategy_gates_pass:
        status = "PASS"
    else:
        status = "FAIL"
    rows.append(
        {
            "Gate": "FINAL_STATUS",
            "Pass": status == "PASS",
            "Mandatory": False,
            "Value": status,
            "Threshold": "status precedence",
            "Status": status,
        }
    )
    return status, pd.DataFrame(rows, columns=["Gate", "Pass", "Mandatory", "Value", "Threshold", "Status"])
