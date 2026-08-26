"""Analyze Strategy V2 entries with locked exits, diagnostics, and gates."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from build_v2_features import (
    DOWNLOAD_END_EXCLUSIVE,
    DOWNLOAD_START,
    build_feature_frames,
    compute_price_features,
    load_membership,
    rank_point_in_time_rs,
    download_adjusted_ohlcv,
)


def _finite(value: object) -> bool:
    try:
        return bool(pd.notna(value) and np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _prices_for_trade(prices: pd.DataFrame) -> pd.DataFrame:
    required = {"Date", "Open", "High", "Low", "Close", "SMA20"}
    missing = required.difference(prices.columns)
    if missing:
        raise ValueError(f"trade prices missing columns: {sorted(missing)}")
    result = prices.copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
    if getattr(result["Date"].dt, "tz", None) is not None:
        result["Date"] = result["Date"].dt.tz_localize(None)
    if result["Date"].isna().any() or result["Date"].duplicated().any():
        raise ValueError("trade prices contain invalid or duplicate dates")
    return result.sort_values("Date").reset_index(drop=True)


def _result_base(entry_row: pd.Series, exit_row: pd.Series, exit_reason: str) -> dict[str, object]:
    entry_date = pd.Timestamp(entry_row["Entry_Date"])
    entry_open = float(entry_row["Entry_Open"])
    exit_price = float(exit_row["Open"] if exit_reason in {"SMA20", "STOP_GAP"} else exit_row["Open"])
    result = {
        "Entry_ID": entry_row["Entry_ID"],
        "Symbol": entry_row.get("Symbol", ""),
        "Entry_Date": entry_date,
        "Entry_Open": entry_open,
        "Exit_Date": pd.Timestamp(exit_row["Date"]),
        "Exit_Price": exit_price,
        "Exit_Reason": exit_reason,
    }
    result["Return"] = (result["Exit_Price"] - entry_open) / entry_open
    return result


def simulate_setup_quality_trade(entry_row: pd.Series, prices: pd.DataFrame) -> dict[str, object] | None:
    """Exit at the next open after the first close below SMA20."""

    data = _prices_for_trade(prices)
    entry_date = pd.Timestamp(entry_row["Entry_Date"])
    positions = np.flatnonzero(data["Date"].eq(entry_date))
    if len(positions) == 0 or not _finite(entry_row.get("Entry_Open", np.nan)):
        return None
    entry_index = int(positions[0])
    for index in range(entry_index, len(data)):
        close = data.loc[index, "Close"]
        sma20 = data.loc[index, "SMA20"]
        if _finite(close) and _finite(sma20) and float(close) < float(sma20):
            if index + 1 >= len(data) or not _finite(data.loc[index + 1, "Open"]):
                return None
            exit_row = data.loc[index + 1]
            result = _result_base(entry_row, exit_row, "SMA20")
            result["Exit_Signal_Date"] = pd.Timestamp(data.loc[index, "Date"])
            result["Return"] = (result["Exit_Price"] - result["Entry_Open"]) / result["Entry_Open"]
            result["Holding_Sessions"] = index + 1 - entry_index
            return result
    return None


def simulate_practical_trade(entry_row: pd.Series, prices: pd.DataFrame) -> dict[str, object] | None:
    """Apply scheduled SMA20 exit before the fixed structural stop."""

    data = _prices_for_trade(prices)
    entry_date = pd.Timestamp(entry_row["Entry_Date"])
    positions = np.flatnonzero(data["Date"].eq(entry_date))
    stop = entry_row.get("Structural_Stop", np.nan)
    entry_open = entry_row.get("Entry_Open", np.nan)
    if len(positions) == 0 or not _finite(stop) or not _finite(entry_open):
        return None
    entry_index = int(positions[0])
    scheduled_sma20_exit = False
    exit_signal_date: pd.Timestamp | None = None
    for index in range(entry_index, len(data)):
        row = data.loc[index]
        if scheduled_sma20_exit:
            if not _finite(row["Open"]):
                return None
            result = _result_base(entry_row, row, "SMA20")
            result["Exit_Signal_Date"] = exit_signal_date
            result["Initial_Risk"] = float(entry_open) - float(stop)
            result["R_Multiple"] = (result["Exit_Price"] - result["Entry_Open"]) / result["Initial_Risk"]
            result["Holding_Sessions"] = index - entry_index
            return result
        if not _finite(row["Open"]) or not _finite(row["Low"]):
            return None
        if float(row["Open"]) <= float(stop):
            result = _result_base(entry_row, row, "STOP_GAP")
            result["Initial_Risk"] = float(entry_open) - float(stop)
            result["R_Multiple"] = (result["Exit_Price"] - result["Entry_Open"]) / result["Initial_Risk"]
            result["Holding_Sessions"] = index - entry_index
            return result
        if float(row["Low"]) <= float(stop):
            result = _result_base(entry_row, row, "STOP_INTRADAY")
            result["Exit_Price"] = float(stop)
            result["Initial_Risk"] = float(entry_open) - float(stop)
            result["R_Multiple"] = (result["Exit_Price"] - result["Entry_Open"]) / result["Initial_Risk"]
            result["Holding_Sessions"] = index - entry_index
            return result
        if _finite(row["Close"]) and _finite(row["SMA20"]) and float(row["Close"]) < float(row["SMA20"]):
            scheduled_sma20_exit = True
            exit_signal_date = pd.Timestamp(row["Date"])
    return None


def safe_profit_factor(values: pd.Series) -> float:
    """Return profit factor with explicit no-win/no-loss behavior."""

    numeric = pd.to_numeric(values, errors="coerce").dropna()
    positive = float(numeric.loc[numeric > 0].sum())
    negative = float(numeric.loc[numeric < 0].sum())
    if positive and not negative:
        return np.inf
    if negative and not positive:
        return 0.0
    if not positive and not negative:
        return np.nan
    return positive / abs(negative)


def attach_prior_breadth(trades: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame:
    """Attach the latest breadth row strictly before each entry date."""

    if trades.empty:
        return trades.copy()
    if "Entry_Date" not in trades or "Date" not in breadth:
        raise ValueError("trades need Entry_Date and breadth needs Date")
    left = trades.copy()
    left["Entry_Date"] = pd.to_datetime(left["Entry_Date"], errors="coerce")
    right = breadth.copy()
    right["Date"] = pd.to_datetime(right["Date"], errors="coerce")
    if left["Entry_Date"].isna().any() or right["Date"].isna().any():
        raise ValueError("breadth join contains invalid dates")
    left["_original_order"] = np.arange(len(left))
    right = right.rename(columns={"Date": "Breadth_Matched_Date"})
    joined = pd.merge_asof(
        left.sort_values("Entry_Date"),
        right.sort_values("Breadth_Matched_Date"),
        left_on="Entry_Date",
        right_on="Breadth_Matched_Date",
        direction="backward",
        allow_exact_matches=False,
    )
    matched = joined["Breadth_Matched_Date"].notna()
    if (joined.loc[matched, "Breadth_Matched_Date"] >= joined.loc[matched, "Entry_Date"]).any():
        raise AssertionError("breadth match is not strictly before entry")
    return joined.sort_values("_original_order").drop(columns="_original_order").reset_index(drop=True)


def validate_trade_integrity(setup: pd.DataFrame, practical: pd.DataFrame) -> None:
    """Reject mismatched lens samples and non-strict breadth timing."""

    setup_ids = set(setup.get("Entry_ID", pd.Series(dtype=str)))
    practical_ids = set(practical.get("Entry_ID", pd.Series(dtype=str)))
    if setup_ids != practical_ids:
        raise AssertionError("setup/practical accepted Entry_ID sets differ")
    for trades in (setup, practical):
        if "Breadth_Matched_Date" not in trades.columns or trades.empty:
            continue
        matched = trades["Breadth_Matched_Date"].notna()
        if (trades.loc[matched, "Breadth_Matched_Date"] >= trades.loc[matched, "Entry_Date"]).any():
            raise AssertionError("breadth context is not strictly prior to entry")


def summarize_lens(trades: pd.DataFrame, lens: str) -> dict[str, object]:
    """Summarize one completed trade lens."""

    if lens not in {"setup", "practical"}:
        raise ValueError("lens must be setup or practical")
    returns = pd.to_numeric(trades.get("Return", pd.Series(dtype=float)), errors="coerce")
    r_values = pd.to_numeric(trades.get("R_Multiple", pd.Series(dtype=float)), errors="coerce")
    holding = pd.to_numeric(trades.get("Holding_Sessions", pd.Series(dtype=float)), errors="coerce")
    measure = returns if lens == "setup" else r_values
    return {
        "Completed_Trades": int(measure.notna().sum()),
        "Winners": int((measure > 0).sum()),
        "Losers": int((measure < 0).sum()),
        "Win_Rate": float((measure > 0).mean()) if len(measure) else np.nan,
        "Mean_Return": float(returns.mean()) if returns.notna().any() else np.nan,
        "Median_Return": float(returns.median()) if returns.notna().any() else np.nan,
        "Return_PF": safe_profit_factor(returns),
        "Mean_R": float(r_values.mean()) if r_values.notna().any() else np.nan,
        "Median_R": float(r_values.median()) if r_values.notna().any() else np.nan,
        "R_PF": safe_profit_factor(r_values),
        "Median_Holding_Sessions": float(holding.median()) if holding.notna().any() else np.nan,
    }


def _paired_trades(setup: pd.DataFrame, practical: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ids = set(setup.get("Entry_ID", pd.Series(dtype=str))) & set(practical.get("Entry_ID", pd.Series(dtype=str)))
    return (
        setup.loc[setup["Entry_ID"].isin(ids)].copy() if "Entry_ID" in setup else setup.copy(),
        practical.loc[practical["Entry_ID"].isin(ids)].copy() if "Entry_ID" in practical else practical.copy(),
    )


def year_summary(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame:
    setup, practical = _paired_trades(setup, practical)
    years = sorted(
        set(pd.to_datetime(setup.get("Entry_Date", pd.Series(dtype="datetime64[ns]")).dropna()).dt.year)
        | set(pd.to_datetime(practical.get("Entry_Date", pd.Series(dtype="datetime64[ns]")).dropna()).dt.year)
    )
    rows = []
    for year in years:
        setup_year = setup.loc[pd.to_datetime(setup["Entry_Date"]).dt.year.eq(year)]
        practical_year = practical.loc[pd.to_datetime(practical["Entry_Date"]).dt.year.eq(year)]
        setup_metrics = summarize_lens(setup_year, "setup")
        practical_metrics = summarize_lens(practical_year, "practical")
        rows.append(
            {
                "Entry_Year": int(year),
                **{f"Setup_{key}": value for key, value in setup_metrics.items()},
                **{f"Practical_{key}": value for key, value in practical_metrics.items()},
            }
        )
    return pd.DataFrame(rows)


def outlier_robustness(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame:
    setup, practical = _paired_trades(setup, practical)
    if setup.empty:
        return pd.DataFrame(
            columns=[
                "Removed_Top_N",
                "Removed_Entry_IDs",
                "Removed_Symbols",
                "Remaining_Entry_Count",
                "Setup_Mean_Return",
                "Setup_Return_PF",
                "Practical_Mean_R",
                "Practical_R_PF",
            ]
        )
    ranked = setup.sort_values(["Return", "Entry_ID"], ascending=[False, True]).reset_index(drop=True)
    rows = []
    for count in (1, 3, 5):
        removed = ranked.head(count)
        remaining_ids = set(ranked.iloc[count:]["Entry_ID"])
        setup_remaining = setup.loc[setup["Entry_ID"].isin(remaining_ids)]
        practical_remaining = practical.loc[practical["Entry_ID"].isin(remaining_ids)]
        setup_metrics = summarize_lens(setup_remaining, "setup")
        practical_metrics = summarize_lens(practical_remaining, "practical")
        rows.append(
            {
                "Removed_Top_N": count,
                "Removed_Entry_IDs": ";".join(removed["Entry_ID"].astype(str)),
                "Removed_Symbols": ";".join(removed["Symbol"].astype(str)),
                "Remaining_Entry_Count": len(remaining_ids),
                "Setup_Mean_Return": setup_metrics["Mean_Return"],
                "Setup_Return_PF": setup_metrics["Return_PF"],
                "Practical_Mean_R": practical_metrics["Mean_R"],
                "Practical_R_PF": practical_metrics["R_PF"],
            }
        )
    return pd.DataFrame(rows)


def leave_one_symbol_out(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame:
    setup, practical = _paired_trades(setup, practical)
    symbols = sorted(set(setup.get("Symbol", pd.Series(dtype=str))))
    rows = []
    for symbol in symbols:
        setup_remaining = setup.loc[setup["Symbol"] != symbol]
        practical_remaining = practical.loc[practical["Symbol"] != symbol]
        setup_metrics = summarize_lens(setup_remaining, "setup")
        practical_metrics = summarize_lens(practical_remaining, "practical")
        rows.append(
            {
                "Omitted_Symbol": symbol,
                "Remaining_Entry_Count": len(setup_remaining),
                "Setup_Mean_Return": setup_metrics["Mean_Return"],
                "Setup_Return_PF": setup_metrics["Return_PF"],
                "Practical_Mean_R": practical_metrics["Mean_R"],
                "Practical_R_PF": practical_metrics["R_PF"],
            }
        )
    return pd.DataFrame(rows)


def overlap_diagnostic(practical: pd.DataFrame) -> pd.DataFrame:
    if practical.empty:
        return pd.DataFrame(
            [
                {
                    "Total_Accepted_Entries": 0,
                    "Entries_With_Another_Open_Same_Symbol_Trade": 0,
                    "Max_Simultaneous_Signal_Level_Trades": 0,
                    "Max_Same_Day_Entries": 0,
                }
            ]
        )
    data = practical.copy()
    data["Entry_Date"] = pd.to_datetime(data["Entry_Date"])
    data["Exit_Date"] = pd.to_datetime(data["Exit_Date"])
    overlap_count = 0
    max_simultaneous = 0
    for _, current in data.iterrows():
        others = data.loc[
            (data["Symbol"] == current["Symbol"])
            & (data["Entry_ID"] != current["Entry_ID"])
            & (data["Entry_Date"] <= current["Entry_Date"])
            & (data["Exit_Date"] >= current["Entry_Date"])
        ]
        overlap_count += int(not others.empty)
    dates = sorted(set(data["Entry_Date"]))
    for date in dates:
        open_at_date = data.loc[(data["Entry_Date"] <= date) & (data["Exit_Date"] >= date)]
        max_simultaneous = max(max_simultaneous, len(open_at_date))
    max_same_day = int(data["Entry_Date"].value_counts().max())
    return pd.DataFrame(
        [
            {
                "Total_Accepted_Entries": len(data),
                "Entries_With_Another_Open_Same_Symbol_Trade": overlap_count,
                "Max_Simultaneous_Signal_Level_Trades": max_simultaneous,
                "Max_Same_Day_Entries": max_same_day,
            }
        ]
    )


def breadth_summary(setup: pd.DataFrame, practical: pd.DataFrame) -> pd.DataFrame:
    setup, practical = _paired_trades(setup, practical)
    if "Regime" not in setup.columns:
        return pd.DataFrame()
    rows = []
    for regime in sorted(setup["Regime"].dropna().astype(str)):
        setup_regime = setup.loc[setup["Regime"].eq(regime)]
        practical_regime = practical.loc[practical["Regime"].eq(regime)]
        rows.append(
            {
                "Regime": regime,
                **{f"Setup_{key}": value for key, value in summarize_lens(setup_regime, "setup").items()},
                **{f"Practical_{key}": value for key, value in summarize_lens(practical_regime, "practical").items()},
            }
        )
    return pd.DataFrame(rows)


def evaluate_gates(
    setup: pd.DataFrame,
    practical: pd.DataFrame,
    *,
    point_in_time_violations: int = 0,
) -> pd.DataFrame:
    """Evaluate the precommitted V2 gates without optimizing any threshold."""

    setup, practical = _paired_trades(setup, practical)
    setup_metrics = summarize_lens(setup, "setup")
    practical_metrics = summarize_lens(practical, "practical")
    years = year_summary(setup, practical)
    qualifying_years = years.loc[
        (years["Setup_Completed_Trades"] >= 20)
        & (years["Setup_Mean_Return"] > 0)
        & (years["Setup_Return_PF"] >= 1.0)
        & (years["Practical_Mean_R"] > 0)
    ] if not years.empty else pd.DataFrame()
    outliers = outlier_robustness(setup, practical)
    leave_out = leave_one_symbol_out(setup, practical)
    rows = [
        {"Gate": "COMPLETED_TRADES", "Passed": len(setup) >= 100, "Value": len(setup)},
        {"Gate": "SETUP_MEAN_RETURN", "Passed": bool(setup_metrics["Mean_Return"] > 0), "Value": setup_metrics["Mean_Return"]},
        {"Gate": "SETUP_RETURN_PF", "Passed": bool(setup_metrics["Return_PF"] >= 1.20), "Value": setup_metrics["Return_PF"]},
        {"Gate": "PRACTICAL_MEAN_R", "Passed": bool(practical_metrics["Mean_R"] >= 0.15), "Value": practical_metrics["Mean_R"]},
        {"Gate": "PRACTICAL_R_PF", "Passed": bool(practical_metrics["R_PF"] >= 1.20), "Value": practical_metrics["R_PF"]},
        {"Gate": "TEMPORAL_ROBUSTNESS", "Passed": len(qualifying_years) >= 2, "Value": len(qualifying_years)},
        {
            "Gate": "TOP_FIVE_OUTLIER_ROBUSTNESS",
            "Passed": bool(
                not outliers.empty
                and outliers.loc[outliers["Removed_Top_N"].eq(5), "Setup_Mean_Return"].iloc[0] > 0
                and outliers.loc[outliers["Removed_Top_N"].eq(5), "Setup_Return_PF"].iloc[0] >= 1.0
            ),
            "Value": "top5",
        },
        {
            "Gate": "LEAVE_ONE_SYMBOL_OUT",
            "Passed": bool(
                not leave_out.empty
                and (leave_out["Setup_Mean_Return"] > 0).all()
                and (leave_out["Setup_Return_PF"] >= 1.0).all()
            ),
            "Value": len(leave_out),
        },
        {"Gate": "POINT_IN_TIME_INTEGRITY", "Passed": point_in_time_violations == 0, "Value": point_in_time_violations},
    ]
    all_passed = all(bool(row["Passed"]) for row in rows)
    status = "INSUFFICIENT_EVIDENCE" if len(setup) < 100 else ("PASS" if all_passed else "FAIL")
    rows.append({"Gate": "FINAL_STATUS", "Passed": status == "PASS", "Value": status, "Status": status})
    result = pd.DataFrame(rows)
    result["Status"] = result.get("Status", result["Passed"].map(lambda value: "PASS" if value else "FAIL"))
    result.loc[result["Gate"] != "FINAL_STATUS", "Status"] = result.loc[
        result["Gate"] != "FINAL_STATUS", "Passed"
    ].map(lambda value: "PASS" if value else "FAIL")
    return result


def _attach_breadth_to_lenses(setup: pd.DataFrame, practical: pd.DataFrame, breadth: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    joined_setup = attach_prior_breadth(setup, breadth)
    joined_practical = attach_prior_breadth(practical, breadth)
    return joined_setup, joined_practical


def _completed_trade_frames(entries: pd.DataFrame, membership: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    if entries.empty:
        return pd.DataFrame(), pd.DataFrame(), 0
    ticker_by_symbol = (
        membership.loc[:, ["Symbol", "Yahoo_Ticker"]]
        .drop_duplicates("Symbol")
        .set_index("Symbol")["Yahoo_Ticker"].to_dict()
    )
    setup_rows = []
    practical_rows = []
    incomplete = 0
    for symbol, group in entries.groupby("Symbol", sort=True):
        ticker = ticker_by_symbol.get(symbol, "")
        if not ticker:
            incomplete += len(group)
            continue
        try:
            prices = compute_price_features(download_adjusted_ohlcv(ticker, DOWNLOAD_START, DOWNLOAD_END_EXCLUSIVE))
        except Exception:
            incomplete += len(group)
            continue
        for _, entry in group.iterrows():
            setup_trade = simulate_setup_quality_trade(entry, prices)
            practical_trade = simulate_practical_trade(entry, prices)
            if setup_trade is None or practical_trade is None:
                incomplete += 1
                continue
            setup_rows.append(setup_trade)
            practical_rows.append(practical_trade)
    return pd.DataFrame(setup_rows), pd.DataFrame(practical_rows), incomplete


def _read_csv_or_empty(path: Path, **kwargs: object) -> pd.DataFrame:
    try:
        return pd.read_csv(path, **kwargs)
    except (pd.errors.EmptyDataError, FileNotFoundError):
        return pd.DataFrame()


def _write_report(
    output_dir: Path,
    validation: pd.DataFrame,
    rs_audit: pd.DataFrame,
    states: pd.DataFrame,
    signals: pd.DataFrame,
    entries: pd.DataFrame,
    cancellations: pd.DataFrame,
    setup: pd.DataFrame,
    practical: pd.DataFrame,
    year: pd.DataFrame,
    outliers: pd.DataFrame,
    leave_out: pd.DataFrame,
    breadth: pd.DataFrame,
    overlap: pd.DataFrame,
    gates: pd.DataFrame,
    incomplete: int,
) -> None:
    setup_metrics = summarize_lens(setup, "setup")
    practical_metrics = summarize_lens(practical, "practical")
    final_status = gates.loc[gates["Gate"].eq("FINAL_STATUS"), "Status"].iloc[0]
    lines = [
        "# Strategy V2 Quality-Base Breakout Validation",
        "",
        "## 1. Locked hypothesis",
        "Strategy V2 validates RS leader → pivot → quality base → volatility contraction → breakout → controlled next-session entry.",
        "Design spec: `Swing Trading/docs/superpowers/specs/2026-08-26-strategy-v2-quality-base-breakout-design.md`.",
        "",
        "## 2. Data and timing",
        "Signal window: 2023-08-01 through 2026-08-25. Yahoo Finance daily OHLCV uses `auto_adjust=True`; indicators use standard Wilder ATR14.",
        "Point-in-time membership: `market_breadth/config/nifty500_membership.csv`. Breadth is diagnostic-only and joined from a strictly prior date.",
        "",
        "## 3. Download and audit counts",
        f"Usable symbols: {int(validation['Usable'].sum()) if not validation.empty else 0}; audited symbols: {len(validation)}.",
        f"RS audit dates: {len(rs_audit)}; unsafe RS dates: {int((~rs_audit['RS_Research_Safe']).sum()) if not rs_audit.empty else 0}.",
        "",
        "## 4. RS coverage",
        f"Minimum coverage: {rs_audit['RS_Coverage'].min() if not rs_audit.empty else np.nan}; median: {rs_audit['RS_Coverage'].median() if not rs_audit.empty else np.nan}.",
        "",
        "## 5. Base events and rejections",
        f"Base events: {states['Event'].value_counts().to_dict() if not states.empty else {}}.",
        f"Signal rejection reasons: {signals['Signal_Rejection_Reason'].value_counts(dropna=False).to_dict() if not signals.empty else {}}.",
        "",
        "## 6. Signals and entries",
        f"Candidates: {len(signals)}; qualified signals: {int(signals['Signal_Qualified'].sum()) if not signals.empty else 0}; accepted entries: {len(entries)}; cancellations: {len(cancellations)}; incomplete outcomes: {incomplete}.",
        "",
        "## 7. Setup-quality headline metrics",
        f"{setup_metrics}",
        "",
        "## 8. Practical headline metrics",
        f"{practical_metrics}",
        "",
        "## 9. Entry-year summary",
        year.to_string(index=False) if not year.empty else "No completed trades.",
        "",
        "## 10. Top-1/3/5 winner robustness",
        outliers.to_string(index=False) if not outliers.empty else "No completed trades.",
        "",
        "## 11. Leave-one-symbol-out robustness",
        leave_out.to_string(index=False) if not leave_out.empty else "No completed trades.",
        "Full CSV: `v2_leave_one_symbol_out.csv`.",
        "",
        "## 12. Breadth diagnostic summary",
        breadth.to_string(index=False) if not breadth.empty else "No breadth-attached completed trades.",
        "",
        "## 13. Overlap diagnostic summary",
        overlap.to_string(index=False),
        "",
        "## 14. Precommitted gates",
        gates.to_string(index=False),
        "",
        f"## 15. Final status: {final_status}",
        "",
        "This report supplies locked evidence only. It does not tune Strategy V2 or prescribe a follow-up change. Portfolio Advisor retains the strategy decision.",
    ]
    (output_dir / "research_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[4]
    module_dir = Path(__file__).resolve().parent
    output_dir = module_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    membership = load_membership(root / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv")
    entries = _read_csv_or_empty(output_dir / "v2_entries.csv", parse_dates=["Signal_Date", "Entry_Date"])
    cancellations = _read_csv_or_empty(output_dir / "v2_entry_cancellations.csv", parse_dates=["Signal_Date", "Next_Session_Date"])
    candidates = _read_csv_or_empty(output_dir / "v2_signal_candidates.csv", parse_dates=["Seed_Date", "Signal_Date"])
    states = _read_csv_or_empty(output_dir / "v2_base_state_audit.csv", parse_dates=["Date", "Seed_Date"])
    validation = _read_csv_or_empty(output_dir / "v2_data_validation.csv")
    rs_audit = _read_csv_or_empty(output_dir / "v2_universe_rs_audit.csv", parse_dates=["Date"])
    setup, practical, incomplete = _completed_trade_frames(entries, membership)
    breadth_daily = pd.read_csv(
        root / "Swing Trading/research/swing/market_breadth/output/nifty500_breadth_daily.csv",
        parse_dates=["Date"],
    )
    setup, practical = _attach_breadth_to_lenses(setup, practical, breadth_daily)
    validate_trade_integrity(setup, practical)
    year = year_summary(setup, practical)
    outliers = outlier_robustness(setup, practical)
    leave_out = leave_one_symbol_out(setup, practical)
    breadth = breadth_summary(setup, practical)
    overlap = overlap_diagnostic(practical)
    gates = evaluate_gates(setup, practical)
    setup.to_csv(output_dir / "v2_setup_quality_trades.csv", index=False, date_format="%Y-%m-%d")
    practical.to_csv(output_dir / "v2_practical_trades.csv", index=False, date_format="%Y-%m-%d")
    pd.DataFrame(
        [
            {"Lens": "setup-quality", **summarize_lens(setup, "setup")},
            {"Lens": "practical", **summarize_lens(practical, "practical")},
        ]
    ).to_csv(output_dir / "v2_validation_summary.csv", index=False)
    year.to_csv(output_dir / "v2_year_summary.csv", index=False)
    outliers.to_csv(output_dir / "v2_outlier_robustness.csv", index=False)
    leave_out.to_csv(output_dir / "v2_leave_one_symbol_out.csv", index=False)
    breadth.to_csv(output_dir / "v2_breadth_summary.csv", index=False)
    overlap.to_csv(output_dir / "v2_overlap_diagnostic.csv", index=False)
    gates.to_csv(output_dir / "v2_validation_gates.csv", index=False)
    _write_report(
        output_dir,
        validation,
        rs_audit,
        states,
        candidates,
        entries,
        cancellations,
        setup,
        practical,
        year,
        outliers,
        leave_out,
        breadth,
        overlap,
        gates,
        incomplete,
    )
    print(gates.to_string(index=False))
