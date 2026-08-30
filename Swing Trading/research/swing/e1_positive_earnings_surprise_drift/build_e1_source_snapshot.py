"""Build the immutable, source-only E1 Stage A input package."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from constants import (
    EPS_HISTORY_START,
    NIFTY500_YAHOO_TICKER,
    PRICE_END_EXCLUSIVE,
    PRICE_START,
    PRIMARY_END,
    PRIMARY_START,
    SOURCE_CUTOFF,
)
from load_e1_inputs import active_members_on, load_membership, sha256_file
from source_clients import (
    BSE_CORPORATE_ACTIONS_URL,
    BSE_RESULTS_URL,
    BseIdentifierError,
    NSE_LEGACY_URL,
    BseResultsClient,
    NseResultsClient,
    _records,
    normalize_bse_record,
    normalize_nse_record,
)
from xbrl_eps import extract_basic_eps_continuing
from price_identity import load_price_aliases, resolve_price_identity, validate_shared_provider_intervals


PRICE_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
PRICE_IDENTITY_COLUMNS = [
    "Research_Symbol",
    "Membership_Yahoo_Ticker",
    "Provider",
    "Provider_Ticker",
    "Alias_Applied",
    "Security_ISIN",
    "Identity_Effective_Date",
    "Identity_Source_URL",
    "Reason",
    "Member_From",
    "Member_To",
]
PRICE_SNAPSHOT_COLUMNS = [
    "Symbol",
    "Yahoo_Ticker",
    "Membership_Yahoo_Ticker",
    "Provider",
    "Provider_Ticker",
    "Alias_Applied",
    "Security_ISIN",
    "Identity_Effective_Date",
    "Identity_Source_URL",
    "Reason",
    *PRICE_COLUMNS,
]
PRICE_IDENTITY_AUDIT_COLUMNS = [
    "Research_Symbol",
    "Membership_Yahoo_Ticker",
    "Provider",
    "Provider_Ticker",
    "Alias_Applied",
    "Security_ISIN",
    "Identity_Effective_Date",
    "Identity_Source_URL",
    "Reason",
    "Member_From",
    "Member_To",
    "Provider_Data_Min",
    "Provider_Data_Max",
    "Provider_Row_Count",
    "Active_Interval_Row_Count",
    "Coverage_Status",
    "Violation",
]
ALIAS_REGISTRY_PATH = Path(__file__).resolve().with_name("price_provider_aliases.csv")
SOURCE_COLUMNS = [
    "Symbol",
    "Exchange",
    "Feed",
    "Fiscal_Period_End",
    "Fiscal_Quarter",
    "Reporting_Basis",
    "Quarterly_or_Annual",
    "Original_or_Revised",
    "Public_Timestamp",
    "Source_URL",
    "Source_Record_ID",
    "Machine_Readable_URL",
    "BSE_Scrip_Code",
    "BSE_Scrip_ID",
    "BSE_Mapping_Source_URL",
]
EPS_COLUMNS = SOURCE_COLUMNS + ["EPS", "EPS_Source_Resolved"]
ACTION_COLUMNS = [
    "Symbol",
    "Action_Type",
    "Old_Shares",
    "New_Shares",
    "Bonus_Shares",
    "Share_Count_Factor",
    "Ratio_Numerator",
    "Ratio_Denominator",
    "Normalization_Status",
    "Action_Text",
    "Ex_Date",
    "Record_Date",
    "Source_URL",
    "Source_Record_ID",
]

CHECKPOINT_SCHEMA_VERSION = 2
SOURCE_NORMALIZER_VERSION = 2
EPS_PARSER_VERSION = 2
TRANSIENT_CHECKPOINT_VIOLATIONS = {
    "NSE_SOURCE_ERROR",
    "BSE_SOURCE_ERROR",
    "BSE_SOURCE_NON_JSON",
    "EPS_PAYLOAD_HTTP_ERROR",
    "CORPORATE_ACTION_SOURCE_ERROR",
}


@dataclass(frozen=True)
class SourcePayload:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    payload_kind: str
    body_bytes: bytes


_OFFICIAL_SOURCE_HOSTS = {
    "www.nseindia.com",
    "nsearchives.nseindia.com",
    "www.bseindia.com",
    "api.bseindia.com",
}
_PAYLOAD_ERROR_CODES = {
    "EPS_PAYLOAD_HTTP_ERROR",
    "EPS_PAYLOAD_UNSUPPORTED_FORMAT",
    "EPS_FACT_NOT_FOUND",
    "EPS_FACT_AMBIGUOUS",
}


def _payload_error(code: str, detail: str) -> ValueError:
    return ValueError(f"{code}: {detail}")


def _payload_error_code(exc: Exception) -> str:
    message = str(exc)
    code = message.split(":", 1)[0].strip()
    return code if code in _PAYLOAD_ERROR_CODES else "EPS_PAYLOAD_HTTP_ERROR"


def _normalize_payload_url(record: dict[str, object]) -> str:
    requested = str(record.get("Machine_Readable_URL") or "").strip()
    if not requested:
        raise _payload_error("EPS_PAYLOAD_UNSUPPORTED_FORMAT", "missing machine-readable URL")
    parsed = urlparse(requested)
    if parsed.scheme:
        if parsed.scheme != "https" or parsed.hostname not in _OFFICIAL_SOURCE_HOSTS:
            raise _payload_error("EPS_PAYLOAD_UNSUPPORTED_FORMAT", requested)
        return requested
    source = str(record.get("Source_URL") or "").strip()
    origin = urlparse(source)
    if origin.scheme != "https" or origin.hostname not in _OFFICIAL_SOURCE_HOSTS:
        raise _payload_error("EPS_PAYLOAD_UNSUPPORTED_FORMAT", requested)
    resolved = urljoin(source, requested)
    resolved_parts = urlparse(resolved)
    if resolved_parts.scheme != "https" or resolved_parts.hostname not in _OFFICIAL_SOURCE_HOSTS:
        raise _payload_error("EPS_PAYLOAD_UNSUPPORTED_FORMAT", requested)
    return resolved


def _classify_payload(body: bytes, content_type: str) -> str:
    media_type = content_type.split(";", 1)[0].strip().lower()
    prefix = body.lstrip()[:256].lower()
    if (
        "xml" in media_type
        or prefix.startswith(b"<?xml")
        or prefix.startswith(b"<xbrl")
        or prefix.startswith(b"<xbrli:xbrl")
    ):
        return "xml"
    is_html = "html" in media_type or b"<html" in prefix or b"<!doctype" in prefix
    if is_html and re.search(rb"<\s*ix:(?:nonfraction|nonnumeric)\b", body, re.IGNORECASE):
        return "ixbrl_html"
    return "unsupported"


def fetch_machine_payload(
    record: dict[str, object],
    session: requests.Session,
    timeout: float = 30.0,
) -> SourcePayload:
    requested_url = str(record.get("Machine_Readable_URL") or "").strip()
    url = _normalize_payload_url(record)
    try:
        response = session.get(url, timeout=timeout)
    except requests.RequestException as exc:
        raise _payload_error("EPS_PAYLOAD_HTTP_ERROR", str(exc)) from exc
    status_code = int(getattr(response, "status_code", 0))
    if status_code != 200:
        raise _payload_error("EPS_PAYLOAD_HTTP_ERROR", f"HTTP {status_code}: {url}")
    headers = getattr(response, "headers", {}) or {}
    content_type = str(headers.get("Content-Type", headers.get("content-type", "")))
    body = bytes(getattr(response, "content", b""))
    final_url = str(getattr(response, "url", "") or url)
    return SourcePayload(
        requested_url=requested_url,
        final_url=final_url,
        status_code=status_code,
        content_type=content_type,
        payload_kind=_classify_payload(body, content_type),
        body_bytes=body,
    )


def _number(value: object) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip().replace(",", "")
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"
    try:
        number = float(text)
    except ValueError:
        return None
    return number if np.isfinite(number) else None


def _naive_date(value: object) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return pd.NaT
    stamp = pd.Timestamp(parsed)
    return stamp.tz_localize(None) if stamp.tz is not None else stamp.normalize()


def _fetch_eps(
    record: dict[str, object],
    session: requests.Session,
    timeout: float = 30.0,
) -> float | None:
    direct = _number(record.get("EPS"))
    if direct is not None:
        return direct
    basis = str(record.get("Reporting_Basis") or "").strip()
    period_end = record.get("Fiscal_Period_End")
    if not basis or pd.isna(period_end):
        raise _payload_error("EPS_FACT_NOT_FOUND", "missing reporting basis or period end")
    payload = fetch_machine_payload(record, session, timeout=timeout)
    if payload.payload_kind == "unsupported":
        raise _payload_error("EPS_PAYLOAD_UNSUPPORTED_FORMAT", payload.final_url)
    value = extract_basic_eps_continuing(payload.body_bytes, pd.Timestamp(period_end), basis)
    if value is None:
        raise _payload_error("EPS_FACT_NOT_FOUND", payload.final_url)
    return value


def _checkpoint_stem(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9_.-]", "_", str(symbol).strip().upper())


def _checkpoint_paths(checkpoint_dir: Path, symbol: str) -> dict[str, Path]:
    stem = _checkpoint_stem(symbol)
    return {
        "filings": checkpoint_dir / f"{stem}.filings.csv",
        "eps": checkpoint_dir / f"{stem}.eps.csv",
        "audit": checkpoint_dir / f"{stem}.audit.csv",
        "metadata": checkpoint_dir / f"{stem}.checkpoint.json",
    }


def _read_symbol_checkpoint(
    checkpoint_dir: Path | None,
    symbol: str,
    cutoff: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None:
    if checkpoint_dir is None:
        return None
    paths = _checkpoint_paths(checkpoint_dir, symbol)
    try:
        metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
        if (
            metadata.get("Checkpoint_Schema_Version") != CHECKPOINT_SCHEMA_VERSION
            or metadata.get("Source_Normalizer_Version") != SOURCE_NORMALIZER_VERSION
            or metadata.get("EPS_Parser_Version") != EPS_PARSER_VERSION
            or metadata.get("Symbol") != str(symbol).strip().upper()
            or metadata.get("Source_Cutoff") != str(cutoff.date())
            or metadata.get("Acquisition_Complete") is not True
            or metadata.get("Reusable") is not True
        ):
            return None
        frames = {
            "filings": pd.read_csv(paths["filings"]),
            "eps": pd.read_csv(paths["eps"]),
            "audit": pd.read_csv(paths["audit"]),
        }
        required = {
            "filings": set(SOURCE_COLUMNS),
            "eps": set(EPS_COLUMNS),
            "audit": {"Symbol", "Source_Record_ID", "Violation", "Detail"},
        }
        for name, frame in frames.items():
            artifact = metadata.get("Artifacts", {}).get(name, {})
            if not required[name].issubset(frame.columns):
                return None
            if len(frame) != int(artifact.get("Row_Count", -1)):
                return None
            if sha256_file(paths[name]) != artifact.get("SHA256"):
                return None
        if frames["audit"]["Violation"].isin(TRANSIENT_CHECKPOINT_VIOLATIONS).any():
            return None
        return frames["filings"], frames["eps"], frames["audit"]
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None


def _write_symbol_checkpoint(
    checkpoint_dir: Path,
    symbol: str,
    cutoff: pd.Timestamp,
    filings: pd.DataFrame,
    eps: pd.DataFrame,
    audit: pd.DataFrame,
) -> None:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    paths = _checkpoint_paths(checkpoint_dir, symbol)
    frames = {
        "filings": filings.reindex(columns=SOURCE_COLUMNS),
        "eps": eps.reindex(columns=EPS_COLUMNS),
        "audit": audit.reindex(columns=["Symbol", "Source_Record_ID", "Violation", "Detail"]),
    }
    for name, frame in frames.items():
        frame.to_csv(paths[name], index=False)
    reusable = not frames["audit"]["Violation"].isin(TRANSIENT_CHECKPOINT_VIOLATIONS).any()
    metadata = {
        "Checkpoint_Schema_Version": CHECKPOINT_SCHEMA_VERSION,
        "Source_Normalizer_Version": SOURCE_NORMALIZER_VERSION,
        "EPS_Parser_Version": EPS_PARSER_VERSION,
        "Symbol": str(symbol).strip().upper(),
        "Source_Cutoff": str(cutoff.date()),
        "Acquisition_Complete": True,
        "Reusable": bool(reusable),
        "Artifacts": {
            name: {"Row_Count": len(frame), "SHA256": sha256_file(paths[name])}
            for name, frame in frames.items()
        },
        "Scope": "official filing, EPS, and source-audit provenance only",
    }
    paths["metadata"].write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def _canonicalize_source_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "Fiscal_Period_End" in result:
        result["Fiscal_Period_End"] = pd.to_datetime(result["Fiscal_Period_End"], errors="coerce")
    if "Public_Timestamp" in result:
        result["Public_Timestamp"] = pd.to_datetime(
            result["Public_Timestamp"], errors="coerce", utc=True
        )
    for column in result.columns:
        if column not in {"Fiscal_Period_End", "Public_Timestamp", "EPS"}:
            result[column] = result[column].astype("string")
    return result


def _build_filing_snapshot_for_symbol(
    symbol: str,
    cutoff: pd.Timestamp,
    nse: NseResultsClient,
    bse: BseResultsClient,
    fetch_session: requests.Session,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    records: list[tuple[dict[str, object], str]] = []
    audit_rows: list[dict[str, object]] = []
    try:
        records.extend((record, "legacy") for record in nse.list_legacy(symbol))
        records.extend((record, "integrated") for record in nse.list_integrated(symbol))
    except Exception as exc:  # noqa: BLE001 - preserve per-symbol source errors
        audit_rows.append({"Symbol": symbol, "Violation": "NSE_SOURCE_ERROR", "Detail": str(exc)})
    try:
        records.extend((record, "bse") for record in bse.list_results(symbol))
    except BseIdentifierError as exc:
        audit_rows.append({"Symbol": symbol, "Violation": exc.code, "Detail": str(exc)})
    except Exception as exc:  # noqa: BLE001 - preserve per-symbol source errors
        audit_rows.append({"Symbol": symbol, "Violation": "BSE_SOURCE_ERROR", "Detail": str(exc)})

    filing_rows: list[dict[str, object]] = []
    eps_rows: list[dict[str, object]] = []
    for raw, feed in records:
        normalized = normalize_bse_record(raw) if feed == "bse" else normalize_nse_record(raw, feed)
        public_timestamp = normalized.get("Public_Timestamp")
        public_date = (
            pd.Timestamp(public_timestamp).tz_convert("Asia/Kolkata").tz_localize(None).normalize()
            if pd.notna(public_timestamp) and getattr(public_timestamp, "tz", None) is not None
            else _naive_date(public_timestamp)
        )
        if pd.notna(public_date) and public_date > cutoff:
            continue
        filing_rows.append({column: normalized.get(column) for column in SOURCE_COLUMNS})
        try:
            eps = _fetch_eps(normalized, fetch_session)
        except Exception as exc:  # noqa: BLE001 - keep failed parsing explicit in audit
            eps = None
            audit_rows.append(
                {
                    "Symbol": normalized.get("Symbol", symbol),
                    "Source_Record_ID": normalized.get("Source_Record_ID", ""),
                    "Violation": _payload_error_code(exc),
                    "Detail": f"{type(exc).__name__}: {exc}",
                }
            )
        if eps is not None:
            eps_rows.append(
                {
                    **{column: normalized.get(column) for column in SOURCE_COLUMNS},
                    "EPS": eps,
                    "EPS_Source_Resolved": True,
                }
            )
    return (
        pd.DataFrame(filing_rows, columns=SOURCE_COLUMNS),
        pd.DataFrame(eps_rows, columns=EPS_COLUMNS),
        pd.DataFrame(audit_rows, columns=["Symbol", "Source_Record_ID", "Violation", "Detail"]),
    )


def build_filing_snapshot(
    symbols: list[str],
    cutoff: pd.Timestamp,
    checkpoint_dir: Path | str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Acquire normalized official filings, optionally using validated checkpoints."""

    nse = NseResultsClient()
    bse = BseResultsClient()
    fetch_session = requests.Session()
    fetch_session.headers.update({"User-Agent": "Mozilla/5.0 E1-source-snapshot"})
    checkpoint_root = Path(checkpoint_dir) if checkpoint_dir is not None else None
    cutoff = pd.Timestamp(cutoff).normalize()
    filing_frames: list[pd.DataFrame] = []
    eps_frames: list[pd.DataFrame] = []
    audit_frames: list[pd.DataFrame] = []
    for symbol in sorted({str(item).strip().upper() for item in symbols if str(item).strip()}):
        checkpoint = _read_symbol_checkpoint(checkpoint_root, symbol, cutoff)
        if checkpoint is None:
            checkpoint = _build_filing_snapshot_for_symbol(symbol, cutoff, nse, bse, fetch_session)
            if checkpoint_root is not None:
                _write_symbol_checkpoint(checkpoint_root, symbol, cutoff, *checkpoint)
        filing_frame, eps_frame, audit_frame = checkpoint
        filing_frames.append(_canonicalize_source_frame(filing_frame))
        eps_frames.append(_canonicalize_source_frame(eps_frame))
        audit_frames.append(audit_frame)
    filings = pd.concat(filing_frames, ignore_index=True) if filing_frames else pd.DataFrame(columns=SOURCE_COLUMNS)
    eps = pd.concat(eps_frames, ignore_index=True) if eps_frames else pd.DataFrame(columns=EPS_COLUMNS)
    audit = (
        pd.concat(audit_frames, ignore_index=True)
        if audit_frames
        else pd.DataFrame(columns=["Symbol", "Source_Record_ID", "Violation", "Detail"])
    )
    return filings, eps, audit


