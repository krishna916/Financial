"""Frozen constants for the E1 positive earnings surprise drift study."""

from __future__ import annotations

import pandas as pd


PRIMARY_START = pd.Timestamp("2023-08-01")
PRIMARY_END = pd.Timestamp("2026-06-30")
SOURCE_CUTOFF = pd.Timestamp("2026-08-25")
FIRST_HALF_END = pd.Timestamp("2025-01-14")
SECOND_HALF_START = pd.Timestamp("2025-01-15")

BASE_FRICTION = 0.004
STRESS_FRICTION = 0.006
SEVERE_FRICTION = 0.008

PRICE_START = "2023-07-31"
PRICE_END_EXCLUSIVE = "2026-08-27"
NIFTY500_YAHOO_TICKER = "^CRSLDX"

EPS_HISTORY_START = pd.Timestamp("2020-01-01")
PRIMARY_POSITIVE_MIN = 300
PRIMARY_NEUTRAL_MIN = 300
PRIMARY_NEGATIVE_MIN = 300
TEMPORAL_POSITIVE_MIN = 100
TECHNICAL_EPS_COVERAGE_MIN = 0.95
COMPLETED_HOLDING_SESSIONS = 40
PRIMARY_PRICE_COHORTS = frozenset(
    {
        "POSITIVE_SURPRISE",
        "NEUTRAL_CONTROL",
        "NEGATIVE_CONTROL",
    }
)
PRICE_REQUIREMENT_COLUMNS = [
    "Event_ID",
    "Symbol",
    "Cohort",
    "SUE",
    "Event_Public_Date",
    "Fiscal_Period_End",
]

REQUIRED_INPUT_ARTIFACTS = (
    "e1_exchange_filings_snapshot.csv",
    "e1_eps_snapshot.csv",
    "e1_corporate_actions_snapshot.csv",
    "e1_stock_prices_snapshot.csv",
    "e1_nifty500_prices_snapshot.csv",
    "e1_price_identity_audit.csv",
    "e1_price_requirements.csv",
    "e1_source_manifest.csv",
    "e1_source_build_audit.csv",
)

REQUIRED_OUTPUT_ARTIFACTS = (
    "e1_data_validation.csv",
    "e1_source_coverage.csv",
    "e1_event_master.csv",
    "e1_event_exclusions.csv",
    "e1_eps_history.csv",
    "e1_sue_events.csv",
    "e1_cohort_classification.csv",
    "e1_positive_trades.csv",
    "e1_neutral_control.csv",
    "e1_negative_control.csv",
    "e1_validation_summary.csv",
    "e1_cohort_comparison.csv",
    "e1_benchmark_comparison.csv",
    "e1_temporal_summary.csv",
    "e1_year_summary.csv",
    "e1_leave_one_year_out.csv",
    "e1_top_five_robustness.csv",
    "e1_leave_one_symbol_out.csv",
    "e1_downside_diagnostic.csv",
    "e1_diagnostic_summary.csv",
    "e1_overlap_capacity_diagnostic.csv",
    "e1_integrity_audit.csv",
    "e1_validation_gates.csv",
    "research_report.md",
)
