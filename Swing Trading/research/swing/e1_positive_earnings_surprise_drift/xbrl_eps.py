"""Strict, namespace-agnostic extraction of quarterly basic continuing EPS."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import pandas as pd


BASIC_EPS_ALIASES = {
    "basicearningslossperordinarysharefromcontinuingoperations",
    "basicearningslossperordinarysharecontinuingoperations",
    "basicearningslosspersharefromcontinuingoperations",
    "basicearningslosspersharecontinuingoperations",
    "basicearningspersharefromcontinuingoperations",
    "basicepsfromcontinuingoperations",
}
NATURE_OF_REPORT_ALIASES = {
    "natureofreportstandaloneconsolidated",
    "natureofreportstandaloneorconsolidated",
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
    return _basis_from_text(" ".join(context.itertext()))


def _basis_from_text(value: object) -> str:
    text = str(value or "").lower()
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


def _is_current_quarter_context(context_ref: object, start: pd.Timestamp, end: pd.Timestamp) -> bool:
    """Use NSE's OneD/FourD marker when both contexts reuse the same dates."""

    marker = _normalized_name(str(context_ref or ""))
    if marker.startswith(("four", "six", "nine", "twelve")) or any(
        token in marker for token in ("ytd", "annual", "year")
    ):
        return False
    if marker.startswith("one") or "quarter" in marker:
        return True
    return _is_quarter(start, end)


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


def _context_record(context: ET.Element) -> dict[str, object]:
    start = end = pd.NaT
    for child in context.iter():
        local = _local_name(child.tag).lower()
        if local == "startdate":
            start = _naive_date(child.text)
        elif local == "enddate":
            end = _naive_date(child.text)
    return {
        "start": start,
        "end": end,
        "basis": _context_basis(context),
    }


def _add_basis_fact(
    contexts: dict[str, dict[str, object]],
    context_ref: str,
    text: object,
) -> None:
    basis = _basis_from_text(text)
    if not basis or context_ref not in contexts:
        return
    current = str(contexts[context_ref].get("basis") or "")
    if current and current != basis:
        contexts[context_ref]["basis"] = ""
    else:
        contexts[context_ref]["basis"] = basis


def _extract_contexts_from_root(root: ET.Element) -> dict[str, dict[str, object]]:
    contexts: dict[str, dict[str, object]] = {}
    for element in root.iter():
        if _local_name(element.tag).lower() != "context":
            continue
        context_id = element.attrib.get("id")
        if context_id:
            contexts[context_id] = _context_record(element)
    for element in root.iter():
        local = _normalized_name(_local_name(element.tag))
        if local in NATURE_OF_REPORT_ALIASES:
            _add_basis_fact(
                contexts,
                element.attrib.get("contextRef", ""),
                " ".join(element.itertext()),
            )
    return contexts


