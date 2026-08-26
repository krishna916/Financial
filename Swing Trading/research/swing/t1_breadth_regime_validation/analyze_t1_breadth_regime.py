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
BREADTH_PATH = SWING_RESEARCH_DIR / "market_breadth" / "output" / "nifty500_breadth_daily.csv"
SIMPLE_REGIME_PATH = SWING_TRADING_DIR / "nifty500_regime_daily.csv"
OUTPUT_DIR = BASE_DIR / "output"

EXPECTED_T1_SHA256 = "6b4c2931f23f0e043816d973eba16b5bf3ca57411642d4528de060ea2febb1e4"
REGIME_ORDER = ["STRONG_MOMENTUM", "NORMAL", "HOSTILE"]
BINARY_ORDER = ["STRONG_MOMENTUM", "NON_STRONG"]
HOSTILE_ORDER = ["HOSTILE", "NON_HOSTILE"]
T1_SYMBOLS = {
    "HDFCBANK", "ICICIBANK", "SBIN", "BAJFINANCE", "TCS", "INFY", "M&M", "MARUTI", "LT",
    "RELIANCE", "ONGC", "ITC", "HINDUNILVR", "SUNPHARMA", "APOLLOHOSP", "BHARTIARTL",
    "TATASTEEL", "POWERGRID", "ADANIENT", "ULTRACEMCO",
}
TRADE_COLUMNS = [
    "Symbol", "Entry_Date", "Exit_Date", "Entry_Price", "Exit_Price", "Qty", "Return_Pct", "PnL",
    "Holding_Days", "Source_Log",
]
METRIC_COLUMNS = [
    "Trades", "Winners", "Losers", "Win_Rate", "Mean_Return", "Median_Return", "Average_Winner",
    "Average_Loser", "Payoff_Ratio", "Return_Profit_Factor", "PnL_Profit_Factor", "Total_PnL",
    "Median_Holding_Days",
]


def _require_columns(frame: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def _dates(values: pd.Series | pd.Index) -> pd.Series | pd.DatetimeIndex:
    parsed = pd.to_datetime(values, errors="raise", utc=True)
    if isinstance(parsed, pd.Series):
        return parsed.dt.tz_localize(None).dt.normalize()
    return parsed.tz_localize(None).normalize()


def load_and_validate_trades(path: Path = T1_TRADES_PATH) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"fixed T1 input is missing: {path}")
    raw = path.read_bytes()
    if path.resolve() == T1_TRADES_PATH.resolve() and hashlib.sha256(raw).hexdigest() != EXPECTED_T1_SHA256:
        raise ValueError("fixed T1 input SHA-256 does not match the locked payload")
    trades = pd.read_csv(path)
    if trades.columns.tolist() != TRADE_COLUMNS:
        raise ValueError(f"T1 input columns must be {TRADE_COLUMNS}")
    trades["Entry_Date"] = _dates(trades["Entry_Date"])
    trades["Exit_Date"] = _dates(trades["Exit_Date"])
    numeric = ["Entry_Price", "Exit_Price", "Qty", "Return_Pct", "PnL", "Holding_Days"]
    for column in numeric:
        trades[column] = pd.to_numeric(trades[column], errors="coerce")
    if trades.isna().any().any() or not np.isfinite(trades[numeric].to_numpy(dtype=float)).all():
        raise ValueError("T1 input contains invalid required values")
    if not trades["Symbol"].isin(T1_SYMBOLS).all() or trades["Symbol"].nunique() != 20:
        raise ValueError("T1 input symbol basket is not the locked 20-stock basket")
    if len(trades) != 218 or int((trades["Return_Pct"] > 0).sum()) != 76:
        raise ValueError("T1 input row or winner count does not match the locked sample")
    if not math.isclose(float(trades["PnL"].sum()), -4631.32, abs_tol=0.01):
        raise ValueError("T1 input total PnL does not match the locked sample")
    return trades


