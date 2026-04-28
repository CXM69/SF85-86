"""PDF audit module for Sections 12-14."""

from __future__ import annotations

from datetime import date
import re
from typing import List

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
            entries = []
            for context in page_contexts:
                if context.section != section_id:
                    continue
                from .pdf_audit import _split_entry_segments

                entry_segments = _split_entry_segments(context.text) or [(context.entry_number, context.text)]
                for entry_number, entry_text in entry_segments:
                    dates = _extract_dates(entry_text)
                    if len(dates) < 2:
                        continue
                    entries.append((dates[0], dates[1], context, entry_number, entry_text))

            entries.sort(key=lambda item: (item[0], item[1]))
            for previous, current in zip(entries, entries[1:]):
                previous_end = previous[1]
                current_start = current[0]
                if previous_end and current_start:
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


def _extract_dates(text: str) -> List[date]:
    dates: List[date] = []
    for token in DATE_TOKEN_RE.findall(text):
        try:
            parsed = parse_date(token)
        except ValueError:
            continue
        if parsed is not None:
            dates.append(parsed)
    return dates
