import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyze_m1_results import (
    add_practical_friction,
    add_setup_friction,
    evaluate_gates,
    leave_one_symbol_out,
    overlap_capacity_diagnostic,
    regime_comparison,
    safe_profit_factor,
    top_five_robustness,
    temporal_summary,
)


def test_setup_friction_is_gross_return_minus_round_trip_cost():
    trades = pd.DataFrame([{"Entry_ID": "A", "Return": 0.02}])
    out, audit = add_setup_friction(trades)
    assert audit.empty
    assert out.loc[0, "Base_Net_Return"] == pytest.approx(0.016)
    assert out.loc[0, "Stress_Net_Return"] == pytest.approx(0.014)
    assert out.loc[0, "Severe_Net_Return"] == pytest.approx(0.012)


def test_practical_net_r_uses_entry_price_cost_over_initial_risk():
    trades = pd.DataFrame(
        [
            {
                "Entry_ID": "A",
                "Entry_Open": 100.0,
                "Structural_Stop": 95.0,
                "Initial_Risk": 5.0,
                "Exit_Price": 110.0,
                "R_Multiple": 2.0,
            }
        ]
    )
    out, audit = add_practical_friction(trades)
    assert audit.empty
    assert out.loc[0, "Base_Net_R"] == pytest.approx((10.0 - 0.4) / 5.0)
    assert out.loc[0, "Stress_Net_R"] == pytest.approx((10.0 - 0.6) / 5.0)


def test_initial_risk_mismatch_is_integrity_violation():
    trades = pd.DataFrame(
        [
            {
                "Entry_ID": "A",
                "Entry_Open": 100.0,
                "Structural_Stop": 95.0,
                "Initial_Risk": 4.0,
                "Exit_Price": 110.0,
                "R_Multiple": 2.0,
            }
        ]
    )
    _, audit = add_practical_friction(trades)
    assert "INITIAL_RISK_MISMATCH" in audit["Violation"].tolist()


def test_gross_r_mismatch_is_integrity_violation():
    trades = pd.DataFrame(
        [
            {
                "Entry_ID": "A",
                "Entry_Open": 100.0,
                "Structural_Stop": 95.0,
                "Initial_Risk": 5.0,
                "Exit_Price": 110.0,
                "R_Multiple": 1.5,
            }
        ]
    )
    _, audit = add_practical_friction(trades)
    assert "GROSS_R_MISMATCH" in audit["Violation"].tolist()


def test_profit_factor_boundaries():
    assert safe_profit_factor(pd.Series([2.0, -1.0])) == pytest.approx(2.0)
    assert safe_profit_factor(pd.Series([2.0, 1.0])) == np.inf
    assert safe_profit_factor(pd.Series([-2.0, -1.0])) == 0.0


def test_temporal_split_uses_signal_date_not_entry_date():
    trades = pd.DataFrame(
        [
            {"Entry_ID": "A", "Signal_Date": "2025-02-11", "Entry_Date": "2025-02-12", "Base_Net_R": 1.0},
            {"Entry_ID": "B", "Signal_Date": "2025-02-12", "Entry_Date": "2025-02-13", "Base_Net_R": -0.5},
        ]
    )
    out = temporal_summary(trades)
    counts = dict(zip(out["Period"], out["Completed_Trades"]))
    assert counts["FIRST_HALF"] == 1
    assert counts["SECOND_HALF"] == 1


def test_enabled_and_disabled_receive_identical_comparison_formula():
    enabled = pd.DataFrame({"Base_Net_R": [1.0, -0.2]})
    disabled = pd.DataFrame({"Base_Net_R": [0.1, -0.2]})
    out = regime_comparison(enabled, disabled).iloc[0]
    assert bool(out["Enabled_Beats_Disabled_Mean"])
    assert bool(out["Enabled_Beats_Disabled_R_PF"])


def passing_inputs(integrity_violations=0, completed_enabled=300):
    setup = {"Base_Mean_Net_Return": 0.01, "Base_Net_Return_PF": 1.5}
    practical = {
        "Base_Mean_Net_R": 0.25,
        "Base_Net_R_PF": 1.5,
        "Stress_Mean_Net_R": 0.10,
        "Stress_Net_R_PF": 1.2,
    }
    comparison = pd.DataFrame(
        [
            {
                "Enabled_Completed": completed_enabled,
                "Disabled_Completed": 50,
                "Enabled_Base_Mean_Net_R": 0.25,
                "Disabled_Base_Mean_Net_R": 0.05,
                "Enabled_Base_R_PF": 1.5,
                "Disabled_Base_R_PF": 1.05,
                "Enabled_Beats_Disabled_Mean": True,
                "Enabled_Beats_Disabled_R_PF": True,
            }
        ]
    )
    temporal = pd.DataFrame(
        [
            {"Period": "FIRST_HALF", "Mean_Base_Net_R": 0.1, "Base_R_PF": 1.1},
            {"Period": "SECOND_HALF", "Mean_Base_Net_R": 0.1, "Base_R_PF": 1.1},
        ]
    )
    top_five = pd.DataFrame([{"Remaining_Mean_Base_Net_R": 0.1, "Remaining_Base_R_PF": 1.1}])
    loso = pd.DataFrame(
        [
            {"Omitted_Symbol": "AAA", "Mean_Base_Net_R": 0.1, "Base_R_PF": 1.1},
            {"Omitted_Symbol": "BBB", "Mean_Base_Net_R": 0.1, "Base_R_PF": 1.1},
        ]
    )
    return setup, practical, comparison, temporal, top_five, loso, completed_enabled, integrity_violations


