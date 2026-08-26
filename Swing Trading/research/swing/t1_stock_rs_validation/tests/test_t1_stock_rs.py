import hashlib
import math
from pathlib import Path
import sys

import pandas as pd
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from research.swing.t1_stock_rs_validation.analyze_t1_stock_rs import (  # noqa: E402
    ALLOWED_RS_STATUSES,
    EXPECTED_T1_SHA256,
    STOCK_RS_PATH,
    T1_TRADES_PATH,
    calculate_profit_factor,
    calculate_trade_metrics,
    join_stock_rs_at_decision_time,
    join_market_regime_strictly_before_entry,
    join_sector_leadership_strictly_before_entry,
    load_and_validate_market_regime,
    load_and_validate_mapping,
    load_and_validate_sector_data,
    load_and_validate_stock_rs,
    load_and_validate_trades,
    prepare_joined_trade_export,
    summarize_composite_ranks,
    summarize_by_entry_year,
    summarize_leave_one_symbol_out,
    summarize_market_interactions,
    summarize_outlier_robustness,
    summarize_primary_binary_tests,
    summarize_status_groups,
    summarize_symbol_status,
    summarize_sector_interactions,
    validate_stock_rs_join,
    validate_context_joins,
)


def test_locked_t1_input_is_exact_218_trade_sample():
    raw = T1_TRADES_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_T1_SHA256

    trades = load_and_validate_trades(T1_TRADES_PATH)
    assert len(trades) == 218
    assert trades["Symbol"].nunique() == 20
    assert int((trades["Return_Pct"] > 0).sum()) == 76
    assert math.isclose(float(trades["PnL"].sum()), -4631.32, abs_tol=0.01)
    assert math.isclose(float(trades["Return_Pct"].mean()), -0.0548680341, abs_tol=1e-8)


def test_stock_rs_input_is_research_safe_and_locked():
    rs = load_and_validate_stock_rs(STOCK_RS_PATH)
    assert set(rs["RS_Status"].unique()) <= ALLOWED_RS_STATUSES
    assert (rs["Stock_Count"] == 20).all()
    assert rs["Is_Full_Universe"].all()
    assert rs["Composite_Rank"].between(1, 20).all()
    assert not rs.duplicated(["Date", "Symbol"]).any()


def test_load_and_validate_trades_rejects_duplicate_normalized_trade_key(tmp_path):
    trades = pd.read_csv(T1_TRADES_PATH)
    duplicate = pd.concat([trades, trades.iloc[[0]]], ignore_index=True)
    path = tmp_path / "duplicate.csv"
    duplicate.to_csv(path, index=False)

    with pytest.raises(ValueError, match="duplicate normalized trade keys"):
        load_and_validate_trades(path)


def test_calculate_trade_metrics_uses_locked_definitions():
    trades = pd.DataFrame(
        {
            "Return_Pct": [0.10, 0.05, -0.10, -0.20],
            "PnL": [100.0, 50.0, -40.0, -60.0],
            "Holding_Days": [5, 7, 9, 11],
        }
    )

    result = calculate_trade_metrics(trades)

    assert result["Trades"] == 4
    assert result["Winners"] == 2
    assert result["Losers"] == 2
    assert result["Win_Rate"] == 50.0
    assert result["Mean_Return"] == -0.0375
    assert result["Median_Return"] == -0.025
    assert result["Average_Winner"] == pytest.approx(0.075)
    assert result["Average_Loser"] == pytest.approx(-0.15)
    assert result["Payoff_Ratio"] == pytest.approx(0.5)
    assert result["Return_Profit_Factor"] == pytest.approx(0.5)
    assert result["PnL_Profit_Factor"] == pytest.approx(1.5)
    assert result["Total_PnL"] == pytest.approx(50.0)
    assert result["Median_Holding_Days"] == pytest.approx(8.0)


def test_calculate_profit_factor_handles_locked_edge_behavior():
    assert calculate_profit_factor(pd.Series([2.0, -1.0])) == 2.0
    assert math.isinf(calculate_profit_factor(pd.Series([2.0, 0.0])))
    assert calculate_profit_factor(pd.Series([-2.0, 0.0])) == 0.0
    assert math.isnan(calculate_profit_factor(pd.Series([0.0, 0.0])))


