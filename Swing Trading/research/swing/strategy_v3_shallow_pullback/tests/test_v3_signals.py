import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[5]

from generate_v3_signals import (  # noqa: E402
    SIGNAL_END,
    SIGNAL_START,
    build_candidate,
    build_entries,
    is_leader_seed,
    load_canonical_market_sessions,
    new_state,
    prewindow_seed_start,
    qualify_candidate,
    scan_symbol_pullbacks,
    seed_eligibility,
    validate_signal_integrity,
)


def make_state_frame() -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=235)
    close = np.linspace(80.0, 99.0, len(dates))
    frame = pd.DataFrame(
        {
            "Date": dates,
            "Open": close,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": np.full(len(dates), 2_000_000.0),
            "True_Range": np.full(len(dates), 2.0),
            "ATR14": np.full(len(dates), 2.0),
            "SMA20": close - 2.0,
            "SMA50": close - 4.0,
            "SMA200": close - 8.0,
            "Median_Traded_Value_20": np.full(len(dates), 200_000_000.0),
            "RS21": np.full(len(dates), 80.0),
            "RS63": np.full(len(dates), 80.0),
            "RS126": np.full(len(dates), 80.0),
            "Composite_RS": np.full(len(dates), 80.0),
            "RS_Coverage": np.full(len(dates), 1.0),
            "RS_Research_Safe": np.full(len(dates), True),
            "Point_In_Time_Member": np.full(len(dates), True),
        }
    )
    seed = 220
    frame.loc[seed - 19 : seed, "Close"] = np.linspace(95.0, 100.0, 20)
    frame.loc[seed - 19 : seed, "High"] = frame.loc[seed - 19 : seed, "Close"] + 0.5
    frame.loc[seed - 19 : seed, "Low"] = frame.loc[seed - 19 : seed, "Close"] - 0.5
    frame.loc[seed, ["Open", "High", "Low", "Close", "ATR14"]] = [99.5, 100.5, 99.0, 100.0, 2.0]
    return frame


def state_events(frame: pd.DataFrame) -> pd.DataFrame:
    return scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))[0]


def test_canonical_session_spine_and_prewindow_boundary():
    loaded = load_canonical_market_sessions(
        REPO_ROOT / "Swing Trading/nifty500_regime_daily.csv",
        pd.DatetimeIndex([pd.Timestamp("2026-08-27")]),
    )
    assert pd.Timestamp("2026-08-27") in loaded
    sessions = pd.bdate_range("2023-07-17", "2023-08-04")
    pos = int(sessions.searchsorted(SIGNAL_START, side="left"))
    assert prewindow_seed_start(sessions) == sessions[pos - 10]


def test_is_leader_seed_uses_twenty_session_closing_high_with_equality():
    frame = make_state_frame()
    assert is_leader_seed(frame, 220)
    frame.loc[220, "Close"] = 98.0
    assert not is_leader_seed(frame, 220)


def test_seed_eligibility_reports_exact_failure_codes():
    row = make_state_frame().loc[220].copy()
    mutations = {
        "NOT_POINT_IN_TIME_MEMBER": {"Point_In_Time_Member": False},
        "RS_COVERAGE_UNSAFE": {"RS_Research_Safe": False},
        "LIQUIDITY_FAIL": {"Median_Traded_Value_20": 99_999_999.0},
        "TREND_FAIL": {"SMA50": 100.0},
        "RS_FAIL": {"Composite_RS": 69.9},
    }
    for expected, changes in mutations.items():
        mutated = row.copy()
        for column, value in changes.items():
            mutated[column] = value
        assert seed_eligibility(mutated) == (False, expected)
    assert seed_eligibility(row) == (True, "")


def test_age_one_starts_on_session_after_seed():
    frame = make_state_frame()
    frame.loc[221, ["Close", "High", "Low"]] = [99.0, 99.5, 98.5]
    events, _ = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
    active = events.loc[events["Date"] == frame.loc[221, "Date"]]
    assert active.iloc[0]["Age"] == 1


