from pathlib import Path
import sys

import pandas as pd

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from constants import (
    FIRST_HALF_END,
    PRIMARY_END,
    PRIMARY_START,
    SECOND_HALF_START,
    SOURCE_CUTOFF,
)
from load_e1_inputs import active_members_on, verify_manifest


def test_frozen_windows_are_exact():
    assert PRIMARY_START == pd.Timestamp("2023-08-01")
    assert PRIMARY_END == pd.Timestamp("2026-06-30")
    assert SOURCE_CUTOFF == pd.Timestamp("2026-08-25")
    assert FIRST_HALF_END == pd.Timestamp("2025-01-14")
    assert SECOND_HALF_START == pd.Timestamp("2025-01-15")


def test_active_members_on_uses_inclusive_membership_boundaries():
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Member_From": [pd.Timestamp("2024-01-02")],
            "Member_To": [pd.Timestamp("2024-01-05")],
        }
    )
    assert active_members_on(membership, pd.Timestamp("2024-01-02"))["Symbol"].tolist() == ["AAA"]
    assert active_members_on(membership, pd.Timestamp("2024-01-05"))["Symbol"].tolist() == ["AAA"]


def test_verify_manifest_rejects_hash_mismatch(tmp_path: Path):
    source = tmp_path / "a.csv"
    source.write_text("x\n1\n", encoding="utf-8")
    manifest = pd.DataFrame(
        [
            {
                "Artifact": "a.csv",
                "SHA256": "0" * 64,
                "Row_Count": 1,
            }
        ]
    )
    audit = verify_manifest(manifest, tmp_path)
    assert "HASH_MISMATCH" in audit["Violation"].tolist()
