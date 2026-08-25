"""Build a point-in-time NIFTY 500 market-regime dataset.

This script intentionally does not inspect trade-performance data or tune any
regime parameters. It downloads only Yahoo Finance ticker ``^CRSLDX`` and
uses the unadjusted daily Close for both moving averages and classification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf


TICKER = "^CRSLDX"
START_DATE = "2022-01-01"
END_DATE_EXCLUSIVE = "2026-08-26"
REGIMES = ("RISK_ON", "MIXED", "RISK_OFF")
DAILY_COLUMNS = (
    "Date",
    "Open",
    "High",
    "Low",
    "Close",
    "Adj_Close",
    "SMA50",
    "SMA200",
    "Regime",
)
CHANGE_COLUMNS = (
    "Date",
    "Close",
    "SMA50",
    "SMA200",
    "Previous_Regime",
    "New_Regime",
)
SUMMARY_COLUMNS = (
    "Regime",
    "Trading_Days",
    "Percentage_of_Trading_Days",
    "First_Date",
    "Last_Date",
)


def _column_name(frame: pd.DataFrame, name: str) -> Any:
    """Return the actual column label for a named price field."""

    if name in frame.columns:
        return name

    if isinstance(frame.columns, pd.MultiIndex):
        matches = [
            column
            for column in frame.columns
            if name in column
        ]
        if len(matches) == 1:
            return matches[0]

    raise ValueError(
        f"Yahoo Finance response did not provide a unique {name!r} column; "
        f"received columns: {list(frame.columns)!r}"
    )


def _normalise_download(downloaded: pd.DataFrame) -> pd.DataFrame:
    """Normalize yfinance's single- or multi-level columns to price fields."""

    fields = ["Open", "High", "Low", "Close"]
    if "Adj Close" in downloaded.columns or (
        isinstance(downloaded.columns, pd.MultiIndex)
        and any("Adj Close" in column for column in downloaded.columns)
    ):
        fields.append("Adj Close")

    normalized = pd.DataFrame(
        {field: downloaded[_column_name(downloaded, field)] for field in fields},
        index=downloaded.index,
    )
    normalized.index = pd.to_datetime(normalized.index)
    if getattr(normalized.index, "tz", None) is not None:
        normalized.index = normalized.index.tz_localize(None)
    normalized.index.name = "Date"
    normalized = normalized.sort_index()
    return normalized


def download_history() -> pd.DataFrame:
    """Download the required daily history, stopping on any ticker failure."""

    try:
        downloaded = yf.download(
            TICKER,
            start=START_DATE,
            end=END_DATE_EXCLUSIVE,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
            group_by="column",
            multi_level_index=False,
        )
    except Exception as exc:
        raise RuntimeError(
            f"DOWNLOAD FAILED for {TICKER}: {type(exc).__name__}: {exc}"
        ) from exc

    if downloaded is None or downloaded.empty:
        raise RuntimeError(
            f"DOWNLOAD FAILED for {TICKER}: Yahoo Finance returned no rows"
        )

    try:
        normalized = _normalise_download(downloaded)
    except Exception as exc:
        raise RuntimeError(
            f"DOWNLOAD FAILED for {TICKER}: {type(exc).__name__}: {exc}"
        ) from exc

    missing_close = int(normalized["Close"].isna().sum())
    if missing_close:
        raise RuntimeError(
            f"DOWNLOAD FAILED for {TICKER}: received {missing_close} rows "
            "with missing Close values"
        )

    return normalized


def build_dataset(
    raw: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, int | str]]:
    """Compute the locked regime definition and return all requested outputs."""

    work = raw.copy()
    work["SMA50"] = work["Close"].rolling(50).mean()
    work["SMA200"] = work["Close"].rolling(200).mean()

    exported = work.loc[work["SMA200"].notna()].copy()
    risk_on = (exported["Close"] > exported["SMA50"]) & (
        exported["SMA50"] > exported["SMA200"]
    )
    risk_off = exported["Close"] < exported["SMA200"]
    exported["Regime"] = "MIXED"
    exported.loc[risk_on, "Regime"] = "RISK_ON"
    exported.loc[risk_off, "Regime"] = "RISK_OFF"

    exported.insert(0, "Date", exported.index.strftime("%Y-%m-%d"))
    exported = exported.rename(columns={"Adj Close": "Adj_Close"})
    if "Adj_Close" not in exported.columns:
        exported["Adj_Close"] = pd.NA
    daily = exported[list(DAILY_COLUMNS)].copy()

    previous_regime = daily["Regime"].shift(1)
    changed = previous_regime.notna() & previous_regime.ne(daily["Regime"])
    changes = pd.DataFrame(
        {
            "Date": daily.loc[changed, "Date"].to_numpy(),
            "Close": daily.loc[changed, "Close"].to_numpy(),
            "SMA50": daily.loc[changed, "SMA50"].to_numpy(),
            "SMA200": daily.loc[changed, "SMA200"].to_numpy(),
            "Previous_Regime": previous_regime.loc[changed].to_numpy(),
            "New_Regime": daily.loc[changed, "Regime"].to_numpy(),
        },
        columns=CHANGE_COLUMNS,
    )

    total_days = len(daily)
    summary_rows: list[dict[str, str | int | float]] = []
    for regime in REGIMES:
        regime_dates = daily.loc[daily["Regime"] == regime, "Date"]
        count = int(regime_dates.shape[0])
        summary_rows.append(
            {
                "Regime": regime,
                "Trading_Days": count,
                "Percentage_of_Trading_Days": (
                    (count / total_days * 100.0) if total_days else 0.0
                ),
                "First_Date": regime_dates.iloc[0] if count else "",
                "Last_Date": regime_dates.iloc[-1] if count else "",
            }
        )
    summary = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)

    validation = validate_outputs(raw, daily, changes, summary)
    return daily, changes, summary, validation


