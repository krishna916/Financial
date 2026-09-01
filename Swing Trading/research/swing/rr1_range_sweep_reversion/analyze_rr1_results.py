"""RR1 metrics, robustness diagnostics, formal gates, and report rendering."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

from constants import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    FIRST_HALF_END,
    MIN_HALF_COMPLETED,
    MIN_LOWER_COMPLETED,
    MIN_UPPER_COMPLETED,
    SECOND_HALF_START,
)


def _numeric(values: Iterable[object]) -> np.ndarray:
    return pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)


def profit_factor(values: pd.Series) -> float:
    x = _numeric(values)
    x = x[np.isfinite(x)]
    winners = float(x[x > 0.0].sum())
    losers = float(abs(x[x < 0.0].sum()))
    if losers == 0.0:
        return float("inf") if winners > 0.0 else float("nan")
    return winners / losers


def _mean(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns or frame.empty:
        return float("nan")
    values = pd.to_numeric(frame[column], errors="coerce")
    return float(values.mean()) if values.notna().any() else float("nan")


def summarize_lens_a(trades: pd.DataFrame) -> dict[str, float]:
    return {
        "Count": float(len(trades)),
        "Gross_Mean_Return": _mean(trades, "Gross_Return"),
        "Gross_Return_PF": profit_factor(trades["Gross_Return"]) if "Gross_Return" in trades else float("nan"),
        "Base_Net_Mean_Return": _mean(trades, "Base_Net_Return"),
        "Base_Net_Return_PF": profit_factor(trades["Base_Net_Return"]) if "Base_Net_Return" in trades else float("nan"),
        "Stress_Net_Mean_Return": _mean(trades, "Stress_Net_Return"),
        "Stress_Net_Return_PF": profit_factor(trades["Stress_Net_Return"]) if "Stress_Net_Return" in trades else float("nan"),
        "Severe_Net_Mean_Return": _mean(trades, "Severe_Net_Return"),
        "Severe_Net_Return_PF": profit_factor(trades["Severe_Net_Return"]) if "Severe_Net_Return" in trades else float("nan"),
        "Mean_Base_Excess_Return": _mean(trades, "Base_Excess_Return"),
    }


def summarize_practical(trades: pd.DataFrame) -> dict[str, float]:
    return {
        "Count": float(len(trades)),
        "Gross_Mean_Return": _mean(trades, "Gross_Return"),
        "Base_Net_Mean_Return": _mean(trades, "Base_Net_Return"),
        "Stress_Net_Mean_Return": _mean(trades, "Stress_Net_Return"),
        "Severe_Net_Mean_Return": _mean(trades, "Severe_Net_Return"),
        "Gross_Mean_R": _mean(trades, "Gross_R"),
        "Base_Practical_Mean_R": _mean(trades, "Base_Net_R"),
        "Stress_Practical_Mean_R": _mean(trades, "Stress_Net_R"),
        "Severe_Practical_Mean_R": _mean(trades, "Severe_Net_R"),
        "Base_Practical_R_PF": profit_factor(trades["Base_Net_R"]) if "Base_Net_R" in trades else float("nan"),
        "Stress_Practical_R_PF": profit_factor(trades["Stress_Net_R"]) if "Stress_Net_R" in trades else float("nan"),
        "Severe_Practical_R_PF": profit_factor(trades["Severe_Net_R"]) if "Severe_Net_R" in trades else float("nan"),
        "Mean_Base_Practical_Excess_Return": _mean(trades, "Base_Practical_Excess_Return"),
        "Practical_Median_R": (
            float(pd.to_numeric(trades["Base_Net_R"], errors="coerce").median())
            if "Base_Net_R" in trades and pd.to_numeric(trades["Base_Net_R"], errors="coerce").notna().any()
            else float("nan")
        ),
    }


def bootstrap_mean_ci(
    values: np.ndarray | Iterable[object],
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> tuple[float, float]:
    x = _numeric(values)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = np.empty(resamples, dtype=float)
    for index in range(resamples):
        means[index] = rng.choice(x, size=len(x), replace=True).mean()
    return tuple(np.quantile(means, [0.025, 0.975]))


def bootstrap_mean_difference_ci(
    lower: np.ndarray | Iterable[object],
    upper: np.ndarray | Iterable[object],
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> tuple[float, float]:
    lower_x = _numeric(lower)
    upper_x = _numeric(upper)
    lower_x = lower_x[np.isfinite(lower_x)]
    upper_x = upper_x[np.isfinite(upper_x)]
    if len(lower_x) == 0 or len(upper_x) == 0:
        return float("nan"), float("nan")

    rng = np.random.default_rng(seed)
    differences = np.empty(resamples, dtype=float)
    for index in range(resamples):
        lower_star = rng.choice(lower_x, size=len(lower_x), replace=True)
        upper_star = rng.choice(upper_x, size=len(upper_x), replace=True)
        differences[index] = lower_star.mean() - upper_star.mean()
    return tuple(np.quantile(differences, [0.025, 0.975]))


def _paired_lens_a(practical: pd.DataFrame, lens_a: pd.DataFrame) -> pd.DataFrame:
    if practical.empty or lens_a.empty:
        return practical.iloc[0:0].copy()
    ids = set(practical["Entry_ID"]) & set(lens_a["Entry_ID"])
    return lens_a.loc[lens_a["Entry_ID"].isin(ids)].copy()


def build_temporal_summary(practical: pd.DataFrame, lens_a: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    practical_dates = pd.to_datetime(practical.get("Signal_Date", pd.Series(dtype="datetime64[ns]")))
    lens_dates = pd.to_datetime(lens_a.get("Signal_Date", pd.Series(dtype="datetime64[ns]")))
    for label, mask, lens_mask in [
        ("FIRST", practical_dates <= FIRST_HALF_END, lens_dates <= FIRST_HALF_END),
        ("SECOND", practical_dates >= SECOND_HALF_START, lens_dates >= SECOND_HALF_START),
    ]:
        practical_part = practical.loc[mask] if len(practical_dates) else practical.iloc[0:0]
        lens_part = lens_a.loc[lens_mask] if len(lens_dates) else lens_a.iloc[0:0]
        lens_part = _paired_lens_a(practical_part, lens_part)
        p = summarize_practical(practical_part)
        a = summarize_lens_a(lens_part)
        rows.append(
            {
                "Half": label,
                "Completed_Paired_Lower": int(len(practical_part)),
                "Base_Practical_Mean_R": p["Base_Practical_Mean_R"],
                "Base_Practical_R_PF": p["Base_Practical_R_PF"],
                "Mean_Base_Practical_Excess_Return": p["Mean_Base_Practical_Excess_Return"],
                "Lens_A_Base_Net_Mean_Return": a["Base_Net_Mean_Return"],
            }
        )
    return pd.DataFrame(rows)


def _robustness_row(label: str, frame: pd.DataFrame) -> dict[str, object]:
    summary = summarize_practical(frame)
    return {
        "Removed": label,
        "Remaining_Count": int(len(frame)),
        "Base_Practical_Mean_R": summary["Base_Practical_Mean_R"],
        "Base_Practical_R_PF": summary["Base_Practical_R_PF"],
    }


def build_top_five_robustness(practical: pd.DataFrame) -> pd.DataFrame:
    if practical.empty:
        return pd.DataFrame([_robustness_row("TOP_FIVE_GROSS_R_WINNERS", practical)])
    winners = practical["Gross_R"].nlargest(min(5, len(practical))).index
    return pd.DataFrame(
        [_robustness_row("TOP_FIVE_GROSS_R_WINNERS", practical.drop(index=winners))]
    )


def build_leave_one_year_out(practical: pd.DataFrame) -> pd.DataFrame:
    if practical.empty:
        return pd.DataFrame(columns=["Removed_Year", "Remaining_Count", "Base_Practical_Mean_R", "Base_Practical_R_PF"])
    years = pd.to_datetime(practical["Signal_Date"]).dt.year
    rows = []
    for year in sorted(years.dropna().unique()):
        rows.append(_robustness_row(str(int(year)), practical.loc[years.ne(year)]))
    return pd.DataFrame(rows).rename(columns={"Removed": "Removed_Year"})


def build_leave_one_symbol_out(practical: pd.DataFrame) -> pd.DataFrame:
    if practical.empty:
        return pd.DataFrame(columns=["Removed_Symbol", "Remaining_Count", "Base_Practical_Mean_R", "Base_Practical_R_PF"])
    rows = []
    for symbol in sorted(practical["Symbol"].astype(str).unique()):
        rows.append(_robustness_row(symbol, practical.loc[practical["Symbol"].astype(str).ne(symbol)]))
    return pd.DataFrame(rows).rename(columns={"Removed": "Removed_Symbol"})


def build_overlap_diagnostic(
    entries: pd.DataFrame, sessions: pd.DatetimeIndex | None = None
) -> pd.DataFrame:
    if entries.empty:
        return pd.DataFrame(
            {
                "Metric": [
                    "Max_Concurrent_Accepted_Lower",
                    "Average_Concurrent_Accepted_Lower",
                    "Max_Same_Day_Entries",
                    "Overlap_Percentage",
                    "Rough_Capital_Risk_Count",
                ],
                "Value": [0.0] * 5,
            }
        )
    index = (
        pd.DatetimeIndex(pd.to_datetime(sessions)).normalize().drop_duplicates().sort_values()
        if sessions is not None
        else pd.DatetimeIndex(
            sorted(
                set(pd.to_datetime(entries["Entry_Date"]).dt.normalize())
                | set(pd.to_datetime(entries["Scheduled_Exit_Date"]).dropna().dt.normalize())
            )
        )
    )
    counts = pd.Series(0, index=index, dtype=float)
    same_day = pd.to_datetime(entries["Entry_Date"]).dt.normalize().value_counts()
    for _, entry in entries.iterrows():
        start = pd.Timestamp(entry["Entry_Date"]).normalize()
        end = pd.Timestamp(entry["Scheduled_Exit_Date"]).normalize() if pd.notna(entry["Scheduled_Exit_Date"]) else pd.Timestamp.max
        counts.loc[(counts.index >= start) & (counts.index < end)] += 1
    active = counts[counts > 0]
    overlap = float((active > 1).mean() * 100.0) if len(active) else 0.0
    max_concurrent = float(counts.max()) if len(counts) else 0.0
    return pd.DataFrame(
        {
            "Metric": [
                "Max_Concurrent_Accepted_Lower",
                "Average_Concurrent_Accepted_Lower",
                "Max_Same_Day_Entries",
                "Overlap_Percentage",
                "Rough_Capital_Risk_Count",
            ],
            "Value": [
                max_concurrent,
                float(active.mean()) if len(active) else 0.0,
                float(same_day.max()) if len(same_day) else 0.0,
                overlap,
                max_concurrent,
            ],
        }
    )


def _finite_metric(evidence: dict[str, object], key: str) -> float:
    try:
        return float(evidence[key])
    except (KeyError, TypeError, ValueError):
        return float("nan")


def _passed(value: bool) -> bool:
    return bool(value)


def _gate(name: str, passed: bool, observed: object, requirement: str, category: str) -> dict[str, object]:
    return {
        "Gate": name,
        "Passed": _passed(passed),
        "Observed": observed,
        "Requirement": requirement,
        "Category": category,
    }


def evaluate_gates(evidence: dict[str, object]) -> tuple[pd.DataFrame, str]:
    integrity_ok = bool(evidence.get("integrity_ok", False))
    lower_count = int(evidence.get("lower_count", 0))
    first_count = int(evidence.get("first_count", 0))
    second_count = int(evidence.get("second_count", 0))
    upper_count = int(evidence.get("upper_count", 0))
    rows = [
        _gate("RESEARCH_VALIDITY", integrity_ok, integrity_ok, "integrity/accounting/evidence all pass", "VALIDITY"),
        _gate(
            "SAMPLE_SUFFICIENCY",
            lower_count >= MIN_LOWER_COMPLETED and first_count >= MIN_HALF_COMPLETED
            and second_count >= MIN_HALF_COMPLETED and upper_count >= MIN_UPPER_COMPLETED,
            {"lower": lower_count, "first": first_count, "second": second_count, "upper": upper_count},
            f"lower>={MIN_LOWER_COMPLETED}, first>={MIN_HALF_COMPLETED}, second>={MIN_HALF_COMPLETED}, upper>={MIN_UPPER_COMPLETED}",
            "SAMPLE",
        ),
        _gate("LENS_A_RETURN", _finite_metric(evidence, "lens_a_mean") > 0 and _finite_metric(evidence, "lens_a_pf") > 1.0, evidence.get("lens_a_mean"), "mean>0 and PF>1", "STRATEGY"),
        _gate("LENS_A_EXCESS", _finite_metric(evidence, "lens_a_excess") > 0, evidence.get("lens_a_excess"), "mean excess>0", "STRATEGY"),
        _gate("PRACTICAL_EXPECTANCY", _finite_metric(evidence, "practical_mean_r") >= 0.15 and _finite_metric(evidence, "practical_rpf") >= 1.20, evidence.get("practical_mean_r"), "mean R>=0.15 and RPF>=1.20", "STRATEGY"),
        _gate("PRACTICAL_EXCESS", _finite_metric(evidence, "practical_excess") > 0, evidence.get("practical_excess"), "mean excess>0", "STRATEGY"),
        _gate("STRESS_ROBUSTNESS", _finite_metric(evidence, "stress_mean_r") > 0 and _finite_metric(evidence, "stress_rpf") > 1.0, evidence.get("stress_mean_r"), "stress mean R>0 and RPF>1", "STRATEGY"),
        _gate("MIRROR_DIRECTION", _finite_metric(evidence, "lower_mean") > _finite_metric(evidence, "upper_mean") and _finite_metric(evidence, "upper_mean") < 0, evidence.get("upper_mean"), "lower mean>upper mean and upper mean<0", "STRATEGY"),
        _gate("TEMPORAL_ROBUSTNESS", bool(evidence.get("temporal_ok", _finite_metric(evidence, "first_practical_mean_r") > 0 and _finite_metric(evidence, "first_practical_rpf") > 1.0 and _finite_metric(evidence, "first_practical_excess") > 0 and _finite_metric(evidence, "second_practical_mean_r") > 0 and _finite_metric(evidence, "second_practical_rpf") > 1.0 and _finite_metric(evidence, "second_practical_excess") > 0)), evidence.get("temporal_ok", True), "both temporal halves pass", "ROBUSTNESS"),
        _gate("TOP_FIVE_ROBUSTNESS", bool(evidence.get("topfive_ok", False)), evidence.get("topfive_ok"), "mean R>0 and RPF>1 after removal", "ROBUSTNESS"),
        _gate("LEAVE_ONE_YEAR_OUT", bool(evidence.get("year_robustness_ok", False)), evidence.get("year_robustness_ok"), "every year omission passes", "ROBUSTNESS"),
        _gate("LEAVE_ONE_SYMBOL_OUT", bool(evidence.get("symbol_robustness_ok", False)), evidence.get("symbol_robustness_ok"), "every symbol omission passes", "ROBUSTNESS"),
    ]
    gates = pd.DataFrame(rows)
    gates["Passed"] = gates["Passed"].astype(object)
    if not integrity_ok:
        status = "INVALID_RESEARCH_RUN"
    elif not bool(gates.loc[gates["Gate"] == "SAMPLE_SUFFICIENCY", "Passed"].iloc[0]):
        status = "INSUFFICIENT_EVIDENCE"
    elif bool(gates.loc[gates["Category"].eq("STRATEGY") | gates["Category"].eq("ROBUSTNESS"), "Passed"].all()):
        status = "PASS"
    else:
        status = "FAIL"
    return gates, status


def render_report(
    evidence: dict[str, object], gates: pd.DataFrame, final_status: str,
    artifacts: dict[str, pd.DataFrame] | None = None,
) -> str:
    lines = [
        "# RR1 Objective Range Sweep Reversion Validation",
        "",
        "## Frozen hypothesis/rules",
        "RR1 tests a liquid point-in-time Nifty 500 stock after an exact 60-session objectively non-directional range, a strict downside sweep and close back inside, next-session Open entry, midpoint target, ATR14 structural stop, 15-session lifecycle, paired raw/practical lenses, and an upper failed-break mirror.",
        "",
        "## Universe/window/data coverage",
        f"Signal window: {evidence.get('signal_window', '2023-08-01..2026-08-25')}. Benchmark: {evidence.get('benchmark', '^CRSLDX')}. PIT membership and adjusted Yahoo OHLCV are the only primary data inputs.",
        "",
        "## Funnel and accounting",
        f"Range-qualified sessions: {evidence.get('range_qualified_count', 'n/a')}; lower signals: {evidence.get('lower_signal_count', 'n/a')}; upper signals: {evidence.get('upper_signal_count', 'n/a')}.",
        f"Lower accepted/cancelled/completed/incomplete: {evidence.get('lower_accounting', 'n/a')}; upper accepted/cancelled/completed/incomplete: {evidence.get('upper_accounting', 'n/a')}.",
        "",
        "## Lens A / Lens B / mirror results",
        f"Lens A: {evidence.get('lens_a_summary', 'n/a')}",
        f"Lens B: {evidence.get('practical_summary', 'n/a')}",
        f"Upper mirror: {evidence.get('mirror_summary', 'n/a')}",
        "",
        "## Robustness and diagnostics",
        "Temporal halves, calendar-year diagnostics, top-five winner removal, leave-one-year-out, leave-one-symbol-out, bootstrap intervals, exits, benchmark excess, and overlap/capacity are reported in the accompanying CSV artifacts.",
        "",
        "## Integrity audit and mandatory gates",
        f"Integrity result: {'PASS' if evidence.get('integrity_ok', False) else 'FAIL'}.",
    ]
    if final_status == "INVALID_RESEARCH_RUN":
        lines.append("Profitability gates are not interpretable because the research run is invalid.")
    lines.extend(["", gates.to_string(index=False), "", f"FINAL_STATUS: {final_status}", "", "RR1 is the final planned strategy-family test. Diagnostics cannot tune or rescue the frozen methodology; after this verdict the swing strategy-family program must be reassessed rather than expanded."])
    return "\n".join(lines) + "\n"
