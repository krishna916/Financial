from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

import compute_e1_sue as sue  # noqa: E402
from compute_e1_sue import (  # noqa: E402
    _sue_from_changes,
    adjust_historical_eps_for_actions,
    build_sue_events,
    classify_sue,
    compute_sue_for_event,
)


def test_sue_uses_exactly_eight_prior_seasonal_changes_and_ddof_one():
    seasonal = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    current = 10.0
    expected = (current - seasonal.mean()) / seasonal.std(ddof=1)
    row = _sue_from_changes(current, seasonal)
    assert row["Historical_Mean"] == pytest.approx(seasonal.mean())
    assert row["Historical_SD"] == pytest.approx(seasonal.std(ddof=1))
    assert row["SUE"] == pytest.approx(expected)


def test_build_sue_events_uses_only_matching_symbol_basis_history(monkeypatch):
    event_master = pd.DataFrame(
        [
            {
                "Event_ID": "AAA-1",
                "Symbol": "AAA",
                "Fiscal_Period_End": "2024-06-30",
                "Event_Public_Date": "2024-08-10",
                "Event_Public_Timestamp": "2024-08-10T10:00:00+05:30",
                "Reporting_Basis": "CONSOLIDATED",
                "Selected_Basis": "CONSOLIDATED",
                "PIT_Membership_OK": True,
                "Timely_Result": True,
                "EPS_Source_Resolved": True,
                "EPS_Source_Status": "RESOLVED",
            }
        ]
    )
    eps_snapshot = pd.DataFrame(
        [
            {"Symbol": "AAA", "Reporting_Basis": "CONSOLIDATED", "Fiscal_Period_End": "2024-06-30", "EPS": 1.0},
            {"Symbol": "AAA", "Reporting_Basis": "CONSOLIDATED", "Fiscal_Period_End": "2024-03-31", "EPS": 0.9},
            {"Symbol": "BBB", "Reporting_Basis": "CONSOLIDATED", "Fiscal_Period_End": "2024-06-30", "EPS": 0.8},
        ]
    )
    seen_sizes: list[int] = []

    def fake_compute_sue_for_event(event, history, actions):
        seen_sizes.append(len(history))
        assert history.attrs.get("_e1_prepared_history") is True
        return {"Event_ID": event["Event_ID"], "Symbol": "AAA", "SUE": 1.0, "Cohort": "POSITIVE_SURPRISE"}, ""

    monkeypatch.setattr(sue, "compute_sue_for_event", fake_compute_sue_for_event)

    build_sue_events(event_master, eps_snapshot, pd.DataFrame())

    assert seen_sizes == [2]