def _synthetic_rs_row(date, symbol, composite_rs, rank):
    return {
        "Date": pd.Timestamp(date),
        "Symbol": symbol,
        "Ret21": 0.10,
        "Ret63": 0.20,
        "Ret126": 0.30,
        "RS21_Percentile": 80.0,
        "RS63_Percentile": 80.0,
        "RS126_Percentile": 80.0,
        "Composite_RS": composite_rs,
        "Composite_Rank": rank,
        "Stock_Count": 20,
        "Is_Full_Universe": True,
        "RS_Status": "PREFERRED" if composite_rs >= 80 else "VALID",
    }


def test_stock_rs_join_forbids_same_entry_day_observation():
    trades = pd.DataFrame(
        {"Symbol": ["SBIN"], "Entry_Date": [pd.Timestamp("2026-01-05")]}
    )
    rs = pd.DataFrame(
        [
            _synthetic_rs_row("2026-01-02", "SBIN", 70.0, 2),
            _synthetic_rs_row("2026-01-05", "SBIN", 90.0, 1),
        ]
    )

    result = join_stock_rs_at_decision_time(trades, rs)

    assert result.loc[0, "RS_Matched_Date"] == pd.Timestamp("2026-01-02")
    assert result.loc[0, "Composite_RS"] == 70.0


def test_stock_rs_join_never_forward_matches_future_observation():
    trades = pd.DataFrame(
        {"Symbol": ["SBIN"], "Entry_Date": [pd.Timestamp("2026-01-04")]}
    )
    rs = pd.DataFrame([_synthetic_rs_row("2026-01-05", "SBIN", 90.0, 1)])

    result = join_stock_rs_at_decision_time(trades, rs)

    assert pd.isna(result.loc[0, "RS_Matched_Date"])
    assert pd.isna(result.loc[0, "Composite_RS"])


def test_stock_rs_join_isolated_by_symbol():
    trades = pd.DataFrame(
        {"Symbol": ["SBIN"], "Entry_Date": [pd.Timestamp("2026-01-05")]}
    )
    rs = pd.DataFrame(
        [
            _synthetic_rs_row("2026-01-02", "SBIN", 71.0, 2),
            _synthetic_rs_row("2026-01-02", "INFY", 99.0, 1),
        ]
    )

    result = join_stock_rs_at_decision_time(trades, rs)

    assert result.loc[0, "Symbol"] == "SBIN"
    assert result.loc[0, "Composite_RS"] == 71.0


def test_stock_rs_join_exports_calendar_lag():
    trades = pd.DataFrame(
        {"Symbol": ["SBIN"], "Entry_Date": [pd.Timestamp("2026-01-05")]}
    )
    rs = pd.DataFrame([_synthetic_rs_row("2026-01-02", "SBIN", 71.0, 2)])

    result = join_stock_rs_at_decision_time(trades, rs)

    assert result.loc[0, "RS_Date_Lag_Days"] == 3
    assert result.loc[0, "RS_Date_Lag_Days"] > 0


def test_real_stock_rs_join_is_complete_and_reconciles_locked_t1_input():
    trades = load_and_validate_trades(T1_TRADES_PATH)
    rs = load_and_validate_stock_rs(STOCK_RS_PATH)

    joined = join_stock_rs_at_decision_time(trades, rs)
    validate_stock_rs_join(joined)

    assert len(joined) == 218
    assert joined["RS_Matched_Date"].notna().all()
    assert (joined["RS_Matched_Date"] < joined["Entry_Date"]).all()
    assert (joined["RS_Date_Lag_Days"] > 0).all()
    assert joined["Stock_Count"].eq(20).all()
    assert joined["Is_Full_Universe"].eq(True).all()
    assert joined["Composite_Rank"].between(1, 20).all()
    assert math.isclose(float(joined["PnL"].sum()), -4631.32, abs_tol=0.01)


def test_status_summary_preserves_locked_status_order_and_metrics():
    joined = pd.DataFrame(
        {
            "RS_Status": ["BELOW_VALID", "PREFERRED", "VALID"],
            "Return_Pct": [1.0, 2.0, -1.0],
            "PnL": [10.0, 20.0, -5.0],
            "Holding_Days": [3, 4, 5],
        }
    )

    result = summarize_status_groups(joined)

    assert result["RS_Status"].tolist() == ["PREFERRED", "VALID", "BELOW_VALID"]
    assert result.columns.tolist() == ["RS_Status", *[
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
    ]]
    assert result["Trades"].tolist() == [1, 1, 1]


