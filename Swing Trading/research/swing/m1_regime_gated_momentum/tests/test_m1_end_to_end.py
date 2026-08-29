import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fixtures import write_minimal_v3_package
from run_m1_validation import (
    OUTPUT_FILES,
    _final_package_issues,
    _signal_window_audit,
    run_validation,
)


def write_market_package(
    root: Path,
    dates: list[str] | None = None,
) -> tuple[Path, Path, Path, Path]:
    breadth_path = root / "breadth.csv"
    index_path = root / "index.csv"
    membership_path = root / "membership.csv"
    sector_path = root / "sector.csv"
    dates = dates or ["2024-01-02", "2024-01-03", "2024-01-04"]
    pd.DataFrame(
        {
            "Date": dates,
            "SMA50_Denominator": [3] * len(dates),
            "Pct_Above_SMA50": [100.0] * len(dates),
            "Universe_Member_Count": [3] * len(dates),
            "Regime": ["HOSTILE"] * len(dates),
        }
    ).to_csv(breadth_path, index=False)
    pd.DataFrame(
        {
            "Date": dates,
            "Close": [120.0] * len(dates),
            "SMA50": [110.0] * len(dates),
            "SMA200": [100.0] * len(dates),
            "Regime": ["RISK_OFF"] * len(dates),
        }
    ).to_csv(index_path, index=False)
    pd.DataFrame(
        {
            "Symbol": ["AAA", "BBB", "CCC"],
            "Member_From": ["2023-01-01"] * 3,
            "Member_To": ["2024-12-31"] * 3,
            "Method": ["POINT_IN_TIME"] * 3,
        }
    ).to_csv(membership_path, index=False)
    pd.DataFrame({"Stock": ["AAA"], "Sector_Key": ["IT"]}).to_csv(sector_path, index=False)
    return breadth_path, index_path, membership_path, sector_path


def test_end_to_end_missing_source_is_invalid(tmp_path):
    v3_root = tmp_path / "v3"
    write_minimal_v3_package(v3_root)
    (v3_root / "v3_entries.csv").unlink()
    breadth, index_daily, membership, sector = write_market_package(tmp_path)
    status, _ = run_validation(v3_root, breadth, index_daily, membership, sector, tmp_path / "out")
    assert status == "INVALID_RESEARCH_RUN"


def test_end_to_end_fixture_with_fewer_than_300_enabled_trades_is_insufficient(tmp_path):
    v3_root = tmp_path / "v3"
    write_minimal_v3_package(v3_root)
    breadth, index_daily, membership, sector = write_market_package(tmp_path)
    status, _ = run_validation(v3_root, breadth, index_daily, membership, sector, tmp_path / "out")
    assert status == "INSUFFICIENT_EVIDENCE"


def test_signal_window_audit_rejects_dates_outside_frozen_primary_window():
    qualified = pd.DataFrame(
        [
            {
                "Entry_ID": "BEFORE-2023-07-31",
                "Symbol": "BEFORE",
                "Signal_Date": pd.Timestamp("2023-07-31"),
            },
            {
                "Entry_ID": "START-2023-08-01",
                "Symbol": "START",
                "Signal_Date": pd.Timestamp("2023-08-01"),
            },
            {
                "Entry_ID": "END-2026-08-25",
                "Symbol": "END",
                "Signal_Date": pd.Timestamp("2026-08-25"),
            },
            {
                "Entry_ID": "AFTER-2026-08-26",
                "Symbol": "AFTER",
                "Signal_Date": pd.Timestamp("2026-08-26"),
            },
        ]
    )

    audit = _signal_window_audit(qualified)

    assert set(audit["Entry_ID"]) == {
        "BEFORE-2023-07-31",
        "AFTER-2026-08-26",
    }
    assert set(audit["Violation"]) == {"SIGNAL_DATE_OUTSIDE_PRIMARY_WINDOW"}
    assert set(audit["Source"]) == {"signal_window"}
    assert set(audit["Expected"]) == {"2023-08-01 <= Signal_Date <= 2026-08-25"}


def test_end_to_end_out_of_window_qualified_signal_forces_invalid(tmp_path):
    v3_root = tmp_path / "v3"
    write_minimal_v3_package(v3_root)

    replacements = {
        "v3_signal_candidates.csv": ["Signal_Date"],
        "v3_entries.csv": ["Signal_Date"],
        "v3_setup_quality_trades.csv": ["Signal_Date"],
        "v3_practical_trades.csv": ["Signal_Date"],
    }
    for filename, columns in replacements.items():
        path = v3_root / filename
        frame = pd.read_csv(path)
        mask = frame["Entry_ID"].eq("AAA-2024-01-02")
        for column in columns:
            frame.loc[mask, column] = "2023-07-31"
        frame.to_csv(path, index=False)

    breadth, index_daily, membership, sector = write_market_package(
        tmp_path,
        dates=["2023-07-31", "2024-01-03", "2024-01-04"],
    )

    status, _ = run_validation(
        v3_root,
        breadth,
        index_daily,
        membership,
        sector,
        tmp_path / "out",
    )

    audit = pd.read_csv(tmp_path / "out" / "m1_integrity_audit.csv")
    assert status == "INVALID_RESEARCH_RUN"
    assert "SIGNAL_DATE_OUTSIDE_PRIMARY_WINDOW" in audit["Violation"].tolist()


def write_minimal_final_package(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    from run_m1_validation import FINAL_REQUIRED_COLUMNS

    for filename, columns in FINAL_REQUIRED_COLUMNS.items():
        pd.DataFrame([{column: "x" for column in columns}]).to_csv(
            output_dir / filename,
            index=False,
        )


def test_final_package_verifier_rejects_missing_research_report(tmp_path):
    out = tmp_path / "out"
    write_minimal_final_package(out)

    issues = _final_package_issues(out)

    assert any(
        row["Violation"] == "MISSING_FINAL_EVIDENCE"
        and row["Observed"] == "research_report.md"
        for row in issues
    )


def test_final_package_verifier_rejects_blank_research_report(tmp_path):
    out = tmp_path / "out"
    write_minimal_final_package(out)
    (out / "research_report.md").write_text("   \n", encoding="utf-8")

    issues = _final_package_issues(out)

    assert any(
        row["Violation"] == "INVALID_FINAL_EVIDENCE"
        and "research_report.md" in str(row["Observed"])
        for row in issues
    )


def test_end_to_end_blank_required_report_forces_invalid(tmp_path, monkeypatch):
    import run_m1_validation as runner

    assert "research_report.md" in OUTPUT_FILES
    v3_root = tmp_path / "v3"
    write_minimal_v3_package(v3_root)
    breadth, index_daily, membership, sector = write_market_package(tmp_path)

    def write_blank_report(path, status, evidence):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n", encoding="utf-8")

    monkeypatch.setattr(runner, "write_research_report", write_blank_report)

    status, _ = runner.run_validation(
        v3_root,
        breadth,
        index_daily,
        membership,
        sector,
        tmp_path / "out",
    )

    audit = pd.read_csv(tmp_path / "out" / "m1_integrity_audit.csv")
    assert status == "INVALID_RESEARCH_RUN"
    assert "INVALID_FINAL_EVIDENCE" in audit["Violation"].tolist()
