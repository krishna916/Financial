from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from build_e1_events import (  # noqa: E402
    _coverage_row,
    build_event_master,
    eps_values_match,
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


def test_first_public_selection_does_not_iterate_rows(monkeypatch):
    rows = pd.DataFrame(
        [
            {
                "Symbol": "AAA",
                "Fiscal_Period_End": "2024-06-30",
                "Reporting_Basis": "CONSOLIDATED",
                "Original_or_Revised": "ORIGINAL",
                "Public_Timestamp": "2024-08-10 10:00:00+05:30",
                "Source_Record_ID": "a",
                "Exchange": "NSE",
            },
            {
                "Symbol": "AAA",
                "Fiscal_Period_End": "2024-06-30",
                "Reporting_Basis": "CONSOLIDATED",
                "Original_or_Revised": "REVISED",
                "Public_Timestamp": "2024-08-12 10:00:00+05:30",
                "Source_Record_ID": "b",
                "Exchange": "BSE",
            },
        ]
    )

    def fail_iterrows(self):
        raise AssertionError("first-public normalization must not iterate rows")

    monkeypatch.setattr(pd.DataFrame, "iterrows", fail_iterrows)

    selected, ignored = select_first_public_filings(rows)

    assert selected["Source_Record_ID"].tolist() == ["a"]
    assert ignored["Reason"].tolist() == ["REVISED_OR_DUPLICATE_IGNORED"]


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
    period_ends = pd.period_range("2021Q2", "2024Q2", freq="Q").to_timestamp(how="end").normalize()
    filing = {
        "Symbol": "AAA",
        "Exchange": "NSE",
        "Feed": "legacy",
        "Fiscal_Period_End": period_ends[-1],
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
            {
                **filing,
                "Fiscal_Period_End": period_end,
                "Source_Record_ID": f"eps-consolidated-{index}",
                "EPS": float(index + 1),
                "EPS_Source_Resolved": True,
            }
            for index, period_end in enumerate(period_ends)
        ]
        + [
            {
                **standalone,
                "Fiscal_Period_End": period_end,
                "Source_Record_ID": f"eps-standalone-{index}",
                "EPS": float(index + 1),
                "EPS_Source_Resolved": True,
            }
            for index, period_end in enumerate(period_ends)
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


def test_standalone_basis_fallback_requires_complete_sue_chain():
    period_ends = pd.period_range("2021Q2", "2024Q2", freq="Q").to_timestamp(how="end").normalize()
    filing = {
        "Symbol": "AAA",
        "Exchange": "NSE",
        "Feed": "legacy",
        "Fiscal_Period_End": period_ends[-1],
        "Fiscal_Quarter": "Q1",
        "Reporting_Basis": "CONSOLIDATED",
        "Quarterly_or_Annual": "QUARTERLY",
        "Original_or_Revised": "ORIGINAL",
        "Public_Timestamp": "2024-08-10 10:00:00+05:30",
        "Source_URL": "https://example.test/a",
        "Source_Record_ID": "filing-consolidated",
        "Machine_Readable_URL": "https://example.test/a.xml",
    }
    standalone_filing = {**filing, "Reporting_Basis": "STANDALONE", "Source_Record_ID": "filing-standalone"}
    filings = pd.DataFrame([filing, standalone_filing])
    eps_rows = []
    for basis in ("CONSOLIDATED", "STANDALONE"):
        basis_periods = period_ends if basis == "STANDALONE" else period_ends[1:]
        for index, period_end in enumerate(basis_periods):
            eps_rows.append(
                {
                    **filing,
                    "Fiscal_Period_End": period_end,
                    "Reporting_Basis": basis,
                    "Public_Timestamp": "2024-08-09 10:00:00+05:30",
                    "Source_Record_ID": f"eps-{basis.lower()}-{index}",
                    "EPS": float(index + 1),
                    "EPS_Source_Resolved": True,
                }
            )
    eps = pd.DataFrame(eps_rows)
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Member_From": [pd.Timestamp("2020-01-01")],
            "Member_To": [pd.Timestamp("2026-12-31")],
        }
    )

    master, _, _, _ = build_event_master(filings, eps, membership)

    assert master.iloc[0]["Selected_Basis"] == "STANDALONE"


def test_cross_exchange_eps_tolerance_matches_frozen_boundaries():
    assert eps_values_match(10.00, 10.01)
    assert eps_values_match(100.0, 100.5)
    assert not eps_values_match(10.00, 10.20)
    assert eps_values_match(0.0, 0.0)


def test_technical_coverage_denominator_contains_only_primary_candidates():
    common = {
        "PIT_Membership_OK": True,
        "Timely_Result": True,
        "Selected_Basis": "CONSOLIDATED",
        "Machine_Readable_URL": "https://example.test/result.xml",
        "Original_or_Revised": "ORIGINAL",
        "EPS_Source_Resolved": True,
        "Source_Exchanges": "NSE",
        "Original_Record_Count": 1,
        "EPS_Source_Status": "RESOLVED",
        "Primary_Event": True,
    }
    events = pd.DataFrame(
        [
            {**common, "Event_ID": "HISTORY", "Event_Public_Date": "2022-07-31"},
            {**common, "Event_ID": "PRIMARY", "Event_Public_Date": "2024-07-31"},
            {**common, "Event_ID": "FORWARD", "Event_Public_Date": "2026-07-01"},
        ]
    )

    coverage = _coverage_row(events)

    assert int(coverage.iloc[0]["Technical_EPS_Candidates"]) == 1
    assert int(coverage.iloc[0]["Resolved_EPS_Candidates"]) == 1
