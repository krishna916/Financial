from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyze_rr1_results import (  # noqa: E402
    bootstrap_mean_ci,
    evaluate_gates,
    profit_factor,
)


def fake_evidence(
    integrity_ok: bool = True,
    lower_count: int = 300,
    first_count: int = 100,
    second_count: int = 100,
    upper_count: int = 100,
    profitable: bool = True,
) -> dict[str, object]:
    value = 1.0 if profitable else -1.0
    return {
        "integrity_ok": integrity_ok,
        "lower_count": lower_count,
        "first_count": first_count,
        "second_count": second_count,
        "upper_count": upper_count,
        "lens_a_mean": value,
        "lens_a_pf": 2.0 if profitable else 0.5,
        "lens_a_excess": value,
        "practical_mean_r": 0.2 if profitable else -0.2,
        "practical_rpf": 1.5 if profitable else 0.8,
        "practical_excess": value,
        "stress_mean_r": 0.1 if profitable else -0.3,
        "stress_rpf": 1.2 if profitable else 0.7,
        "lower_mean": 0.2 if profitable else -0.1,
        "upper_mean": -0.1 if profitable else 0.1,
        "first_practical_mean_r": 0.1 if profitable else -0.1,
        "first_practical_rpf": 1.1 if profitable else 0.8,
        "first_practical_excess": value,
        "second_practical_mean_r": 0.1 if profitable else -0.1,
        "second_practical_rpf": 1.1 if profitable else 0.8,
        "second_practical_excess": value,
        "topfive_ok": profitable,
        "year_robustness_ok": profitable,
        "symbol_robustness_ok": profitable,
    }


def test_profit_factor_uses_sum_winners_over_abs_sum_losers():
    assert profit_factor(pd.Series([2.0, 1.0, -1.0, -0.5])) == pytest.approx(2.0)


def test_integrity_failure_precedes_sample_and_profitability():
    gates, status = evaluate_gates(fake_evidence(integrity_ok=False, lower_count=0))
    assert status == "INVALID_RESEARCH_RUN"
    assert gates.loc[gates["Gate"] == "RESEARCH_VALIDITY", "Passed"].iloc[0] is False


def test_sample_failure_precedes_strategy_fail():
    gates, status = evaluate_gates(
        fake_evidence(
            integrity_ok=True,
            lower_count=299,
            first_count=150,
            second_count=149,
            upper_count=200,
            profitable=False,
        )
    )
    assert status == "INSUFFICIENT_EVIDENCE"


def test_positive_median_is_not_a_gate():
    evidence = fake_evidence()
    evidence["Practical_Median_R"] = -0.25
    gates, status = evaluate_gates(evidence)
    assert status == "PASS"
    assert "MEDIAN_PRACTICAL_R" not in set(gates["Gate"])


def test_practical_inclusive_boundaries_pass_and_strict_zero_gates_fail():
    evidence = fake_evidence()
    evidence.update(
        {
            "practical_mean_r": 0.15,
            "practical_rpf": 1.20,
            "lens_a_excess": 0.0,
            "upper_mean": 0.0,
        }
    )
    gates, status = evaluate_gates(evidence)
    assert status == "FAIL"
    assert gates.loc[gates["Gate"] == "PRACTICAL_EXPECTANCY", "Passed"].iloc[0] is True
    assert gates.loc[gates["Gate"] == "LENS_A_EXCESS", "Passed"].iloc[0] is False
    assert gates.loc[gates["Gate"] == "MIRROR_DIRECTION", "Passed"].iloc[0] is False


def test_bootstrap_is_seeded_and_reproducible():
    values = [0.1, -0.05, 0.2, 0.0]
    assert bootstrap_mean_ci(values, resamples=200) == bootstrap_mean_ci(values, resamples=200)
