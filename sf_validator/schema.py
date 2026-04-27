"""JSON contract helpers for the validator."""

from __future__ import annotations

from typing import Any, Dict


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
