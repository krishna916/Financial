"""Validate the fixed T1 trade sample against point-in-time sector leadership."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / "input" / "t1_trades.csv"
PAYLOAD_PATH = BASE_DIR / "input" / "t1_trades.csv.gz.b64"
SECTOR_PATH = BASE_DIR.parent / "sector_leadership" / "output" / "sector_leadership_daily.csv"
MAPPING_PATH = BASE_DIR.parent / "sector_leadership" / "stock_sector_map.csv"
REGIME_PATH = BASE_DIR.parents[2] / "nifty500_regime_daily.csv"
OUTPUT_DIR = BASE_DIR / "output"

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
ALLOWED_BUCKETS = ("LEADING", "ACCEPTABLE", "WEAK", "LAGGING")
ALLOWED_REGIMES = ("RISK_ON", "MIXED", "RISK_OFF")
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


def _require_columns(df: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def _parse_dates(df: pd.DataFrame, columns: Iterable[str], label: str) -> pd.DataFrame:
    result = df.copy()
    for column in columns:
        result[column] = pd.to_datetime(result[column], errors="coerce")
        if result[column].isna().any():
            raise ValueError(f"{label} has invalid or missing {column} values")
    return result


def load_and_validate_trades(path: Path = INPUT_PATH) -> pd.DataFrame:
    """Load the immutable normalized T1 input and enforce its locked invariants."""

    if not path.exists():
        raise FileNotFoundError(f"fixed T1 input is missing: {path}")
    trades = pd.read_csv(path)
    if trades.columns.tolist() != EXPECTED_TRADE_COLUMNS:
        raise ValueError(
            f"T1 input columns must be {EXPECTED_TRADE_COLUMNS}, "
            f"received {trades.columns.tolist()}"
        )
    trades = _parse_dates(trades, ("Entry_Date", "Exit_Date"), "T1 input")
    for column in ("Entry_Price", "Exit_Price", "Qty", "Return_Pct", "PnL", "Holding_Days"):
        trades[column] = pd.to_numeric(trades[column], errors="coerce")
    if trades[EXPECTED_TRADE_COLUMNS].isna().any().any():
        raise ValueError("T1 input contains null required fields")
    if len(trades) != 218:
        raise ValueError(f"T1 input must contain 218 trades, found {len(trades)}")
    symbols = set(trades["Symbol"])
    if symbols != set(LOCKED_STOCK_SECTOR_MAP):
        raise ValueError("T1 input symbols do not match the locked 20-stock basket")
    if (trades["Entry_Date"] > trades["Exit_Date"]).any():
        raise ValueError("T1 input contains Entry_Date after Exit_Date")
    if (trades["Qty"] <= 0).any():
        raise ValueError("T1 input contains non-positive Qty")
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
    if (trades["Return_Pct"] > 0).sum() != 76:
        raise ValueError("T1 input winner count is not 76")
    if not math.isclose(float(trades["PnL"].sum()), -4631.32, abs_tol=0.01):
        raise ValueError("T1 input total PnL does not equal -4631.32")
    if not math.isclose(float(trades["Return_Pct"].mean()), -0.0548680341, abs_tol=1e-8):
        raise ValueError("T1 input mean Return_Pct does not match the locked aggregate")
    return trades


def load_and_validate_mapping(path: Path = MAPPING_PATH) -> pd.DataFrame:
    """Load and verify the precommitted stock-to-sector proxy mapping."""

    mapping = pd.read_csv(path, dtype=str).fillna("")
    if mapping.columns.tolist() != ["Stock", "Sector_Key"]:
        raise ValueError("stock-sector mapping must contain Stock,Sector_Key")
    if mapping["Stock"].duplicated().any():
        raise ValueError("stock-sector mapping contains duplicate stocks")
    observed = dict(zip(mapping["Stock"], mapping["Sector_Key"]))
    if observed != LOCKED_STOCK_SECTOR_MAP:
        raise ValueError("stock-sector mapping differs from the locked 20-stock mapping")
    return mapping


def load_and_validate_sector_data(path: Path = SECTOR_PATH) -> pd.DataFrame:
    """Load the Issue #1 sector output without changing its methodology."""

    required = [
        "Date",
        "Sector_Key",
        "Composite_RS",
        "Composite_Rank",
        "Sector_Count",
        "Leadership_Bucket",
    ]
    sector = pd.read_csv(path)
    _require_columns(sector, required, "sector leadership output")
    sector = _parse_dates(sector, ("Date",), "sector leadership output")
    for column in ("Composite_RS", "Composite_Rank", "Sector_Count"):
        sector[column] = pd.to_numeric(sector[column], errors="coerce")
    if sector[required].isna().any().any():
        raise ValueError("sector leadership output has null required values")
    if not set(sector["Leadership_Bucket"]).issubset(ALLOWED_BUCKETS):
        raise ValueError("sector leadership output contains an invalid bucket")
    if sector.duplicated(["Date", "Sector_Key"]).any():
        raise ValueError("sector leadership output contains duplicate date-sector rows")
    if "Is_Full_Universe" in sector.columns:
        flag = sector["Is_Full_Universe"]
        if flag.dtype == object:
            flag = flag.astype(str).str.strip().str.lower().map({"true": True, "false": False})
        if flag.isna().any() or not flag.eq(sector["Sector_Count"].eq(11)).all():
            raise ValueError("Is_Full_Universe is inconsistent with Sector_Count == 11")
        sector["Is_Full_Universe"] = flag.astype(bool)
    return sector


