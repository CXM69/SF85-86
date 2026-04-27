import unittest

from sf_validator.section_13 import Section13Validator


class Section13ValidatorTests(unittest.TestCase):
    def test_flags_unemployment_without_verifier(self) -> None:
        validator = Section13Validator()
        payload = {
            "section_13": [
                {
                    "employment_type": "Unemployed",
                    "from_date": "2020-01-01",
                    "to_date": "2020-03-15",
                }
            ]
        }

        results = validator.generate(payload)
        self.assertEqual(results[0].code, "SECTION_13_UNEMPLOYED_NO_VERIFIER")

    def test_flags_incomplete_military_entry(self) -> None:
        validator = Section13Validator()
        payload = {
            "section_13": [
                {
                    "employment_type": "Military Duty",
                    "from_date": "2020-01-01",
                    "to_date": "2020-02-01",
                    "rank": "Sergeant",
                }
            ]
        }

        results = validator.generate(payload)
        self.assertEqual(results[0].code, "SECTION_13_MILITARY_INCOMPLETE")
