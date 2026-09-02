from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_rr1_features import compute_rr1_features  # noqa: E402
from run_rr1_validation import (  # noqa: E402
    _bootstrap_summary,
    _range_qualified_count,
    _write_atomic,
    run_validation,
)


def synthetic_inputs():
    sessions = pd.bdate_range("2024-01-01", periods=80)
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA", "BBB", "CCC", "DDD"],
            "Member_From": [sessions[0]] * 4,
            "Member_To": [sessions[-1]] * 4,
            "Downloadable": [True] * 4,
            "Yahoo_Ticker": ["AAA.NS", "BBB.NS", "CCC.NS", "DDD.NS"],
        }
    )
    feature_frames: dict[str, pd.DataFrame] = {}
    for symbol in membership["Symbol"]:
        close = np.array([105.0 + (i % 2) for i in range(len(sessions))])
        high = close + 15.0
        low = close - 5.0
        open_ = close.copy()
        volume = np.full(len(sessions), 2_000_000.0)
        signal_positions = [61]
        if symbol == "AAA":
            signal_positions.append(65)
        if symbol == "DDD":
            signal_positions.append(75)
        for position in signal_positions:
            low[position] = 99.0 if position == 61 else 98.0
            high[position] = 122.0 if position == 61 else 123.0
            close[position] = 105.0
        if symbol in {"AAA", "BBB"}:
            open_[62] = 99.0
        elif symbol == "CCC":
            open_[62] = 108.0
        else:
            open_[76] = 98.0
        # Make the first accepted AAA observation hit target and BBB hit stop.
        high[62] = 111.0 if symbol == "AAA" else 105.0
        low[62] = 98.0 if symbol == "AAA" else 90.0 if symbol == "BBB" else close[62] - 5.0
        # Keep the later mirror reference's fixed-horizon outcome negative.
        open_[77] = 90.0
        raw = pd.DataFrame(
            {
                "Date": sessions,
                "Open": open_,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": volume,
            }
        )
        features = compute_rr1_features(raw, sessions)
        features["Symbol"] = symbol
        features["Yahoo_Ticker"] = f"{symbol}.NS"
        features["Point_In_Time_Member"] = True
        feature_frames[symbol] = features
    benchmark = pd.DataFrame(
        {
            "Date": sessions,
            "Open": np.full(len(sessions), 200.0),
            "High": np.full(len(sessions), 201.0),
            "Low": np.full(len(sessions), 199.0),
            "Close": np.full(len(sessions), 200.0),
            "Volume": np.full(len(sessions), 1_000_000.0),
        }
    )
    return feature_frames, benchmark, membership


