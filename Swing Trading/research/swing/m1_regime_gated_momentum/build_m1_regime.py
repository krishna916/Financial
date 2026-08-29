"""Recompute the frozen M1 market regime from point-in-time inputs."""

from __future__ import annotations

import numpy as np
import pandas as pd


MIN_BREADTH_COVERAGE = 0.80
MIN_PCT_ABOVE_SMA50 = 50.0
AUDIT_COLUMNS = ("Entry_ID", "Symbol", "Violation", "Observed", "Expected")


def _audit(
    violation: str,
    *,
    entry_id: object = "",
    symbol: object = "",
    observed: object = "",
    expected: object = "",
) -> dict[str, object]:
    return {
        "Entry_ID": "" if pd.isna(entry_id) else str(entry_id),
        "Symbol": "" if pd.isna(symbol) else str(symbol),
        "Violation": violation,
        "Observed": observed,
        "Expected": expected,
    }


def _to_dates(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_datetime(result[column], errors="coerce")
    return result


def active_member_count_on(membership: pd.DataFrame, date: pd.Timestamp) -> int:
    """Return the count of inclusive point-in-time membership intervals."""

    day = pd.Timestamp(date)
    if pd.isna(day) or membership.empty:
        return 0
    frame = _to_dates(membership, ("Member_From", "Member_To"))
    start_ok = frame["Member_From"].le(day)
    end_ok = frame["Member_To"].isna() | frame["Member_To"].ge(day)
    method_ok = frame["Method"].astype(str).eq("POINT_IN_TIME") if "Method" in frame else True
    return int(frame.loc[start_ok & end_ok & method_ok, "Symbol"].astype(str).nunique())


def _empty_audit() -> pd.DataFrame:
    return pd.DataFrame(columns=AUDIT_COLUMNS)


def build_m1_regime(
    breadth: pd.DataFrame,
    index_daily: pd.DataFrame,
    membership: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build M1 states without consulting any persisted regime labels."""

    breadth = _to_dates(breadth, ("Date",))
    index_daily = _to_dates(index_daily, ("Date",))
    membership = _to_dates(membership, ("Member_From", "Member_To"))
    audit_rows: list[dict[str, object]] = []

    if breadth.empty or index_daily.empty:
        return pd.DataFrame(), _empty_audit()

    if breadth["Date"].isna().any() or index_daily["Date"].isna().any():
        audit_rows.append(
            _audit(
                "INVALID_MARKET_DATE",
                observed="unparseable Date",
                expected="all market dates parse successfully",
            )
        )

    left = breadth.drop_duplicates("Date", keep=False).copy()
    right = index_daily.drop_duplicates("Date", keep=False).copy()
    merged = left.merge(right, on="Date", how="left", suffixes=("", "_index"), indicator=True)

    for _, row in merged.loc[merged["_merge"].ne("both")].iterrows():
        audit_rows.append(
            _audit(
                "MISSING_EXACT_MARKET_CONTEXT",
                observed=str(row.get("Date", "")),
                expected="breadth and index row on identical date",
            )
        )

    regime_rows: list[dict[str, object]] = []
    for _, row in merged.loc[merged["_merge"].eq("both")].iterrows():
        date = pd.Timestamp(row["Date"])
        active_count = active_member_count_on(membership, date)
        denominator = pd.to_numeric(pd.Series([row.get("SMA50_Denominator")]), errors="coerce").iloc[0]
        pct_above = pd.to_numeric(pd.Series([row.get("Pct_Above_SMA50")]), errors="coerce").iloc[0]
        close = pd.to_numeric(pd.Series([row.get("Close")]), errors="coerce").iloc[0]
        sma50 = pd.to_numeric(pd.Series([row.get("SMA50")]), errors="coerce").iloc[0]
        sma200 = pd.to_numeric(pd.Series([row.get("SMA200")]), errors="coerce").iloc[0]
        coverage = float(denominator) / active_count if active_count and pd.notna(denominator) else np.nan

        denominator_match = True
        optional_count_column = next(
            (column for column in ("Universe_Member_Count", "Member_Count") if column in row.index),
            None,
        )
        if optional_count_column is not None and pd.notna(row[optional_count_column]):
            declared_count = float(row[optional_count_column])
            denominator_match = bool(np.isclose(declared_count, active_count, rtol=0, atol=0))
            if not denominator_match:
                audit_rows.append(
                    _audit(
                        "BREADTH_PIT_DENOMINATOR_MISMATCH",
                        observed=f"{optional_count_column}={declared_count}, active={active_count}",
                        expected="breadth universe count equals active PIT membership count",
                    )
                )

        data_safe = bool(pd.notna(coverage) and coverage >= MIN_BREADTH_COVERAGE)
        index_trend_ok = bool(
            pd.notna(close)
            and pd.notna(sma50)
            and pd.notna(sma200)
            and close > sma200
            and sma50 > sma200
        )
        breadth_ok = bool(pd.notna(pct_above) and pct_above >= MIN_PCT_ABOVE_SMA50)
        regime_rows.append(
            {
                "Date": date,
                "Active_PIT_Member_Count": active_count,
                "SMA50_Denominator": denominator,
                "SMA50_Breadth_Coverage": coverage,
                "Pct_Above_SMA50": pct_above,
                "Nifty500_Close": close,
                "Nifty500_SMA50": sma50,
                "Nifty500_SMA200": sma200,
                "DATA_SAFE": data_safe,
                "INDEX_TREND_OK": index_trend_ok,
                "BREADTH_OK": breadth_ok,
                "PIT_Denominator_Match": denominator_match,
                "M1_Regime": (
                    "MOMENTUM_ENABLED"
                    if data_safe and index_trend_ok and breadth_ok
                    else "MOMENTUM_DISABLED"
                ),
            }
        )

    regime = pd.DataFrame(regime_rows).sort_values("Date").reset_index(drop=True)
    return regime, pd.DataFrame(audit_rows, columns=AUDIT_COLUMNS).drop_duplicates(
        subset=["Entry_ID", "Symbol", "Violation", "Observed"]
    ).reset_index(drop=True)


def attach_exact_signal_regime(
    signals: pd.DataFrame,
    regime_daily: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Join regime context only when ``Signal_Date == Date`` exactly."""

    signal_frame = _to_dates(signals, ("Signal_Date",)).copy()
    regime_frame = _to_dates(regime_daily, ("Date",)).copy()
    regime_columns = [
        "Date",
        "Active_PIT_Member_Count",
        "SMA50_Denominator",
        "SMA50_Breadth_Coverage",
        "Pct_Above_SMA50",
        "Nifty500_Close",
        "Nifty500_SMA50",
        "Nifty500_SMA200",
        "DATA_SAFE",
        "INDEX_TREND_OK",
        "BREADTH_OK",
        "PIT_Denominator_Match",
        "M1_Regime",
    ]
    for column in regime_columns:
        if column not in regime_frame:
            regime_frame[column] = pd.NA
    joined = signal_frame.merge(
        regime_frame.loc[:, regime_columns].rename(columns={"Date": "Regime_Context_Date"}),
        left_on="Signal_Date",
        right_on="Regime_Context_Date",
        how="left",
        sort=False,
        validate="many_to_one",
    )
    joined["Exact_Date_Match"] = joined["Regime_Context_Date"].notna() & joined["Signal_Date"].eq(
        joined["Regime_Context_Date"]
    )
    audit_rows: list[dict[str, object]] = []
    for _, row in joined.iterrows():
        if not bool(row["Exact_Date_Match"]):
            audit_rows.append(
                _audit(
                    "MISSING_EXACT_SIGNAL_REGIME",
                    entry_id=row.get("Entry_ID", ""),
                    symbol=row.get("Symbol", ""),
                    observed=str(row.get("Signal_Date", "")),
                    expected="one regime row on exact Signal_Date",
                )
            )
    audit_columns = [
        "Entry_ID",
        "Symbol",
        "Signal_Date",
        "Regime_Context_Date",
        "Active_PIT_Member_Count",
        "SMA50_Denominator",
        "SMA50_Breadth_Coverage",
        "Pct_Above_SMA50",
        "Nifty500_Close",
        "Nifty500_SMA50",
        "Nifty500_SMA200",
        "DATA_SAFE",
        "INDEX_TREND_OK",
        "BREADTH_OK",
        "M1_Regime",
        "Exact_Date_Match",
        "PIT_Denominator_Match",
    ]
    for column in audit_columns:
        if column not in joined:
            joined[column] = pd.NA
    regime_audit = joined.loc[:, audit_columns].copy()
    violations = pd.DataFrame(audit_rows, columns=AUDIT_COLUMNS)
    return joined, regime_audit, violations