def prepare_full_universe_sector_data(
    sector: pd.DataFrame, expected_sector_count: int = 11
) -> pd.DataFrame:
    """Return only complete comparison-universe observations."""

    _require_columns(
        sector,
        ["Date", "Sector_Key", "Composite_RS", "Composite_Rank", "Sector_Count", "Leadership_Bucket"],
        "sector leadership data",
    )
    result = sector.copy()
    if "Is_Full_Universe" in result.columns:
        if not result["Is_Full_Universe"].eq(result["Sector_Count"].eq(expected_sector_count)).all():
            raise ValueError("sector full-universe flag does not match Sector_Count")
    result = result.loc[result["Sector_Count"].eq(expected_sector_count)].copy()
    if result.empty:
        raise ValueError("sector leadership output has no full-universe observations")
    return result.sort_values(["Sector_Key", "Date"]).reset_index(drop=True)


def asof_join_sector_leadership(
    trades: pd.DataFrame, sector: pd.DataFrame
) -> pd.DataFrame:
    """Backward/as-of join sector features to each trade entry."""

    _require_columns(trades, ["Symbol", "Entry_Date", "Sector_Key"], "trade data")
    _require_columns(
        sector,
        ["Date", "Sector_Key", "Composite_RS", "Composite_Rank", "Sector_Count", "Leadership_Bucket"],
        "sector data",
    )
    if not sector["Sector_Count"].eq(11).all():
        raise ValueError("as-of sector input contains non-full-universe rows")
    left = trades.copy().reset_index(drop=True)
    right = sector.copy()
    left["Entry_Date"] = pd.to_datetime(left["Entry_Date"], errors="coerce")
    right["Date"] = pd.to_datetime(right["Date"], errors="coerce")
    left["_trade_order"] = np.arange(len(left))
    feature_columns = [
        "Date",
        "Sector_Key",
        "Composite_RS",
        "Composite_Rank",
        "Sector_Count",
        "Leadership_Bucket",
    ]
    if "Is_Full_Universe" in right.columns:
        feature_columns.append("Is_Full_Universe")
    pieces = []
    for sector_key, trade_group in left.groupby("Sector_Key", sort=False):
        feature_group = right.loc[right["Sector_Key"].eq(sector_key), feature_columns]
        matched = pd.merge_asof(
            trade_group.sort_values("Entry_Date"),
            feature_group.sort_values("Date"),
            left_on="Entry_Date",
            right_on="Date",
            by="Sector_Key",
            direction="backward",
            allow_exact_matches=True,
        )
        pieces.append(matched)
    if not pieces:
        raise ValueError("no trade rows available for sector join")
    joined = pd.concat(pieces, ignore_index=True).sort_values("_trade_order").reset_index(drop=True)
    joined = joined.rename(columns={"Date": "Sector_Matched_Date"})
    unmatched = int(joined["Sector_Matched_Date"].isna().sum())
    if unmatched:
        raise ValueError(f"{unmatched} trades could not be matched to a prior full-universe sector row")
    joined["Sector_Date_Lag_Days"] = (
        joined["Entry_Date"] - joined["Sector_Matched_Date"]
    ).dt.days
    if (joined["Sector_Matched_Date"] > joined["Entry_Date"]).any():
        raise ValueError("sector as-of join used a future observation")
    if (joined["Sector_Date_Lag_Days"] < 0).any():
        raise ValueError("sector date lag is negative")
    if not joined["Sector_Count"].eq(11).all():
        raise ValueError("sector as-of join contains a non-full-universe match")
    return joined.drop(columns="_trade_order")


