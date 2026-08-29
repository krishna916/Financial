"""Official NSE/BSE filing catalog clients and metadata normalizers.

This module is deliberately limited to source acquisition and provenance. It
does not identify trades, calculate SUE, or inspect post-event prices.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import pandas as pd
import pytz
import requests


NSE_LEGACY_URL = "https://www.nseindia.com/api/corporates-financial-results"
NSE_INTEGRATED_URL = "https://www.nseindia.com/api/integrated-filing-results"
BSE_RESULTS_URL = "https://api.bseindia.com/BseIndiaAPI/api/Result/w"
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

    period_end = _date(_get(record, "toDate", "periodEndDate", "period_end", "periodEnd"))
    submission = _get(record, "Type of Submission", "typeOfSubmission", "submissionType")
    revision = _get(record, "revised", "revision", "isRevised")
    if submission is not None:
        original_or_revised = _original_or_revised(submission)
    else:
        original_or_revised = _original_or_revised(revision)
    machine_url = _get(
        record,
        "xbrl",
        "xbrlFile",
        "xbrlUrl",
        "iXBRL",
        "ixbrl",
        "machineReadableUrl",
    )
    source_url = _get(record, "sourceUrl", "source_url", "detailUrl", "url", "attachment")
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
            _get(record, "broadCastDate", "broadcastDate", "Broadcast Date", "publicTimestamp", "filingDate")
        ),
        "Source_URL": str(source_url or ""),
        "Source_Record_ID": str(_get(record, "recordId", "id", "fileName", "xbrl") or ""),
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
        "Source_Record_ID": str(_get(record, "recordId", "id", "scripCode") or ""),
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
    for key in ("data", "results", "result", "records", "items", "Table", "Table1"):
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
                _get(record, "Symbol", "symbol", "securitySymbol"),
            )
            if value is not None and str(value).strip()
        }
        if requested not in aliases:
            continue
        code_value = _get(record, "Scrip Code", "scripCode", "securityCode", "security_code")
        scrip_code = str(code_value).strip() if code_value is not None else ""
        scrip_id_value = _get(
            record,
            "Scrip ID",
            "scripId",
            "scripID",
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

    def list_securities(self) -> list[dict[str, object]]:
        """Load the official BSE equity security master once per client."""

        if self._security_master is None:
            payload = self._get_json(
                BSE_SECURITY_MASTER_URL,
                {"scripcode": "", "Group": "", "industry": "", "segment": "", "status": ""},
            )
            self._security_master = _records(payload)
        return list(self._security_master)

    def resolve_identifier(self, symbol: str) -> dict[str, str]:
        return resolve_bse_identifier(symbol, self.list_securities())

    def list_results(self, symbol: str) -> list[dict[str, object]]:
        identity = self.resolve_identifier(symbol)
        payload = self._get_json(
            BSE_RESULTS_URL,
            {"scripcode": identity["BSE_Scrip_Code"], "pageno": 1, "pagesize": 100},
        )
        rows: list[dict[str, object]] = []
        for record in _records(payload):
            enriched = dict(record)
            enriched.update(
                {
                    "BSE_Scrip_Code": identity["BSE_Scrip_Code"],
                    "BSE_Scrip_ID": identity["BSE_Scrip_ID"],
                    "BSE_Mapping_Source_URL": identity["BSE_Mapping_Source_URL"],
                }
            )
            rows.append(enriched)
        return rows
