"""Build the fixed-universe stock relative-strength dataset."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pandas as pd
import yfinance as yf


START_DATE = "2022-01-01"
END_DATE_EXCLUSIVE = "2026-08-26"
INTERVAL = "1d"
LATEST_INCLUDED_DATE = pd.Timestamp("2026-08-25")
START_DATE_TIMESTAMP = pd.Timestamp(START_DATE)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "stock_ticker_config.csv"
OUTPUT_DIR = BASE_DIR / "output"

EXPECTED_TICKERS = {
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "M&M": "M&M.NS",
    "MARUTI": "MARUTI.NS",
    "LT": "LT.NS",
    "RELIANCE": "RELIANCE.NS",
    "ONGC": "ONGC.NS",
    "ITC": "ITC.NS",
    "HINDUNILVR": "HINDUNILVR.NS",
    "SUNPHARMA": "SUNPHARMA.NS",
    "APOLLOHOSP": "APOLLOHOSP.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "TATASTEEL": "TATASTEEL.NS",
    "POWERGRID": "POWERGRID.NS",
    "ADANIENT": "ADANIENT.NS",
    "ULTRACEMCO": "ULTRACEMCO.NS",
}

PRIMARY_COLUMNS = [
    "Date",
    "Symbol",
    "Yahoo_Ticker",
    "Close",
    "Adj_Close",
    "Ret21",
    "Ret63",
    "Ret126",
    "RS21_Percentile",
    "RS63_Percentile",
    "RS126_Percentile",
    "Composite_RS",
    "Composite_Rank",
    "Stock_Count",
    "Is_Full_Universe",
    "RS_Status",
]
SUMMARY_COLUMNS = [
    "Symbol",
    "Yahoo_Ticker",
    "Valid_Ranked_Days",
    "Preferred_Days",
    "Valid_Days",
    "Below_Valid_Days",
    "Earliest_Ranked_Date",
    "Latest_Ranked_Date",
    "Mean_Composite_RS",
    "Median_Composite_RS",
]
VALIDATION_COLUMNS = [
    "Symbol",
    "Yahoo_Ticker",
    "Download_Status",
    "Raw_Rows",
    "Earliest_Raw_Date",
    "Latest_Raw_Date",
    "Duplicate_Date_Count",
    "Missing_Close_Count",
    "Missing_Adj_Close_Count",
]


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
    if dates.min() < START_DATE_TIMESTAMP or dates.max() > LATEST_INCLUDED_DATE:
        raise ValueError("Yahoo response contains a date outside locked range")

    normalized = pd.DataFrame(
        {
            "Date": dates.to_numpy(),
            "Symbol": symbol,
            "Yahoo_Ticker": ticker,
            "Close": pd.to_numeric(
                downloaded[close_column], errors="coerce"
            ).to_numpy(),
            "Adj_Close": pd.to_numeric(
                downloaded[adjusted_close_column], errors="coerce"
            ).to_numpy(),
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


def load_stock_config() -> pd.DataFrame:
    """Load and enforce the exact Issue #5 stock-to-Yahoo mapping."""

    config = pd.read_csv(CONFIG_PATH, dtype=str)
    if config.columns.tolist() != ["Symbol", "Yahoo_Ticker"]:
        raise ValueError("stock config must contain exactly Symbol,Yahoo_Ticker")
    if len(config) != len(EXPECTED_TICKERS):
        raise ValueError("stock config must contain exactly 20 stocks")
    if not config["Symbol"].is_unique or not config["Yahoo_Ticker"].is_unique:
        raise ValueError("stock config symbols and tickers must be unique")
    observed = dict(zip(config["Symbol"], config["Yahoo_Ticker"]))
    if observed != EXPECTED_TICKERS:
        raise ValueError("stock config does not match the locked Issue #5 mapping")
    return config


