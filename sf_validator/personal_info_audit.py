"""PDF audit module for Sections 1-10."""

from __future__ import annotations

from typing import List

from .pdf_audit import PageContext, PdfFinding, _text_looks_unanswered, get_section_schema


class PersonalInfoAudit:
    """Audits the personal-information band of the SF-85/SF-86."""

    name = "personal_info"
    sections = {str(number) for number in range(1, 11)}

    def run(self, page_contexts: List[PageContext], form_type: str) -> List[PdfFinding]:
        del form_type
        findings: List[PdfFinding] = []

        for context in page_contexts:
            if context.section not in self.sections:
                continue

            schema = get_section_schema(context.section)
            entry_segments = []
            if schema.entry_based:
                from .pdf_audit import _split_entry_segments  # lazy to avoid hard import cycle at module import time

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
                                    "data was detected for this entry. Review the entry and complete the required "
                                    "fields with the applicant."
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

        return findings
