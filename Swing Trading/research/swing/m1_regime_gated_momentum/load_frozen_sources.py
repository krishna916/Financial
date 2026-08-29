"""Load the closed V3 and point-in-time market evidence used by M1.

The V3 output directory is an immutable input to M1.  This module only reads
CSV evidence and emits explicit audit rows when the required evidence cannot
support the frozen experiment.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
V3_OUTPUT_ROOT = (
    REPOSITORY_ROOT
    / "Swing Trading/research/swing/strategy_v3_shallow_pullback/output"
)
BREADTH_PATH = (
    REPOSITORY_ROOT
    / "Swing Trading/research/swing/market_breadth/output/nifty500_breadth_daily.csv"
)
INDEX_PATH = REPOSITORY_ROOT / "Swing Trading/nifty500_regime_daily.csv"
MEMBERSHIP_PATH = (
    REPOSITORY_ROOT
    / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv"
)
SECTOR_MAP_PATH = (
    REPOSITORY_ROOT
    / "Swing Trading/research/swing/sector_leadership/stock_sector_map.csv"
)

V3_REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "v3_signal_candidates.csv": (
        "Entry_ID",
        "Symbol",
        "Signal_Date",
        "Signal_Qualified",
    ),
    "v3_entries.csv": (
        "Entry_ID",
        "Symbol",
        "Signal_Date",
        "Entry_Date",
        "Entry_Open",
        "Structural_Stop",
        "Initial_Risk",
    ),
    "v3_entry_cancellations.csv": (
        "Entry_ID",
        "Symbol",
        "Signal_Date",
        "Cancellation_Reason",
    ),
    "v3_setup_quality_trades.csv": (
        "Entry_ID",
        "Symbol",
        "Signal_Date",
        "Entry_Date",
        "Entry_Open",
        "Structural_Stop",
        "Initial_Risk",
        "Exit_Date",
        "Exit_Price",
        "Return",
    ),
    "v3_practical_trades.csv": (
        "Entry_ID",
        "Symbol",
        "Signal_Date",
        "Entry_Date",
        "Entry_Open",
        "Structural_Stop",
        "Initial_Risk",
        "Exit_Date",
        "Exit_Price",
        "R_Multiple",
        "Holding_Sessions",
        "Exit_Reason",
    ),
    "v3_validation_gates.csv": ("Gate", "Passed", "Value", "Status"),
}

BREADTH_COLUMNS = ("Date", "SMA50_Denominator", "Pct_Above_SMA50")
INDEX_COLUMNS = ("Date", "Close", "SMA50", "SMA200")
MEMBERSHIP_COLUMNS = ("Symbol", "Member_From", "Member_To", "Method")
AUDIT_COLUMNS = ("Entry_ID", "Symbol", "Violation", "Observed", "Expected")


def _audit_row(
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


def _empty_audit() -> pd.DataFrame:
    return pd.DataFrame(columns=AUDIT_COLUMNS)


def _truthy(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _parse_date_columns(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_datetime(result[column], errors="coerce")
    return result


def load_required_csv(
    path: Path,
    required_columns: tuple[str, ...],
    parse_dates: tuple[str, ...] = (),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read one required CSV and return its frame plus schema audit rows."""

    audit: list[dict[str, object]] = []
    try:
        frame = pd.read_csv(path)
    except FileNotFoundError:
        audit.append(
            _audit_row(
                "MISSING_REQUIRED_ARTIFACT",
                observed=str(path),
                expected="readable CSV",
            )
        )
        return pd.DataFrame(), pd.DataFrame(audit, columns=AUDIT_COLUMNS)
    except (pd.errors.EmptyDataError, OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        audit.append(
            _audit_row(
                "INVALID_REQUIRED_ARTIFACT",
                observed=f"{path}: {exc}",
                expected="readable CSV with required columns",
            )
        )
        return pd.DataFrame(), pd.DataFrame(audit, columns=AUDIT_COLUMNS)

    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        audit.append(
            _audit_row(
                "INVALID_REQUIRED_ARTIFACT",
                observed=",".join(frame.columns.astype(str)),
                expected=f"columns={','.join(missing)}",
            )
        )
        return frame, pd.DataFrame(audit, columns=AUDIT_COLUMNS)

    parsed = _parse_date_columns(frame, parse_dates)
    for column in parse_dates:
        if column in parsed.columns and parsed[column].isna().any():
            audit.append(
                _audit_row(
                    "INVALID_REQUIRED_ARTIFACT",
                    observed=f"invalid dates in {column}",
                    expected="all dates parse successfully",
                )
            )
    return parsed, pd.DataFrame(audit, columns=AUDIT_COLUMNS)


def _date_columns(frame: pd.DataFrame) -> tuple[str, ...]:
    return tuple(
        column
        for column in frame.columns
        if column.endswith("Date") or column in {"Date", "Member_From", "Member_To"}
    )


def load_v3_artifacts(
    v3_output_root: Path = V3_OUTPUT_ROOT,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Load all required V3 files without modifying or regenerating them."""

    artifacts: dict[str, pd.DataFrame] = {}
    audit_frames: list[pd.DataFrame] = []
    for filename, required_columns in V3_REQUIRED_COLUMNS.items():
        frame, audit = load_required_csv(
            Path(v3_output_root) / filename,
            required_columns,
            parse_dates=tuple(
                column
                for column in required_columns
                if column.endswith("Date") or column in {"Date", "Member_From", "Member_To"}
            ),
        )
        artifacts[filename] = frame
        if not audit.empty:
            audit_frames.append(audit)

    audit = (
        pd.concat(audit_frames, ignore_index=True)
        if audit_frames
        else _empty_audit()
    )
    return artifacts, audit


def _ids(frame: pd.DataFrame) -> set[str]:
    if "Entry_ID" not in frame.columns:
        return set()
    return set(frame["Entry_ID"].dropna().astype(str))


def _duplicate_ids(frame: pd.DataFrame, violation: str) -> list[dict[str, object]]:
    if "Entry_ID" not in frame.columns:
        return []
    duplicates = frame.loc[frame["Entry_ID"].duplicated(keep=False), "Entry_ID"]
    return [
        _audit_row(
            violation,
            entry_id=entry_id,
            observed="duplicate Entry_ID",
            expected="unique Entry_ID",
        )
        for entry_id in sorted(set(duplicates.astype(str)))
    ]


def validate_frozen_v3_accounting(
    artifacts: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Check the V3 qualified/accepted/cancelled/completed accounting contract."""

    violations: list[dict[str, object]] = []
    for filename, frame in artifacts.items():
        violations.extend(_duplicate_ids(frame, "DUPLICATE_ENTRY_ID"))

    signals = artifacts.get("v3_signal_candidates.csv", pd.DataFrame())
    entries = artifacts.get("v3_entries.csv", pd.DataFrame())
    cancellations = artifacts.get("v3_entry_cancellations.csv", pd.DataFrame())
    setup = artifacts.get("v3_setup_quality_trades.csv", pd.DataFrame())
    practical = artifacts.get("v3_practical_trades.csv", pd.DataFrame())
    gates = artifacts.get("v3_validation_gates.csv", pd.DataFrame())

    qualified = (
        set(
            signals.loc[
                signals.get(
                    "Signal_Qualified", pd.Series(False, index=signals.index)
                ).map(_truthy),
                "Entry_ID",
            ].dropna().astype(str)
        )
        if "Entry_ID" in signals
        else set()
    )
    accepted = _ids(entries)
    cancelled = _ids(cancellations)
    setup_ids = _ids(setup)
    practical_ids = _ids(practical)

    if qualified != accepted | cancelled or accepted & cancelled:
        violations.append(
            _audit_row(
                "V3_QUALIFIED_ACCOUNTING_MISMATCH",
                observed=f"qualified={len(qualified)}, accepted={len(accepted)}, cancelled={len(cancelled)}",
                expected="qualified == accepted union cancelled; accepted/cancelled disjoint",
            )
        )
    if setup_ids != practical_ids or not setup_ids.issubset(accepted):
        violations.append(
            _audit_row(
                "V3_COMPLETED_PAIR_MISMATCH",
                observed=f"setup={len(setup_ids)}, practical={len(practical_ids)}, accepted={len(accepted)}",
                expected="setup == practical and completed subset of accepted",
            )
        )

    pit_rows = (
        gates.loc[gates["Gate"].astype(str).eq("POINT_IN_TIME_INTEGRITY")]
        if "Gate" in gates.columns
        else pd.DataFrame()
    )
    if pit_rows.empty or not pit_rows["Passed"].map(_truthy).all():
        violations.append(
            _audit_row(
                "V3_PIT_INTEGRITY_NOT_CLEAN",
                observed="missing or failed POINT_IN_TIME_INTEGRITY gate",
                expected="POINT_IN_TIME_INTEGRITY Passed=True",
            )
        )

    return pd.DataFrame(violations, columns=AUDIT_COLUMNS).drop_duplicates(
        subset=["Entry_ID", "Symbol", "Violation"]
    ).reset_index(drop=True)


def load_market_sources(
    breadth_path: Path = BREADTH_PATH,
    index_path: Path = INDEX_PATH,
    membership_path: Path = MEMBERSHIP_PATH,
    sector_map_path: Path = SECTOR_MAP_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the frozen market inputs and a source-integrity audit."""

    audit_frames: list[pd.DataFrame] = []
    breadth, breadth_audit = load_required_csv(
        Path(breadth_path), BREADTH_COLUMNS, parse_dates=("Date",)
    )
    index_daily, index_audit = load_required_csv(
        Path(index_path), INDEX_COLUMNS, parse_dates=("Date",)
    )
    membership, membership_audit = load_required_csv(
        Path(membership_path), MEMBERSHIP_COLUMNS, parse_dates=("Member_From", "Member_To")
    )
    audit_frames.extend(
        frame for frame in (breadth_audit, index_audit, membership_audit) if not frame.empty
    )

    if not membership.empty:
        bad_method = ~membership["Method"].astype(str).eq("POINT_IN_TIME")
        if bad_method.any():
            bad_rows = membership.loc[bad_method]
            audit_frames.append(
                pd.DataFrame(
                    [
                        _audit_row(
                            "INVALID_MEMBERSHIP_METHOD",
                            symbol=row.get("Symbol", ""),
                            observed=row.get("Method", ""),
                            expected="POINT_IN_TIME",
                        )
                        for _, row in bad_rows.iterrows()
                    ],
                    columns=AUDIT_COLUMNS,
                )
            )
            membership = membership.loc[~bad_method].copy()

    sector_mapping = pd.DataFrame(columns=["Stock", "Sector_Key"])
    if Path(sector_map_path).exists():
        try:
            candidate = pd.read_csv(sector_map_path)
            if {"Stock", "Sector_Key"}.issubset(candidate.columns):
                sector_mapping = candidate.loc[:, ["Stock", "Sector_Key"]].copy()
        except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
            pass

    audit = (
        pd.concat(audit_frames, ignore_index=True)
        if audit_frames
        else _empty_audit()
    )
    return breadth, index_daily, membership, sector_mapping, audit
