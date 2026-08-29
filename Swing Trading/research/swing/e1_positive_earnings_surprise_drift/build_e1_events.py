"""Normalize frozen filings into point-in-time E1 event evidence."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from constants import PRIMARY_END, PRIMARY_START
from load_e1_inputs import active_members_on


def _date(value: object) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    stamp = pd.Timestamp(parsed)
    if stamp.tz is not None:
        stamp = stamp.tz_convert("Asia/Kolkata").tz_localize(None)
    return stamp.normalize()


def _public_date(value: object) -> pd.Timestamp:
    return _date(value)


def _event_id(symbol: object, period_end: object, basis: object) -> str:
    date = _date(period_end)
    date_part = "UNKNOWN" if pd.isna(date) else date.strftime("%Y%m%d")
    return f"{str(symbol).strip().upper()}-{date_part}-{str(basis or 'UNKNOWN').strip().upper()}"


def _event_key(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["Symbol"].astype(str).str.strip().str.upper()
        + "|"
        + pd.to_datetime(frame["Fiscal_Period_End"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("UNKNOWN")
        + "|"
        + frame["Reporting_Basis"].fillna("").astype(str).str.upper()
    )


def select_first_public_filings(filings: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select earliest original filings; retain revisions and duplicate sources as ignored evidence."""

    required = {
        "Symbol",
        "Fiscal_Period_End",
        "Reporting_Basis",
        "Original_or_Revised",
        "Public_Timestamp",
    }
    missing = required.difference(filings.columns)
    if missing:
        raise ValueError(f"filings missing columns: {sorted(missing)}")
    frame = filings.copy()
    if "Source_Record_ID" not in frame.columns:
        frame["Source_Record_ID"] = ""
    frame["Symbol"] = frame["Symbol"].astype(str).str.strip().str.upper()
    frame["Fiscal_Period_End"] = frame["Fiscal_Period_End"].map(_date)
    frame["Reporting_Basis"] = frame["Reporting_Basis"].fillna("").astype(str).str.upper()
    frame["Original_or_Revised"] = frame["Original_or_Revised"].fillna("").astype(str).str.upper()
    frame["_Event_Key"] = _event_key(frame)

    selected_rows: list[pd.Series] = []
    ignored_rows: list[dict[str, object]] = []
    for event_key, group in frame.groupby("_Event_Key", sort=True):
        originals = group.loc[group["Original_or_Revised"].eq("ORIGINAL")].copy()
        if originals.empty:
            for _, row in group.iterrows():
                ignored_rows.append(
                    {
                        "Event_ID": _event_id(row["Symbol"], row["Fiscal_Period_End"], row["Reporting_Basis"]),
                        "Symbol": row["Symbol"],
                        "Fiscal_Period_End": row["Fiscal_Period_End"],
                        "Reason": "NO_ORIGINAL_FILING",
                        "Source_Record_ID": row.get("Source_Record_ID", ""),
                    }
                )
            continue
        originals["_Sort_Timestamp"] = originals["Public_Timestamp"].map(
            lambda value: pd.Timestamp(value).value if pd.notna(value) else np.iinfo(np.int64).max
        )
        originals = originals.sort_values(["_Sort_Timestamp", "Source_Record_ID"], kind="stable")
        chosen = originals.iloc[0].copy()
        chosen["_Event_Key"] = event_key
        chosen["Event_ID"] = _event_id(chosen["Symbol"], chosen["Fiscal_Period_End"], chosen["Reporting_Basis"])
        chosen["Source_Exchanges"] = "|".join(
            sorted({str(item).upper() for item in originals.get("Exchange", pd.Series(dtype=str)).dropna()})
        )
        chosen["Original_Record_Count"] = len(originals)
        selected_rows.append(chosen)
        for index, row in group.iterrows():
            if index == chosen.name:
                continue
            ignored_rows.append(
                {
                    "Event_ID": chosen["Event_ID"],
                    "Symbol": row["Symbol"],
                    "Fiscal_Period_End": row["Fiscal_Period_End"],
                    "Reason": "REVISED_OR_DUPLICATE_IGNORED"
                    if row["Original_or_Revised"] == "REVISED"
                    else "DUPLICATE_ORIGINAL_IGNORED",
                    "Source_Record_ID": row.get("Source_Record_ID", ""),
                }
            )
    selected = pd.DataFrame(selected_rows).drop(columns=["_Sort_Timestamp"], errors="ignore")
    if not selected.empty:
        selected = selected.drop(columns=["_Event_Key"], errors="ignore").reset_index(drop=True)
    ignored = pd.DataFrame(
        ignored_rows,
        columns=["Event_ID", "Symbol", "Fiscal_Period_End", "Reason", "Source_Record_ID"],
    )
    return selected, ignored


def is_timely_result(period_end: pd.Timestamp, public_date: pd.Timestamp, fiscal_quarter: str) -> bool:
    """Return whether a result meets the inclusive Q1-Q3/Q4 filing deadline."""

    end = _date(period_end)
    public = _public_date(public_date)
    quarter = str(fiscal_quarter or "").upper().strip()
    if pd.isna(end) or pd.isna(public) or quarter not in {"Q1", "Q2", "Q3", "Q4"}:
        return False
    days = 60 if quarter == "Q4" else 45
    return bool(end <= public <= end + pd.Timedelta(days=days))


