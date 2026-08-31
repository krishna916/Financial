"""Load and integrity-check the immutable E1 input snapshots."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


def _naive_dates(values: object) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(values, errors="coerce"))
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    return dates


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _validate_membership_intervals(membership: pd.DataFrame) -> None:
    if membership["Symbol"].isna().any() or membership["Symbol"].eq("").any():
        raise ValueError("membership contains a blank symbol")
    if membership[["Member_From", "Member_To"]].isna().any().any():
        raise ValueError("membership contains invalid interval dates")
    if (membership["Member_From"] > membership["Member_To"]).any():
        raise ValueError("membership interval starts after its end")

    ordered = membership.sort_values(["Symbol", "Member_From", "Member_To"])
    for symbol, group in ordered.groupby("Symbol", sort=False):
        previous_end = group["Member_To"].shift()
        if (group["Member_From"] <= previous_end).fillna(False).any():
            raise ValueError(f"membership intervals overlap for {symbol}")


def load_membership(path: Path) -> pd.DataFrame:
    """Load the inclusive, point-in-time Nifty 500 membership manifest."""

    membership = pd.read_csv(path)
    required = {"Symbol", "Member_From", "Member_To", "Yahoo_Ticker", "Downloadable"}
    missing = required.difference(membership.columns)
    if missing:
        raise ValueError(f"membership missing columns: {sorted(missing)}")

    membership = membership.copy()
    membership["Symbol"] = membership["Symbol"].astype("string").str.strip()
    membership["Yahoo_Ticker"] = membership["Yahoo_Ticker"].fillna("").astype(str).str.strip()
    membership["Member_From"] = _naive_dates(membership["Member_From"])
    membership["Member_To"] = _naive_dates(membership["Member_To"])
    membership["Downloadable"] = membership["Downloadable"].map(_parse_bool)
    _validate_membership_intervals(membership)
    return membership.sort_values(["Member_From", "Symbol", "Member_To"]).reset_index(drop=True)


def active_members_on(membership: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    """Return membership rows active on a date, including both boundaries."""

    required = {"Symbol", "Member_From", "Member_To"}
    missing = required.difference(membership.columns)
    if missing:
        raise ValueError(f"membership missing columns: {sorted(missing)}")
    day = _naive_dates([date])[0]
    if pd.isna(day):
        raise ValueError("date is invalid")
    frame = membership.copy()
    frame["Member_From"] = _naive_dates(frame["Member_From"])
    frame["Member_To"] = _naive_dates(frame["Member_To"])
    return frame.loc[
        frame["Member_From"].le(day) & frame["Member_To"].ge(day)
    ].sort_values("Symbol").reset_index(drop=True)


def sha256_file(path: Path) -> str:
    """Return the SHA256 digest of a file without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(manifest: pd.DataFrame, root: Path) -> pd.DataFrame:
    """Audit manifest hashes and CSV row counts without changing the manifest."""

    required = {"Artifact", "SHA256", "Row_Count"}
    missing = required.difference(manifest.columns)
    if missing:
        raise ValueError(f"manifest missing columns: {sorted(missing)}")

    audit: list[dict[str, object]] = []
    for row in manifest.itertuples(index=False):
        artifact = str(row.Artifact)
        path = root / artifact
        expected_hash = str(row.SHA256).strip().lower()
        expected_rows = row.Row_Count
        if not path.is_file():
            audit.append(
                {
                    "Artifact": artifact,
                    "Violation": "MISSING_FILE",
                    "Expected": "readable file",
                    "Actual": "missing",
                }
            )
            continue
        try:
            actual_hash = sha256_file(path)
        except OSError as exc:
            audit.append(
                {
                    "Artifact": artifact,
                    "Violation": "UNREADABLE_FILE",
                    "Expected": "readable file",
                    "Actual": str(exc),
                }
            )
            continue

        if actual_hash != expected_hash:
            audit.append(
                {
                    "Artifact": artifact,
                    "Violation": "HASH_MISMATCH",
                    "Expected": expected_hash,
                    "Actual": actual_hash,
                }
            )

        if path.suffix.lower() == ".csv" and pd.notna(expected_rows):
            try:
                actual_rows = len(pd.read_csv(path))
            except Exception as exc:  # noqa: BLE001 - report unreadable CSVs in the audit
                audit.append(
                    {
                        "Artifact": artifact,
                        "Violation": "UNREADABLE_FILE",
                        "Expected": "readable CSV",
                        "Actual": str(exc),
                    }
                )
            else:
                try:
                    expected_count = int(expected_rows)
                except (TypeError, ValueError):
                    expected_count = None
                if expected_count is not None and actual_rows != expected_count:
                    audit.append(
                        {
                            "Artifact": artifact,
                            "Violation": "CSV_ROW_COUNT_MISMATCH",
                            "Expected": expected_count,
                            "Actual": actual_rows,
                        }
                    )

    return pd.DataFrame(audit, columns=["Artifact", "Violation", "Expected", "Actual"])