def test_depth_uses_running_low_and_seed_atr():
    frame = make_state_frame()
    frame.loc[221, "Low"] = 96.0
    events, _ = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
    active = events.loc[events["Date"] == frame.loc[221, "Date"]]
    assert active.iloc[0]["Pullback_Depth_ATR"] == 2.0


def test_sma50_invalidation_precedes_depth_and_resumption():
    frame = make_state_frame()
    frame.loc[221, ["SMA50", "Close", "Low"]] = [99.0, 98.0, 93.0]
    events, candidates = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
    assert events.loc[events["Date"] == frame.loc[221, "Date"], "Event"].tolist() == ["SMA50_INVALIDATED"]
    assert candidates.empty


def test_depth_invalidation_precedes_new_leader_and_resumption():
    frame = make_state_frame()
    frame.loc[221, ["Low", "Close"]] = [94.0, 99.0]
    events, candidates = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
    assert events.loc[events["Date"] == frame.loc[221, "Date"], "Event"].tolist()[0] == "DEPTH_INVALIDATED"
    assert candidates.empty


def test_new_leader_closes_old_state_and_reseeds_same_bar():
    frame = make_state_frame()
    frame.loc[221, ["Close", "High", "Low"]] = [100.2, 100.4, 99.4]
    events, candidates = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
    same_day = events.loc[events["Date"] == frame.loc[221, "Date"], "Event"].tolist()
    assert same_day == ["NEW_LEADER_CLOSE", "SEEDED"]
    assert candidates.empty


def test_new_leader_close_requires_strictly_greater_close():
    frame = make_state_frame()
    # Seed row 220 has Leader_Close == 100.0.
    frame.loc[221, ["Close", "High", "Low", "SMA20"]] = [100.0, 100.5, 99.0, 97.0]

    events, candidates = scan_symbol_pullbacks(
        "AAA", frame, pd.DatetimeIndex(frame["Date"])
    )

    same_day = events.loc[
        events["Date"].eq(frame.loc[221, "Date"]), "Event"
    ].tolist()
    assert "NEW_LEADER_CLOSE" not in same_day
    assert candidates.empty


def test_too_short_resumption_closes_at_age_two():
    frame = make_state_frame()
    frame.loc[221, "High"] = 99.0
    frame.loc[222, ["High", "Close", "SMA20"]] = [98.5, 99.2, 97.0]
    events, candidates = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
    row = events.loc[(events["Date"] == frame.loc[222, "Date"]) & events["Event"].eq("TOO_SHORT_RESUMPTION")]
    assert row.iloc[0]["Age"] == 2
    assert candidates.empty


def test_valid_resumption_occurs_at_age_three():
    frame = make_state_frame()
    frame.loc[221, "Low"] = 98.0
    frame.loc[222, "Low"] = 97.5
    frame.loc[223, ["High", "Close", "SMA20"]] = [98.5, 99.0, 97.0]
    events, candidates = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
    assert len(candidates) == 1
    assert candidates.iloc[0]["Pullback_Age"] == 3
    assert "RESUMPTION_CANDIDATE" in events["Event"].tolist()


def test_valid_resumption_occurs_at_age_ten():
    frame = make_state_frame()
    frame.loc[221:229, "Close"] = np.linspace(98.5, 98.9, 9)
    frame.loc[221:229, "High"] = frame.loc[221:229, "Close"] + 0.5
    frame.loc[230, ["High", "Close", "SMA20"]] = [99.0, 99.5, 97.0]
    events, candidates = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
    assert len(candidates) == 1
    assert candidates.iloc[0]["Pullback_Age"] == 10


def test_no_resumption_by_age_ten_expires():
    frame = make_state_frame()
    events, candidates = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
    assert events.loc[events["Event"].eq("EXPIRED"), "Age"].tolist() == [10]
    assert candidates.empty


