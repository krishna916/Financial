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
        if not filings.empty:
            raise ValueError(f"filings missing columns: {sorted(missing)}")
        filings = filings.copy()
        for column in sorted(missing):
            filings[column] = pd.Series(dtype="object")
    frame = filings.copy()
    if "Source_Record_ID" not in frame.columns:
        frame["Source_Record_ID"] = ""
    frame["Symbol"] = frame["Symbol"].astype(str).str.strip().str.upper()
    frame["Fiscal_Period_End"] = frame["Fiscal_Period_End"].map(_date)
    frame["Reporting_Basis"] = frame["Reporting_Basis"].fillna("").astype(str).str.upper()
    frame["Original_or_Revised"] = frame["Original_or_Revised"].fillna("").astype(str).str.upper()
    frame["_Event_Key"] = _event_key(frame)
    frame["_Source_Row_Order"] = np.arange(len(frame), dtype=np.int64)
    originals = frame.loc[frame["Original_or_Revised"].eq("ORIGINAL")].copy()
    if not originals.empty:
        originals["_Sort_Timestamp"] = originals["Public_Timestamp"].map(
            lambda value: pd.Timestamp(value).value if pd.notna(value) else np.iinfo(np.int64).max
        )
        chosen = (
            originals.sort_values(
                ["_Event_Key", "_Sort_Timestamp", "Source_Record_ID"], kind="stable"
            )
            .drop_duplicates("_Event_Key", keep="first")
            .sort_values("_Event_Key", kind="stable")
            .copy()
        )
        chosen["Event_ID"] = [
            _event_id(symbol, period, basis)
            for symbol, period, basis in zip(
                chosen["Symbol"],
                chosen["Fiscal_Period_End"],
                chosen["Reporting_Basis"],
            )
        ]
        original_counts = originals.groupby("_Event_Key", sort=True).size()
        chosen["Original_Record_Count"] = chosen["_Event_Key"].map(original_counts)
        if "Exchange" in originals.columns:
            exchanges = originals.loc[
                originals["Exchange"].notna(), ["_Event_Key", "Exchange"]
            ].copy()
            exchanges["_Exchange"] = exchanges["Exchange"].astype(str).str.upper()
            exchanges = exchanges.drop_duplicates(["_Event_Key", "_Exchange"])
            exchanges = exchanges.sort_values(["_Event_Key", "_Exchange"], kind="stable")
            source_exchanges = exchanges.groupby("_Event_Key", sort=True)["_Exchange"].agg("|".join)
            chosen["Source_Exchanges"] = chosen["_Event_Key"].map(source_exchanges).fillna("")
        else:
            chosen["Source_Exchanges"] = ""
    else:
        chosen = pd.DataFrame()

    chosen_keys = set(chosen["_Event_Key"]) if not chosen.empty else set()
    ignored = frame.loc[
        ~frame["_Source_Row_Order"].isin(chosen.get("_Source_Row_Order", pd.Series(dtype=np.int64)))
    ].sort_values(["_Event_Key", "_Source_Row_Order"], kind="stable").copy()
    if not ignored.empty:
        ignored["Event_ID"] = ignored["_Event_Key"].map(
            chosen.set_index("_Event_Key")["Event_ID"] if not chosen.empty else pd.Series(dtype=str)
        )
        no_original = ~ignored["_Event_Key"].isin(chosen_keys)
        ignored.loc[no_original, "Event_ID"] = [
            _event_id(symbol, period, basis)
            for symbol, period, basis in zip(
                ignored.loc[no_original, "Symbol"],
                ignored.loc[no_original, "Fiscal_Period_End"],
                ignored.loc[no_original, "Reporting_Basis"],
            )
        ]
        ignored["Reason"] = np.where(
            no_original,
            "NO_ORIGINAL_FILING",
            np.where(
                ignored["Original_or_Revised"].eq("REVISED"),
                "REVISED_OR_DUPLICATE_IGNORED",
                "DUPLICATE_ORIGINAL_IGNORED",
            ),
        )
        ignored = ignored[
            ["Event_ID", "Symbol", "Fiscal_Period_End", "Reason", "Source_Record_ID"]
        ]
    else:
        ignored = pd.DataFrame(
            columns=["Event_ID", "Symbol", "Fiscal_Period_End", "Reason", "Source_Record_ID"]
        )
    if chosen.empty:
        selected = pd.DataFrame()
    else:
        selected = chosen.drop(
            columns=["_Sort_Timestamp", "_Event_Key", "_Source_Row_Order"], errors="ignore"
        ).reset_index(drop=True)
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


