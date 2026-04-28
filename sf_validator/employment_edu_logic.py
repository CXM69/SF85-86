"""PDF audit module for Sections 12-14."""

from __future__ import annotations

from datetime import date
import re
from typing import List, Optional, Tuple

from .pdf_audit import (
    MILITARY_RE,
    RANK_RE,
    SUPERVISOR_RE,
    UNEMPLOYED_RE,
    PageContext,
    PdfFinding,
    _text_looks_unanswered,
    get_section_schema,
)
from .utils import parse_date


DATE_TOKEN_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{4}/\d{2}/\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}-\d{1,2}-\d{2,4}|\d{4}-\d{2}|\d{4})\b"
)
SUPERVISOR_CONTACT_RE = re.compile(r"\b(?:telephone|phone|email|address|contact)\b", re.IGNORECASE)
ADVERSE_REASON_RE = re.compile(
    r"\b(?:fired|terminated|misconduct|disciplinary|resigned\s+in\s+lieu|forced\s+to\s+resign|quit\s+after\s+warning|suspended)\b",
    re.IGNORECASE,
)
FROM_DATE_LABEL_RE = re.compile(r"\bfrom\s+date\b", re.IGNORECASE)
TO_DATE_LABEL_RE = re.compile(r"\bto\s+date\b", re.IGNORECASE)
PRESENT_RE = re.compile(r"\bpresent\b", re.IGNORECASE)
OMB_NUMBER_RE = re.compile(r"\b3206\s+0005\b")
LABEL_ONLY_RE = re.compile(
    r"\b(?:entry\s*#\s*\d+|from\s+date|to\s+date|month/year|est\.?|present|provide|select|complete|continued|section\s+1[234][a-z]?)\b",
    re.IGNORECASE,
)


