"""Section 13 employment validators."""

from __future__ import annotations

from typing import Any, Dict, List

from .models import ValidationFlag
from .utils import coerce_entries, normalize_text, parse_date


class Section13Validator:
    UNEMPLOYED_NO_VERIFIER = "SECTION_13_UNEMPLOYED_NO_VERIFIER"
    MILITARY_INCOMPLETE = "SECTION_13_MILITARY_INCOMPLETE"

    def generate(self, payload: Dict[str, Any]) -> List[ValidationFlag]:
        entries = list(coerce_entries(payload, "section_13", "employment"))
        flags: List[ValidationFlag] = []

        for index, entry in enumerate(entries, start=1):
            if self._is_unemployed(entry) and self._duration_over_30_days(entry) and not self._has_verifier(entry):
                flags.append(
                    ValidationFlag(
                        code=self.UNEMPLOYED_NO_VERIFIER,
                        severity="high",
                        section="13",
                        message=(
                            f"Employment entry {index} records unemployment over 30 days without a verifier."
                        ),
                        context={"entry_index": index},
                    )
                )

            if self._is_military(entry) and not self._has_military_details(entry):
                flags.append(
                    ValidationFlag(
                        code=self.MILITARY_INCOMPLETE,
                        severity="high",
                        section="13",
                        message=(
                            f"Employment entry {index} is marked as military duty but is missing "
                            "rank or supervisor contact."
                        ),
                        context={"entry_index": index},
                    )
                )

        return flags

    @staticmethod
    def _is_unemployed(entry: Dict[str, Any]) -> bool:
        text = " ".join(
            normalize_text(entry.get(field))
            for field in ("employment_type", "type", "status", "position_title", "employer_name")
        )
        return "unemployed" in text.split()

    @staticmethod
    def _duration_over_30_days(entry: Dict[str, Any]) -> bool:
        from_date = parse_date(entry.get("from_date") or entry.get("from"))
        to_date = parse_date(entry.get("to_date") or entry.get("to"))
        if not from_date or not to_date:
            return False
        return (to_date - from_date).days > 30

    @staticmethod
    def _has_verifier(entry: Dict[str, Any]) -> bool:
        verifier = entry.get("verifier")
        if isinstance(verifier, dict):
            name = verifier.get("name")
            contact = verifier.get("phone") or verifier.get("email")
            return bool(str(name or "").strip() and str(contact or "").strip())

        name = entry.get("verifier_name")
        contact = entry.get("verifier_phone") or entry.get("verifier_email")
        return bool(str(name or "").strip() and str(contact or "").strip())

    @staticmethod
    def _is_military(entry: Dict[str, Any]) -> bool:
        text = " ".join(
            normalize_text(entry.get(field))
            for field in ("employment_type", "type", "status", "position_title", "employer_name")
        )
        return "military" in text.split() or "duty" in text.split()

    @staticmethod
    def _has_military_details(entry: Dict[str, Any]) -> bool:
        rank = entry.get("rank")
        supervisor_contact = entry.get("supervisor_phone") or entry.get("supervisor_email")
        return bool(str(rank or "").strip() and str(supervisor_contact or "").strip())