def test_status_summary_reconciles_canonical_join():
    trades = load_and_validate_trades(T1_TRADES_PATH)
    rs = load_and_validate_stock_rs(STOCK_RS_PATH)
    joined = join_stock_rs_at_decision_time(trades, rs)

    result = summarize_status_groups(joined)

    assert result["Trades"].sum() == 218
    assert math.isclose(float(result["Total_PnL"].sum()), -4631.32, abs_tol=0.01)


def test_joined_trade_export_uses_locked_columns_and_sort_order():
    joined = pd.DataFrame(
        {
            "Symbol": ["SBIN", "ADANIENT"],
            "Entry_Date": pd.to_datetime(["2024-02-01", "2024-01-01"]),
            "Exit_Date": pd.to_datetime(["2024-02-02", "2024-01-03"]),
            "Entry_Price": [2.0, 1.0],
            "Exit_Price": [2.1, 1.1],
            "Qty": [1, 1],
            "Return_Pct": [5.0, 10.0],
            "PnL": [1.0, 2.0],
            "Holding_Days": [1, 2],
            "Source_Log": ["b", "a"],
            "RS_Matched_Date": pd.to_datetime(["2024-01-31", "2023-12-29"]),
            "RS_Date_Lag_Days": [1, 3],
            "Ret21": [0.1, 0.2],
            "Ret63": [0.1, 0.2],
            "Ret126": [0.1, 0.2],
            "RS21_Percentile": [80.0, 90.0],
            "RS63_Percentile": [80.0, 90.0],
            "RS126_Percentile": [80.0, 90.0],
            "Composite_RS": [80.0, 90.0],
            "Composite_Rank": [2, 1],
            "Stock_Count": [20, 20],
            "Is_Full_Universe": [True, True],
            "RS_Status": ["PREFERRED", "PREFERRED"],
        }
    )

    result = prepare_joined_trade_export(joined)

    assert result.columns.tolist() == [
        "Symbol", "Entry_Date", "Exit_Date", "Entry_Price", "Exit_Price", "Qty",
        "Return_Pct", "PnL", "Holding_Days", "Source_Log", "RS_Matched_Date",
        "RS_Date_Lag_Days", "Ret21", "Ret63", "Ret126", "RS21_Percentile",
        "RS63_Percentile", "RS126_Percentile", "Composite_RS", "Composite_Rank",
        "Stock_Count", "Is_Full_Universe", "RS_Status",
    ]
    assert result["Symbol"].tolist() == ["ADANIENT", "SBIN"]


def test_primary_binary_tests_use_only_the_two_locked_partitions():
    joined = pd.DataFrame(
        {
            "RS_Status": ["PREFERRED", "VALID", "BELOW_VALID"],
            "Return_Pct": [1.0, 2.0, -1.0],
            "PnL": [10.0, 20.0, -5.0],
            "Holding_Days": [3, 4, 5],
        }
    )

    result = summarize_primary_binary_tests(joined)

    assert result[["Comparison", "Group"]].to_records(index=False).tolist() == [
        ("PREFERRED_TEST", "PREFERRED"),
        ("PREFERRED_TEST", "NON_PREFERRED"),
        ("VALID_OR_BETTER_TEST", "VALID_OR_BETTER"),
        ("VALID_OR_BETTER_TEST", "BELOW_VALID"),
    ]
    assert result["Trades"].tolist() == [1, 2, 2, 1]


def test_primary_binary_tests_reconcile_canonical_join():
    trades = load_and_validate_trades(T1_TRADES_PATH)
    rs = load_and_validate_stock_rs(STOCK_RS_PATH)
    joined = join_stock_rs_at_decision_time(trades, rs)

    result = summarize_primary_binary_tests(joined)

    for comparison in ["PREFERRED_TEST", "VALID_OR_BETTER_TEST"]:
        part = result.loc[result["Comparison"].eq(comparison)]
        assert part["Trades"].sum() == 218
        assert math.isclose(float(part["Total_PnL"].sum()), -4631.32, abs_tol=0.01)


