"""Audited Stage A market-price provider identity resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


ALIAS_COLUMNS = [
    "Research_Symbol",
    "Provider",
    "Provider_Ticker",
    "Security_ISIN",
    "Identity_Effective_Date",
    "Identity_Source_URL",
    "Reason",
]
INTERVAL_VIOLATION_COLUMNS = [
    "Provider",
    "Provider_Ticker",
    "Research_Symbol_A",
    "Research_Symbol_B",
    "Violation",
    "Detail",
]


@dataclass(frozen=True)
class PriceIdentity:
    research_symbol: str
    membership_ticker: str
    provider: str
    provider_ticker: str
    alias_applied: bool
    security_isin: str
    identity_effective_date: pd.Timestamp | None
    identity_source_url: str
    reason: str


def _invalid_row(detail: str) -> ValueError:
    return ValueError(f"PRICE_ALIAS_INVALID_ROW: {detail}")


def _clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _validate_alias_frame(aliases: pd.DataFrame) -> pd.DataFrame:
    missing = set(ALIAS_COLUMNS).difference(aliases.columns)
    if missing:
        raise _invalid_row(f"missing columns: {sorted(missing)}")

    frame = aliases.loc[:, ALIAS_COLUMNS].copy()
    for column in ("Research_Symbol", "Provider", "Provider_Ticker", "Security_ISIN", "Identity_Source_URL", "Reason"):
        frame[column] = frame[column].map(_clean_text)
    frame["Research_Symbol"] = frame["Research_Symbol"].str.upper()
    frame["Provider"] = frame["Provider"].str.upper()
    frame["Identity_Effective_Date"] = pd.to_datetime(
        frame["Identity_Effective_Date"], errors="coerce"
    )

    for index, row in frame.iterrows():
        if not row["Research_Symbol"]:
            raise _invalid_row(f"row {index + 2}: blank Research_Symbol")
        if not row["Provider_Ticker"]:
            raise _invalid_row(f"row {index + 2}: blank Provider_Ticker")
        if row["Provider"] != "YAHOO":
            raise _invalid_row(f"row {index + 2}: Provider must be YAHOO")
        if not row["Security_ISIN"]:
            raise _invalid_row(f"row {index + 2}: blank Security_ISIN")
        if pd.isna(row["Identity_Effective_Date"]):
            raise _invalid_row(f"row {index + 2}: invalid Identity_Effective_Date")
        source_url = urlparse(row["Identity_Source_URL"])
        if source_url.scheme != "https" or not source_url.netloc:
            raise _invalid_row(f"row {index + 2}: Identity_Source_URL must be HTTPS")

    if frame["Research_Symbol"].duplicated().any():
        duplicate = frame.loc[frame["Research_Symbol"].duplicated(), "Research_Symbol"].iloc[0]
        raise ValueError(f"PRICE_ALIAS_DUPLICATE_SYMBOL: {duplicate}")
    return frame


def load_price_aliases(path: Path) -> pd.DataFrame:
    """Load and validate the explicit, provenance-backed provider alias registry."""

    try:
        aliases = pd.read_csv(path, dtype="string")
    except Exception as exc:  # noqa: BLE001 - expose a stable registry error
        raise _invalid_row(f"cannot read registry: {exc}") from exc
    return _validate_alias_frame(aliases)


def resolve_price_identity(
    research_symbol: str, membership_ticker: str, aliases: pd.DataFrame
) -> PriceIdentity:
    """Resolve one research identity without guessing or mutating its ticker."""

    symbol = _clean_text(research_symbol).upper()
    membership = _clean_text(membership_ticker)
    if not symbol or not membership:
        raise _invalid_row("blank research symbol or membership ticker")
    frame = _validate_alias_frame(aliases)
    matches = frame.loc[frame["Research_Symbol"].eq(symbol)]
    if matches.empty:
        return PriceIdentity(symbol, membership, "YAHOO", membership, False, "", None, "", "")
    row = matches.iloc[0]
    return PriceIdentity(
        research_symbol=symbol,
        membership_ticker=membership,
        provider=str(row["Provider"]),
        provider_ticker=str(row["Provider_Ticker"]),
        alias_applied=True,
        security_isin=str(row["Security_ISIN"]),
        identity_effective_date=pd.Timestamp(row["Identity_Effective_Date"]),
        identity_source_url=str(row["Identity_Source_URL"]),
        reason=str(row["Reason"]),
    )


def validate_shared_provider_intervals(identities: pd.DataFrame) -> pd.DataFrame:
    """Reject inclusive PIT interval overlap for distinct symbols sharing a provider ticker."""

    required = {"Provider", "Provider_Ticker", "Research_Symbol", "Member_From", "Member_To"}
    missing = required.difference(identities.columns)
    if missing:
        raise ValueError(f"price identity table missing columns: {sorted(missing)}")
    frame = identities.copy()
    frame["Member_From"] = pd.to_datetime(frame["Member_From"], errors="coerce")
    frame["Member_To"] = pd.to_datetime(frame["Member_To"], errors="coerce")
    if frame[["Member_From", "Member_To"]].isna().any().any():
        raise ValueError("price identity table contains invalid membership interval dates")
    if (frame["Member_From"] > frame["Member_To"]).any():
        raise ValueError("price identity table contains reversed membership interval")

    violations: list[dict[str, str]] = []
    for (provider, ticker), group in frame.groupby(["Provider", "Provider_Ticker"], sort=True):
        rows = list(group.sort_values(["Research_Symbol", "Member_From", "Member_To"]).itertuples())
        for index, left in enumerate(rows):
            for right in rows[index + 1 :]:
                symbol_a = str(left.Research_Symbol)
                symbol_b = str(right.Research_Symbol)
                if symbol_a == symbol_b:
                    continue
                if left.Member_From <= right.Member_To and right.Member_From <= left.Member_To:
                    first, second = sorted((symbol_a, symbol_b))
                    violations.append(
                        {
                            "Provider": str(provider),
                            "Provider_Ticker": str(ticker),
                            "Research_Symbol_A": first,
                            "Research_Symbol_B": second,
                            "Violation": "PROVIDER_ALIAS_MEMBERSHIP_OVERLAP",
                            "Detail": (
                                f"{symbol_a} [{left.Member_From.date()}..{left.Member_To.date()}] overlaps "
                                f"{symbol_b} [{right.Member_From.date()}..{right.Member_To.date()}]"
                            ),
                        }
                    )
    return pd.DataFrame(violations, columns=INTERVAL_VIOLATION_COLUMNS)
