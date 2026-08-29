import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fixtures import write_minimal_v3_package
from run_m1_validation import run_validation


def write_market_package(root: Path) -> tuple[Path, Path, Path, Path]:
    breadth_path = root / "breadth.csv"
    index_path = root / "index.csv"
    membership_path = root / "membership.csv"
    sector_path = root / "sector.csv"
    dates = ["2024-01-02", "2024-01-03", "2024-01-04"]
    pd.DataFrame(
        {
            "Date": dates,
            "SMA50_Denominator": [3, 3, 3],
            "Pct_Above_SMA50": [100.0, 100.0, 100.0],
            "Universe_Member_Count": [3, 3, 3],
            "Regime": ["HOSTILE", "HOSTILE", "HOSTILE"],
        }
    ).to_csv(breadth_path, index=False)
    pd.DataFrame(
        {
            "Date": dates,
            "Close": [120.0, 121.0, 122.0],
            "SMA50": [110.0, 110.0, 110.0],
            "SMA200": [100.0, 100.0, 100.0],
            "Regime": ["RISK_OFF", "RISK_OFF", "RISK_OFF"],
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
