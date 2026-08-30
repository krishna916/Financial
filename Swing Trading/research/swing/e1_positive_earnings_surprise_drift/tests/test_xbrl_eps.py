from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from xbrl_eps import extract_basic_eps_continuing  # noqa: E402


FIXTURES = Path(__file__).parent / "fixtures"
REAL_FIXTURE_SOURCE_URL = (
    "https://nsearchives.nseindia.com/corporate/xbrl/"
    "INTEGRATED_FILING_INDAS_1695741_17072026075004_WEB.xml"
)
REAL_PERIOD_END = pd.Timestamp("2026-06-30")
REAL_BASIS = "CONSOLIDATED"
REAL_BASIC_CONTINUING_EPS = 15.48


def test_extract_basic_eps_from_real_nse_integrated_ixbrl():
    value = extract_basic_eps_continuing(
        (FIXTURES / "nse_integrated_real_ixbrl.html").read_bytes(),
        REAL_PERIOD_END,
        REAL_BASIS,
    )

    assert value == pytest.approx(REAL_BASIC_CONTINUING_EPS)


def test_real_nse_integrated_eps_rejects_wrong_basis():
    value = extract_basic_eps_continuing(
        (FIXTURES / "nse_integrated_real_ixbrl.html").read_bytes(),
        REAL_PERIOD_END,
        "STANDALONE",
    )

    assert value is None


def test_real_nse_integrated_eps_rejects_ytd_context_for_same_end_date():
    value = extract_basic_eps_continuing(
        (FIXTURES / "nse_integrated_real_ixbrl.html").read_bytes(),
        REAL_PERIOD_END,
        REAL_BASIS,
    )

    assert value != pytest.approx(47.52)


def test_extract_basic_eps_supports_malformed_inline_xbrl_html():
    payload = b"""
    <html xmlns:ix='http://www.xbrl.org/2013/inlineXBRL'
          xmlns:xbrli='http://www.xbrl.org/2003/instance'>
      <ix:header>
        <xbrli:context id='c'>
          <xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate>
          <xbrli:endDate>2024-06-30</xbrli:endDate></xbrli:period>
        </xbrli:context>
      </ix:header>
      <ix:nonNumeric name='in-capmkt:NatureOfReportStandaloneConsolidated'
                     contextRef='c'>Consolidated</ix:nonNumeric>
      <ix:nonFraction name='in-capmkt:BasicEarningsLossPerShareFromContinuingOperations'
                      contextRef='c'>7.25</ix:nonFraction>
      <br>
    """

    assert extract_basic_eps_continuing(
        payload,
        pd.Timestamp("2024-06-30"),
        "CONSOLIDATED",
    ) == pytest.approx(7.25)


def test_extract_basic_eps_rejects_disagreeing_remaining_facts():
    payload = b"""
    <xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance'
                xmlns:in-capmkt='http://www.icai.org/in-capmkt'>
      <xbrli:context id='c'>
        <xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate>
        <xbrli:endDate>2024-06-30</xbrli:endDate></xbrli:period>
      </xbrli:context>
      <in-capmkt:NatureOfReportStandaloneConsolidated contextRef='c'>Consolidated</in-capmkt:NatureOfReportStandaloneConsolidated>
      <in-capmkt:BasicEarningsLossPerShareFromContinuingOperations contextRef='c'>7.25</in-capmkt:BasicEarningsLossPerShareFromContinuingOperations>
      <in-capmkt:BasicEarningsLossPerShareFromContinuingOperations contextRef='c'>8.25</in-capmkt:BasicEarningsLossPerShareFromContinuingOperations>
    </xbrli:xbrl>
    """

    with pytest.raises(ValueError, match="EPS_FACT_AMBIGUOUS"):
        extract_basic_eps_continuing(
            payload,
            pd.Timestamp("2024-06-30"),
            "CONSOLIDATED",
        )


def test_extract_basic_eps_prefers_nse_one_day_context_when_cumulative_context_reuses_dates():
    payload = b"""
    <xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance'
                xmlns:in-capmkt='http://www.icai.org/in-capmkt'>
      <xbrli:context id='OneD'>
        <xbrli:period><xbrli:startDate>2024-10-01</xbrli:startDate>
        <xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period>
      </xbrli:context>
      <xbrli:context id='FourD'>
        <xbrli:period><xbrli:startDate>2024-10-01</xbrli:startDate>
        <xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period>
      </xbrli:context>
      <in-capmkt:NatureOfReportStandaloneConsolidated contextRef='OneD'>Consolidated</in-capmkt:NatureOfReportStandaloneConsolidated>
      <in-capmkt:NatureOfReportStandaloneConsolidated contextRef='FourD'>Consolidated</in-capmkt:NatureOfReportStandaloneConsolidated>
      <in-capmkt:BasicEarningsLossPerShareFromContinuingOperations contextRef='OneD'>16.43</in-capmkt:BasicEarningsLossPerShareFromContinuingOperations>
      <in-capmkt:BasicEarningsLossPerShareFromContinuingOperations contextRef='FourD'>47.52</in-capmkt:BasicEarningsLossPerShareFromContinuingOperations>
    </xbrli:xbrl>
    """

    assert extract_basic_eps_continuing(
        payload,
        pd.Timestamp("2024-12-31"),
        "CONSOLIDATED",
    ) == pytest.approx(16.43)


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
