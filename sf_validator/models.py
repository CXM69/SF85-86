"""Shared result types for SF-85/SF-86 validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ValidationFlag:
    """Normalized validation output across all modules."""

    code: str
    severity: str
    section: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    export_tag: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
