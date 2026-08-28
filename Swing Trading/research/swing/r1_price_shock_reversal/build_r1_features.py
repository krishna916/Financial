"""Build the adjusted OHLCV and prior-window features used by R1."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import yfinance as yf


SIGNAL_START = pd.Timestamp("2023-08-01")
SIGNAL_END = pd.Timestamp("2026-08-25")
DOWNLOAD_START = "2022-01-01"
DOWNLOAD_END_EXCLUSIVE = "2026-08-27"
LIQUIDITY_FLOOR = 100_000_000.0
PRICE_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]


def _naive_dates(values: object) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(values, errors="coerce"))
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    return dates


def _parse_bool(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _validate_membership_intervals(membership: pd.DataFrame) -> None:
    if membership[["Member_From", "Member_To"]].isna().any().any():
        raise ValueError("membership contains invalid interval dates")
    if (membership["Member_From"] > membership["Member_To"]).any():
        raise ValueError("membership interval starts after its end")
    if membership["Symbol"].isna().any() or membership["Symbol"].eq("").any():
        raise ValueError("membership contains a blank symbol")

    ordered = membership.sort_values(["Symbol", "Member_From", "Member_To"])
    for symbol, group in ordered.groupby("Symbol", sort=False):
        if (group["Member_From"] <= group["Member_To"].shift()).any():
            raise ValueError(f"membership intervals overlap for {symbol}")


def load_membership(path: Path) -> pd.DataFrame:
    """Load and validate inclusive point-in-time membership intervals."""

    membership = pd.read_csv(path)
    required = {"Symbol", "Member_From", "Member_To", "Downloadable", "Yahoo_Ticker"}
    missing = required.difference(membership.columns)
    if missing:
        raise ValueError(f"membership missing columns: {sorted(missing)}")
    membership = membership.copy()
    membership["Symbol"] = membership["Symbol"].astype("string").str.strip()
    membership["Member_From"] = _naive_dates(membership["Member_From"])
    membership["Member_To"] = _naive_dates(membership["Member_To"])
    membership["Downloadable"] = membership["Downloadable"].map(_parse_bool)
    membership["Yahoo_Ticker"] = membership["Yahoo_Ticker"].fillna("").astype(str).str.strip()
    _validate_membership_intervals(membership)
    return membership.sort_values(["Member_From", "Symbol", "Member_To"]).reset_index(drop=True)


def active_members_on(membership: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    """Return members active on ``date``; both interval endpoints are inclusive."""

    required = {"Symbol", "Member_From", "Member_To"}
    missing = required.difference(membership.columns)
    if missing:
        raise ValueError(f"membership missing columns: {sorted(missing)}")
    day = _naive_dates([date])[0]
    if pd.isna(day):
        raise ValueError("date is invalid")
    frame = membership.copy()
    frame["Member_From"] = _naive_dates(frame["Member_From"])
    frame["Member_To"] = _naive_dates(frame["Member_To"])
    return frame.loc[
        frame["Member_From"].le(day) & frame["Member_To"].ge(day)
    ].sort_values("Symbol").reset_index(drop=True)


def _resolve_yahoo_field(frame: pd.DataFrame, field: str) -> object:
    if not isinstance(frame.columns, pd.MultiIndex):
        if field in frame.columns:
            return field
        raise ValueError(f"Yahoo response missing {field!r} column")
    matches = [
        column
        for column in frame.columns
        if field in {str(level) for level in column}
    ]
    if len(matches) != 1:
        raise ValueError(f"Yahoo response did not provide a unique {field!r} column")
    return matches[0]


def download_adjusted_ohlcv(ticker: str, start: str, end_exclusive: str) -> pd.DataFrame:
    """Download one ticker's adjusted daily OHLCV without fabricating missing bars."""

    raw = yf.download(
        tickers=ticker,
        start=start,
        end=end_exclusive,
        interval="1d",
        auto_adjust=True,
        actions=False,
        progress=False,
        threads=False,
        timeout=30,
    )
    if raw is None or raw.empty:
        raise ValueError(f"Yahoo returned no daily rows for {ticker}")
    frame = raw.reset_index() if "Date" not in raw.columns else raw.copy()
    if "Date" not in frame.columns:
        raise ValueError(f"Yahoo response missing Date for {ticker}")
    dates = _naive_dates(frame["Date"])
    if dates.isna().any():
        raise ValueError(f"Yahoo response contains invalid dates for {ticker}")
    if dates.duplicated().any():
        raise ValueError(f"Yahoo response contains duplicate dates for {ticker}")
    start_date = _naive_dates([start])[0]
    end_date = _naive_dates([end_exclusive])[0]
    if (dates < start_date).any() or (dates >= end_date).any():
        raise ValueError(f"Yahoo response contains dates outside requested range for {ticker}")

    normalized = pd.DataFrame({"Date": dates.to_numpy()})
    for field in PRICE_COLUMNS[1:]:
        column = _resolve_yahoo_field(frame, field)
        normalized[field] = pd.to_numeric(frame[column], errors="coerce").to_numpy()
    return normalized.sort_values("Date").reset_index(drop=True)


