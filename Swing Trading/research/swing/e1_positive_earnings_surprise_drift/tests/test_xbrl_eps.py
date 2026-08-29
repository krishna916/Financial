from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from xbrl_eps import extract_basic_eps_continuing  # noqa: E402


FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_basic_eps_uses_current_quarter_context_not_ytd():
    value = extract_basic_eps_continuing(
        (FIXTURES / "nse_xbrl_basic_eps.xml").read_bytes(),
        pd.Timestamp("2024-06-30"),
        "CONSOLIDATED",
    )
    assert value == pytest.approx(12.34)


def test_extract_basic_eps_rejects_context_for_wrong_reporting_basis():
    xml = (FIXTURES / "nse_xbrl_basic_eps.xml").read_bytes().replace(
        b"StandaloneMember", b"ConsolidatedMember"
    )
    value = extract_basic_eps_continuing(
        xml,
        pd.Timestamp("2024-06-30"),
        "STANDALONE",
    )
    assert value is None


def test_extract_basic_eps_returns_none_when_basic_eps_fact_is_missing():
    xml = b"<xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance' />"
    assert extract_basic_eps_continuing(xml, pd.Timestamp("2024-06-30"), "CONSOLIDATED") is None
