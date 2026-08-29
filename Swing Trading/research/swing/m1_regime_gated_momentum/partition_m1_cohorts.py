"""Partition frozen V3 evidence by the independently computed M1 regime."""

from __future__ import annotations

import pandas as pd


AUDIT_COLUMNS = ("Entry_ID", "Symbol", "Violation", "Observed", "Expected")
CLASSIFICATION_COLUMNS = (
    "Entry_ID",
    "Symbol",
    "Signal_Date",
    "M1_Regime",
    "DATA_SAFE",
    "INDEX_TREND_OK",
    "BREADTH_OK",
    "SMA50_Breadth_Coverage",
    "Pct_Above_SMA50",
    "Nifty500_Close",
    "Nifty500_SMA50",
    "Nifty500_SMA200",
    "V3_Entry_Status",
    "V3_Cancellation_Reason",
)


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


def _ids(frame: pd.DataFrame) -> set[str]:
    return set(frame["Entry_ID"].dropna().astype(str)) if "Entry_ID" in frame else set()


def _subset(frame: pd.DataFrame, ids: set[str]) -> pd.DataFrame:
    if "Entry_ID" not in frame:
        return frame.iloc[0:0].copy()
    return frame.loc[frame["Entry_ID"].astype(str).isin(ids)].copy().reset_index(drop=True)


