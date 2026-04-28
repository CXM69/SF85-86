"""PDF audit module for Section 11."""

from __future__ import annotations

from typing import List

from .pdf_audit import (
    APO_FPO_RE,
    BASE_POST_UNIT_RE,
    PageContext,
    PdfFinding,
    _section11_has_po_box_in_residence_address,
)


class HistoryAudit:
    """Audits the residence-history section."""

    name = "history"
    sections = {"11"}

    def run(self, page_contexts: List[PageContext], form_type: str) -> List[PdfFinding]:
        del form_type
        findings: List[PdfFinding] = []

        for context in page_contexts:
            if context.section not in self.sections:
                continue

            if context.section == "11" and _section11_has_po_box_in_residence_address(context.text):
                findings.append(
                    PdfFinding(
                        code="PDF_SECTION_11_PO_BOX",
                        severity="high",
                        section=context.section,
                        subsection=context.subsection,
                        section_title=context.section_title,
                        entry_number=context.entry_number,
                        screening_protocol="Physical Address Verification",
                        page=context.page,
                        message="Potential Section 11 issue: P.O. Box found where a physical address is expected.",
                        snippet=context.snippet,
                    )
                )

            if context.section == "11" and APO_FPO_RE.search(context.text) and not BASE_POST_UNIT_RE.search(context.text):
                findings.append(
                    PdfFinding(
                        code="PDF_SECTION_11_APO_FPO_INCOMPLETE",
                        severity="medium",
                        section=context.section,
                        subsection=context.subsection,
                        section_title=context.section_title,
                        entry_number=context.entry_number,
                        screening_protocol="APO/FPO Completeness Review",
                        page=context.page,
                        message="Potential Section 11 issue: APO/FPO text found without nearby base, post, or unit detail.",
                        snippet=context.snippet,
                    )
                )

        return findings