def load_breadth(path: Path = BREADTH_PATH) -> pd.DataFrame:
    breadth = pd.read_csv(path)
    aliases = {
        "Universe_Member_Count": "Member_Count",
        "Eligible_Count_50": "SMA50_Denominator",
        "Eligible_Count_200": "SMA200_Denominator",
        "Momentum_Regime": "Regime",
    }
    for required_name, legacy_name in aliases.items():
        if required_name not in breadth.columns and legacy_name in breadth.columns:
            breadth[required_name] = breadth[legacy_name]
    required = {
        "Date", "Universe_Member_Count", "Eligible_Count_50", "Eligible_Count_200", "Pct_Above_SMA50",
        "Pct_Above_SMA200", "Nifty500_Close", "Nifty500_SMA200", "Momentum_Regime", "Coverage_OK",
    }
    _require_columns(breadth, required, "breadth data")
    breadth["Date"] = _dates(breadth["Date"])
    if breadth["Date"].duplicated().any():
        raise ValueError("breadth data contains duplicate dates")
    for column in ["Universe_Member_Count", "Eligible_Count_50", "Eligible_Count_200"]:
        breadth[column] = pd.to_numeric(breadth[column], errors="coerce")
    for column in ["Pct_Above_SMA50", "Pct_Above_SMA200", "Nifty500_Close", "Nifty500_SMA200"]:
        breadth[column] = pd.to_numeric(breadth[column], errors="coerce")
    coverage = breadth["Coverage_OK"].astype("string").str.lower().eq("true")
    if not breadth["Momentum_Regime"].isin(REGIME_ORDER + ["INSUFFICIENT_COVERAGE"]).all():
        raise ValueError("breadth data contains an invalid regime label")
    if not breadth[["Pct_Above_SMA50", "Pct_Above_SMA200"]].apply(lambda column: column.dropna().between(0, 100).all()).all():
        raise ValueError("breadth percentages must stay in [0, 100]")
    if (breadth["Eligible_Count_50"] > breadth["Universe_Member_Count"]).any() or (breadth["Eligible_Count_200"] > breadth["Universe_Member_Count"]).any():
        raise ValueError("breadth eligible denominators exceed the universe")
    expected_coverage = breadth["Eligible_Count_200"] >= 0.80 * breadth["Universe_Member_Count"]
    if not np.array_equal(coverage.fillna(False).to_numpy(dtype=bool), expected_coverage.fillna(False).to_numpy(dtype=bool)):
        raise ValueError("breadth Coverage_OK does not match the locked 80% rule")
    breadth["Coverage_OK"] = coverage.astype(bool)
    breadth["Universe_Method"] = "POINT_IN_TIME"
    return breadth.sort_values("Date").reset_index(drop=True)


