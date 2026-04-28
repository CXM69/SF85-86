"""Main PDF audit orchestration entrypoint."""

from __future__ import annotations

from typing import List

from .conduct_audit import ConductAudit
from .employment_edu_logic import EmploymentEduLogic
from .history_audit import HistoryAudit
from .pdf_audit import PageContext, PdfFinding, _finding_sort_key, _sequence_gap_findings
from .personal_info_audit import PersonalInfoAudit
from .validation_registry import ValidationRegistry


def run_pdf_audit(page_contexts: List[PageContext], form_type: str) -> List[PdfFinding]:
    registry = ValidationRegistry()
    registry.register(PersonalInfoAudit())
    registry.register(HistoryAudit())
    registry.register(EmploymentEduLogic())
    registry.register(ConductAudit())

    findings = registry.run(page_contexts, form_type)
    findings.extend(_sequence_gap_findings(page_contexts, form_type))
    return sorted(findings, key=_finding_sort_key)