def _flag(value: object) -> bool:
    if value is None or (not isinstance(value, (list, tuple, dict, set)) and pd.isna(value)):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def formal_event_eligibility(row: pd.Series) -> tuple[bool, str]:
    """Apply the frozen primary-event rules in their formal decision order."""

    event_date = _date(row.get("Event_Public_Date"))
    if pd.isna(event_date) or not (PRIMARY_START <= event_date <= PRIMARY_END):
        return False, "NON_PRIMARY_EVENT"
    if not _flag(row.get("PIT_Membership_OK", False)):
        return False, "PIT_MEMBERSHIP_NOT_ACTIVE"
    if not _flag(row.get("Timely_Result", False)):
        return False, "LATE_RESULT"
    selected_basis = row.get("Selected_Basis")
    basis = "" if selected_basis is None or pd.isna(selected_basis) else str(selected_basis).strip()
    if not basis:
        return False, "INVALID_REPORTING_BASIS"
    if str(row.get("EPS_Source_Status") or "") == "CROSS_EXCHANGE_EPS_MISMATCH":
        return False, "CROSS_EXCHANGE_EPS_MISMATCH"
    if not _flag(row.get("EPS_Source_Resolved", False)):
        return False, "EPS_SOURCE_UNRESOLVED"
    return True, ""