def test_too_shallow_resumption_is_rejected_and_state_ends():
    frame = make_state_frame()
    frame.loc[221:223, "Low"] = 99.2
    frame.loc[223, ["High", "Close", "SMA20"]] = [98.5, 99.0, 97.0]
    events, candidates = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
    assert not bool(candidates.iloc[0]["Signal_Qualified"])
    assert events.loc[events["Event"].eq("PULLBACK_TOO_SHALLOW")].shape[0] == 1
    assert events.loc[events["Event"].eq("RESUMPTION_CANDIDATE")].empty


def test_first_trigger_closes_state_even_when_signal_gate_fails():
    frame = make_state_frame()
    frame.loc[221, "Low"] = 98.0
    frame.loc[222, "Low"] = 97.5
    frame.loc[223, ["High", "Close", "SMA20", "Composite_RS"]] = [98.5, 99.0, 97.0, 69.9]
    events, candidates = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
    assert len(candidates) == 1
    assert not bool(candidates.iloc[0]["Signal_Qualified"])
    later = candidates.loc[candidates["Signal_Date"] > frame.loc[223, "Date"]]
    assert later.empty


def test_same_bar_reseed_runs_after_compatible_closures():
    cases = {
        "DEPTH_INVALIDATED": {221: {"Low": 94.0, "Close": 100.0, "High": 100.5}},
        "NEW_LEADER_CLOSE": {221: {"Close": 100.2, "High": 100.5, "Low": 99.0}},
        "TOO_SHORT_RESUMPTION": {
            221: {"High": 99.0},
            222: {"High": 98.5, "Close": 100.0, "SMA20": 97.0, "Low": 99.0},
        },
        "PULLBACK_TOO_SHALLOW": {
            221: {"Low": 99.2},
            222: {"Low": 99.2},
            223: {"Low": 99.2, "High": 98.5, "Close": 100.0, "SMA20": 97.0},
        },
        "RESUMPTION_CANDIDATE": {
            221: {"Low": 98.0},
            222: {"Low": 97.5},
            223: {"High": 98.5, "Close": 100.0, "SMA20": 97.0},
        },
        "EXPIRED": {
            221: {"Close": 98.0},
            229: {"High": 100.5, "Close": 99.0},
            230: {"High": 100.5, "Close": 100.0},
        },
    }
    for expected, mutations in cases.items():
        frame = make_state_frame()
        for index, changes in mutations.items():
            for column, value in changes.items():
                frame.loc[index, column] = value
        events, _ = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
        closure_dates = events.loc[events["Event"].eq(expected), "Date"]
        assert not closure_dates.empty, expected
        for date in closure_dates:
            same_day = events.loc[events["Date"].eq(date), "Event"].tolist()
            assert same_day[-1] == "SEEDED", (expected, date, same_day)


def test_sma50_closure_cannot_reseed_when_seed_trend_is_impossible():
    frame = make_state_frame()
    frame.loc[221, ["SMA50", "Close", "Low"]] = [99.0, 98.0, 98.0]
    events, _ = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
    same_day = events.loc[events["Date"] == frame.loc[221, "Date"], "Event"].tolist()
    assert same_day == ["SMA50_INVALIDATED"]


def test_pre_window_seed_can_create_in_window_signal_but_out_of_window_candidate_is_excluded():
    frame = make_state_frame()
    frame["Date"] = pd.bdate_range("2023-07-03", periods=len(frame))
    seed = int(frame.index[frame["Date"].eq(pd.Timestamp("2023-07-28"))][0])
    frame.loc[seed - 19 : seed, "Close"] = np.linspace(95.0, 100.0, 20)
    frame.loc[seed - 19 : seed, "High"] = frame.loc[seed - 19 : seed, "Close"] + 0.5
    frame.loc[seed - 19 : seed, "Low"] = frame.loc[seed - 19 : seed, "Close"] - 0.5
    frame.loc[seed, ["Open", "High", "Low", "Close", "ATR14"]] = [99.5, 100.5, 99.0, 100.0, 2.0]
    signal_index = int(frame.index[frame["Date"].eq(pd.Timestamp("2023-08-02"))][0])
    frame.loc[seed + 1 : signal_index - 1, "Low"] = 98.0
    frame.loc[signal_index, ["High", "Close", "SMA20", "Low"]] = [98.5, 99.0, 97.0, 98.0]
    events, candidates = scan_symbol_pullbacks("AAA", frame, pd.DatetimeIndex(frame["Date"]))
    assert events.loc[events["Event"].eq("SEEDED"), "Date"].min() == pd.Timestamp("2023-07-28")
    assert candidates["Signal_Date"].min() >= SIGNAL_START
    assert not candidates["Signal_Date"].between(pd.Timestamp("2023-07-31"), pd.Timestamp("2023-07-31")).any()


