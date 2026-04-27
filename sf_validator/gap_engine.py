"""Timeline validations across Sections 11, 12, and 13."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from .models import ValidationFlag
from .utils import best_location_text, coerce_entries, date_ranges_overlap, geo_signature, parse_date


@dataclass(frozen=True)
class TimelineSpec:
    section: str
    keys: Sequence[str]
    label: str


TIMELINE_SPECS = (
    TimelineSpec(section="11", keys=("section_11", "residences"), label="Residence"),
    TimelineSpec(section="12", keys=("section_12", "education"), label="Education"),
    TimelineSpec(section="13", keys=("section_13", "employment"), label="Employment"),
)


class GapEngine:
    GAP_FLAG = "TIMELINE_GAP_OVER_30_DAYS"
    GEO_FLAG = "TIMELINE_UNEXPLAINED_GEO_OVERLAP"

    def generate(self, payload: Dict[str, Any]) -> List[ValidationFlag]:
        flags: List[ValidationFlag] = []
        for spec in TIMELINE_SPECS:
            entries = list(coerce_entries(payload, *spec.keys))
            flags.extend(self._gap_flags(entries, spec))

        residences = list(coerce_entries(payload, "section_11", "residences"))
        flags.extend(self._geo_overlap_flags(residences, coerce_entries(payload, "section_12", "education"), "12"))
        flags.extend(self._geo_overlap_flags(residences, coerce_entries(payload, "section_13", "employment"), "13"))
        return flags

    def _gap_flags(self, entries: Sequence[Dict[str, Any]], spec: TimelineSpec) -> List[ValidationFlag]:
        normalized = []
        for index, entry in enumerate(entries, start=1):
            from_date = parse_date(entry.get("from_date") or entry.get("from"))
            to_date = parse_date(entry.get("to_date") or entry.get("to"))
            if from_date:
                normalized.append((index, from_date, to_date, entry))

        normalized.sort(key=lambda item: item[1])
        flags: List[ValidationFlag] = []
        for current, nxt in zip(normalized, normalized[1:]):
            current_index, _, current_to, _ = current
            next_index, next_from, _, _ = nxt
            if not current_to or not next_from:
                continue
            gap_days = (next_from - current_to).days
            if gap_days > 30:
                flags.append(
                    ValidationFlag(
                        code=self.GAP_FLAG,
                        severity="high",
                        section=spec.section,
                        message=(
                            f"{spec.label} timeline has a {gap_days}-day gap between entries "
                            f"{current_index} and {next_index}."
                        ),
                        context={"current_index": current_index, "next_index": next_index, "gap_days": gap_days},
                    )
                )
        return flags

    def _geo_overlap_flags(
        self,
        residences: Sequence[Dict[str, Any]],
        other_entries: Sequence[Dict[str, Any]],
        other_section: str,
    ) -> List[ValidationFlag]:
        flags: List[ValidationFlag] = []
        for residence_index, residence in enumerate(residences, start=1):
            for other_index, other in enumerate(other_entries, start=1):
                if not date_ranges_overlap(
                    parse_date(residence.get("from_date") or residence.get("from")),
                    parse_date(residence.get("to_date") or residence.get("to")),
                    parse_date(other.get("from_date") or other.get("from")),
                    parse_date(other.get("to_date") or other.get("to")),
                ):
                    continue

                if geo_signature(residence) == geo_signature(other):
                    continue

                explanation = str(other.get("location_explanation") or other.get("explanation") or "").strip()
                if explanation:
                    continue

                flags.append(
                    ValidationFlag(
                        code=self.GEO_FLAG,
                        severity="medium",
                        section=f"11/{other_section}",
                        message=(
                            f"Residence entry {residence_index} overlaps with Section {other_section} entry "
                            f"{other_index} in different regions without explanation."
                        ),
                        context={
                            "residence_index": residence_index,
                            "other_index": other_index,
                            "residence_location": best_location_text(residence),
                            "other_location": best_location_text(other),
                        },
                    )
                )
        return flags