def _eps_key(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["Symbol"].astype(str).str.strip().str.upper()
        + "|"
        + pd.to_datetime(frame["Fiscal_Period_End"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("UNKNOWN")
        + "|"
        + frame["Reporting_Basis"].fillna("").astype(str).str.upper()
    )


def eps_values_match(a: float, b: float) -> bool:
    """Apply the frozen cross-exchange EPS equality tolerance."""

    absolute = abs(float(a) - float(b))
    if absolute <= 0.01:
        return True
    scale = max(abs(float(a)), abs(float(b)))
    return scale > 0 and absolute / scale <= 0.005


def select_reporting_basis(
    events: pd.DataFrame,
    eps: pd.DataFrame,
    actions: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Prefer the first basis with a complete comparable point-in-time SUE chain."""

    if events.empty:
        result = events.copy()
        result["Selected_Basis"] = pd.Series(dtype="string")
        return result
    frame = events.copy()
    frame["Symbol"] = frame["Symbol"].astype(str).str.strip().str.upper()
    frame["Fiscal_Period_End"] = frame["Fiscal_Period_End"].map(_date)
    eps_frame = eps.copy()
    if not eps_frame.empty:
        eps_frame["Symbol"] = eps_frame["Symbol"].astype(str).str.strip().str.upper()
        eps_frame["Fiscal_Period_End"] = eps_frame["Fiscal_Period_End"].map(_date)
        eps_frame["Reporting_Basis"] = eps_frame["Reporting_Basis"].fillna("").astype(str).str.upper()
        if "EPS" in eps_frame.columns:
            eps_frame["EPS"] = pd.to_numeric(eps_frame["EPS"], errors="coerce")
        if "Public_Timestamp" in eps_frame.columns:
            from compute_e1_sue import _quarter_index, _timestamp

            eps_frame["_Public_Timestamp"] = eps_frame["Public_Timestamp"].map(_timestamp)
    eps_by_identity: dict[tuple[str, str], pd.DataFrame] = {}
    if {"Symbol", "Reporting_Basis"}.issubset(eps_frame.columns):
        for (symbol, basis), group in eps_frame.groupby(
            ["Symbol", "Reporting_Basis"], sort=False
        ):
            history = group.copy()
            history.attrs["_e1_prepared_history"] = True
            if {"Fiscal_Period_End", "EPS", "Public_Timestamp"}.issubset(history.columns):
                public_values = history.get("_Public_Timestamp", history["Public_Timestamp"].map(_timestamp))
                original_values = (
                    history["Original_or_Revised"].fillna("").astype(str).str.upper().eq("ORIGINAL")
                    if "Original_or_Revised" in history.columns
                    else pd.Series(True, index=history.index)
                )
                prepared_rows = []
                for period, public, value, original in zip(
                    history["Fiscal_Period_End"],
                    public_values,
                    history["EPS"],
                    original_values,
                ):
                    if pd.notna(period) and pd.notna(value):
                        prepared_rows.append(
                            (
                                period,
                                _quarter_index(period),
                                public,
                                float(value),
                                bool(original),
                            )
                        )
                history.attrs["_e1_prepared_basis_rows"] = tuple(prepared_rows)
            eps_by_identity[(symbol, basis)] = history
    from compute_e1_sue import _prepare_action_index, basis_chain_status

    action_frame = _prepare_action_index(actions)
    choices: list[pd.Series] = []
    for (_, period), group in frame.groupby(["Symbol", "Fiscal_Period_End"], sort=True):
        fallback = None
        fallback_reason = "INSUFFICIENT_EPS_HISTORY"
        for basis in ("CONSOLIDATED", "STANDALONE"):
            candidates = group.loc[group["Reporting_Basis"].eq(basis)]
            if candidates.empty:
                continue
            candidate = candidates.iloc[0].copy()
            if fallback is None:
                fallback = candidate.copy()

            basis_history = eps_by_identity.get(
                (str(candidate["Symbol"]), basis), eps_frame.iloc[0:0]
            )
            ok, reason = basis_chain_status(
                str(candidate["Symbol"]),
                period,
                basis,
                candidate.get("Public_Timestamp"),
                basis_history,
                action_frame,
            )
            if ok:
                chosen = candidate
                chosen["Selected_Basis"] = basis
                choices.append(chosen)
                break
            fallback_reason = reason
        else:
            chosen = fallback
            if chosen is not None:
                chosen["Selected_Basis"] = np.nan
                chosen["Basis_Selection_Reason"] = fallback_reason
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
        event_master["Event_Public_Date"].map(_date).between(PRIMARY_START, PRIMARY_END, inclusive="both")
        & event_master["PIT_Membership_OK"].map(_flag)
        & event_master["Timely_Result"].map(_flag)
        & event_master["Selected_Basis"].fillna("").astype(str).str.strip().ne("")
        & event_master["Machine_Readable_URL"].fillna("").astype(str).str.strip().ne("")
        & event_master["Original_or_Revised"].fillna("").astype(str).str.upper().eq("ORIGINAL")
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
    actions: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build event master, explicit exclusions, coverage evidence, and ignored filing audit."""

    first_public, ignored = select_first_public_filings(filings)
    selected = select_reporting_basis(first_public, eps, actions)
    rows: list[dict[str, object]] = []
    exclusions: list[dict[str, object]] = []
    eps_frame = eps.copy()
    if not eps_frame.empty:
        eps_frame["Symbol"] = eps_frame["Symbol"].astype(str).str.upper().str.strip()
        eps_frame["Fiscal_Period_End"] = eps_frame["Fiscal_Period_End"].map(_date)
        eps_frame["Reporting_Basis"] = eps_frame["Reporting_Basis"].fillna("").astype(str).str.upper()

    eps_by_event_key: dict[tuple[str, pd.Timestamp, str], pd.DataFrame] = {}
    eps_key_columns = {"Symbol", "Fiscal_Period_End", "Reporting_Basis", "Original_or_Revised"}
    if not eps_frame.empty and eps_key_columns.issubset(eps_frame.columns):
        eps_frame["Original_or_Revised"] = eps_frame["Original_or_Revised"].fillna("").astype(str).str.upper()
        eps_frame["EPS"] = pd.to_numeric(eps_frame.get("EPS"), errors="coerce")
        original_eps = eps_frame.loc[eps_frame["Original_or_Revised"].eq("ORIGINAL")]
        eps_by_event_key = {
            (symbol, period, basis): group
            for (symbol, period, basis), group in original_eps.groupby(
                ["Symbol", "Fiscal_Period_End", "Reporting_Basis"], sort=False
            )
        }

    membership_by_symbol: dict[str, pd.DataFrame] | None = None
    membership_key_columns = {"Symbol", "Member_From", "Member_To"}
    if membership_key_columns.issubset(membership.columns):
        membership_frame = membership.copy()
        membership_frame["Symbol"] = membership_frame["Symbol"].astype(str).str.upper().str.strip()
        membership_frame["_Member_From"] = membership_frame["Member_From"].map(_date)
        membership_frame["_Member_To"] = membership_frame["Member_To"].map(_date)
        membership_by_symbol = {
            symbol: group
            for symbol, group in membership_frame.groupby("Symbol", sort=False)
        }

    for _, event in selected.iterrows():
        symbol = str(event.get("Symbol", "")).upper().strip()
        period_end = _date(event.get("Fiscal_Period_End"))
        public_timestamp = event.get("Public_Timestamp")
        public_date = _public_date(public_timestamp)
        selected_basis = event.get("Selected_Basis")
        basis = "" if selected_basis is None or pd.isna(selected_basis) else str(selected_basis).upper()
        event_id = str(event.get("Event_ID") or _event_id(symbol, period_end, basis))
        fiscal_quarter = str(event.get("Fiscal_Quarter") or "").upper()
        timely = is_timely_result(period_end, public_date, fiscal_quarter)
        if membership_by_symbol is None:
            pit_ok = _membership_ok(membership, symbol, public_date)
        else:
            membership_rows = membership_by_symbol.get(symbol, pd.DataFrame())
            pit_ok = bool(
                not membership_rows.empty
                and (
                    membership_rows["_Member_From"].le(public_date)
                    & membership_rows["_Member_To"].ge(public_date)
                ).any()
            )
        matching = eps_by_event_key.get(
            (symbol, period_end, basis), eps_frame.iloc[0:0]
        )
        values = pd.to_numeric(matching.get("EPS", pd.Series(dtype=float)), errors="coerce").dropna()
        mismatch = len(values) > 1 and not eps_values_match(values.max(), values.min())
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
            "Primary_Event": False,
        }
        eligible, eligibility_reason = formal_event_eligibility(pd.Series(row))
        row["Primary_Event"] = eligible
        rows.append(row)
        if eligibility_reason:
            exclusions.append(
                {
                    "Event_ID": event_id,
                    "Symbol": symbol,
                    "Fiscal_Period_End": period_end,
                    "Reason": eligibility_reason,
                    "Exclusion_Stage": "EVENT",
                    "Event_Public_Date": public_date,
                }
            )

    master = pd.DataFrame(rows)
    exclusion_frame = pd.DataFrame(
        exclusions,
        columns=["Event_ID", "Symbol", "Fiscal_Period_End", "Reason", "Exclusion_Stage", "Event_Public_Date"],
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
