"""Validate the fixed T1 trade sample against point-in-time stock relative strength."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
SWING_RESEARCH_DIR = BASE_DIR.parent
SWING_TRADING_DIR = BASE_DIR.parents[2]

T1_TRADES_PATH = SWING_RESEARCH_DIR / "t1_sector_validation" / "input" / "t1_trades.csv"
STOCK_RS_PATH = SWING_RESEARCH_DIR / "stock_rs" / "output" / "stock_rs_daily.csv"
SECTOR_RS_PATH = SWING_RESEARCH_DIR / "sector_leadership" / "output" / "sector_leadership_daily.csv"
STOCK_SECTOR_MAP_PATH = SWING_RESEARCH_DIR / "sector_leadership" / "stock_sector_map.csv"
MARKET_REGIME_PATH = SWING_TRADING_DIR / "nifty500_regime_daily.csv"
OUTPUT_DIR = BASE_DIR / "output"

EXPECTED_T1_SHA256 = "6b4c2931f23f0e043816d973eba16b5bf3ca57411642d4528de060ea2febb1e4"
ALLOWED_RS_STATUSES = {"PREFERRED", "VALID", "BELOW_VALID"}
ALLOWED_MARKET_REGIMES = {"RISK_ON", "MIXED", "RISK_OFF"}
ALLOWED_SECTOR_BUCKETS = {"LEADING", "ACCEPTABLE", "WEAK", "LAGGING"}
MARKET_REGIME_ORDER = ["RISK_ON", "MIXED", "RISK_OFF"]
SECTOR_BUCKET_ORDER = ["LEADING", "ACCEPTABLE", "WEAK", "LAGGING"]
LOCKED_STOCK_SECTOR_MAP = {
    "HDFCBANK": "BANK",
    "ICICIBANK": "BANK",
    "SBIN": "BANK",
    "BAJFINANCE": "FINANCIAL_SERVICES",
    "TCS": "IT",
    "INFY": "IT",
    "M&M": "AUTO",
    "MARUTI": "AUTO",
    "LT": "INFRASTRUCTURE",
    "RELIANCE": "ENERGY",
    "ONGC": "ENERGY",
    "ITC": "FMCG",
    "HINDUNILVR": "FMCG",
    "SUNPHARMA": "PHARMA",
    "APOLLOHOSP": "PHARMA",
    "BHARTIARTL": "INFRASTRUCTURE",
    "TATASTEEL": "METAL",
    "POWERGRID": "ENERGY",
    "ADANIENT": "INFRASTRUCTURE",
    "ULTRACEMCO": "INFRASTRUCTURE",
}

EXPECTED_TRADE_COLUMNS = [
    "Symbol",
    "Entry_Date",
    "Exit_Date",
    "Entry_Price",
    "Exit_Price",
    "Qty",
    "Return_Pct",
    "PnL",
    "Holding_Days",
    "Source_Log",
]
STOCK_RS_REQUIRED_COLUMNS = [
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
METRIC_COLUMNS = [
    "Trades",
    "Winners",
    "Losers",
    "Win_Rate",
    "Mean_Return",
    "Median_Return",
    "Average_Winner",
    "Average_Loser",
    "Payoff_Ratio",
    "Return_Profit_Factor",
    "PnL_Profit_Factor",
    "Total_PnL",
    "Median_Holding_Days",
]
STOCK_RS_FEATURE_COLUMNS = [
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
STATUS_ORDER = ["PREFERRED", "VALID", "BELOW_VALID"]
PRIMARY_BINARY_SPECS = [
    (
        "PREFERRED_TEST",
        [("PREFERRED", {"PREFERRED"}), ("NON_PREFERRED", {"VALID", "BELOW_VALID"})],
    ),
    (
        "VALID_OR_BETTER_TEST",
        [("VALID_OR_BETTER", {"PREFERRED", "VALID"}), ("BELOW_VALID", {"BELOW_VALID"})],
    ),
]
JOINED_TRADE_COLUMNS = [
    "Symbol",
    "Entry_Date",
    "Exit_Date",
    "Entry_Price",
    "Exit_Price",
    "Qty",
    "Return_Pct",
    "PnL",
    "Holding_Days",
    "Source_Log",
    "RS_Matched_Date",
    "RS_Date_Lag_Days",
    *STOCK_RS_FEATURE_COLUMNS,
]
CONTEXT_EXPORT_COLUMNS = [
    "Market_Matched_Date",
    "Market_Date_Lag_Days",
    "Market_Regime",
    "Sector_Key",
    "Sector_Matched_Date",
    "Sector_Date_Lag_Days",
    "Leadership_Bucket",
    "Sector_Composite_RS",
    "Sector_Composite_Rank",
    "Sector_Count",
]
EXPECTED_T1_SYMBOLS = {
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "BAJFINANCE",
    "TCS",
    "INFY",
    "M&M",
    "MARUTI",
    "LT",
    "RELIANCE",
    "ONGC",
    "ITC",
    "HINDUNILVR",
    "SUNPHARMA",
    "APOLLOHOSP",
    "BHARTIARTL",
    "TATASTEEL",
    "POWERGRID",
    "ADANIENT",
    "ULTRACEMCO",
}


def _require_columns(frame: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def _parse_dates(
    frame: pd.DataFrame, columns: Iterable[str], label: str
) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_datetime(result[column], errors="coerce")
        if result[column].isna().any():
            raise ValueError(f"{label} has invalid or missing {column} values")
    return result


def _parse_full_universe_flag(series: pd.Series, label: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    normalized = series.astype("string").str.strip().str.lower()
    if normalized.isna().any() or not normalized.isin({"true", "false"}).all():
        raise ValueError(f"{label} contains invalid Is_Full_Universe values")
    return normalized.eq("true")


def _validate_finite_numeric(
    frame: pd.DataFrame, columns: Iterable[str], label: str
) -> None:
    values = frame[list(columns)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"{label} contains invalid numeric required values")


def load_and_validate_trades(path: Path = T1_TRADES_PATH) -> pd.DataFrame:
    """Load the immutable normalized T1 input and enforce locked invariants."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"fixed T1 input is missing: {path}")
    raw = path.read_bytes()
    if path.resolve() == T1_TRADES_PATH.resolve():
        digest = hashlib.sha256(raw).hexdigest()
        if digest != EXPECTED_T1_SHA256:
            raise ValueError(
                f"T1 input SHA-256 {digest} does not match expected {EXPECTED_T1_SHA256}"
            )

    trades = pd.read_csv(path)
    if trades.columns.tolist() != EXPECTED_TRADE_COLUMNS:
        raise ValueError(
            f"T1 input columns must be {EXPECTED_TRADE_COLUMNS}, "
            f"received {trades.columns.tolist()}"
        )
    trades = _parse_dates(trades, ("Entry_Date", "Exit_Date"), "T1 input")
    numeric_columns = (
        "Entry_Price",
        "Exit_Price",
        "Qty",
        "Return_Pct",
        "PnL",
        "Holding_Days",
    )
    for column in numeric_columns:
        trades[column] = pd.to_numeric(trades[column], errors="coerce")
    if trades[EXPECTED_TRADE_COLUMNS].isna().any().any():
        raise ValueError("T1 input contains null required fields")
    _validate_finite_numeric(trades, numeric_columns, "T1 input")
    duplicate_key = [
        "Symbol",
        "Entry_Date",
        "Exit_Date",
        "Entry_Price",
        "Exit_Price",
        "Qty",
    ]
    if trades.duplicated(duplicate_key).any():
        raise ValueError("T1 input contains duplicate normalized trade keys")
    if len(trades) != 218:
        raise ValueError(f"T1 input must contain 218 trades, found {len(trades)}")
    if set(trades["Symbol"]) != EXPECTED_T1_SYMBOLS:
        raise ValueError("T1 input symbols do not match the locked 20-stock basket")
    if (trades["Entry_Date"] > trades["Exit_Date"]).any():
        raise ValueError("T1 input contains Entry_Date after Exit_Date")
    if (trades["Qty"] <= 0).any():
        raise ValueError("T1 input contains non-positive Qty")
    if int((trades["Return_Pct"] > 0).sum()) != 76:
        raise ValueError("T1 input winner count is not 76")
    if not math.isclose(float(trades["PnL"].sum()), -4631.32, abs_tol=0.01):
        raise ValueError("T1 input total PnL does not equal -4631.32")
    if not math.isclose(
        float(trades["Return_Pct"].mean()), -0.0548680341, abs_tol=1e-8
    ):
        raise ValueError("T1 input mean Return_Pct does not match the locked aggregate")
    return trades