def test_new_state_stores_seed_metadata():
    frame = make_state_frame()
    state = new_state("AAA", frame.loc[220], 220)
    assert state["Leader_Date"] == frame.loc[220, "Date"]
    assert state["Leader_Close"] == 100.0
    assert state["ATR14_Seed"] == 2.0
    assert state["Age"] == 0
    assert state["Pullback_Low"] == np.inf
    assert state["Pullback_Indices"] == []


def test_build_candidate_carries_original_atr_and_running_pullback():
    frame = make_state_frame()
    active = new_state("AAA", frame.loc[220], 220)
    active["Age"] = 3
    active["Pullback_Low"] = 97.5
    active["Pullback_Indices"] = [221, 222, 223]
    candidate = build_candidate("AAA", frame.loc[223], 98.5, active)
    assert candidate["ATR14_Seed"] == 2.0
    assert candidate["Pullback_Low"] == 97.5
    assert candidate["Pullback_Depth_ATR"] == 1.25


def valid_candidate() -> dict[str, object]:
    return {
        "Entry_ID": "AAA-2024-01-10",
        "Symbol": "AAA",
        "Leader_Date": pd.Timestamp("2024-01-05"),
        "Signal_Date": pd.Timestamp("2024-01-10"),
        "Pullback_Age": 3,
        "Leader_Close": 100.0,
        "ATR14_Seed": 2.0,
        "ATR14_Signal": 2.0,
        "Pullback_Low": 98.0,
        "Pullback_Depth_ATR": 1.0,
        "Close": 99.5,
        "Prior_High": 99.0,
        "SMA20": 98.0,
        "SMA50": 95.0,
        "SMA200": 90.0,
        "Median_Traded_Value_20": 200_000_000.0,
        "Composite_RS": 80.0,
        "RS_Coverage": 1.0,
        "RS_Research_Safe": True,
        "Point_In_Time_Member": True,
    }


def test_candidate_qualification_uses_exact_signal_rejection_codes():
    mutations = {
        "NOT_POINT_IN_TIME_MEMBER": {"Point_In_Time_Member": False},
        "RS_COVERAGE_UNSAFE": {"RS_Research_Safe": False},
        "LIQUIDITY_FAIL": {"Median_Traded_Value_20": 99_999_999.0},
        "TREND_FAIL": {"SMA50": 100.0},
        "RS_FAIL": {"Composite_RS": 69.9},
        "AGE_FAIL": {"Pullback_Age": 2},
        "PULLBACK_TOO_SHALLOW": {"Pullback_Depth_ATR": 0.49},
        "DEPTH_FAIL": {"Pullback_Depth_ATR": 2.51},
        "RESUMPTION_FAIL": {"Close": 98.0},
        "NEW_LEADER_FAIL": {"Close": 100.01},
    }
    assert qualify_candidate(valid_candidate())["Signal_Qualified"]
    for expected, changes in mutations.items():
        candidate = valid_candidate()
        candidate.update(changes)
        result = qualify_candidate(candidate)
        assert not bool(result["Signal_Qualified"])
        assert result["Signal_Rejection_Reason"] == expected


def signal_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Entry_ID": "AAA-2024-01-10",
                "Symbol": "AAA",
                "Signal_Date": pd.Timestamp("2024-01-10"),
                "Leader_Date": pd.Timestamp("2024-01-05"),
                "Leader_Close": 100.0,
                "SMA20": 98.0,
                "ATR14_Signal": 4.0,
                "Pullback_Low": 96.0,
                "Signal_Qualified": True,
            }
        ]
    )


