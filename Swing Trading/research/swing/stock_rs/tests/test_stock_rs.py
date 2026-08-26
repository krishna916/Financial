import math
from pathlib import Path
import sys

import pandas as pd
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from research.swing.stock_rs.build_stock_rs import (  # noqa: E402
    assign_rs_status,
    build_stock_summary,
    calculate_returns,
    calculate_daily_stock_rs,
    EXPECTED_TICKERS,
    LATEST_INCLUDED_DATE,
    PRIMARY_COLUMNS,
    SUMMARY_COLUMNS,
    START_DATE,
    VALIDATION_COLUMNS,
    load_stock_config,
    normalize_yahoo_frame,
    validate_primary_output,
)


BASE_DIR = Path(__file__).resolve().parents[1]


def test_stock_config_is_exact_fixed_twenty_stock_universe():
    df = pd.read_csv(BASE_DIR / "stock_ticker_config.csv", dtype=str)
    assert df.columns.tolist() == ["Symbol", "Yahoo_Ticker"]
    assert len(df) == 20
    assert df["Symbol"].is_unique
    assert df["Yahoo_Ticker"].is_unique
    mapping = dict(zip(df["Symbol"], df["Yahoo_Ticker"]))
    assert mapping["M&M"] == "M&M.NS"
    assert mapping["HDFCBANK"] == "HDFCBANK.NS"
    assert mapping["ULTRACEMCO"] == "ULTRACEMCO.NS"


def test_load_stock_config_enforces_the_complete_locked_mapping():
    config = load_stock_config()
    assert dict(zip(config["Symbol"], config["Yahoo_Ticker"])) == EXPECTED_TICKERS


def test_calculate_returns_uses_exact_adjusted_close_session_shifts():
    df = pd.DataFrame({"Adj_Close": [100.0 + i for i in range(140)]})
    result = calculate_returns(df)
    assert pd.isna(result.loc[20, "Ret21"])
    assert math.isclose(result.loc[21, "Ret21"], 121.0 / 100.0 - 1.0)
    assert math.isclose(result.loc[63, "Ret63"], 163.0 / 100.0 - 1.0)
    assert math.isclose(result.loc[126, "Ret126"], 226.0 / 100.0 - 1.0)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100.0, "PREFERRED"),
        (80.0, "PREFERRED"),
        (79.999, "VALID"),
        (70.0, "VALID"),
        (69.999, "BELOW_VALID"),
        (5.0, "BELOW_VALID"),
    ],
)
def test_assign_rs_status_uses_locked_v1_thresholds(score, expected):
    assert assign_rs_status(score) == expected


def _synthetic_stock_rs_rows(date, count=20, offset=0):
    return [
        {
            "Date": pd.Timestamp(date),
            "Symbol": f"S{i:02d}",
            "Yahoo_Ticker": f"S{i:02d}.NS",
            "Close": 100.0,
            "Adj_Close": 100.0,
            "Ret21": float(i + offset),
            "Ret63": float(i + offset),
            "Ret126": float(i + offset),
        }
        for i in range(count)
    ]


def test_daily_rs_percentiles_and_composite_rank_strongest_stock_first():
    result = calculate_daily_stock_rs(
        pd.DataFrame(_synthetic_stock_rs_rows("2026-01-02"))
    )
    strongest = result.loc[result["Symbol"].eq("S19")].iloc[0]
    weakest = result.loc[result["Symbol"].eq("S00")].iloc[0]
    assert len(result) == 20
    assert strongest["RS21_Percentile"] == 100.0
    assert strongest["Composite_RS"] == 100.0
    assert strongest["Composite_Rank"] == 1
    assert strongest["RS_Status"] == "PREFERRED"
    assert weakest["RS21_Percentile"] == 5.0
    assert weakest["Composite_Rank"] == 20
    assert result["Stock_Count"].eq(20).all()
    assert result["Is_Full_Universe"].all()


def test_daily_rs_excludes_dates_without_the_full_twenty_stock_universe():
    rows = _synthetic_stock_rs_rows("2026-01-02")
    rows.extend(_synthetic_stock_rs_rows("2026-01-03", count=19, offset=20))
    result = calculate_daily_stock_rs(pd.DataFrame(rows))
    assert result["Date"].eq(pd.Timestamp("2026-01-02")).all()
    assert len(result) == 20


