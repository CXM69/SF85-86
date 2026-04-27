"""Section 11 residence validators."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import re

from .models import ValidationFlag
from .utils import coerce_entries, compact_address, normalize_text, parse_date


PO_BOX_PATTERN = re.compile(r"\b(p\.?\s*o\.?\s*box|post\s+office\s+box)\b", re.IGNORECASE)


class Section11Validator:
    MISSING_PHYSICAL_ADDRESS = "SECTION_11_MISSING_PHYSICAL_ADDRESS"
    PO_BOX_ADDRESS = "SECTION_11_PO_BOX_NOT_ALLOWED"
    APO_FPO_INCOMPLETE = "SECTION_11_APO_FPO_INCOMPLETE"
    VERIFIER_MATCH = "SECTION_11_VERIFIER_SAME_AS_CURRENT"

    def generate(self, payload: Dict[str, Any]) -> List[ValidationFlag]:
        residences = list(coerce_entries(payload, "section_11", "residences"))
        current_address = self._current_residence_address(residences)
        flags: List[ValidationFlag] = []

        for index, residence in enumerate(residences, start=1):
            address = compact_address(residence)
            normalized_address = normalize_text(address)

            if not address:
                flags.append(
                    ValidationFlag(
                        code=self.MISSING_PHYSICAL_ADDRESS,
                        severity="high",
                        section="11",
                        message=f"Residence entry {index} is missing a physical address.",
                        context={"entry_index": index},
                    )
                )
            elif PO_BOX_PATTERN.search(address):
                flags.append(
                    ValidationFlag(
                        code=self.PO_BOX_ADDRESS,
                        severity="high",
                        section="11",
                        message=f"Residence entry {index} uses a P.O. Box, which is not allowed.",
                        context={"entry_index": index, "address": address},
                    )
                )

            if self._is_apo_fpo(residence) and not self._has_apo_fpo_details(residence):
                flags.append(
                    ValidationFlag(
                        code=self.APO_FPO_INCOMPLETE,
                        severity="high",
                        section="11",
                        message=(
                            f"Residence entry {index} uses APO/FPO addressing but is missing "
                            "base/post name or unit information."
                        ),
                        context={"entry_index": index, "address": address},
                    )
                )

            verifier_address = compact_address(residence.get("verifier", {}))
            if (
                current_address
                and verifier_address
                and normalize_text(verifier_address) == normalize_text(current_address)
                and normalized_address == normalize_text(current_address)
            ):
                flags.append(
                    ValidationFlag(
                        code=self.VERIFIER_MATCH,
                        severity="medium",
                        section="11",
                        message=(
                            f"Residence entry {index} lists a verifier address that matches the "
                            "applicant's current address."
                        ),
                        context={"entry_index": index, "verifier_address": verifier_address},
                    )
                )

        return flags

    def _current_residence_address(self, residences: List[Dict[str, Any]]) -> Optional[str]:
        current_entries = []
        for residence in residences:
            if residence.get("is_current") is True or parse_date(residence.get("to_date") or residence.get("to")) is None:
                current_entries.append(residence)

        if current_entries:
            return compact_address(current_entries[0])
        return None

    @staticmethod
    def _is_apo_fpo(residence: Dict[str, Any]) -> bool:
        values = (
            residence.get("city"),
            residence.get("state"),
            residence.get("postal_code"),
            residence.get("zip"),
            residence.get("address"),
            residence.get("street1"),
        )
        combined = " ".join(str(value) for value in values if value)
        normalized = normalize_text(combined)
        return "apo" in normalized.split() or "fpo" in normalized.split()

    @staticmethod
    def _has_apo_fpo_details(residence: Dict[str, Any]) -> bool:
        base_or_post = residence.get("base_name") or residence.get("post_name")
        unit = residence.get("unit") or residence.get("unit_number")
        return bool(str(base_or_post or "").strip() and str(unit or "").strip())