def load_and_validate_stock_rs(path: Path = STOCK_RS_PATH) -> pd.DataFrame:
    """Load the merged stock-RS output and reject unsafe or malformed rows."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"stock RS input is missing: {path}")
    stock_rs = pd.read_csv(path)
    _require_columns(stock_rs, STOCK_RS_REQUIRED_COLUMNS, "stock RS input")
    stock_rs = _parse_dates(stock_rs, ("Date",), "stock RS input")
    numeric_columns = [
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
    ]
    for column in numeric_columns:
        stock_rs[column] = pd.to_numeric(stock_rs[column], errors="coerce")
    stock_rs["Is_Full_Universe"] = _parse_full_universe_flag(
        stock_rs["Is_Full_Universe"], "stock RS input"
    )
    required = STOCK_RS_REQUIRED_COLUMNS
    if stock_rs[required].isna().any().any():
        raise ValueError("stock RS input contains null required values")
    _validate_finite_numeric(stock_rs, numeric_columns, "stock RS input")
    if stock_rs.duplicated(["Date", "Symbol"]).any():
        raise ValueError("stock RS input contains duplicate (Date, Symbol) rows")
    if set(stock_rs["Symbol"]) != EXPECTED_T1_SYMBOLS:
        raise ValueError("stock RS input symbols do not match the locked 20-stock basket")
    if not stock_rs["Stock_Count"].eq(20).all():
        raise ValueError("stock RS input contains a non-20 Stock_Count row")
    if not stock_rs["Is_Full_Universe"].eq(True).all():
        raise ValueError("stock RS input contains a non-full-universe row")
    if not stock_rs["Composite_Rank"].between(1, 20).all():
        raise ValueError("stock RS input contains a Composite_Rank outside 1..20")
    if not stock_rs["RS_Status"].isin(ALLOWED_RS_STATUSES).all():
        raise ValueError("stock RS input contains an invalid RS_Status")
    expected_status = stock_rs["Composite_RS"].map(
        lambda score: "PREFERRED"
        if score >= 80.0
        else "VALID"
        if score >= 70.0
        else "BELOW_VALID"
    )
    if not stock_rs["RS_Status"].eq(expected_status).all():
        raise ValueError("stock RS input RS_Status does not match Composite_RS")
    for date, group in stock_rs.groupby("Date", sort=False):
        if len(group) != 20 or set(group["Composite_Rank"]) != set(range(1, 21)):
            raise ValueError(
                f"stock RS date {date!s} does not contain the complete ranks 1..20"
            )
    return stock_rs.sort_values(["Date", "Composite_Rank"]).reset_index(drop=True)


def calculate_profit_factor(values: pd.Series) -> float:
    """Calculate positive sum divided by the absolute non-positive sum."""

    numeric = pd.to_numeric(values, errors="coerce").dropna()
    positive = float(numeric.loc[numeric > 0].sum())
    non_positive = float(numeric.loc[numeric <= 0].sum())
    if non_positive == 0:
        return math.inf if positive > 0 else math.nan
    if positive == 0:
        return 0.0
    return positive / abs(non_positive)


def _payoff_ratio(average_winner: float, average_loser: float) -> float:
    if math.isnan(average_loser):
        return math.inf if not math.isnan(average_winner) else math.nan
    if average_loser == 0:
        return math.nan
    if math.isnan(average_winner):
        return 0.0
    return average_winner / abs(average_loser)


def calculate_trade_metrics(
    frame: pd.DataFrame,
) -> dict[str, float | int]:
    """Return the locked return, PnL, and holding-period metrics."""

    _require_columns(frame, ["Return_Pct", "PnL", "Holding_Days"], "trade data")
    returns = pd.to_numeric(frame["Return_Pct"], errors="coerce")
    pnl = pd.to_numeric(frame["PnL"], errors="coerce")
    holding = pd.to_numeric(frame["Holding_Days"], errors="coerce")
    count = len(frame)
    winners = returns.loc[returns > 0]
    losers = returns.loc[returns <= 0]
    average_winner = float(winners.mean()) if not winners.empty else math.nan
    average_loser = float(losers.mean()) if not losers.empty else math.nan
    return {
        "Trades": count,
        "Winners": int(len(winners)),
        "Losers": int(len(losers)),
        "Win_Rate": float(len(winners) / count * 100.0) if count else math.nan,
        "Mean_Return": float(returns.mean()) if count else math.nan,
        "Median_Return": float(returns.median()) if count else math.nan,
        "Average_Winner": average_winner,
        "Average_Loser": average_loser,
        "Payoff_Ratio": _payoff_ratio(average_winner, average_loser),
        "Return_Profit_Factor": calculate_profit_factor(returns),
        "PnL_Profit_Factor": calculate_profit_factor(pnl),
        "Total_PnL": float(pnl.sum()) if count else 0.0,
        "Median_Holding_Days": float(holding.median()) if count else math.nan,
    }


def join_stock_rs_at_decision_time(
    trades: pd.DataFrame, rs: pd.DataFrame
) -> pd.DataFrame:
    """Backward/as-of join stock RS observations strictly before each entry."""

    _require_columns(trades, ["Symbol", "Entry_Date"], "T1 trade data")
    _require_columns(rs, ["Date", "Symbol", *STOCK_RS_FEATURE_COLUMNS], "stock RS data")
    left = _parse_dates(trades, ("Entry_Date",), "T1 trade data").reset_index(drop=True)
    right = _parse_dates(rs, ("Date",), "stock RS data")
    if right.duplicated(["Date", "Symbol"]).any():
        raise ValueError("stock RS data contains duplicate (Date, Symbol) rows")
    left["_trade_order"] = np.arange(len(left))
    pieces: list[pd.DataFrame] = []
    for symbol, trade_group in left.groupby("Symbol", sort=False):
        ordered_trades = trade_group.sort_values("Entry_Date")
        feature_group = right.loc[right["Symbol"].eq(symbol), ["Date", *STOCK_RS_FEATURE_COLUMNS]]
        feature_group = feature_group.sort_values("Date")
        if feature_group.empty:
            matched = ordered_trades.copy()
            matched["RS_Matched_Date"] = pd.NaT
            for column in STOCK_RS_FEATURE_COLUMNS:
                matched[column] = np.nan
        else:
            matched = pd.merge_asof(
                ordered_trades,
                feature_group,
                left_on="Entry_Date",
                right_on="Date",
                direction="backward",
                allow_exact_matches=False,
            )
            matched = matched.rename(columns={"Date": "RS_Matched_Date"})
        pieces.append(matched)
    if not pieces:
        raise ValueError("no trade rows available for stock RS join")
    joined = (
        pd.concat(pieces, ignore_index=True)
        .sort_values("_trade_order")
        .reset_index(drop=True)
    )
    joined["RS_Date_Lag_Days"] = (
        joined["Entry_Date"] - joined["RS_Matched_Date"]
    ).dt.days
    return joined.drop(columns="_trade_order")


def validate_stock_rs_join(
    joined: pd.DataFrame,
    expected_trade_count: int = 218,
    expected_total_pnl: float = -4631.32,
) -> None:
    """Fail loudly when the strict stock-RS join violates locked invariants."""

    _require_columns(
        joined,
        [
            "Symbol",
            "Entry_Date",
            "RS_Matched_Date",
            "RS_Date_Lag_Days",
            *STOCK_RS_FEATURE_COLUMNS,
        ],
        "joined stock RS data",
    )
    if len(joined) != expected_trade_count:
        raise ValueError(
            f"joined stock RS rows must equal {expected_trade_count}, found {len(joined)}"
        )
    unmatched = int(joined["RS_Matched_Date"].isna().sum())
    if unmatched:
        missing = joined.loc[
            joined["RS_Matched_Date"].isna(), ["Symbol", "Entry_Date"]
        ]
        raise ValueError(f"{unmatched} trades could not be matched to a prior stock RS row: {missing.to_dict('records')}")
    if (joined["RS_Matched_Date"] >= joined["Entry_Date"]).any():
        raise ValueError("stock RS join used a same-entry-day or future observation")
    if (joined["RS_Date_Lag_Days"] <= 0).any():
        raise ValueError("stock RS date lag must be strictly positive")
    if not joined["Stock_Count"].eq(20).all():
        raise ValueError("stock RS join contains a non-20 Stock_Count match")
    if not joined["Is_Full_Universe"].eq(True).all():
        raise ValueError("stock RS join contains a non-full-universe match")
    if not joined["Composite_Rank"].between(1, 20).all():
        raise ValueError("stock RS join contains a Composite_Rank outside 1..20")
    if not joined["RS_Status"].isin(ALLOWED_RS_STATUSES).all():
        raise ValueError("stock RS join contains an invalid RS_Status")
    if "PnL" in joined.columns and not math.isclose(
        float(joined["PnL"].sum()), expected_total_pnl, abs_tol=0.01
    ):
        raise ValueError("joined stock RS PnL does not reconcile to the locked T1 input")


def summarize_status_groups(joined: pd.DataFrame) -> pd.DataFrame:
    """Summarize the three locked stock-RS status bands in fixed order."""

    _require_columns(joined, ["RS_Status", *["Return_Pct", "PnL", "Holding_Days"]], "joined stock RS data")
    if not joined["RS_Status"].isin(ALLOWED_RS_STATUSES).all():
        raise ValueError("joined stock RS data contains an invalid RS_Status")
    rows = []
    for status in STATUS_ORDER:
        group = joined.loc[joined["RS_Status"].eq(status)]
        rows.append({"RS_Status": status, **calculate_trade_metrics(group)})
    return pd.DataFrame(rows, columns=["RS_Status", *METRIC_COLUMNS])


def summarize_primary_binary_tests(joined: pd.DataFrame) -> pd.DataFrame:
    """Summarize only the two predeclared binary stock-RS comparisons."""

    _require_columns(joined, ["RS_Status", "Return_Pct", "PnL", "Holding_Days"], "joined stock RS data")
    if not joined["RS_Status"].isin(ALLOWED_RS_STATUSES).all():
        raise ValueError("joined stock RS data contains an invalid RS_Status")
    rows = []
    for comparison, groups in PRIMARY_BINARY_SPECS:
        for group_name, statuses in groups:
            group = joined.loc[joined["RS_Status"].isin(statuses)]
            rows.append(
                {"Comparison": comparison, "Group": group_name, **calculate_trade_metrics(group)}
            )
    return pd.DataFrame(rows, columns=["Comparison", "Group", *METRIC_COLUMNS])


def summarize_composite_ranks(joined: pd.DataFrame) -> pd.DataFrame:
    """Export diagnostic metrics for each exact Composite_Rank from 1 through 20."""

    _require_columns(
        joined,
        ["Composite_Rank", "Composite_RS", "Return_Pct", "PnL", "Holding_Days"],
        "joined stock RS data",
    )
    ranks = pd.to_numeric(joined["Composite_Rank"], errors="coerce")
    if ranks.isna().any() or not ranks.eq(ranks.round()).all() or not ranks.between(1, 20).all():
        raise ValueError("joined stock RS data contains a Composite_Rank outside 1..20")
    rows = []
    for rank in range(1, 21):
        group = joined.loc[ranks.eq(rank)]
        rows.append(
            {
                "Composite_Rank": rank,
                **calculate_trade_metrics(group),
                "Mean_Composite_RS": float(group["Composite_RS"].mean())
                if not group.empty
                else math.nan,
                "Median_Composite_RS": float(group["Composite_RS"].median())
                if not group.empty
                else math.nan,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "Composite_Rank",
            *METRIC_COLUMNS,
            "Mean_Composite_RS",
            "Median_Composite_RS",
        ],
    )


def summarize_by_entry_year(joined: pd.DataFrame) -> pd.DataFrame:
    """Recompute both locked binary tests independently for entry years 2023-2026."""

    _require_columns(joined, ["Entry_Date"], "joined stock RS data")
    frame = _parse_dates(joined, ("Entry_Date",), "joined stock RS data")
    parts = []
    for year in (2023, 2024, 2025, 2026):
        year_frame = frame.loc[frame["Entry_Date"].dt.year.eq(year)]
        binary = summarize_primary_binary_tests(year_frame)
        binary.insert(0, "Entry_Year", year)
        parts.append(binary)
    return pd.concat(parts, ignore_index=True)


def summarize_outlier_robustness(joined: pd.DataFrame) -> pd.DataFrame:
    """Recompute primary tests after removing only globally largest positive PnLs."""

    _require_columns(
        joined,
        ["PnL", "Entry_Date", "Symbol", "Exit_Date"],
        "joined stock RS data",
    )
    positive = joined.loc[joined["PnL"] > 0].sort_values(
        ["PnL", "Entry_Date", "Symbol", "Exit_Date"],
        ascending=[False, True, True, True],
    )
    parts = []
    for scenario, count in (
        ("ALL_TRADES", 0),
        ("EXCLUDE_TOP_1_POSITIVE_PNL", 1),
        ("EXCLUDE_TOP_3_POSITIVE_PNL", 3),
        ("EXCLUDE_TOP_5_POSITIVE_PNL", 5),
    ):
        excluded = positive.head(count)
        excluded_indices = set(excluded.index)
        retained = joined.loc[~joined.index.isin(excluded_indices)]
        excluded_text = ";".join(
            f"{row.Symbol}|{pd.Timestamp(row.Entry_Date):%Y-%m-%d}|{float(row.PnL):.2f}"
            for row in excluded.itertuples()
        )
        binary = summarize_primary_binary_tests(retained)
        binary.insert(0, "Scenario", scenario)
        binary.insert(1, "Excluded_Trades", excluded_text)
        parts.append(binary)
    return pd.concat(parts, ignore_index=True)


def summarize_symbol_status(joined: pd.DataFrame) -> pd.DataFrame:
    """Summarize every observed Symbol x RS_Status cell, including small cells."""

    _require_columns(joined, ["Symbol", "RS_Status"], "joined stock RS data")
    if not joined["RS_Status"].isin(ALLOWED_RS_STATUSES).all():
        raise ValueError("joined stock RS data contains an invalid RS_Status")
    rows = []
    for symbol in sorted(joined["Symbol"].unique()):
        symbol_frame = joined.loc[joined["Symbol"].eq(symbol)]
        for status in STATUS_ORDER:
            group = symbol_frame.loc[symbol_frame["RS_Status"].eq(status)]
            if group.empty:
                continue
            rows.append(
                {
                    "Symbol": symbol,
                    "RS_Status": status,
                    **calculate_trade_metrics(group),
                    "Small_Sample": len(group) < 5,
                }
            )
    return pd.DataFrame(
        rows,
        columns=["Symbol", "RS_Status", *METRIC_COLUMNS, "Small_Sample"],
    )


def summarize_leave_one_symbol_out(joined: pd.DataFrame) -> pd.DataFrame:
    """Recompute both primary tests after excluding each symbol in turn."""

    _require_columns(joined, ["Symbol"], "joined stock RS data")
    parts = []
    for symbol in sorted(joined["Symbol"].unique()):
        retained = joined.loc[~joined["Symbol"].eq(symbol)]
        binary = summarize_primary_binary_tests(retained)
        binary.insert(0, "Excluded_Symbol", symbol)
        parts.append(binary)
    if not parts:
        raise ValueError("joined stock RS data contains no symbols")
    return pd.concat(parts, ignore_index=True)


def load_and_validate_mapping(
    path: Path = STOCK_SECTOR_MAP_PATH,
) -> pd.DataFrame:
    """Load and enforce the fixed stock-to-sector mapping."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"stock-sector mapping is missing: {path}")
    mapping = pd.read_csv(path, dtype=str).fillna("")
    if mapping.columns.tolist() != ["Stock", "Sector_Key"]:
        raise ValueError("stock-sector mapping must contain Stock,Sector_Key")
    if len(mapping) != 20 or mapping["Stock"].duplicated().any():
        raise ValueError("stock-sector mapping must contain exactly 20 unique stocks")
    if dict(zip(mapping["Stock"], mapping["Sector_Key"])) != LOCKED_STOCK_SECTOR_MAP:
        raise ValueError("stock-sector mapping differs from the locked 20-stock mapping")
    return mapping


