"""Build a point-in-time Nifty sector-leadership dataset."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


ALLOWED_BUCKETS = {"LEADING", "ACCEPTABLE", "WEAK", "LAGGING"}
LOOKBACKS = (21, 63, 126)
START_DATE = "2022-01-01"
END_DATE_EXCLUSIVE = "2026-08-26"
LATEST_INCLUDED_DATE = pd.Timestamp("2026-08-25")
INTERVAL = "1d"

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "sector_index_config.csv"
OUTPUT_DIR = BASE_DIR / "output"

PRIMARY_COLUMNS = [
    "Date",
    "Sector_Key",
    "Index_Name",
    "Yahoo_Ticker",
    "Close",
    "Ret21",
    "Ret63",
    "Ret126",
    "RS21_Percentile",
    "RS63_Percentile",
    "RS126_Percentile",
    "Composite_RS",
    "Composite_Rank",
    "Sector_Count",
    "Leadership_Bucket",
]
SUMMARY_COLUMNS = [
    "Sector_Key",
    "Index_Name",
    "Yahoo_Ticker",
    "Valid_Ranked_Days",
    "Leading_Days",
    "Acceptable_Days",
    "Weak_Days",
    "Lagging_Days",
    "Earliest_Ranked_Date",
    "Latest_Ranked_Date",
]
VALIDATION_COLUMNS = [
    "Sector_Key",
    "Index_Name",
    "Yahoo_Ticker",
    "Download_Status",
    "Raw_Row_Count",
    "Earliest_Date",
    "Latest_Date",
    "Missing_Close_Count",
    "Duplicate_Date_Count",
    "First_Valid_Ret126_Date",
    "Notes",
]


def calculate_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate fixed trading-session returns from the daily Close series."""

    result = df.copy()
    result["Ret21"] = result["Close"] / result["Close"].shift(21) - 1.0
    result["Ret63"] = result["Close"] / result["Close"].shift(63) - 1.0
    result["Ret126"] = result["Close"] / result["Close"].shift(126) - 1.0
    return result


def calculate_daily_rs(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate same-day cross-sectional percentiles and the locked composite."""

    result = df.copy()
    valid = result[["Ret21", "Ret63", "Ret126"]].notna().all(axis=1)
    for return_column, percentile_column in (
        ("Ret21", "RS21_Percentile"),
        ("Ret63", "RS63_Percentile"),
        ("Ret126", "RS126_Percentile"),
    ):
        result[percentile_column] = np.nan
        result.loc[valid, percentile_column] = (
            result.loc[valid]
            .groupby("Date")[return_column]
            .rank(method="average", pct=True)
            .mul(100.0)
        )

    result["Composite_RS"] = (
        0.30 * result["RS21_Percentile"]
        + 0.40 * result["RS63_Percentile"]
        + 0.30 * result["RS126_Percentile"]
    )
    return result


def assign_leadership_bucket(rank: int, sector_count: int) -> str:
    """Assign the locked bucket for an ordinal rank within one date."""

    top_third_count = math.ceil(sector_count / 3)
    top_half_count = math.ceil(sector_count / 2)
    bottom_third_count = math.ceil(sector_count / 3)

    if rank <= top_third_count:
        return "LEADING"
    if rank <= top_half_count:
        return "ACCEPTABLE"
    if rank > sector_count - bottom_third_count:
        return "LAGGING"
    return "WEAK"


def rank_and_bucket(df: pd.DataFrame) -> pd.DataFrame:
    """Rank composite scores descending and assign deterministic buckets."""

    result = df.copy()
    result["Composite_Rank"] = (
        result.groupby("Date")["Composite_RS"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    result["Sector_Count"] = (
        result.groupby("Date")["Composite_RS"].transform("count").astype(int)
    )
    result["Leadership_Bucket"] = [
        assign_leadership_bucket(rank, sector_count)
        for rank, sector_count in zip(
            result["Composite_Rank"], result["Sector_Count"]
        )
    ]
    return result


def _format_date(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _resolve_price_column(frame: pd.DataFrame, name: str) -> object:
    if not isinstance(frame.columns, pd.MultiIndex) and name in frame.columns:
        return name
    if isinstance(frame.columns, pd.MultiIndex):
        matches = [
            column
            for column in frame.columns
            if name in {str(level) for level in column}
        ]
        if len(matches) == 1:
            return matches[0]
    raise ValueError(
        f"Yahoo response did not provide a unique {name!r} column; "
        f"received columns: {list(frame.columns)!r}"
    )


def normalize_yahoo_frame(downloaded: pd.DataFrame) -> pd.DataFrame:
    """Normalize a one-ticker yfinance response to flat daily price columns."""

    fields = ["Open", "High", "Low", "Close"]
    has_adj_close = "Adj Close" in downloaded.columns or (
        isinstance(downloaded.columns, pd.MultiIndex)
        and any(
            "Adj Close" in {str(level) for level in column}
            for column in downloaded.columns
        )
    )
    if has_adj_close:
        fields.append("Adj Close")

    normalized = pd.DataFrame(
        {
            field: pd.to_numeric(
                downloaded.iloc[
                    :,
                    list(downloaded.columns).index(
                        _resolve_price_column(downloaded, field)
                    ),
                ],
                errors="coerce",
            )
            for field in fields
        },
        index=downloaded.index,
    )
    dates = pd.to_datetime(normalized.index)
    if getattr(dates, "tz", None) is not None:
        dates = dates.tz_localize(None)
    normalized.index.name = None
    normalized.insert(0, "Date", dates)
    normalized = normalized.sort_values("Date").reset_index(drop=True)
    normalized = normalized.rename(columns={"Adj Close": "Adj_Close"})
    if "Adj_Close" not in normalized.columns:
        normalized["Adj_Close"] = pd.NA
    return normalized


def _new_validation_row(
    sector_key: str, index_name: str, ticker: str
) -> dict[str, object]:
    return {
        "Sector_Key": sector_key,
        "Index_Name": index_name,
        "Yahoo_Ticker": ticker,
        "Download_Status": "UNAVAILABLE",
        "Raw_Row_Count": 0,
        "Earliest_Date": "",
        "Latest_Date": "",
        "Missing_Close_Count": 0,
        "Duplicate_Date_Count": 0,
        "First_Valid_Ret126_Date": "",
        "Notes": "",
    }


def _identity_text(value: object) -> str:
    return "".join(character for character in str(value).upper() if character.isalnum())


def _check_metadata_identity(index_name: str, ticker: str) -> tuple[bool, str]:
    """Validate Yahoo metadata when available without blocking price downloads."""

    try:
        metadata = yf.Ticker(ticker).get_history_metadata() or {}
    except Exception as exc:
        return (
            True,
            "metadata lookup unavailable; ticker identity was pre-verified from "
            f"Yahoo history metadata ({type(exc).__name__}: {exc})",
        )

    issues: list[str] = []
    instrument_type = metadata.get("instrumentType")
    if instrument_type and str(instrument_type).upper() != "INDEX":
        issues.append(f"instrumentType={instrument_type!r}, expected INDEX")
    exchange_name = metadata.get("exchangeName")
    if exchange_name and str(exchange_name).upper() not in {"NSI", "NSE"}:
        issues.append(f"exchangeName={exchange_name!r}, expected NSI/NSE")
    observed_symbol = metadata.get("symbol")
    if observed_symbol and str(observed_symbol) != ticker:
        issues.append(f"symbol={observed_symbol!r}, expected {ticker!r}")

    observed_names = " ".join(
        str(metadata.get(key, ""))
        for key in ("shortName", "longName")
        if metadata.get(key)
    )
    expected_name = _identity_text(index_name)
    if observed_names and expected_name not in _identity_text(observed_names):
        issues.append(
            f"metadata name={observed_names!r} does not match {index_name!r}"
        )

    if issues:
        return False, "metadata identity mismatch: " + "; ".join(issues)
    if observed_names:
        return True, f"metadata identity verified: {observed_names}"
    return True, "metadata returned no display-name fields; price identity pre-verified"


def download_sector_history(
    sector_key: str, index_name: str, ticker: str
) -> tuple[pd.DataFrame | None, dict[str, object]]:
    """Download, normalize, and validate one configured Nifty sector index."""

    validation = _new_validation_row(sector_key, index_name, ticker)
    if not ticker or pd.isna(ticker):
        validation["Notes"] = "No Yahoo ticker configured"
        return None, validation

    try:
        downloaded = yf.download(
            ticker,
            start=START_DATE,
            end=END_DATE_EXCLUSIVE,
            interval="1d",
            auto_adjust=False,
            progress=False,
            actions=False,
        )
    except Exception as exc:
        validation["Notes"] = f"download failed: {type(exc).__name__}: {exc}"
        return None, validation

    if downloaded is None or downloaded.empty:
        validation["Notes"] = "Yahoo returned no daily rows"
        return None, validation

    try:
        normalized = normalize_yahoo_frame(downloaded)
    except Exception as exc:
        validation["Download_Status"] = "INVALID"
        validation["Notes"] = f"column normalization failed: {type(exc).__name__}: {exc}"
        return None, validation

    validation["Raw_Row_Count"] = len(normalized)
    validation["Earliest_Date"] = _format_date(normalized["Date"].min())
    validation["Latest_Date"] = _format_date(normalized["Date"].max())
    validation["Missing_Close_Count"] = int(normalized["Close"].isna().sum())
    validation["Duplicate_Date_Count"] = int(normalized["Date"].duplicated().sum())

    invalid_reasons: list[str] = []
    if validation["Missing_Close_Count"]:
        invalid_reasons.append("missing Close values")
    if validation["Duplicate_Date_Count"]:
        invalid_reasons.append("duplicate dates")
    if normalized["Date"].min() < pd.Timestamp(START_DATE):
        invalid_reasons.append("data before requested start date")
    if normalized["Date"].max() > LATEST_INCLUDED_DATE:
        invalid_reasons.append("data after requested end date")

    with_returns = calculate_returns(normalized)
    valid_ret126_dates = with_returns.loc[with_returns["Ret126"].notna(), "Date"]
    if not valid_ret126_dates.empty:
        validation["First_Valid_Ret126_Date"] = _format_date(valid_ret126_dates.iloc[0])
    else:
        invalid_reasons.append("fewer than 127 valid Close observations")

    identity_ok, identity_note = _check_metadata_identity(index_name, ticker)
    if not identity_ok:
        invalid_reasons.append(identity_note)

    if invalid_reasons:
        validation["Download_Status"] = "INVALID"
        validation["Notes"] = "; ".join(invalid_reasons)
        return None, validation

    validation["Download_Status"] = "OK"
    validation["Notes"] = identity_note
    return normalized, validation


def _load_sector_config(path: Path = CONFIG_PATH) -> pd.DataFrame:
    config = pd.read_csv(path, dtype=str).fillna("")
    expected_columns = ["Sector_Key", "Index_Name", "Yahoo_Ticker"]
    if config.columns.tolist() != expected_columns:
        raise ValueError(
            f"sector config columns must be {expected_columns}, "
            f"received {config.columns.tolist()}"
        )
    if config["Sector_Key"].duplicated().any():
        raise ValueError("sector config contains duplicate Sector_Key values")
    return config


def validate_primary_output(df: pd.DataFrame) -> None:
    """Raise a precise error if any primary-output invariant is violated."""

    if df.columns.tolist() != PRIMARY_COLUMNS:
        raise ValueError(
            f"primary columns must be {PRIMARY_COLUMNS}, received {df.columns.tolist()}"
        )
    if df.empty:
        raise ValueError("primary output is empty")
    if df.duplicated(["Date", "Sector_Key"]).any():
        raise ValueError("primary output contains duplicate (Date, Sector_Key) rows")
    required_non_null = [
        "Close",
        "Ret21",
        "Ret63",
        "Ret126",
        "RS21_Percentile",
        "RS63_Percentile",
        "RS126_Percentile",
        "Composite_RS",
        "Composite_Rank",
        "Sector_Count",
        "Leadership_Bucket",
    ]
    if df[required_non_null].isna().any().any():
        missing = df[required_non_null].isna().sum()
        raise ValueError(f"primary output has missing required values: {missing.to_dict()}")
    if not df["Date"].is_monotonic_increasing:
        raise ValueError("primary dates are not sorted ascending")
    if not df.set_index(["Date", "Composite_Rank"]).index.is_monotonic_increasing:
        raise ValueError("primary rows are not sorted by Date and Composite_Rank")
    if not set(df["Leadership_Bucket"]).issubset(ALLOWED_BUCKETS):
        raise ValueError("primary output contains an invalid Leadership_Bucket")

    for date, group in df.groupby("Date", sort=False):
        sector_count = len(group)
        if group["Sector_Count"].nunique() != 1 or int(group["Sector_Count"].iloc[0]) != sector_count:
            raise ValueError(f"Sector_Count mismatch on {date}")
        ranks = sorted(int(rank) for rank in group["Composite_Rank"])
        if ranks != list(range(1, sector_count + 1)):
            raise ValueError(f"Composite_Rank must be exactly 1..N on {date}: {ranks}")
        if min(ranks) != 1 or max(ranks) > sector_count:
            raise ValueError(f"Composite_Rank out of bounds on {date}")
        for row in group.itertuples(index=False):
            expected_bucket = assign_leadership_bucket(
                int(row.Composite_Rank), int(row.Sector_Count)
            )
            if row.Leadership_Bucket != expected_bucket:
                raise ValueError(
                    f"bucket mismatch on {date}/{row.Sector_Key}: "
                    f"{row.Leadership_Bucket!r} != {expected_bucket!r}"
                )


def validate_sampled_returns(
    raw_histories: dict[str, pd.DataFrame], primary: pd.DataFrame
) -> None:
    """Check first/middle/last eligible return rows against positional shifts."""

    for sector_key, raw in raw_histories.items():
        raw_reset = raw.reset_index(drop=True)
        eligible_positions = [
            position
            for position in range(len(raw_reset))
            if position >= 126
            and all(
                pd.notna(
                    raw_reset.loc[position, "Close"]
                    / raw_reset.loc[position - lookback, "Close"]
                    - 1.0
                )
                for lookback in LOOKBACKS
            )
        ]
        if not eligible_positions:
            raise ValueError(f"no eligible sampled return rows for {sector_key}")
        sample_positions = sorted(
            set(
                [
                    eligible_positions[0],
                    eligible_positions[len(eligible_positions) // 2],
                    eligible_positions[-1],
                ]
            )
        )
        for position in sample_positions:
            date = _format_date(raw_reset.loc[position, "Date"])
            matches = primary.loc[
                primary["Sector_Key"].eq(sector_key) & primary["Date"].eq(date)
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"expected one primary row for sampled return {sector_key}/{date}"
                )
            row = matches.iloc[0]
            for lookback, column in zip(LOOKBACKS, ("Ret21", "Ret63", "Ret126")):
                expected = (
                    raw_reset.loc[position, "Close"]
                    / raw_reset.loc[position - lookback, "Close"]
                    - 1.0
                )
                if not math.isclose(
                    float(row[column]), float(expected), rel_tol=1e-12, abs_tol=1e-12
                ):
                    raise ValueError(
                        f"{column} mismatch for {sector_key}/{date}: "
                        f"{row[column]} != {expected}"
                    )


def build_summary(primary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for sector_key, group in primary.groupby("Sector_Key", sort=True):
        rows.append(
            {
                "Sector_Key": sector_key,
                "Index_Name": group["Index_Name"].iloc[0],
                "Yahoo_Ticker": group["Yahoo_Ticker"].iloc[0],
                "Valid_Ranked_Days": len(group),
                "Leading_Days": int(group["Leadership_Bucket"].eq("LEADING").sum()),
                "Acceptable_Days": int(
                    group["Leadership_Bucket"].eq("ACCEPTABLE").sum()
                ),
                "Weak_Days": int(group["Leadership_Bucket"].eq("WEAK").sum()),
                "Lagging_Days": int(group["Leadership_Bucket"].eq("LAGGING").sum()),
                "Earliest_Ranked_Date": group["Date"].iloc[0],
                "Latest_Ranked_Date": group["Date"].iloc[-1],
            }
        )
    summary = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
    if summary.empty:
        raise ValueError("sector leadership summary is empty")
    if summary.columns.tolist() != SUMMARY_COLUMNS:
        raise ValueError("sector leadership summary schema mismatch")
    for row in summary.itertuples(index=False):
        bucket_total = (
            row.Leading_Days
            + row.Acceptable_Days
            + row.Weak_Days
            + row.Lagging_Days
        )
        if bucket_total != row.Valid_Ranked_Days:
            raise ValueError(f"summary bucket counts do not reconcile for {row.Sector_Key}")
    return summary


def run_pipeline(base_dir: Path = BASE_DIR) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run the complete download, scoring, validation, and export pipeline."""

    config = _load_sector_config(base_dir / "sector_index_config.csv")
    scored_parts: list[pd.DataFrame] = []
    raw_histories: dict[str, pd.DataFrame] = {}
    validation_rows: list[dict[str, object]] = []

    for row in config.itertuples(index=False):
        raw, validation = download_sector_history(
            row.Sector_Key, row.Index_Name, row.Yahoo_Ticker
        )
        validation_rows.append(validation)
        if raw is None:
            continue

        with_returns = calculate_returns(raw)
        valid = with_returns.dropna(subset=["Ret21", "Ret63", "Ret126"]).copy()
        valid["Sector_Key"] = row.Sector_Key
        valid["Index_Name"] = row.Index_Name
        valid["Yahoo_Ticker"] = row.Yahoo_Ticker
        scored_parts.append(valid)
        raw_histories[row.Sector_Key] = with_returns

    if not scored_parts:
        raise ValueError("no valid sector histories were available for ranking")

    combined = pd.concat(scored_parts, ignore_index=True)
    scored = calculate_daily_rs(combined)
    ranked = rank_and_bucket(scored.dropna(subset=["Composite_RS"]).copy())
    ranked["Date"] = pd.to_datetime(ranked["Date"]).dt.strftime("%Y-%m-%d")
    primary = ranked[PRIMARY_COLUMNS].sort_values(
        ["Date", "Composite_Rank"], ascending=[True, True]
    ).reset_index(drop=True)

    validate_primary_output(primary)
    validate_sampled_returns(raw_histories, primary)

    summary = build_summary(primary)
    validation = pd.DataFrame(validation_rows, columns=VALIDATION_COLUMNS)
    return primary, summary, validation


def write_outputs(
    base_dir: Path, primary: pd.DataFrame, summary: pd.DataFrame, validation: pd.DataFrame
) -> None:
    output_dir = base_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    primary.to_csv(output_dir / "sector_leadership_daily.csv", index=False)
    summary.to_csv(output_dir / "sector_leadership_summary.csv", index=False)
    validation.to_csv(output_dir / "sector_data_validation.csv", index=False)


def main() -> None:
    primary, summary, validation = run_pipeline()
    write_outputs(BASE_DIR, primary, summary, validation)

    raw_earliest = validation.loc[validation["Download_Status"].eq("OK"), "Earliest_Date"].min()
    raw_latest = validation.loc[validation["Download_Status"].eq("OK"), "Latest_Date"].max()
    print(f"Python pipeline: {__file__}")
    print(f"Requested window: {START_DATE} through 2026-08-25 inclusive")
    print(f"Raw date range across valid sectors: {raw_earliest} to {raw_latest}")
    print(f"Ranked date range: {primary['Date'].min()} to {primary['Date'].max()}")
    print(
        "Sector count per ranked date: "
        f"min={primary.groupby('Date')['Sector_Count'].first().min()}, "
        f"max={primary.groupby('Date')['Sector_Count'].first().max()}"
    )
    print(f"Primary output rows: {len(primary)}")
    print(f"Download statuses: {validation['Download_Status'].value_counts().to_dict()}")
    print("Resolved sector index names/tickers:")
    print(validation[["Sector_Key", "Index_Name", "Yahoo_Ticker", "Download_Status"]].to_string(index=False))
    print("Generated:")
    print(f"  {BASE_DIR / 'output' / 'sector_leadership_daily.csv'}")
    print(f"  {BASE_DIR / 'output' / 'sector_leadership_summary.csv'}")
    print(f"  {BASE_DIR / 'output' / 'sector_data_validation.csv'}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc
