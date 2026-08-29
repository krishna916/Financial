"""Build the immutable, source-only E1 Stage A input package."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    BSE_RESULTS_URL,
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
    url = str(record.get("Machine_Readable_URL") or "").strip()
    basis = str(record.get("Reporting_Basis") or "").strip()
    period_end = record.get("Fiscal_Period_End")
    if not url or not basis or pd.isna(period_end):
        return None
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return extract_basic_eps_continuing(response.content, pd.Timestamp(period_end), basis)


def build_filing_snapshot(
    symbols: list[str], cutoff: pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Acquire and normalize official filing catalogs without return calculations."""

    nse = NseResultsClient()
    bse = BseResultsClient()
    fetch_session = requests.Session()
    fetch_session.headers.update({"User-Agent": "Mozilla/5.0 E1-source-snapshot"})
    filing_rows: list[dict[str, object]] = []
    eps_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    cutoff = pd.Timestamp(cutoff).normalize()

    for symbol in sorted({str(item).strip().upper() for item in symbols if str(item).strip()}):
        records: list[tuple[dict[str, object], str]] = []
        try:
            records.extend((record, "legacy") for record in nse.list_legacy(symbol))
            records.extend((record, "integrated") for record in nse.list_integrated(symbol))
        except Exception as exc:  # noqa: BLE001 - preserve per-symbol source errors
            audit_rows.append({"Symbol": symbol, "Violation": "NSE_SOURCE_ERROR", "Detail": str(exc)})
        try:
            records.extend((record, "bse") for record in bse.list_results(symbol))
        except Exception as exc:  # noqa: BLE001 - preserve per-symbol source errors
            audit_rows.append({"Symbol": symbol, "Violation": "BSE_SOURCE_ERROR", "Detail": str(exc)})

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
                        "Violation": "EPS_PARSE_ERROR",
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

    filings = pd.DataFrame(filing_rows, columns=SOURCE_COLUMNS)
    eps = pd.DataFrame(eps_rows, columns=EPS_COLUMNS)
    audit = pd.DataFrame(audit_rows)
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
    action_text = str(
        record.get("purpose")
        or record.get("Purpose")
        or record.get("action")
        or record.get("Action_Type")
        or ""
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
        "Ex_Date": _naive_date(record.get("exDate") or record.get("ex_date")),
        "Record_Date": _naive_date(record.get("recordDate") or record.get("record_date")),
        "Source_URL": str(record.get("sourceUrl") or record.get("url") or ""),
        "Source_Record_ID": str(record.get("id") or record.get("recordId") or ""),
    }


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
        endpoints = [
            (
                nse,
                "https://www.nseindia.com/api/corporates-corporateActions",
                {"index": "equities", "symbol": symbol},
            ),
            (
                bse,
                "https://api.bseindia.com/BseIndiaAPI/api/CorporateAction/w",
                {"scripcode": symbol, "pageno": 1, "pagesize": 100},
            ),
        ]
        for client, url, params in endpoints:
            try:
                payload = client._get_json(url, params)
            except Exception as exc:  # noqa: BLE001 - keep acquisition failure visible
                audit.append({"Symbol": symbol, "Violation": "CORPORATE_ACTION_SOURCE_ERROR", "Detail": str(exc)})
                continue
            for record in _records(payload):
                action = _normalize_action(record, symbol)
                if action is None:
                    text = str(record.get("purpose") or record.get("Purpose") or record.get("action") or "")
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


def _write_stage_a(input_dir: Path, membership: pd.DataFrame, symbols: list[str]) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    filings, eps, audit = build_filing_snapshot(symbols, SOURCE_CUTOFF)
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
    module_root = Path(__file__).resolve().parent
    membership = load_membership(
        repository_root() / "Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv"
    )
    symbols = _symbols_active_in_window(membership)["Symbol"].astype(str).tolist()
    _write_stage_a(module_root / "input", membership, symbols)
    print(f"Frozen E1 Stage A snapshot for {len(symbols)} symbols")
