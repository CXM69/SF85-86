"""Local export helpers for review tags."""

from __future__ import annotations

from typing import Dict, List

from .models import ValidationFlag


def build_export_summary(flags: List[ValidationFlag]) -> Dict[str, object]:
    review_required = [flag.to_dict() for flag in flags if flag.export_tag == "Review Required"]
    return {
        "review_required_count": len(review_required),
        "review_required_flags": review_required,
    }
