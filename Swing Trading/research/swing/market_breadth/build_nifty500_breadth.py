from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from yfinance import cache as yf_cache


MODULE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_ROOT.parents[3]
INDEX_PATH = PROJECT_ROOT / "Swing Trading" / "nifty500_regime_daily.csv"
MEMBERSHIP_PATH = MODULE_ROOT / "config" / "nifty500_membership.csv"
OUTPUT_ROOT = MODULE_ROOT / "output"

RESEARCH_START = pd.Timestamp("2023-08-01")
RESEARCH_END = pd.Timestamp("2026-08-25")
DOWNLOAD_START = "2022-08-01"
DOWNLOAD_END_EXCLUSIVE = "2026-08-26"
MIN_COVERAGE = 0.80


def _as_naive_dates(values: pd.Series | pd.Index) -> pd.Series | pd.DatetimeIndex:
    parsed = pd.to_datetime(values, errors="raise", utc=True)
    if isinstance(parsed, pd.Series):
        return parsed.dt.tz_localize(None).dt.normalize()
    return parsed.tz_localize(None).normalize()


def validate_membership_intervals(membership: pd.DataFrame) -> None:
    required = {"Symbol", "Member_From", "Member_To"}
    missing = required - set(membership.columns)
    if missing:
        raise ValueError(f"membership missing columns: {sorted(missing)}")
    frame = membership.copy()
    frame["Member_From"] = _as_naive_dates(frame["Member_From"])
    frame["Member_To"] = _as_naive_dates(frame["Member_To"])
    if (frame["Member_From"] > frame["Member_To"]).any():
        raise ValueError("membership interval starts after its end")
    if frame["Symbol"].isna().any() or frame["Symbol"].astype(str).str.strip().eq("").any():
        raise ValueError("membership contains a blank symbol")
    for symbol, group in frame.sort_values(["Symbol", "Member_From", "Member_To"]).groupby("Symbol", sort=False):
        previous_end = group["Member_To"].shift()
        if (group["Member_From"] <= previous_end).any():
            raise ValueError(f"membership intervals overlap for {symbol}")


def load_membership(path: Path = MEMBERSHIP_PATH) -> pd.DataFrame:
    membership = pd.read_csv(path)
    required = {"Symbol", "Member_From", "Member_To", "Method"}
    missing = required - set(membership.columns)
    if missing:
        raise ValueError(f"membership missing columns: {sorted(missing)}")
    if set(membership["Method"].dropna().astype(str)) != {"POINT_IN_TIME"}:
        raise ValueError("membership must use exactly the POINT_IN_TIME method")
    membership["Member_From"] = _as_naive_dates(membership["Member_From"])
    membership["Member_To"] = _as_naive_dates(membership["Member_To"])
    validate_membership_intervals(membership)
    return membership.sort_values(["Member_From", "Symbol", "Member_To"]).reset_index(drop=True)


def members_on_date(membership: pd.DataFrame, as_of: date | pd.Timestamp | str) -> pd.DataFrame:
    day = _as_naive_dates(pd.Index([as_of]))[0]
    frame = membership.copy()
    frame["Member_From"] = _as_naive_dates(frame["Member_From"])
    frame["Member_To"] = _as_naive_dates(frame["Member_To"])
    return frame.loc[(frame["Member_From"] <= day) & (day <= frame["Member_To"])].copy()


def calculate_stock_smas(history: pd.DataFrame) -> pd.DataFrame:
    if "Adj_Close" not in history.columns:
        raise ValueError("stock history must include Adj_Close")
    result = history.copy()
    result["SMA50"] = result["Adj_Close"].rolling(window=50, min_periods=50).mean()
    result["SMA200"] = result["Adj_Close"].rolling(window=200, min_periods=200).mean()
    return result


def _flatten_price_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if not isinstance(result.columns, pd.MultiIndex):
        return result
    required = {"Close", "Adj Close"}
    for level in range(result.columns.nlevels):
        values = result.columns.get_level_values(level)
        if required.issubset(set(values)):
            result.columns = values
            return result
    result.columns = result.columns.get_level_values(0)
    return result