def load_and_validate_market_regime(
    path: Path = MARKET_REGIME_PATH,
) -> pd.DataFrame:
    """Load the existing market-regime output without recalculating it."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"market regime input is missing: {path}")
    market = pd.read_csv(path)
    _require_columns(market, ["Date", "Regime"], "market regime input")
    market = _parse_dates(market, ("Date",), "market regime input")
    if market["Regime"].isna().any() or not market["Regime"].isin(ALLOWED_MARKET_REGIMES).all():
        raise ValueError("market regime input contains an invalid Regime")
    if market["Date"].duplicated().any():
        raise ValueError("market regime input contains duplicate dates")
    return market.sort_values("Date").reset_index(drop=True)


def load_and_validate_sector_data(
    path: Path = SECTOR_RS_PATH,
) -> pd.DataFrame:
    """Load existing sector leadership rows for strict, full-universe matching."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"sector leadership input is missing: {path}")
    sector = pd.read_csv(path)
    required = [
        "Date",
        "Sector_Key",
        "Composite_RS",
        "Composite_Rank",
        "Sector_Count",
        "Leadership_Bucket",
    ]
    _require_columns(sector, required, "sector leadership input")
    sector = _parse_dates(sector, ("Date",), "sector leadership input")
    for column in ("Composite_RS", "Composite_Rank", "Sector_Count"):
        sector[column] = pd.to_numeric(sector[column], errors="coerce")
    if "Is_Full_Universe" in sector.columns:
        sector["Is_Full_Universe"] = _parse_full_universe_flag(
            sector["Is_Full_Universe"], "sector leadership input"
        )
    else:
        sector["Is_Full_Universe"] = sector["Sector_Count"].eq(11)
    if sector[required].isna().any().any() or sector["Is_Full_Universe"].isna().any():
        raise ValueError("sector leadership input contains null required values")
    _validate_finite_numeric(
        sector, ["Composite_RS", "Composite_Rank", "Sector_Count"], "sector leadership input"
    )
    if not sector["Leadership_Bucket"].isin(ALLOWED_SECTOR_BUCKETS).all():
        raise ValueError("sector leadership input contains an invalid Leadership_Bucket")
    if sector.duplicated(["Date", "Sector_Key"]).any():
        raise ValueError("sector leadership input contains duplicate (Date, Sector_Key) rows")
    if not sector["Is_Full_Universe"].eq(sector["Sector_Count"].eq(11)).all():
        raise ValueError("sector leadership input has an inconsistent full-universe flag")
    return sector.sort_values(["Date", "Sector_Key"]).reset_index(drop=True)


