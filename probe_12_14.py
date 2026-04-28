#!/usr/bin/env python3
"""Standalone probe for SF-86 Sections 12-14 header and date extraction.

Usage:
    python probe_12_14.py /path/to/form.pdf

Behavior:
    1. Searches the PDF text for Section 12, 13, and 14 headers.
    2. If found, extracts per-entry From/To dates for those sections.
    3. If any of the headers are missing, also emits the raw OCR text for pages 11-34
       so the extraction quality can be reviewed directly.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from pypdf import PdfReader
from sf_validator.utils import parse_date


DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{4}/\d{2}/\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}-\d{1,2}-\d{2,4}|\d{4}-\d{2}|\d{4})\b"
)
ENTRY_RE = re.compile(r"\bentry\s*#\s*(\d+)\b", re.IGNORECASE)
FROM_LABEL_RE = re.compile(r"\bfrom\b(?:\s+date)?[:\s-]*", re.IGNORECASE)
TO_LABEL_RE = re.compile(r"\bto\b(?:\s+date)?[:\s-]*", re.IGNORECASE)
PRESENT_RE = re.compile(r"\bpresent\b", re.IGNORECASE)
OMB_NUMBER_RE = re.compile(r"\b3206\s+0005\b")
LABEL_ONLY_RE = re.compile(
    r"\b(?:entry\s*#\s*\d+|from\s+date|to\s+date|month/year|est\.?|present|provide|select|complete|continued|section\s+1[234][a-z]?)\b",
    re.IGNORECASE,
)

SECTION_SPECS = {
    "12": {
        "title": "Education",
        "header_patterns": (
            re.compile(r"\bsection\s*12\b.*\beducation\b", re.IGNORECASE),
            re.compile(r"\bwhere you went to school\b", re.IGNORECASE),
            re.compile(r"\beducation activities\b", re.IGNORECASE),
        ),
    },
    "13": {
        "title": "Employment",
        "header_patterns": (
            re.compile(r"\bsection\s*13\b.*\bemployment\b", re.IGNORECASE),
            re.compile(r"\bemployment activities\b", re.IGNORECASE),
            re.compile(r"\bemployment record\b", re.IGNORECASE),
        ),
    },
    "14": {
        "title": "Military",
        "header_patterns": (
            re.compile(r"\bsection\s*14\b.*\bmilitary\b", re.IGNORECASE),
            re.compile(r"\bselective service record\b", re.IGNORECASE),
            re.compile(r"\bmilitary record\b", re.IGNORECASE),
        ),
    },
}


@dataclass
class PageText:
    page_number: int
    text: str


def read_pdf_pages(pdf_path: Path) -> List[PageText]:
    reader = PdfReader(str(pdf_path))
    pages: List[PageText] = []
    for index, page in enumerate(reader.pages, start=1):
        pages.append(PageText(page_number=index, text=page.extract_text() or ""))
    return pages


def has_header(text: str, patterns: Iterable[re.Pattern[str]]) -> bool:
    normalized = " ".join(text.split())
    return any(pattern.search(normalized) for pattern in patterns)


def split_entries(text: str) -> List[tuple[Optional[int], str]]:
    matches = list(ENTRY_RE.finditer(text))
    if not matches:
        return [(None, text)]

    entries: List[tuple[Optional[int], str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        entries.append((int(match.group(1)), text[start:end].strip()))
    return entries


def _normalize_probe_text(text: str) -> str:
    normalized = " ".join(text.split())
    normalized = OMB_NUMBER_RE.sub(" ", normalized)
    return " ".join(normalized.split())


def _safe_parse_date(token: str) -> Optional[str]:
    cleaned = token.strip()
    if cleaned.isdigit() and len(cleaned) == 4:
        year = int(cleaned)
        if year < 1900 or year > 2100:
            return None
    try:
        parsed = parse_date(cleaned)
    except ValueError:
        return None
    return parsed.isoformat() if parsed is not None else None


def _first_date_after(label_pattern: re.Pattern[str], text: str) -> Optional[str]:
    label_match = label_pattern.search(text)
    if not label_match:
        return None
    tail = text[label_match.end():label_match.end() + 80]
    if PRESENT_RE.search(tail):
        return None
    for token in DATE_RE.findall(tail):
        parsed = _safe_parse_date(token)
        if parsed is not None:
            return parsed
    return None


def _is_continuation_prompt_only(text: str) -> bool:
    normalized = _normalize_probe_text(text)
    if not normalized:
        return True
    if DATE_RE.search(normalized):
        return False
    stripped = LABEL_ONLY_RE.sub(" ", normalized)
    tokens = [token for token in re.split(r"\W+", stripped) if token]
    meaningful = [token for token in tokens if len(token) > 2 and not token.isdigit()]
    return len(meaningful) < 2


def extract_entry_dates(entry_text: str) -> Dict[str, Optional[str]]:
    normalized = _normalize_probe_text(entry_text)
    return {
        "from_date": _first_date_after(FROM_LABEL_RE, normalized),
        "to_date": _first_date_after(TO_LABEL_RE, normalized),
    }


def probe_sections(pages: Sequence[PageText]) -> Dict[str, Any]:
    results: Dict[str, Any] = {
        "sections": {},
        "missing_headers": [],
        "raw_pages_11_34": [],
    }

    for section_id, spec in SECTION_SPECS.items():
        matching_pages = [page for page in pages if has_header(page.text, spec["header_patterns"])]
        if not matching_pages:
            results["missing_headers"].append(
                {
                    "section": section_id,
                    "expected_header": f"Section {section_id} - {spec['title']}",
                }
            )
            continue

        section_pages: List[Dict[str, Any]] = []
        for page in matching_pages:
            entries = []
            for entry_number, entry_text in split_entries(page.text):
                if _is_continuation_prompt_only(entry_text):
                    continue
                date_info = extract_entry_dates(entry_text)
                entries.append(
                    {
                        "entry_number": entry_number,
                        "from_date": date_info["from_date"],
                        "to_date": date_info["to_date"],
                        "snippet": " ".join(entry_text.split())[:240],
                    }
                )
            section_pages.append(
                {
                    "page": page.page_number,
                    "entry_count": len(entries),
                    "entries": entries,
                }
            )

        results["sections"][section_id] = {
            "title": spec["title"],
            "detected": True,
            "pages": section_pages,
        }

    if results["missing_headers"]:
        for page in pages:
            if 11 <= page.page_number <= 34:
                results["raw_pages_11_34"].append(
                    {
                        "page": page.page_number,
                        "text": page.text,
                    }
                )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe SF-86 Sections 12-14 for headers and entry dates.")
    parser.add_argument("pdf_path", help="Path to the PDF to inspect.")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path).expanduser().resolve()
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    pages = read_pdf_pages(pdf_path)
    report = probe_sections(pages)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