def _with_classification(frame: pd.DataFrame, classification: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        result = frame.copy()
        if "M1_Regime" not in result:
            result["M1_Regime"] = pd.Series(dtype=str)
        return result
    market_columns = [
        column
        for column in (
            "M1_Regime",
            "DATA_SAFE",
            "INDEX_TREND_OK",
            "BREADTH_OK",
            "SMA50_Breadth_Coverage",
            "Pct_Above_SMA50",
            "Nifty500_Close",
            "Nifty500_SMA50",
            "Nifty500_SMA200",
        )
        if column in classification.columns
    ]
    classification_for_join = classification.drop_duplicates("Entry_ID", keep="first")
    result = frame.merge(
        classification_for_join.loc[:, ["Entry_ID", *market_columns]],
        on="Entry_ID",
        how="left",
        validate="one_to_one",
        suffixes=("", "_classification"),
    )
    for column in market_columns:
        classification_column = f"{column}_classification"
        if classification_column in result:
            result[column] = result[column].where(result[column].notna(), result[classification_column])
            result = result.drop(columns=classification_column)
    return result


def partition_v3_evidence(
    classification: pd.DataFrame,
    artifacts: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Return enabled and disabled cohort frames plus explicit audit rows."""

    audit_rows: list[dict[str, object]] = []
    classification = classification.copy()
    if "Entry_ID" not in classification.columns:
        audit_rows.append(
            _audit(
                "INVALID_CLASSIFICATION",
                observed="Entry_ID missing",
                expected="one classified row per qualified V3 signal",
            )
        )
        return {}, pd.DataFrame(audit_rows, columns=AUDIT_COLUMNS)

    classification["Entry_ID"] = classification["Entry_ID"].astype(str)
    duplicate_ids = classification.loc[
        classification["Entry_ID"].duplicated(keep=False), "Entry_ID"
    ]
    for entry_id in sorted(set(duplicate_ids)):
        audit_rows.append(
            _audit(
                "DUPLICATE_REGIME_CLASSIFICATION",
                entry_id=entry_id,
                observed="multiple M1 regime rows",
                expected="exactly one M1 regime row",
            )
        )

    signals = artifacts.get("v3_signal_candidates.csv", pd.DataFrame())
    entries = artifacts.get("v3_entries.csv", pd.DataFrame())
    cancellations = artifacts.get("v3_entry_cancellations.csv", pd.DataFrame())
    setup = artifacts.get("v3_setup_quality_trades.csv", pd.DataFrame())
    practical = artifacts.get("v3_practical_trades.csv", pd.DataFrame())
    qualified = (
        set(
            signals.loc[
                signals.get("Signal_Qualified", pd.Series(False, index=signals.index)).map(
                    lambda value: str(value).strip().lower() in {"true", "1", "yes", "y"}
                ),
                "Entry_ID",
            ].dropna().astype(str)
        )
        if "Entry_ID" in signals
        else set()
    )
    classified_ids = set(classification["Entry_ID"])
    if classified_ids != qualified:
        for entry_id in sorted(qualified - classified_ids):
            audit_rows.append(
                _audit(
                    "UNCLASSIFIED_QUALIFIED_SIGNAL",
                    entry_id=entry_id,
                    observed="missing M1 classification",
                    expected="classified exactly once",
                )
            )
        for entry_id in sorted(classified_ids - qualified):
            audit_rows.append(
                _audit(
                    "NONQUALIFIED_SIGNAL_CLASSIFIED",
                    entry_id=entry_id,
                    observed="classification is not a qualified V3 signal",
                    expected="qualified V3 signal",
                )
            )

    entry_ids = _ids(entries)
    cancellation_ids = _ids(cancellations)
    classification["V3_Entry_Status"] = "UNKNOWN"
    classification["V3_Cancellation_Reason"] = pd.NA
    classification.loc[classification["Entry_ID"].isin(entry_ids), "V3_Entry_Status"] = "ACCEPTED"
    cancellation_mask = classification["Entry_ID"].isin(cancellation_ids)
    classification.loc[cancellation_mask, "V3_Entry_Status"] = "CANCELLED"
    if "Cancellation_Reason" in cancellations:
        reasons = cancellations.drop_duplicates("Entry_ID").set_index("Entry_ID")["Cancellation_Reason"]
        classification.loc[cancellation_mask, "V3_Cancellation_Reason"] = (
            classification.loc[cancellation_mask, "Entry_ID"].map(reasons)
        )
    unknown = classification.loc[classification["V3_Entry_Status"].eq("UNKNOWN")]
    for _, row in unknown.iterrows():
        audit_rows.append(
            _audit(
                "CLASSIFICATION_NOT_ACCEPTED_OR_CANCELLED",
                entry_id=row["Entry_ID"],
                symbol=row.get("Symbol", ""),
                observed="no frozen V3 entry/cancellation row",
                expected="accepted or cancelled",
            )
        )

    enabled_mask = classification["M1_Regime"].astype(str).eq("MOMENTUM_ENABLED")
    disabled_mask = classification["M1_Regime"].astype(str).eq("MOMENTUM_DISABLED")
    invalid_regime = classification.loc[~(enabled_mask | disabled_mask)]
    for _, row in invalid_regime.iterrows():
        audit_rows.append(
            _audit(
                "INVALID_M1_REGIME",
                entry_id=row["Entry_ID"],
                symbol=row.get("Symbol", ""),
                observed=row.get("M1_Regime", ""),
                expected="MOMENTUM_ENABLED or MOMENTUM_DISABLED",
            )
        )

    enabled_ids = set(classification.loc[enabled_mask, "Entry_ID"])
    disabled_ids = set(classification.loc[disabled_mask, "Entry_ID"])
    enabled_entry_ids = enabled_ids & entry_ids
    disabled_entry_ids = disabled_ids & entry_ids
    enabled_cancel_ids = enabled_ids & cancellation_ids
    disabled_cancel_ids = disabled_ids & cancellation_ids

    frozen_completed = _ids(setup) & _ids(practical)
    enabled_setup_ids = _ids(setup) & enabled_entry_ids
    disabled_setup_ids = _ids(setup) & disabled_entry_ids
    enabled_practical_ids = _ids(practical) & enabled_entry_ids
    disabled_practical_ids = _ids(practical) & disabled_entry_ids

    if enabled_ids | disabled_ids != qualified:
        audit_rows.append(
            _audit(
                "QUALIFIED_PARTITION_MISMATCH",
                observed=f"enabled={len(enabled_ids)}, disabled={len(disabled_ids)}, frozen={len(qualified)}",
                expected="enabled union disabled equals frozen qualified",
            )
        )
    if enabled_entry_ids | disabled_entry_ids != entry_ids or enabled_entry_ids & disabled_entry_ids:
        audit_rows.append(
            _audit(
                "ACCEPTED_PARTITION_MISMATCH",
                observed=f"partitioned={len(enabled_entry_ids | disabled_entry_ids)}, frozen={len(entry_ids)}",
                expected="enabled and disabled accepted union equals frozen accepted",
            )
        )
    if enabled_cancel_ids | disabled_cancel_ids != cancellation_ids or enabled_cancel_ids & disabled_cancel_ids:
        audit_rows.append(
            _audit(
                "CANCELLED_PARTITION_MISMATCH",
                observed=f"partitioned={len(enabled_cancel_ids | disabled_cancel_ids)}, frozen={len(cancellation_ids)}",
                expected="enabled and disabled cancellation union equals frozen cancellations",
            )
        )
    if enabled_setup_ids != enabled_practical_ids or disabled_setup_ids != disabled_practical_ids:
        audit_rows.append(
            _audit(
                "COHORT_COMPLETED_PAIR_MISMATCH",
                observed=f"enabled setup/practical={len(enabled_setup_ids)}/{len(enabled_practical_ids)}, disabled={len(disabled_setup_ids)}/{len(disabled_practical_ids)}",
                expected="setup and practical Entry_ID sets match in each cohort",
            )
        )
    if enabled_setup_ids | disabled_setup_ids != frozen_completed:
        audit_rows.append(
            _audit(
                "COMPLETED_PARTITION_MISMATCH",
                observed=f"partitioned={len(enabled_setup_ids | disabled_setup_ids)}, frozen paired={len(frozen_completed)}",
                expected="enabled and disabled completed union equals frozen paired sample",
            )
        )

    cohorts = {
        "classification": classification,
        "enabled_entries": _with_classification(_subset(entries, enabled_entry_ids), classification),
        "enabled_cancellations": _with_classification(_subset(cancellations, enabled_cancel_ids), classification),
        "disabled_shadow_entries": _with_classification(_subset(entries, disabled_entry_ids), classification),
        "disabled_shadow_cancellations": _with_classification(_subset(cancellations, disabled_cancel_ids), classification),
        "enabled_setup": _with_classification(_subset(setup, enabled_setup_ids), classification),
        "enabled_practical": _with_classification(_subset(practical, enabled_practical_ids), classification),
        "disabled_setup": _with_classification(_subset(setup, disabled_setup_ids), classification),
        "disabled_practical": _with_classification(_subset(practical, disabled_practical_ids), classification),
    }
    return cohorts, pd.DataFrame(audit_rows, columns=AUDIT_COLUMNS).drop_duplicates(
        subset=["Entry_ID", "Symbol", "Violation"]
    ).reset_index(drop=True)