def test_sample_below_300_is_insufficient():
    status, _ = evaluate_gates(*passing_inputs(completed_enabled=299))
    assert status == "INSUFFICIENT_EVIDENCE"


def test_any_integrity_violation_overrides_insufficient_and_fail():
    status, _ = evaluate_gates(*passing_inputs(integrity_violations=1, completed_enabled=10))
    assert status == "INVALID_RESEARCH_RUN"


def test_all_mandatory_gates_pass_returns_pass():
    status, gates = evaluate_gates(*passing_inputs())
    assert status == "PASS"
    assert gates.loc[gates["Mandatory"], "Pass"].all()


def test_diagnostics_are_not_gate_inputs():
    _, gates = evaluate_gates(*passing_inputs())
    forbidden = {"SECTOR", "CAPACITY", "SIMULTANEOUS", "SAME_DAY", "RS_BAND"}
    assert all(not any(term in str(name) for term in forbidden) for name in gates["Gate"])


def test_valid_sufficient_single_gate_failure_returns_fail():
    args = list(passing_inputs())
    args[1] = dict(args[1])
    args[1]["Base_Mean_Net_R"] = 0.14
    status, _ = evaluate_gates(*args)
    assert status == "FAIL"


def test_top_five_removes_largest_gross_r_not_net_r():
    trades = pd.DataFrame(
        {
            "Entry_ID": list("ABCDEFG"),
            "R_Multiple": [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, -1.0],
            "Base_Net_R": [-5.0, 8.0, 7.0, 6.0, 5.0, 4.0, -1.0],
        }
    )
    out = top_five_robustness(trades)
    removed = set(out.loc[0, "Removed_Entry_IDs"].split(";"))
    assert removed == set("ABCDE")


def test_loso_reports_every_symbol():
    trades = pd.DataFrame({"Symbol": ["AAA", "AAA", "BBB"], "Base_Net_R": [1.0, -0.2, 0.5]})
    out = leave_one_symbol_out(trades)
    assert set(out["Omitted_Symbol"]) == {"AAA", "BBB"}


def test_overlap_capacity_uses_exact_one_percent_risk_weight_and_partial_sector_mapping():
    classification = pd.DataFrame(
        {
            "Entry_ID": ["A", "B"],
            "Symbol": ["AAA", "BBB"],
            "Signal_Date": pd.to_datetime(["2024-01-02", "2024-01-02"]),
        }
    )
    entries = pd.DataFrame(
        {
            "Entry_ID": ["A", "B"],
            "Symbol": ["AAA", "BBB"],
            "Entry_Date": pd.to_datetime(["2024-01-03", "2024-01-03"]),
            "Entry_Open": [100.0, 200.0],
            "Initial_Risk": [5.0, 20.0],
        }
    )
    practical = pd.DataFrame(
        {
            "Entry_ID": ["A", "B"],
            "Entry_Date": pd.to_datetime(["2024-01-03", "2024-01-03"]),
            "Exit_Date": pd.to_datetime(["2024-01-05", "2024-01-04"]),
        }
    )
    sector_mapping = pd.DataFrame({"Stock": ["AAA"], "Sector_Key": ["IT"]})
    sessions = pd.DatetimeIndex(pd.to_datetime(["2024-01-03", "2024-01-04", "2024-01-05"]))
    out = overlap_capacity_diagnostic(classification, entries, practical, sessions, sector_mapping)
    metrics = out.set_index(["Metric", "Dimension"])["Value"]
    assert float(metrics.loc[("MEDIAN_IMPLIED_POSITION_WEIGHT", "")]) == 0.15
    assert float(metrics.loc[("MAPPED_ACCEPTED_ENTRIES", "")]) == 1.0
    assert float(metrics.loc[("UNMAPPED_ACCEPTED_ENTRIES", "")]) == 1.0
    assert float(metrics.loc[("SECTOR_ENTRY_COUNT", "IT")]) == 1.0
