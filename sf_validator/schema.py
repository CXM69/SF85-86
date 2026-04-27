"""JSON contract helpers for the validator."""

from __future__ import annotations

from typing import Any, Dict


class SchemaValidationError(ValueError):
    """Raised when input payload does not match the accepted schema."""


ENTRY_STRING_FIELDS = {
    "from_date",
    "to_date",
    "street1",
    "street2",
    "address",
    "address1",
    "address2",
    "city",
    "state",
    "postal_code",
    "zip",
    "country",
    "location",
    "location_text",
    "city_state_country",
    "explanation",
    "location_explanation",
    "employment_type",
    "type",
    "status",
    "position_title",
    "employer_name",
    "rank",
    "supervisor_phone",
    "supervisor_email",
    "verifier_name",
    "verifier_phone",
    "verifier_email",
    "base_name",
    "post_name",
    "unit",
    "unit_number",
}

ENTRY_BOOL_FIELDS = {"is_current"}
SECTION_ENTRY_ARRAYS = {"section_11", "section_12", "section_13", "section_23"}
SECTION_OBJECTS = {
    "section_21",
    "section_22",
    "section_24",
    "section_25",
    "section_26",
    "section_27",
    "section_28",
    "section_29",
}


def input_schema() -> Dict[str, Any]:
    """Return a minimal JSON-schema-style contract for accepted input."""
    entry = {
        "type": "object",
        "properties": {
            "from_date": {"type": "string"},
            "to_date": {"type": "string"},
            "street1": {"type": "string"},
            "street2": {"type": "string"},
            "address": {"type": "string"},
            "city": {"type": "string"},
            "state": {"type": "string"},
            "postal_code": {"type": "string"},
            "zip": {"type": "string"},
            "country": {"type": "string"},
            "location": {"type": "string"},
            "explanation": {"type": "string"},
            "location_explanation": {"type": "string"},
            "verifier": {"type": "object"},
        },
        "additionalProperties": True,
    }

    return {
        "type": "object",
        "properties": {
            "section_11": {"type": "array", "items": entry},
            "section_12": {"type": "array", "items": entry},
            "section_13": {"type": "array", "items": entry},
            "section_21": {"type": "object", "additionalProperties": True},
            "section_22": {"type": "object", "additionalProperties": True},
            "section_23": {"type": "array", "items": entry},
            "section_24": {"type": "object", "additionalProperties": True},
            "section_25": {"type": "object", "additionalProperties": True},
            "section_26": {"type": "object", "additionalProperties": True},
            "section_27": {"type": "object", "additionalProperties": True},
            "section_28": {"type": "object", "additionalProperties": True},
            "section_29": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": True,
    }


def validate_payload(payload: Dict[str, Any]) -> None:
    """Validate the incoming JSON payload shape before runtime processing."""
    if not isinstance(payload, dict):
        raise SchemaValidationError("Input payload must be a JSON object.")

    for section_name in SECTION_ENTRY_ARRAYS:
        section_value = payload.get(section_name)
        if section_value is None:
            continue
        if not isinstance(section_value, list):
            raise SchemaValidationError(f"{section_name} must be an array of objects.")
        for index, entry in enumerate(section_value, start=1):
            _validate_entry(section_name, index, entry)

    for section_name in SECTION_OBJECTS:
        section_value = payload.get(section_name)
        if section_value is None:
            continue
        if not isinstance(section_value, dict):
            raise SchemaValidationError(f"{section_name} must be an object.")
        _validate_section_object(section_name, section_value)


def _validate_entry(section_name: str, index: int, entry: Any) -> None:
    if not isinstance(entry, dict):
        raise SchemaValidationError(f"{section_name}[{index}] must be an object.")

    for field_name, value in entry.items():
        if value is None:
            continue
        if field_name in ENTRY_STRING_FIELDS and not isinstance(value, str):
            raise SchemaValidationError(f"{section_name}[{index}].{field_name} must be a string.")
        if field_name in ENTRY_BOOL_FIELDS and not isinstance(value, bool):
            raise SchemaValidationError(f"{section_name}[{index}].{field_name} must be a boolean.")
        if field_name == "verifier":
            _validate_verifier(section_name, index, value)


def _validate_verifier(section_name: str, index: int, verifier: Any) -> None:
    if not isinstance(verifier, dict):
        raise SchemaValidationError(f"{section_name}[{index}].verifier must be an object.")
    for field_name, value in verifier.items():
        if value is None:
            continue
        if not isinstance(value, str):
            raise SchemaValidationError(
                f"{section_name}[{index}].verifier.{field_name} must be a string."
            )


def _validate_section_object(section_name: str, section_value: Dict[str, Any]) -> None:
    for field_name, value in section_value.items():
        if value is None:
            continue
        if not isinstance(value, (str, bool, int, float, dict, list)):
            raise SchemaValidationError(f"{section_name}.{field_name} has an unsupported value type.")
