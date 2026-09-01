"""Acquire generic PIT inputs and build RR1's frozen feature frames."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import yfinance as yf

from constants import (
    ATR_PERIOD,
    DOWNLOAD_END_EXCLUSIVE,
    DOWNLOAD_START,
    MEMBERSHIP_PATH,
    NIFTY500_YAHOO_TICKER,
    SIGNAL_END,
    SIGNAL_START,
)

PRICE_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
AUDIT_COLUMNS = [
    "Symbol",
    "Yahoo_Ticker",
    "Member_From",
    "Member_To",
    "Raw_Rows",
    "Canonical_Rows",
    "Earliest_Date",
    "Latest_Date",
    "Duplicate_Dates",
    "Provider_Overlap_Dates",
    "Missing_Open",
    "Missing_High",
    "Missing_Low",
    "Missing_Close",
    "Missing_Volume",
    "Exact_Prehistory_Sessions",
    "Usable_Signal_Window_Sessions",
    "Download_Error",
]


def _naive_dates(values: object) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(values, errors="coerce"))
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    return dates.normalize()


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
    """Load inclusive point-in-time membership intervals."""

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
    """Download adjusted daily OHLCV without fabricating missing bars."""

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


def load_nifty500_benchmark(start: str, end_exclusive: str) -> pd.DataFrame:
    return download_adjusted_ohlcv(NIFTY500_YAHOO_TICKER, start, end_exclusive)


def canonical_sessions(benchmark: pd.DataFrame) -> pd.DatetimeIndex:
    if "Date" not in benchmark.columns:
        raise ValueError("benchmark must contain Date")
    dates = _naive_dates(benchmark["Date"])
    if dates.isna().any():
        raise ValueError("benchmark contains invalid dates")
    return pd.DatetimeIndex(sorted(dates.unique()))


def wilder_atr(true_range: pd.Series, period: int = ATR_PERIOD) -> pd.Series:
    """Compute Wilder ATR seeded by the first ``period`` valid TR values."""

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


def _normalise_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(PRICE_COLUMNS).difference(frame.columns)
    if missing:
        raise ValueError(f"price frame missing columns: {sorted(missing)}")
    result = frame.loc[:, PRICE_COLUMNS].copy()
    result["Date"] = _naive_dates(result["Date"])
    if result["Date"].isna().any():
        raise ValueError("price frame contains invalid dates")
    if result["Date"].duplicated().any():
        raise ValueError("price frame contains duplicate dates")
    for column in PRICE_COLUMNS[1:]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.sort_values("Date").reset_index(drop=True)


def compute_rr1_features(frame: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """Align one stock to the canonical session spine and compute frozen features."""

    source = _normalise_price_frame(frame)
    session_index = pd.DatetimeIndex(_naive_dates(sessions))
    if session_index.isna().any():
        raise ValueError("sessions contain invalid dates")
    session_index = session_index.drop_duplicates().sort_values()
    indexed = source.set_index("Date").reindex(session_index)
    indexed.index.name = "Date"
    result = indexed.reset_index()

    bar_valid = result[["Open", "High", "Low", "Close"]].notna().all(axis=1)
    result["Exact_Prehistory_61"] = bar_valid.rolling(62, min_periods=62).sum().eq(62)

    result["Range_Low"] = result["Low"].shift(1).rolling(60, min_periods=60).min()
    result["Range_High"] = result["High"].shift(1).rolling(60, min_periods=60).max()
    result["Range_Mid"] = (result["Range_Low"] + result["Range_High"]) / 2.0

    er_num = (result["Close"].shift(1) - result["Close"].shift(61)).abs()
    er_den = result["Close"].diff().abs().shift(1).rolling(60, min_periods=60).sum()
    result["ER60_Numerator"] = er_num
    result["ER60_Denominator"] = er_den
    result["ER60"] = er_num / er_den

    result["Daily_Traded_Value"] = result["Close"] * result["Volume"]
    result["Prior20_Median_Traded_Value"] = (
        result["Daily_Traded_Value"].shift(1).rolling(20, min_periods=20).median()
    )
    result["Prior20_Median_Volume"] = (
        result["Volume"].shift(1).rolling(20, min_periods=20).median()
    )
    result["Volume_Ratio"] = result["Volume"] / result["Prior20_Median_Volume"]

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

    result["Signal_Return"] = result["Close"].pct_change(fill_method=None)
    result["Range_Width_Pct"] = result["Range_High"] / result["Range_Low"] - 1.0
    result["Sweep_Depth_ATR"] = (
        result["Range_Low"] - result["Low"]
    ) / result["ATR14"]
    result["SMA20"] = result["Close"].rolling(20, min_periods=20).mean()
    result["SMA50"] = result["Close"].rolling(50, min_periods=50).mean()
    result["SMA200"] = result["Close"].rolling(200, min_periods=200).mean()
    result["Calendar_Year"] = result["Date"].dt.year
    return result


def _symbol_membership_mask(
    dates: pd.Series, membership: pd.DataFrame, symbol: str
) -> pd.Series:
    intervals = membership.loc[membership["Symbol"].eq(symbol)]
    mask = pd.Series(False, index=dates.index)
    for interval in intervals.itertuples(index=False):
        mask |= dates.ge(interval.Member_From) & dates.le(interval.Member_To)
    return mask


def _interval_text(group: pd.DataFrame, column: str) -> str:
    return ";".join(
        getattr(row, column).date().isoformat()
        for row in group.itertuples()
    )


def _audit_row(
    symbol: str,
    ticker: str,
    group: pd.DataFrame,
    frame: pd.DataFrame | None,
    raw_rows: int,
    duplicate_dates: int,
    overlap_dates: int,
    error: str = "",
) -> dict[str, object]:
    if frame is None:
        return {
            "Symbol": symbol,
            "Yahoo_Ticker": ticker,
            "Member_From": _interval_text(group, "Member_From"),
            "Member_To": _interval_text(group, "Member_To"),
            "Raw_Rows": raw_rows,
            "Canonical_Rows": 0,
            "Earliest_Date": "",
            "Latest_Date": "",
            "Duplicate_Dates": duplicate_dates,
            "Provider_Overlap_Dates": overlap_dates,
            "Missing_Open": 0,
            "Missing_High": 0,
            "Missing_Low": 0,
            "Missing_Close": 0,
            "Missing_Volume": 0,
            "Exact_Prehistory_Sessions": 0,
            "Usable_Signal_Window_Sessions": 0,
            "Download_Error": error,
        }
    window = frame["Date"].between(SIGNAL_START, SIGNAL_END)
    return {
        "Symbol": symbol,
        "Yahoo_Ticker": ticker,
        "Member_From": _interval_text(group, "Member_From"),
        "Member_To": _interval_text(group, "Member_To"),
        "Raw_Rows": raw_rows,
        "Canonical_Rows": len(frame),
        "Earliest_Date": frame["Date"].min().date().isoformat() if not frame.empty else "",
        "Latest_Date": frame["Date"].max().date().isoformat() if not frame.empty else "",
        "Duplicate_Dates": duplicate_dates,
        "Provider_Overlap_Dates": overlap_dates,
        "Missing_Open": int(frame["Open"].isna().sum()),
        "Missing_High": int(frame["High"].isna().sum()),
        "Missing_Low": int(frame["Low"].isna().sum()),
        "Missing_Close": int(frame["Close"].isna().sum()),
        "Missing_Volume": int(frame["Volume"].isna().sum()),
        "Exact_Prehistory_Sessions": int(
            frame.loc[window, "Exact_Prehistory_61"].fillna(False).sum()
        ),
        "Usable_Signal_Window_Sessions": int(
            (window & frame["Point_In_Time_Member"]).sum()
        ),
        "Download_Error": error,
    }


def _combine_provider_frames(frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, int, int]:
    if not frames:
        return pd.DataFrame(columns=PRICE_COLUMNS), 0, 0
    combined = pd.concat(frames, ignore_index=True)
    dates = combined["Date"]
    duplicate_dates = int(dates.duplicated(keep=False).sum())
    overlap_dates = int(dates[dates.duplicated(keep=False)].nunique())
    unique = combined.loc[~dates.duplicated(keep=False)].copy()
    if overlap_dates:
        invalid = combined.loc[dates.duplicated(keep=False)].drop_duplicates("Date")
        invalid.loc[:, PRICE_COLUMNS[1:]] = np.nan
        unique = pd.concat([unique, invalid], ignore_index=True)
    return unique.sort_values("Date").reset_index(drop=True), duplicate_dates, overlap_dates


def build_feature_frames(
    membership: pd.DataFrame,
    benchmark: pd.DataFrame,
    downloader: Callable[[str, str, str], pd.DataFrame] = download_adjusted_ohlcv,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Download distinct PIT providers and build one canonical frame per symbol."""

    sessions = canonical_sessions(benchmark)
    frames: dict[str, pd.DataFrame] = {}
    audit_rows: list[dict[str, object]] = []
    pairs = (
        membership.loc[
            membership["Downloadable"] & membership["Yahoo_Ticker"].ne(""),
            ["Symbol", "Yahoo_Ticker"],
        ]
        .drop_duplicates()
        .sort_values(["Symbol", "Yahoo_Ticker"])
    )
    for symbol, symbol_pairs in pairs.groupby("Symbol", sort=True):
        provider_frames: list[pd.DataFrame] = []
        errors: list[str] = []
        raw_rows = 0
        ticker_names: list[str] = []
        for pair in symbol_pairs.itertuples(index=False):
            ticker = str(pair.Yahoo_Ticker)
            ticker_names.append(ticker)
            try:
                downloaded = _normalise_price_frame(
                    downloader(ticker, DOWNLOAD_START, DOWNLOAD_END_EXCLUSIVE)
                )
                raw_rows += len(downloaded)
                provider_frames.append(downloaded)
            except Exception as exc:  # noqa: BLE001 - preserve source failures in audit
                errors.append(f"{ticker}: {type(exc).__name__}: {exc}")
        combined, duplicate_dates, overlap_dates = _combine_provider_frames(provider_frames)
        error = "; ".join(errors)
        symbol_membership = membership.loc[membership["Symbol"].eq(symbol)]
        if combined.empty:
            audit_rows.append(
                _audit_row(
                    str(symbol), ",".join(ticker_names), symbol_membership, None,
                    raw_rows, duplicate_dates, overlap_dates, error or "no provider rows",
                )
            )
            continue
        feature_frame = compute_rr1_features(combined, sessions)
        feature_frame["Symbol"] = str(symbol)
        feature_frame["Yahoo_Ticker"] = ",".join(ticker_names)
        feature_frame["Point_In_Time_Member"] = _symbol_membership_mask(
            feature_frame["Date"], membership, str(symbol)
        ).to_numpy()
        frames[str(symbol)] = feature_frame
        audit_rows.append(
            _audit_row(
                str(symbol), ",".join(ticker_names), symbol_membership, feature_frame,
                raw_rows, duplicate_dates, overlap_dates, error,
            )
        )
    validation = pd.DataFrame(audit_rows, columns=AUDIT_COLUMNS)
    return frames, validation


def main() -> None:
    root = Path(__file__).resolve().parents[4]
    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    membership = load_membership(
        root / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv"
    )
    benchmark = load_nifty500_benchmark(DOWNLOAD_START, DOWNLOAD_END_EXCLUSIVE)
    frames, validation = build_feature_frames(membership, benchmark)
    validation.to_csv(output_dir / "rr1_data_validation.csv", index=False)
    print(f"Built RR1 features for {len(frames)} symbols")
    print(f"Wrote {output_dir / 'rr1_data_validation.csv'}")


if __name__ == "__main__":
    main()