def calculate_profit_factor(values: pd.Series) -> float:
    """Calculate positive-sum divided by absolute negative-sum."""

    numeric = pd.to_numeric(values, errors="coerce").dropna()
    positive = float(numeric.loc[numeric > 0].sum())
    negative = float(numeric.loc[numeric < 0].sum())
    if negative == 0:
        return math.inf if positive > 0 else math.nan
    if positive == 0:
        return 0.0
    return positive / abs(negative)


def _payoff_ratio(average_winner: float, average_loser: float) -> float:
    if math.isnan(average_loser):
        return math.inf if not math.isnan(average_winner) else math.nan
    if average_loser == 0:
        return math.nan
    if math.isnan(average_winner):
        return 0.0
    return average_winner / abs(average_loser)


def calculate_trade_metrics(trades: pd.DataFrame) -> dict[str, float | int]:
    """Return the predeclared return, PnL, and holding-period metrics."""

    _require_columns(trades, ["Return_Pct", "PnL", "Holding_Days"], "trade data")
    count = len(trades)
    returns = pd.to_numeric(trades["Return_Pct"], errors="coerce")
    pnl = pd.to_numeric(trades["PnL"], errors="coerce")
    holding = pd.to_numeric(trades["Holding_Days"], errors="coerce")
    winners = returns.loc[returns > 0]
    losers = returns.loc[returns < 0]
    average_winner = float(winners.mean()) if not winners.empty else math.nan
    average_loser = float(losers.mean()) if not losers.empty else math.nan
    return {
        "Trades": count,
        "Winners": int(len(winners)),
        "Losers": int(len(losers)),
        "Win_Rate": float(len(winners) / count) if count else math.nan,
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


def classify_binary_groups(trades: pd.DataFrame) -> pd.DataFrame:
    """Add exactly the three binary comparisons declared by the issue."""

    _require_columns(trades, ["Leadership_Bucket"], "joined trade data")
    if not set(trades["Leadership_Bucket"]).issubset(ALLOWED_BUCKETS):
        raise ValueError("joined trades contain an invalid leadership bucket")
    result = trades.copy()
    result["Leading_Group"] = np.where(
        result["Leadership_Bucket"].eq("LEADING"), "LEADING", "NON_LEADING"
    )
    result["Top_Half_Group"] = np.where(
        result["Leadership_Bucket"].isin(["LEADING", "ACCEPTABLE"]),
        "TOP_HALF",
        "LOWER_HALF",
    )
    result["Lagging_Group"] = np.where(
        result["Leadership_Bucket"].eq("LAGGING"), "LAGGING", "NON_LAGGING"
    )
    return result


def _summary_rows(
    frame: pd.DataFrame,
    group_column: str,
    fixed: dict[str, object] | None = None,
    ordered_values: Iterable[object] | None = None,
) -> pd.DataFrame:
    fixed = fixed or {}
    groups = {value: group for value, group in frame.groupby(group_column, sort=False)}
    values = list(ordered_values) if ordered_values is not None else list(groups)
    rows = []
    for value in values:
        metrics = calculate_trade_metrics(groups[value]) if value in groups else calculate_trade_metrics(frame.iloc[0:0])
        rows.append({**fixed, group_column: value, **metrics})
    return pd.DataFrame(rows)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, date_format="%Y-%m-%d")


def _fmt(value: object, digits: int = 4) -> str:
    if pd.isna(value):
        return "NA"
    if isinstance(value, (float, np.floating)) and math.isinf(float(value)):
        return "inf"
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{digits}f}"
    return str(value)


def load_and_validate_regime_data(path: Path = REGIME_PATH) -> pd.DataFrame:
    regime = pd.read_csv(path)
    _require_columns(regime, ["Date", "Regime"], "market regime output")
    regime = _parse_dates(regime, ("Date",), "market regime output")
    if not set(regime["Regime"]).issubset(ALLOWED_REGIMES):
        raise ValueError("market regime output contains an invalid regime")
    if regime["Date"].duplicated().any():
        raise ValueError("market regime output contains duplicate dates")
    return regime.sort_values("Date").reset_index(drop=True)


