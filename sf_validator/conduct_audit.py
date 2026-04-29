"""PDF audit module for Sections 15-29."""

from __future__ import annotations

from datetime import date
import re
from typing import List, Optional, Tuple

from .pdf_audit import (
    PageContext,
    PdfFinding,
    _detect_answer_state_from_text,
    _expected_field_summary,
    _has_section23_detail,
    _has_supporting_detail_in_text,
    _looks_like_section23_followup,
    _text_looks_unanswered,
    get_section_schema,
)
from .utils import parse_date


DATE_TOKEN_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{4}/\d{2}/\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}-\d{1,2}-\d{2,4}|\d{4}-\d{2}|\d{4})\b"
)
FROM_DATE_LABEL_RE = re.compile(r"\bfrom\s+date\b", re.IGNORECASE)
TO_DATE_LABEL_RE = re.compile(r"\bto\s+date\b", re.IGNORECASE)
PRESENT_RE = re.compile(r"\bpresent\b", re.IGNORECASE)
HONORABLE_RE = re.compile(r"\bhonorable\b", re.IGNORECASE)
FULL_TIME_RE = re.compile(r"\bfull[\s-]*time\b", re.IGNORECASE)


class ConductAudit:
    """Audits the conduct/disclosure band of the SF-86."""

    name = "conduct"
    sections = {str(number) for number in range(15, 30)} | {"20A", "20B", "20C", "20D", "20E"}

    def run(self, page_contexts: List[PageContext], form_type: str) -> List[PdfFinding]:
        findings: List[PdfFinding] = []

        for context in page_contexts:
            if context.section not in self.sections:
                continue

            schema = get_section_schema(context.section)
            entry_segments = []
            if schema.entry_based:
                from .pdf_audit import _split_entry_segments

                entry_segments = _split_entry_segments(context.text)

            if schema.blank_review_enabled and schema.entry_based and entry_segments and not schema.answer_gated:
                for entry_number, entry_text in entry_segments:
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
            elif schema.blank_review_enabled and not schema.answer_gated and _text_looks_unanswered(schema, context.text):
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

            if form_type != "SF86" or not schema.answer_gated:
                continue

            if not entry_segments:
                entry_segments = [(context.entry_number, context.text)]

            if context.section == "23" and _looks_like_section23_followup(context.text):
                for entry_number, entry_text in entry_segments:
                    entry_snippet = " ".join(entry_text.split())[:220]
                    findings.append(
                        PdfFinding(
                            code="PDF_SECTION_23_REVIEW_REQUIRED",
                            severity="high",
                            section=context.section,
                            subsection=context.subsection,
                            section_title=context.section_title,
                            entry_number=entry_number,
                            screening_protocol=schema.review_protocol,
                            page=context.page,
                            message="Potential Section 23 issue: this page appears to be a drug-use follow-up disclosure. Review this entry and confirm the applicant completed the required drug-use details.",
                            snippet=entry_snippet,
                        )
                    )
                    if not _has_section23_detail(entry_text, schema.detail_signal_min):
                        findings.append(
                            PdfFinding(
                                code="PDF_SECTION_23_INCOMPLETE",
                                severity="high",
                                section=context.section,
                                subsection=context.subsection,
                                section_title=context.section_title,
                                entry_number=entry_number,
                                screening_protocol=schema.completeness_protocol,
                                page=context.page,
                                message=f"Potential Section 23 issue: this drug-use entry appears incomplete. Review this entry and obtain the missing { _expected_field_summary(schema) } from the applicant.",
                                snippet=entry_snippet,
                            )
                        )
                continue

            for entry_number, entry_text in entry_segments:
                entry_snippet = " ".join(entry_text.split())[:220]
                answer_state = _detect_answer_state_from_text(entry_text, schema)
                if answer_state == "yes":
                    findings.append(
                        PdfFinding(
                            code="PDF_EVER_FLAG_REVIEW_REQUIRED",
                            severity="high",
                            section=context.section,
                            subsection=context.subsection,
                            section_title=context.section_title,
                            entry_number=entry_number,
                            screening_protocol=schema.review_protocol,
                            page=context.page,
                            message=f"Potential Section {context.section} issue: a 'Yes' response appears in this entry. Review the entry and confirm all required follow-up details are completed.",
                            snippet=entry_snippet,
                        )
                    )
                    if not _has_supporting_detail_in_text(entry_text, schema, schema.detail_signal_min):
                        findings.append(
                            PdfFinding(
                                code="PDF_EVER_FLAG_INCOMPLETE",
                                severity="high",
                                section=context.section,
                                subsection=context.subsection,
                                section_title=context.section_title,
                                entry_number=entry_number,
                                screening_protocol=schema.completeness_protocol,
                                page=context.page,
                                message=f"Potential Section {context.section} issue: a 'Yes' response appears without nearby supporting detail. Review this entry because required follow-up information may be missing, including { _expected_field_summary(schema) }.",
                                snippet=entry_snippet,
                            )
                        )
                elif answer_state == "missing":
                    findings.append(
                        PdfFinding(
                            code="PDF_EVER_FLAG_SELECTION_MISSING",
                            severity="high",
                            section=context.section,
                            subsection=context.subsection,
                            section_title=context.section_title,
                            entry_number=entry_number,
                            screening_protocol=schema.missing_selection_protocol,
                            page=context.page,
                            message=f"Potential Section {context.section} issue: no clear Yes/No selection was detected for this entry. Review the entry and confirm the applicant selected an answer and completed any required follow-up information such as { _expected_field_summary(schema) } when applicable.",
                            snippet=entry_snippet,
                        )
                    )

        findings.extend(self._military_discharge_findings(page_contexts))
        findings.extend(self._concurrent_activity_findings(page_contexts))
        return findings

    def _military_discharge_findings(self, page_contexts: List[PageContext]) -> List[PdfFinding]:
        findings: List[PdfFinding] = []

        for context in page_contexts:
            if context.section != "15":
                continue
            from .pdf_audit import _split_entry_segments

            entry_segments = _split_entry_segments(context.text) or [(context.entry_number, context.text)]
            for entry_number, entry_text in entry_segments:
                lower = " ".join(entry_text.lower().split())
                if "type of discharge" not in lower:
                    continue
                if "yes" not in lower and "ever served" not in lower:
                    continue
                if HONORABLE_RE.search(entry_text):
                    continue
                findings.append(
                    PdfFinding(
                        code="PDF_SECTION_15_DISCHARGE_ANOMALY",
                        severity="high",
                        section=context.section,
                        subsection=context.subsection,
                        section_title=context.section_title,
                        entry_number=entry_number,
                        screening_protocol="Discharge Review Anomaly",
                        page=context.page,
                        message=(
                            "Potential Section 15 issue: military service was indicated and the detected Type of Discharge "
                            "does not appear to be Honorable. Manual review is required."
                        ),
                        snippet=" ".join(entry_text.split())[:220],
                    )
                )

        return findings

    def _concurrent_activity_findings(self, page_contexts: List[PageContext]) -> List[PdfFinding]:
        findings: List[PdfFinding] = []
        employment_windows = _collect_section13_employment_windows(page_contexts)
        if not employment_windows:
            return findings

        for context in page_contexts:
            if context.section != "15":
                continue
            from .pdf_audit import _split_entry_segments

            entry_segments = _split_entry_segments(context.text) or [(context.entry_number, context.text)]
            for entry_number, entry_text in entry_segments:
                if "branch of service" not in entry_text.lower() and "ever served" not in entry_text.lower():
                    continue
                military_window = _extract_from_to_dates(entry_text)
                if military_window is None:
                    continue
                military_from, military_to = military_window
                for employment_from, employment_to, employment_page in employment_windows:
                    employment_end = employment_to or date.max
                    military_end = military_to or date.max
                    overlap = military_from <= employment_end and employment_from <= military_end
                    if overlap:
                        findings.append(
                            PdfFinding(
                                code="PDF_SECTION_15_CONCURRENT_ACTIVITY",
                                severity="high",
                                section=context.section,
                                subsection=context.subsection,
                                section_title=context.section_title,
                                entry_number=entry_number,
                                screening_protocol="Concurrent Activity Review",
                                page=context.page,
                                message=(
                                    f"Potential Section 15 issue: military service dates overlap with a full-time civilian employment "
                                    f"entry from Section 13 (page {employment_page}). Review for concurrent activity."
                                ),
                                snippet=" ".join(entry_text.split())[:220],
                            )
                        )
                        break

        return findings


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


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
    normalized = _normalize_text(text)
    from_date = _first_date_after(FROM_DATE_LABEL_RE, normalized)
    if from_date is None:
        return None
    to_date = _first_date_after(TO_DATE_LABEL_RE, normalized)
    return from_date, to_date


def _collect_section13_employment_windows(page_contexts: List[PageContext]) -> List[Tuple[date, Optional[date], int]]:
    windows: List[Tuple[date, Optional[date], int]] = []

    for context in page_contexts:
        if context.section != "13":
            continue
        if not FULL_TIME_RE.search(context.text):
            continue
        from .pdf_audit import _split_entry_segments

        entry_segments = _split_entry_segments(context.text) or [(context.entry_number, context.text)]
        for _entry_number, entry_text in entry_segments:
            if not FULL_TIME_RE.search(entry_text):
                continue
            date_window = _extract_from_to_dates(entry_text)
            if date_window is None:
                continue
            windows.append((date_window[0], date_window[1], context.page))

    return windows
