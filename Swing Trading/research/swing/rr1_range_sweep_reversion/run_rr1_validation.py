"""Run one unchanged RR1 validation from source inputs to formal evidence."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_rr1_results import (
    bootstrap_mean_ci,
    build_leave_one_symbol_out,
    build_leave_one_year_out,
    build_overlap_diagnostic,
    build_temporal_summary,
    build_top_five_robustness,
    evaluate_gates,
    render_report,
    summarize_lens_a,
    summarize_practical,
)
from audit_rr1_integrity import accounting_invariants, run_integrity_audit
from build_rr1_features import (
    build_feature_frames,
    canonical_sessions,
    load_membership,
    load_nifty500_benchmark,
)
from constants import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    DOWNLOAD_END_EXCLUSIVE,
    DOWNLOAD_START,
    MEMBERSHIP_PATH,
    SIGNAL_END,
    SIGNAL_START,
)
from generate_rr1_signals import (
    build_lower_entries,
    build_signal_tables,
    build_upper_references,
)
from simulate_rr1_outcomes import build_outcomes


def _empty_like(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _injected_validation(feature_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for symbol in sorted(feature_frames):
        frame = feature_frames[symbol]
        dates = pd.to_datetime(frame["Date"]).dt.normalize()
        window = dates.between(SIGNAL_START, SIGNAL_END)
        rows.append(
            {
                "Symbol": symbol,
                "Yahoo_Ticker": str(frame.get("Yahoo_Ticker", pd.Series([""])).iloc[0])
                if "Yahoo_Ticker" in frame.columns and len(frame)
                else "",
                "Member_From": "",
                "Member_To": "",
                "Raw_Rows": len(frame),
                "Canonical_Rows": len(frame),
                "Earliest_Date": dates.min().date().isoformat() if len(frame) else "",
                "Latest_Date": dates.max().date().isoformat() if len(frame) else "",
                "Duplicate_Dates": int(dates.duplicated().sum()),
                "Provider_Overlap_Dates": 0,
                "Missing_Open": int(frame["Open"].isna().sum()),
                "Missing_High": int(frame["High"].isna().sum()),
                "Missing_Low": int(frame["Low"].isna().sum()),
                "Missing_Close": int(frame["Close"].isna().sum()),
                "Missing_Volume": int(frame["Volume"].isna().sum()),
                "Exact_Prehistory_Sessions": int(frame.loc[window, "Exact_Prehistory_61"].sum())
                if "Exact_Prehistory_61" in frame.columns
                else 0,
                "Usable_Signal_Window_Sessions": int(window.sum()),
                "Download_Error": "",
            }
        )
    return pd.DataFrame(rows)


def _robustness_pass(frame: pd.DataFrame) -> bool:
    return bool(
        not frame.empty
        and frame["Base_Practical_Mean_R"].notna().all()
        and frame["Base_Practical_R_PF"].notna().all()
        and (frame["Base_Practical_Mean_R"] > 0).all()
        and (frame["Base_Practical_R_PF"] > 1.0).all()
    )


def _temporal_pass(temporal: pd.DataFrame) -> bool:
    return bool(
        len(temporal) == 2
        and (temporal["Base_Practical_Mean_R"] > 0).all()
        and (temporal["Base_Practical_R_PF"] > 1.0).all()
        and (temporal["Mean_Base_Practical_Excess_Return"] > 0).all()
    )


def _bootstrap_summary(
    lens_a: pd.DataFrame, practical: pd.DataFrame, upper: pd.DataFrame
) -> pd.DataFrame:
    series: list[tuple[str, Iterable[object]]] = [
        ("LOWER_GROSS_15_SESSION_RETURN", lens_a.get("Gross_Return", [])),
        ("LOWER_BASE_NET_15_SESSION_RETURN", lens_a.get("Base_Net_Return", [])),
        ("LOWER_BASE_PRACTICAL_MEAN_R", practical.get("Base_Net_R", [])),
        ("LOWER_BASE_PRACTICAL_EXCESS_RETURN", practical.get("Base_Practical_Excess_Return", [])),
    ]
    if not lens_a.empty and not upper.empty:
        n = min(len(lens_a), len(upper))
        series.append(
            (
                "LOWER_MINUS_UPPER_GROSS_15_RETURN",
                lens_a["Gross_Return"].iloc[:n].to_numpy()
                - upper["Mirror_Gross_Return_15"].iloc[:n].to_numpy(),
            )
        )
    rows: list[dict[str, object]] = []
    for offset, (metric, values) in enumerate(series):
        numeric = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
        lower, upper_ci = bootstrap_mean_ci(
            numeric.to_numpy(),
            seed=BOOTSTRAP_SEED + offset,
            resamples=BOOTSTRAP_RESAMPLES,
        )
        rows.append(
            {
                "Metric": metric,
                "Count": len(numeric),
                "Mean": float(numeric.mean()) if len(numeric) else np.nan,
                "CI_Lower_95": lower,
                "CI_Upper_95": upper_ci,
                "Seed": BOOTSTRAP_SEED + offset,
                "Resamples": BOOTSTRAP_RESAMPLES,
            }
        )
    return pd.DataFrame(rows)


def _analysis_evidence(
    lens_a: pd.DataFrame,
    practical: pd.DataFrame,
    upper: pd.DataFrame,
    temporal: pd.DataFrame,
    top_five: pd.DataFrame,
    years: pd.DataFrame,
    symbols: pd.DataFrame,
    audit: pd.DataFrame,
    lower_signals: pd.DataFrame,
    lower_entries: pd.DataFrame,
    lower_cancellations: pd.DataFrame,
    upper_signals: pd.DataFrame,
    upper_refs: pd.DataFrame,
    upper_cancellations: pd.DataFrame,
    diagnostics: pd.DataFrame,
) -> dict[str, object]:
    a = summarize_lens_a(lens_a)
    p = summarize_practical(practical)
    upper_mean = (
        float(pd.to_numeric(upper["Mirror_Gross_Return_15"], errors="coerce").mean())
        if not upper.empty
        else np.nan
    )
    inv = accounting_invariants(
        lower_signals,
        lower_entries,
        lower_cancellations,
        lens_a,
        practical,
        upper_signals,
        upper_refs,
        upper_cancellations,
        upper,
        diagnostics,
    )
    integrity_ok = bool(not audit.empty and audit["Passed"].astype(bool).all())
    first = temporal.loc[temporal["Half"] == "FIRST"].iloc[0] if (temporal["Half"] == "FIRST").any() else {}
    second = temporal.loc[temporal["Half"] == "SECOND"].iloc[0] if (temporal["Half"] == "SECOND").any() else {}
    return {
        "integrity_ok": integrity_ok and all(inv.values()),
        "lower_count": len(practical),
        "first_count": int(first.get("Completed_Paired_Lower", 0)),
        "second_count": int(second.get("Completed_Paired_Lower", 0)),
        "upper_count": len(upper),
        "lens_a_mean": a["Base_Net_Mean_Return"],
        "lens_a_pf": a["Base_Net_Return_PF"],
        "lens_a_excess": a["Mean_Base_Excess_Return"],
        "practical_mean_r": p["Base_Practical_Mean_R"],
        "practical_rpf": p["Base_Practical_R_PF"],
        "practical_excess": p["Mean_Base_Practical_Excess_Return"],
        "stress_mean_r": p["Stress_Practical_Mean_R"],
        "stress_rpf": p["Stress_Practical_R_PF"],
        "lower_mean": a["Gross_Mean_Return"],
        "upper_mean": upper_mean,
        "first_practical_mean_r": first.get("Base_Practical_Mean_R", np.nan),
        "first_practical_rpf": first.get("Base_Practical_R_PF", np.nan),
        "first_practical_excess": first.get("Mean_Base_Practical_Excess_Return", np.nan),
        "second_practical_mean_r": second.get("Base_Practical_Mean_R", np.nan),
        "second_practical_rpf": second.get("Base_Practical_R_PF", np.nan),
        "second_practical_excess": second.get("Mean_Base_Practical_Excess_Return", np.nan),
        "temporal_ok": _temporal_pass(temporal),
        "topfive_ok": _robustness_pass(top_five),
        "year_robustness_ok": _robustness_pass(years),
        "symbol_robustness_ok": _robustness_pass(symbols),
        "signal_window": f"{SIGNAL_START.date()}..{SIGNAL_END.date()}",
        "benchmark": "^CRSLDX",
        "range_qualified_count": len(lower_signals) + len(upper_signals),
        "lower_signal_count": len(lower_signals),
        "upper_signal_count": len(upper_signals),
        "lower_accounting": f"{len(lower_entries)} accepted / {len(lower_cancellations)} cancelled / {len(lens_a)} paired complete",
        "upper_accounting": f"{len(upper_refs)} accepted / {len(upper_cancellations)} cancelled / {len(upper)} complete",
        "lens_a_summary": a,
        "practical_summary": p,
        "mirror_summary": {"Count": len(upper), "Mean_Gross_Return": upper_mean},
    }


def _write_atomic(output_dir: Path, artifacts: dict[str, object]) -> None:
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
    try:
        for name, artifact in artifacts.items():
            target = temporary / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(artifact, pd.DataFrame):
                artifact.to_csv(target, index=False)
            else:
                target.write_text(str(artifact), encoding="utf-8")
        try:
            if output_dir.exists():
                shutil.rmtree(output_dir)
            # Windows does not reliably replace an existing directory with
            # ``os.replace``.  The complete staged tree is promoted only after
            # the old evidence directory has been removed.
            os.rename(temporary, output_dir)
        except PermissionError:
            # Some managed Windows workspaces deny directory promotion while
            # allowing file writes.  The staged set still prevents new files
            # from being mixed with old files before this fallback begins.
            output_dir.mkdir(parents=True, exist_ok=True)
            for existing in output_dir.iterdir():
                if existing.is_dir():
                    shutil.rmtree(existing)
                else:
                    existing.unlink()
            for staged in temporary.iterdir():
                os.replace(staged, output_dir / staged.name)
            temporary.rmdir()
        temporary = None  # type: ignore[assignment]
    finally:
        if temporary is not None and temporary.exists():
            shutil.rmtree(temporary)


def _failure_artifacts(output_dir: Path, exc: Exception) -> None:
    audit = pd.DataFrame(
        [{"Entity": "RUN", "Check": "SOURCE_OR_BUILD", "Passed": False,
          "Observed": f"{type(exc).__name__}: {exc}", "Expected": "successful build"}]
    )
    gates = pd.DataFrame(
        [{"Gate": "RESEARCH_VALIDITY", "Passed": False,
          "Observed": "source/build failure", "Requirement": "valid run", "Category": "VALIDITY"}]
    )
    report = render_report({"integrity_ok": False}, gates, "INVALID_RESEARCH_RUN")
    _write_atomic(output_dir, {"rr1_integrity_audit.csv": audit, "research_report.md": report})


def run_validation(
    feature_frames: dict[str, pd.DataFrame] | None = None,
    benchmark: pd.DataFrame | None = None,
    membership: pd.DataFrame | None = None,
    output_dir: Path | None = None,
) -> str:
    """Run the immutable RR1 stage order and return exactly one final status."""

    module_dir = Path(__file__).resolve().parent
    output_path = Path(output_dir) if output_dir is not None else module_dir / "output"
    try:
        root = module_dir.parents[3]
        membership = membership if membership is not None else load_membership(
            root / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv"
        )
        benchmark = benchmark if benchmark is not None else load_nifty500_benchmark(
            DOWNLOAD_START, DOWNLOAD_END_EXCLUSIVE
        )
        if feature_frames is None:
            feature_frames, validation = build_feature_frames(membership, benchmark)
        else:
            validation = _injected_validation(feature_frames)
        sessions = canonical_sessions(benchmark)
        candidates, lower_signals, upper_signals = build_signal_tables(feature_frames, membership)
        lower_entries, lower_cancellations = build_lower_entries(
            lower_signals, feature_frames, sessions
        )
        upper_refs, upper_cancellations = build_upper_references(
            upper_signals, feature_frames, sessions
        )
        lens_a, practical, upper_outcomes, diagnostics = build_outcomes(
            lower_entries, upper_refs, feature_frames, benchmark, sessions
        )
        audit = run_integrity_audit(
            lower_entries,
            upper_refs,
            lower_signals,
            upper_signals,
            lower_cancellations,
            upper_cancellations,
            lens_a,
            practical,
            upper_outcomes,
            diagnostics,
            feature_frames,
            membership,
            benchmark,
            sessions,
        )
        temporal = build_temporal_summary(practical, lens_a)
        top_five = build_top_five_robustness(practical)
        years = build_leave_one_year_out(practical)
        symbols = build_leave_one_symbol_out(practical)
        bootstrap = _bootstrap_summary(lens_a, practical, upper_outcomes)
        overlap = build_overlap_diagnostic(lower_entries, sessions)
        evidence = _analysis_evidence(
            lens_a, practical, upper_outcomes, temporal, top_five, years, symbols,
            audit, lower_signals, lower_entries, lower_cancellations, upper_signals,
            upper_refs, upper_cancellations, diagnostics,
        )
        gates, status = evaluate_gates(evidence)
        validation_summary = pd.DataFrame(
            [
                {"Metric": "Range_Qualified_Sessions", "Value": len(candidates)},
                {"Metric": "Lower_Signals", "Value": len(lower_signals)},
                {"Metric": "Upper_Signals", "Value": len(upper_signals)},
                {"Metric": "Lower_Accepted", "Value": len(lower_entries)},
                {"Metric": "Lower_Cancelled", "Value": len(lower_cancellations)},
                {"Metric": "Lower_Paired_Completed", "Value": len(practical)},
                {"Metric": "Upper_Completed", "Value": len(upper_outcomes)},
                {"Metric": "Integrity_Failures", "Value": int((~audit["Passed"].astype(bool)).sum())},
                {"Metric": "FINAL_STATUS", "Value": status},
            ]
        )
        artifacts: dict[str, object] = {
            "rr1_data_validation.csv": validation,
            "rr1_range_candidates.csv": candidates,
            "rr1_lower_signals.csv": lower_signals,
            "rr1_upper_signals.csv": upper_signals,
            "rr1_lower_entries.csv": lower_entries,
            "rr1_lower_entry_cancellations.csv": lower_cancellations,
            "rr1_upper_references.csv": upper_refs,
            "rr1_upper_cancellations.csv": upper_cancellations,
            "rr1_lens_a_trades.csv": lens_a,
            "rr1_practical_trades.csv": practical,
            "rr1_upper_outcomes.csv": upper_outcomes,
            "rr1_forward_diagnostics.csv": diagnostics,
            "rr1_validation_summary.csv": validation_summary,
            "rr1_temporal_summary.csv": temporal,
            "rr1_top_five_robustness.csv": top_five,
            "rr1_leave_one_year_out.csv": years,
            "rr1_leave_one_symbol_out.csv": symbols,
            "rr1_bootstrap_summary.csv": bootstrap,
            "rr1_overlap_diagnostic.csv": overlap,
            "rr1_integrity_audit.csv": audit,
            "rr1_validation_gates.csv": gates,
            "research_report.md": render_report(evidence, gates, status),
        }
        _write_atomic(output_path, artifacts)
        return status
    except Exception as exc:
        _failure_artifacts(output_path, exc)
        raise


def main() -> None:
    status = run_validation()
    print(f"FINAL_STATUS: {status}")
    if status == "INVALID_RESEARCH_RUN":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
