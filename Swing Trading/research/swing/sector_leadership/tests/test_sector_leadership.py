import math

import numpy as np
import pandas as pd
import pytest

import research.swing.sector_leadership.build_sector_leadership as pipeline
from research.swing.sector_leadership.build_sector_leadership import (
    add_full_universe_flag,
    assign_leadership_bucket,
    calculate_returns,
    calculate_daily_rs,
    normalize_yahoo_frame,
    rank_and_bucket,
    validate_primary_output,
)


def test_calculate_returns_uses_exact_session_shifts():
    df = pd.DataFrame({"Close": [100.0 + i for i in range(140)]})
    result = calculate_returns(df)

    assert pd.isna(result.loc[20, "Ret21"])
    assert math.isclose(result.loc[21, "Ret21"], 121.0 / 100.0 - 1.0)
    assert math.isclose(result.loc[63, "Ret63"], 163.0 / 100.0 - 1.0)
    assert math.isclose(result.loc[126, "Ret126"], 226.0 / 100.0 - 1.0)


@pytest.mark.parametrize(
    "rank,n,expected",
    [
        (1, 8, "LEADING"),
        (3, 8, "LEADING"),
        (4, 8, "ACCEPTABLE"),
        (5, 8, "WEAK"),
        (6, 8, "LAGGING"),
        (8, 8, "LAGGING"),
        (1, 10, "LEADING"),
        (4, 10, "LEADING"),
        (5, 10, "ACCEPTABLE"),
        (6, 10, "WEAK"),
        (7, 10, "LAGGING"),
        (10, 10, "LAGGING"),
        (1, 11, "LEADING"),
        (4, 11, "LEADING"),
        (5, 11, "ACCEPTABLE"),
        (6, 11, "ACCEPTABLE"),
        (7, 11, "WEAK"),
        (8, 11, "LAGGING"),
        (11, 11, "LAGGING"),
    ],
)
def test_assign_leadership_bucket(rank, n, expected):
    assert assign_leadership_bucket(rank, n) == expected


def test_daily_rs_uses_same_day_percentiles_and_locked_composite():
    rows = []
    for date, values in [
        ("2024-01-01", [0.10, 0.20, 0.30, 0.40]),
        ("2024-01-02", [0.40, 0.30, 0.20, 0.10]),
    ]:
        for sector, value in zip(["A", "B", "C", "D"], values):
            rows.append(
                {
                    "Date": date,
                    "Sector_Key": sector,
                    "Ret21": value,
                    "Ret63": value,
                    "Ret126": value,
                }
            )

    result = calculate_daily_rs(pd.DataFrame(rows))
    strongest = result[
        result["Date"].eq("2024-01-01") & result["Sector_Key"].eq("D")
    ]
    weakest = result[
        result["Date"].eq("2024-01-01") & result["Sector_Key"].eq("A")
    ]

    assert (strongest["RS21_Percentile"] == 100.0).all()
    assert (strongest["RS63_Percentile"] == 100.0).all()
    assert (strongest["RS126_Percentile"] == 100.0).all()
    assert (strongest["Composite_RS"] == 100.0).all()
    assert (weakest["Composite_RS"] == 25.0).all()

    ranked = rank_and_bucket(result)
    for _, group in ranked.groupby("Date"):
        assert set(group["Composite_Rank"]) == {1, 2, 3, 4}
        assert group["Sector_Count"].eq(4).all()


def test_normalize_yahoo_columns_handles_one_ticker_multiindex():
    frame = pd.DataFrame(
        {
            ("Open", "^TEST"): [100.0, 101.0],
            ("High", "^TEST"): [102.0, 103.0],
            ("Low", "^TEST"): [99.0, 100.0],
            ("Close", "^TEST"): [101.0, 102.0],
            ("Adj Close", "^TEST"): [100.5, 101.5],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )

    result = normalize_yahoo_frame(frame)

    assert result.columns.tolist() == [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Adj_Close",
    ]
    assert result["Date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2024-01-02",
        "2024-01-03",
    ]
    assert result["Close"].tolist() == [101.0, 102.0]


def _valid_primary_output():
    return pd.DataFrame(
        {
            "Date": ["2024-01-01"] * 4,
            "Sector_Key": ["A", "B", "C", "D"],
            "Index_Name": ["NIFTY A"] * 4,
            "Yahoo_Ticker": ["^A"] * 4,
            "Close": [100.0] * 4,
            "Ret21": [0.1] * 4,
            "Ret63": [0.1] * 4,
            "Ret126": [0.1] * 4,
            "RS21_Percentile": [100.0, 75.0, 50.0, 25.0],
            "RS63_Percentile": [100.0, 75.0, 50.0, 25.0],
            "RS126_Percentile": [100.0, 75.0, 50.0, 25.0],
            "Composite_RS": [100.0, 75.0, 50.0, 25.0],
            "Composite_Rank": [1, 2, 3, 4],
            "Sector_Count": [4] * 4,
            "Is_Full_Universe": [False] * 4,
            "Leadership_Bucket": ["LEADING", "LEADING", "LAGGING", "LAGGING"],
        }
    )


@pytest.mark.parametrize(
    "mutation", ["duplicate", "bucket", "rank", "missing_return", "full_flag"]
)
def test_validate_primary_output_rejects_broken_invariants(mutation):
    bad = _valid_primary_output()
    if mutation == "duplicate":
        bad.loc[1, "Sector_Key"] = "A"
    elif mutation == "bucket":
        bad.loc[0, "Leadership_Bucket"] = "INVALID"
    elif mutation == "rank":
        bad.loc[0, "Composite_Rank"] = 5
    elif mutation == "missing_return":
        bad.loc[0, "Ret21"] = np.nan
    elif mutation == "full_flag":
        bad.loc[0, "Is_Full_Universe"] = True

    with pytest.raises(ValueError):
        validate_primary_output(bad)


def test_partial_universe_date_is_explicitly_identifiable():
    ranked = rank_and_bucket(
        pd.DataFrame(
            {
                "Date": ["2026-01-01", "2026-01-01"],
                "Sector_Key": ["BANK", "IT"],
                "Composite_RS": [100.0, 90.0],
            }
        )
    )

    flagged = add_full_universe_flag(ranked, universe_size=11)

    assert flagged["Sector_Count"].eq(2).all()
    assert flagged["Is_Full_Universe"].eq(False).all()

    full = add_full_universe_flag(
        pd.DataFrame({"Sector_Count": [11]}), universe_size=11
    )
    assert full["Is_Full_Universe"].eq(True).all()


def test_trailing_incomplete_provider_row_is_excluded_without_filling(monkeypatch):
    dates = pd.bdate_range("2022-01-03", periods=130)
    downloaded = pd.DataFrame(
        {
            "Open": np.arange(130, dtype=float),
            "High": np.arange(130, dtype=float) + 2.0,
            "Low": np.arange(130, dtype=float) - 1.0,
            "Close": np.arange(130, dtype=float) + 100.0,
            "Adj Close": np.arange(130, dtype=float) + 100.0,
        },
        index=dates,
    )
    downloaded.loc[dates[-1], "Close"] = np.nan

    monkeypatch.setattr(pipeline.yf, "download", lambda *args, **kwargs: downloaded)
    monkeypatch.setattr(
        pipeline,
        "_check_metadata_identity",
        lambda index_name, ticker: (True, "metadata test stub"),
    )

    result, validation = pipeline.download_sector_history(
        "AUTO", "NIFTY AUTO", "^CNXAUTO"
    )

    assert validation["Download_Status"] == "OK"
    assert validation["Raw_Row_Count"] == 130
    assert validation["Missing_Close_Count"] == 1
    assert len(result) == 129
    assert result["Close"].notna().all()
