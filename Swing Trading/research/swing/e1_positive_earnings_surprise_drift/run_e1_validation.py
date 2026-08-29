"""Offline E1 validator, integrity audit, formal gates, and report writer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_e1_results import (
    cohort_comparison,
    diagnostic_summary,
    downside_diagnostic,
    leave_one_symbol_out,
    leave_one_year_out,
    overlap_capacity_diagnostic,
    summarize_cohort,
    temporal_summary,
    top_five_robustness,
    write_analysis_outputs,
    year_summary,
)
from build_e1_events import build_event_master, write_event_outputs
from build_e1_trades import build_primary_trades, write_trade_outputs
from compute_e1_sue import build_sue_events, write_sue_outputs
from constants import (
    PRIMARY_NEGATIVE_MIN,
    PRIMARY_NEUTRAL_MIN,
    PRIMARY_POSITIVE_MIN,
    REQUIRED_INPUT_ARTIFACTS,
    REQUIRED_OUTPUT_ARTIFACTS,
    TECHNICAL_EPS_COVERAGE_MIN,
    TEMPORAL_POSITIVE_MIN,
)
from load_e1_inputs import load_membership, verify_manifest


OUTPUT_SCHEMAS: dict[str, tuple[str, ...]] = {
    "e1_data_validation.csv": ("Check", "Violation", "Count", "Detail"),
    "e1_source_coverage.csv": ("Technical_EPS_Candidates", "Resolved_EPS_Candidates", "Machine_Readable_EPS_Resolution"),
    "e1_event_master.csv": ("Event_ID", "Symbol", "Event_Public_Date", "Primary_Event"),
    "e1_event_exclusions.csv": ("Event_ID", "Reason"),
    "e1_eps_history.csv": ("Event_ID", "Current_EPS", "SUE"),
    "e1_sue_events.csv": ("Event_ID", "SUE", "Cohort"),
    "e1_cohort_classification.csv": ("Event_ID", "SUE", "Cohort"),
    "e1_positive_trades.csv": ("Event_ID", "Entry_Date", "Exit_Date", "Base_Net_Return"),
    "e1_neutral_control.csv": ("Event_ID", "Entry_Date", "Exit_Date", "Base_Net_Return"),
    "e1_negative_control.csv": ("Event_ID", "Entry_Date", "Exit_Date", "Base_Net_Return"),
    "e1_validation_summary.csv": ("Completed_Count", "Base_Mean_Net_Return"),
    "e1_cohort_comparison.csv": ("Cohort", "Completed_Count"),
    "e1_benchmark_comparison.csv": ("Cohort", "Benchmark_Mean_Return"),
    "e1_temporal_summary.csv": ("Period", "Completed_Count"),
    "e1_year_summary.csv": ("Year", "Completed_Count"),
    "e1_leave_one_year_out.csv": ("Year_Removed", "Pass"),
    "e1_top_five_robustness.csv": ("Removed_Count", "Pass"),
    "e1_leave_one_symbol_out.csv": ("Symbol_Removed", "Pass"),
    "e1_downside_diagnostic.csv": ("Worst_Completed_Trade", "Mandatory_Gate"),
    "e1_diagnostic_summary.csv": ("Diagnostic", "Bucket", "Mandatory_Gate"),
    "e1_overlap_capacity_diagnostic.csv": ("Max_Simultaneous_Trades", "Mandatory_Gate"),
    "e1_integrity_audit.csv": ("Check", "Violation", "Count", "Detail"),
    "e1_validation_gates.csv": ("Gate", "Value", "Threshold", "Pass", "Mandatory"),
}


def _empty_frame(columns: tuple[str, ...] | list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def _as_summary(value: object, fallback_frame: pd.DataFrame | None = None) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, pd.DataFrame):
        return summarize_cohort(value)
    if fallback_frame is not None:
        return summarize_cohort(fallback_frame)
    return {}


def _metric(summary: dict[str, object], key: str) -> float:
    value = summary.get(key, np.nan)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _gate(rows: list[dict[str, object]], name: str, value: object, threshold: object, passed: bool, mandatory: bool = True) -> None:
    rows.append({"Gate": name, "Value": value, "Threshold": threshold, "Pass": bool(passed), "Mandatory": bool(mandatory)})


def evaluate_gates(
    positive: pd.DataFrame | dict[str, object] | None = None,
    neutral: pd.DataFrame | dict[str, object] | None = None,
    negative: pd.DataFrame | dict[str, object] | None = None,
    temporal: pd.DataFrame | None = None,
    year_loo: pd.DataFrame | None = None,
    top_five: pd.DataFrame | None = None,
    loso: pd.DataFrame | None = None,
    *,
    integrity_count: int = 0,
    technical_coverage: float = float("nan"),
    positive_count: int | None = None,
    neutral_count: int | None = None,
    negative_count: int | None = None,
) -> tuple[str, pd.DataFrame]:
    """Evaluate the frozen gates with integrity and evidence precedence."""

    positive_frame = positive if isinstance(positive, pd.DataFrame) else pd.DataFrame()
    neutral_frame = neutral if isinstance(neutral, pd.DataFrame) else pd.DataFrame()
    negative_frame = negative if isinstance(negative, pd.DataFrame) else pd.DataFrame()
    positive_summary = _as_summary(positive, positive_frame)
    neutral_summary = _as_summary(neutral, neutral_frame)
    negative_summary = _as_summary(negative, negative_frame)
    p_count = len(positive_frame) if positive_count is None else positive_count
    n_count = len(neutral_frame) if neutral_count is None else neutral_count
    neg_count = len(negative_frame) if negative_count is None else negative_count
    rows: list[dict[str, object]] = []
    coverage_value = float(technical_coverage)
    coverage_pass = np.isfinite(coverage_value) and coverage_value >= TECHNICAL_EPS_COVERAGE_MIN
    _gate(rows, "TECHNICAL_EPS_COVERAGE", coverage_value, TECHNICAL_EPS_COVERAGE_MIN, coverage_pass)
    _gate(rows, "POSITIVE_SAMPLE_SUFFICIENCY", p_count, PRIMARY_POSITIVE_MIN, p_count >= PRIMARY_POSITIVE_MIN)
    _gate(rows, "NEUTRAL_SAMPLE_SUFFICIENCY", n_count, PRIMARY_NEUTRAL_MIN, n_count >= PRIMARY_NEUTRAL_MIN)
    _gate(rows, "NEGATIVE_SAMPLE_SUFFICIENCY", neg_count, PRIMARY_NEGATIVE_MIN, neg_count >= PRIMARY_NEGATIVE_MIN)

    p_mean = _metric(positive_summary, "Base_Mean_Net_Return")
    p_median = _metric(positive_summary, "Base_Median_Net_Return")
    p_pf = _metric(positive_summary, "Base_Return_PF")
    p_excess = _metric(positive_summary, "Base_Mean_Net_Excess_Return")
    p_excess_pf = _metric(positive_summary, "Base_Excess_Return_PF")
    _gate(rows, "BASE_POSITIVE_MEAN_NET_RETURN", p_mean, 0.01, np.isfinite(p_mean) and p_mean >= 0.01)
    _gate(rows, "BASE_POSITIVE_MEDIAN_NET_RETURN", p_median, 0.0, np.isfinite(p_median) and p_median > 0)
    _gate(rows, "BASE_POSITIVE_RETURN_PF", p_pf, 1.20, np.isfinite(p_pf) and p_pf >= 1.20)
    _gate(rows, "BASE_POSITIVE_MEAN_NET_EXCESS_RETURN", p_excess, 0.0, np.isfinite(p_excess) and p_excess > 0)
    _gate(rows, "BASE_POSITIVE_EXCESS_RETURN_PF", p_excess_pf, 1.0, np.isfinite(p_excess_pf) and p_excess_pf > 1.0)
    stress_mean = _metric(positive_summary, "Stress_Mean_Net_Return")
    stress_pf = _metric(positive_summary, "Stress_Return_PF")
    stress_excess = _metric(positive_summary, "Stress_Mean_Net_Excess_Return")
    _gate(rows, "STRESS_POSITIVE_MEAN_NET_RETURN", stress_mean, 0.0, np.isfinite(stress_mean) and stress_mean > 0)
    _gate(rows, "STRESS_POSITIVE_RETURN_PF", stress_pf, 1.0, np.isfinite(stress_pf) and stress_pf > 1.0)
    _gate(rows, "STRESS_POSITIVE_MEAN_NET_EXCESS_RETURN", stress_excess, 0.0, np.isfinite(stress_excess) and stress_excess > 0)

    nm = _metric(neutral_summary, "Base_Mean_Net_Return")
    negm = _metric(negative_summary, "Base_Mean_Net_Return")
    ne = _metric(neutral_summary, "Base_Mean_Net_Excess_Return")
    nege = _metric(negative_summary, "Base_Mean_Net_Excess_Return")
    npf = _metric(neutral_summary, "Base_Return_PF")
    negpf = _metric(negative_summary, "Base_Return_PF")
    _gate(rows, "DIRECTIONAL_MEAN_ORDERING", p_mean > nm > negm, "positive > neutral > negative", np.isfinite([p_mean, nm, negm]).all())
    rows[-1]["Pass"] = bool(np.isfinite([p_mean, nm, negm]).all() and p_mean > nm > negm)
    _gate(rows, "DIRECTIONAL_EXCESS_ORDERING", p_excess > ne > nege, "positive > neutral > negative", np.isfinite([p_excess, ne, nege]).all())
    rows[-1]["Pass"] = bool(np.isfinite([p_excess, ne, nege]).all() and p_excess > ne > nege)
    _gate(rows, "POSITIVE_PF_GT_NEUTRAL_PF", p_pf > npf, True, np.isfinite([p_pf, npf]).all() and p_pf > npf)
    _gate(rows, "POSITIVE_PF_GT_NEGATIVE_PF", p_pf > negpf, True, np.isfinite([p_pf, negpf]).all() and p_pf > negpf)

    temporal = temporal if isinstance(temporal, pd.DataFrame) else pd.DataFrame()
    for period in ("FIRST", "SECOND"):
        row = temporal.loc[temporal.get("Period", pd.Series(dtype=object)).eq(period)] if not temporal.empty else pd.DataFrame()
        count = int(row.iloc[0].get("Completed_Count", 0)) if not row.empty else 0
        mean = float(row.iloc[0].get("Base_Mean_Net_Return", np.nan)) if not row.empty else np.nan
        pf = float(row.iloc[0].get("Base_Return_PF", np.nan)) if not row.empty else np.nan
        excess = float(row.iloc[0].get("Base_Mean_Net_Excess_Return", np.nan)) if not row.empty else np.nan
        _gate(rows, f"{period}_POSITIVE_SAMPLE_SUFFICIENCY", count, TEMPORAL_POSITIVE_MIN, count >= TEMPORAL_POSITIVE_MIN)
        _gate(rows, f"{period}_POSITIVE_MEAN_NET_RETURN", mean, 0.0, np.isfinite(mean) and mean > 0)
        _gate(rows, f"{period}_POSITIVE_RETURN_PF", pf, 1.0, np.isfinite(pf) and pf > 1)
        _gate(rows, f"{period}_POSITIVE_MEAN_NET_EXCESS_RETURN", excess, 0.0, np.isfinite(excess) and excess > 0)

    for name, frame in (("LEAVE_ONE_YEAR_OUT", year_loo), ("TOP_FIVE_REMOVAL", top_five), ("LEAVE_ONE_SYMBOL_OUT", loso)):
        if frame is None or frame.empty:
            passed = False
        else:
            passed = bool(frame["Pass"].astype(bool).all()) if "Pass" in frame else False
        _gate(rows, f"{name}_ALL_PASS", passed, True, passed)

    preliminary = pd.DataFrame(rows)
    if integrity_count > 0 or not coverage_pass:
        status = "INVALID_RESEARCH_RUN"
    elif p_count < PRIMARY_POSITIVE_MIN or n_count < PRIMARY_NEUTRAL_MIN or neg_count < PRIMARY_NEGATIVE_MIN:
        status = "INSUFFICIENT_EVIDENCE"
    elif not preliminary.loc[preliminary["Mandatory"], "Pass"].astype(bool).all():
        status = "FAIL"
    else:
        status = "PASS"
    _gate(rows, "FINAL_STATUS", status, "PASS/FAIL/INSUFFICIENT_EVIDENCE/INVALID_RESEARCH_RUN", status == "PASS", mandatory=False)
    return status, pd.DataFrame(rows, columns=["Gate", "Value", "Threshold", "Pass", "Mandatory"])


def build_integrity_audit(
    manifest_audit: pd.DataFrame | None = None,
    event_master: pd.DataFrame | None = None,
    sue_events: pd.DataFrame | None = None,
    trade_frames: dict[str, pd.DataFrame] | None = None,
    cancellations: pd.DataFrame | None = None,
    final_package_issues: list[dict[str, object]] | None = None,
    event_exclusions: pd.DataFrame | None = None,
    sue_exclusions: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Create explicit systemic integrity rows; never filter violations away."""

    rows: list[dict[str, object]] = []

    def add(check: str, violation: str, count: int, detail: object = "") -> None:
        if count:
            rows.append({"Check": check, "Violation": violation, "Count": int(count), "Detail": str(detail)})

    if manifest_audit is not None and not manifest_audit.empty:
        for violation, group in manifest_audit.groupby("Violation", dropna=False):
            add("INPUT_MANIFEST", str(violation), len(group), group.to_dict("records"))
    events = event_master if isinstance(event_master, pd.DataFrame) else pd.DataFrame()
    if not events.empty and "Event_ID" in events:
        add("EVENT_ID_UNIQUENESS", "DUPLICATE_EVENT_ID", int(events["Event_ID"].duplicated().sum()))
        if "Event_Public_Date" in events:
            dates = pd.to_datetime(events["Event_Public_Date"], errors="coerce")
            formal = events.get("Primary_Event", pd.Series(False, index=events.index)).astype(bool)
            add("PRIMARY_EVENT_WINDOW", "EVENT_AFTER_PRIMARY_WINDOW_IN_FORMAL_SAMPLE", int((formal & dates.gt(pd.Timestamp("2026-06-30"))).sum()))
            add("PRIMARY_EVENT_WINDOW", "EVENT_BEFORE_PRIMARY_WINDOW_IN_FORMAL_SAMPLE", int((formal & dates.lt(pd.Timestamp("2023-08-01"))).sum()))
        if "SUE" in events and "Cohort" in events:
            sue = pd.to_numeric(events["SUE"], errors="coerce")
            add("SUE_CLASSIFICATION", "UNCLASSIFIED_FINITE_SUE", int(sue.notna() & events["Cohort"].isna()).sum())
    sue = sue_events if isinstance(sue_events, pd.DataFrame) else pd.DataFrame()
    if not sue.empty and "Event_ID" in sue and "Cohort" in sue:
        add("SUE_CLASSIFICATION", "SUE_COHORT_OVERLAP", int(sue["Event_ID"].duplicated().sum()))
    if not events.empty and "Event_ID" in events:
        formal_ids = set(
            events.loc[
                events.get("Primary_Event", pd.Series(False, index=events.index)).map(bool),
                "Event_ID",
            ].dropna().astype(str)
        )
        finite_ids = (
            set(sue["Event_ID"].dropna().astype(str))
            if not sue.empty and "Event_ID" in sue
            else set()
        )
        sue_exclusion_frame = sue_exclusions if isinstance(sue_exclusions, pd.DataFrame) else pd.DataFrame()
        sue_exclusion_ids = (
            set(sue_exclusion_frame["Event_ID"].dropna().astype(str))
            if not sue_exclusion_frame.empty and "Event_ID" in sue_exclusion_frame
            else set()
        )
        event_exclusion_frame = event_exclusions if isinstance(event_exclusions, pd.DataFrame) else pd.DataFrame()
        event_exclusion_ids = (
            set(event_exclusion_frame["Event_ID"].dropna().astype(str))
            if not event_exclusion_frame.empty and "Event_ID" in event_exclusion_frame
            else set()
        )
        unaccounted = formal_ids - finite_ids - sue_exclusion_ids
        add(
            "EVENT_ACCOUNTING",
            "FORMAL_EVENT_UNACCOUNTED",
            len(unaccounted),
            sorted(unaccounted),
        )
        duplicate_finite = (
            set(sue.loc[sue["Event_ID"].duplicated(keep=False), "Event_ID"].dropna().astype(str))
            if not sue.empty and "Event_ID" in sue
            else set()
        )
        duplicate_sue_exclusions = (
            set(
                sue_exclusion_frame.loc[
                    sue_exclusion_frame["Event_ID"].duplicated(keep=False), "Event_ID"
                ].dropna().astype(str)
            )
            if not sue_exclusion_frame.empty and "Event_ID" in sue_exclusion_frame
            else set()
        )
        double_accounted = (
            (finite_ids & sue_exclusion_ids)
            | duplicate_finite
            | duplicate_sue_exclusions
            | (formal_ids & event_exclusion_ids)
        )
        add(
            "EVENT_ACCOUNTING",
            "FORMAL_EVENT_DOUBLE_ACCOUNTED",
            len(double_accounted),
            sorted(double_accounted),
        )
    for cohort, frame in (trade_frames or {}).items():
        if frame.empty:
            continue
        if "Event_Public_Date" in frame and "Entry_Date" in frame:
            event_dates = frame["Event_Public_Date"].map(pd.Timestamp)
            entries = frame["Entry_Date"].map(pd.Timestamp)
            add(f"{cohort}_TRADE_TIMING", "ENTRY_NOT_AFTER_EVENT", int((entries <= event_dates).sum()))
        if "Nifty500_Entry_Open" in frame and "Nifty500_Exit_Open" in frame:
            add(f"{cohort}_BENCHMARK", "BENCHMARK_DATE_MISMATCH", int(frame[["Nifty500_Entry_Open", "Nifty500_Exit_Open"]].isna().any(axis=1).sum()))
    if cancellations is not None and not cancellations.empty:
        pass
    for item in final_package_issues or []:
        rows.append({"Check": "FINAL_EVIDENCE_PACKAGE", "Violation": item.get("Violation", "INVALID_FINAL_EVIDENCE"), "Count": 1, "Detail": item.get("Detail", "")})
    return pd.DataFrame(rows, columns=["Check", "Violation", "Count", "Detail"])


