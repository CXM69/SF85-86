"""Shared parsing and normalization helpers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional, Sequence, Set, Tuple
import re


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def parse_date(value: Any) -> Optional[date]:
    if value in (None, "", "present", "current"):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%m-%d-%Y", "%Y-%m"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value!r}")


def date_ranges_overlap(
    left_from: Optional[date],
    left_to: Optional[date],
    right_from: Optional[date],
    right_to: Optional[date],
) -> bool:
    floor = date.min
    ceiling = date.max

    left_start = left_from or floor
    left_end = left_to or ceiling
    right_start = right_from or floor
    right_end = right_to or ceiling
    return left_start <= right_end and right_start <= left_end


def compact_address(record: Dict[str, Any]) -> str:
    fields = (
        record.get("street1") or record.get("address1") or record.get("address"),
        record.get("street2") or record.get("address2"),
        record.get("city"),
        record.get("state"),
        record.get("postal_code") or record.get("zip"),
        record.get("country"),
    )
    return " ".join(str(part).strip() for part in fields if part and str(part).strip())


def street_address(record: Dict[str, Any]) -> str:
    fields = (
        record.get("street1") or record.get("address1") or record.get("address"),
        record.get("street2") or record.get("address2"),
    )
    return " ".join(str(part).strip() for part in fields if part and str(part).strip())


def best_location_text(record: Dict[str, Any]) -> str:
    candidates = (
        record.get("location"),
        record.get("location_text"),
        record.get("address"),
        record.get("city_state_country"),
        compact_address(record),
    )
    for candidate in candidates:
        normalized = normalize_text(candidate)
        if normalized:
            return normalized
    return ""


def geo_signature(record: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        normalize_text(record.get("city")),
        normalize_text(record.get("state")),
        normalize_text(record.get("country")),
    )


def extract_tokens(*values: Any) -> Set[str]:
    tokens: Set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if normalized:
            tokens.update(normalized.split())
    return tokens


def coerce_entries(payload: Dict[str, Any], *keys: str) -> Sequence[Dict[str, Any]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []
