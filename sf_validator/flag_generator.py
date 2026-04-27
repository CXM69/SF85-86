"""Generate review flags for cross-section SF-85/SF-86 data checks."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .models import ValidationFlag
from .utils import (
    best_location_text,
    coerce_entries,
    compact_address,
    date_ranges_overlap,
    extract_tokens,
    geo_signature,
    normalize_text,
    parse_date,
    street_address,
)


def _match_strength(residence: Dict[str, Any], activity: Dict[str, Any]) -> Tuple[bool, str]:
    residence_street = normalize_text(street_address(residence))
    activity_street = normalize_text(street_address(activity))
    residence_address = normalize_text(compact_address(residence))
    activity_address = normalize_text(compact_address(activity))
    residence_geo = geo_signature(residence)
    activity_geo = geo_signature(activity)
    residence_location = best_location_text(residence)
    activity_location = best_location_text(activity)

    if (
        residence_street
        and activity_street
        and residence_address
        and activity_address
        and residence_address == activity_address
    ):
        return True, "exact_address"

    if residence_geo == activity_geo and any(residence_geo):
        return True, "same_region"

    residence_tokens = extract_tokens(residence_location)
    activity_tokens = extract_tokens(activity_location)
    common_tokens = residence_tokens & activity_tokens
    if len(common_tokens) >= 2:
        return True, "shared_location_terms"

    return False, "no_match"


class FlagGenerator:
    """Cross-reference Section 11 residences against Section 23 drug activity entries.

    Expected JSON shape:

    {
        "section_11": [{"from_date": "...", "to_date": "...", "city": "...", ...}],
        "section_23": [{"from_date": "...", "to_date": "...", "location": "...", ...}]
    }
    """

    FLAG_CODE = "SECTION_11_23_LOCATION_OVERLAP"

    def generate(self, payload: Dict[str, Any]) -> List[ValidationFlag]:
        residences = coerce_entries(payload, "section_11", "residences")
        activities = coerce_entries(payload, "section_23", "drug_activity_locations")

        results: List[ValidationFlag] = []
        for residence_index, residence in enumerate(residences, start=1):
            for activity_index, activity in enumerate(activities, start=1):
                if not self._entries_overlap(residence, activity):
                    continue

                matched, match_basis = _match_strength(residence, activity)
                if not matched:
                    continue

                results.append(
                    ValidationFlag(
                        code=self.FLAG_CODE,
                        severity="high",
                        section="11/23",
                        message=self._build_message(
                            residence_index=residence_index,
                            activity_index=activity_index,
                            match_basis=match_basis,
                            residence=residence,
                            activity=activity,
                        ),
                        context={
                            "residence_index": residence_index,
                            "activity_index": activity_index,
                            "match_basis": match_basis,
                            "residence_location": best_location_text(residence),
                            "activity_location": best_location_text(activity),
                        },
                    )
                )

        return results

    @staticmethod
    def _entries_overlap(residence: Dict[str, Any], activity: Dict[str, Any]) -> bool:
        return date_ranges_overlap(
            parse_date(residence.get("from_date") or residence.get("from")),
            parse_date(residence.get("to_date") or residence.get("to")),
            parse_date(activity.get("from_date") or activity.get("from")),
            parse_date(activity.get("to_date") or activity.get("to")),
        )

    @staticmethod
    def _build_message(
        residence_index: int,
        activity_index: int,
        match_basis: str,
        residence: Dict[str, Any],
        activity: Dict[str, Any],
    ) -> str:
        residence_label = compact_address(residence) or residence.get("location") or "unknown residence"
        activity_label = compact_address(activity) or activity.get("location") or "unknown location"
        basis_text = match_basis.replace("_", " ")
        return (
            f"Section 11 residence entry {residence_index} overlaps with Section 23 activity entry "
            f"{activity_index} at a matching location ({basis_text}). Residence: {residence_label}. "
            f"Activity location: {activity_label}."
        )