def test_daily_rs_composite_uses_locked_thirty_forty_thirty_weights():
    result = calculate_daily_stock_rs(
        pd.DataFrame(_synthetic_stock_rs_rows("2026-01-02"))
    )
    target = result.loc[result["Symbol"].eq("S07")].iloc[0]
    expected = (
        0.30 * target["RS21_Percentile"]
        + 0.40 * target["RS63_Percentile"]
        + 0.30 * target["RS126_Percentile"]
    )
    assert target["Composite_RS"] == pytest.approx(expected)


def test_normalize_yahoo_frame_handles_single_level_columns_and_sorts_dates():
    downloaded = pd.DataFrame(
        {
            "Close": [101.0, 100.0],
            "Adj Close": [100.5, 99.5],
        },
        index=pd.to_datetime(["2026-01-03", "2026-01-02"]),
    )
    result = normalize_yahoo_frame(downloaded, "SBIN", "SBIN.NS")
    assert result.columns.tolist() == [
        "Date",
        "Symbol",
        "Yahoo_Ticker",
        "Close",
        "Adj_Close",
    ]
    assert result["Date"].tolist() == list(
        pd.to_datetime(["2026-01-02", "2026-01-03"])
    )
    assert result["Symbol"].tolist() == ["SBIN", "SBIN"]
    assert result["Yahoo_Ticker"].tolist() == ["SBIN.NS", "SBIN.NS"]
    assert result["Close"].tolist() == [100.0, 101.0]
    assert result["Adj_Close"].tolist() == [99.5, 100.5]


def test_normalize_yahoo_frame_handles_one_ticker_multiindex_columns():
    columns = pd.MultiIndex.from_tuples(
        [("Close", "SBIN.NS"), ("Adj Close", "SBIN.NS")]
    )
    downloaded = pd.DataFrame(
        [[100.0, 99.5], [101.0, 100.5]],
        columns=columns,
        index=pd.to_datetime(["2026-01-02", "2026-01-03"]),
    )
    result = normalize_yahoo_frame(downloaded, "SBIN", "SBIN.NS")
    assert result[["Close", "Adj_Close"]].to_dict("list") == {
        "Close": [100.0, 101.0],
        "Adj_Close": [99.5, 100.5],
    }


def test_normalize_yahoo_frame_handles_yahoo_named_date_index():
    downloaded = pd.DataFrame(
        {
            "Close": [100.0, 101.0],
            "Adj Close": [99.5, 100.5],
        },
        index=pd.DatetimeIndex(["2026-01-02", "2026-01-03"], name="Date"),
    )
    result = normalize_yahoo_frame(downloaded, "SBIN", "SBIN.NS")
    assert result.index.name is None
    assert result["Date"].tolist() == list(
        pd.to_datetime(["2026-01-02", "2026-01-03"])
    )


def test_normalize_yahoo_frame_rejects_missing_adjusted_close():
    downloaded = pd.DataFrame(
        {"Close": [100.0]}, index=pd.to_datetime(["2026-01-02"])
    )
    with pytest.raises(ValueError, match="Adj Close"):
        normalize_yahoo_frame(downloaded, "SBIN", "SBIN.NS")


@pytest.mark.parametrize("date", ["2021-12-31", "2026-08-26"])
def test_normalize_yahoo_frame_rejects_dates_outside_locked_window(date):
    downloaded = pd.DataFrame(
        {
            "Close": [100.0],
            "Adj Close": [99.5],
        },
        index=pd.to_datetime([date]),
    )
    with pytest.raises(ValueError, match="date outside locked range"):
        normalize_yahoo_frame(downloaded, "SBIN", "SBIN.NS")


def test_validate_primary_output_accepts_a_valid_full_universe_frame():
    result = calculate_daily_stock_rs(
        pd.DataFrame(_synthetic_stock_rs_rows("2026-01-02"))
    )
    validate_primary_output(result)


def test_build_stock_summary_reconciles_locked_status_counts():
    result = calculate_daily_stock_rs(
        pd.DataFrame(_synthetic_stock_rs_rows("2026-01-02"))
    )
    summary = build_stock_summary(result)
    assert summary.columns.tolist() == [
        "Symbol",
        "Yahoo_Ticker",
        "Valid_Ranked_Days",
        "Preferred_Days",
        "Valid_Days",
        "Below_Valid_Days",
        "Earliest_Ranked_Date",
        "Latest_Ranked_Date",
        "Mean_Composite_RS",
        "Median_Composite_RS",
    ]
    assert len(summary) == 20
    assert (
        summary["Preferred_Days"]
        + summary["Valid_Days"]
        + summary["Below_Valid_Days"]
    ).eq(summary["Valid_Ranked_Days"]).all()


