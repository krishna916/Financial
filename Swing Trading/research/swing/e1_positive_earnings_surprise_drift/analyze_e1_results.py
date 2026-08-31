"""Analyze frozen E1 trade outcomes without changing qualification mechanics."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from constants import FIRST_HALF_END, SECOND_HALF_START


def return_profit_factor(values: pd.Series) -> float:
    """Return gross gains divided by absolute gross losses."""

    numeric = pd.to_numeric(values, errors="coerce").dropna()
    gains = float(numeric.loc[numeric > 0].sum())
    losses = float(-numeric.loc[numeric < 0].sum())
    if losses == 0:
        return float("inf") if gains > 0 else float("nan")
    return gains / losses


def _mean(frame: pd.DataFrame, column: str) -> float:
    return float(pd.to_numeric(frame.get(column, pd.Series(dtype=float)), errors="coerce").mean())


def _median(frame: pd.DataFrame, column: str) -> float:
    return float(pd.to_numeric(frame.get(column, pd.Series(dtype=float)), errors="coerce").median())


def _win_rate(frame: pd.DataFrame, column: str) -> float:
    values = pd.to_numeric(frame.get(column, pd.Series(dtype=float)), errors="coerce").dropna()
    return float((values > 0).mean()) if len(values) else float("nan")


def summarize_cohort(frame: pd.DataFrame) -> dict[str, float]:
    """Summarize base/stress/severe and benchmark-relative outcomes for one cohort."""

    return {
        "Completed_Count": float(len(frame)),
        "Base_Mean_Net_Return": _mean(frame, "Base_Net_Return"),
        "Base_Median_Net_Return": _median(frame, "Base_Net_Return"),
        "Base_Win_Rate": _win_rate(frame, "Base_Net_Return"),
        "Base_Return_PF": return_profit_factor(frame.get("Base_Net_Return", pd.Series(dtype=float))),
        "Stress_Mean_Net_Return": _mean(frame, "Stress_Net_Return"),
        "Stress_Median_Net_Return": _median(frame, "Stress_Net_Return"),
        "Stress_Win_Rate": _win_rate(frame, "Stress_Net_Return"),
        "Stress_Return_PF": return_profit_factor(frame.get("Stress_Net_Return", pd.Series(dtype=float))),
        "Severe_Mean_Net_Return": _mean(frame, "Severe_Net_Return"),
        "Severe_Return_PF": return_profit_factor(frame.get("Severe_Net_Return", pd.Series(dtype=float))),
        "Benchmark_Mean_Return": _mean(frame, "Benchmark_Return"),
        "Base_Mean_Net_Excess_Return": _mean(frame, "Base_Net_Excess_Return"),
        "Base_Excess_Return_PF": return_profit_factor(frame.get("Base_Net_Excess_Return", pd.Series(dtype=float))),
        "Stress_Mean_Net_Excess_Return": _mean(frame, "Stress_Net_Excess_Return"),
        "Stress_Excess_Return_PF": return_profit_factor(frame.get("Stress_Net_Excess_Return", pd.Series(dtype=float))),
    }


def cohort_comparison(
    positive: pd.DataFrame,
    neutral: pd.DataFrame,
    negative: pd.DataFrame,
) -> pd.DataFrame:
    """Compare all primary cohorts and expose directional ordering booleans."""

    frames = {
        "POSITIVE_SURPRISE": positive,
        "NEUTRAL_CONTROL": neutral,
        "NEGATIVE_CONTROL": negative,
    }
    rows: list[dict[str, object]] = []
    for cohort, frame in frames.items():
        rows.append({"Cohort": cohort, **summarize_cohort(frame)})
    result = pd.DataFrame(rows)
    by_cohort = result.set_index("Cohort")
    positive_mean = by_cohort.loc["POSITIVE_SURPRISE", "Base_Mean_Net_Return"]
    neutral_mean = by_cohort.loc["NEUTRAL_CONTROL", "Base_Mean_Net_Return"]
    negative_mean = by_cohort.loc["NEGATIVE_CONTROL", "Base_Mean_Net_Return"]
    positive_excess = by_cohort.loc["POSITIVE_SURPRISE", "Base_Mean_Net_Excess_Return"]
    neutral_excess = by_cohort.loc["NEUTRAL_CONTROL", "Base_Mean_Net_Excess_Return"]
    negative_excess = by_cohort.loc["NEGATIVE_CONTROL", "Base_Mean_Net_Excess_Return"]
    result["Positive_GT_Neutral_GT_Negative_Mean"] = positive_mean > neutral_mean > negative_mean
    result["Positive_GT_Neutral_GT_Negative_Excess"] = positive_excess > neutral_excess > negative_excess
    result["Positive_PF_GT_Neutral_PF"] = by_cohort.loc["POSITIVE_SURPRISE", "Base_Return_PF"] > by_cohort.loc["NEUTRAL_CONTROL", "Base_Return_PF"]
    result["Positive_PF_GT_Negative_PF"] = by_cohort.loc["POSITIVE_SURPRISE", "Base_Return_PF"] > by_cohort.loc["NEGATIVE_CONTROL", "Base_Return_PF"]
    return result


def _period_frame(positive: pd.DataFrame, period: str) -> pd.DataFrame:
    dates = positive["Event_Public_Date"].map(_date) if "Event_Public_Date" in positive else pd.Series(dtype="datetime64[ns]")
    if period == "FIRST":
        return positive.loc[dates.le(FIRST_HALF_END)]
    return positive.loc[dates.ge(SECOND_HALF_START)]


def _date(value: object) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    stamp = pd.Timestamp(parsed)
    if stamp.tz is not None:
        stamp = stamp.tz_convert("Asia/Kolkata").tz_localize(None)
    return stamp.normalize()


def _robustness_metrics(frame: pd.DataFrame) -> dict[str, object]:
    return {
        "Remaining_Count": len(frame),
        "Mean_Net_Return": _mean(frame, "Base_Net_Return"),
        "Return_PF": return_profit_factor(frame.get("Base_Net_Return", pd.Series(dtype=float))),
        "Mean_Net_Excess_Return": _mean(frame, "Base_Net_Excess_Return"),
    }


def temporal_summary(positive: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for period in ("FIRST", "SECOND"):
        frame = _period_frame(positive, period)
        rows.append({"Period": period, "Mandatory_Gate": True, **{"Completed_Count": len(frame)}, **summarize_cohort(frame)})
    return pd.DataFrame(rows)


def year_summary(positive: pd.DataFrame) -> pd.DataFrame:
    if positive.empty:
        return pd.DataFrame(columns=["Year", "Mandatory_Gate", "Completed_Count"])
    frame = positive.copy()
    frame["Year"] = frame["Event_Public_Date"].map(_date).dt.year
    rows = [
        {"Year": int(year), "Mandatory_Gate": False, **summarize_cohort(group)}
        for year, group in frame.groupby("Year", sort=True)
    ]
    return pd.DataFrame(rows)


def leave_one_year_out(positive: pd.DataFrame) -> pd.DataFrame:
    if positive.empty:
        return pd.DataFrame(columns=["Year_Removed", "Mandatory_Gate", "Remaining_Count", "Mean_Net_Return", "Return_PF", "Mean_Net_Excess_Return", "Pass"])
    frame = positive.copy()
    frame["_Year"] = frame["Event_Public_Date"].map(_date).dt.year
    rows: list[dict[str, object]] = []
    for year in sorted(frame["_Year"].dropna().unique()):
        remaining = frame.loc[frame["_Year"] != year]
        metrics = _robustness_metrics(remaining)
        rows.append(
            {
                "Year_Removed": int(year),
                "Mandatory_Gate": True,
                **metrics,
                "Pass": bool(metrics["Mean_Net_Return"] > 0 and metrics["Return_PF"] > 1 and metrics["Mean_Net_Excess_Return"] > 0),
            }
        )
    return pd.DataFrame(rows)


def top_five_robustness(positive: pd.DataFrame) -> pd.DataFrame:
    count = min(5, len(positive))
    ranked = positive.sort_values("Gross_Return", ascending=False, kind="stable") if "Gross_Return" in positive else positive
    remaining = ranked.iloc[count:]
    metrics = _robustness_metrics(remaining)
    return pd.DataFrame(
        [
            {
                "Removed_Count": count,
                "Mandatory_Gate": True,
                **metrics,
                "Pass": bool(metrics["Mean_Net_Return"] > 0 and metrics["Return_PF"] > 1 and metrics["Mean_Net_Excess_Return"] > 0),
            }
        ]
    )


def leave_one_symbol_out(positive: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for symbol in sorted(positive["Symbol"].astype(str).unique()) if "Symbol" in positive else []:
        remaining = positive.loc[positive["Symbol"].astype(str) != symbol]
        metrics = _robustness_metrics(remaining)
        rows.append(
            {
                "Symbol_Removed": symbol,
                "Mandatory_Gate": True,
                **metrics,
                "Pass": bool(metrics["Mean_Net_Return"] > 0 and metrics["Return_PF"] > 1 and metrics["Mean_Net_Excess_Return"] > 0),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "Symbol_Removed",
            "Mandatory_Gate",
            "Remaining_Count",
            "Mean_Net_Return",
            "Return_PF",
            "Mean_Net_Excess_Return",
            "Pass",
        ],
    )


def downside_diagnostic(positive: pd.DataFrame) -> pd.DataFrame:
    values = pd.to_numeric(positive.get("Base_Net_Return", pd.Series(dtype=float)), errors="coerce").dropna()
    return pd.DataFrame(
        [
            {
                "Worst_Completed_Trade": float(values.min()) if len(values) else np.nan,
                "Return_1st_Percentile": float(values.quantile(0.01)) if len(values) else np.nan,
                "Return_5th_Percentile": float(values.quantile(0.05)) if len(values) else np.nan,
                "Median_Trade_Drawdown": float(pd.to_numeric(positive.get("Max_Trade_Drawdown", pd.Series(dtype=float)), errors="coerce").median()),
                "Max_Trade_Drawdown": float(pd.to_numeric(positive.get("Max_Trade_Drawdown", pd.Series(dtype=float)), errors="coerce").min()),
                "Mandatory_Gate": False,
            }
        ]
    )


def _diagnostic_cut(frame: pd.DataFrame, name: str, values: pd.Series) -> pd.DataFrame:
    rows = []
    for label, mask in values.groupby(values).groups.items():
        subset = frame.loc[mask]
        rows.append({"Diagnostic": name, "Bucket": label, "Mandatory_Gate": False, **summarize_cohort(subset)})
    return pd.DataFrame(rows)


def diagnostic_summary(positive: pd.DataFrame) -> pd.DataFrame:
    if positive.empty:
        return pd.DataFrame(columns=["Diagnostic", "Bucket", "Mandatory_Gate"])
    pieces: list[pd.DataFrame] = []
    if "SUE" in positive:
        sue = pd.to_numeric(positive["SUE"], errors="coerce")
        bands = pd.cut(sue, [-np.inf, 2, 3, 5, np.inf], labels=["1-2", "2-3", "3-5", ">=5"], right=False)
        pieces.append(_diagnostic_cut(positive, "SUE_BAND", bands))
    if "Entry_Gap" in positive:
        gap = pd.to_numeric(positive["Entry_Gap"], errors="coerce")
        buckets = pd.cut(gap, [-np.inf, -0.05, 0, 0.05, np.inf], labels=["<-5%", "-5%..0%", "0%..5%", ">5%"])
        pieces.append(_diagnostic_cut(positive, "ENTRY_GAP", buckets))
    return pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame(columns=["Diagnostic", "Bucket", "Mandatory_Gate"])


def overlap_capacity_diagnostic(positive: pd.DataFrame) -> pd.DataFrame:
    if positive.empty:
        return pd.DataFrame([{"Max_Simultaneous_Trades": 0, "Median_Simultaneous_Trades": 0, "Same_Day_Entries": 0, "Mandatory_Gate": False}])
    entries = positive["Entry_Date"].map(_date)
    exits = positive["Exit_Date"].map(_date)
    dates = sorted(set(entries.dropna()) | set(exits.dropna()))
    active = [int((entries.le(day) & exits.gt(day)).sum()) for day in dates]
    return pd.DataFrame(
        [
            {
                "Max_Simultaneous_Trades": max(active, default=0),
                "Median_Simultaneous_Trades": float(np.median(active)) if active else 0.0,
                "Same_Day_Entries": int(entries.duplicated(keep=False).sum()),
                "Event_Season_Clustering": int(positive.get("Fiscal_Quarter", pd.Series(dtype=object)).duplicated(keep=False).sum()),
                "Mandatory_Gate": False,
            }
        ]
    )


def write_analysis_outputs(output_dir: Path, positive: pd.DataFrame, neutral: pd.DataFrame, negative: pd.DataFrame) -> dict[str, pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "e1_validation_summary.csv": pd.DataFrame([summarize_cohort(positive)]),
        "e1_cohort_comparison.csv": cohort_comparison(positive, neutral, negative),
        "e1_benchmark_comparison.csv": cohort_comparison(positive, neutral, negative)[["Cohort", "Benchmark_Mean_Return", "Base_Mean_Net_Excess_Return"]],
        "e1_temporal_summary.csv": temporal_summary(positive),
        "e1_year_summary.csv": year_summary(positive),
        "e1_leave_one_year_out.csv": leave_one_year_out(positive),
        "e1_top_five_robustness.csv": top_five_robustness(positive),
        "e1_leave_one_symbol_out.csv": leave_one_symbol_out(positive),
        "e1_downside_diagnostic.csv": downside_diagnostic(positive),
        "e1_diagnostic_summary.csv": diagnostic_summary(positive),
        "e1_overlap_capacity_diagnostic.csv": overlap_capacity_diagnostic(positive),
    }
    for name, frame in outputs.items():
        frame.to_csv(output_dir / name, index=False)
    return outputs