def test_synthetic_rr1_run_preserves_accounting_and_incomplete_pairs(tmp_path):
    feature_frames, benchmark, membership = synthetic_inputs()
    output_dir = tmp_path / "output"

    final_status = run_validation(
        feature_frames=feature_frames,
        benchmark=benchmark,
        membership=membership,
        output_dir=output_dir,
    )

    lower_signals = pd.read_csv(output_dir / "rr1_lower_signals.csv")
    lower_entries = pd.read_csv(output_dir / "rr1_lower_entries.csv")
    lower_cancellations = pd.read_csv(output_dir / "rr1_lower_entry_cancellations.csv")
    upper_cancellations = pd.read_csv(output_dir / "rr1_upper_cancellations.csv")
    lens_a = pd.read_csv(output_dir / "rr1_lens_a_trades.csv")
    practical = pd.read_csv(output_dir / "rr1_practical_trades.csv")
    diagnostics = pd.read_csv(output_dir / "rr1_forward_diagnostics.csv")
    audit = pd.read_csv(output_dir / "rr1_integrity_audit.csv")
    candidates = pd.read_csv(output_dir / "rr1_range_candidates.csv")
    validation_summary = pd.read_csv(output_dir / "rr1_validation_summary.csv")
    report = (output_dir / "research_report.md").read_text(encoding="utf-8")

    assert len(lower_signals) == len(lower_entries) + len(lower_cancellations)
    assert set(lens_a["Entry_ID"]) == set(practical["Entry_ID"])
    assert len(lower_cancellations) >= 2
    assert "SAME_SYMBOL_LOCKOUT" in set(lower_cancellations["Cancellation_Reason"])
    assert "INSUFFICIENT_REWARD_RISK" in set(lower_cancellations["Cancellation_Reason"])
    assert "SAME_SYMBOL_LOCKOUT" in set(upper_cancellations["Cancellation_Reason"])
    incomplete = diagnostics.loc[diagnostics["Primary_Complete"] == False, "Entry_ID"]  # noqa: E712
    assert incomplete.astype(str).str.contains("DDD").any()
    assert audit["Passed"].all()
    checks = set(audit["Check"].astype(str))
    assert "LOWER_LOCKOUT_REPLAY" in checks
    assert "UPPER_LOCKOUT_REPLAY" in checks
    assert "LENS_A_GROSS_RETURN" in checks
    assert "PRACTICAL_EXIT_REASON" in checks
    assert "PRACTICAL_BENCHMARK_RETURN" in checks
    assert "UPPER_ENTRY_OPEN_RECOMPUTE" in checks
    assert "UPPER_OUTCOME_GROSS_RETURN" in checks
    candidate_count = int(
        validation_summary.loc[
            validation_summary["Metric"] == "Range_Qualified_Sessions", "Value"
        ].iloc[0]
    )
    expected_candidate_count = int(
        candidates["Range_Eligibility_Reason"].eq("QUALIFIED_RANGE").sum()
    )
    assert candidate_count == expected_candidate_count
    assert f"Range-qualified sessions: {expected_candidate_count};" in report
    assert final_status == "INSUFFICIENT_EVIDENCE"


def test_atomic_writer_replaces_existing_output_set(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "stale.csv").write_text("stale", encoding="utf-8")

    import run_rr1_validation

    original_rename = run_rr1_validation.os.rename

    def deny_directory_rename(source, target):
        if str(source).startswith(str(tmp_path)):
            raise PermissionError("directory promotion denied")
        return original_rename(source, target)

    monkeypatch.setattr(run_rr1_validation.os, "rename", deny_directory_rename)
    _write_atomic(output_dir, {"fresh.csv": pd.DataFrame({"Value": [1]})})

    assert (output_dir / "fresh.csv").exists()
    assert not (output_dir / "stale.csv").exists()


def test_atomic_writer_copies_when_file_promotion_is_locked(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    import run_rr1_validation

    original_replace = run_rr1_validation.os.replace

    def deny_file_replace(source, target):
        if str(source).startswith(str(tmp_path)):
            raise PermissionError("file promotion denied")
        return original_replace(source, target)

    def deny_directory_rename(source, target):
        raise PermissionError("directory promotion denied")

    monkeypatch.setattr(run_rr1_validation.os, "replace", deny_file_replace)
    monkeypatch.setattr(run_rr1_validation.os, "rename", deny_directory_rename)
    _write_atomic(output_dir, {"fresh.csv": pd.DataFrame({"Value": [1]})})

    assert (output_dir / "fresh.csv").read_text(encoding="utf-8").splitlines() == [
        "Value",
        "1",
    ]


def test_range_qualified_count_uses_only_qualified_rows():
    candidates = pd.DataFrame(
        {
            "Range_Eligibility_Reason": [
                "QUALIFIED_RANGE",
                "ER60_ABOVE_MAX",
                "LOW_LIQUIDITY",
                "QUALIFIED_RANGE",
            ]
        }
    )

    assert _range_qualified_count(candidates) == 2


def test_bootstrap_summary_keeps_full_unequal_lower_and_upper_samples():
    lens_a = pd.DataFrame({"Gross_Return": [0.1, 0.2, 0.3]})
    practical = pd.DataFrame(
        {"Base_Net_R": [0.1], "Base_Practical_Excess_Return": [0.01]}
    )
    upper = pd.DataFrame({"Mirror_Gross_Return_15": [-0.1, -0.2]})

    summary = _bootstrap_summary(lens_a, practical, upper)
    row = summary.loc[
        summary["Metric"].eq("LOWER_MINUS_UPPER_GROSS_15_RETURN")
    ].iloc[0]

    assert row["Mean"] == pytest.approx(0.2 - (-0.15))
