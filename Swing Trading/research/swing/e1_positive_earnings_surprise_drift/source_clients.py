"""Official NSE/BSE filing catalog clients and metadata normalizers.

This module is deliberately limited to source acquisition and provenance. It
does not identify trades, calculate SUE, or inspect post-event prices.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

import pandas as pd
import pytz
import requests


NSE_LEGACY_URL = "https://www.nseindia.com/api/corporates-financial-results"
NSE_INTEGRATED_URL = "https://www.nseindia.com/api/integrated-filing-results"
BSE_RESULTS_URL = "https://api.bseindia.com/BseIndiaAPI/api/TabResults/w"
BSE_CORPORATE_ACTIONS_URL = "https://api.bseindia.com/BseIndiaAPI/api/CorporateAction/w"
BSE_SECURITY_MASTER_URL = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
INDIA_TZ = "Asia/Kolkata"
TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


class BseIdentifierError(ValueError):
    """Raised when an official BSE security identity cannot be resolved uniquely."""

    def __init__(self, code: str, symbol: str) -> None:
        self.code = code
        self.symbol = symbol
        super().__init__(f"{code}: {symbol}")


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _get(record: Mapping[str, object], *names: str) -> object | None:
    by_key = {_key(name): value for name, value in record.items()}
    for name in names:
        value = by_key.get(_key(name))
        if value is not None and not (isinstance(value, str) and not value.strip()):
            return value
    return None


def _get_usable(record: Mapping[str, object], *names: str) -> object | None:
    """Return the first non-placeholder value from the source aliases."""

    for name in names:
        value = _get(record, name)
        if value is None:
            continue
        normalized = str(value).strip().lower()
        last_path_part = normalized.rstrip("/").rsplit("/", 1)[-1]
        if normalized in {"", "-", "na", "n/a", "null", "none"} or last_path_part in {
            "-",
            "null",
            "undefined",
        }:
            continue
        return value
    return None


def _date(value: object | None) -> pd.Timestamp:
    if value is None:
        return pd.NaT
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return pd.NaT
    stamp = pd.Timestamp(parsed)
    return stamp.tz_localize(None) if stamp.tz is not None else stamp.normalize()


def _public_timestamp(value: object | None) -> pd.Timestamp:
    if value is None:
        return pd.NaT
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return pd.NaT
    stamp = pd.Timestamp(parsed)
    if stamp.tz is None:
        return stamp.tz_localize(pytz.timezone(INDIA_TZ))
    return stamp.tz_convert(pytz.timezone(INDIA_TZ))


def _basis(value: object | None) -> str:
    text = str(value or "").strip().lower()
    if "consolid" in text or text in {"c", "true", "1"}:
        return "CONSOLIDATED"
    if "standalone" in text or "separate" in text or text in {"s", "false", "0"}:
        return "STANDALONE"
    return ""


def _original_or_revised(value: object | None) -> str:
    text = str(value or "").strip().lower()
    if any(token in text for token in ("revis", "amend", "correct")):
        return "REVISED"
    return "ORIGINAL"


def _quarter(period_end: pd.Timestamp) -> str:
    if pd.isna(period_end):
        return ""
    return {3: "Q4", 6: "Q1", 9: "Q2", 12: "Q3"}.get(int(period_end.month), "")


def _period_kind(value: object | None) -> str:
    text = str(value or "").strip().lower()
    return "ANNUAL" if "annual" in text or "year" in text else "QUARTERLY"


def normalize_nse_record(record: dict[str, object], feed: str) -> dict[str, object]:
    """Normalize one NSE catalog record while retaining its source identity."""

    period_end = _date(
        _get(record, "toDate", "periodEndDate", "period_end", "periodEnd", "qe_Date", "qeDate")
    )
    submission = _get(
        record,
        "Type of Submission",
        "typeOfSubmission",
        "submissionType",
        "type_Sub",
    )
    revision = _get(record, "revised", "revision", "isRevised", "revised_Date")
    if submission is not None:
        original_or_revised = _original_or_revised(submission)
    else:
        original_or_revised = _original_or_revised(revision)
    machine_url = _get_usable(
        record,
        "xbrl",
        "xbrlFile",
        "xbrlUrl",
        "iXBRL",
        "ixbrl",
        "machineReadableUrl",
    )
    source_url = _get_usable(
        record, "sourceUrl", "source_url", "detailUrl", "url", "attachment"
    )
    if source_url is None:
        source_url = machine_url or ""
    basis = _basis(_get(record, "consolidated", "reportingBasis", "basis", "resultType"))
    kind = _period_kind(_get(record, "quarterlyOrAnnual", "periodType", "resultPeriod"))
    row: dict[str, object] = {
        "Symbol": str(_get(record, "symbol", "Symbol", "series") or "").strip().upper(),
        "Exchange": "NSE",
        "Feed": feed,
        "Fiscal_Period_End": period_end,
        "Fiscal_Quarter": _quarter(period_end),
        "Reporting_Basis": basis,
        "Quarterly_or_Annual": kind,
        "Original_or_Revised": original_or_revised,
        "Public_Timestamp": _public_timestamp(
            _get(
                record,
                "broadCastDate",
                "broadcastDate",
                "broadcast_Date",
                "Broadcast Date",
                "publicTimestamp",
                "filingDate",
                "creation_Date",
            )
        ),
        "Source_URL": str(source_url or ""),
        "Source_Record_ID": str(
            _get_usable(record, "recordId", "id", "fileName", "seq_Id", "seqNumber", "xbrl")
            or ""
        ),
        "Machine_Readable_URL": str(machine_url or ""),
    }
    if _get(record, "EPS", "basicEPS", "basicEps") is not None:
        row["EPS"] = _get(record, "EPS", "basicEPS", "basicEps")
    return row


def normalize_bse_record(record: dict[str, object]) -> dict[str, object]:
    """Normalize one BSE result record while retaining exact provenance."""

    period_end = _date(_get(record, "period_end", "periodEnd", "toDate", "periodEndDate"))
    revision = _get(record, "revision", "revised", "submissionType")
    machine_url = _get(record, "xbrl", "xbrlFile", "xbrlUrl", "machineReadableUrl")
    source_url = _get(record, "sourceUrl", "source_url", "detailUrl", "url", "attachment")
    if source_url is None:
        source_url = machine_url or ""
    row: dict[str, object] = {
        "Symbol": str(_get(record, "symbol", "scripName", "securityName") or "").strip().upper(),
        "Exchange": "BSE",
        "Feed": "corporate-results",
        "Fiscal_Period_End": period_end,
        "Fiscal_Quarter": _quarter(period_end),
        "Reporting_Basis": _basis(_get(record, "consolidated", "reportingBasis", "basis", "result_type")),
        "Quarterly_or_Annual": _period_kind(_get(record, "periodType", "quarterlyOrAnnual", "resultPeriod")),
        "Original_or_Revised": _original_or_revised(revision),
        "Public_Timestamp": _public_timestamp(
            _get(record, "announcement_datetime", "broadcastDate", "publicTimestamp", "filingDate")
        ),
        "Source_URL": str(source_url or ""),
        "Source_Record_ID": str(
            _get(record, "recordId", "id", "scripCode", "SCRIP_CD", "BSE_Scrip_Code") or ""
        ),
        "Machine_Readable_URL": str(machine_url or ""),
        "BSE_Scrip_Code": str(_get(record, "BSE_Scrip_Code", "scripCode", "securityCode") or ""),
        "BSE_Scrip_ID": str(
            _get(record, "BSE_Scrip_ID", "scripId", "scripID", "instrumentCode", "symbol") or ""
        ),
        "BSE_Mapping_Source_URL": str(_get(record, "BSE_Mapping_Source_URL") or ""),
    }
    if _get(record, "EPS", "basicEPS", "basicEps") is not None:
        row["EPS"] = _get(record, "EPS", "basicEPS", "basicEps")
    return row


def _records(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in (
        "data",
        "results",
        "result",
        "records",
        "items",
        "resultinS",
        "Table",
        "Table1",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _records(value)
            if nested:
                return nested
    return []


def resolve_bse_identifier(
    symbol: str,
    securities: list[dict[str, object]],
    source_url: str = BSE_SECURITY_MASTER_URL,
) -> dict[str, str]:
    """Resolve an NSE symbol using exact fields from an official BSE security list."""

    requested = str(symbol).strip().upper()
    matches: list[dict[str, str]] = []
    for record in securities:
        aliases = {
            str(value).strip().upper()
            for value in (
                _get(record, "Scrip ID", "scripId", "scripID", "instrumentCode"),
                _get(record, "scrip_id", "Symbol", "symbol", "securitySymbol"),
            )
            if value is not None and str(value).strip()
        }
        if requested not in aliases:
            continue
        code_value = _get(
            record,
            "Scrip Code",
            "SCRIP_CD",
            "scripCode",
            "securityCode",
            "security_code",
        )
        scrip_code = str(code_value).strip() if code_value is not None else ""
        scrip_id_value = _get(
            record,
            "Scrip ID",
            "scripId",
            "scripID",
            "scrip_id",
            "instrumentCode",
            "Symbol",
            "symbol",
        )
        scrip_id = str(scrip_id_value).strip() if scrip_id_value is not None else ""
        if not scrip_code.isdigit() or not scrip_id:
            continue
        matches.append(
            {
                "BSE_Scrip_Code": scrip_code,
                "BSE_Scrip_ID": scrip_id,
                "BSE_Mapping_Source_URL": source_url,
            }
        )
    unique = {(item["BSE_Scrip_Code"], item["BSE_Scrip_ID"]): item for item in matches}
    if not unique:
        raise BseIdentifierError("BSE_IDENTIFIER_UNRESOLVED", requested)
    if len(unique) != 1:
        raise BseIdentifierError("BSE_IDENTIFIER_AMBIGUOUS", requested)
    return next(iter(unique.values()))


class _OfficialResultsClient:
    def __init__(
        self,
        session: requests.Session | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
                "Accept": "application/json,text/plain,*/*",
            }
        )
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self._active_symbol: str | None = None

    def _get_json(self, url: str, params: dict[str, object] | None = None) -> object:
        last_response: requests.Response | None = None
        for attempt in range(self.max_retries):
            response = self.session.get(url, params=params, timeout=self.timeout)
            last_response = response
            if response.status_code in TRANSIENT_STATUS_CODES and attempt + 1 < self.max_retries:
                continue
            response.raise_for_status()
            return response.json()
        assert last_response is not None
        last_response.raise_for_status()
        return last_response.json()

    def _get_json_checked(self, url: str, params: dict[str, object] | None = None) -> object:
        """Fetch JSON while preserving BSE non-JSON and HTTP failures explicitly."""

        last_response: requests.Response | None = None
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                if self._active_symbol:
                    raise BseIdentifierError("BSE_SOURCE_ERROR", self._active_symbol) from exc
                raise
            last_response = response
            if response.status_code in TRANSIENT_STATUS_CODES and attempt + 1 < self.max_retries:
                continue
            if response.status_code != 200:
                try:
                    response.raise_for_status()
                except Exception as exc:  # noqa: BLE001 - preserve the source failure code
                    if self._active_symbol:
                        raise BseIdentifierError("BSE_SOURCE_ERROR", self._active_symbol) from exc
                    raise
                raise ValueError(f"HTTP {response.status_code}")
            content = bytes(getattr(response, "content", b""))
            content_type = str(
                (getattr(response, "headers", {}) or {}).get("Content-Type", "")
            ).lower()
            looks_json = content.lstrip().startswith((b"{", b"[")) or "json" in content_type
            if not looks_json:
                error = BseIdentifierError(
                    "BSE_SOURCE_NON_JSON", self._active_symbol or "UNKNOWN"
                )
                raise error
            try:
                decoded = json.loads(content.decode("utf-8-sig"))
                if isinstance(decoded, str):
                    decoded = json.loads(decoded)
                return decoded
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                if self._active_symbol:
                    raise BseIdentifierError("BSE_SOURCE_NON_JSON", self._active_symbol) from exc
                raise ValueError("BSE_SOURCE_NON_JSON") from exc
        assert last_response is not None
        last_response.raise_for_status()
        raise ValueError("BSE_SOURCE_ERROR")


class NseResultsClient(_OfficialResultsClient):
    def list_legacy(self, symbol: str) -> list[dict[str, object]]:
        payload = self._get_json(
            NSE_LEGACY_URL,
            {"index": "equities", "period": "Quarterly", "symbol": symbol.upper()},
        )
        return _records(payload)

    def list_integrated(self, symbol: str) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        page = 0
        while True:
            payload = self._get_json(
                NSE_INTEGRATED_URL,
                {
                    "index": "equities",
                    "symbol": symbol.upper(),
                    "filingType": "Integrated Filing- Financials",
                    "page": page,
                },
            )
            page_records = _records(payload)
            records.extend(page_records)
            total_pages: int | None = None
            if isinstance(payload, dict):
                raw_total = payload.get("totalPages", payload.get("total_pages"))
                try:
                    total_pages = int(raw_total) if raw_total is not None else None
                except (TypeError, ValueError):
                    total_pages = None
            if not page_records or (total_pages is not None and page + 1 >= total_pages) or len(page_records) < 100:
                break
            page += 1
        return records


class BseResultsClient(_OfficialResultsClient):
    def __init__(
        self,
        session: requests.Session | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        super().__init__(session=session, timeout=timeout, max_retries=max_retries)
        self._security_master: list[dict[str, object]] | None = None
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.bseindia.com/",
                "Origin": "https://www.bseindia.com",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

    def list_securities(self) -> list[dict[str, object]]:
        """Load the official BSE equity security master once per client."""

        if self._security_master is None:
            payload = self._get_json_checked(
                BSE_SECURITY_MASTER_URL,
                {
                    "scripcode": "",
                    "Group": "",
                    "industry": "",
                    "segment": "Equity",
                    "status": "Active",
                },
            )
            self._security_master = _records(payload)
        return list(self._security_master)

    def resolve_identifier(self, symbol: str) -> dict[str, str]:
        previous = self._active_symbol
        self._active_symbol = str(symbol).strip().upper()
        try:
            return resolve_bse_identifier(symbol, self.list_securities())
        finally:
            self._active_symbol = previous

    def list_results(self, symbol: str) -> list[dict[str, object]]:
        previous = self._active_symbol
        self._active_symbol = str(symbol).strip().upper()
        try:
            identity = self.resolve_identifier(symbol)
            payload = self._get_json_checked(
                BSE_RESULTS_URL,
                {"scripcode": identity["BSE_Scrip_Code"], "tabtype": "RESULTS"},
            )
            rows: list[dict[str, object]] = []
            for record in _records(payload):
                returned_code = _get(record, "scripCode", "SCRIP_CD", "securityCode")
                if returned_code is not None and str(returned_code).strip() != identity["BSE_Scrip_Code"]:
                    raise BseIdentifierError("BSE_SOURCE_ERROR", symbol)
                returned_symbol = _get(record, "scripId", "scripName", "symbol", "short_name")
                if returned_symbol is not None:
                    normalized_symbol = str(returned_symbol).strip().upper()
                    if normalized_symbol and normalized_symbol not in {
                        str(symbol).strip().upper(),
                        identity["BSE_Scrip_ID"].strip().upper(),
                    }:
                        raise BseIdentifierError("BSE_SOURCE_ERROR", symbol)
                enriched = dict(record)
                enriched.setdefault("symbol", str(symbol).strip().upper())
                enriched.update(
                    {
                        "BSE_Scrip_Code": identity["BSE_Scrip_Code"],
                        "BSE_Scrip_ID": identity["BSE_Scrip_ID"],
                        "BSE_Mapping_Source_URL": identity["BSE_Mapping_Source_URL"],
                    }
                )
                rows.append(enriched)
            return rows
        finally:
            self._active_symbol = previous

    def corporate_actions(self, symbol: str) -> object:
        """Fetch the official BSE corporate-action payload for one identity."""

        previous = self._active_symbol
        self._active_symbol = str(symbol).strip().upper()
        try:
            identity = self.resolve_identifier(symbol)
            return self._get_json_checked(
                BSE_CORPORATE_ACTIONS_URL,
                {"scripcode": identity["BSE_Scrip_Code"]},
            )
        finally:
            self._active_symbol = previous