def normalize_stock_history(raw: pd.DataFrame, symbol: str, yahoo_ticker: str) -> pd.DataFrame:
    frame = _flatten_price_columns(raw)
    if "Date" not in frame.columns:
        frame = frame.reset_index()
    required = {"Date", "Close", "Adj Close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{yahoo_ticker} history missing columns: {sorted(missing)}")
    result = frame.loc[:, ["Date", "Close", "Adj Close"]].rename(columns={"Adj Close": "Adj_Close"})
    result["Date"] = _as_naive_dates(result["Date"])
    if result["Date"].duplicated().any():
        raise ValueError(f"{yahoo_ticker} history contains duplicate dates")
    result["Symbol"] = symbol
    result["Yahoo_Ticker"] = yahoo_ticker
    return result.loc[:, ["Symbol", "Yahoo_Ticker", "Date", "Close", "Adj_Close"]].sort_values("Date").reset_index(drop=True)


def download_stock_history(yahoo_ticker: str, start: str = DOWNLOAD_START, end: str = DOWNLOAD_END_EXCLUSIVE) -> pd.DataFrame:
    raw = yf.download(
        tickers=yahoo_ticker,
        start=start,
        end=end,
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
        timeout=15,
    )
    return raw


def download_stock_histories(yahoo_tickers: list[str]) -> dict[str, pd.DataFrame]:
    if not yahoo_tickers:
        return {}
    raw = download_stock_history(" ".join(yahoo_tickers))
    if raw.empty:
        return {}
    if not isinstance(raw.columns, pd.MultiIndex):
        return {yahoo_tickers[0]: raw}
    ticker_level = next(
        (
            level
            for level in range(raw.columns.nlevels)
            if set(yahoo_tickers).intersection(set(raw.columns.get_level_values(level)))
        ),
        None,
    )
    if ticker_level is None:
        return {}
    return {
        ticker: raw.xs(ticker, axis=1, level=ticker_level, drop_level=True)
        for ticker in yahoo_tickers
        if ticker in set(raw.columns.get_level_values(ticker_level))
    }


def _finite(value: object) -> bool:
    return pd.notna(value) and np.isfinite(float(value))


def calculate_daily_breadth(
    membership: pd.DataFrame,
    stock_history: pd.DataFrame,
    research_start: date | pd.Timestamp | str,
    research_end: date | pd.Timestamp | str,
) -> pd.DataFrame:
    validate_membership_intervals(membership)
    required = {"Symbol", "Date", "Adj_Close", "SMA50", "SMA200"}
    missing = required - set(stock_history.columns)
    if missing:
        raise ValueError(f"stock history missing columns: {sorted(missing)}")
    history = stock_history.copy()
    history["Date"] = _as_naive_dates(history["Date"])
    if history.duplicated(["Symbol", "Date"]).any():
        raise ValueError("stock history contains duplicate symbol/date rows")
    start = _as_naive_dates(pd.Index([research_start]))[0]
    end = _as_naive_dates(pd.Index([research_end]))[0]
    dates = pd.DatetimeIndex(sorted(history.loc[history["Date"].between(start, end), "Date"].unique()))
    rows: list[dict[str, object]] = []
    for day in dates:
        members = members_on_date(membership, day)
        member_symbols = set(members["Symbol"].astype(str))
        day_history = history.loc[history["Date"].eq(day) & history["Symbol"].isin(member_symbols)].copy()
        covered = day_history.loc[day_history["Adj_Close"].map(_finite)]
        sma50 = day_history.loc[day_history["Adj_Close"].map(_finite) & day_history["SMA50"].map(_finite)]
        sma200 = day_history.loc[day_history["Adj_Close"].map(_finite) & day_history["SMA200"].map(_finite)]
        member_count = len(member_symbols)
        sma200_denominator = len(sma200)
        coverage_200 = sma200_denominator / member_count if member_count else np.nan
        rows.append(
            {
                "Date": day,
                "Member_Count": member_count,
                "Covered_Member_Count": len(covered),
                "SMA50_Denominator": len(sma50),
                "Above_SMA50_Count": int((sma50["Adj_Close"] > sma50["SMA50"]).sum()),
                "Pct_Above_SMA50": (100.0 * (sma50["Adj_Close"] > sma50["SMA50"]).mean()) if len(sma50) else np.nan,
                "SMA200_Denominator": sma200_denominator,
                "Above_SMA200_Count": int((sma200["Adj_Close"] > sma200["SMA200"]).sum()),
                "Pct_Above_SMA200": (100.0 * (sma200["Adj_Close"] > sma200["SMA200"]).mean()) if sma200_denominator else np.nan,
                "Coverage_200_Sessions": coverage_200,
                "Coverage_OK": bool(coverage_200 >= MIN_COVERAGE) if member_count else False,
            }
        )
    return pd.DataFrame(rows)