def asof_join_market_regime(trades: pd.DataFrame, regime: pd.DataFrame) -> pd.DataFrame:
    left = trades.copy().reset_index(drop=True)
    left["_trade_order"] = np.arange(len(left))
    left = left.sort_values("Entry_Date")
    matched = pd.merge_asof(
        left,
        regime[["Date", "Regime"]].sort_values("Date"),
        left_on="Entry_Date",
        right_on="Date",
        direction="backward",
        allow_exact_matches=True,
    )
    matched = matched.rename(columns={"Date": "Market_Matched_Date", "Regime": "Market_Regime"})
    unmatched = int(matched["Market_Matched_Date"].isna().sum())
    if unmatched:
        raise ValueError(f"{unmatched} trades could not be matched to a prior market-regime row")
    matched["Market_Date_Lag_Days"] = (
        matched["Entry_Date"] - matched["Market_Matched_Date"]
    ).dt.days
    if (matched["Market_Date_Lag_Days"] < 0).any():
        raise ValueError("market regime as-of join used a future observation")
    return matched.sort_values("_trade_order").drop(columns="_trade_order").reset_index(drop=True)


def _build_bucket_summary(joined: pd.DataFrame) -> pd.DataFrame:
    return _summary_rows(
        joined,
        "Leadership_Bucket",
        ordered_values=ALLOWED_BUCKETS,
    )