def validate_outputs(
    raw: pd.DataFrame,
    daily: pd.DataFrame,
    changes: pd.DataFrame,
    summary: pd.DataFrame,
) -> dict[str, int | str]:
    """Validate required schemas, data quality, and regime inequalities."""

    duplicate_date_count = int(raw.index.duplicated().sum())
    missing_close_count = int(raw["Close"].isna().sum())
    missing_sma50_count = int(daily["SMA50"].isna().sum())
    missing_sma200_count = int(daily["SMA200"].isna().sum())
    invalid_regime_count = int((~daily["Regime"].isin(REGIMES)).sum())
    risk_on_violation_count = int(
        (
            (daily["Regime"] == "RISK_ON")
            & ~(
                (daily["Close"] > daily["SMA50"])
                & (daily["SMA50"] > daily["SMA200"])
            )
        ).sum()
    )
    risk_off_violation_count = int(
        (
            (daily["Regime"] == "RISK_OFF")
            & ~(daily["Close"] < daily["SMA200"])
        ).sum()
    )
    summary_count_total = int(summary["Trading_Days"].sum())
    change_violation_count = int(
        (
            changes["Previous_Regime"].eq(changes["New_Regime"])
            | ~changes["Previous_Regime"].isin(REGIMES)
            | ~changes["New_Regime"].isin(REGIMES)
        ).sum()
    )

    checks: dict[str, int | str] = {
        "earliest_downloaded_date": raw.index.min().strftime("%Y-%m-%d"),
        "latest_downloaded_date": raw.index.max().strftime("%Y-%m-%d"),
        "raw_trading_day_rows": len(raw),
        "exported_regime_rows": len(daily),
        "duplicate_date_count": duplicate_date_count,
        "missing_close_count": missing_close_count,
        "missing_sma50_count": missing_sma50_count,
        "missing_sma200_count": missing_sma200_count,
        "invalid_regime_count": invalid_regime_count,
        "risk_on_violation_count": risk_on_violation_count,
        "risk_off_violation_count": risk_off_violation_count,
        "summary_count_total": summary_count_total,
        "change_violation_count": change_violation_count,
        "allowed_regime_values": ", ".join(sorted(daily["Regime"].unique())),
    }
    failures = {
        name: value
        for name, value in checks.items()
        if name.endswith("_count") and value != 0
    }
    if summary_count_total != len(daily):
        failures["summary_count_total"] = summary_count_total
    if invalid_regime_count or not set(daily["Regime"]).issubset(REGIMES):
        failures["invalid_regime_count"] = invalid_regime_count
    if summary.columns.tolist() != list(SUMMARY_COLUMNS):
        failures["summary_schema"] = 1
    if daily.columns.tolist() != list(DAILY_COLUMNS):
        failures["daily_schema"] = 1
    if changes.columns.tolist() != list(CHANGE_COLUMNS):
        failures["changes_schema"] = 1
    if failures:
        raise ValueError(f"Validation failed: {failures}")

    checks["regime_counts"] = "; ".join(
        f"{regime}={int((daily['Regime'] == regime).sum())}"
        for regime in REGIMES
    )
    checks["all_regime_values_allowed"] = "YES"
    checks["regime_change_rows"] = len(changes)
    return checks


def _write_outputs(
    output_dir: Path,
    daily: pd.DataFrame,
    changes: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:
    daily.to_csv(output_dir / "nifty500_regime_daily.csv", index=False)
    changes.to_csv(output_dir / "nifty500_regime_changes.csv", index=False)
    summary.to_csv(output_dir / "nifty500_regime_summary.csv", index=False)


def main() -> None:
    output_dir = Path(__file__).resolve().parent
    raw = download_history()
    daily, changes, summary, validation = build_dataset(raw)
    _write_outputs(output_dir, daily, changes, summary)

    print(f"Ticker: {TICKER}")
    print(f"Requested window: {START_DATE} through 2026-08-25 inclusive")
    print("Validation:")
    for name, value in validation.items():
        print(f"  {name}: {value}")
    print("Output files:")
    for filename in (
        "nifty500_regime_daily.csv",
        "nifty500_regime_changes.csv",
        "nifty500_regime_summary.csv",
    ):
        print(f"  {output_dir / filename}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc))
        raise SystemExit(1) from exc
