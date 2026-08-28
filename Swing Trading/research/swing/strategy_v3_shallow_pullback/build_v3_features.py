"""Build Strategy V3 adjusted price features and point-in-time RS inputs."""

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
MIN_RS_COVERAGE = 0.80
LIQUIDITY_FLOOR = 100_000_000.0

PRICE_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
RETURN_COLUMNS = ["Return21", "Return63", "Return126"]
RS_COLUMNS = [
    "RS21",
    "RS63",
    "RS126",
    "Composite_RS",
    "RS_Active_Count",
    "RS_Eligible_Count",
    "RS_Coverage",
    "RS_Research_Safe",
]


def _naive_dates(values: object) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(values, errors="coerce"))
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    return dates


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
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
    """Load and validate the official inclusive point-in-time membership manifest."""

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
    """Return all manifest members active on ``date`` using inclusive intervals."""

    required = {"Symbol", "Member_From", "Member_To"}
    missing = required.difference(membership.columns)
    if missing:
        raise ValueError(f"membership missing columns: {sorted(missing)}")
    day = _naive_dates([date])[0]
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


def _wilder_atr(true_range: pd.Series, period: int = 14) -> pd.Series:
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


def compute_price_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add locked V3 indicators to one adjusted OHLCV frame."""

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
    result["ATR14"] = _wilder_atr(result["True_Range"])
    result["SMA20"] = result["Close"].rolling(20, min_periods=20).mean()
    result["SMA50"] = result["Close"].rolling(50, min_periods=50).mean()
    result["SMA200"] = result["Close"].rolling(200, min_periods=200).mean()
    result["Median_Traded_Value_20"] = (
        (result["Close"] * result["Volume"])
        .rolling(20, min_periods=20)
        .median()
    )
    result["Return21"] = result["Close"] / result["Close"].shift(21) - 1.0
    result["Return63"] = result["Close"] / result["Close"].shift(63) - 1.0
    result["Return126"] = result["Close"] / result["Close"].shift(126) - 1.0
    return result


def _frame_row_on_date(frame: pd.DataFrame, date: pd.Timestamp) -> pd.Series | None:
    rows = frame.loc[frame["Date"].eq(date)]
    if rows.empty:
        return None
    if len(rows) > 1:
        raise ValueError("feature frame contains duplicate dates")
    return rows.iloc[0]


def rank_point_in_time_rs(
    feature_frames: dict[str, pd.DataFrame],
    membership: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Rank same-day returns across the active point-in-time Nifty 500 universe."""

    if not feature_frames:
        return {}, pd.DataFrame(
            columns=[
                "Date",
                "Active_Member_Count",
                "Downloadable_Active_Count",
                "RS_Eligible_Count",
                "RS_Coverage",
                "RS_Research_Safe",
            ]
        )
    frames = {symbol: frame.copy() for symbol, frame in feature_frames.items()}
    for symbol, frame in frames.items():
        if "Date" not in frame.columns or set(RETURN_COLUMNS).difference(frame.columns):
            raise ValueError(f"feature frame for {symbol} lacks RS columns")
        frame["Date"] = _naive_dates(frame["Date"])
        for column in RS_COLUMNS:
            if column not in frame.columns:
                frame[column] = np.nan if column != "RS_Research_Safe" else False
        if "Point_In_Time_Member" not in frame.columns:
            frame["Point_In_Time_Member"] = False
        frames[symbol] = frame

    membership_start = _naive_dates(membership["Member_From"]).min()
    ranking_start = min(SIGNAL_START, membership_start)
    all_dates = sorted(
        {
            date
            for frame in frames.values()
            for date in frame.loc[
                frame["Date"].between(ranking_start, SIGNAL_END), "Date"
            ].dropna()
        }
    )
    audit_rows: list[dict[str, object]] = []
    for date in all_dates:
        active = active_members_on(membership, date)
        active_symbols = set(active["Symbol"].astype(str))
        rows_by_symbol = {
            symbol: _frame_row_on_date(frame, date)
            for symbol, frame in frames.items()
            if symbol in active_symbols
        }
        eligible_symbols = [
            symbol
            for symbol, row in rows_by_symbol.items()
            if row is not None
            and all(pd.notna(row[column]) for column in RETURN_COLUMNS)
            and ("Close" not in row.index or pd.notna(row["Close"]))
        ]
        active_count = len(active)
        eligible_count = len(eligible_symbols)
        coverage = eligible_count / active_count if active_count else np.nan
        safe = bool(active_count and coverage >= MIN_RS_COVERAGE)
        audit_rows.append(
            {
                "Date": date,
                "Active_Member_Count": active_count,
                "Downloadable_Active_Count": int(active["Downloadable"].sum())
                if "Downloadable" in active.columns
                else np.nan,
                "RS_Eligible_Count": eligible_count,
                "RS_Coverage": coverage,
                "RS_Research_Safe": safe,
            }
        )
        if not active_count:
            continue
        for symbol, frame in frames.items():
            mask = frame["Date"].eq(date)
            if not mask.any():
                continue
            frame.loc[mask, "Point_In_Time_Member"] = symbol in active_symbols
            frame.loc[mask, "RS_Active_Count"] = active_count
            frame.loc[mask, "RS_Eligible_Count"] = eligible_count
            frame.loc[mask, "RS_Coverage"] = coverage
            frame.loc[mask, "RS_Research_Safe"] = safe
        if not safe:
            continue
        eligible_frame = pd.DataFrame(
            [rows_by_symbol[symbol] for symbol in eligible_symbols],
            index=eligible_symbols,
        )
        ranks = {
            column: eligible_frame[column].rank(method="average", pct=True) * 100.0
            for column in RETURN_COLUMNS
        }
        for symbol in eligible_symbols:
            frame = frames[symbol]
            mask = frame["Date"].eq(date)
            frame.loc[mask, "RS21"] = ranks["Return21"].loc[symbol]
            frame.loc[mask, "RS63"] = ranks["Return63"].loc[symbol]
            frame.loc[mask, "RS126"] = ranks["Return126"].loc[symbol]
            frame.loc[mask, "Composite_RS"] = (
                0.30 * ranks["Return21"].loc[symbol]
                + 0.40 * ranks["Return63"].loc[symbol]
                + 0.30 * ranks["Return126"].loc[symbol]
            )
    return frames, pd.DataFrame(audit_rows)


def data_quality_audit(
    membership: pd.DataFrame,
    feature_frames: dict[str, pd.DataFrame],
    errors: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Create the compact per-symbol data-quality audit required by the plan."""

    errors = errors or {}
    rows: list[dict[str, object]] = []
    symbols = (
        membership.loc[membership["Downloadable"], ["Symbol", "Yahoo_Ticker"]]
        .drop_duplicates()
        .sort_values("Symbol")
    )
    for item in symbols.itertuples(index=False):
        symbol = str(item.Symbol)
        ticker = str(item.Yahoo_Ticker)
        frame = feature_frames.get(symbol)
        if frame is None:
            rows.append(
                {
                    "Symbol": symbol,
                    "Yahoo_Ticker": ticker,
                    "Download_Start": DOWNLOAD_START,
                    "Download_End": "",
                    "Raw_Rows": 0,
                    "Duplicate_Dates": 0,
                    "Missing_Open": 0,
                    "Missing_High": 0,
                    "Missing_Low": 0,
                    "Missing_Close": 0,
                    "Missing_Volume": 0,
                    "Usable": False,
                }
            )
            continue
        duplicate_count = int(frame["Date"].duplicated().sum())
        rows.append(
            {
                "Symbol": symbol,
                "Yahoo_Ticker": ticker,
                "Download_Start": DOWNLOAD_START,
                "Download_End": frame["Date"].max().date().isoformat()
                if not frame.empty
                else "",
                "Raw_Rows": len(frame),
                "Duplicate_Dates": duplicate_count,
                "Missing_Open": int(frame["Open"].isna().sum()),
                "Missing_High": int(frame["High"].isna().sum()),
                "Missing_Low": int(frame["Low"].isna().sum()),
                "Missing_Close": int(frame["Close"].isna().sum()),
                "Missing_Volume": int(frame["Volume"].isna().sum()),
                "Usable": bool(
                    len(frame)
                    and duplicate_count == 0
                    and frame[["Open", "High", "Low", "Close", "Volume"]]
                    .notna()
                    .any(axis=1)
                    .any()
                ),
            }
        )
    result = pd.DataFrame(rows)
    if errors:
        result.attrs["errors"] = errors
    return result


def build_feature_frames(
    membership: pd.DataFrame,
    downloader: Callable[[str, str, str], pd.DataFrame] = download_adjusted_ohlcv,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict[str, str]]:
    """Download, feature-build, and audit all distinct downloadable symbols."""

    frames: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
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
            frames[symbol] = compute_price_features(
                downloader(ticker, DOWNLOAD_START, DOWNLOAD_END_EXCLUSIVE)
            )
        except Exception as exc:  # noqa: BLE001 - preserve each failure in the audit
            errors[symbol] = f"{type(exc).__name__}: {exc}"
    audit = data_quality_audit(membership, frames, errors)
    audit.attrs["errors"] = errors
    return frames, audit, errors


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[4]
    membership_path = root / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv"
    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    membership = load_membership(membership_path)
    frames, validation, errors = build_feature_frames(membership)
    _, rs_audit = rank_point_in_time_rs(frames, membership)
    validation.to_csv(output_dir / "v3_data_validation.csv", index=False)
    rs_audit.to_csv(output_dir / "v3_universe_rs_audit.csv", index=False, date_format="%Y-%m-%d")
    print(validation["Usable"].value_counts(dropna=False).to_string())
    if errors:
        for symbol, error in sorted(errors.items()):
            print(f"{symbol}: {error}")
    print(f"RS dates: {len(rs_audit)}; safe: {int(rs_audit['RS_Research_Safe'].sum())}")