def test_daily_rs_rejects_duplicate_date_symbol_rows():
    rows = _synthetic_stock_rs_rows("2026-01-02")
    rows.append(rows[0].copy())
    with pytest.raises(ValueError, match="duplicate"):
        calculate_daily_stock_rs(pd.DataFrame(rows))


def test_validate_primary_output_rejects_invalid_rank_set():
    result = calculate_daily_stock_rs(
        pd.DataFrame(_synthetic_stock_rs_rows("2026-01-02"))
    )
    result.loc[result["Symbol"].eq("S19"), "Composite_Rank"] = 21
    with pytest.raises(ValueError, match="ranks 1..20"):
        validate_primary_output(result)


def test_validate_primary_output_rejects_invalid_universe_count():
    result = calculate_daily_stock_rs(
        pd.DataFrame(_synthetic_stock_rs_rows("2026-01-02"))
    )
    result.loc[0, "Stock_Count"] = 19
    with pytest.raises(ValueError, match="Stock_Count"):
        validate_primary_output(result)


def test_validate_primary_output_rejects_invalid_universe_flag():
    result = calculate_daily_stock_rs(
        pd.DataFrame(_synthetic_stock_rs_rows("2026-01-02"))
    )
    result.loc[0, "Is_Full_Universe"] = False
    with pytest.raises(ValueError, match="full-universe"):
        validate_primary_output(result)


def test_validate_primary_output_rejects_invalid_status():
    result = calculate_daily_stock_rs(
        pd.DataFrame(_synthetic_stock_rs_rows("2026-01-02"))
    )
    result.loc[0, "RS_Status"] = "STRONG"
    with pytest.raises(ValueError, match="RS_Status"):
        validate_primary_output(result)


@pytest.mark.parametrize("date", ["2021-12-31", "2026-08-26"])
def test_validate_primary_output_rejects_dates_outside_locked_window(date):
    result = calculate_daily_stock_rs(
        pd.DataFrame(_synthetic_stock_rs_rows("2026-01-02"))
    )
    result.loc[:, "Date"] = pd.Timestamp(date)
    with pytest.raises(ValueError, match="date outside locked range"):
        validate_primary_output(result)


def test_validate_primary_output_rejects_status_threshold_mismatch():
    result = calculate_daily_stock_rs(
        pd.DataFrame(_synthetic_stock_rs_rows("2026-01-02"))
    )
    result.loc[result["Symbol"].eq("S19"), "RS_Status"] = "BELOW_VALID"
    with pytest.raises(ValueError, match="RS_Status does not match"):
        validate_primary_output(result)


def test_daily_rs_ties_rank_by_symbol_ascending_after_composite_sort():
    rows = _synthetic_stock_rs_rows("2026-01-02")
    for row in rows:
        row["Ret21"] = 1.0
        row["Ret63"] = 1.0
        row["Ret126"] = 1.0
    result = calculate_daily_stock_rs(pd.DataFrame(rows))
    assert result["Symbol"].tolist() == [f"S{i:02d}" for i in range(20)]
    assert result["Composite_Rank"].tolist() == list(range(1, 21))


def test_committed_artifacts_match_stock_rs_contracts():
    output_dir = BASE_DIR / "output"
    daily = pd.read_csv(output_dir / "stock_rs_daily.csv", parse_dates=["Date"])
    summary = pd.read_csv(output_dir / "stock_rs_summary.csv")
    validation = pd.read_csv(output_dir / "stock_rs_validation.csv")
    start = pd.Timestamp(START_DATE)

    assert daily.columns.tolist() == PRIMARY_COLUMNS
    assert summary.columns.tolist() == SUMMARY_COLUMNS
    assert validation.columns.tolist() == VALIDATION_COLUMNS
    assert not daily.empty
    assert daily["Date"].between(start, LATEST_INCLUDED_DATE).all()
    assert daily["Symbol"].nunique() == 20
    assert daily[["Date", "Symbol"]].duplicated().sum() == 0
    assert daily["Stock_Count"].eq(20).all()
    assert daily["Is_Full_Universe"].eq(True).all()
    assert daily.groupby("Date")["Symbol"].nunique().eq(20).all()
    assert daily.groupby("Date")["Composite_Rank"].apply(
        lambda values: set(values) == set(range(1, 21))
    ).all()
    assert validation["Download_Status"].eq("OK").all()
    assert len(validation) == 20
    assert len(summary) == 20
    assert (
        summary["Preferred_Days"]
        + summary["Valid_Days"]
        + summary["Below_Valid_Days"]
    ).eq(summary["Valid_Ranked_Days"]).all()