def wilder_atr(true_range: pd.Series, period: int = 14) -> pd.Series:
    """Compute Wilder ATR using the first ``period`` valid TR values to seed it."""

    if period <= 0:
        raise ValueError("period must be positive")
    values = pd.to_numeric(true_range, errors="coerce").to_numpy(dtype=float)
    result = np.full(len(values), np.nan, dtype=float)
    valid_values: list[float] = []
    previous_atr: float | None = None
    for index, value in enumerate(values):
        if not np.isfinite(value):
            continue
        if previous_atr is None:
            valid_values.append(float(value))
            if len(valid_values) == period:
                previous_atr = float(np.mean(valid_values))
                result[index] = previous_atr
        else:
            previous_atr = ((previous_atr * (period - 1)) + float(value)) / period
            result[index] = previous_atr
    return pd.Series(result, index=true_range.index, name="ATR14")


def compute_r1_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add frozen R1 features while preserving missing source values."""

    missing = set(PRICE_COLUMNS).difference(frame.columns)
    if missing:
        raise ValueError(f"price frame missing columns: {sorted(missing)}")
    result = frame.loc[:, PRICE_COLUMNS].copy()
    result["Date"] = _naive_dates(result["Date"])
    if result["Date"].isna().any():
        raise ValueError("price frame contains invalid dates")
    if result["Date"].duplicated().any():
        raise ValueError("price frame contains duplicate dates")
    result = result.sort_values("Date").reset_index(drop=True)
    for column in PRICE_COLUMNS[1:]:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    result["Return"] = result["Close"].pct_change(fill_method=None)
    result["Sigma20"] = (
        result["Return"].shift(1).rolling(20, min_periods=20).std(ddof=1)
    )
    result["Prior20_Median_Volume"] = (
        result["Volume"].shift(1).rolling(20, min_periods=20).median()
    )
    result["Daily_Traded_Value"] = result["Close"] * result["Volume"]
    result["Prior20_Median_Traded_Value"] = (
        result["Daily_Traded_Value"].shift(1).rolling(20, min_periods=20).median()
    )
    result["Volume_Ratio"] = result["Volume"] / result["Prior20_Median_Volume"]
    result["Shock_Score"] = result["Return"] / result["Sigma20"]

    previous_close = result["Close"].shift(1)
    true_range_parts = pd.concat(
        [
            result["High"] - result["Low"],
            (result["High"] - previous_close).abs(),
            (result["Low"] - previous_close).abs(),
        ],
        axis=1,
    )
    result["True_Range"] = true_range_parts.max(axis=1, skipna=True)
    result["ATR14"] = wilder_atr(result["True_Range"])

    result["SMA20"] = result["Close"].rolling(20, min_periods=20).mean()
    result["SMA50"] = result["Close"].rolling(50, min_periods=50).mean()
    result["SMA200"] = result["Close"].rolling(200, min_periods=200).mean()
    result["Return21"] = result["Close"] / result["Close"].shift(21) - 1.0
    result["Return63"] = result["Close"] / result["Close"].shift(63) - 1.0
    result["Return126"] = result["Close"] / result["Close"].shift(126) - 1.0
    result["Prior252_High"] = result["High"].shift(1).rolling(252, min_periods=252).max()
    result["Distance_From_252_High"] = result["Close"] / result["Prior252_High"] - 1.0
    return result


def _symbol_membership_mask(
    dates: pd.Series,
    membership: pd.DataFrame,
    symbol: str,
) -> pd.Series:
    intervals = membership.loc[membership["Symbol"].eq(symbol)]
    mask = pd.Series(False, index=dates.index)
    for interval in intervals.itertuples(index=False):
        mask |= dates.ge(interval.Member_From) & dates.le(interval.Member_To)
    return mask


def _audit_row(
    symbol: str,
    ticker: str,
    frame: pd.DataFrame | None,
    error: str = "",
) -> dict[str, object]:
    if frame is None:
        return {
            "Symbol": symbol,
            "Yahoo_Ticker": ticker,
            "Raw_Rows": 0,
            "Earliest_Date": "",
            "Latest_Date": "",
            "Duplicate_Dates": 0,
            "Missing_Open": 0,
            "Missing_High": 0,
            "Missing_Low": 0,
            "Missing_Close": 0,
            "Missing_Volume": 0,
            "First_Valid_Sigma20_Date": "",
            "First_Valid_ATR14_Date": "",
            "Usable": False,
            "Download_Error": error,
        }
    duplicate_dates = int(frame["Date"].duplicated().sum())
    required_values = ["Open", "High", "Low", "Close", "Volume"]
    return {
        "Symbol": symbol,
        "Yahoo_Ticker": ticker,
        "Raw_Rows": len(frame),
        "Earliest_Date": frame["Date"].min().date().isoformat() if not frame.empty else "",
        "Latest_Date": frame["Date"].max().date().isoformat() if not frame.empty else "",
        "Duplicate_Dates": duplicate_dates,
        "Missing_Open": int(frame["Open"].isna().sum()),
        "Missing_High": int(frame["High"].isna().sum()),
        "Missing_Low": int(frame["Low"].isna().sum()),
        "Missing_Close": int(frame["Close"].isna().sum()),
        "Missing_Volume": int(frame["Volume"].isna().sum()),
        "First_Valid_Sigma20_Date": (
            frame.loc[frame["Sigma20"].notna(), "Date"].min().date().isoformat()
            if frame["Sigma20"].notna().any()
            else ""
        ),
        "First_Valid_ATR14_Date": (
            frame.loc[frame["ATR14"].notna(), "Date"].min().date().isoformat()
            if frame["ATR14"].notna().any()
            else ""
        ),
        "Usable": bool(
            len(frame)
            and duplicate_dates == 0
            and frame[required_values].notna().all(axis=1).any()
        ),
        "Download_Error": error,
    }


def build_feature_frames(
    membership: pd.DataFrame,
    downloader: Callable[[str, str, str], pd.DataFrame] = download_adjusted_ohlcv,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Download and feature-build each distinct downloadable PIT symbol."""

    frames: dict[str, pd.DataFrame] = {}
    audit_rows: list[dict[str, object]] = []
    pairs = (
        membership.loc[
            membership["Downloadable"] & membership["Yahoo_Ticker"].ne(""),
            ["Symbol", "Yahoo_Ticker"],
        ]
        .drop_duplicates()
        .sort_values("Symbol")
    )
    for item in pairs.itertuples(index=False):
        symbol = str(item.Symbol)
        ticker = str(item.Yahoo_Ticker)
        try:
            frame = compute_r1_features(
                downloader(ticker, DOWNLOAD_START, DOWNLOAD_END_EXCLUSIVE)
            )
            frame["Point_In_Time_Member"] = _symbol_membership_mask(
                frame["Date"], membership, symbol
            ).to_numpy()
            frames[symbol] = frame
            audit_rows.append(_audit_row(symbol, ticker, frame))
        except Exception as exc:  # noqa: BLE001 - preserve failures in the audit
            audit_rows.append(
                _audit_row(symbol, ticker, None, f"{type(exc).__name__}: {exc}")
            )
    return frames, pd.DataFrame(audit_rows)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[4]
    membership_path = root / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv"
    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    membership = load_membership(membership_path)
    frames, validation = build_feature_frames(membership)
    validation.to_csv(output_dir / "r1_data_validation.csv", index=False)
    print(validation["Usable"].value_counts(dropna=False).to_string())
    failures = validation.loc[validation["Download_Error"].ne("")]
    for row in failures.itertuples(index=False):
        print(f"{row.Symbol}: {row.Download_Error}")
    print(f"Feature frames: {len(frames)}; failures: {len(failures)}")
