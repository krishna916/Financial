"""Build the immutable, source-only E1 Stage A input package."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
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


PRICE_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
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
    overlap = membership.loc[
        membership["Member_From"].le(PRIMARY_END) & membership["Member_To"].ge(PRIMARY_START)
    ]
    return (
        overlap.loc[overlap["Downloadable"] & overlap["Yahoo_Ticker"].ne(""), ["Symbol", "Yahoo_Ticker"]]
        .drop_duplicates()
        .sort_values("Symbol")
        .reset_index(drop=True)
    )


def build_market_snapshot(membership: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Freeze adjusted stock OHLCV and the Nifty 500 benchmark OHLC frame."""

    stock_rows: list[pd.DataFrame] = []
    for item in _symbols_active_in_window(membership).itertuples(index=False):
        frame = download_adjusted_prices(str(item.Yahoo_Ticker), PRICE_START, PRICE_END_EXCLUSIVE)
        copy = frame.copy()
        copy.insert(0, "Yahoo_Ticker", str(item.Yahoo_Ticker))
        copy.insert(0, "Symbol", str(item.Symbol))
        stock_rows.append(copy[["Symbol", "Yahoo_Ticker", *PRICE_COLUMNS]])
    stock = pd.concat(stock_rows, ignore_index=True) if stock_rows else pd.DataFrame(
        columns=["Symbol", "Yahoo_Ticker", *PRICE_COLUMNS]
    )
    if not stock.empty and stock.duplicated(["Symbol", "Date"]).any():
        raise ValueError("stock snapshot contains duplicate symbol dates")

    benchmark = download_adjusted_prices(NIFTY500_YAHOO_TICKER, PRICE_START, PRICE_END_EXCLUSIVE)
    benchmark = benchmark[["Date", "Open", "High", "Low", "Close"]]
    if benchmark["Date"].duplicated().any():
        raise ValueError("benchmark snapshot contains duplicate dates")
    return stock, benchmark


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
    market, benchmark = build_market_snapshot(membership)
    filings.to_csv(input_dir / "e1_exchange_filings_snapshot.csv", index=False, date_format="%Y-%m-%d")
    eps.to_csv(input_dir / "e1_eps_snapshot.csv", index=False, date_format="%Y-%m-%d")
    actions.to_csv(input_dir / "e1_corporate_actions_snapshot.csv", index=False, date_format="%Y-%m-%d")
    market.to_csv(input_dir / "e1_stock_prices_snapshot.csv", index=False, date_format="%Y-%m-%d")
    benchmark.to_csv(input_dir / "e1_nifty500_prices_snapshot.csv", index=False, date_format="%Y-%m-%d")
    audit.reindex(columns=["Symbol", "Source_Record_ID", "Violation", "Detail"]).to_csv(
        input_dir / "e1_source_build_audit.csv", index=False
    )
    write_manifest(input_dir, {"Source": "official NSE/BSE and adjusted Yahoo price snapshot"})


def repository_root() -> Path:
    """Resolve the Financial checkout root for direct CLI execution."""

    return Path(__file__).resolve().parents[4]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build the immutable E1 Stage A source snapshot")
    parser.add_argument("--smoke", action="store_true", help="validate a fixed small official-source symbol set only")
    parser.add_argument("--work-dir", type=Path, help="temporary directory for resumable source checkpoints")
    args = parser.parse_args()
    module_root = Path(__file__).resolve().parent
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