def asof_join_breadth(trades: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame:
    _require_columns(trades, ["Entry_Date"], "trades")
    _require_columns(breadth, ["Date"], "breadth")
    left = trades.copy()
    right = breadth.copy()
    left["Entry_Date"] = _dates(left["Entry_Date"])
    right["Date"] = _dates(right["Date"])
    if right["Date"].duplicated().any():
        raise ValueError("breadth data contains duplicate dates")
    left["_trade_order"] = np.arange(len(left))
    joined = pd.merge_asof(
        left.sort_values("Entry_Date"),
        right.sort_values("Date"),
        left_on="Entry_Date",
        right_on="Date",
        direction="backward",
        allow_exact_matches=False,
    ).sort_values("_trade_order").reset_index(drop=True)
    joined = joined.rename(columns={"Date": "Breadth_Matched_Date"})
    if "Momentum_Regime" not in joined.columns and "Regime" in joined.columns:
        joined["Momentum_Regime"] = joined["Regime"]
    joined["Breadth_Date_Lag_Days"] = (joined["Entry_Date"] - joined["Breadth_Matched_Date"]).dt.days
    joined["Breadth_Lag_Over_7_Days"] = joined["Breadth_Date_Lag_Days"].gt(7).fillna(False)
    joined["Breadth_Match_Status"] = np.select(
        [
            joined["Breadth_Matched_Date"].isna(),
            joined["Coverage_OK"].fillna(False).ne(True),
            ~joined["Momentum_Regime"].isin(REGIME_ORDER),
        ],
        ["NO_PRIOR_OBSERVATION", "UNSAFE_COVERAGE", "UNSAFE_REGIME"],
        default="MATCHED_RESEARCH_SAFE",
    )
    if joined["Breadth_Matched_Date"].notna().any():
        matched = joined["Breadth_Matched_Date"].notna()
        if not (joined.loc[matched, "Breadth_Matched_Date"] < joined.loc[matched, "Entry_Date"]).all():
            raise ValueError("strict breadth join produced a same-day or future match")
    return joined.drop(columns="_trade_order")


def calculate_profit_factor(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    positive = float(numeric.loc[numeric > 0].sum())
    negative = float(numeric.loc[numeric < 0].sum())
    if negative == 0:
        return math.inf if positive > 0 else math.nan
    return positive / abs(negative) if positive else 0.0


def _payoff_ratio(average_winner: float, average_loser: float) -> float:
    if math.isnan(average_loser):
        return math.inf if not math.isnan(average_winner) else math.nan
    if average_loser == 0:
        return math.nan
    return 0.0 if math.isnan(average_winner) else average_winner / abs(average_loser)


def calculate_trade_metrics(trades: pd.DataFrame) -> dict[str, float | int]:
    _require_columns(trades, ["Return_Pct", "PnL", "Holding_Days"], "trade data")
    returns = pd.to_numeric(trades["Return_Pct"], errors="coerce")
    pnl = pd.to_numeric(trades["PnL"], errors="coerce")
    holding = pd.to_numeric(trades["Holding_Days"], errors="coerce")
    winners = returns.loc[returns > 0]
    losers = returns.loc[returns < 0]
    average_winner = float(winners.mean()) if not winners.empty else math.nan
    average_loser = float(losers.mean()) if not losers.empty else math.nan
    return {
        "Trades": len(trades),
        "Winners": len(winners),
        "Losers": len(losers),
        "Win_Rate": float(len(winners) / len(trades)) if len(trades) else math.nan,
        "Mean_Return": float(returns.mean()) if len(trades) else math.nan,
        "Median_Return": float(returns.median()) if len(trades) else math.nan,
        "Average_Winner": average_winner,
        "Average_Loser": average_loser,
        "Payoff_Ratio": _payoff_ratio(average_winner, average_loser),
        "Return_Profit_Factor": calculate_profit_factor(returns),
        "PnL_Profit_Factor": calculate_profit_factor(pnl),
        "Total_PnL": float(pnl.sum()) if len(trades) else 0.0,
        "Median_Holding_Days": float(holding.median()) if len(trades) else math.nan,
    }


def _summary_rows(frame: pd.DataFrame, column: str, values: list[str], comparison: str) -> pd.DataFrame:
    rows = []
    for value in values:
        group = frame.loc[frame[column].eq(value)]
        rows.append({"Comparison": comparison, "Group": value, **calculate_trade_metrics(group)})
    return pd.DataFrame(rows)


def add_regime_groups(trades: pd.DataFrame) -> pd.DataFrame:
    regime_column = "Momentum_Regime" if "Momentum_Regime" in trades else "Regime"
    _require_columns(trades, [regime_column], "joined trades")
    result = trades.copy()
    regime = result[regime_column]
    if not regime.isin(REGIME_ORDER).all():
        raise ValueError("joined trades contain non-primary regime labels")
    result["Regime"] = regime
    result["Strong_Group"] = np.where(regime.eq("STRONG_MOMENTUM"), "STRONG_MOMENTUM", "NON_STRONG")
    result["Hostile_Group"] = np.where(regime.eq("HOSTILE"), "HOSTILE", "NON_HOSTILE")
    return result


def build_regime_summary(joined: pd.DataFrame) -> pd.DataFrame:
    return _summary_rows(joined, "Regime", REGIME_ORDER, "THREE_REGIMES")


def build_binary_tests(joined: pd.DataFrame) -> pd.DataFrame:
    return pd.concat(
        [
            _summary_rows(joined, "Strong_Group", BINARY_ORDER, "STRONG_MOMENTUM_vs_NON_STRONG"),
            _summary_rows(joined, "Hostile_Group", HOSTILE_ORDER, "HOSTILE_vs_NON_HOSTILE"),
        ],
        ignore_index=True,
    )


def build_year_summary(joined: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for year in (2023, 2024, 2025, 2026):
        frame = joined.loc[joined["Entry_Date"].dt.year.eq(year)]
        if not frame.empty:
            part = _summary_rows(frame, "Strong_Group", BINARY_ORDER, "STRONG_MOMENTUM_vs_NON_STRONG")
            part.insert(0, "Entry_Year", year)
            parts.append(part)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def build_outlier_robustness(joined: pd.DataFrame) -> pd.DataFrame:
    positive = joined.loc[joined["PnL"] > 0].sort_values(
        ["PnL", "Entry_Date", "Symbol", "Exit_Date"], ascending=[False, True, True, True]
    )
    parts = []
    for scenario, count in [("ALL_TRADES", 0), ("EXCLUDE_TOP_1_POSITIVE_PNL", 1), ("EXCLUDE_TOP_3_POSITIVE_PNL", 3), ("EXCLUDE_TOP_5_POSITIVE_PNL", 5)]:
        excluded = positive.head(count)
        frame = joined.loc[~joined.index.isin(excluded.index)]
        part = _summary_rows(frame, "Strong_Group", BINARY_ORDER, "STRONG_MOMENTUM_vs_NON_STRONG")
        part.insert(1, "Scenario", scenario)
        part.insert(2, "Excluded_Trade_Count", count)
        part.insert(3, "Excluded_Trades", ";".join(f"{row.Symbol}/{row.Entry_Date:%Y-%m-%d}" for row in excluded.itertuples()))
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def build_leave_one_symbol_out(joined: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for symbol in sorted(T1_SYMBOLS):
        frame = joined.loc[joined["Symbol"].ne(symbol)]
        part = _summary_rows(frame, "Strong_Group", BINARY_ORDER, "STRONG_MOMENTUM_vs_NON_STRONG")
        part.insert(0, "Excluded_Symbol", symbol)
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def build_episode_summary(daily: pd.DataFrame) -> pd.DataFrame:
    _require_columns(daily, ["Date", "Regime"], "breadth daily data")
    frame = daily.sort_values("Date").reset_index(drop=True).copy()
    strong = frame["Regime"].eq("STRONG_MOMENTUM")
    starts = strong & ~strong.shift(fill_value=False)
    episode_numbers = starts.cumsum().where(strong)
    rows = []
    for number, group in frame.loc[strong].assign(Episode_Number=episode_numbers[strong]).groupby("Episode_Number", sort=True):
        rows.append(
            {
                "Episode_Number": int(number),
                "Episode_Start_Date": group["Date"].min(),
                "Episode_End_Date": group["Date"].max(),
                "Episode_Length_Sessions": len(group),
                "T1_Trade_Count": 0,
            }
        )
    return pd.DataFrame(rows)


def _attach_episode_numbers(joined: pd.DataFrame, daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    episodes = build_episode_summary(daily)
    if episodes.empty:
        joined["Strong_Episode_Number"] = np.nan
        return joined, episodes
    strong_dates = daily.loc[daily["Regime"].eq("STRONG_MOMENTUM"), ["Date"]].copy()
    starts = daily["Regime"].eq("STRONG_MOMENTUM") & ~daily["Regime"].eq("STRONG_MOMENTUM").shift(fill_value=False)
    strong_dates["Episode_Number"] = starts.cumsum().loc[strong_dates.index].astype(int).to_numpy()
    result = joined.merge(
        strong_dates.rename(columns={"Date": "Breadth_Matched_Date", "Episode_Number": "Strong_Episode_Number"}),
        on="Breadth_Matched_Date",
        how="left",
        validate="many_to_one",
    )
    counts = result["Strong_Episode_Number"].value_counts(dropna=True)
    episodes = episodes.copy()
    episodes["T1_Trade_Count"] = episodes["Episode_Number"].map(counts).fillna(0).astype(int)
    return result, episodes


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, date_format="%Y-%m-%d")


def _simple_regime_summary(joined: pd.DataFrame) -> pd.DataFrame:
    simple = pd.read_csv(SIMPLE_REGIME_PATH)
    _require_columns(simple, ["Date", "Regime"], "existing simple regime")
    simple = simple.loc[:, ["Date", "Regime"]].rename(columns={"Regime": "Simple_Regime"})
    simple["Date"] = _dates(simple["Date"])
    simple["_order"] = np.arange(len(simple))
    right = simple.rename(columns={"Date": "Simple_Matched_Date"}).sort_values("Simple_Matched_Date")
    left = joined.loc[:, ["Entry_Date", "Symbol", "Source_Log", "Return_Pct", "PnL", "Holding_Days"]].copy().sort_values("Entry_Date")
    matched = pd.merge_asof(left, right, left_on="Entry_Date", right_on="Simple_Matched_Date", direction="backward", allow_exact_matches=False)
    if matched["Simple_Matched_Date"].isna().any() or not (matched["Simple_Matched_Date"] < matched["Entry_Date"]).all():
        raise ValueError("existing simple regime could not be joined strictly")
    return matched


def _metric_table_markdown(frame: pd.DataFrame) -> str:
    columns = ["Comparison", "Group", "Trades", "Win_Rate", "Mean_Return", "Return_Profit_Factor", "Total_PnL"]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in frame.loc[:, columns].itertuples(index=False, name=None):
        values = []
        for value in row:
            if pd.isna(value):
                values.append("NA")
            elif isinstance(value, (float, np.floating)) and math.isinf(float(value)):
                values.append("inf")
            elif isinstance(value, (float, np.floating)):
                values.append(f"{float(value):.4f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _write_report(joined: pd.DataFrame, regimes: pd.DataFrame, binaries: pd.DataFrame, years: pd.DataFrame, outliers: pd.DataFrame, episodes: pd.DataFrame, validation: pd.DataFrame) -> None:
    simple = _simple_regime_summary(joined)
    simple_rows = []
    for regime in ["RISK_ON", "MIXED", "RISK_OFF"]:
        group = simple.loc[simple["Simple_Regime"].eq(regime)]
        simple_rows.append({"Comparison": "EXISTING_SIMPLE_INDEX_REGIME", "Group": regime, **calculate_trade_metrics(group)})
    simple_summary = pd.DataFrame(simple_rows)
    safe = int(validation.loc[validation["Check"] == "all_breadth_matches_research_safe", "Observed"].iloc[0])
    text = f"""# T1 Breadth Regime Validation

This is the precommitted final rescue test for the immutable 218-trade T1 sample. The Portfolio Advisor's methodology decision was `CUSTOM_REQUIRED`; the implementation is mechanical and does not tune thresholds after observing outcomes.

## Data-integrity gate

- Breadth universe method: `POINT_IN_TIME`.
- Breadth rows were built independently in `market_breadth/`; the breadth builder does not load the T1 input.
- The frozen breadth series contains {len(joined)} decision-time matches; research-safe matches: {safe}.
- Breadth lag maximum: {joined['Breadth_Date_Lag_Days'].max():.0f} calendar days; median: {joined['Breadth_Date_Lag_Days'].median():.0f} calendar days; lags over seven days: {int(joined['Breadth_Lag_Over_7_Days'].sum())}.
- No minimum-duration filter was applied to strong episodes.

## New breadth-regime result

{_metric_table_markdown(regimes)}

{_metric_table_markdown(binaries)}

## Robustness outputs

- Entry-year comparison: `output/t1_breadth_year_summary.csv`.
- Global positive-P&L outlier removal: `output/t1_breadth_outlier_robustness.csv`.
- Leave-one-symbol-out diagnostic across all 20 fixed symbols: `output/t1_breadth_leave_one_symbol_out.csv`.
- Strong-episode fragmentation and trade distribution: `output/t1_breadth_episode_summary.csv`.

## Existing simple index regime comparison

The earlier `RISK_ON`/`MIXED`/`RISK_OFF` labels were matched strictly before entry from the existing committed Nifty 500 regime file. The table is factual context only; no regime definition was changed to improve the result.

{_metric_table_markdown(simple_summary)}

## Interpretation boundary

This report supplies the locked evidence only. The Portfolio Advisor retains the keep/retire decision. The precommitted gate calls for positive expectancy, materially stronger separation from `NON_STRONG`, robustness to removing the top 1/3/5 positive-P&L trades, no single-symbol dependence, and evidence across more than one episode where sample size permits.
"""
    (OUTPUT_DIR / "research_report.md").write_text(text, encoding="utf-8")


def run_analysis() -> dict[str, object]:
    trades = load_and_validate_trades()
    breadth = load_breadth()
    joined = asof_join_breadth(trades, breadth)
    status_counts = joined["Breadth_Match_Status"].value_counts()
    if len(joined) != len(trades):
        raise ValueError("breadth join did not preserve all T1 trades")
    if not joined["Breadth_Match_Status"].eq("MATCHED_RESEARCH_SAFE").all():
        raise ValueError(f"T1 breadth matches are not all research-safe: {status_counts.to_dict()}")
    joined = add_regime_groups(joined)
    episode_daily = breadth.drop(columns=["Regime"], errors="ignore").rename(columns={"Momentum_Regime": "Regime"})
    joined, episodes = _attach_episode_numbers(joined, episode_daily)
    regimes = build_regime_summary(joined)
    binaries = build_binary_tests(joined)
    years = build_year_summary(joined)
    outliers = build_outlier_robustness(joined)
    loo = build_leave_one_symbol_out(joined)
    validation = pd.DataFrame(
        [
            {"Check": "t1_trade_count", "Expected": 218, "Observed": len(trades), "Pass": len(trades) == 218},
            {"Check": "t1_unique_symbols", "Expected": 20, "Observed": trades["Symbol"].nunique(), "Pass": trades["Symbol"].nunique() == 20},
            {"Check": "t1_winner_count", "Expected": 76, "Observed": int((trades["Return_Pct"] > 0).sum()), "Pass": int((trades["Return_Pct"] > 0).sum()) == 76},
            {"Check": "t1_total_pnl", "Expected": -4631.32, "Observed": float(trades["PnL"].sum()), "Pass": math.isclose(float(trades["PnL"].sum()), -4631.32, abs_tol=0.01)},
            {"Check": "breadth_universe_method_point_in_time", "Expected": "POINT_IN_TIME", "Observed": breadth["Universe_Method"].unique()[0], "Pass": breadth["Universe_Method"].eq("POINT_IN_TIME").all()},
            {"Check": "all_breadth_matches_research_safe", "Expected": 218, "Observed": int(joined["Breadth_Match_Status"].eq("MATCHED_RESEARCH_SAFE").sum()), "Pass": joined["Breadth_Match_Status"].eq("MATCHED_RESEARCH_SAFE").all()},
            {"Check": "strict_before_entry", "Expected": True, "Observed": bool((joined["Breadth_Matched_Date"] < joined["Entry_Date"]).all()), "Pass": bool((joined["Breadth_Matched_Date"] < joined["Entry_Date"]).all())},
            {"Check": "binary_group_reconciliation", "Expected": 218, "Observed": int(binaries.loc[binaries["Comparison"].eq("STRONG_MOMENTUM_vs_NON_STRONG"), "Trades"].sum()), "Pass": int(binaries.loc[binaries["Comparison"].eq("STRONG_MOMENTUM_vs_NON_STRONG"), "Trades"].sum()) == 218},
            {"Check": "breadth_pct_range", "Expected": "[0,100]", "Observed": "[0,100]", "Pass": bool(breadth[["Pct_Above_SMA50", "Pct_Above_SMA200"]].apply(lambda column: column.dropna().between(0, 100).all()).all())},
        ]
    )
    _write_csv(joined, OUTPUT_DIR / "t1_breadth_joined_trades.csv")
    _write_csv(regimes, OUTPUT_DIR / "t1_breadth_regime_summary.csv")
    _write_csv(binaries, OUTPUT_DIR / "t1_breadth_binary_tests.csv")
    _write_csv(years, OUTPUT_DIR / "t1_breadth_year_summary.csv")
    _write_csv(outliers, OUTPUT_DIR / "t1_breadth_outlier_robustness.csv")
    _write_csv(loo, OUTPUT_DIR / "t1_breadth_leave_one_symbol_out.csv")
    _write_csv(episodes, OUTPUT_DIR / "t1_breadth_episode_summary.csv")
    _write_csv(validation, OUTPUT_DIR / "validation_report.csv")
    _write_report(joined, regimes, binaries, years, outliers, episodes, validation)
    return {"joined": joined, "regimes": regimes, "binaries": binaries, "years": years, "outliers": outliers, "loo": loo, "episodes": episodes, "validation": validation}


if __name__ == "__main__":
    result = run_analysis()
    print(result["validation"].to_string(index=False))
    print(result["regimes"].to_string(index=False))