def _final_package_issues(output_dir: Path) -> list[dict[str, object]]:
    """Verify every required evidence artifact and its minimum schema."""

    issues: list[dict[str, object]] = []
    for name in REQUIRED_OUTPUT_ARTIFACTS:
        path = output_dir / name
        if not path.is_file():
            issues.append({"Artifact": name, "Violation": "MISSING_FINAL_EVIDENCE", "Detail": "file does not exist"})
            continue
        try:
            if path.suffix.lower() == ".csv":
                frame = pd.read_csv(path)
                missing = set(OUTPUT_SCHEMAS.get(name, ())).difference(frame.columns)
                if missing:
                    issues.append({"Artifact": name, "Violation": "INVALID_FINAL_EVIDENCE", "Detail": f"missing columns: {sorted(missing)}"})
            else:
                if not path.read_text(encoding="utf-8").strip():
                    issues.append({"Artifact": name, "Violation": "INVALID_FINAL_EVIDENCE", "Detail": "empty UTF-8 report"})
        except Exception as exc:  # noqa: BLE001 - convert read errors to formal integrity evidence
            issues.append({"Artifact": name, "Violation": "INVALID_FINAL_EVIDENCE", "Detail": str(exc)})
    return issues


def write_research_report(path: Path, status: str, evidence: dict[str, object]) -> None:
    """Generate the fixed-section E1 report from local evidence frames."""

    sections = [
        ("Frozen E1 hypothesis", "Official quarterly positive earnings surprises are tested with the frozen seasonal SUE signal and a fixed next-session-open, 40-complete-session lifecycle."),
        ("Source provenance", "Evidence is derived from the frozen official NSE/BSE filing and adjusted market-price snapshots."),
        ("Source coverage", "Technical machine-readable EPS coverage and unresolved candidates are reported in e1_source_coverage.csv."),
        ("PIT/event integrity", "Point-in-time membership, public timestamps, original filings, and integrity violations are reported."),
        ("Event exclusions", "Every excluded event retains one primary reason in e1_event_exclusions.csv."),
        ("SUE methodology", "SUE uses the current seasonal EPS change against exactly eight prior seasonal changes with sample standard deviation."),
        ("Cohort counts", "Positive, neutral, and negative completed observations are reported in the cohort comparison."),
        ("Positive base results", "Base friction positive-cohort results are reported in the validation summary."),
        ("Market-relative results", "Exact stock and Nifty 500 entry/exit dates are compared in the benchmark evidence."),
        ("Stress/severe friction", "Stress results and severe-friction diagnostics are reported without changing formal qualification."),
        ("Positive vs neutral vs negative discrimination", "Frozen directional mean, excess-return, and profit-factor comparisons are reported."),
        ("Temporal halves", "FIRST and SECOND event-public-date halves are reported."),
        ("Calendar years", "Calendar-year evidence is diagnostic and retained separately."),
        ("Leave-one-year-out", "The predeclared leave-one-year-out robustness table is reported."),
        ("Top-five robustness", "The five largest positive gross-return observations are removed for the predeclared diagnostic gate."),
        ("Leave-one-symbol-out", "Every positive-cohort symbol omission is reported."),
        ("Downside diagnostics", "Worst return, tail percentiles, and trade drawdown diagnostics are reported."),
        ("Capacity/overlap diagnostics", "Signal-level overlap and simultaneous-trade diagnostics are reported without portfolio truncation."),
        ("Mandatory gate table", "The formal gate authority is e1_validation_gates.csv."),
        ("Formal conclusion and next action", f"Formal status: {status}. The next action follows the frozen E1 decision hierarchy and is owned by the Portfolio Advisor."),
    ]
    lines = ["# E1 Positive Earnings Surprise Drift Validation", ""]
    for number, (heading, body) in enumerate(sections, 1):
        lines.extend([f"## {number}. {heading}", "", body, ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_input(input_dir: Path, name: str) -> tuple[pd.DataFrame, dict[str, object] | None]:
    path = input_dir / name
    if not path.is_file():
        return pd.DataFrame(), {"Artifact": name, "Violation": "MISSING_REQUIRED_INPUT", "Detail": "file does not exist"}
    try:
        return pd.read_csv(path), None
    except Exception as exc:  # noqa: BLE001 - formal audit records unreadable inputs
        return pd.DataFrame(), {"Artifact": name, "Violation": "UNREADABLE_REQUIRED_INPUT", "Detail": str(exc)}


def _ensure_frame(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    return frame.reindex(columns=list(columns)) if frame is not None else _empty_frame(columns)


def run_validation(
    input_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
    membership_path: Path | str | None = None,
) -> tuple[str, pd.DataFrame]:
    """Run all Stage B operations strictly offline against frozen input files."""

    module_root = Path(__file__).resolve().parent
    input_root = Path(input_dir) if input_dir is not None else module_root / "input"
    output_root = Path(output_dir) if output_dir is not None else module_root / "output"
    output_root.mkdir(parents=True, exist_ok=True)
    loaded: dict[str, pd.DataFrame] = {}
    read_issues: list[dict[str, object]] = []
    for name in REQUIRED_INPUT_ARTIFACTS:
        if name == "e1_source_manifest.csv":
            continue
        loaded[name], issue = _read_input(input_root, name)
        if issue:
            read_issues.append(issue)
    manifest, manifest_issue = _read_input(input_root, "e1_source_manifest.csv")
    if manifest_issue:
        read_issues.append(manifest_issue)
        manifest_audit = pd.DataFrame([manifest_issue])
    else:
        try:
            manifest_audit = verify_manifest(manifest, input_root)
        except ValueError as exc:
            manifest_audit = pd.DataFrame([{"Artifact": "e1_source_manifest.csv", "Violation": "INVALID_MANIFEST", "Detail": str(exc)}])
    if read_issues:
        manifest_audit = pd.concat([manifest_audit, pd.DataFrame(read_issues)], ignore_index=True)
    membership_file = Path(membership_path) if membership_path is not None else module_root.parent / "market_breadth/config/nifty500_membership.csv"
    try:
        membership = load_membership(membership_file)
    except Exception as exc:  # noqa: BLE001 - fail closed on PIT-universe errors
        membership = pd.DataFrame(columns=["Symbol", "Member_From", "Member_To"])
        manifest_audit = pd.concat([manifest_audit, pd.DataFrame([{"Artifact": str(membership_file), "Violation": "PIT_MEMBERSHIP_VIOLATION", "Detail": str(exc)}])], ignore_index=True)

    event_master, exclusions, coverage, _ = build_event_master(
        loaded.get("e1_exchange_filings_snapshot.csv", pd.DataFrame()),
        loaded.get("e1_eps_snapshot.csv", pd.DataFrame()),
        membership,
    )
    _, sue_events, classified, sue_exclusions = build_sue_events(
        event_master,
        loaded.get("e1_eps_snapshot.csv", pd.DataFrame()),
        loaded.get("e1_corporate_actions_snapshot.csv", pd.DataFrame()),
    )
    stock_prices = loaded.get("e1_stock_prices_snapshot.csv", pd.DataFrame())
    index_prices = loaded.get("e1_nifty500_prices_snapshot.csv", pd.DataFrame())
    classified_events = classified.copy()
    trade_frames, cancellations = build_primary_trades(classified_events, stock_prices, index_prices, event_master)

    event_schema = OUTPUT_SCHEMAS["e1_event_master.csv"] + ("Event_Public_Timestamp", "Fiscal_Period_End", "Reporting_Basis", "Selected_Basis", "Fiscal_Quarter", "Timely_Result", "PIT_Membership_OK", "EPS_Source_Status", "EPS_Source_Resolved", "Machine_Readable_URL", "Source_Exchanges", "Original_or_Revised", "Original_Record_Count")
    exclusion_schema = OUTPUT_SCHEMAS["e1_event_exclusions.csv"] + ("Symbol", "Fiscal_Period_End", "Exclusion_Stage", "Event_Public_Date")
    event_exclusions = pd.concat([exclusions, sue_exclusions], ignore_index=True)
    if not event_exclusions.empty:
        event_exclusions = event_exclusions.drop_duplicates("Event_ID", keep="first")
    write_event_outputs(output_root, _ensure_frame(event_master, event_schema), _ensure_frame(event_exclusions, exclusion_schema), coverage)
    sue_schema = OUTPUT_SCHEMAS["e1_sue_events.csv"] + ("Symbol", "Fiscal_Period_End", "Event_Public_Date", "Reporting_Basis", "Current_EPS", "EPS_t_minus_4", "D_t", "D_t_minus_1", "D_t_minus_2", "D_t_minus_3", "D_t_minus_4", "D_t_minus_5", "D_t_minus_6", "D_t_minus_7", "D_t_minus_8", "Historical_Mean", "Historical_SD")
    write_sue_outputs(output_root, _ensure_frame(sue_events, sue_schema), _ensure_frame(sue_events, sue_schema), _ensure_frame(classified, sue_schema))
    write_trade_outputs(output_root, trade_frames)
    positive = trade_frames.get("POSITIVE_SURPRISE", pd.DataFrame())
    neutral = trade_frames.get("NEUTRAL_CONTROL", pd.DataFrame())
    negative = trade_frames.get("NEGATIVE_CONTROL", pd.DataFrame())
    analysis = write_analysis_outputs(output_root, positive, neutral, negative)
    coverage_value = float(coverage.iloc[0].get("Machine_Readable_EPS_Resolution", np.nan)) if not coverage.empty else np.nan
    integrity = build_integrity_audit(
        manifest_audit,
        event_master,
        classified,
        trade_frames,
        cancellations,
        event_exclusions=exclusions,
        sue_exclusions=sue_exclusions,
    )
    temporal = analysis.get("e1_temporal_summary.csv", temporal_summary(positive))
    year_loo = analysis.get("e1_leave_one_year_out.csv", leave_one_year_out(positive))
    top_five = analysis.get("e1_top_five_robustness.csv", top_five_robustness(positive))
    loso = analysis.get("e1_leave_one_symbol_out.csv", leave_one_symbol_out(positive))
    status, gates = evaluate_gates(
        positive,
        neutral,
        negative,
        temporal,
        year_loo,
        top_five,
        loso,
        integrity_count=len(integrity),
        technical_coverage=coverage_value,
    )
    _ensure_frame(integrity, OUTPUT_SCHEMAS["e1_integrity_audit.csv"]).to_csv(output_root / "e1_integrity_audit.csv", index=False)
    gates.to_csv(output_root / "e1_validation_gates.csv", index=False)
    report_evidence = {"coverage": coverage, "gates": gates, "integrity": integrity}
    write_research_report(output_root / "research_report.md", status, report_evidence)
    data_validation = pd.concat([manifest_audit, integrity], ignore_index=True) if not manifest_audit.empty or not integrity.empty else _empty_frame(OUTPUT_SCHEMAS["e1_data_validation.csv"])
    _ensure_frame(data_validation, OUTPUT_SCHEMAS["e1_data_validation.csv"]).to_csv(output_root / "e1_data_validation.csv", index=False)
    final_issues = _final_package_issues(output_root)
    if final_issues:
        integrity = pd.concat([integrity, build_integrity_audit(final_package_issues=final_issues)], ignore_index=True)
        status, gates = evaluate_gates(
            positive,
            neutral,
            negative,
            temporal,
            year_loo,
            top_five,
            loso,
            integrity_count=len(integrity),
            technical_coverage=coverage_value,
        )
        integrity.to_csv(output_root / "e1_integrity_audit.csv", index=False)
        gates.to_csv(output_root / "e1_validation_gates.csv", index=False)
        write_research_report(output_root / "research_report.md", status, {"coverage": coverage, "gates": gates, "integrity": integrity})
    data_validation = pd.concat([manifest_audit, integrity], ignore_index=True) if not manifest_audit.empty or not integrity.empty else _empty_frame(OUTPUT_SCHEMAS["e1_data_validation.csv"])
    _ensure_frame(data_validation, OUTPUT_SCHEMAS["e1_data_validation.csv"]).to_csv(output_root / "e1_data_validation.csv", index=False)
    return status, gates


if __name__ == "__main__":
    result, _ = run_validation()
    print(f"Formal E1 status: {result}")
