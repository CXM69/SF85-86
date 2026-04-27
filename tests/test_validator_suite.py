import unittest

from sf_validator import ValidatorSuite


class ValidatorSuiteTests(unittest.TestCase):
    def test_runs_all_modules(self) -> None:
        suite = ValidatorSuite()
        payload = {
            "section_11": [
                {
                    "street1": "P.O. Box 9",
                    "city": "Austin",
                    "state": "TX",
                    "is_current": True,
                    "verifier": {"address": "P.O. Box 9", "city": "Austin", "state": "TX"},
                    "from_date": "2020-01-01",
                    "to_date": "2020-12-01",
                }
            ],
            "section_13": [
                {
                    "employment_type": "Unemployed",
                    "from_date": "2021-02-15",
                    "to_date": "2021-04-15",
                    "city": "Denver",
                    "state": "CO",
                }
            ],
            "section_21": {"illegal_drug_use": "Yes"},
            "section_23": [
                {
                    "street1": "P.O. Box 9",
                    "city": "Austin",
                    "state": "TX",
                    "from_date": "2020-03-01",
                    "to_date": "2020-03-10",
                }
            ],
        }

        results = suite.run(payload)
        codes = {flag.code for flag in results}

        self.assertIn("SECTION_11_PO_BOX_NOT_ALLOWED", codes)
        self.assertIn("SECTION_13_UNEMPLOYED_NO_VERIFIER", codes)
        self.assertIn("EVER_FLAG_REVIEW_REQUIRED", codes)
        self.assertIn("SECTION_11_23_LOCATION_OVERLAP", codes)