def join_market_regime_strictly_before_entry(
    trades: pd.DataFrame, market: pd.DataFrame
) -> pd.DataFrame:
    """Backward/as-of join market regime observations strictly before entry."""

    _require_columns(trades, ["Entry_Date"], "T1 trade data")
    _require_columns(market, ["Date", "Regime"], "market regime data")
    left = _parse_dates(trades, ("Entry_Date",), "T1 trade data").reset_index(drop=True)
    right = _parse_dates(market, ("Date",), "market regime data")
    if right["Date"].duplicated().any():
        raise ValueError("market regime data contains duplicate dates")
    left["_trade_order"] = np.arange(len(left))
    matched = pd.merge_asof(
        left.sort_values("Entry_Date"),
        right[["Date", "Regime"]].sort_values("Date"),
        left_on="Entry_Date",
        right_on="Date",
        direction="backward",
        allow_exact_matches=False,
    )
    matched = matched.rename(
        columns={"Date": "Market_Matched_Date", "Regime": "Market_Regime"}
    )
    matched["Market_Date_Lag_Days"] = (
        matched["Entry_Date"] - matched["Market_Matched_Date"]
    ).dt.days
    return (
        matched.sort_values("_trade_order")
        .drop(columns="_trade_order")
        .reset_index(drop=True)
    )