def _eps_history(public_dates: list[str]) -> pd.DataFrame:
    periods = pd.date_range("2020-03-31", periods=len(public_dates), freq="QE-MAR")
    quarter_labels = (["Q4", "Q1", "Q2", "Q3"] * ((len(periods) + 3) // 4))[: len(periods)]
    return pd.DataFrame(
        {
            "Symbol": ["AAA"] * len(periods),
            "Fiscal_Period_End": periods,
            "Fiscal_Quarter": quarter_labels,
            "Reporting_Basis": ["CONSOLIDATED"] * len(periods),
            "Original_or_Revised": ["ORIGINAL"] * len(periods),
            "Public_Timestamp": public_dates,
            "EPS": np.arange(1.0, len(periods) + 1.0),
        }
    )


def test_future_public_historical_eps_makes_sue_unavailable():
    public_dates = ["2020-05-15 10:00:00+05:30"] * 13
    public_dates[0] = "2023-08-11 10:00:00+05:30"
    public_dates[-1] = "2023-08-10 10:00:00+05:30"
    history = _eps_history(public_dates)
    event = pd.Series(
        {
            "Event_ID": "AAA-20230331-CONSOLIDATED",
            "Symbol": "AAA",
            "Fiscal_Period_End": pd.Timestamp("2023-03-31"),
            "Event_Public_Timestamp": pd.Timestamp("2023-08-10 10:00:00", tz="Asia/Kolkata"),
            "Reporting_Basis": "CONSOLIDATED",
        }
    )
    row, reason = compute_sue_for_event(event, history, pd.DataFrame())
    assert row is None
    assert reason in {"INSUFFICIENT_EPS_HISTORY", "FUTURE_EPS_USED"}


def test_sue_unavailable_reason_is_persisted_as_explicit_exclusion():
    event_master = pd.DataFrame(
        [
            {
                "Event_ID": "AAA-20240630-CONSOLIDATED",
                "Symbol": "AAA",
                "Fiscal_Period_End": pd.Timestamp("2024-06-30"),
                "Event_Public_Date": pd.Timestamp("2024-08-10"),
                "Selected_Basis": "CONSOLIDATED",
                "Reporting_Basis": "CONSOLIDATED",
                "Timely_Result": True,
                "PIT_Membership_OK": True,
                "EPS_Source_Status": "RESOLVED",
                "EPS_Source_Resolved": True,
                "Primary_Event": True,
            }
        ]
    )
    eps = pd.DataFrame(columns=["Symbol", "Fiscal_Period_End", "Reporting_Basis", "EPS"])

    _, _, _, exclusions = build_sue_events(event_master, eps, pd.DataFrame())

    assert exclusions[["Event_ID", "Reason", "Exclusion_Stage"]].to_dict("records") == [
        {
            "Event_ID": "AAA-20240630-CONSOLIDATED",
            "Reason": "MISSING_CURRENT_EPS",
            "Exclusion_Stage": "SUE",
        }
    ]


@pytest.mark.parametrize(
    ("action_type", "old_shares", "new_shares", "bonus_shares", "expected"),
    [
        ("SPLIT", 1.0, 2.0, np.nan, 5.0),
        ("CONSOLIDATION", 2.0, 1.0, np.nan, 20.0),
        ("BONUS", 1.0, 2.0, 1.0, 5.0),
        ("BONUS", 1.0, 3.0, 2.0, 10.0 / 3.0),
    ],
)
def test_corporate_action_share_count_factors_adjust_eps_economically(
    action_type: str,
    old_shares: float,
    new_shares: float,
    bonus_shares: float,
    expected: float,
):
    history = pd.DataFrame(
        {
            "Symbol": ["AAA", "AAA"],
            "Fiscal_Period_End": pd.to_datetime(["2023-03-31", "2024-03-31"]),
            "EPS": [10.0, 5.0],
        }
    )
    actions = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Action_Type": [action_type],
            "Old_Shares": [old_shares],
            "New_Shares": [new_shares],
            "Bonus_Shares": [bonus_shares],
            "Ex_Date": [pd.Timestamp("2023-06-01")],
        }
    )
    adjusted = adjust_historical_eps_for_actions(history, actions, pd.Timestamp("2024-06-30"))
    assert adjusted.loc[0, "EPS"] == pytest.approx(expected)

    after_event = adjust_historical_eps_for_actions(history, actions, pd.Timestamp("2023-05-31"))
    assert after_event.loc[0, "EPS"] == pytest.approx(10.0)


def test_unparseable_relevant_action_is_not_silently_ignored():
    history = pd.DataFrame({"Symbol": ["AAA"], "Fiscal_Period_End": [pd.Timestamp("2023-03-31")], "EPS": [10.0]})
    actions = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Action_Type": ["SPLIT"],
            "Old_Shares": [np.nan],
            "New_Shares": [2.0],
            "Bonus_Shares": [np.nan],
            "Ex_Date": [pd.Timestamp("2023-06-01")],
        }
    )
    with pytest.raises(ValueError, match="EPS_HISTORY_NOT_COMPARABLE"):
        adjust_historical_eps_for_actions(history, actions, pd.Timestamp("2024-06-30"))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1.0, "POSITIVE_SURPRISE"),
        (0.5, "POSITIVE_BUFFER"),
        (-0.5, "NEGATIVE_BUFFER"),
        (-1.0, "NEGATIVE_CONTROL"),
        (1.0 - 1e-9, "POSITIVE_BUFFER"),
        (0.5 - 1e-9, "NEUTRAL_CONTROL"),
        (-0.5 + 1e-9, "NEUTRAL_CONTROL"),
        (-1.0 + 1e-9, "NEGATIVE_BUFFER"),
    ],
)
def test_sue_cohort_boundaries_are_exact(value: float, expected: str):
    assert classify_sue(value) == expected