class EmploymentEduLogic:
    """Audits the education, employment, and selective-service band."""

    name = "employment_edu_logic"
    sections = {"12", "13", "14"}

    def run(self, page_contexts: List[PageContext], form_type: str) -> List[PdfFinding]:
        del form_type
        findings: List[PdfFinding] = []

        for context in page_contexts:
            if context.section not in self.sections:
                continue

            schema = get_section_schema(context.section)
            entry_segments = []
            if schema.entry_based:
                from .pdf_audit import _split_entry_segments

                entry_segments = _split_entry_segments(context.text)

            if schema.blank_review_enabled and schema.entry_based and entry_segments:
                for entry_number, entry_text in entry_segments:
                    if _is_continuation_prompt_only(entry_text):
                        continue
                    if _text_looks_unanswered(schema, entry_text):
                        findings.append(
                            PdfFinding(
                                code="PDF_SECTION_DATA_MISSING",
                                severity="high",
                                section=context.section,
                                subsection=context.subsection,
                                section_title=context.section_title,
                                entry_number=entry_number,
                                screening_protocol=schema.completeness_protocol,
                                page=context.page,
                                message=(
                                    f"Potential Section {context.section} issue: no clear applicant-supplied "
                                    "data was detected for this entry. Review the entry and complete the required fields with the applicant."
                                ),
                                snippet=" ".join(entry_text.split())[:220],
                            )
                        )
            elif schema.blank_review_enabled and _text_looks_unanswered(schema, context.text):
                findings.append(
                    PdfFinding(
                        code="PDF_SECTION_DATA_MISSING",
                        severity="high",
                        section=context.section,
                        subsection=context.subsection,
                        section_title=context.section_title,
                        entry_number=context.entry_number,
                        screening_protocol=schema.completeness_protocol,
                        page=context.page,
                        message=(
                            f"Potential Section {context.section} issue: no clear applicant-supplied data was "
                            "detected on this page. Review the section and complete the required fields with the applicant."
                        ),
                        snippet=context.snippet,
                    )
                )

            if context.section == "13" and UNEMPLOYED_RE.search(context.text) and "verifier" not in context.text.lower():
                findings.append(
                    PdfFinding(
                        code="PDF_SECTION_13_UNEMPLOYED_NO_VERIFIER",
                        severity="high",
                        section=context.section,
                        subsection=context.subsection,
                        section_title=context.section_title,
                        entry_number=context.entry_number,
                        screening_protocol="Employment Verifier Review",
                        page=context.page,
                        message="Potential Section 13 issue: unemployment text found without nearby verifier text.",
                        snippet=context.snippet,
                    )
                )

            if context.section == "13" and MILITARY_RE.search(context.text) and not (RANK_RE.search(context.text) and SUPERVISOR_RE.search(context.text)):
                findings.append(
                    PdfFinding(
                        code="PDF_SECTION_13_MILITARY_INCOMPLETE",
                        severity="medium",
                        section=context.section,
                        subsection=context.subsection,
                        section_title=context.section_title,
                        entry_number=context.entry_number,
                        screening_protocol="Military Service Detail Review",
                        page=context.page,
                        message="Potential Section 13 issue: military-duty text found without nearby rank and supervisor text.",
                        snippet=context.snippet,
                    )
                )

        findings.extend(self._timeline_gap_findings(page_contexts))
        findings.extend(self._supervisor_contact_findings(page_contexts))
        findings.extend(self._adverse_reason_findings(page_contexts))
        return findings

    def _timeline_gap_findings(self, page_contexts: List[PageContext]) -> List[PdfFinding]:
        findings: List[PdfFinding] = []

        for section_id in self.sections:
            entries: List[Tuple[date, Optional[date], PageContext, Optional[int], str]] = []
            for context in page_contexts:
                if context.section != section_id:
                    continue
                from .pdf_audit import _split_entry_segments

                entry_segments = _split_entry_segments(context.text) or [(context.entry_number, context.text)]
                for entry_number, entry_text in entry_segments:
                    if _is_continuation_prompt_only(entry_text):
                        continue
                    date_window = _extract_from_to_dates(entry_text)
                    if date_window is None:
                        continue
                    entries.append((date_window[0], date_window[1], context, entry_number, entry_text))

            entries.sort(key=lambda item: (item[0], item[1] or date.max))
            for previous, current in zip(entries, entries[1:]):
                previous_end = previous[1]
                current_start = current[0]
                if previous_end is not None and current_start:
                    gap_days = (current_start - previous_end).days
                    if gap_days > 30:
                        context = current[2]
                        findings.append(
                            PdfFinding(
                                code="PDF_SECTION_12_14_TIMELINE_GAP",
                                severity="high",
                                section=section_id,
                                subsection=context.subsection,
                                section_title=context.section_title,
                                entry_number=current[3],
                                screening_protocol="Timeline Gap Review",
                                page=context.page,
                                message=(
                                    f"Potential Section {section_id} issue: a timeline gap greater than 30 days was detected "
                                    f"between entries. Review this section and confirm the chronology is complete."
                                ),
                                snippet=" ".join(current[4].split())[:220],
                            )
                        )
        return findings

    def _supervisor_contact_findings(self, page_contexts: List[PageContext]) -> List[PdfFinding]:
        findings: List[PdfFinding] = []

        for context in page_contexts:
            if context.section not in self.sections:
                continue
            from .pdf_audit import _split_entry_segments

            entry_segments = _split_entry_segments(context.text) or [(context.entry_number, context.text)]
            for entry_number, entry_text in entry_segments:
                if _is_continuation_prompt_only(entry_text):
                    continue
                lower = entry_text.lower()
                if context.section != "13" and "supervisor" not in lower:
                    continue
                if "supervisor" not in lower and "verifier" not in lower:
                    findings.append(
                        PdfFinding(
                            code="PDF_SECTION_12_14_SUPERVISOR_CONTACT_INCOMPLETE",
                            severity="medium",
                            section=context.section,
                            subsection=context.subsection,
                            section_title=context.section_title,
                            entry_number=entry_number,
                            screening_protocol="Supervisor Contact Review",
                            page=context.page,
                            message=(
                                f"Potential Section {context.section} issue: supervisor or verifier contact information "
                                "was not clearly detected for this entry."
                            ),
                            snippet=" ".join(entry_text.split())[:220],
                        )
                    )
                    continue
                if not SUPERVISOR_CONTACT_RE.search(entry_text):
                    findings.append(
                        PdfFinding(
                            code="PDF_SECTION_12_14_SUPERVISOR_CONTACT_INCOMPLETE",
                            severity="medium",
                            section=context.section,
                            subsection=context.subsection,
                            section_title=context.section_title,
                            entry_number=entry_number,
                            screening_protocol="Supervisor Contact Review",
                            page=context.page,
                            message=(
                                f"Potential Section {context.section} issue: supervisor or verifier contact detail appears incomplete. "
                                "Review the entry and confirm phone, email, or address details are present."
                            ),
                            snippet=" ".join(entry_text.split())[:220],
                        )
                    )
        return findings

    def _adverse_reason_findings(self, page_contexts: List[PageContext]) -> List[PdfFinding]:
        findings: List[PdfFinding] = []

        for context in page_contexts:
            if context.section not in self.sections:
                continue
            from .pdf_audit import _split_entry_segments

            entry_segments = _split_entry_segments(context.text) or [(context.entry_number, context.text)]
            for entry_number, entry_text in entry_segments:
                if _is_continuation_prompt_only(entry_text):
                    continue
                if not ADVERSE_REASON_RE.search(entry_text):
                    continue
                findings.append(
                    PdfFinding(
                        code="PDF_SECTION_12_14_ADVERSE_REASON",
                        severity="high",
                        section=context.section,
                        subsection=context.subsection,
                        section_title=context.section_title,
                        entry_number=entry_number,
                        screening_protocol="Adverse Departure Review",
                        page=context.page,
                        message=(
                            f"Potential Section {context.section} issue: adverse reason-for-leaving language was detected. "
                            "Review the entry and determine whether manual follow-up is required."
                        ),
                        snippet=" ".join(entry_text.split())[:220],
                    )
                )
        return findings