def validate_primary_output(frame: pd.DataFrame, expected_count: int = 20) -> None:
    """Fail loudly when the primary output violates a research invariant."""

    missing_columns = set(PRIMARY_COLUMNS).difference(frame.columns)
    if missing_columns:
        raise ValueError(
            "primary output is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )
    if frame.empty:
        raise ValueError("primary output is empty")
    if frame.duplicated(["Date", "Symbol"]).any():
        raise ValueError("primary output contains duplicate (Date, Symbol) rows")
    if frame[PRIMARY_COLUMNS].isna().any().any():
        raise ValueError("primary output contains missing required values")
    dates = pd.to_datetime(frame["Date"], errors="coerce")
    if dates.isna().any():
        raise ValueError("primary output contains invalid dates")
    if not dates.between(START_DATE_TIMESTAMP, LATEST_INCLUDED_DATE).all():
        raise ValueError("primary output contains date outside locked range")
    if not frame["Stock_Count"].eq(expected_count).all():
        raise ValueError("primary output contains an invalid Stock_Count")
    if not frame["Is_Full_Universe"].eq(True).all():
        raise ValueError("primary output contains a non-full-universe row")

    valid_statuses = {"PREFERRED", "VALID", "BELOW_VALID"}
    if not frame["RS_Status"].isin(valid_statuses).all():
        raise ValueError("primary output contains an invalid RS_Status")
    expected_statuses = frame["Composite_RS"].map(assign_rs_status)
    if not frame["RS_Status"].eq(expected_statuses).all():
        raise ValueError("primary output RS_Status does not match Composite_RS")

    for date, group in frame.groupby("Date", sort=False):
        if len(group) != expected_count or group["Symbol"].nunique() != expected_count:
            raise ValueError(f"date {date!r} does not contain the full stock universe")
        if set(group["Composite_Rank"]) != set(range(1, expected_count + 1)):
            raise ValueError(f"date {date!r} does not contain ranks 1..{expected_count}")

    for column in [
        "RS21_Percentile",
        "RS63_Percentile",
        "RS126_Percentile",
        "Composite_RS",
    ]:
        values = frame[column].to_numpy(dtype=float)
        if not ((values > 0.0) & (values <= 100.0)).all():
            raise ValueError(f"primary output contains an invalid {column}")

    recomputed = (
        0.30 * frame["RS21_Percentile"]
        + 0.40 * frame["RS63_Percentile"]
        + 0.30 * frame["RS126_Percentile"]
    )
    if not np.allclose(frame["Composite_RS"], recomputed, rtol=0.0, atol=1e-9):
        raise ValueError("primary output Composite_RS does not match 30/40/30")

    top_scores = (
        frame.loc[frame["Composite_Rank"].eq(1)]
        .set_index("Date")["Composite_RS"]
        .sort_index()
    )
    bottom_scores = (
        frame.loc[frame["Composite_Rank"].eq(expected_count)]
        .set_index("Date")["Composite_RS"]
        .sort_index()
    )
    if not (top_scores >= bottom_scores).all():
        raise ValueError("primary output rank 1 is weaker than rank 20")


def build_stock_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Build per-symbol ranked-day and status-count summaries."""

    validate_primary_output(frame)
    rows: list[dict[str, object]] = []
    for symbol in sorted(frame["Symbol"].unique()):
        stock = frame.loc[frame["Symbol"].eq(symbol)].copy()
        tickers = stock["Yahoo_Ticker"].unique()
        if len(tickers) != 1:
            raise ValueError(f"symbol {symbol!r} maps to multiple Yahoo tickers")
        status_counts = stock["RS_Status"].value_counts()
        row = {
            "Symbol": symbol,
            "Yahoo_Ticker": tickers[0],
            "Valid_Ranked_Days": int(len(stock)),
            "Preferred_Days": int(status_counts.get("PREFERRED", 0)),
            "Valid_Days": int(status_counts.get("VALID", 0)),
            "Below_Valid_Days": int(status_counts.get("BELOW_VALID", 0)),
            "Earliest_Ranked_Date": _format_date(stock["Date"].min()),
            "Latest_Ranked_Date": _format_date(stock["Date"].max()),
            "Mean_Composite_RS": float(stock["Composite_RS"].mean()),
            "Median_Composite_RS": float(stock["Composite_RS"].median()),
        }
        if (
            row["Preferred_Days"]
            + row["Valid_Days"]
            + row["Below_Valid_Days"]
            != row["Valid_Ranked_Days"]
        ):
            raise ValueError(f"summary status counts do not reconcile for {symbol}")
        rows.append(row)
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    output = frame.copy()
    if "Date" in output.columns:
        output["Date"] = pd.to_datetime(output["Date"]).dt.strftime("%Y-%m-%d")
    output.to_csv(path, index=False, lineterminator="\n")


def _publish_outputs(
    daily: pd.DataFrame, summary: pd.DataFrame, validation: pd.DataFrame
) -> None:
    """Stage all canonical CSVs and publish them with rollback on failure."""

    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=".stock_rs_publish_", dir=OUTPUT_DIR.parent)
    )
    staged = {
        "stock_rs_daily.csv": daily[PRIMARY_COLUMNS],
        "stock_rs_summary.csv": summary[SUMMARY_COLUMNS],
        "stock_rs_validation.csv": validation[VALIDATION_COLUMNS],
    }
    backups: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for filename, frame in staged.items():
            _write_csv(frame, staging_dir / filename)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for filename in staged:
            target = OUTPUT_DIR / filename
            backup = staging_dir / f"{filename}.backup"
            if target.exists():
                os.replace(target, backup)
                backups.append((target, backup))
            os.replace(staging_dir / filename, target)
            installed.append(target)
    except Exception:
        for target in installed:
            target.unlink(missing_ok=True)
        for target, backup in reversed(backups):
            if backup.exists():
                os.replace(backup, target)
        raise
    else:
        for _, backup in backups:
            backup.unlink(missing_ok=True)
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def build_stock_rs_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Download all configured stocks and build the validated daily dataset."""

    config = load_stock_config()
    calculated_frames: list[pd.DataFrame] = []
    validation_rows: list[dict[str, object]] = []
    failures: list[str] = []

    for row in config.to_dict(orient="records"):
        symbol = row["Symbol"]
        ticker = row["Yahoo_Ticker"]
        try:
            history = download_stock_history(symbol, ticker)
            validation = build_raw_validation_row(symbol, ticker, history)
            missing_prices = history[["Close", "Adj_Close"]].isna().any().any()
            if history.empty or validation["Duplicate_Date_Count"] != 0 or missing_prices:
                validation["Download_Status"] = "INVALID"
                failures.append(
                    f"{symbol}: invalid raw history "
                    f"(rows={validation['Raw_Rows']}, "
                    f"missing_close={validation['Missing_Close_Count']}, "
                    f"missing_adj_close={validation['Missing_Adj_Close_Count']}, "
                    f"duplicate_dates={validation['Duplicate_Date_Count']})"
                )
            else:
                calculated_frames.append(calculate_returns(history))
        except Exception as exc:
            validation = build_raw_validation_row(
                symbol, ticker, None, download_status="FAILED"
            )
            failures.append(f"{symbol}: {type(exc).__name__}: {exc}")
        validation_rows.append(validation)

    validation = pd.DataFrame(validation_rows, columns=VALIDATION_COLUMNS)
    if failures:
        details = "; ".join(failures)
        raise RuntimeError(f"stock RS raw-data validation failed: {details}")
    if len(calculated_frames) != len(EXPECTED_TICKERS):
        raise RuntimeError("stock RS build did not produce all 20 stock histories")
    if not validation["Download_Status"].eq("OK").all():
        raise RuntimeError("stock RS build requires 20/20 Download_Status == OK")

    combined = pd.concat(calculated_frames, ignore_index=True)
    daily = calculate_daily_stock_rs(combined, expected_count=len(EXPECTED_TICKERS))
    validate_primary_output(daily, expected_count=len(EXPECTED_TICKERS))
    return daily, validation


def run_build() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build and export all verified stock RS artifacts."""

    daily, validation = build_stock_rs_dataset()
    summary = build_stock_summary(daily)
    _publish_outputs(daily, summary, validation)

    print(f"Downloads: {len(validation)}/{len(EXPECTED_TICKERS)} OK")
    for row in validation.to_dict(orient="records"):
        print(
            f"{row['Symbol']}: raw_rows={row['Raw_Rows']} "
            f"dates={row['Earliest_Raw_Date']}..{row['Latest_Raw_Date']}"
        )
    print(
        f"Ranked dates: {daily['Date'].nunique()}; "
        f"primary rows: {len(daily)}; "
        f"ranked range: {_format_date(daily['Date'].min())}.."
        f"{_format_date(daily['Date'].max())}"
    )
    print(f"Generated outputs under {OUTPUT_DIR}")
    return daily, summary, validation


if __name__ == "__main__":
    try:
        run_build()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc
