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


def calculate_daily_stock_rs(
    frame: pd.DataFrame, expected_count: int = 20
) -> pd.DataFrame:
    """Calculate same-day cross-sectional RS for complete universe dates."""

    if expected_count <= 0:
        raise ValueError("expected_count must be positive")

    required_columns = {
        "Date",
        "Symbol",
        "Yahoo_Ticker",
        "Close",
        "Adj_Close",
        "Ret21",
        "Ret63",
        "Ret126",
    }
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        raise ValueError(
            "stock RS input is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    if frame.duplicated(["Date", "Symbol"]).any():
        raise ValueError("stock RS input contains duplicate (Date, Symbol) rows")

    result = frame.copy()
    horizon_columns = ["Ret21", "Ret63", "Ret126"]
    result = result.loc[result[horizon_columns].notna().all(axis=1)].copy()

    date_counts = result.groupby("Date")["Symbol"].nunique()
    complete_dates = date_counts[date_counts.eq(expected_count)].index
    result = result.loc[result["Date"].isin(complete_dates)].copy()

    for return_column, percentile_column in (
        ("Ret21", "RS21_Percentile"),
        ("Ret63", "RS63_Percentile"),
        ("Ret126", "RS126_Percentile"),
    ):
        result[percentile_column] = (
            result.groupby("Date")[return_column]
            .rank(method="average", pct=True, ascending=True)
            .mul(100.0)
        )

    result["Composite_RS"] = (
        0.30 * result["RS21_Percentile"]
        + 0.40 * result["RS63_Percentile"]
        + 0.30 * result["RS126_Percentile"]
    )
    result = result.sort_values(["Date", "Symbol"]).reset_index(drop=True)
    result["Composite_Rank"] = (
        result.groupby("Date")["Composite_RS"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    result["Stock_Count"] = expected_count
    result["Is_Full_Universe"] = True
    result["RS_Status"] = result["Composite_RS"].map(assign_rs_status)
    return result.sort_values(["Date", "Composite_Rank"]).reset_index(drop=True)
