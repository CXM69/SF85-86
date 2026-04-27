import unittest

from sf_validator.section_11 import Section11Validator


class Section11ValidatorTests(unittest.TestCase):
    def test_flags_po_box_address(self) -> None:
        validator = Section11Validator()
        payload = {
            "section_11": [
                {
                    "from_date": "2020-01-01",
                    "to_date": "2020-12-01",
                    "street1": "P.O. Box 123",
                    "city": "Austin",
                    "state": "TX",
                }
            ]
        }

        results = validator.generate(payload)
        self.assertEqual(results[0].code, "SECTION_11_PO_BOX_NOT_ALLOWED")

    def test_flags_incomplete_apo_fpo(self) -> None:
        validator = Section11Validator()
        payload = {
            "section_11": [
                {
                    "street1": "PSC 123 Box 456",
                    "city": "APO",
                    "state": "AE",
                    "postal_code": "09012",
                }
            ]
        }

        results = validator.generate(payload)
        self.assertEqual(results[0].code, "SECTION_11_APO_FPO_INCOMPLETE")

    def test_flags_verifier_same_as_current_address(self) -> None:
        validator = Section11Validator()
        payload = {
            "section_11": [
                {
                    "street1": "123 Main St",
                    "city": "Austin",
                    "state": "TX",
                    "is_current": True,
                    "verifier": {"address": "123 Main St", "city": "Austin", "state": "TX"},
                }
            ]
        }

        results = validator.generate(payload)
        self.assertEqual(results[0].code, "SECTION_11_VERIFIER_SAME_AS_CURRENT")
