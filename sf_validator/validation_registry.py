"""Ordered registry for PDF audit modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Protocol

from .pdf_audit import PageContext, PdfFinding


class PdfAuditModule(Protocol):
    name: str

    def run(self, page_contexts: List[PageContext], form_type: str) -> List[PdfFinding]:
        ...


@dataclass
class ValidationRegistry:
    """Runs PDF audit modules in a fixed sequence."""

    modules: List[PdfAuditModule] = field(default_factory=list)

    def register(self, module: PdfAuditModule) -> None:
        self.modules.append(module)

    def run(self, page_contexts: List[PageContext], form_type: str) -> List[PdfFinding]:
        findings: List[PdfFinding] = []
        for module in self.modules:
            findings.extend(module.run(page_contexts, form_type))
        return findings