def join_sector_leadership_strictly_before_entry(
    trades: pd.DataFrame, sector: pd.DataFrame
) -> pd.DataFrame:
    """Backward/as-of join full-universe sector rows strictly before entry."""

    _require_columns(trades, ["Entry_Date", "Sector_Key"], "T1 trade data")
    _require_columns(
        sector,
        [
            "Date",
            "Sector_Key",
            "Composite_RS",
            "Composite_Rank",
            "Sector_Count",
            "Leadership_Bucket",
        ],
        "sector leadership data",
    )
    left = _parse_dates(trades, ("Entry_Date",), "T1 trade data").reset_index(drop=True)
    right = _parse_dates(sector, ("Date",), "sector leadership data")
    right = right.loc[
        right["Sector_Count"].eq(11) & right["Is_Full_Universe"].eq(True)
    ].copy()
    if right.empty:
        raise ValueError("sector leadership data has no full-universe rows")
    if right.duplicated(["Date", "Sector_Key"]).any():
        raise ValueError("sector leadership data contains duplicate (Date, Sector_Key) rows")
    left["_trade_order"] = np.arange(len(left))
    right_columns = {
        "Composite_RS": "Sector_Composite_RS",
        "Composite_Rank": "Sector_Composite_Rank",
        "Sector_Count": "Sector_Count",
        "Leadership_Bucket": "Leadership_Bucket",
    }
    pieces = []
    for sector_key, trade_group in left.groupby("Sector_Key", sort=False):
        ordered_trades = trade_group.sort_values("Entry_Date")
        feature_group = right.loc[
            right["Sector_Key"].eq(sector_key),
            ["Date", *right_columns.keys()],
        ].rename(columns=right_columns)
        feature_group = feature_group.sort_values("Date")
        if feature_group.empty:
            matched = ordered_trades.copy()
            matched["Sector_Matched_Date"] = pd.NaT
            for column in right_columns.values():
                matched[column] = np.nan
        else:
            matched = pd.merge_asof(
                ordered_trades,
                feature_group,
                left_on="Entry_Date",
                right_on="Date",
                direction="backward",
                allow_exact_matches=False,
            ).rename(columns={"Date": "Sector_Matched_Date"})
        pieces.append(matched)
    if not pieces:
        raise ValueError("no trade rows available for sector join")
    joined = (
        pd.concat(pieces, ignore_index=True)
        .sort_values("_trade_order")
        .reset_index(drop=True)
    )
    joined["Sector_Date_Lag_Days"] = (
        joined["Entry_Date"] - joined["Sector_Matched_Date"]
    ).dt.days
    return joined.drop(columns="_trade_order")


def validate_context_joins(
    joined: pd.DataFrame,
    expected_trade_count: int = 218,
) -> None:
    """Fail loudly when market and sector context violate strict timing invariants."""

    required = [
        "Entry_Date",
        "Market_Matched_Date",
        "Market_Date_Lag_Days",
        "Market_Regime",
        "Sector_Matched_Date",
        "Sector_Date_Lag_Days",
        "Sector_Count",
        "Leadership_Bucket",
    ]
    _require_columns(joined, required, "joined context data")
    if len(joined) != expected_trade_count:
        raise ValueError(
            f"joined context rows must equal {expected_trade_count}, found {len(joined)}"
        )
    if joined["Market_Matched_Date"].isna().any() or joined["Sector_Matched_Date"].isna().any():
        raise ValueError("joined context data contains unmatched trades")
    if (joined["Market_Matched_Date"] >= joined["Entry_Date"]).any():
        raise ValueError("market context includes a same-entry-day or future observation")
    if (joined["Sector_Matched_Date"] >= joined["Entry_Date"]).any():
        raise ValueError("sector context includes a same-entry-day or future observation")
    if (joined["Market_Date_Lag_Days"] <= 0).any() or (joined["Sector_Date_Lag_Days"] <= 0).any():
        raise ValueError("market and sector context lags must be strictly positive")
    if not joined["Market_Regime"].isin(ALLOWED_MARKET_REGIMES).all():
        raise ValueError("joined context data contains an invalid market regime")
    if not joined["Leadership_Bucket"].isin(ALLOWED_SECTOR_BUCKETS).all():
        raise ValueError("joined context data contains an invalid leadership bucket")
    if not joined["Sector_Count"].eq(11).all():
        raise ValueError("joined context data contains a non-full-universe sector match")


INTERACTION_COLUMNS = [
    "Analysis_Type",
    "Market_Regime",
    "Leadership_Bucket",
    "RS_Status",
    "Comparison",
    "Group",
    *METRIC_COLUMNS,
    "Small_Sample",
]


def summarize_market_interactions(joined: pd.DataFrame) -> pd.DataFrame:
    """Summarize stock-RS status and locked binary tests within each regime."""

    _require_columns(
        joined,
        ["Market_Regime", "RS_Status", "Return_Pct", "PnL", "Holding_Days"],
        "joined market interaction data",
    )
    if not joined["Market_Regime"].isin(ALLOWED_MARKET_REGIMES).all():
        raise ValueError("joined market interaction data contains an invalid regime")
    if not joined["RS_Status"].isin(ALLOWED_RS_STATUSES).all():
        raise ValueError("joined market interaction data contains an invalid RS_Status")
    rows = []
    for regime in MARKET_REGIME_ORDER:
        regime_frame = joined.loc[joined["Market_Regime"].eq(regime)]
        for status in STATUS_ORDER:
            group = regime_frame.loc[regime_frame["RS_Status"].eq(status)]
            rows.append(
                {
                    "Analysis_Type": "STATUS_MATRIX",
                    "Market_Regime": regime,
                    "Leadership_Bucket": "",
                    "RS_Status": status,
                    "Comparison": "",
                    "Group": status,
                    **calculate_trade_metrics(group),
                    "Small_Sample": len(group) < 5,
                }
            )
        binary = summarize_primary_binary_tests(regime_frame)
        for row in binary.to_dict(orient="records"):
            rows.append(
                {
                    "Analysis_Type": "BINARY_WITHIN_REGIME",
                    "Market_Regime": regime,
                    "Leadership_Bucket": "",
                    "RS_Status": "",
                    "Comparison": row["Comparison"],
                    "Group": row["Group"],
                    **{column: row[column] for column in METRIC_COLUMNS},
                    "Small_Sample": row["Trades"] < 5,
                }
            )
    return pd.DataFrame(rows, columns=INTERACTION_COLUMNS)