def load_nifty500_index_regime(path: Path = INDEX_PATH) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"Date", "Close", "SMA200"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"index history missing columns: {sorted(missing)}")
    frame["Date"] = _as_naive_dates(frame["Date"])
    if frame["Date"].duplicated().any():
        raise ValueError("index history contains duplicate dates")
    return frame.loc[:, ["Date", "Close", "SMA200"]].rename(
        columns={"Close": "Nifty500_Close", "SMA200": "Nifty500_SMA200"}
    ).sort_values("Date").reset_index(drop=True)


def classify_momentum_regime(row: pd.Series) -> str:
    values = row[["Nifty500_Close", "Nifty500_SMA200", "Pct_Above_SMA50", "Pct_Above_SMA200"]]
    if not all(_finite(value) for value in values):
        return "INSUFFICIENT_COVERAGE"
    if float(row["Nifty500_Close"]) <= float(row["Nifty500_SMA200"]):
        return "HOSTILE"
    if float(row["Pct_Above_SMA50"]) >= 60.0 and float(row["Pct_Above_SMA200"]) >= 60.0:
        return "STRONG_MOMENTUM"
    return "NORMAL"


def join_index_regime(breadth: pd.DataFrame, index_regime: pd.DataFrame) -> pd.DataFrame:
    result = breadth.merge(index_regime, on="Date", how="inner", validate="one_to_one")
    result["Regime"] = result.apply(classify_momentum_regime, axis=1)
    return result


def _history_audit_row(symbol: str, ticker: str, status: str, raw: pd.DataFrame | None = None, error: str = "") -> dict[str, object]:
    if raw is None or raw.empty:
        return {
            "Symbol": symbol,
            "Yahoo_Ticker": ticker,
            "Download_Status": status,
            "Raw_Row_Count": 0,
            "Raw_Date_Min": "",
            "Raw_Date_Max": "",
            "Missing_Close_Count": 0,
            "Missing_Adj_Close_Count": 0,
            "Duplicate_Date_Count": 0,
            "Error": error,
        }
    frame = _flatten_price_columns(raw)
    frame = frame.reset_index() if "Date" not in frame.columns else frame.copy()
    dates = _as_naive_dates(frame["Date"])
    close = frame["Close"] if "Close" in frame else pd.Series(dtype=float)
    adjusted = frame["Adj Close"] if "Adj Close" in frame else pd.Series(dtype=float)
    return {
        "Symbol": symbol,
        "Yahoo_Ticker": ticker,
        "Download_Status": status,
        "Raw_Row_Count": len(frame),
        "Raw_Date_Min": dates.min().date().isoformat() if len(dates) else "",
        "Raw_Date_Max": dates.max().date().isoformat() if len(dates) else "",
        "Missing_Close_Count": int(close.isna().sum()),
        "Missing_Adj_Close_Count": int(adjusted.isna().sum()),
        "Duplicate_Date_Count": int(dates.duplicated().sum()),
        "Error": error,
    }