def _eps_key(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["Symbol"].astype(str).str.strip().str.upper()
        + "|"
        + pd.to_datetime(frame["Fiscal_Period_End"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("UNKNOWN")
        + "|"
        + frame["Reporting_Basis"].fillna("").astype(str).str.upper()
    )


def select_reporting_basis(events: pd.DataFrame, eps: pd.DataFrame) -> pd.DataFrame:
    """Prefer consolidated current EPS, falling back to standalone when necessary."""

    if events.empty:
        result = events.copy()
        result["Selected_Basis"] = pd.Series(dtype="string")
        return result
    eps_frame = eps.copy()
    if not eps_frame.empty:
        eps_frame["Symbol"] = eps_frame["Symbol"].astype(str).str.strip().str.upper()
        eps_frame["Reporting_Basis"] = eps_frame["Reporting_Basis"].fillna("").astype(str).str.upper()
        eps_frame["_Key"] = _eps_key(eps_frame)
        available = set(
            eps_frame.loc[
                pd.to_numeric(eps_frame.get("EPS"), errors="coerce").notna(), "_Key"
            ].astype(str)
        )
    else:
        available = set()

    frame = events.copy()
    frame["Symbol"] = frame["Symbol"].astype(str).str.strip().str.upper()
    frame["Fiscal_Period_End"] = frame["Fiscal_Period_End"].map(_date)
    choices: list[pd.Series] = []
    for (_, period), group in frame.groupby(["Symbol", "Fiscal_Period_End"], sort=True):
        chosen = None
        for basis in ("CONSOLIDATED", "STANDALONE"):
            candidates = group.loc[group["Reporting_Basis"].eq(basis)]
            if candidates.empty:
                continue
            has_current_eps = any(_eps_key(candidates.to_frame().T).iloc[0] in available for _, candidates in candidates.iterrows())
            if has_current_eps or chosen is None:
                chosen = candidates.iloc[0].copy()
            if has_current_eps:
                break
        if chosen is not None:
            chosen["Selected_Basis"] = str(chosen.get("Reporting_Basis") or "").upper()
            choices.append(chosen)
    return pd.DataFrame(choices).reset_index(drop=True)


def _membership_ok(membership: pd.DataFrame, symbol: str, event_date: pd.Timestamp) -> bool:
    if pd.isna(event_date) or membership.empty:
        return False
    rows = membership.loc[membership["Symbol"].astype(str).str.upper().eq(symbol.upper())]
    if rows.empty:
        return False
    return bool(
        (
            rows["Member_From"].map(_date).le(event_date)
            & rows["Member_To"].map(_date).ge(event_date)
        ).any()
    )


def _coverage_row(event_master: pd.DataFrame) -> pd.DataFrame:
    if event_master.empty:
        return pd.DataFrame(
            [
                {
                    "Technical_EPS_Candidates": 0,
                    "Resolved_EPS_Candidates": 0,
                    "Machine_Readable_EPS_Resolution": np.nan,
                    "Unresolved_Event_IDs": "",
                    "Cross_Exchange_EPS_Mismatches": 0,
                    "NSE_Only": 0,
                    "BSE_Only": 0,
                    "Cross_Exchange": 0,
                    "Original_Record_Count": 0,
                    "Revision_Ignored_Count": 0,
                    "Structural_Exclusion_Count": 0,
                }
            ]
        )
    technical = event_master.loc[
        event_master["PIT_Membership_OK"].astype(bool)
        & event_master["Timely_Result"].astype(bool)
        & event_master["Selected_Basis"].notna()
        & event_master["Machine_Readable_URL"].notna()
    ]
    resolved = technical["EPS_Source_Resolved"].astype(bool)
    exchanges = event_master["Source_Exchanges"].fillna("").astype(str)
    return pd.DataFrame(
        [
            {
                "Technical_EPS_Candidates": len(technical),
                "Resolved_EPS_Candidates": int(resolved.sum()),
                "Machine_Readable_EPS_Resolution": float(resolved.mean()) if len(technical) else np.nan,
                "Unresolved_Event_IDs": "|".join(technical.loc[~resolved, "Event_ID"].astype(str)),
                "Cross_Exchange_EPS_Mismatches": int(event_master["EPS_Source_Status"].eq("CROSS_EXCHANGE_EPS_MISMATCH").sum()),
                "NSE_Only": int(exchanges.eq("NSE").sum()),
                "BSE_Only": int(exchanges.eq("BSE").sum()),
                "Cross_Exchange": int(exchanges.str.contains(r"NSE\|BSE|BSE\|NSE", regex=True).sum()),
                "Original_Record_Count": int(pd.to_numeric(event_master["Original_Record_Count"], errors="coerce").fillna(0).sum()),
                "Revision_Ignored_Count": 0,
                "Structural_Exclusion_Count": int((~event_master["Primary_Event"].astype(bool)).sum()),
            }
        ]
    )


def build_event_master(
    filings: pd.DataFrame,
    eps: pd.DataFrame,
    membership: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build event master, explicit exclusions, coverage evidence, and ignored filing audit."""

    first_public, ignored = select_first_public_filings(filings)
    selected = select_reporting_basis(first_public, eps)
    rows: list[dict[str, object]] = []
    exclusions: list[dict[str, object]] = []
    eps_frame = eps.copy()
    if not eps_frame.empty:
        eps_frame["Symbol"] = eps_frame["Symbol"].astype(str).str.upper().str.strip()
        eps_frame["Fiscal_Period_End"] = eps_frame["Fiscal_Period_End"].map(_date)
        eps_frame["Reporting_Basis"] = eps_frame["Reporting_Basis"].fillna("").astype(str).str.upper()

    for _, event in selected.iterrows():
        symbol = str(event.get("Symbol", "")).upper().strip()
        period_end = _date(event.get("Fiscal_Period_End"))
        public_timestamp = event.get("Public_Timestamp")
        public_date = _public_date(public_timestamp)
        basis = str(event.get("Selected_Basis") or "").upper()
        event_id = str(event.get("Event_ID") or _event_id(symbol, period_end, basis))
        fiscal_quarter = str(event.get("Fiscal_Quarter") or "").upper()
        timely = is_timely_result(period_end, public_date, fiscal_quarter)
        pit_ok = _membership_ok(membership, symbol, public_date)
        matching = eps_frame.loc[
            eps_frame["Symbol"].eq(symbol)
            & eps_frame["Fiscal_Period_End"].eq(period_end)
            & eps_frame["Reporting_Basis"].eq(basis)
            & eps_frame["Original_or_Revised"].fillna("").astype(str).str.upper().eq("ORIGINAL")
        ] if not eps_frame.empty else pd.DataFrame()
        values = pd.to_numeric(matching.get("EPS", pd.Series(dtype=float)), errors="coerce").dropna()
        mismatch = len(values) > 1 and not np.isclose(values.max(), values.min())
        resolved = bool(len(values) and not mismatch)
        machine_url = str(event.get("Machine_Readable_URL") or "").strip()
        if not machine_url and not matching.empty:
            machine_url = str(matching.iloc[0].get("Machine_Readable_URL") or "").strip()
        row = {
            "Event_ID": event_id,
            "Symbol": symbol,
            "Fiscal_Period_End": period_end,
            "Event_Public_Timestamp": public_timestamp,
            "Event_Public_Date": public_date,
            "Reporting_Basis": basis,
            "Selected_Basis": basis or np.nan,
            "Fiscal_Quarter": fiscal_quarter,
            "Timely_Result": timely,
            "PIT_Membership_OK": pit_ok,
            "EPS_Source_Status": "CROSS_EXCHANGE_EPS_MISMATCH" if mismatch else ("RESOLVED" if resolved else "UNRESOLVED"),
            "EPS_Source_Resolved": resolved,
            "Machine_Readable_URL": machine_url or np.nan,
            "Source_Exchanges": event.get("Source_Exchanges", ""),
            "Original_or_Revised": event.get("Original_or_Revised", "ORIGINAL"),
            "Original_Record_Count": event.get("Original_Record_Count", 1),
            "Primary_Event": (
                bool(PRIMARY_START <= public_date <= PRIMARY_END) and pit_ok
                if pd.notna(public_date)
                else False
            ),
        }
        rows.append(row)
        reason = None
        if not pit_ok:
            reason = "PIT_MEMBERSHIP_NOT_ACTIVE"
        elif not (pd.notna(public_date) and PRIMARY_START <= public_date <= PRIMARY_END):
            reason = "NON_PRIMARY_EVENT"
        elif not timely:
            reason = "LATE_RESULT"
        elif not basis:
            reason = "INVALID_REPORTING_BASIS"
        elif mismatch or not resolved:
            reason = "EPS_SOURCE_UNRESOLVED"
        if reason:
            exclusions.append(
                {
                    "Event_ID": event_id,
                    "Symbol": symbol,
                    "Fiscal_Period_End": period_end,
                    "Reason": reason,
                    "Event_Public_Date": public_date,
                }
            )

    master = pd.DataFrame(rows)
    exclusion_frame = pd.DataFrame(
        exclusions,
        columns=["Event_ID", "Symbol", "Fiscal_Period_End", "Reason", "Event_Public_Date"],
    )
    coverage = _coverage_row(master)
    return master, exclusion_frame, coverage, ignored


def write_event_outputs(
    output_dir: Path,
    event_master: pd.DataFrame,
    exclusions: pd.DataFrame,
    coverage: pd.DataFrame,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    event_master.to_csv(output_dir / "e1_event_master.csv", index=False, date_format="%Y-%m-%d")
    exclusions.to_csv(output_dir / "e1_event_exclusions.csv", index=False, date_format="%Y-%m-%d")
    coverage.to_csv(output_dir / "e1_source_coverage.csv", index=False)