def _build_binary_summary(joined: pd.DataFrame) -> pd.DataFrame:
    specifications = [
        ("LEADING_vs_NON_LEADING", "Leading_Group", ("LEADING", "NON_LEADING")),
        ("TOP_HALF_vs_LOWER_HALF", "Top_Half_Group", ("TOP_HALF", "LOWER_HALF")),
        ("LAGGING_vs_NON_LAGGING", "Lagging_Group", ("LAGGING", "NON_LAGGING")),
    ]
    parts = []
    for comparison, column, groups in specifications:
        part = _summary_rows(joined, column, {"Comparison": comparison}, groups)
        part = part.rename(columns={column: "Group"})
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def _build_rank_summary(joined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for rank in range(1, 12):
        group = joined.loc[joined["Composite_Rank"].eq(rank)]
        row = {"Composite_Rank": rank, **calculate_trade_metrics(group)}
        row["Mean_Composite_RS"] = float(group["Composite_RS"].mean()) if not group.empty else math.nan
        row["Median_Composite_RS"] = float(group["Composite_RS"].median()) if not group.empty else math.nan
        rows.append(row)
    return pd.DataFrame(rows)


def _build_within_sector_summary(joined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (sector_key, bucket), group in joined.groupby(["Sector_Key", "Leadership_Bucket"], sort=True):
        rows.append(
            {
                "Comparison_Type": "DETAILED_BUCKET",
                "Sector_Key": sector_key,
                "Leadership_Bucket": bucket,
                "Group": bucket,
                "Small_Sample": len(group) < 5,
                **calculate_trade_metrics(group),
            }
        )
    top_half = joined.assign(
        _Within_Sector_Group=np.where(
            joined["Leadership_Bucket"].isin(["LEADING", "ACCEPTABLE"]),
            "TOP_HALF",
            "LOWER_HALF",
        )
    )
    for (sector_key, group_name), group in top_half.groupby(["Sector_Key", "_Within_Sector_Group"], sort=True):
        rows.append(
            {
                "Comparison_Type": "TOP_HALF_VS_LOWER_HALF",
                "Sector_Key": sector_key,
                "Leadership_Bucket": "",
                "Group": group_name,
                "Small_Sample": len(group) < 5,
                **calculate_trade_metrics(group),
            }
        )
    return pd.DataFrame(rows)


def _build_year_summary(joined: pd.DataFrame) -> pd.DataFrame:
    result = []
    for year in (2023, 2024, 2025, 2026):
        year_frame = joined.loc[joined["Entry_Date"].dt.year.eq(year)]
        if year_frame.empty:
            continue
        binary = _build_binary_summary(year_frame)
        binary.insert(0, "Entry_Year", year)
        result.append(binary)
    return pd.concat(result, ignore_index=True) if result else pd.DataFrame()


def _build_outlier_summary(joined: pd.DataFrame) -> pd.DataFrame:
    positive = joined.loc[joined["PnL"] > 0].sort_values(
        ["PnL", "Entry_Date", "Symbol", "Exit_Date"], ascending=[False, True, True, True]
    )
    rows = []
    for scenario, count in (
        ("ALL_TRADES", 0),
        ("EXCLUDE_TOP_1_POSITIVE_PNL", 1),
        ("EXCLUDE_TOP_3_POSITIVE_PNL", 3),
        ("EXCLUDE_TOP_5_POSITIVE_PNL", 5),
    ):
        excluded = positive.head(count)
        excluded_indices = set(excluded.index)
        frame = joined.loc[~joined.index.isin(excluded_indices)]
        audit = ";".join(
            f"{row.Symbol}/{row.Entry_Date:%Y-%m-%d}"
            for row in excluded.itertuples()
        )
        binary = _build_binary_summary(frame)
        binary.insert(1, "Scenario", scenario)
        binary.insert(2, "Excluded_Trades", audit)
        rows.append(binary)
    return pd.concat(rows, ignore_index=True)


def _build_market_sector_matrix(joined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for regime in ALLOWED_REGIMES:
        for bucket in ALLOWED_BUCKETS:
            group = joined.loc[
                joined["Market_Regime"].eq(regime) & joined["Leadership_Bucket"].eq(bucket)
            ]
            rows.append(
                {
                    "Comparison_Type": "REGIME_X_BUCKET",
                    "Market_Regime": regime,
                    "Leadership_Bucket": bucket,
                    "Group": "",
                    **calculate_trade_metrics(group),
                }
            )
    grouped = joined.assign(
        _Market_Sector_Group=np.where(
            joined["Market_Regime"].isin(["RISK_ON", "MIXED"])
            & joined["Leadership_Bucket"].isin(["LEADING", "ACCEPTABLE"]),
            "RISK_ON_OR_MIXED_TOP_HALF",
            "ALL_OTHER_VALID",
        )
    )
    for group_name in ("RISK_ON_OR_MIXED_TOP_HALF", "ALL_OTHER_VALID"):
        group = grouped.loc[grouped["_Market_Sector_Group"].eq(group_name)]
        rows.append(
            {
                "Comparison_Type": "RISK_ON_OR_MIXED_TOP_HALF_VS_ALL_OTHER",
                "Market_Regime": "",
                "Leadership_Bucket": "",
                "Group": group_name,
                **calculate_trade_metrics(group),
            }
        )
    return pd.DataFrame(rows)


def _validate_joined_input(trades: pd.DataFrame, joined: pd.DataFrame) -> dict[str, object]:
    bucket_counts = joined["Leadership_Bucket"].value_counts().sum() == len(trades)
    pnl_reconciles = math.isclose(float(joined["PnL"].sum()), float(trades["PnL"].sum()), abs_tol=0.01)
    return {
        "Input_Trade_Count": len(trades),
        "Unique_Symbols": trades["Symbol"].nunique(),
        "Winners": int((trades["Return_Pct"] > 0).sum()),
        "Input_Total_PnL": float(trades["PnL"].sum()),
        "Unmatched_Sector_Trades": int(joined["Sector_Matched_Date"].isna().sum()),
        "Future_Sector_Matches": int((joined["Sector_Matched_Date"] > joined["Entry_Date"]).sum()),
        "NonFullUniverse_Sector_Matches": int((~joined["Sector_Count"].eq(11)).sum()),
        "Median_Sector_Lag_Days": float(joined["Sector_Date_Lag_Days"].median()),
        "Max_Sector_Lag_Days": int(joined["Sector_Date_Lag_Days"].max()),
        "Bucket_Count_Reconciles": bool(bucket_counts),
        "PnL_Reconciles": bool(pnl_reconciles),
        "Market_Regime_Interaction": "COMPLETED",
    }


def _write_research_report(
    joined: pd.DataFrame,
    bucket: pd.DataFrame,
    binary: pd.DataFrame,
    rank: pd.DataFrame,
    within: pd.DataFrame,
    years: pd.DataFrame,
    outliers: pd.DataFrame,
    matrix: pd.DataFrame,
    validation: dict[str, object],
) -> None:
    bucket_lines = [
        f"| {row.Leadership_Bucket} | {row.Trades} | {_fmt(row.Win_Rate)} | {_fmt(row.Mean_Return)} | {_fmt(row.Median_Return)} | {_fmt(row.Total_PnL, 2)} |"
        for row in bucket.itertuples()
    ]
    binary_lines = [
        f"| {row.Comparison} | {row.Group} | {row.Trades} | {_fmt(row.Win_Rate)} | {_fmt(row.Mean_Return)} | {_fmt(row.Return_Profit_Factor)} | {_fmt(row.Total_PnL, 2)} |"
        for row in binary.itertuples()
    ]
    matrix_lines = [
        f"| {row.Comparison_Type} | {row.Market_Regime} | {row.Leadership_Bucket} | {row.Group} | {row.Trades} | {_fmt(row.Win_Rate)} | {_fmt(row.Mean_Return)} |"
        for row in matrix.itertuples()
    ]
    years_text = "Entry-year output is available in `output/t1_sector_year_summary.csv` for 2023-2026."
    if years.empty:
        years_text = "No requested entry years had matched trades."
    text = f"""# T1 Sector Leadership Validation

## Input Integrity

The fixed normalized input contains **{validation['Input_Trade_Count']} trades**, **{validation['Unique_Symbols']} symbols**, and **{validation['Winners']} winners**. Total P&L is `{validation['Input_Total_PnL']:.2f}`. The committed payload is decoded deterministically before analysis and validated against its locked SHA-256 in the repository workflow.

The sector join matched every trade to the latest full-universe (`Sector_Count == 11`) observation on or before entry. Median sector-date lag was **{validation['Median_Sector_Lag_Days']:.1f} calendar days** and maximum lag was **{validation['Max_Sector_Lag_Days']} days**.

## Four-Bucket Results

| Bucket | Trades | Win rate | Mean return | Median return | Total P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(bucket_lines)}

## Locked Binary Comparisons

| Comparison | Group | Trades | Win rate | Mean return | Return PF | Total P&L |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(binary_lines)}

## Rank Diagnostics

Rank-level metrics are exported in `output/t1_sector_rank_summary.csv` for Composite_Rank 1 through 11. These diagnostics do not select a new cutoff.

## Within-Sector Controls

Detailed and TOP_HALF versus LOWER_HALF results by sector are exported in `output/t1_sector_within_sector_summary.csv`. The fixed 20-stock sample is sector-imbalanced, and rows with fewer than five observations are marked `Small_Sample`.

## Time Stability

{years_text} Calendar years are diagnostic periods, not optimized market regimes.

## Outlier Robustness

Outlier variants excluding the largest one, three, and five positive-P&L trades are exported in `output/t1_sector_outlier_robustness.csv`. Excluded trades are recorded in an audit field; no losing trades were removed.

## Market-Regime Interaction

The existing NIFTY 500 daily regime dataset was available, so the backward/as-of market-regime join was completed. The complete regime × leadership matrix and the predeclared RISK_ON/MIXED + sector TOP_HALF comparison are in `output/t1_market_sector_matrix.csv`.

| Type | Market regime | Sector bucket | Group | Trades | Win rate | Mean return |
| --- | --- | --- | --- | ---: | ---: | ---: |
{chr(10).join(matrix_lines)}

## Limitations

- This is a fixed 20-stock sample and sector identity is confounded with leadership frequency.
- Small cells and outlier dependence can make subgroup metrics unstable.
- No transaction-cost adjustment was added unless it was already present in the fixed T1 input.
- The analysis preserves the locked RS windows, weights, ranking, bucket boundaries, mapping, and T1 entry/exit rules.
- This factual report does not authorize changing V1 rules or make the Portfolio Advisor's final strategy decision.
"""
    (OUTPUT_DIR / "research_report.md").write_text(text, encoding="utf-8")


def _write_readme() -> None:
    text = """# T1 Sector Leadership Validation

This analysis validates the fixed 218-trade T1 sample against the existing Issue #1/PR #2 point-in-time sector-leadership output. It is a validation experiment, not an optimization or a strategy decision.

## Run from repository root

```bash
python -m pytest "Swing Trading/research/swing/t1_sector_validation/tests/test_t1_sector_validation.py" -v
python "Swing Trading/research/swing/t1_sector_validation/analyze_t1_sector_leadership.py"
```

The fixed input source is `input/t1_trades.csv.gz.b64`. The analysis requires the deterministic decoded `input/t1_trades.csv`; the payload is decoded from base64/gzip and checked against SHA-256 `6b4c2931f23f0e043816d973eba16b5bf3ca57411642d4528de060ea2febb1e4` before analysis. The normalized input is locked at 218 completed trades across the 20-stock basket.

Only sector rows with `Sector_Count == 11` (and a consistent `Is_Full_Universe` flag when present) are eligible. Each trade is matched backward/as-of to the latest eligible row satisfying `Sector_Date <= Entry_Date`; the matched date and calendar lag are exported for audit. The stock-to-sector mapping is the precommitted Issue #1 mapping and is checked exactly.

The existing NIFTY 500 regime dataset is also joined backward/as-of when present. No future data, regenerated trade set, additional indicators, or result-driven filters are introduced.
"""
    (BASE_DIR / "README.md").write_text(text, encoding="utf-8")


def run_analysis() -> dict[str, object]:
    trades = load_and_validate_trades()
    mapping = load_and_validate_mapping()
    trades = trades.merge(mapping.rename(columns={"Stock": "Symbol"}), on="Symbol", how="left", validate="many_to_one")
    if trades["Sector_Key"].isna().any():
        raise ValueError("some T1 trades have no stock-sector mapping")
    sector = prepare_full_universe_sector_data(load_and_validate_sector_data())
    joined = asof_join_sector_leadership(trades, sector)
    regime = load_and_validate_regime_data()
    joined = asof_join_market_regime(joined, regime)
    joined = classify_binary_groups(joined)
    joined = joined.sort_values(["Entry_Date", "Symbol", "Exit_Date"]).reset_index(drop=True)
    validation = _validate_joined_input(trades, joined)
    if validation["Input_Trade_Count"] != 218 or validation["Unmatched_Sector_Trades"] != 0:
        raise ValueError("joined validation failed locked count or unmatched-trade check")
    if not validation["Bucket_Count_Reconciles"] or not validation["PnL_Reconciles"]:
        raise ValueError("joined validation failed bucket/PnL reconciliation")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joined_columns = [
        "Symbol",
        "Entry_Date",
        "Exit_Date",
        "Return_Pct",
        "PnL",
        "Holding_Days",
        "Sector_Key",
        "Sector_Matched_Date",
        "Sector_Date_Lag_Days",
        "Composite_RS",
        "Composite_Rank",
        "Sector_Count",
        "Leadership_Bucket",
        "Market_Matched_Date",
        "Market_Date_Lag_Days",
        "Market_Regime",
    ]
    _write_csv(joined[joined_columns], OUTPUT_DIR / "t1_sector_joined_trades.csv")
    bucket = _build_bucket_summary(joined)
    binary = _build_binary_summary(joined)
    rank = _build_rank_summary(joined)
    within = _build_within_sector_summary(joined)
    years = _build_year_summary(joined)
    outliers = _build_outlier_summary(joined)
    matrix = _build_market_sector_matrix(joined)
    _write_csv(bucket, OUTPUT_DIR / "t1_sector_bucket_summary.csv")
    _write_csv(binary, OUTPUT_DIR / "t1_sector_binary_tests.csv")
    _write_csv(rank, OUTPUT_DIR / "t1_sector_rank_summary.csv")
    _write_csv(within, OUTPUT_DIR / "t1_sector_within_sector_summary.csv")
    _write_csv(years, OUTPUT_DIR / "t1_sector_year_summary.csv")
    _write_csv(outliers, OUTPUT_DIR / "t1_sector_outlier_robustness.csv")
    _write_csv(matrix, OUTPUT_DIR / "t1_market_sector_matrix.csv")
    validation_frame = pd.DataFrame(
        [{"Check": key, "Value": value} for key, value in validation.items()]
    )
    _write_csv(validation_frame, OUTPUT_DIR / "validation_report.csv")
    _write_research_report(joined, bucket, binary, rank, within, years, outliers, matrix, validation)
    _write_readme()
    print(f"Input trades: {len(trades)}; symbols: {trades['Symbol'].nunique()}; winners: {(trades['Return_Pct'] > 0).sum()}")
    print(f"Sector matches: {len(joined)}; unmatched: {validation['Unmatched_Sector_Trades']}")
    print(f"Sector lag days: median={validation['Median_Sector_Lag_Days']:.1f}, max={validation['Max_Sector_Lag_Days']}")
    print(f"Market-regime interaction: {validation['Market_Regime_Interaction']}")
    print(f"Generated outputs under {OUTPUT_DIR}")
    return validation


if __name__ == "__main__":
    try:
        run_analysis()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc
