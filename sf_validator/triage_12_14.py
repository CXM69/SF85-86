"""Targeted recovery logic for SF-86 Sections 12-14."""

from __future__ import annotations

from dataclasses import replace
import re
from typing import List

from .form_schema import get_section_schema
from .pdf_audit import PageContext


SECTION12_PATTERNS = (
    re.compile(r"\bsection\s*12\b", re.IGNORECASE),
    re.compile(r"\bwhere you went to school\b", re.IGNORECASE),
)
SECTION14_PATTERNS = (
    re.compile(r"\bsection\s*14\b", re.IGNORECASE),
    re.compile(r"\byour military history\b", re.IGNORECASE),
)
SECTION13_PATTERNS = (
    re.compile(r"\bsection\s*13\b", re.IGNORECASE),
    re.compile(r"\bemployment activities\b", re.IGNORECASE),
    re.compile(r"\bemployment record\b", re.IGNORECASE),
)
SECTION15_PATTERNS = (
    re.compile(r"\bsection\s*15\b", re.IGNORECASE),
    re.compile(r"\bmilitary record\b", re.IGNORECASE),
)


def apply_12_14_lookbacks(page_contexts: List[PageContext]) -> List[PageContext]:
    contexts = list(page_contexts)

    # Direct keyword-anchor recovery first.
    for index, context in enumerate(contexts):
        normalized = " ".join(context.text.split())
        if _matches_any(normalized, SECTION12_PATTERNS):
            contexts[index] = _with_section(context, "12")
        elif _matches_any(normalized, SECTION14_PATTERNS):
            contexts[index] = _with_section(context, "14")

    # If Section 13 is found, force a lookback for Section 12 on the previous 2 pages.
    for index, context in enumerate(contexts):
        normalized = " ".join(context.text.split())
        if context.section == "13" or _matches_any(normalized, SECTION13_PATTERNS):
            contexts = _assign_lookback(contexts, index, "12", SECTION12_PATTERNS)

    # If Section 15 is found, force a lookback for Section 14 on the previous 2 pages.
    for index, context in enumerate(contexts):
        normalized = " ".join(context.text.split())
        if context.section == "15" or _matches_any(normalized, SECTION15_PATTERNS):
            contexts = _assign_lookback(contexts, index, "14", SECTION14_PATTERNS)

    return contexts


def _assign_lookback(
    page_contexts: List[PageContext],
    current_index: int,
    target_section: str,
    patterns: tuple[re.Pattern[str], ...],
) -> List[PageContext]:
    contexts = list(page_contexts)
    for back_index in range(max(0, current_index - 2), current_index):
        context = contexts[back_index]
        normalized = " ".join(context.text.split())
        if _matches_any(normalized, patterns):
            contexts[back_index] = _with_section(context, target_section)
    return contexts


def _with_section(context: PageContext, section_id: str) -> PageContext:
    schema = get_section_schema(section_id)
    return replace(
        context,
        section=section_id,
        subsection=section_id,
        section_title=schema.title,
    )


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)
