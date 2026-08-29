"""Strict, namespace-agnostic extraction of quarterly basic continuing EPS."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pandas as pd


BASIC_EPS_ALIASES = {
    "basicearningslossperordinarysharefromcontinuingoperations",
    "basicearningslossperordinarysharecontinuingoperations",
    "basicearningslosspersharefromcontinuingoperations",
    "basicearningslosspersharecontinuingoperations",
    "basicearningspersharefromcontinuingoperations",
    "basicepsfromcontinuingoperations",
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _naive_date(value: object) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    stamp = pd.Timestamp(parsed)
    return stamp.tz_localize(None) if stamp.tz is not None else stamp.normalize()


def _context_basis(context: ET.Element) -> str:
    text = " ".join(context.itertext()).lower()
    if "standalone" in text or "separate" in text:
        return "STANDALONE"
    if "consolidated" in text or "consolidation" in text:
        return "CONSOLIDATED"
    return ""


def _is_quarter(start: pd.Timestamp, end: pd.Timestamp) -> bool:
    if pd.isna(start) or pd.isna(end) or end < start:
        return False
    month_delta = (end.year - start.year) * 12 + end.month - start.month
    return month_delta == 2 and start.day <= 7


def _number(value: str) -> float | None:
    text = value.strip().replace(",", "").replace("−", "-")
    if not text or text.lower() in {"na", "n/a", "nil", "-"}:
        return None
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if pd.notna(parsed) else None


def extract_basic_eps_continuing(
    xbrl_bytes: bytes,
    period_end: pd.Timestamp,
    basis: str,
) -> float | None:
    """Extract only a current-quarter, basis-matching basic continuing EPS fact."""

    try:
        root = ET.fromstring(xbrl_bytes)
    except ET.ParseError:
        return None
    requested_end = _naive_date(period_end)
    requested_basis = str(basis).upper().strip()
    contexts: dict[str, dict[str, object]] = {}
    for element in root.iter():
        if _local_name(element.tag).lower() != "context":
            continue
        context_id = element.attrib.get("id")
        if not context_id:
            continue
        start = end = pd.NaT
        for child in element.iter():
            local = _local_name(child.tag).lower()
            if local == "startdate":
                start = _naive_date(child.text)
            elif local == "enddate":
                end = _naive_date(child.text)
        contexts[context_id] = {
            "start": start,
            "end": end,
            "basis": _context_basis(element),
        }

    candidates: list[tuple[str, float]] = []
    for element in root.iter():
        local = _normalized_name(_local_name(element.tag))
        if local not in BASIC_EPS_ALIASES or "diluted" in local:
            continue
        context = contexts.get(element.attrib.get("contextRef", ""))
        if not context:
            continue
        start = context["start"]
        end = context["end"]
        if not isinstance(start, pd.Timestamp) or not isinstance(end, pd.Timestamp):
            continue
        if end != requested_end or not _is_quarter(start, end):
            continue
        if context["basis"] != requested_basis:
            continue
        parsed = _number("".join(element.itertext()))
        if parsed is not None:
            candidates.append((element.attrib.get("contextRef", ""), parsed))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[0][1]