def prices_for_entry(open_price: float = 99.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-10", "2024-01-11", "2024-01-12"]),
            "Open": [100.0, open_price, 101.0],
            "High": [102.0, open_price + 1.0, 102.0],
            "Low": [99.0, open_price - 1.0, 100.0],
            "Close": [101.0, open_price, 101.0],
        }
    )


def test_entry_uses_immediate_next_session_and_signal_known_bounds():
    signals = signal_fixture()
    sessions = pd.DatetimeIndex(pd.to_datetime(["2024-01-10", "2024-01-11", "2024-01-12"]))
    accepted, cancellations = build_entries(signals, {"AAA": prices_for_entry()}, sessions)
    assert len(accepted) == 1
    assert cancellations.empty
    assert accepted.iloc[0]["Entry_Date"] == pd.Timestamp("2024-01-11")
    assert accepted.iloc[0]["Structural_Stop"] == 95.0


def test_entry_cancellation_reasons_are_precedence_ordered():
    sessions = pd.DatetimeIndex(pd.to_datetime(["2024-01-10", "2024-01-11", "2024-01-12"]))
    _, cancellations = build_entries(signal_fixture(), {"AAA": prices_for_entry(97.5)}, sessions)
    assert cancellations.iloc[0]["Cancellation_Reason"] == "OPEN_BELOW_SMA20_SIGNAL"
    _, cancellations = build_entries(signal_fixture(), {"AAA": prices_for_entry(102.1)}, sessions)
    assert cancellations.iloc[0]["Cancellation_Reason"] == "OPEN_ABOVE_EXTENSION_LIMIT"


def test_missing_immediate_bar_or_session_never_retries_later():
    sessions = pd.DatetimeIndex(pd.to_datetime(["2024-01-10", "2024-01-11", "2024-01-12"]))
    missing_bar = prices_for_entry().loc[[0, 2]].reset_index(drop=True)
    _, cancellations = build_entries(signal_fixture(), {"AAA": missing_bar}, sessions)
    assert cancellations.iloc[0]["Cancellation_Reason"] == "MISSING_NEXT_SESSION_BAR"
    no_next_session = pd.DatetimeIndex([pd.Timestamp("2024-01-10")])
    _, cancellations = build_entries(signal_fixture(), {"AAA": prices_for_entry()}, no_next_session)
    assert cancellations.iloc[0]["Cancellation_Reason"] == "MISSING_NEXT_SESSION"


def test_stop_rejections_use_signal_pullback_low_and_signal_atr():
    sessions = pd.DatetimeIndex(pd.to_datetime(["2024-01-10", "2024-01-11"]))
    too_high = signal_fixture().copy()
    too_high.loc[0, "Pullback_Low"] = 100.0
    _, cancellations = build_entries(too_high, {"AAA": prices_for_entry()}, sessions)
    assert cancellations.iloc[0]["Cancellation_Reason"] == "STOP_NOT_BELOW_ENTRY"
    too_wide = signal_fixture().copy()
    too_wide.loc[0, "Pullback_Low"] = 80.0
    _, cancellations = build_entries(too_wide, {"AAA": prices_for_entry()}, sessions)
    assert cancellations.iloc[0]["Cancellation_Reason"] == "STOP_TOO_WIDE"


def test_signal_integrity_rejects_delayed_entry():
    signals = signal_fixture()
    entries = pd.DataFrame(
        [
            {
                **signals.iloc[0].to_dict(),
                "Entry_Date": pd.Timestamp("2024-01-12"),
                "Entry_Open": 99.0,
                "Structural_Stop": 95.0,
            }
        ]
    )
    with pytest.raises(AssertionError, match="immediate next"):
        validate_signal_integrity(
            signals,
            entries,
            pd.DatetimeIndex(pd.to_datetime(["2024-01-10", "2024-01-11", "2024-01-12"])),
        )