def test_rank_summary_preserves_exact_rank_identity_without_bucketing():
    joined = pd.DataFrame(
        {
            "Composite_Rank": [1, 2, 20],
            "Composite_RS": [99.0, 85.0, 20.0],
            "Return_Pct": [1.0, 2.0, -1.0],
            "PnL": [10.0, 20.0, -5.0],
            "Holding_Days": [3, 4, 5],
        }
    )

    result = summarize_composite_ranks(joined)

    assert result["Composite_Rank"].tolist() == list(range(1, 21))
    assert result.loc[result["Composite_Rank"].eq(1), "Trades"].item() == 1
    assert result.loc[result["Composite_Rank"].eq(2), "Trades"].item() == 1
    assert result.loc[result["Composite_Rank"].eq(20), "Trades"].item() == 1
    assert not result.astype(str).apply(
        lambda column: column.str.contains(
            "TOP_5|TOP_8|TOP_10|TOP_HALF|OPTIMAL_CUTOFF", regex=True
        ).any()
    ).any()


def test_rank_summary_canonical_output_has_all_diagnostic_ranks():
    trades = load_and_validate_trades(T1_TRADES_PATH)
    rs = load_and_validate_stock_rs(STOCK_RS_PATH)
    joined = join_stock_rs_at_decision_time(trades, rs)

    result = summarize_composite_ranks(joined)

    assert result["Composite_Rank"].tolist() == list(range(1, 21))
    assert result["Trades"].sum() == 218


def _synthetic_robustness_frame():
    return pd.DataFrame(
        {
            "Symbol": ["A", "A", "B", "B", "C"],
            "Entry_Date": pd.to_datetime(
                ["2023-01-03", "2024-01-03", "2025-01-03", "2026-01-03", "2026-02-03"]
            ),
            "Exit_Date": pd.to_datetime(
                ["2023-01-04", "2024-01-04", "2025-01-04", "2026-01-04", "2026-02-04"]
            ),
            "RS_Status": ["PREFERRED", "VALID", "BELOW_VALID", "PREFERRED", "VALID"],
            "Composite_Rank": [1, 2, 20, 1, 2],
            "Composite_RS": [90.0, 75.0, 20.0, 95.0, 72.0],
            "Return_Pct": [1.0, -1.0, 2.0, 3.0, -2.0],
            "PnL": [100.0, -20.0, 50.0, 200.0, 10.0],
            "Holding_Days": [1, 2, 3, 4, 5],
        }
    )


def test_year_summary_uses_only_the_four_locked_entry_years():
    result = summarize_by_entry_year(_synthetic_robustness_frame())

    assert set(result["Entry_Year"]) <= {2023, 2024, 2025, 2026}
    assert set(result["Entry_Year"]) == {2023, 2024, 2025, 2026}
    assert set(result["Comparison"]) == {"PREFERRED_TEST", "VALID_OR_BETTER_TEST"}


def test_outlier_robustness_excludes_only_global_positive_pnl_trades():
    result = summarize_outlier_robustness(_synthetic_robustness_frame())

    assert result["Scenario"].drop_duplicates().tolist() == [
        "ALL_TRADES",
        "EXCLUDE_TOP_1_POSITIVE_PNL",
        "EXCLUDE_TOP_3_POSITIVE_PNL",
        "EXCLUDE_TOP_5_POSITIVE_PNL",
    ]
    top_three = result.loc[
        result["Scenario"].eq("EXCLUDE_TOP_3_POSITIVE_PNL"), "Excluded_Trades"
    ].iloc[0]
    assert "B|2026-01-03|200.00" in top_three
    assert "A|2023-01-03|100.00" in top_three
    assert "B|2025-01-03|50.00" in top_three
    assert "-20.00" not in top_three


def test_symbol_status_summary_retains_observed_cells_and_flags_small_samples():
    result = summarize_symbol_status(_synthetic_robustness_frame())

    assert result[["Symbol", "RS_Status"]].to_records(index=False).tolist() == [
        ("A", "PREFERRED"),
        ("A", "VALID"),
        ("B", "PREFERRED"),
        ("B", "BELOW_VALID"),
        ("C", "VALID"),
    ]
    assert result["Small_Sample"].all()


def test_leave_one_symbol_out_excludes_exactly_the_requested_symbol():
    result = summarize_leave_one_symbol_out(_synthetic_robustness_frame())

    assert result["Excluded_Symbol"].unique().tolist() == ["A", "B", "C"]
    assert len(result) == 3 * 2 * 2
    for excluded in result["Excluded_Symbol"].unique():
        remaining = _synthetic_robustness_frame().loc[
            ~_synthetic_robustness_frame()["Symbol"].eq(excluded)
        ]
        assert remaining["Symbol"].nunique() == 2