def _normalize_probe_text(text: str) -> str:
    normalized = " ".join(text.split())
    normalized = OMB_NUMBER_RE.sub(" ", normalized)
    return " ".join(normalized.split())


def _is_continuation_prompt_only(text: str) -> bool:
    normalized = _normalize_probe_text(text)
    if not normalized:
        return True
    if DATE_TOKEN_RE.search(normalized):
        return False
    stripped = LABEL_ONLY_RE.sub(" ", normalized)
    tokens = [token for token in re.split(r"\W+", stripped) if token]
    meaningful = [token for token in tokens if len(token) > 2 and not token.isdigit()]
    return len(meaningful) < 2


def _safe_parse_date(token: str) -> Optional[date]:
    cleaned = token.strip()
    if cleaned.isdigit() and len(cleaned) == 4:
        year = int(cleaned)
        if year < 1900 or year > 2100:
            return None
    try:
        return parse_date(cleaned)
    except ValueError:
        return None


def _first_date_after(pattern: re.Pattern[str], text: str) -> Optional[date]:
    match = pattern.search(text)
    if not match:
        return None
    window = text[match.end():match.end() + 80]
    if PRESENT_RE.search(window):
        return None
    for token in DATE_TOKEN_RE.findall(window):
        parsed = _safe_parse_date(token)
        if parsed is not None:
            return parsed
    return None


def _extract_from_to_dates(text: str) -> Optional[Tuple[date, Optional[date]]]:
    normalized = _normalize_probe_text(text)
    from_date = _first_date_after(FROM_DATE_LABEL_RE, normalized)
    if from_date is None:
        return None
    to_date = _first_date_after(TO_DATE_LABEL_RE, normalized)
    return from_date, to_date
