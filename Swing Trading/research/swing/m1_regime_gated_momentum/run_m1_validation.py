"""Run the one-command, evidence-only M1 validation."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

MODULE_ROOT = Path(__file__).resolve().parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from analyze_m1_results import (  # noqa: E402
    add_practical_friction,
    add_setup_friction,
    evaluate_gates,
    leave_one_symbol_out,
    overlap_capacity_diagnostic,
    regime_comparison,
    summarize_practical,
    summarize_setup,
    temporal_summary,
    top_five_robustness,
    year_summary,
)
from build_m1_regime import attach_exact_signal_regime, build_m1_regime  # noqa: E402
from load_frozen_sources import (  # noqa: E402
    BREADTH_PATH,
    INDEX_PATH,
    MEMBERSHIP_PATH,
    SECTOR_MAP_PATH,
    V3_OUTPUT_ROOT,
    load_market_sources,
    load_v3_artifacts,
    validate_frozen_v3_accounting,
)
from partition_m1_cohorts import partition_v3_evidence  # noqa: E402


OUTPUT_ROOT = MODULE_ROOT / "output"
PRIMARY_START = pd.Timestamp("2023-08-01")
PRIMARY_END = pd.Timestamp("2026-08-25")

OUTPUT_FILES = (
    "m1_data_validation.csv",
    "m1_regime_daily.csv",
    "m1_regime_audit.csv",
    "m1_signal_classification.csv",
    "m1_enabled_entries.csv",
    "m1_enabled_cancellations.csv",
    "m1_disabled_shadow_entries.csv",
    "m1_disabled_shadow_cancellations.csv",
    "m1_setup_quality_trades.csv",
    "m1_practical_trades.csv",
    "m1_disabled_setup_control.csv",
    "m1_disabled_practical_control.csv",
    "m1_validation_summary.csv",
    "m1_regime_comparison.csv",
    "m1_temporal_summary.csv",
    "m1_year_summary.csv",
    "m1_top_five_robustness.csv",
    "m1_leave_one_symbol_out.csv",
    "m1_overlap_capacity_diagnostic.csv",
    "m1_integrity_audit.csv",
    "m1_validation_gates.csv",
    "research_report.md",
)

FINAL_REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "m1_data_validation.csv": ("Metric", "Value", "Pass"),
    "m1_regime_daily.csv": ("Date", "M1_Regime"),
    "m1_regime_audit.csv": (
        "Entry_ID",
        "Signal_Date",
        "Regime_Context_Date",
        "M1_Regime",
        "Exact_Date_Match",
    ),
    "m1_signal_classification.csv": ("Entry_ID", "M1_Regime", "V3_Entry_Status"),
    "m1_enabled_entries.csv": ("Entry_ID",),
    "m1_enabled_cancellations.csv": ("Entry_ID",),
    "m1_disabled_shadow_entries.csv": ("Entry_ID",),
    "m1_disabled_shadow_cancellations.csv": ("Entry_ID",),
    "m1_setup_quality_trades.csv": ("Entry_ID", "Base_Net_Return"),
    "m1_practical_trades.csv": ("Entry_ID", "Base_Net_R"),
    "m1_disabled_setup_control.csv": ("Entry_ID", "Base_Net_Return"),
    "m1_disabled_practical_control.csv": ("Entry_ID", "Base_Net_R"),
    "m1_validation_summary.csv": ("Metric", "Value"),
    "m1_regime_comparison.csv": ("Enabled_Base_Mean_Net_R", "Disabled_Base_Mean_Net_R"),
    "m1_temporal_summary.csv": ("Period",),
    "m1_year_summary.csv": ("Signal_Year",),
    "m1_top_five_robustness.csv": ("Remaining_Mean_Base_Net_R", "Remaining_Base_R_PF"),
    "m1_leave_one_symbol_out.csv": ("Omitted_Symbol",),
    "m1_overlap_capacity_diagnostic.csv": ("Metric", "Dimension", "Value"),
    "m1_integrity_audit.csv": ("Violation",),
    "m1_validation_gates.csv": ("Gate", "Pass", "Mandatory"),
}


def _empty_audit() -> pd.DataFrame:
    return pd.DataFrame(columns=["Entry_ID", "Symbol", "Violation", "Observed", "Expected", "Source"])


def _audit_rows(rows: list[dict[str, object]], source: str) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["Entry_ID", "Symbol", "Violation", "Observed", "Expected"])
    frame["Source"] = source
    return frame.loc[:, ["Entry_ID", "Symbol", "Violation", "Observed", "Expected", "Source"]]


def _tag_audit(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    if frame.empty:
        return _empty_audit()
    result = frame.copy()
    for column in ("Entry_ID", "Symbol", "Violation", "Observed", "Expected"):
        if column not in result:
            result[column] = ""
    result["Source"] = source
    return result.loc[:, ["Entry_ID", "Symbol", "Violation", "Observed", "Expected", "Source"]]


def _truthy(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _qualified_signals(signals: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame(columns=["Entry_ID", "Symbol", "Signal_Date"])
    result = signals.copy()
    result["Signal_Date"] = pd.to_datetime(result.get("Signal_Date"), errors="coerce")
    mask = result.get("Signal_Qualified", pd.Series(False, index=result.index)).map(_truthy)
    return result.loc[mask].copy().reset_index(drop=True)


def _classification_base() -> pd.DataFrame:
    return pd.DataFrame(columns=["Entry_ID", "Symbol", "Signal_Date"])


def _canonical_sessions(index_daily: pd.DataFrame) -> pd.DatetimeIndex:
    if "Date" not in index_daily:
        return pd.DatetimeIndex([])
    return pd.DatetimeIndex(
        pd.to_datetime(index_daily["Date"], errors="coerce")
    ).dropna().drop_duplicates().sort_values()


def _merge_audits(*frames: pd.DataFrame) -> pd.DataFrame:
    nonempty = [frame for frame in frames if frame is not None and not frame.empty]
    if not nonempty:
        return _empty_audit()
    result = pd.concat(nonempty, ignore_index=True)
    return result.drop_duplicates(
        subset=["Entry_ID", "Symbol", "Violation", "Source"]
    ).reset_index(drop=True)


def _write_csv(frame: pd.DataFrame, path: Path, required_columns: tuple[str, ...] = ()) -> None:
    result = frame.copy()
    for column in required_columns:
        if column not in result:
            result[column] = pd.Series(dtype=object)
    path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(path, index=False, date_format="%Y-%m-%d")


def _final_package_issues(output_dir: Path) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for filename, required in FINAL_REQUIRED_COLUMNS.items():
        if filename == "research_report.md":
            path = output_dir / filename
            if not path.exists() or not path.read_text(encoding="utf-8").strip():
                issues.append(
                    {
                        "Entry_ID": "",
                        "Symbol": "",
                        "Violation": "MISSING_FINAL_EVIDENCE",
                        "Observed": filename,
                        "Expected": "non-empty research_report.md",
                    }
                )
            continue
        path = output_dir / filename
        try:
            frame = pd.read_csv(path)
        except (FileNotFoundError, OSError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as exc:
            issues.append(
                {
                    "Entry_ID": "",
                    "Symbol": "",
                    "Violation": "MISSING_FINAL_EVIDENCE" if not path.exists() else "INVALID_FINAL_EVIDENCE",
                    "Observed": f"{filename}: {exc}",
                    "Expected": f"readable CSV with columns={','.join(required)}",
                }
            )
            continue
        missing = [column for column in required if column not in frame.columns]
        if missing:
            issues.append(
                {
                    "Entry_ID": "",
                    "Symbol": "",
                    "Violation": "INVALID_FINAL_EVIDENCE",
                    "Observed": f"{filename}: {','.join(frame.columns)}",
                    "Expected": f"columns={','.join(missing)}",
                }
            )
    return issues


def _data_validation(
    artifacts: dict[str, pd.DataFrame],
    breadth: pd.DataFrame,
    index_daily: pd.DataFrame,
    membership: pd.DataFrame,
    classification: pd.DataFrame,
    package_pass: bool,
    integrity_count: int,
    status: str,
) -> pd.DataFrame:
    signals = artifacts.get("v3_signal_candidates.csv", pd.DataFrame())
    entries = artifacts.get("v3_entries.csv", pd.DataFrame())
    cancellations = artifacts.get("v3_entry_cancellations.csv", pd.DataFrame())
    setup = artifacts.get("v3_setup_quality_trades.csv", pd.DataFrame())
    practical = artifacts.get("v3_practical_trades.csv", pd.DataFrame())
    qualified_count = int(
        signals.get("Signal_Qualified", pd.Series(dtype=bool)).map(_truthy).sum()
    )
    v3_gates = artifacts.get("v3_validation_gates.csv", pd.DataFrame())
    pit_pass = False
    if "Gate" in v3_gates and "Passed" in v3_gates:
        pit_rows = v3_gates.loc[v3_gates["Gate"].astype(str).eq("POINT_IN_TIME_INTEGRITY")]
        pit_pass = bool(not pit_rows.empty and pit_rows["Passed"].map(_truthy).all())
    exact_count = int(classification.get("Exact_Date_Match", pd.Series(dtype=bool)).map(_truthy).sum())
    rows = [
        {"Metric": "V3_QUALIFIED_SIGNALS", "Value": qualified_count, "Pass": qualified_count > 0},
        {"Metric": "V3_ACCEPTED_ENTRIES", "Value": len(entries), "Pass": True},
        {"Metric": "V3_CANCELLED_ENTRIES", "Value": len(cancellations), "Pass": True},
        {"Metric": "V3_COMPLETED_PAIRED", "Value": min(len(setup), len(practical)), "Pass": len(setup) == len(practical)},
        {"Metric": "V3_POINT_IN_TIME_INTEGRITY", "Value": pit_pass, "Pass": pit_pass},
        {"Metric": "BREADTH_SOURCE_ROWS", "Value": len(breadth), "Pass": len(breadth) > 0},
        {"Metric": "INDEX_SOURCE_ROWS", "Value": len(index_daily), "Pass": len(index_daily) > 0},
        {"Metric": "MEMBERSHIP_INTERVAL_ROWS", "Value": len(membership), "Pass": len(membership) > 0},
        {"Metric": "QUALIFIED_SIGNALS_WITH_EXACT_REGIME", "Value": exact_count, "Pass": exact_count == qualified_count},
        {"Metric": "INTEGRITY_VIOLATIONS", "Value": integrity_count, "Pass": integrity_count == 0},
        {"Metric": "FINAL_FORMAL_STATUS", "Value": status, "Pass": status == "PASS"},
        {"Metric": "FINAL_REQUIRED_EVIDENCE_PACKAGE", "Value": package_pass, "Pass": package_pass},
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value", "Pass"])


def _summary_frame(
    setup_metrics: dict[str, float],
    practical_metrics: dict[str, float],
    comparison: pd.DataFrame,
    temporal: pd.DataFrame,
    top_five: pd.DataFrame,
    loso: pd.DataFrame,
    overlap: pd.DataFrame,
    regime_daily: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for source, values in (
        ("enabled_setup", setup_metrics),
        ("enabled_practical", practical_metrics),
    ):
        rows.extend({"Metric": f"{source}.{key}", "Value": value} for key, value in values.items())
    for source, frame in (
        ("regime_comparison", comparison),
        ("top_five", top_five),
        ("loso", loso),
    ):
        if not frame.empty:
            for column in frame.columns:
                if column in {"Period", "Signal_Year", "Omitted_Symbol", "Removed_Entry_IDs", "Status"}:
                    continue
                value = frame.iloc[0][column]
                if np.isscalar(value):
                    rows.append({"Metric": f"{source}.{column}", "Value": value})
    if not overlap.empty:
        rows.extend(
            {"Metric": f"overlap.{row.Metric}.{row.Dimension}", "Value": row.Value}
            for row in overlap.itertuples(index=False)
        )
    if "M1_Regime" in regime_daily:
        rows.extend(
            {"Metric": f"regime_sessions.{key}", "Value": value}
            for key, value in regime_daily["M1_Regime"].value_counts().items()
        )
    rows.append({"Metric": "temporal.rows", "Value": len(temporal)})
    return pd.DataFrame(rows, columns=["Metric", "Value"])


def _classification_accounting(classification: pd.DataFrame) -> pd.DataFrame:
    if classification.empty:
        return pd.DataFrame(columns=["M1_Regime", "V3_Entry_Status", "Signals"])
    return (
        classification.groupby(["M1_Regime", "V3_Entry_Status"], dropna=False)
        .size()
        .rename("Signals")
        .reset_index()
        .sort_values(["M1_Regime", "V3_Entry_Status"])
        .reset_index(drop=True)
    )


def _diagnostic_summary(enabled_practical: pd.DataFrame) -> pd.DataFrame:
    """Summarize diagnostics already present in frozen enabled trade evidence."""

    rows: list[dict[str, object]] = []
    numeric_columns = (
        "R_Multiple",
        "Base_Net_R",
        "Stress_Net_R",
        "Severe_Net_R",
        "Return",
        "Base_Net_Return",
        "Stress_Net_Return",
        "Severe_Net_Return",
        "Holding_Sessions",
        "Pct_Above_SMA50",
        "SMA50_Breadth_Coverage",
        "Composite_RS",
        "Pullback_Age",
        "Pullback_Depth_ATR",
    )
    for column in numeric_columns:
        if column not in enabled_practical:
            continue
        values = pd.to_numeric(enabled_practical[column], errors="coerce").dropna()
        for statistic, value in (
            ("COUNT", len(values)),
            ("MIN", values.min() if not values.empty else np.nan),
            ("MEDIAN", values.median() if not values.empty else np.nan),
            ("MEAN", values.mean() if not values.empty else np.nan),
            ("MAX", values.max() if not values.empty else np.nan),
        ):
            rows.append({"Metric": f"{column}_{statistic}", "Value": value})
    if {"Entry_Open", "Leader_Close", "ATR14_Signal"}.issubset(enabled_practical.columns):
        entry_open = pd.to_numeric(enabled_practical["Entry_Open"], errors="coerce")
        leader_close = pd.to_numeric(enabled_practical["Leader_Close"], errors="coerce")
        atr = pd.to_numeric(enabled_practical["ATR14_Signal"], errors="coerce")
        extension = ((entry_open - leader_close) / atr).replace([np.inf, -np.inf], np.nan).dropna()
        rows.extend(
            {"Metric": f"Entry_Extension_ATR14_{statistic}", "Value": value}
            for statistic, value in (
                ("COUNT", len(extension)),
                ("MIN", extension.min() if not extension.empty else np.nan),
                ("MEDIAN", extension.median() if not extension.empty else np.nan),
                ("MEAN", extension.mean() if not extension.empty else np.nan),
                ("MAX", extension.max() if not extension.empty else np.nan),
            )
        )
    if "Exit_Reason" in enabled_practical:
        for reason, count in enabled_practical["Exit_Reason"].fillna("MISSING").astype(str).value_counts().sort_index().items():
            rows.append({"Metric": "Exit_Reason_COUNT", "Value": f"{reason}={count}"})
    if {"Nifty500_Close", "Nifty500_SMA200"}.issubset(enabled_practical.columns):
        close = pd.to_numeric(enabled_practical["Nifty500_Close"], errors="coerce")
        sma200 = pd.to_numeric(enabled_practical["Nifty500_SMA200"], errors="coerce")
        distance = (close / sma200 - 1.0).replace([np.inf, -np.inf], np.nan).dropna()
        rows.append({"Metric": "Nifty500_Distance_From_SMA200_MEDIAN", "Value": distance.median() if not distance.empty else np.nan})
    return pd.DataFrame(rows, columns=["Metric", "Value"])


def _frame_text(frame: pd.DataFrame) -> str:
    return frame.to_string(index=False) if not frame.empty else "No rows."


def write_research_report(path: Path, status: str, evidence: dict[str, object]) -> None:
    """Write the exact 16-section, decision-focused M1 report."""

    setup_metrics = evidence.get("setup_metrics", {})
    practical_metrics = evidence.get("practical_metrics", {})
    comparison = evidence.get("comparison", pd.DataFrame())
    temporal = evidence.get("temporal", pd.DataFrame())
    years = evidence.get("years", pd.DataFrame())
    top_five = evidence.get("top_five", pd.DataFrame())
    loso = evidence.get("loso", pd.DataFrame())
    overlap = evidence.get("overlap", pd.DataFrame())
    gates = evidence.get("gates", pd.DataFrame())
    integrity = evidence.get("integrity", pd.DataFrame())
    regime_daily = evidence.get("regime_daily", pd.DataFrame())
    classification = evidence.get("classification", pd.DataFrame())
    classification_accounting = evidence.get("classification_accounting", pd.DataFrame())
    diagnostics = evidence.get("diagnostics", pd.DataFrame())
    data_validation = evidence.get("data_validation", pd.DataFrame())
    next_action = {
        "PASS": "PASS -> portfolio/execution validation",
        "FAIL": "FAIL -> close M1 and proceed to Candidate 2",
        "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE -> do not loosen M1; proceed to Candidate 2",
        "INVALID_RESEARCH_RUN": "INVALID_RESEARCH_RUN -> fix only research integrity and rerun unchanged",
    }.get(status, f"{status} -> follow the frozen status hierarchy")
    lines = [
        "# M1 Regime-Gated Momentum Resumption Validation",
        "",
        "## 1. Frozen M1 hypothesis and rules",
        "M1 partitions the closed V3 opportunity set using only signal-date PIT breadth coverage >= 80%, Nifty 500 Close > SMA200, Nifty 500 SMA50 > SMA200, and Pct_Above_SMA50 >= 50%. Disabled signals remain cash; V3 setup, entry, cancellation, exits, and gross outcomes remain frozen.",
        "Friction is frozen at 0.40% base, 0.60% stress, and 0.80% severe diagnostic. No post-result threshold or rescue changes are permitted.",
        "",
        "## 2. Source-artifact and PIT coverage/integrity",
        _frame_text(data_validation),
        "",
        "## 3. M1 regime distribution",
        _frame_text(regime_daily["M1_Regime"].value_counts().rename_axis("M1_Regime").reset_index(name="Sessions")) if "M1_Regime" in regime_daily else "No regime rows.",
        "",
        "## 4. Signal/cohort accounting",
        _frame_text(classification_accounting),
        "",
        "## 5. Base setup-quality results",
        str(setup_metrics),
        "",
        "## 6. Base practical results",
        str(practical_metrics),
        "",
        "## 7. Stress/severe friction results",
        str({key: value for key, value in practical_metrics.items() if "Stress" in key or "Severe" in key}),
        "",
        "## 8. Enabled-vs-disabled regime comparison",
        _frame_text(comparison),
        "",
        "## 9. Temporal halves",
        _frame_text(temporal),
        "",
        "## 10. Calendar-year diagnostics",
        _frame_text(years),
        "",
        "## 11. Top-five-winner robustness",
        _frame_text(top_five),
        "",
        "## 12. Leave-one-symbol-out robustness",
        _frame_text(loso),
        "",
        "## 13. Overlap/capacity diagnostics including clustering, partial-sector coverage and 1%-risk sizing",
        _frame_text(overlap),
        "",
        "Frozen enabled-trade diagnostics:",
        _frame_text(diagnostics),
        "",
        "## 14. Integrity audit",
        _frame_text(integrity),
        "",
        "## 15. Mandatory gate table",
        _frame_text(gates),
        "",
        "## 16. One formal final status and explicit next action",
        f"Formal M1 status: {status}",
        next_action,
        "No alternate thresholds, rescue suggestions, or post-result strategy changes are proposed.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_validation(
    v3_output_root: Path = V3_OUTPUT_ROOT,
    breadth_path: Path = BREADTH_PATH,
    index_path: Path = INDEX_PATH,
    membership_path: Path = MEMBERSHIP_PATH,
    sector_map_path: Path = SECTOR_MAP_PATH,
    output_dir: Path = OUTPUT_ROOT,
) -> tuple[str, pd.DataFrame]:
    """Execute the M1 pipeline in the frozen plan order."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    artifacts, v3_loader_audit = load_v3_artifacts(Path(v3_output_root))
    v3_accounting_audit = validate_frozen_v3_accounting(artifacts)
    breadth, index_daily, membership, sector_mapping, market_audit = load_market_sources(
        Path(breadth_path), Path(index_path), Path(membership_path), Path(sector_map_path)
    )

    regime_daily, regime_build_audit = build_m1_regime(breadth, index_daily, membership)
    qualified = _qualified_signals(artifacts.get("v3_signal_candidates.csv", pd.DataFrame()))
    if qualified.empty and not {"Entry_ID", "Symbol", "Signal_Date"}.issubset(qualified.columns):
        qualified = _classification_base()
    classified, regime_audit, regime_violations = attach_exact_signal_regime(qualified, regime_daily)
    cohorts, partition_audit = partition_v3_evidence(classified, artifacts)
    classification = cohorts.get("classification", classified)

    enabled_setup, enabled_setup_audit = add_setup_friction(cohorts.get("enabled_setup", pd.DataFrame()))
    disabled_setup, disabled_setup_audit = add_setup_friction(cohorts.get("disabled_setup", pd.DataFrame()))
    enabled_practical, enabled_practical_audit = add_practical_friction(cohorts.get("enabled_practical", pd.DataFrame()))
    disabled_practical, disabled_practical_audit = add_practical_friction(cohorts.get("disabled_practical", pd.DataFrame()))

    enabled_entries = cohorts.get("enabled_entries", pd.DataFrame())
    disabled_entries = cohorts.get("disabled_shadow_entries", pd.DataFrame())
    if "M1_Regime" in classification.columns:
        enabled_classification = classification.loc[
            classification["M1_Regime"].astype(str).eq("MOMENTUM_ENABLED")
        ].copy()
    else:
        enabled_classification = classification.iloc[0:0].copy()
    sessions = _canonical_sessions(index_daily)
    overlap = overlap_capacity_diagnostic(
        enabled_classification,
        enabled_entries,
        enabled_practical,
        sessions,
        sector_mapping,
    )
    setup_metrics = summarize_setup(enabled_setup, "")
    practical_metrics = summarize_practical(enabled_practical, "")
    comparison = regime_comparison(enabled_practical, disabled_practical)
    temporal = temporal_summary(enabled_practical)
    years = year_summary(enabled_practical)
    top_five = top_five_robustness(enabled_practical)
    loso = leave_one_symbol_out(enabled_practical)
    classification_accounting = _classification_accounting(classification)
    diagnostics = _diagnostic_summary(enabled_practical)

    additional_rows: list[dict[str, object]] = []
    for _, row in enabled_entries.iterrows():
        signal_date = pd.to_datetime(row.get("Signal_Date"), errors="coerce")
        entry_date = pd.to_datetime(row.get("Entry_Date"), errors="coerce")
        if pd.isna(signal_date) or pd.isna(entry_date) or signal_date >= entry_date:
            additional_rows.append(
                {
                    "Entry_ID": row.get("Entry_ID", ""),
                    "Symbol": row.get("Symbol", ""),
                    "Violation": "SIGNAL_NOT_BEFORE_ENTRY",
                    "Observed": f"signal={signal_date}, entry={entry_date}",
                    "Expected": "Signal_Date < Entry_Date",
                }
            )
    for _, row in regime_audit.iterrows():
        if not _truthy(row.get("Exact_Date_Match")):
            continue
        if pd.Timestamp(row["Signal_Date"]) != pd.Timestamp(row["Regime_Context_Date"]):
            additional_rows.append(
                {
                    "Entry_ID": row.get("Entry_ID", ""),
                    "Symbol": row.get("Symbol", ""),
                    "Violation": "REGIME_CONTEXT_DATE_MISMATCH",
                    "Observed": row.get("Regime_Context_Date", ""),
                    "Expected": row.get("Signal_Date", ""),
                }
            )
    all_integrity = _merge_audits(
        _tag_audit(v3_loader_audit, "v3_loader"),
        _tag_audit(v3_accounting_audit, "v3_accounting"),
        _tag_audit(market_audit, "market_sources"),
        _tag_audit(regime_build_audit, "m1_regime"),
        _tag_audit(regime_violations, "regime_join"),
        _tag_audit(partition_audit, "partition"),
        _tag_audit(enabled_setup_audit, "enabled_setup_friction"),
        _tag_audit(disabled_setup_audit, "disabled_setup_friction"),
        _tag_audit(enabled_practical_audit, "enabled_practical_friction"),
        _tag_audit(disabled_practical_audit, "disabled_practical_friction"),
        _audit_rows(additional_rows, "timing_checks"),
    )
    status, gates = evaluate_gates(
        setup_metrics,
        practical_metrics,
        comparison,
        temporal,
        top_five,
        loso,
        len(enabled_practical),
        len(all_integrity),
    )
    validation_summary = _summary_frame(
        setup_metrics,
        practical_metrics,
        comparison,
        temporal,
        top_five,
        loso,
        overlap,
        regime_daily,
    )
    validation_summary = pd.concat([validation_summary, diagnostics], ignore_index=True)

    def write_package(package_pass: bool, current_status: str, current_integrity: pd.DataFrame) -> None:
        data_validation = _data_validation(
            artifacts,
            breadth,
            index_daily,
            membership,
            classification,
            package_pass,
            len(current_integrity),
            current_status,
        )
        _write_csv(data_validation, output_dir / "m1_data_validation.csv", ("Metric", "Value", "Pass"))
        _write_csv(regime_daily, output_dir / "m1_regime_daily.csv", ("Date", "M1_Regime"))
        _write_csv(regime_audit, output_dir / "m1_regime_audit.csv", FINAL_REQUIRED_COLUMNS["m1_regime_audit.csv"])
        _write_csv(classification, output_dir / "m1_signal_classification.csv", FINAL_REQUIRED_COLUMNS["m1_signal_classification.csv"])
        _write_csv(enabled_entries, output_dir / "m1_enabled_entries.csv", ("Entry_ID",))
        _write_csv(cohorts.get("enabled_cancellations", pd.DataFrame()), output_dir / "m1_enabled_cancellations.csv", ("Entry_ID",))
        _write_csv(disabled_entries, output_dir / "m1_disabled_shadow_entries.csv", ("Entry_ID",))
        _write_csv(cohorts.get("disabled_shadow_cancellations", pd.DataFrame()), output_dir / "m1_disabled_shadow_cancellations.csv", ("Entry_ID",))
        _write_csv(enabled_setup, output_dir / "m1_setup_quality_trades.csv", FINAL_REQUIRED_COLUMNS["m1_setup_quality_trades.csv"])
        _write_csv(enabled_practical, output_dir / "m1_practical_trades.csv", FINAL_REQUIRED_COLUMNS["m1_practical_trades.csv"])
        _write_csv(disabled_setup, output_dir / "m1_disabled_setup_control.csv", FINAL_REQUIRED_COLUMNS["m1_disabled_setup_control.csv"])
        _write_csv(disabled_practical, output_dir / "m1_disabled_practical_control.csv", FINAL_REQUIRED_COLUMNS["m1_disabled_practical_control.csv"])
        _write_csv(validation_summary, output_dir / "m1_validation_summary.csv", ("Metric", "Value"))
        _write_csv(comparison, output_dir / "m1_regime_comparison.csv", FINAL_REQUIRED_COLUMNS["m1_regime_comparison.csv"])
        _write_csv(temporal, output_dir / "m1_temporal_summary.csv", ("Period",))
        _write_csv(years, output_dir / "m1_year_summary.csv", ("Signal_Year",))
        _write_csv(top_five, output_dir / "m1_top_five_robustness.csv", FINAL_REQUIRED_COLUMNS["m1_top_five_robustness.csv"])
        _write_csv(loso, output_dir / "m1_leave_one_symbol_out.csv", ("Omitted_Symbol",))
        _write_csv(overlap, output_dir / "m1_overlap_capacity_diagnostic.csv", FINAL_REQUIRED_COLUMNS["m1_overlap_capacity_diagnostic.csv"])
        _write_csv(current_integrity, output_dir / "m1_integrity_audit.csv", ("Violation",))
        _write_csv(gates, output_dir / "m1_validation_gates.csv", FINAL_REQUIRED_COLUMNS["m1_validation_gates.csv"])
        evidence = {
            "setup_metrics": setup_metrics,
            "practical_metrics": practical_metrics,
            "comparison": comparison,
            "temporal": temporal,
            "years": years,
            "top_five": top_five,
            "loso": loso,
            "overlap": overlap,
            "gates": gates,
            "integrity": current_integrity,
            "regime_daily": regime_daily,
            "classification": classification,
            "classification_accounting": classification_accounting,
            "diagnostics": diagnostics,
            "data_validation": data_validation,
        }
        write_research_report(output_dir / "research_report.md", current_status, evidence)

    write_package(False, status, all_integrity)
    package_issues = _final_package_issues(output_dir)
    if package_issues:
        final_integrity = _merge_audits(all_integrity, _audit_rows(package_issues, "final_package"))
        status, gates = evaluate_gates(
            setup_metrics,
            practical_metrics,
            comparison,
            temporal,
            top_five,
            loso,
            len(enabled_practical),
            len(final_integrity),
        )
        all_integrity = final_integrity
        write_package(False, status, all_integrity)
    else:
        data_validation = _data_validation(
            artifacts,
            breadth,
            index_daily,
            membership,
            classification,
            True,
            len(all_integrity),
            status,
        )
        _write_csv(data_validation, output_dir / "m1_data_validation.csv", ("Metric", "Value", "Pass"))
        evidence = {
            "setup_metrics": setup_metrics,
            "practical_metrics": practical_metrics,
            "comparison": comparison,
            "temporal": temporal,
            "years": years,
            "top_five": top_five,
            "loso": loso,
            "overlap": overlap,
            "gates": gates,
            "integrity": all_integrity,
            "regime_daily": regime_daily,
            "classification": classification,
            "classification_accounting": classification_accounting,
            "diagnostics": diagnostics,
            "data_validation": data_validation,
        }
        write_research_report(output_dir / "research_report.md", status, evidence)
    return status, gates


if __name__ == "__main__":
    final_status, final_gates = run_validation()
    print(final_gates.to_string(index=False))
    print(f"Formal M1 status: {final_status}")