def summarize_sector_interactions(joined: pd.DataFrame) -> pd.DataFrame:
    """Summarize stock-RS status and locked binary tests within each sector bucket."""

    _require_columns(
        joined,
        ["Leadership_Bucket", "RS_Status", "Return_Pct", "PnL", "Holding_Days"],
        "joined sector interaction data",
    )
    if not joined["Leadership_Bucket"].isin(ALLOWED_SECTOR_BUCKETS).all():
        raise ValueError("joined sector interaction data contains an invalid bucket")
    if not joined["RS_Status"].isin(ALLOWED_RS_STATUSES).all():
        raise ValueError("joined sector interaction data contains an invalid RS_Status")
    rows = []
    for bucket in SECTOR_BUCKET_ORDER:
        bucket_frame = joined.loc[joined["Leadership_Bucket"].eq(bucket)]
        for status in STATUS_ORDER:
            group = bucket_frame.loc[bucket_frame["RS_Status"].eq(status)]
            rows.append(
                {
                    "Analysis_Type": "STATUS_MATRIX",
                    "Market_Regime": "",
                    "Leadership_Bucket": bucket,
                    "RS_Status": status,
                    "Comparison": "",
                    "Group": status,
                    **calculate_trade_metrics(group),
                    "Small_Sample": len(group) < 5,
                }
            )
        binary = summarize_primary_binary_tests(bucket_frame)
        for row in binary.to_dict(orient="records"):
            rows.append(
                {
                    "Analysis_Type": "BINARY_WITHIN_SECTOR_BUCKET",
                    "Market_Regime": "",
                    "Leadership_Bucket": bucket,
                    "RS_Status": "",
                    "Comparison": row["Comparison"],
                    "Group": row["Group"],
                    **{column: row[column] for column in METRIC_COLUMNS},
                    "Small_Sample": row["Trades"] < 5,
                }
            )
    return pd.DataFrame(rows, columns=INTERACTION_COLUMNS)


def prepare_joined_trade_export(joined: pd.DataFrame) -> pd.DataFrame:
    """Select and deterministically sort the auditable trade-level export."""

    _require_columns(joined, JOINED_TRADE_COLUMNS, "joined stock RS data")
    export_columns = [
        *JOINED_TRADE_COLUMNS,
        *[column for column in CONTEXT_EXPORT_COLUMNS if column in joined.columns],
    ]
    return (
        joined[export_columns]
        .sort_values(["Entry_Date", "Symbol", "Exit_Date"])
        .reset_index(drop=True)
    )


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    output = frame.copy()
    for column in output.columns:
        if pd.api.types.is_datetime64_any_dtype(output[column]):
            output[column] = output[column].dt.strftime("%Y-%m-%d")
    output.to_csv(path, index=False, lineterminator="\n")


def _format_report_value(value: object, digits: int = 4) -> str:
    if value is None or pd.isna(value):
        return "NA"
    if isinstance(value, (float, np.floating)) and math.isinf(float(value)):
        return "inf"
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{digits}f}"
    return str(value)


