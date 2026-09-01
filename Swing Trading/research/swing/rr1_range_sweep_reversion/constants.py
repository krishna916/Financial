"""Frozen constants for RR1 objective range sweep reversion."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SIGNAL_START = pd.Timestamp("2023-08-01")
SIGNAL_END = pd.Timestamp("2026-08-25")
FIRST_HALF_END = pd.Timestamp("2025-02-11")
SECOND_HALF_START = pd.Timestamp("2025-02-12")

DOWNLOAD_START = "2023-01-01"
DOWNLOAD_END_EXCLUSIVE = "2026-08-27"
NIFTY500_YAHOO_TICKER = "^CRSLDX"
MEMBERSHIP_PATH = (
    Path(__file__).resolve().parents[1]
    / "market_breadth"
    / "config"
    / "nifty500_membership.csv"
)

RANGE_LOOKBACK = 60
ER60_MAX = 0.25
LIQUIDITY_FLOOR = 100_000_000.0
ATR_PERIOD = 14
STOP_ATR_BUFFER = 0.25
MIN_INITIAL_RR = 2.0
HOLDING_SESSIONS = 15

BASE_FRICTION = 0.004
STRESS_FRICTION = 0.006
SEVERE_FRICTION = 0.008

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260831
MIN_LOWER_COMPLETED = 300
MIN_HALF_COMPLETED = 100
MIN_UPPER_COMPLETED = 100