def _action_ratio(value: object) -> tuple[float, float] | None:
    text = str(value or "").lower().replace("to", ":")
    match = re.search(r"(\d+(?:\.\d+)?)\s*[:/]\s*(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    numerator, denominator = float(match.group(1)), float(match.group(2))
    if denominator <= 0 or numerator <= 0:
        return None
    return numerator, denominator


def _record_number(record: dict[str, object], *names: str) -> float | None:
    for name in names:
        if name in record:
            value = _number(record.get(name))
            if value is not None:
                return value
    return None


def _normalize_action(record: dict[str, object], symbol: str) -> dict[str, object] | None:
    action_text = " ".join(
        str(record.get(name)).strip()
        for name in (
            "purpose",
            "Purpose",
            "action",
            "Action_Type",
            "subject",
            "XTYPE",
            "VALUE",
        )
        if record.get(name) is not None and str(record.get(name)).strip()
    )
    lower = action_text.lower()
    if "split" in lower:
        action_type = "SPLIT"
    elif "bonus" in lower:
        action_type = "BONUS"
    elif "consolid" in lower:
        action_type = "CONSOLIDATION"
    else:
        return None
    ratio = _action_ratio(action_text)
    ratio_numerator, ratio_denominator = ratio or (None, None)
    old_shares = _record_number(record, "oldShares", "old_shares", "fromShares", "from_shares")
    new_shares = _record_number(record, "newShares", "new_shares", "toShares", "to_shares")
    bonus_shares = _record_number(record, "bonusShares", "bonus_shares")
    if old_shares is None or (action_type == "BONUS" and bonus_shares is None):
        if ratio is not None:
            first, second = ratio
            if action_type == "BONUS":
                bonus_shares = first
                old_shares = second
                new_shares = old_shares + bonus_shares
            else:
                new_shares = first
                old_shares = second
    elif action_type == "BONUS" and new_shares is None:
        new_shares = old_shares + bonus_shares

    factor = None
    normalization_status = "NORMALIZED"
    if old_shares is None or new_shares is None or old_shares <= 0 or new_shares <= 0:
        factor = None
        normalization_status = "UNPARSEABLE"
    elif action_type == "BONUS":
        if bonus_shares is None or bonus_shares <= 0 or abs(new_shares - (old_shares + bonus_shares)) > 1e-12:
            factor = None
            normalization_status = "UNPARSEABLE"
        else:
            factor = new_shares / old_shares
    else:
        factor = new_shares / old_shares
    return {
        "Symbol": symbol,
        "Action_Type": action_type,
        "Old_Shares": old_shares,
        "New_Shares": new_shares,
        "Bonus_Shares": bonus_shares,
        "Share_Count_Factor": factor,
        "Ratio_Numerator": ratio_numerator,
        "Ratio_Denominator": ratio_denominator,
        "Normalization_Status": normalization_status,
        "Action_Text": action_text,
        "Ex_Date": _naive_date(
            record.get("exDate")
            or record.get("ex_date")
            or record.get("Ex_date")
            or record.get("BCRD_FROM")
            or record.get("BCRD_from")
        ),
        "Record_Date": _naive_date(
            record.get("recordDate")
            or record.get("record_date")
            or record.get("recDate")
            or record.get("BCRD_FROM")
            or record.get("BCRD_from")
        ),
        "Source_URL": str(record.get("sourceUrl") or record.get("url") or ""),
        "Source_Record_ID": str(record.get("id") or record.get("recordId") or ""),
    }


def _action_records(payload: object) -> list[dict[str, object]]:
    """Return all exchange action tables, preserving each source row."""

    if isinstance(payload, dict):
        tables: list[dict[str, object]] = []
        for key in ("Table", "Table1", "Table2"):
            value = payload.get(key)
            if isinstance(value, list):
                tables.extend(item for item in value if isinstance(item, dict))
        if tables:
            return tables
    return _records(payload)


def build_corporate_action_snapshot(
    symbols: list[str], cutoff: pd.Timestamp
) -> pd.DataFrame:
    """Collect official split/bonus/consolidation actions when exposed by exchanges."""

    rows: list[dict[str, object]] = []
    audit: list[dict[str, object]] = []
    nse = NseResultsClient()
    bse = BseResultsClient()
    cutoff = pd.Timestamp(cutoff).normalize()
    for symbol in sorted({str(item).strip().upper() for item in symbols if str(item).strip()}):
        try:
            bse_identity = bse.resolve_identifier(symbol)
        except BseIdentifierError as exc:
            bse_identity = None
            audit.append({"Symbol": symbol, "Violation": exc.code, "Detail": str(exc)})
        except Exception as exc:  # noqa: BLE001 - preserve malformed official responses in the audit
            bse_identity = None
            audit.append({"Symbol": symbol, "Violation": "BSE_SOURCE_ERROR", "Detail": str(exc)})
        seen_actions: set[tuple[object, ...]] = set()
        endpoints = [
            (
                nse,
                "https://www.nseindia.com/api/corporates-corporateActions",
                {"index": "equities", "symbol": symbol},
            ),
        ]
        if bse_identity is not None:
            endpoints.append(
                (
                    bse,
                    BSE_CORPORATE_ACTIONS_URL,
                    {"scripcode": bse_identity["BSE_Scrip_Code"], "pageno": 1, "pagesize": 100},
                )
            )
        for client, url, params in endpoints:
            try:
                if client is bse:
                    payload = bse.corporate_actions(symbol)
                else:
                    payload = client._get_json(url, params)
            except Exception as exc:  # noqa: BLE001 - keep acquisition failure visible
                audit.append({"Symbol": symbol, "Violation": "CORPORATE_ACTION_SOURCE_ERROR", "Detail": str(exc)})
                continue
            for record in _action_records(payload):
                action = _normalize_action(record, symbol)
                if action is None:
                    text = " ".join(
                        str(record.get(name)).strip()
                        for name in (
                            "purpose",
                            "Purpose",
                            "action",
                            "Action_Type",
                            "subject",
                            "XTYPE",
                            "VALUE",
                        )
                        if record.get(name) is not None and str(record.get(name)).strip()
                    )
                    if any(word in text.lower() for word in ("split", "bonus", "consolid")):
                        audit.append(
                            {
                                "Symbol": symbol,
                                "Violation": "UNPARSEABLE_CORPORATE_ACTION_RATIO",
                                "Detail": text,
                            }
                        )
                    continue
                if action.get("Normalization_Status") != "NORMALIZED":
                    audit.append(
                        {
                            "Symbol": symbol,
                            "Violation": "UNPARSEABLE_CORPORATE_ACTION_RATIO",
                            "Detail": action.get("Action_Text", ""),
                        }
                    )
                effective = action["Ex_Date"]
                if pd.notna(effective) and effective <= cutoff:
                    identity = (
                        action["Action_Type"],
                        action["Ex_Date"],
                        action["Share_Count_Factor"],
                    )
                    if identity in seen_actions:
                        continue
                    seen_actions.add(identity)
                    action["Source_URL"] = action["Source_URL"] or url
                    rows.append(action)
    result = pd.DataFrame(rows, columns=ACTION_COLUMNS)
    result.attrs["audit"] = pd.DataFrame(audit)
    return result


def _resolve_yahoo_field(frame: pd.DataFrame, field: str) -> object:
    if not isinstance(frame.columns, pd.MultiIndex):
        if field in frame.columns:
            return field
        raise ValueError(f"Yahoo response missing {field!r} column")
    matches = [column for column in frame.columns if field in {str(level) for level in column}]
    if len(matches) != 1:
        raise ValueError(f"Yahoo response did not provide a unique {field!r} column")
    return matches[0]


def download_adjusted_prices(ticker: str, start: str, end_exclusive: str) -> pd.DataFrame:
    """Download one adjusted Yahoo daily OHLCV frame with no date fabrication."""

    raw = yf.download(
        tickers=ticker,
        start=start,
        end=end_exclusive,
        interval="1d",
        auto_adjust=True,
        actions=False,
        progress=False,
        threads=False,
        timeout=30,
    )
    if raw is None or raw.empty:
        raise ValueError(f"Yahoo returned no daily rows for {ticker}")
    frame = raw.reset_index() if "Date" not in raw.columns else raw.copy()
    dates = pd.DatetimeIndex(pd.to_datetime(frame["Date"], errors="coerce"))
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    if dates.isna().any() or dates.duplicated().any():
        raise ValueError(f"Yahoo response contains invalid or duplicate dates for {ticker}")
    start_date = pd.Timestamp(start)
    end_date = pd.Timestamp(end_exclusive)
    if (dates < start_date).any() or (dates >= end_date).any():
        raise ValueError(f"Yahoo response contains dates outside requested range for {ticker}")
    normalized = pd.DataFrame({"Date": dates.to_numpy()})
    for field in PRICE_COLUMNS[1:]:
        column = _resolve_yahoo_field(frame, field)
        normalized[field] = pd.to_numeric(frame[column], errors="coerce").to_numpy()
    return normalized.sort_values("Date").reset_index(drop=True)


def _symbols_active_in_window(membership: pd.DataFrame) -> pd.DataFrame:
    normalized = membership.copy()
    normalized["Member_From"] = pd.to_datetime(normalized["Member_From"], errors="coerce")
    normalized["Member_To"] = pd.to_datetime(normalized["Member_To"], errors="coerce")
    normalized["Downloadable"] = normalized["Downloadable"].map(
        lambda value: value
        if isinstance(value, bool)
        else str(value).strip().lower() in {"true", "1", "yes", "y"}
    )
    overlap = normalized.loc[
        normalized["Member_From"].le(PRIMARY_END) & normalized["Member_To"].ge(PRIMARY_START)
    ]
    return (
        overlap.loc[
            overlap["Downloadable"] & overlap["Yahoo_Ticker"].ne(""),
            ["Symbol", "Yahoo_Ticker", "Member_From", "Member_To", "Downloadable"],
        ]
        .sort_values(["Symbol", "Member_From", "Member_To"])
        .reset_index(drop=True)
    )


def build_price_identity_table(
    membership: pd.DataFrame, aliases: pd.DataFrame
) -> pd.DataFrame:
    """Resolve every active PIT membership row to an explicit provider identity."""

    required = {"Symbol", "Yahoo_Ticker", "Member_From", "Member_To", "Downloadable"}
    missing = required.difference(membership.columns)
    if missing:
        raise ValueError(f"membership missing columns: {sorted(missing)}")
    active = _symbols_active_in_window(membership).copy()
    if active.empty:
        return pd.DataFrame(columns=PRICE_IDENTITY_COLUMNS)

    cache: dict[tuple[str, str], object] = {}
    rows: list[dict[str, object]] = []
    for item in active.itertuples(index=False):
        symbol = str(item.Symbol).strip().upper()
        membership_ticker = str(item.Yahoo_Ticker).strip()
        key = (symbol, membership_ticker)
        identity = cache.get(key)
        if identity is None:
            identity = resolve_price_identity(symbol, membership_ticker, aliases)
            cache[key] = identity
        rows.append(
            {
                "Research_Symbol": identity.research_symbol,
                "Membership_Yahoo_Ticker": identity.membership_ticker,
                "Provider": identity.provider,
                "Provider_Ticker": identity.provider_ticker,
                "Alias_Applied": identity.alias_applied,
                "Security_ISIN": identity.security_isin,
                "Identity_Effective_Date": identity.identity_effective_date,
                "Identity_Source_URL": identity.identity_source_url,
                "Reason": identity.reason,
                "Member_From": pd.Timestamp(item.Member_From),
                "Member_To": pd.Timestamp(item.Member_To),
            }
        )
    table = pd.DataFrame(rows, columns=PRICE_IDENTITY_COLUMNS)
    violations = validate_shared_provider_intervals(table)
    if not violations.empty:
        detail = violations.iloc[0]["Detail"]
        raise ValueError(f"PROVIDER_ALIAS_MEMBERSHIP_OVERLAP: {detail}")
    return table.sort_values(
        ["Research_Symbol", "Member_From", "Member_To"]
    ).reset_index(drop=True)


def _validate_provider_price_frame(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise ValueError(f"PRICE_PROVIDER_DATA_EMPTY: {ticker}")
    missing = set(PRICE_COLUMNS).difference(frame.columns)
    if missing:
        raise ValueError(f"PRICE_PROVIDER_SCHEMA_INVALID: {ticker}: {sorted(missing)}")
    result = frame.loc[:, PRICE_COLUMNS].copy()
    dates = pd.DatetimeIndex(pd.to_datetime(result["Date"], errors="coerce"))
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    if dates.isna().any() or dates.duplicated().any():
        raise ValueError(f"PRICE_PROVIDER_DATES_INVALID: {ticker}")
    start_date = pd.Timestamp(PRICE_START)
    end_date = pd.Timestamp(PRICE_END_EXCLUSIVE)
    if (dates < start_date).any() or (dates >= end_date).any():
        raise ValueError(f"PRICE_PROVIDER_DATES_OUT_OF_RANGE: {ticker}")
    result["Date"] = dates.to_numpy()
    return result.sort_values("Date").reset_index(drop=True)


def _download_provider_frames(
    identity_table: pd.DataFrame,
    downloader: Callable[[str, str, str], pd.DataFrame],
) -> dict[tuple[str, str], pd.DataFrame]:
    frames: dict[tuple[str, str], pd.DataFrame] = {}
    provider_groups = identity_table.loc[:, ["Provider", "Provider_Ticker"]].drop_duplicates()
    for provider, ticker in provider_groups.sort_values(["Provider", "Provider_Ticker"]).itertuples(index=False):
        if str(provider).upper() != "YAHOO":
            raise ValueError(f"PRICE_PROVIDER_UNSUPPORTED: {provider}")
        provider_ticker = str(ticker).strip()
        if not provider_ticker:
            raise ValueError("PRICE_PROVIDER_TICKER_BLANK")
        frames[(str(provider), provider_ticker)] = _validate_provider_price_frame(
            downloader(provider_ticker, PRICE_START, PRICE_END_EXCLUSIVE), provider_ticker
        )
    return frames


def _build_price_identity_audit(
    identity_table: pd.DataFrame,
    provider_frames: dict[tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for identity in identity_table.itertuples(index=False):
        provider_frame = provider_frames[(str(identity.Provider), str(identity.Provider_Ticker))]
        dates = provider_frame["Date"]
        active = provider_frame.loc[
            dates.ge(pd.Timestamp(identity.Member_From))
            & dates.le(pd.Timestamp(identity.Member_To))
        ]
        active_count = len(active)
        rows.append(
            {
                **{column: getattr(identity, column) for column in PRICE_IDENTITY_COLUMNS},
                "Provider_Data_Min": dates.min() if not provider_frame.empty else pd.NaT,
                "Provider_Data_Max": dates.max() if not provider_frame.empty else pd.NaT,
                "Provider_Row_Count": len(provider_frame),
                "Active_Interval_Row_Count": active_count,
                "Coverage_Status": "OK" if active_count else "NO_PROVIDER_DATA_IN_ACTIVE_INTERVAL",
                "Violation": "" if active_count else "PRICE_PROVIDER_ACTIVE_INTERVAL_EMPTY",
            }
        )
    return pd.DataFrame(rows, columns=PRICE_IDENTITY_AUDIT_COLUMNS)


def _identity_stock_rows(
    identity_table: pd.DataFrame,
    provider_frames: dict[tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    stock_rows: list[pd.DataFrame] = []
    descriptors = PRICE_IDENTITY_COLUMNS[:9]
    unique_identities = identity_table.drop_duplicates(descriptors)
    for identity in unique_identities.itertuples(index=False):
        provider_frame = provider_frames[(str(identity.Provider), str(identity.Provider_Ticker))]
        copy = provider_frame.copy()
        copy.insert(0, "Reason", str(identity.Reason))
        copy.insert(0, "Identity_Source_URL", str(identity.Identity_Source_URL))
        copy.insert(0, "Identity_Effective_Date", identity.Identity_Effective_Date)
        copy.insert(0, "Security_ISIN", str(identity.Security_ISIN))
        copy.insert(0, "Alias_Applied", bool(identity.Alias_Applied))
        copy.insert(0, "Provider_Ticker", str(identity.Provider_Ticker))
        copy.insert(0, "Provider", str(identity.Provider))
        copy.insert(0, "Membership_Yahoo_Ticker", str(identity.Membership_Yahoo_Ticker))
        copy.insert(0, "Yahoo_Ticker", str(identity.Membership_Yahoo_Ticker))
        copy.insert(0, "Symbol", str(identity.Research_Symbol))
        stock_rows.append(copy.loc[:, PRICE_SNAPSHOT_COLUMNS])
    stock = pd.concat(stock_rows, ignore_index=True) if stock_rows else pd.DataFrame(columns=PRICE_SNAPSHOT_COLUMNS)
    if not stock.empty and stock.duplicated(["Symbol", "Date"]).any():
        raise ValueError("stock snapshot contains duplicate symbol dates")
    return stock


def build_market_snapshot(
    membership: pd.DataFrame,
    aliases: pd.DataFrame,
    downloader: Callable[[str, str, str], pd.DataFrame] = download_adjusted_prices,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Freeze adjusted prices after resolving and validating provider identities."""

    identity_table = build_price_identity_table(membership, aliases)
    provider_frames = _download_provider_frames(identity_table, downloader)
    audit = _build_price_identity_audit(identity_table, provider_frames)
    stock = _identity_stock_rows(identity_table, provider_frames)

    benchmark = _validate_provider_price_frame(
        downloader(NIFTY500_YAHOO_TICKER, PRICE_START, PRICE_END_EXCLUSIVE),
        NIFTY500_YAHOO_TICKER,
    )
    benchmark = benchmark[["Date", "Open", "High", "Low", "Close"]]
    if benchmark["Date"].duplicated().any():
        raise ValueError("benchmark snapshot contains duplicate dates")
    return stock, benchmark, audit


def write_manifest(input_dir: Path, provenance: dict[str, str]) -> pd.DataFrame:
    """Write SHA256/row-count provenance for all frozen CSVs except the manifest itself."""

    input_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    retrieved = datetime.now(timezone.utc).isoformat()
    for path in sorted(input_dir.glob("*.csv")):
        if path.name == "e1_source_manifest.csv":
            continue
        try:
            row_count = len(pd.read_csv(path))
            digest = sha256_file(path)
        except Exception as exc:  # noqa: BLE001 - provenance must retain unreadable artifacts
            row_count = np.nan
            digest = ""
            provenance[f"manifest_error:{path.name}"] = str(exc)
        rows.append(
            {
                "Artifact": path.name,
                "Source": provenance.get(path.name, provenance.get("Source", "official frozen snapshot")),
                "Retrieved_At": retrieved,
                "Row_Count": row_count,
                "SHA256": digest,
                "Primary_Window": f"{PRIMARY_START.date()}..{PRIMARY_END.date()}",
                "Source_Cutoff": str(SOURCE_CUTOFF.date()),
                "Notes": provenance.get(f"notes:{path.name}", ""),
            }
        )
    alias_path = ALIAS_REGISTRY_PATH
    if alias_path.is_file():
        alias_row_count = len(pd.read_csv(alias_path))
        alias_hash = sha256_file(alias_path)
    else:
        alias_row_count = np.nan
        alias_hash = ""
    rows.append(
        {
            "Artifact": "../price_provider_aliases.csv",
            "Source": "official NSE identity-continuity evidence",
            "Retrieved_At": retrieved,
            "Row_Count": alias_row_count,
            "SHA256": alias_hash,
            "Primary_Window": f"{PRIMARY_START.date()}..{PRIMARY_END.date()}",
            "Source_Cutoff": str(SOURCE_CUTOFF.date()),
            "Notes": "provider identity registry; acquisition provenance only",
        }
    )
    membership_path = Path(__file__).resolve().parents[1] / "market_breadth/config/nifty500_membership.csv"
    if membership_path.is_file():
        rows.append(
            {
                "Artifact": "../../market_breadth/config/nifty500_membership.csv",
                "Source": "official PIT membership manifest",
                "Retrieved_At": retrieved,
                "Row_Count": np.nan,
                "SHA256": sha256_file(membership_path),
                "Primary_Window": f"{PRIMARY_START.date()}..{PRIMARY_END.date()}",
                "Source_Cutoff": str(SOURCE_CUTOFF.date()),
                "Notes": "external read-only fingerprint; not copied into E1 input",
            }
        )
    manifest = pd.DataFrame(
        rows,
        columns=[
            "Artifact",
            "Source",
            "Retrieved_At",
            "Row_Count",
            "SHA256",
            "Primary_Window",
            "Source_Cutoff",
            "Notes",
        ],
    )
    manifest.to_csv(input_dir / "e1_source_manifest.csv", index=False)
    return manifest


SMOKE_SYMBOLS = ("RELIANCE", "TCS", "INFY")
SMOKE_VALIDATION_COLUMNS = ["Symbol", "Gate", "Status", "Detail"]
PRICE_SMOKE_SYMBOLS = ("GLS", "ALIVUS")


def _frame_symbol(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame is None or "Symbol" not in frame.columns:
        return pd.DataFrame()
    values = frame["Symbol"].fillna("").astype(str).str.strip().str.upper()
    return frame.loc[values.eq(symbol)].copy()


def _smoke_gate(symbol: str, gate: str, passed: bool, detail: str) -> dict[str, object]:
    return {
        "Symbol": symbol,
        "Gate": gate,
        "Status": "PASS" if passed else "FAIL",
        "Detail": detail,
    }


def evaluate_source_smoke(
    filings: pd.DataFrame,
    eps: pd.DataFrame,
    actions: pd.DataFrame,
    audit: pd.DataFrame,
    symbols: tuple[str, ...] = SMOKE_SYMBOLS,
) -> tuple[str, pd.DataFrame]:
    """Evaluate fixed source-only acceptance gates without inspecting returns or SUE."""

    from compute_e1_sue import basis_chain_status

    requested = tuple(str(symbol).strip().upper() for symbol in symbols)
    rows: list[dict[str, object]] = []
    for symbol in requested:
        symbol_filings = _frame_symbol(filings, symbol)
        symbol_eps = _frame_symbol(eps, symbol)
        filing_ok = not symbol_filings.empty
        rows.append(_smoke_gate(symbol, "FILINGS_PRESENT", filing_ok, f"rows={len(symbol_filings)}"))

        eps_values = pd.to_numeric(symbol_eps.get("EPS", pd.Series(dtype=float)), errors="coerce")
        resolved = symbol_eps.loc[eps_values.notna()].copy()
        if "EPS_Source_Resolved" in resolved:
            resolved = resolved.loc[
                resolved["EPS_Source_Resolved"].astype(str).str.lower().isin({"true", "1"})
            ]
        eps_ok = not resolved.empty
        rows.append(_smoke_gate(symbol, "EPS_RESOLVED", eps_ok, f"rows={len(resolved)}"))

        chain_ok = False
        chain_detail = "no usable 13-quarter basis chain"
        if not resolved.empty and {"Fiscal_Period_End", "Reporting_Basis", "Public_Timestamp"}.issubset(resolved.columns):
            for _, candidate in resolved.sort_values("Fiscal_Period_End").iterrows():
                candidate_basis = str(candidate.get("Reporting_Basis") or "").strip().upper()
                if not candidate_basis or pd.isna(candidate.get("Public_Timestamp")):
                    continue
                chain_ok, reason = basis_chain_status(
                    symbol,
                    pd.Timestamp(candidate["Fiscal_Period_End"]),
                    candidate_basis,
                    pd.Timestamp(candidate["Public_Timestamp"]),
                    resolved,
                    actions,
                )
                if chain_ok:
                    chain_detail = f"basis={candidate_basis} period={candidate['Fiscal_Period_End']}"
                    break
                chain_detail = reason or chain_detail
        rows.append(_smoke_gate(symbol, "BASIS_CHAIN_13_QUARTERS", chain_ok, chain_detail))

        identity_columns = {"BSE_Scrip_Code", "BSE_Scrip_ID"}
        identity_ok = False
        identity_detail = "missing BSE identity columns"
        if identity_columns.issubset(symbol_filings.columns):
            identities = symbol_filings.loc[:, ["BSE_Scrip_Code", "BSE_Scrip_ID"]].copy()
            identities["BSE_Scrip_Code"] = identities["BSE_Scrip_Code"].fillna("").astype(str).str.strip()
            identities["BSE_Scrip_ID"] = identities["BSE_Scrip_ID"].fillna("").astype(str).str.strip().str.upper()
            identities = identities.loc[
                identities["BSE_Scrip_Code"].str.fullmatch(r"\d+")
                & identities["BSE_Scrip_ID"].ne("")
            ].drop_duplicates()
            identity_ok = len(identities) == 1
            identity_detail = f"identities={len(identities)}"
        rows.append(_smoke_gate(symbol, "BSE_IDENTITY_EXACTLY_ONE", identity_ok, identity_detail))

    audit_violations = set()
    if audit is not None and "Violation" in audit.columns:
        audit_violations = set(audit["Violation"].dropna().astype(str))
    transient = sorted(audit_violations.intersection(TRANSIENT_CHECKPOINT_VIOLATIONS))
    rows.append(_smoke_gate("ALL", "NO_TRANSIENT_SOURCE_ERRORS", not transient, ", ".join(transient) or "none"))

    bonus_ok = False
    bonus_detail = "RELIANCE 2024-10-28 bonus factor 2.0 not found"
    if actions is not None and not actions.empty and {"Symbol", "Action_Type", "Ex_Date", "Share_Count_Factor"}.issubset(actions.columns):
        action_frame = actions.copy()
        action_frame["Ex_Date"] = pd.to_datetime(action_frame["Ex_Date"], errors="coerce")
        factor = pd.to_numeric(action_frame["Share_Count_Factor"], errors="coerce")
        sentinel = action_frame.loc[
            action_frame["Symbol"].astype(str).str.upper().eq("RELIANCE")
            & action_frame["Action_Type"].astype(str).str.upper().eq("BONUS")
            & action_frame["Ex_Date"].eq(pd.Timestamp("2024-10-28"))
            & factor.eq(2.0)
        ]
        bonus_ok = not sentinel.empty
        if bonus_ok:
            bonus_detail = "RELIANCE 2024-10-28 bonus factor 2.0 present"
    rows.append(_smoke_gate("RELIANCE", "RELIANCE_BONUS_SENTINEL", bonus_ok, bonus_detail))

    validation = pd.DataFrame(rows, columns=SMOKE_VALIDATION_COLUMNS)
    status = "PASS" if validation["Status"].eq("PASS").all() else "FAIL"
    return status, validation


def run_source_smoke(
    work_dir: Path | str,
    symbols: tuple[str, ...] = SMOKE_SYMBOLS,
) -> dict[str, object]:
    """Run fixed-symbol official-source validation without prices, SUE, or returns."""

    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)
    filings, eps, audit = build_filing_snapshot(
        list(symbols), SOURCE_CUTOFF, checkpoint_dir=root / "filings"
    )
    actions = build_corporate_action_snapshot(list(symbols), SOURCE_CUTOFF)
    filings.to_csv(root / "smoke_exchange_filings.csv", index=False)
    eps.to_csv(root / "smoke_eps.csv", index=False)
    actions.to_csv(root / "smoke_corporate_actions.csv", index=False)
    action_audit = actions.attrs.get("audit", pd.DataFrame())
    if isinstance(action_audit, pd.DataFrame) and not action_audit.empty:
        audit = pd.concat([audit, action_audit], ignore_index=True)
    audit.to_csv(root / "smoke_source_audit.csv", index=False)
    smoke_status, validation = evaluate_source_smoke(filings, eps, actions, audit, symbols=symbols)
    validation.to_csv(root / "smoke_validation.csv", index=False)
    return {
        "Symbols": list(symbols),
        "Filing_Rows": len(filings),
        "EPS_Rows": len(eps),
        "Corporate_Action_Rows": len(actions),
        "Audit_Rows": len(audit),
        "Smoke_Status": smoke_status,
        "Output_Directory": str(root),
    }


def _price_smoke_gate(gate: str, passed: bool, detail: str) -> dict[str, object]:
    return _smoke_gate("PRICE_IDENTITY", gate, passed, detail)


def run_price_identity_smoke(
    work_dir: Path | str,
    downloader: Callable[[str, str, str], pd.DataFrame] = download_adjusted_prices,
) -> dict[str, object]:
    """Run the fixed GLS/ALIVUS provider-identity acquisition gate only."""

    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    calls: list[str] = []
    identities = pd.DataFrame(columns=PRICE_IDENTITY_COLUMNS)
    provider_frames: dict[tuple[str, str], pd.DataFrame] = {}

    try:
        aliases = load_price_aliases(ALIAS_REGISTRY_PATH)
        rows.append(_price_smoke_gate("ALIAS_REGISTRY_VALID", True, str(ALIAS_REGISTRY_PATH)))
    except Exception as exc:  # noqa: BLE001 - smoke output must record invalid provenance
        aliases = pd.DataFrame()
        rows.append(_price_smoke_gate("ALIAS_REGISTRY_VALID", False, str(exc)))

    membership_path = repository_root() / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv"
    try:
        membership = load_membership(membership_path)
        membership = membership.loc[membership["Symbol"].isin(PRICE_SMOKE_SYMBOLS)].copy()
    except Exception as exc:  # noqa: BLE001 - smoke output must fail closed
        membership = pd.DataFrame()
        rows.append(_price_smoke_gate("PIT_MEMBERSHIP_VALID", False, str(exc)))
    else:
        rows.append(_price_smoke_gate("PIT_MEMBERSHIP_VALID", True, f"rows={len(membership)}"))

    resolved: dict[str, object] = {}
    if not aliases.empty:
        for symbol in PRICE_SMOKE_SYMBOLS:
            matching = membership.loc[membership["Symbol"].eq(symbol)] if not membership.empty else pd.DataFrame()
            if matching.empty:
                rows.append(_price_smoke_gate(f"{symbol}_MEMBERSHIP_PRESENT", False, "no PIT rows"))
                continue
            ticker = str(matching.iloc[0]["Yahoo_Ticker"])
            try:
                resolved[symbol] = resolve_price_identity(symbol, ticker, aliases)
                rows.append(_price_smoke_gate(f"{symbol}_MEMBERSHIP_PRESENT", True, f"ticker={ticker}"))
            except Exception as exc:  # noqa: BLE001 - preserve resolver failure
                rows.append(_price_smoke_gate(f"{symbol}_MEMBERSHIP_PRESENT", False, str(exc)))
    else:
        for symbol in PRICE_SMOKE_SYMBOLS:
            rows.append(_price_smoke_gate(f"{symbol}_MEMBERSHIP_PRESENT", False, "alias registry invalid"))

    gls = resolved.get("GLS")
    alivus = resolved.get("ALIVUS")
    rows.append(
        _price_smoke_gate(
            "GLS_PROVIDER_TICKER",
            gls is not None and gls.provider_ticker == "ALIVUS.NS",
            getattr(gls, "provider_ticker", ""),
        )
    )
    rows.append(
        _price_smoke_gate(
            "GLS_ISIN",
            gls is not None and gls.security_isin == "INE03Q201024",
            getattr(gls, "security_isin", ""),
        )
    )
    rows.append(
        _price_smoke_gate(
            "GLS_OFFICIAL_PROVENANCE",
            gls is not None
            and gls.identity_source_url
            == "https://nsearchives.nseindia.com/content/circulars/CML66114.pdf",
            getattr(gls, "identity_source_url", ""),
        )
    )
    rows.append(
        _price_smoke_gate(
            "ALIVUS_NO_ALIAS",
            alivus is not None and alivus.provider_ticker == "ALIVUS.NS" and not alivus.alias_applied,
            getattr(alivus, "provider_ticker", ""),
        )
    )

    try:
        if aliases.empty:
            raise ValueError("PRICE_ALIAS_INVALID_ROW: alias registry invalid")
        identities = build_price_identity_table(membership, aliases)
        interval_violations = validate_shared_provider_intervals(identities)
        rows.append(
            _price_smoke_gate(
                "PIT_INTERVALS_NON_OVERLAPPING",
                interval_violations.empty,
                "none" if interval_violations.empty else interval_violations.to_dict("records"),
            )
        )
    except Exception as exc:  # noqa: BLE001 - retain stable fail-closed smoke evidence
        rows.append(_price_smoke_gate("PIT_INTERVALS_NON_OVERLAPPING", False, str(exc)))

    def recording_downloader(ticker: str, start: str, end_exclusive: str) -> pd.DataFrame:
        calls.append(ticker)
        return downloader(ticker, start, end_exclusive)

    if not identities.empty:
        try:
            provider_frames = _download_provider_frames(identities, recording_downloader)
            rows.append(_price_smoke_gate("ALIVUS_DOWNLOAD_SUCCEEDED", ("YAHOO", "ALIVUS.NS") in provider_frames, "ALIVUS.NS"))
        except Exception as exc:  # noqa: BLE001 - smoke output must retain provider failure
            rows.append(_price_smoke_gate("ALIVUS_DOWNLOAD_SUCCEEDED", False, str(exc)))
    else:
        rows.append(_price_smoke_gate("ALIVUS_DOWNLOAD_SUCCEEDED", False, "identity table unavailable"))

    if provider_frames and not identities.empty:
        audit = _build_price_identity_audit(identities, provider_frames)
        for symbol in PRICE_SMOKE_SYMBOLS:
            active_count = int(audit.loc[audit["Research_Symbol"].eq(symbol), "Active_Interval_Row_Count"].sum())
            rows.append(
                _price_smoke_gate(
                    f"{symbol}_ACTIVE_INTERVAL_DATA",
                    active_count > 0,
                    f"rows={active_count}",
                )
            )
    else:
        for symbol in PRICE_SMOKE_SYMBOLS:
            rows.append(_price_smoke_gate(f"{symbol}_ACTIVE_INTERVAL_DATA", False, "provider data unavailable"))

    rows.append(_price_smoke_gate("ALIVUS_DOWNLOADED_ONCE", calls.count("ALIVUS.NS") == 1, f"calls={calls.count('ALIVUS.NS')}"))
    rows.append(_price_smoke_gate("GLS_NS_NOT_REQUESTED", "GLS.NS" not in calls, f"calls={calls.count('GLS.NS')}"))
    rows.append(_price_smoke_gate("GLS_BO_NOT_REQUESTED", "GLS.BO" not in calls, f"calls={calls.count('GLS.BO')}"))

    validation = pd.DataFrame(rows, columns=SMOKE_VALIDATION_COLUMNS)
    status = "PASS" if not validation.empty and validation["Status"].eq("PASS").all() else "FAIL"
    validation.to_csv(root / "price_identity_smoke.csv", index=False)
    return {
        "Symbols": list(PRICE_SMOKE_SYMBOLS),
        "Requested_Tickers": calls,
        "Price_Smoke_Status": status,
        "Output_Directory": str(root),
    }


def _write_stage_a(
    input_dir: Path,
    membership: pd.DataFrame,
    symbols: list[str],
    work_dir: Path | str | None = None,
) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    work_root = Path(work_dir) if work_dir is not None else None
    if work_root is None:
        filings, eps, audit = build_filing_snapshot(symbols, SOURCE_CUTOFF)
    else:
        filings, eps, audit = build_filing_snapshot(
            symbols, SOURCE_CUTOFF, checkpoint_dir=work_root / "filings"
        )
    actions = build_corporate_action_snapshot(symbols, SOURCE_CUTOFF)
    action_audit = actions.attrs.get("audit", pd.DataFrame())
    if isinstance(action_audit, pd.DataFrame) and not action_audit.empty:
        audit = pd.concat([audit, action_audit], ignore_index=True)
    aliases = load_price_aliases(ALIAS_REGISTRY_PATH)
    market, benchmark, price_identity_audit = build_market_snapshot(membership, aliases)
    filings.to_csv(input_dir / "e1_exchange_filings_snapshot.csv", index=False, date_format="%Y-%m-%d")
    eps.to_csv(input_dir / "e1_eps_snapshot.csv", index=False, date_format="%Y-%m-%d")
    actions.to_csv(input_dir / "e1_corporate_actions_snapshot.csv", index=False, date_format="%Y-%m-%d")
    market.to_csv(input_dir / "e1_stock_prices_snapshot.csv", index=False, date_format="%Y-%m-%d")
    benchmark.to_csv(input_dir / "e1_nifty500_prices_snapshot.csv", index=False, date_format="%Y-%m-%d")
    price_identity_audit.to_csv(
        input_dir / "e1_price_identity_audit.csv", index=False, date_format="%Y-%m-%d"
    )
    audit.reindex(columns=["Symbol", "Source_Record_ID", "Violation", "Detail"]).to_csv(
        input_dir / "e1_source_build_audit.csv", index=False
    )
    price_violations = price_identity_audit.loc[
        price_identity_audit["Violation"].fillna("").astype(str).str.strip().ne("")
    ]
    if not price_violations.empty:
        raise ValueError(
            "PRICE_IDENTITY_INTEGRITY_FAILURE: "
            + "; ".join(price_violations["Violation"].astype(str).unique())
        )
    write_manifest(input_dir, {"Source": "official NSE/BSE and adjusted Yahoo price snapshot"})


def repository_root() -> Path:
    """Resolve the Financial checkout root for direct CLI execution."""

    return Path(__file__).resolve().parents[4]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build the immutable E1 Stage A source snapshot")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--smoke", action="store_true", help="validate a fixed small official-source symbol set only")
    mode.add_argument(
        "--price-smoke",
        action="store_true",
        help="validate the fixed GLS/ALIVUS provider-identity path only",
    )
    parser.add_argument("--work-dir", type=Path, help="temporary directory for resumable source checkpoints")
    args = parser.parse_args()
    module_root = Path(__file__).resolve().parent
    if args.price_smoke:
        smoke_root = args.work_dir or module_root / "price-identity-smoke-work"
        result = run_price_identity_smoke(smoke_root)
        print(result)
        raise SystemExit(0 if result["Price_Smoke_Status"] == "PASS" else 2)
    if args.smoke:
        smoke_root = args.work_dir or module_root / "smoke-work"
        result = run_source_smoke(smoke_root)
        print(result)
        raise SystemExit(0 if result["Smoke_Status"] == "PASS" else 2)
    membership = load_membership(
        repository_root() / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv"
    )
    symbols = _symbols_active_in_window(membership)["Symbol"].astype(str).tolist()
    _write_stage_a(module_root / "input", membership, symbols, work_dir=args.work_dir)
    print(f"Frozen E1 Stage A snapshot for {len(symbols)} symbols")
