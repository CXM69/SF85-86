"""PDF audit module for Sections 15-29."""

from __future__ import annotations

from typing import List

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

        return findings
