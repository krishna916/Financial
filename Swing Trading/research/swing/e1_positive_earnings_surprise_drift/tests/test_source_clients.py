from __future__ import annotations

import sys
import json
from pathlib import Path

import pandas as pd
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from source_clients import (  # noqa: E402
    BSE_CORPORATE_ACTIONS_URL,
    BSE_SECURITY_MASTER_URL,
    BSE_RESULTS_URL,
    BseResultsClient,
    BseIdentifierError,
    NseResultsClient,
    normalize_bse_record,
    normalize_nse_record,
    resolve_bse_identifier,
)


class _Response:
    def __init__(self, status_code: int, content: bytes, content_type: str):
        self.status_code = status_code
        self.content = content
        self.headers = {"Content-Type": content_type}
        self.url = "https://api.bseindia.com/test"

    def raise_for_status(self):
        if self.status_code != 200:
            raise RuntimeError(f"HTTP {self.status_code}")


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return self.responses[min(self.calls - 1, len(self.responses) - 1)]


def test_resolve_bse_identifier_uses_official_security_master_fixture():
    records = json.loads((Path(__file__).parent / "fixtures/bse_security_master_sample.json").read_text())

    identity = resolve_bse_identifier("RELIANCE", records, source_url="official-fixture")

    assert identity["BSE_Scrip_Code"].isdigit()
    assert identity["BSE_Scrip_ID"] == "RELIANCE"


def test_bse_client_rejects_http_200_html_as_non_json():
    session = _Session([_Response(200, b"<html>challenge</html>", "text/html")])
    client = BseResultsClient(session=session, max_retries=1)

    with pytest.raises(BseIdentifierError, match="BSE_SOURCE_NON_JSON"):
        client.resolve_identifier("RELIANCE")


def test_bse_client_retries_http_429_and_fails_visibly():
    response = _Response(429, b"rate limited", "text/plain")
    session = _Session([response, response, response])
    client = BseResultsClient(session=session, max_retries=3)

    with pytest.raises(BseIdentifierError, match="BSE_SOURCE_ERROR"):
        client.resolve_identifier("RELIANCE")

    assert session.calls == 3


def test_normalize_nse_record_preserves_original_and_broadcast_timestamp():
    record = {
        "symbol": "AAA",
        "toDate": "30-Jun-2024",
        "broadCastDate": "12-Aug-2024 17:31:22",
        "consolidated": "Consolidated",
        "xbrl": "https://nsearchives.nseindia.com/example.xml",
        "revised": "No",
    }
    row = normalize_nse_record(record, "legacy")
    assert row["Symbol"] == "AAA"
    assert row["Fiscal_Period_End"] == pd.Timestamp("2024-06-30")
    assert row["Reporting_Basis"] == "CONSOLIDATED"
    assert row["Original_or_Revised"] == "ORIGINAL"
    assert row["Public_Timestamp"].tz.zone == "Asia/Kolkata"
    assert row["Machine_Readable_URL"].endswith("example.xml")


def test_normalize_integrated_filing_uses_original_submission_type():
    row = normalize_nse_record(
        {
            "symbol": "AAA",
            "periodEndDate": "30-Sep-2024",
            "broadcastDate": "14-Nov-2024 18:00:00",
            "consolidated": "Standalone",
            "Type of Submission": "Original",
            "xbrlFile": "https://nsearchives.nseindia.com/example-integrated.xml",
        },
        "integrated",
    )
    assert row["Fiscal_Quarter"] == "Q2"
    assert row["Reporting_Basis"] == "STANDALONE"
    assert row["Original_or_Revised"] == "ORIGINAL"
    assert row["Feed"] == "integrated"


