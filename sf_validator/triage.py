"""Triage report generation for section-by-section PDF audits."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from .form_schema import get_section_schema
from .pdf_audit import PageContext, PdfFinding


TRIAGE_REPORT_PATH = Path(__file__).resolve().parent.parent / "triage_report.json"


def _section_number(section_id: str) -> int:
    digits = "".join(char for char in section_id if char.isdigit())
    return int(digits) if digits else 999


def build_fatal_missing_section_findings(page_contexts: Sequence[PageContext], form_type: str) -> List[PdfFinding]:
    if form_type != "SF86":
        return []

    detected_sections = {context.section for context in page_contexts}
    findings: List[PdfFinding] = []
    for section_id in ("12", "13", "14"):
        if section_id in detected_sections:
            continue
        schema = get_section_schema(section_id)
        findings.append(
            PdfFinding(
                code="PDF_TRIAGE_FATAL_MISSING_SECTION",
                severity="critical",
                section=section_id,
                subsection=section_id,
                section_title=schema.title,
                entry_number=None,
                screening_protocol="Fatal Error",
                page=0,
                message=(
                    f"Fatal Error: Section {section_id} was not detected in the audit stream. "
                    "Review the PDF sequence and restore this section before relying on the report."
                ),
                snippet="",
            )
        )
    return findings


def build_triage_report(page_contexts: Sequence[PageContext], findings: Sequence[PdfFinding], form_type: str) -> Dict[str, Any]:
    detected_sections = {context.section for context in page_contexts}
    findings_by_section: Dict[str, List[PdfFinding]] = {}
    for finding in findings:
        findings_by_section.setdefault(finding.section, []).append(finding)

    fatal_sections = [
        section_id
        for section_id in ("12", "13", "14")
        if form_type == "SF86" and section_id not in detected_sections
    ]

    sections: List[Dict[str, Any]] = []
    manual_review_required = False
    for section_number in range(1, 30):
        section_id = str(section_number)
        schema = get_section_schema(section_id)
        section_findings = sorted(
            findings_by_section.get(section_id, []),
            key=lambda item: (item.page, item.entry_number or 0, item.code),
        )

        if form_type == "SF85" and section_number > 13:
            triage_status = "Not Applicable"
        elif section_id in fatal_sections:
            triage_status = "Fatal Error"
        elif section_findings:
            triage_status = "Manual Review Required"
        elif section_id in detected_sections:
            triage_status = "Clear"
        else:
            triage_status = "Not Detected"

        if triage_status in {"Fatal Error", "Manual Review Required"}:
            manual_review_required = True

        sections.append(
            {
                "section": section_id,
                "title": schema.title,
                "triage_status": triage_status,
                "Manual_Review_Required": triage_status in {"Fatal Error", "Manual Review Required"},
                "anomalies": [
                    {
                        "code": finding.code,
                        "severity": finding.severity,
                        "page": finding.page or None,
                        "entry_number": finding.entry_number,
                        "message": finding.message,
                    }
                    for finding in section_findings
                ],
            }
        )

    report = {
        "form_type": form_type,
        "Fatal_Error": bool(fatal_sections),
        "fatal_sections": fatal_sections,
        "Manual_Review_Required": manual_review_required,
        "sections": sections,
    }
    TRIAGE_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