def run_builder() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cache_root = OUTPUT_ROOT / ".yfinance_cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    yf_cache.set_cache_location(str(cache_root))
    membership = load_membership()
    audit_rows: list[dict[str, object]] = []
    histories: list[pd.DataFrame] = []
    ticker_values = membership["Yahoo_Ticker"].fillna("")
    downloadable = membership.loc[membership["Downloadable"].fillna(False) & ticker_values.ne("")]
    tickers = downloadable.loc[:, ["Symbol", "Yahoo_Ticker"]].drop_duplicates().sort_values("Symbol")
    ticker_by_symbol = dict(tickers.itertuples(index=False, name=None))
    symbol_by_ticker = {ticker: symbol for symbol, ticker in ticker_by_symbol.items()}
    ticker_list = sorted(symbol_by_ticker)
    for offset in range(0, len(ticker_list), 25):
        batch = ticker_list[offset : offset + 25]
        try:
            raw_by_ticker = download_stock_histories(batch)
        except Exception as exc:  # noqa: BLE001 - batch failures are retained in the audit
            raw_by_ticker = {}
            batch_error = str(exc)
        else:
            batch_error = ""
        for ticker in batch:
            symbol = symbol_by_ticker[ticker]
            raw = raw_by_ticker.get(ticker)
            if raw is None or raw.empty:
                audit_rows.append(_history_audit_row(symbol, ticker, "FAILED", error=batch_error or "ticker missing from batch response"))
                continue
            flattened = _flatten_price_columns(raw)
            if "Adj Close" not in flattened.columns or not flattened["Adj Close"].notna().any():
                audit_rows.append(_history_audit_row(symbol, ticker, "NO_USABLE_DATA", raw, "no adjusted-close observations returned"))
                continue
            try:
                normalized = normalize_stock_history(raw, symbol, ticker)
                audit_rows.append(_history_audit_row(symbol, ticker, "DOWNLOADED", raw))
                histories.append(calculate_stock_smas(normalized))
            except Exception as exc:  # noqa: BLE001 - malformed rows remain visible in the audit
                audit_rows.append(_history_audit_row(symbol, ticker, "FAILED", raw, str(exc)))
        time.sleep(0.1)
    audit = pd.DataFrame(audit_rows).sort_values("Symbol").reset_index(drop=True)
    if not histories:
        raise RuntimeError("no stock histories were downloaded")
    stock_history = pd.concat(histories, ignore_index=True)
    breadth = calculate_daily_breadth(membership, stock_history, RESEARCH_START, RESEARCH_END)
    joined = join_index_regime(breadth, load_nifty500_index_regime())
    joined["Universe_Method"] = "POINT_IN_TIME"
    joined["Universe_Member_Count"] = joined["Member_Count"]
    joined["Eligible_Count_50"] = joined["SMA50_Denominator"]
    joined["Eligible_Count_200"] = joined["SMA200_Denominator"]
    joined["Momentum_Regime"] = joined["Regime"]
    validation = pd.DataFrame(
        [
            {
                "Research_Start": RESEARCH_START.date().isoformat(),
                "Research_End": RESEARCH_END.date().isoformat(),
                "Universe_Method": "POINT_IN_TIME",
                "Breadth_Row_Count": len(joined),
                "Safe_Coverage_Row_Count": int(joined["Coverage_OK"].sum()),
                "Safe_Coverage_Min": float(joined["Coverage_200_Sessions"].min()),
                "Member_Count_Min": int(joined["Member_Count"].min()),
                "Member_Count_Max": int(joined["Member_Count"].max()),
                "Ticker_Count": len(tickers),
                "Download_Failure_Count": int((audit["Download_Status"] == "FAILED").sum()),
                "Unmatched_Index_Dates": int(joined["Nifty500_Close"].isna().sum()),
            }
        ]
    )
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    joined.to_csv(OUTPUT_ROOT / "nifty500_breadth_daily.csv", index=False, date_format="%Y-%m-%d")
    validation.to_csv(OUTPUT_ROOT / "breadth_data_validation.csv", index=False)
    audit.to_csv(OUTPUT_ROOT / "breadth_universe_audit.csv", index=False)
    return joined, validation, audit


if __name__ == "__main__":
    daily, validation, audit = run_builder()
    print(validation.to_string(index=False))
    print(audit["Download_Status"].value_counts(dropna=False).to_string())
    print(daily["Regime"].value_counts(dropna=False).to_string())