def test_normalize_actual_nse_integrated_fields_preserves_period_and_machine_url():
    row = normalize_nse_record(
        {
            "symbol": "RELIANCE",
            "qe_Date": "30-JUN-2026",
            "broadcast_Date": "17-Jul-2026 19:50:03",
            "consolidated": "Consolidated",
            "type_Sub": "Original",
            "seq_Id": "175608",
            "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/actual.xml",
            "ixbrl": "https://nsearchives.nseindia.com/corporate/ixbrl/actual.html",
        },
        "integrated",
    )

    assert row["Fiscal_Period_End"] == pd.Timestamp("2026-06-30")
    assert row["Public_Timestamp"].tz.zone == "Asia/Kolkata"
    assert row["Original_or_Revised"] == "ORIGINAL"
    assert row["Source_Record_ID"] == "175608"
    assert row["Machine_Readable_URL"].endswith("actual.xml")


def test_normalize_nse_rejects_placeholder_machine_url_without_fabricating_source():
    row = normalize_nse_record(
        {
            "symbol": "AAA",
            "toDate": "30-Jun-2018",
            "broadCastDate": "03-Aug-2018 17:56:53",
            "consolidated": "Consolidated",
            "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/-",
            "seqNumber": "1046793",
        },
        "legacy",
    )

    assert row["Machine_Readable_URL"] == ""
    assert row["Source_URL"] == ""
    assert row["Source_Record_ID"] == "1046793"


def test_normalize_bse_fixture_retains_revision_and_record_identity():
    row = normalize_bse_record(
        {
            "scripCode": "500001",
            "scripName": "AAA",
            "period_end": "31-Mar-2024",
            "announcement_datetime": "30-May-2024 16:10:00",
            "result_type": "Consolidated",
            "revision": "Revised",
            "id": "bse-500001-20240530",
            "url": "https://www.bseindia.com/corporates/Results.aspx?id=1",
        }
    )
    assert row["Exchange"] == "BSE"
    assert row["Source_Record_ID"] == "bse-500001-20240530"
    assert row["Original_or_Revised"] == "REVISED"
    assert row["Reporting_Basis"] == "CONSOLIDATED"
    assert row["Public_Timestamp"].tz.zone == "Asia/Kolkata"


def test_normalize_bse_company_result_retains_resolved_identity_as_record_id():
    row = normalize_bse_record(
        {
            "symbol": "RELIANCE",
            "BSE_Scrip_Code": "500325",
            "BSE_Scrip_ID": "RELIANCE",
            "BSE_Mapping_Source_URL": BSE_SECURITY_MASTER_URL,
            "LQ": "Jun-26",
        }
    )

    assert row["Source_Record_ID"] == "500325"
    assert row["BSE_Scrip_ID"] == "RELIANCE"


def test_source_clients_return_catalog_records_without_strategy_fields(monkeypatch):
    nse = NseResultsClient()
    monkeypatch.setattr(
        nse,
        "_get_json",
        lambda *args, **kwargs: {
            "data": [{"symbol": "AAA", "toDate": "30-Jun-2024"}],
            "totalPages": 1,
        },
    )
    bse = BseResultsClient()

    def bse_payload(url, params=None):
        if url == BSE_SECURITY_MASTER_URL:
            return {"data": [{"Scrip ID": "AAA", "Scrip Code": "1"}]}
        return {"data": [{"scripCode": "1"}]}

    monkeypatch.setattr(bse, "_get_json_checked", bse_payload)

    nse_rows = nse.list_legacy("AAA")
    bse_rows = bse.list_results("AAA")
    forbidden = {"Gross_Return", "Net_Return", "SUE", "Cohort"}
    assert forbidden.isdisjoint(nse_rows[0])
    assert forbidden.isdisjoint(bse_rows[0])


def test_bse_result_requests_use_resolved_numeric_scrip_code(monkeypatch):
    client = BseResultsClient()
    calls = []

    def fake_get_json(url, params=None):
        calls.append((url, params))
        if url == BSE_SECURITY_MASTER_URL:
            return {"data": [{"Scrip ID": "AAA", "Scrip Code": "500001"}]}
        return {"data": [{"scripCode": "500001", "scripName": "AAA"}]}

    monkeypatch.setattr(client, "_get_json_checked", fake_get_json)

    rows = client.list_results("AAA")

    assert calls[0][0] == BSE_SECURITY_MASTER_URL
    assert calls[1][1]["scripcode"] == "500001"
    assert calls[1][1]["scripcode"] != "AAA"
    assert rows[0]["BSE_Scrip_Code"] == "500001"
    assert rows[0]["BSE_Scrip_ID"] == "AAA"


