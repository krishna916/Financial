from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from build_e1_events import (  # noqa: E402
    build_event_master,
    is_timely_result,
    select_first_public_filings,
)


def test_revision_never_replaces_original_event():
    rows = pd.DataFrame(
        [
            {
                "Symbol": "AAA",
                "Fiscal_Period_End": "2024-06-30",
                "Reporting_Basis": "CONSOLIDATED",
                "Original_or_Revised": "ORIGINAL",
                "Public_Timestamp": "2024-08-10 10:00:00+05:30",
                "EPS": 10.0,
                "Exchange": "NSE",
            },
            {
                "Symbol": "AAA",
                "Fiscal_Period_End": "2024-06-30",
                "Reporting_Basis": "CONSOLIDATED",
                "Original_or_Revised": "REVISED",
                "Public_Timestamp": "2024-08-12 10:00:00+05:30",
                "EPS": 11.0,
                "Exchange": "BSE",
            },
        ]
    )
    selected, ignored = select_first_public_filings(rows)
    assert len(selected) == 1
    assert selected.iloc[0]["Original_or_Revised"] == "ORIGINAL"
    assert selected.iloc[0]["EPS"] == 10.0
    assert len(ignored) == 1


def test_timeliness_boundaries_are_inclusive_for_quarterly_and_final_quarter():
    assert is_timely_result(pd.Timestamp("2024-06-30"), pd.Timestamp("2024-08-14"), "Q1")
    assert not is_timely_result(pd.Timestamp("2024-06-30"), pd.Timestamp("2024-08-15"), "Q1")
    assert is_timely_result(pd.Timestamp("2024-03-31"), pd.Timestamp("2024-05-30"), "Q4")
    assert not is_timely_result(pd.Timestamp("2024-03-31"), pd.Timestamp("2024-05-31"), "Q4")


def test_event_public_date_uses_pit_membership_not_entry_date():
    filings = pd.DataFrame(
        [
            {
                "Symbol": "AAA",
                "Exchange": "NSE",
                "Feed": "legacy",
                "Fiscal_Period_End": "2024-06-30",
                "Fiscal_Quarter": "Q1",
                "Reporting_Basis": "CONSOLIDATED",
                "Quarterly_or_Annual": "QUARTERLY",
                "Original_or_Revised": "ORIGINAL",
                "Public_Timestamp": "2024-08-10 10:00:00+05:30",
                "Source_URL": "https://example.test/a",
                "Source_Record_ID": "a",
                "Machine_Readable_URL": "https://example.test/a.xml",
            }
        ]
    )
    eps = filings.assign(EPS=10.0, EPS_Source_Resolved=True)
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Member_From": [pd.Timestamp("2024-08-11")],
            "Member_To": [pd.Timestamp("2024-12-31")],
            "Yahoo_Ticker": ["AAA.NS"],
            "Downloadable": [True],
        }
    )
    master, exclusions, coverage, _ = build_event_master(filings, eps, membership)
    assert len(master) == 1
    assert not bool(master.iloc[0]["PIT_Membership_OK"])
    assert not bool(master.iloc[0]["Primary_Event"])
    assert exclusions.iloc[0]["Reason"] == "PIT_MEMBERSHIP_NOT_ACTIVE"
    assert int(coverage.iloc[0]["Technical_EPS_Candidates"]) == 0


def test_consolidated_basis_is_preferred_when_current_eps_is_available():
    filing = {
        "Symbol": "AAA",
        "Exchange": "NSE",
        "Feed": "legacy",
        "Fiscal_Period_End": "2024-06-30",
        "Fiscal_Quarter": "Q1",
        "Reporting_Basis": "CONSOLIDATED",
        "Quarterly_or_Annual": "QUARTERLY",
        "Original_or_Revised": "ORIGINAL",
        "Public_Timestamp": "2024-08-10 10:00:00+05:30",
        "Source_URL": "https://example.test/a",
        "Source_Record_ID": "a",
        "Machine_Readable_URL": "https://example.test/a.xml",
    }
    standalone = {**filing, "Reporting_Basis": "STANDALONE", "Source_Record_ID": "s"}
    filings = pd.DataFrame([filing, standalone])
    eps = pd.DataFrame(
        [
            {**filing, "EPS": 10.0, "EPS_Source_Resolved": True},
            {**standalone, "EPS": 9.0, "EPS_Source_Resolved": True},
        ]
    )
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Member_From": [pd.Timestamp("2020-01-01")],
            "Member_To": [pd.Timestamp("2026-12-31")],
        }
    )
    master, _, _, _ = build_event_master(filings, eps, membership)
    assert master.iloc[0]["Selected_Basis"] == "CONSOLIDATED"
