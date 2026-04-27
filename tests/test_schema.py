import unittest

from sf_validator import SchemaValidationError, validate_payload


class SchemaValidationTests(unittest.TestCase):
    def test_rejects_non_object_payload(self) -> None:
        with self.assertRaises(SchemaValidationError):
            validate_payload([])  # type: ignore[arg-type]

    def test_rejects_non_array_section(self) -> None:
        with self.assertRaises(SchemaValidationError):
            validate_payload({"section_11": {}})

    def test_rejects_non_object_entry(self) -> None:
        with self.assertRaises(SchemaValidationError):
            validate_payload({"section_13": ["bad"]})

    def test_rejects_wrong_field_type(self) -> None:
        with self.assertRaises(SchemaValidationError):
            validate_payload({"section_11": [{"city": 123}]})

    def test_accepts_valid_minimal_payload(self) -> None:
        validate_payload({"section_11": [{"city": "Austin", "state": "TX"}], "section_21": {"q1": "No"}})