def _format_date_value(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _reconciles(
    frame: pd.DataFrame,
    count: int = 218,
    total_pnl: float = -4631.32,
) -> tuple[bool, bool]:
    return (
        int(frame["Trades"].sum()) == count,
        math.isclose(float(frame["Total_PnL"].sum()), total_pnl, abs_tol=0.01),
    )


def build_validation_report(
    trades: pd.DataFrame,
    stock_joined: pd.DataFrame,
    contextual: pd.DataFrame,
    status: pd.DataFrame,
    binary: pd.DataFrame,
) -> pd.DataFrame:
    """Build key/value audit rows after all strict joins and reconciliations pass."""

    status_count, status_pnl = _reconciles(status)
    preferred = binary.loc[binary["Comparison"].eq("PREFERRED_TEST")]
    valid_or_better = binary.loc[binary["Comparison"].eq("VALID_OR_BETTER_TEST")]
    preferred_count, preferred_pnl = _reconciles(preferred)
    valid_count, valid_pnl = _reconciles(valid_or_better)
    rs_matched = stock_joined["RS_Matched_Date"]
    entry_dates = stock_joined["Entry_Date"]
    market_matched = contextual["Market_Matched_Date"]
    sector_matched = contextual["Sector_Matched_Date"]
    rows = [
        ("Input_Trade_Count", len(trades)),
        ("Unique_Symbols", trades["Symbol"].nunique()),
        ("Winners", int((trades["Return_Pct"] > 0).sum())),
        ("Input_Total_PnL", round(float(trades["PnL"].sum()), 2)),
        ("Unmatched_RS_Trades", int(rs_matched.isna().sum())),
        ("Same_Day_RS_Matches", int((rs_matched == entry_dates).sum())),
        ("Future_RS_Matches", int((rs_matched > entry_dates).sum())),
        (
            "NonFullUniverse_RS_Matches",
            int((~stock_joined["Stock_Count"].eq(20) | ~stock_joined["Is_Full_Universe"]).sum()),
        ),
        ("Median_RS_Lag_Days", float(stock_joined["RS_Date_Lag_Days"].median())),
        ("Max_RS_Lag_Days", int(stock_joined["RS_Date_Lag_Days"].max())),
        ("RS_Lag_Over_7_Days_Count", int((stock_joined["RS_Date_Lag_Days"] > 7).sum())),
        ("Primary_Status_Count_Reconciles", status_count),
        ("Primary_Status_PnL_Reconciles", status_pnl),
        ("Preferred_Test_Count_Reconciles", preferred_count),
        ("Preferred_Test_PnL_Reconciles", preferred_pnl),
        ("ValidOrBetter_Test_Count_Reconciles", valid_count),
        ("ValidOrBetter_Test_PnL_Reconciles", valid_pnl),
        ("Same_Day_Market_Matches", int((market_matched == contextual["Entry_Date"]).sum())),
        ("Future_Market_Matches", int((market_matched > contextual["Entry_Date"]).sum())),
        ("Same_Day_Sector_Matches", int((sector_matched == contextual["Entry_Date"]).sum())),
        ("Future_Sector_Matches", int((sector_matched > contextual["Entry_Date"]).sum())),
        (
            "NonFullUniverse_Sector_Matches",
            int((~contextual["Sector_Count"].eq(11)).sum()),
        ),
        ("RS_Matched_Date_Min", _format_date_value(rs_matched.min())),
        ("RS_Matched_Date_Max", _format_date_value(rs_matched.max())),
        ("Market_Matched_Date_Min", _format_date_value(market_matched.min())),
        ("Market_Matched_Date_Max", _format_date_value(market_matched.max())),
        ("Sector_Matched_Date_Min", _format_date_value(sector_matched.min())),
        ("Sector_Matched_Date_Max", _format_date_value(sector_matched.max())),
    ]
    return pd.DataFrame(rows, columns=["Check", "Value"])


def _binary_difference(binary: pd.DataFrame, comparison: str) -> float:
    frame = binary.loc[binary["Comparison"].eq(comparison)].set_index("Group")
    first, second = [group for name, groups in PRIMARY_BINARY_SPECS if name == comparison for group, _ in groups]
    first_value = frame.loc[first, "Mean_Return"]
    second_value = frame.loc[second, "Mean_Return"]
    if pd.isna(first_value) or pd.isna(second_value):
        return math.nan
    return float(first_value - second_value)


def _direction(value: float) -> str:
    if math.isnan(value):
        return "unavailable"
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "flat"


def _leave_one_differences(leave_one: pd.DataFrame, comparison: str) -> pd.Series:
    frame = leave_one.loc[leave_one["Comparison"].eq(comparison)]
    first, second = [group for name, groups in PRIMARY_BINARY_SPECS if name == comparison for group, _ in groups]
    pivot = frame.pivot(index="Excluded_Symbol", columns="Group", values="Mean_Return")
    if first not in pivot or second not in pivot:
        return pd.Series(dtype=float)
    result = pivot[first] - pivot[second]
    return result.dropna()


def build_research_report(
    joined: pd.DataFrame,
    status: pd.DataFrame,
    binary: pd.DataFrame,
    rank: pd.DataFrame,
    years: pd.DataFrame,
    outliers: pd.DataFrame,
    leave_one: pd.DataFrame,
    market_matrix: pd.DataFrame,
    sector_matrix: pd.DataFrame,
    validation: pd.DataFrame,
) -> str:
    """Render an evidence-only report from the already-calculated output frames."""

    baseline = calculate_trade_metrics(joined)
    status_lines = [
        f"- {row.RS_Status}: {int(row.Trades)} trades, mean return {_format_report_value(row.Mean_Return)}, total P&L {_format_report_value(row.Total_PnL, 2)}."
        for row in status.itertuples()
    ]
    binary_lines = []
    for comparison, groups in PRIMARY_BINARY_SPECS:
        part = binary.loc[binary["Comparison"].eq(comparison)]
        descriptions = []
        for group, _ in groups:
            row = part.loc[part["Group"].eq(group)].iloc[0]
            descriptions.append(
                f"{group}: {int(row.Trades)} trades, mean return {_format_report_value(row.Mean_Return)}, total P&L {_format_report_value(row.Total_PnL, 2)}"
            )
        binary_lines.append(f"- {comparison}: " + "; ".join(descriptions) + ".")
    year_lines = []
    for year in (2023, 2024, 2025, 2026):
        year_part = years.loc[years["Entry_Year"].eq(year)]
        year_lines.append(
            f"- {year}: "
            + "; ".join(
                f"{row.Comparison} {row.Group} mean return {_format_report_value(row.Mean_Return)}"
                for row in year_part.itertuples()
            )
            + "."
        )
    outlier_lines = []
    all_directions = {
        comparison: _direction(_binary_difference(binary, comparison))
        for comparison, _ in PRIMARY_BINARY_SPECS
    }
    for scenario in [
        "ALL_TRADES",
        "EXCLUDE_TOP_1_POSITIVE_PNL",
        "EXCLUDE_TOP_3_POSITIVE_PNL",
        "EXCLUDE_TOP_5_POSITIVE_PNL",
    ]:
        part = outliers.loc[outliers["Scenario"].eq(scenario)]
        excluded = part["Excluded_Trades"].iloc[0] or "none"
        direction_text = "; ".join(
            f"{comparison} direction {_direction(_binary_difference(part, comparison))} (ALL_TRADES was {all_directions[comparison]})"
            for comparison, _ in PRIMARY_BINARY_SPECS
        )
        outlier_lines.append(f"- {scenario}: excluded {excluded}; {direction_text}.")
    leave_lines = []
    for comparison, _ in PRIMARY_BINARY_SPECS:
        differences = _leave_one_differences(leave_one, comparison)
        if differences.empty:
            leave_lines.append(f"- {comparison}: no complete leave-one-symbol differences were available.")
        else:
            leave_lines.append(
                f"- {comparison}: group mean-return difference range across {len(differences)} exclusions was {_format_report_value(differences.min())} to {_format_report_value(differences.max())}."
            )
    validation_lookup = dict(zip(validation["Check"], validation["Value"]))
    return f"""# T1 Stock Relative-Strength Validation

## Methodology

This is a fixed-sample validation experiment, not optimization. It joins the immutable 218 completed T1 breakout trades to the merged Issue #5 / PR #6 stock-RS dataset. The locked feature uses 21-, 63-, and 126-session returns, 30/40/30 percentile weights, rank 1 as strongest, and the unchanged PREFERRED, VALID, and BELOW_VALID status bands.

## Decision-Time Integrity

T1's Streak daily entry is next-candle-open after an EOD signal, so this validation uses only feature/context observations strictly before Entry_Date. Same-entry-day daily RS/market/sector closes are not decision-time-safe for this experiment.

The stock-RS join had {validation_lookup['Unmatched_RS_Trades']} unmatched trades and used backward/as-of observations with no same-day or future matches. Median RS lag was {_format_report_value(validation_lookup['Median_RS_Lag_Days'], 1)} calendar days and maximum lag was {validation_lookup['Max_RS_Lag_Days']} days. Market and sector interactions use the same strict-before-entry rule and are independent of the earlier same-day sector join.

## Unfiltered T1 Baseline

The unfiltered joined sample contains {int(baseline['Trades'])} trades, {int(baseline['Winners'])} winners, mean return {_format_report_value(baseline['Mean_Return'])}, median return {_format_report_value(baseline['Median_Return'])}, and total P&L {_format_report_value(baseline['Total_PnL'], 2)}. Median holding time was {_format_report_value(baseline['Median_Holding_Days'], 1)} days.

## RS Status Results

{chr(10).join(status_lines)}

## Primary Binary Comparisons

{chr(10).join(binary_lines)}

These are the only two primary binary comparisons. No additional rank cutoff or combined buy rule is inferred here.

## Rank Diagnostics

Diagnostic metrics for every Composite_Rank from 1 through 20 are in `output/t1_stock_rs_rank_summary.csv`. Ranks are retained separately and are not converted into an optimized cutoff.

## Year Stability

{chr(10).join(year_lines)}

## Outlier Robustness

The largest positive-P&L trades were removed globally only for the declared sensitivity scenarios; losing trades were not removed.

{chr(10).join(outlier_lines)}

## Stock-Identity Robustness

Symbol-by-status metrics are in `output/t1_stock_rs_symbol_summary.csv`; cells with fewer than five trades are flagged. Leave-one-symbol-out differences are summarized below, with all fixed-basket symbols retained:

{chr(10).join(leave_lines)}

## Market-Regime Interaction

The secondary market-regime matrix is in `output/t1_stock_rs_market_matrix.csv`. It contains a full Market_Regime x RS_Status status matrix and both locked binary comparisons within each regime. These diagnostics do not redefine the primary stock-RS analysis.

## Sector-Leadership Interaction

The secondary sector matrix is in `output/t1_stock_rs_sector_matrix.csv`. It contains a full Leadership_Bucket x RS_Status status matrix and both locked binary comparisons within each sector bucket. Sector rows use the existing definitions and full-universe observations only.

## Data / Method Limitations

- The T1 sample is a fixed 218-trade, 20-symbol sample and is not regenerated here.
- Stock RS is an observational feature joined as-of by calendar date; a calendar lag over seven days is reported for audit rather than silently filled.
- Small cells and stock identity can make subgroup metrics unstable.
- Interaction tables are secondary diagnostics and do not establish causality or authorize new filters.

## Evidence Summary

The generated CSVs and validation report provide the predeclared factual comparisons, timing checks, and robustness evidence for the Portfolio Advisor's separate decision gate. This report does not adopt a threshold, change T1 rules, or make the final strategy decision.
"""


EXPECTED_OUTPUT_FILENAMES = [
    "t1_stock_rs_joined_trades.csv",
    "t1_stock_rs_status_summary.csv",
    "t1_stock_rs_binary_tests.csv",
    "t1_stock_rs_rank_summary.csv",
    "t1_stock_rs_year_summary.csv",
    "t1_stock_rs_outlier_robustness.csv",
    "t1_stock_rs_symbol_summary.csv",
    "t1_stock_rs_leave_one_symbol_out.csv",
    "t1_stock_rs_market_matrix.csv",
    "t1_stock_rs_sector_matrix.csv",
    "validation_report.csv",
    "research_report.md",
]


def validate_complete_outputs(
    trades: pd.DataFrame,
    stock_joined: pd.DataFrame,
    contextual: pd.DataFrame,
    status: pd.DataFrame,
    binary: pd.DataFrame,
    rank: pd.DataFrame,
    years: pd.DataFrame,
    outliers: pd.DataFrame,
    symbols: pd.DataFrame,
    leave_one: pd.DataFrame,
    market_matrix: pd.DataFrame,
    sector_matrix: pd.DataFrame,
) -> None:
    """Validate every in-memory result before any final output is written."""

    validate_stock_rs_join(stock_joined)
    validate_context_joins(contextual)
    if _reconciles(status) != (True, True):
        raise ValueError("status summary failed locked count/PnL reconciliation")
    for comparison in ("PREFERRED_TEST", "VALID_OR_BETTER_TEST"):
        part = binary.loc[binary["Comparison"].eq(comparison)]
        if len(part) != 2 or _reconciles(part) != (True, True):
            raise ValueError(f"{comparison} failed locked count/PnL reconciliation")
    if rank["Composite_Rank"].tolist() != list(range(1, 21)):
        raise ValueError("rank summary does not contain exact ranks 1..20")
    if int(rank["Trades"].sum()) != len(trades):
        raise ValueError("rank summary trade count does not reconcile")
    if set(years["Entry_Year"]) != {2023, 2024, 2025, 2026}:
        raise ValueError("year summary contains an unexpected entry year")
    for year in (2023, 2024, 2025, 2026):
        expected = int(stock_joined["Entry_Date"].dt.year.eq(year).sum())
        for comparison in ("PREFERRED_TEST", "VALID_OR_BETTER_TEST"):
            part = years.loc[
                years["Entry_Year"].eq(year) & years["Comparison"].eq(comparison)
            ]
            if len(part) != 2 or int(part["Trades"].sum()) != expected:
                raise ValueError(f"year summary failed reconciliation for {year}/{comparison}")
    if outliers["Scenario"].drop_duplicates().tolist() != [
        "ALL_TRADES",
        "EXCLUDE_TOP_1_POSITIVE_PNL",
        "EXCLUDE_TOP_3_POSITIVE_PNL",
        "EXCLUDE_TOP_5_POSITIVE_PNL",
    ]:
        raise ValueError("outlier summary contains an unexpected scenario")
    if set(symbols["Symbol"]) != set(trades["Symbol"]):
        raise ValueError("symbol summary does not cover the locked T1 symbols")
    if set(leave_one["Excluded_Symbol"]) != set(trades["Symbol"]):
        raise ValueError("leave-one-symbol-out summary does not cover the locked T1 symbols")
    if set(market_matrix["Analysis_Type"]) != {
        "STATUS_MATRIX",
        "BINARY_WITHIN_REGIME",
    }:
        raise ValueError("market interaction output sections are incomplete")
    if set(sector_matrix["Analysis_Type"]) != {
        "STATUS_MATRIX",
        "BINARY_WITHIN_SECTOR_BUCKET",
    }:
        raise ValueError("sector interaction output sections are incomplete")


def run_analysis() -> dict[str, object]:
    """Run the complete locked validation and publish outputs after validation."""

    trades = load_and_validate_trades()
    rs = load_and_validate_stock_rs()
    stock_joined = join_stock_rs_at_decision_time(trades, rs)
    status = summarize_status_groups(stock_joined)
    binary = summarize_primary_binary_tests(stock_joined)
    rank = summarize_composite_ranks(stock_joined)
    years = summarize_by_entry_year(stock_joined)
    outliers = summarize_outlier_robustness(stock_joined)
    symbols = summarize_symbol_status(stock_joined)
    leave_one = summarize_leave_one_symbol_out(stock_joined)

    mapping = load_and_validate_mapping()
    contextual = stock_joined.merge(
        mapping.rename(columns={"Stock": "Symbol"}),
        on="Symbol",
        how="left",
        validate="many_to_one",
    )
    if contextual["Sector_Key"].isna().any():
        raise ValueError("some T1 trades have no stock-sector mapping")
    market = load_and_validate_market_regime()
    sector = load_and_validate_sector_data()
    contextual = join_market_regime_strictly_before_entry(contextual, market)
    contextual = join_sector_leadership_strictly_before_entry(contextual, sector)
    market_matrix = summarize_market_interactions(contextual)
    sector_matrix = summarize_sector_interactions(contextual)

    validate_complete_outputs(
        trades,
        stock_joined,
        contextual,
        status,
        binary,
        rank,
        years,
        outliers,
        symbols,
        leave_one,
        market_matrix,
        sector_matrix,
    )
    validation = build_validation_report(
        trades, stock_joined, contextual, status, binary
    )
    report = build_research_report(
        stock_joined,
        status,
        binary,
        rank,
        years,
        outliers,
        leave_one,
        market_matrix,
        sector_matrix,
        validation,
    )

    output_frames = [
        ("t1_stock_rs_joined_trades.csv", prepare_joined_trade_export(contextual)),
        ("t1_stock_rs_status_summary.csv", status),
        ("t1_stock_rs_binary_tests.csv", binary),
        ("t1_stock_rs_rank_summary.csv", rank),
        ("t1_stock_rs_year_summary.csv", years),
        ("t1_stock_rs_outlier_robustness.csv", outliers),
        ("t1_stock_rs_symbol_summary.csv", symbols),
        ("t1_stock_rs_leave_one_symbol_out.csv", leave_one),
        ("t1_stock_rs_market_matrix.csv", market_matrix),
        ("t1_stock_rs_sector_matrix.csv", sector_matrix),
        ("validation_report.csv", validation),
    ]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, frame in output_frames:
        _write_csv(frame, OUTPUT_DIR / filename)
    (OUTPUT_DIR / "research_report.md").write_text(report, encoding="utf-8")
    print(f"Validated {len(trades)} trades across {trades['Symbol'].nunique()} symbols")
    print(f"Stock-RS lag days: median={stock_joined['RS_Date_Lag_Days'].median():.1f}, max={stock_joined['RS_Date_Lag_Days'].max():.0f}")
    print(f"Generated {len(EXPECTED_OUTPUT_FILENAMES)} outputs under {OUTPUT_DIR}")
    return {
        "trades": trades,
        "joined": stock_joined,
        "contextual": contextual,
        "status": status,
        "binary": binary,
        "rank": rank,
        "years": years,
        "outliers": outliers,
        "symbols": symbols,
        "leave_one": leave_one,
        "market_matrix": market_matrix,
        "sector_matrix": sector_matrix,
        "validation": validation,
        "report": report,
    }


if __name__ == "__main__":
    run_analysis()