def _extract_contexts_from_xml(payload: bytes) -> dict[str, dict[str, object]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return {}
    return _extract_contexts_from_root(root)


class _InlineXbrlCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.contexts: dict[str, dict[str, object]] = {}
        self.candidates: list[dict[str, object]] = []
        self._context_id: str | None = None
        self._context_field: str | None = None
        self._fact: dict[str, object] | None = None
        self._fact_depth = 0
        self._basis_fact: dict[str, object] | None = None
        self._basis_depth = 0

    @staticmethod
    def _attributes(attributes: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key.lower(): str(value or "") for key, value in attributes}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        local = _local_name(tag).lower()
        attributes = self._attributes(attrs)
        if local == "context":
            context_id = attributes.get("id", "")
            if context_id:
                self._context_id = context_id
                self.contexts[context_id] = {"start": pd.NaT, "end": pd.NaT, "basis": "", "text": []}
        elif local in {"startdate", "enddate"} and self._context_id:
            self._context_field = "start" if local == "startdate" else "end"

        fact_name = attributes.get("name", "")
        fact_local = _normalized_name(fact_name.rsplit(":", 1)[-1])
        if local in {"nonfraction", "nonnumeric"} and attributes.get("contextref"):
            self._fact = {
                "context_ref": attributes.get("contextref", ""),
                "name": fact_local,
                "text": [],
                "scale": attributes.get("scale", ""),
                "sign": attributes.get("sign", ""),
                "nil": attributes.get("nil", "").lower() == "true",
            }
            self._fact_depth = 1
        elif self._fact is not None:
            self._fact_depth += 1

        if (
            self._basis_fact is None
            and attributes.get("contextref")
            and (fact_local in NATURE_OF_REPORT_ALIASES or local in NATURE_OF_REPORT_ALIASES)
        ):
            self._basis_fact = {"context_ref": attributes["contextref"], "text": []}
            self._basis_depth = 1
        elif self._basis_fact is not None:
            self._basis_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._context_id and self._context_id in self.contexts:
            context = self.contexts[self._context_id]
            if self._context_field:
                current = context.get(self._context_field)
                existing = "" if pd.isna(current) else str(current)
                context[self._context_field] = f"{existing}{data}"
            cast_text = context.setdefault("text", [])
            if isinstance(cast_text, list):
                cast_text.append(data)
        if self._fact is not None:
            fact_text = self._fact.setdefault("text", [])
            if isinstance(fact_text, list):
                fact_text.append(data)
        if self._basis_fact is not None:
            basis_text = self._basis_fact.setdefault("text", [])
            if isinstance(basis_text, list):
                basis_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        local = _local_name(tag).lower()
        if self._fact is not None:
            self._fact_depth -= 1
            if self._fact_depth == 0:
                self.candidates.append(self._fact)
                self._fact = None
        if self._basis_fact is not None:
            self._basis_depth -= 1
            if self._basis_depth == 0:
                self._basis_fact["text"] = " ".join(self._basis_fact.get("text", []))
                self._basis_fact = None
        if local in {"startdate", "enddate"}:
            self._context_field = None
        elif local == "context":
            self._context_id = None


def _extract_contexts_from_ixbrl(payload: bytes) -> dict[str, dict[str, object]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        root = None
    if root is not None:
        return _extract_contexts_from_root(root)
    collector = _InlineXbrlCollector()
    collector.feed(payload.decode("utf-8", errors="replace"))
    collector.close()
    for fact in collector.candidates:
        name = str(fact.get("name") or "")
        if name in NATURE_OF_REPORT_ALIASES:
            _add_basis_fact(
                collector.contexts,
                str(fact.get("context_ref") or ""),
                " ".join(fact.get("text", [])),
            )
    for context in collector.contexts.values():
        context["start"] = _naive_date(context.get("start"))
        context["end"] = _naive_date(context.get("end"))
        context["basis"] = context.get("basis") or _basis_from_text(" ".join(context.get("text", [])))
    return collector.contexts


def _extract_eps_candidates_from_root(root: ET.Element) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for element in root.iter():
        local = _normalized_name(_local_name(element.tag))
        if local not in BASIC_EPS_ALIASES or "diluted" in local:
            continue
        if str(element.attrib.get("nil", "")).lower() == "true":
            continue
        parsed = _number("".join(element.itertext()))
        if parsed is not None:
            candidates.append(
                {
                    "context_ref": element.attrib.get("contextRef", ""),
                    "name": local,
                    "value": parsed,
                }
            )
    return candidates


def _inline_number(fact: dict[str, object]) -> float | None:
    if fact.get("nil"):
        return None
    value = _number("".join(str(item) for item in fact.get("text", [])))
    if value is None:
        return None
    scale = str(fact.get("scale") or "").strip()
    if scale:
        try:
            value *= 10 ** int(scale)
        except ValueError:
            return None
    if str(fact.get("sign") or "").strip() == "-":
        value = -abs(value)
    return value


def _extract_eps_candidates(payload: bytes, payload_kind: str) -> list[dict[str, object]]:
    if payload_kind == "xml":
        try:
            return _extract_eps_candidates_from_root(ET.fromstring(payload))
        except ET.ParseError:
            return []
    collector = _InlineXbrlCollector()
    collector.feed(payload.decode("utf-8", errors="replace"))
    collector.close()
    candidates: list[dict[str, object]] = []
    for fact in collector.candidates:
        name = str(fact.get("name") or "")
        if name not in BASIC_EPS_ALIASES or "diluted" in name:
            continue
        value = _inline_number(fact)
        if value is not None:
            candidates.append(
                {
                    "context_ref": fact.get("context_ref", ""),
                    "name": name,
                    "value": value,
                }
            )
    return candidates


def _eps_values_match(first: float, second: float) -> bool:
    difference = abs(first - second)
    if difference <= 0.01:
        return True
    denominator = max(abs(first), abs(second))
    return denominator > 0 and difference / denominator <= 0.005


def extract_basic_eps_continuing(
    xbrl_bytes: bytes,
    period_end: pd.Timestamp,
    basis: str,
) -> float | None:
    """Extract only a current-quarter, basis-matching basic continuing EPS fact."""

    requested_end = _naive_date(period_end)
    requested_basis = str(basis).upper().strip()
    try:
        ET.fromstring(xbrl_bytes)
        payload_kind = "xml"
        contexts = _extract_contexts_from_xml(xbrl_bytes)
    except ET.ParseError:
        payload_kind = "ixbrl_html"
        contexts = _extract_contexts_from_ixbrl(xbrl_bytes)
    candidates = _extract_eps_candidates(xbrl_bytes, payload_kind)
    selected: list[float] = []
    for candidate in candidates:
        context = contexts.get(str(candidate.get("context_ref") or ""))
        if not context:
            continue
        start = context.get("start")
        end = context.get("end")
        if not isinstance(start, pd.Timestamp) or not isinstance(end, pd.Timestamp):
            continue
        if end != requested_end or not _is_current_quarter_context(
            candidate.get("context_ref"), start, end
        ):
            continue
        if context.get("basis") != requested_basis:
            continue
        value = candidate.get("value")
        if isinstance(value, (int, float)) and pd.notna(value):
            selected.append(float(value))
    if not selected:
        return None
    if any(not _eps_values_match(selected[0], value) for value in selected[1:]):
        raise ValueError("EPS_FACT_AMBIGUOUS: remaining quarterly EPS facts disagree")
    return selected[0]
