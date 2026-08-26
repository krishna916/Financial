"""Build the fixed-universe stock relative-strength dataset."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf


START_DATE = "2022-01-01"
END_DATE_EXCLUSIVE = "2026-08-26"
INTERVAL = "1d"

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "stock_ticker_config.csv"
OUTPUT_DIR = BASE_DIR / "output"


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


def _resolve_yahoo_column(downloaded: pd.DataFrame, field: str) -> object:
    """Resolve a price field from single-level or one-ticker MultiIndex data."""

    if not isinstance(downloaded.columns, pd.MultiIndex):
        if field in downloaded.columns:
            return field
        raise ValueError(
            f"Yahoo response did not provide a unique {field!r} column; "
            f"received columns: {list(downloaded.columns)!r}"
        )

    matches = [
        column
        for column in downloaded.columns
        if field in {str(level) for level in column}
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Yahoo response did not provide a unique {field!r} column; "
            f"received columns: {list(downloaded.columns)!r}"
        )
    return matches[0]


def normalize_yahoo_frame(
    downloaded: pd.DataFrame, symbol: str, ticker: str
) -> pd.DataFrame:
    """Normalize one ticker's Yahoo daily response without filling prices."""

    if downloaded is None or downloaded.empty:
        raise ValueError("Yahoo returned no daily rows")

    close_column = _resolve_yahoo_column(downloaded, "Close")
    adjusted_close_column = _resolve_yahoo_column(downloaded, "Adj Close")
    dates = pd.to_datetime(downloaded.index)
    if isinstance(dates, pd.DatetimeIndex) and dates.tz is not None:
        dates = dates.tz_localize(None)
    if pd.isna(dates).any():
        raise ValueError("Yahoo response contains invalid dates")
    if dates.duplicated().any():
        raise ValueError("Yahoo response contains duplicate dates")

    normalized = pd.DataFrame(
        {
            "Date": dates,
            "Symbol": symbol,
            "Yahoo_Ticker": ticker,
            "Close": pd.to_numeric(downloaded[close_column], errors="coerce"),
            "Adj_Close": pd.to_numeric(
                downloaded[adjusted_close_column], errors="coerce"
            ),
        }
    )
    return normalized.sort_values("Date").reset_index(drop=True)


def download_stock_history(symbol: str, ticker: str) -> pd.DataFrame:
    """Download and normalize one configured ticker's daily history."""

    downloaded = yf.download(
        ticker,
        start=START_DATE,
        end=END_DATE_EXCLUSIVE,
        interval=INTERVAL,
        auto_adjust=False,
        progress=False,
        actions=False,
    )
    return normalize_yahoo_frame(downloaded, symbol, ticker)


def _format_date(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def build_raw_validation_row(
    symbol: str,
    ticker: str,
    frame: pd.DataFrame | None,
    download_status: str = "OK",
) -> dict[str, object]:
    """Build one auditable raw-history validation record."""

    if frame is None or frame.empty:
        return {
            "Symbol": symbol,
            "Yahoo_Ticker": ticker,
            "Download_Status": download_status,
            "Raw_Rows": 0,
            "Earliest_Raw_Date": "",
            "Latest_Raw_Date": "",
            "Duplicate_Date_Count": 0,
            "Missing_Close_Count": 0,
            "Missing_Adj_Close_Count": 0,
        }

    return {
        "Symbol": symbol,
        "Yahoo_Ticker": ticker,
        "Download_Status": download_status,
        "Raw_Rows": int(len(frame)),
        "Earliest_Raw_Date": _format_date(frame["Date"].min()),
        "Latest_Raw_Date": _format_date(frame["Date"].max()),
        "Duplicate_Date_Count": int(frame["Date"].duplicated().sum()),
        "Missing_Close_Count": int(frame["Close"].isna().sum()),
        "Missing_Adj_Close_Count": int(frame["Adj_Close"].isna().sum()),
    }