def test_robustness_summaries_reconcile_canonical_join():
    trades = load_and_validate_trades(T1_TRADES_PATH)
    rs = load_and_validate_stock_rs(STOCK_RS_PATH)
    joined = join_stock_rs_at_decision_time(trades, rs)

    years = summarize_by_entry_year(joined)
    outliers = summarize_outlier_robustness(joined)
    symbols = summarize_symbol_status(joined)
    leave_one = summarize_leave_one_symbol_out(joined)

    assert set(years["Entry_Year"]) == {2023, 2024, 2025, 2026}
    assert outliers["Scenario"].nunique() == 4
    assert len(symbols) >= 20
    assert leave_one["Excluded_Symbol"].nunique() == 20


def test_market_join_forbids_same_entry_day_context():
    trades = pd.DataFrame(
        {"Symbol": ["SBIN"], "Entry_Date": [pd.Timestamp("2026-01-05")]}
    )
    market = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-01-02", "2026-01-05"]),
            "Regime": ["RISK_ON", "RISK_OFF"],
        }
    )

    result = join_market_regime_strictly_before_entry(trades, market)

    assert result.loc[0, "Market_Matched_Date"] == pd.Timestamp("2026-01-02")
    assert result.loc[0, "Market_Regime"] == "RISK_ON"
    assert result.loc[0, "Market_Date_Lag_Days"] == 3


def test_sector_join_uses_only_prior_full_universe_context():
    trades = pd.DataFrame(
        {
            "Symbol": ["SBIN"],
            "Entry_Date": [pd.Timestamp("2026-01-05")],
            "Sector_Key": ["BANK"],
        }
    )
    sector = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-01-02", "2026-01-05"]),
            "Sector_Key": ["BANK", "BANK"],
            "Composite_RS": [70.0, 95.0],
            "Composite_Rank": [4, 1],
            "Sector_Count": [11, 10],
            "Is_Full_Universe": [True, False],
            "Leadership_Bucket": ["LEADING", "LAGGING"],
        }
    )

    result = join_sector_leadership_strictly_before_entry(trades, sector)

    assert result.loc[0, "Sector_Matched_Date"] == pd.Timestamp("2026-01-02")
    assert result.loc[0, "Leadership_Bucket"] == "LEADING"
    assert result.loc[0, "Sector_Date_Lag_Days"] == 3
    assert result.loc[0, "Sector_Count"] == 11


def test_context_joins_reconcile_canonical_inputs_with_strict_timing():
    trades = load_and_validate_trades(T1_TRADES_PATH)
    rs = load_and_validate_stock_rs(STOCK_RS_PATH)
    mapping = load_and_validate_mapping()
    market = load_and_validate_market_regime()
    sector = load_and_validate_sector_data()
    joined = join_stock_rs_at_decision_time(trades, rs).merge(
        mapping.rename(columns={"Stock": "Symbol"}), on="Symbol", how="left", validate="many_to_one"
    )
    joined = join_market_regime_strictly_before_entry(joined, market)
    joined = join_sector_leadership_strictly_before_entry(joined, sector)
    validate_context_joins(joined)

    assert len(joined) == 218
    assert (joined["Market_Matched_Date"] < joined["Entry_Date"]).all()
    assert (joined["Market_Date_Lag_Days"] > 0).all()
    assert (joined["Sector_Matched_Date"] < joined["Entry_Date"]).all()
    assert (joined["Sector_Date_Lag_Days"] > 0).all()
    assert joined["Sector_Count"].eq(11).all()
    assert set(joined["Market_Regime"]) <= {"RISK_ON", "MIXED", "RISK_OFF"}
    assert set(joined["Leadership_Bucket"]) <= {
        "LEADING", "ACCEPTABLE", "WEAK", "LAGGING"
    }


def test_interaction_outputs_have_locked_sections_and_small_sample_flags():
    frame = _synthetic_robustness_frame().assign(
        Market_Regime=["RISK_ON", "RISK_ON", "MIXED", "RISK_OFF", "RISK_OFF"],
        Leadership_Bucket=["LEADING", "ACCEPTABLE", "WEAK", "LAGGING", "LEADING"],
    )

    market = summarize_market_interactions(frame)
    sector = summarize_sector_interactions(frame)

    assert set(market["Analysis_Type"]) == {
        "STATUS_MATRIX", "BINARY_WITHIN_REGIME"
    }
    assert set(sector["Analysis_Type"]) == {
        "STATUS_MATRIX", "BINARY_WITHIN_SECTOR_BUCKET"
    }
    assert market["Small_Sample"].all()
    assert sector["Small_Sample"].all()
