from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from source_clients import (  # noqa: E402
    BseResultsClient,
    NseResultsClient,
    normalize_bse_record,
    normalize_nse_record,
)


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
    monkeypatch.setattr(bse, "_get_json", lambda *args, **kwargs: {"data": [{"scripCode": "1"}]})

    nse_rows = nse.list_legacy("AAA")
    bse_rows = bse.list_results("AAA")
    forbidden = {"Gross_Return", "Net_Return", "SUE", "Cohort"}
    assert forbidden.isdisjoint(nse_rows[0])
    assert forbidden.isdisjoint(bse_rows[0])