def test_bse_company_results_use_official_tab_results_payload(monkeypatch):
    client = BseResultsClient()
    calls = []
    company_results = {
        "resultinS": [
            {
                "LQ": "Jun-26",
                "LLQ": "Jun-25",
                "LSQ": "Mar-26",
            }
        ],
        "resultinCr": [{"title": "EPS", "v1": "9.81"}],
    }

    def fake_get_json(url, params=None):
        calls.append((url, params))
        if url == BSE_SECURITY_MASTER_URL:
            return {"data": [{"Scrip ID": "AAA", "Scrip Code": "500001"}]}
        return company_results

    monkeypatch.setattr(client, "_get_json_checked", fake_get_json)

    rows = client.list_results("AAA")

    assert calls[1][0] == BSE_RESULTS_URL
    assert calls[1][1] == {"scripcode": "500001", "tabtype": "RESULTS"}
    assert rows[0]["LQ"] == "Jun-26"
    assert rows[0]["symbol"] == "AAA"
    assert rows[0]["BSE_Scrip_Code"] == "500001"


def test_bse_company_results_decodes_official_json_string_envelope():
    security_payload = b'[{"Scrip ID":"AAA","Scrip Code":"500001"}]'
    results_payload = json.dumps(
        json.dumps(
            {
                "resultinS": [
                    {"LQ": "Jun-26", "LLQ": "Jun-25", "LSQ": "Mar-26"}
                ]
            }
        )
    ).encode()
    client = BseResultsClient(
        session=_Session(
            [
                _Response(200, security_payload, "application/json"),
                _Response(200, results_payload, "application/json"),
            ]
        ),
        max_retries=1,
    )

    rows = client.list_results("AAA")

    assert rows[0]["LQ"] == "Jun-26"


def test_bse_corporate_actions_use_resolved_numeric_scrip_code(monkeypatch):
    client = BseResultsClient()
    calls = []

    def fake_get_json(url, params=None):
        calls.append((url, params))
        if url == BSE_SECURITY_MASTER_URL:
            return {"data": [{"Scrip ID": "AAA", "Scrip Code": "500001"}]}
        return {"Table1": [{"XTYPE": "Bonus", "VALUE": "issue 1:1"}]}

    monkeypatch.setattr(client, "_get_json_checked", fake_get_json)

    payload = client.corporate_actions("AAA")

    assert calls[1] == (BSE_CORPORATE_ACTIONS_URL, {"scripcode": "500001"})
    assert payload["Table1"][0]["VALUE"] == "issue 1:1"


def test_bse_company_results_fail_closed_when_payload_identity_disagrees(monkeypatch):
    client = BseResultsClient()

    def fake_get_json(url, params=None):
        if url == BSE_SECURITY_MASTER_URL:
            return {"data": [{"Scrip ID": "AAA", "Scrip Code": "500001"}]}
        return {"data": [{"scripCode": "999999", "scripName": "OTHER"}]}

    monkeypatch.setattr(client, "_get_json_checked", fake_get_json)

    with pytest.raises(BseIdentifierError, match="BSE_SOURCE_ERROR"):
        client.list_results("AAA")


def test_bse_identifier_resolution_fails_closed_for_unresolved_and_ambiguous_symbols():
    with pytest.raises(BseIdentifierError, match="BSE_IDENTIFIER_UNRESOLVED"):
        resolve_bse_identifier("AAA", [])

    with pytest.raises(BseIdentifierError, match="BSE_IDENTIFIER_AMBIGUOUS"):
        resolve_bse_identifier(
            "AAA",
            [
                {"Scrip ID": "AAA", "Scrip Code": "500001"},
                {"Scrip ID": "AAA", "Scrip Code": "500002"},
            ],
        )
