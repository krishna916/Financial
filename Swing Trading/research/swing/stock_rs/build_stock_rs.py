"""Build the fixed-universe stock relative-strength dataset."""

from __future__ import annotations

import pandas as pd


def calculate_returns(frame: pd.DataFrame) -> pd.DataFrame:
    """Calculate fixed trading-session returns from adjusted close."""

    result = frame.copy()
    result["Ret21"] = result["Adj_Close"] / result["Adj_Close"].shift(21) - 1.0
    result["Ret63"] = result["Adj_Close"] / result["Adj_Close"].shift(63) - 1.0
    result["Ret126"] = result["Adj_Close"] / result["Adj_Close"].shift(126) - 1.0
    return result


def assign_rs_status(composite_rs: float) -> str:
    """Assign the locked V1 status band to a composite RS score."""

    if composite_rs >= 80.0:
        return "PREFERRED"
    if composite_rs >= 70.0:
        return "VALID"
    return "BELOW_VALID"
