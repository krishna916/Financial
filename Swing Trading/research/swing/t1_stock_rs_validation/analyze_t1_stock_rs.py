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


def prepare_joined_trade_export(joined: pd.DataFrame) -> pd.DataFrame:
    """Select and deterministically sort the auditable trade-level export."""

    _require_columns(joined, JOINED_TRADE_COLUMNS, "joined stock RS data")
    return (
        joined[JOINED_TRADE_COLUMNS]
        .sort_values(["Entry_Date", "Symbol", "Exit_Date"])
        .reset_index(drop=True)
    )


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    output = frame.copy()
    for column in output.columns:
        if pd.api.types.is_datetime64_any_dtype(output[column]):
            output[column] = output[column].dt.strftime("%Y-%m-%d")
    output.to_csv(path, index=False, lineterminator="\n")


def run_analysis() -> dict[str, pd.DataFrame]:
    """Run the currently implemented primary validation outputs."""

    trades = load_and_validate_trades()
    rs = load_and_validate_stock_rs()
    joined = join_stock_rs_at_decision_time(trades, rs)
    validate_stock_rs_join(joined)
    joined_export = prepare_joined_trade_export(joined)
    status = summarize_status_groups(joined)
    binary = summarize_primary_binary_tests(joined)
    rank = summarize_composite_ranks(joined)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(joined_export, OUTPUT_DIR / "t1_stock_rs_joined_trades.csv")
    _write_csv(status, OUTPUT_DIR / "t1_stock_rs_status_summary.csv")
    _write_csv(binary, OUTPUT_DIR / "t1_stock_rs_binary_tests.csv")
    _write_csv(rank, OUTPUT_DIR / "t1_stock_rs_rank_summary.csv")
    return {"joined": joined, "status": status, "binary": binary, "rank": rank}


if __name__ == "__main__":
    run_analysis()
