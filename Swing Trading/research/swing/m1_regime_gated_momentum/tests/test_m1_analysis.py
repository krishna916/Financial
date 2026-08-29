import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyze_m1_results import (
    add_practical_friction,
    add_setup_friction,
    regime_comparison,
    safe_profit_factor,
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
