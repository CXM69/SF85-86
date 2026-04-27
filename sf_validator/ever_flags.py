"""Section 21-29 'ever' answer scanner."""

from __future__ import annotations

from typing import Any, Dict, List

from .models import ValidationFlag


class EverFlagScanner:
    def generate(self, payload: Dict[str, Any]) -> List[ValidationFlag]:
        flags: List[ValidationFlag] = []
        for section_number in range(21, 30):
            section_key = f"section_{section_number}"
            section_data = payload.get(section_key)
            if not isinstance(section_data, dict):
                continue

            for field_name, value in section_data.items():
                if isinstance(value, str) and value.strip().lower() == "yes":
                    flags.append(
                        ValidationFlag(
                            code="EVER_FLAG_REVIEW_REQUIRED",
                            severity="high",
                            section=str(section_number),
                            message=f"Section {section_number} field '{field_name}' answered Yes.",
                            context={"field": field_name, "answer": value},
                            export_tag="Review Required",
                        )
                    )
        return flags
