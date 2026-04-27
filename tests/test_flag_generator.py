import unittest

from sf_validator import FlagGenerator


class FlagGeneratorTests(unittest.TestCase):
    def test_generates_flag_for_exact_address_overlap(self) -> None:
        generator = FlagGenerator()

        payload = {
            "section_11": [
                {
                    "from_date": "2021-01-01",
                    "to_date": "2022-01-15",
                    "street1": "123 Main St",
                    "city": "Denver",
                    "state": "CO",
                    "postal_code": "80202",
                    "country": "USA",
                }
            ],
            "section_23": [
                {
                    "from_date": "2021-06-01",
                    "to_date": "2021-06-30",
                    "street1": "123 Main St",
                    "city": "Denver",
                    "state": "CO",
                    "postal_code": "80202",
                    "country": "USA",
                }
            ],
        }

        results = generator.generate(payload)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].context["match_basis"], "exact_address")
        self.assertIn("entry 1 overlaps with Section 23 activity entry 1", results[0].message)

    def test_generates_flag_for_same_region_when_address_is_missing(self) -> None:
        generator = FlagGenerator()

        payload = {
            "residences": [
                {
                    "from_date": "2020-01-01",
                    "to_date": "2020-12-31",
                    "city": "Austin",
                    "state": "TX",
                    "country": "USA",
                }
            ],
            "drug_activity_locations": [
                {
                    "from_date": "2020-03-15",
                    "to_date": "2020-03-16",
                    "city": "Austin",
                    "state": "TX",
                    "country": "USA",
                    "location": "South Congress, Austin, TX",
                }
            ],
        }

        results = generator.generate(payload)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].context["match_basis"], "same_region")

    def test_ignores_matching_location_without_date_overlap(self) -> None:
        generator = FlagGenerator()

        payload = {
            "section_11": [
                {
                    "from_date": "2018-01-01",
                    "to_date": "2018-12-31",
                    "street1": "100 Pine St",
                    "city": "Seattle",
                    "state": "WA",
                    "country": "USA",
                }
            ],
            "section_23": [
                {
                    "from_date": "2019-02-01",
                    "to_date": "2019-02-15",
                    "street1": "100 Pine St",
                    "city": "Seattle",
                    "state": "WA",
                    "country": "USA",
                }
            ],
        }

        self.assertEqual(generator.generate(payload), [])

    def test_uses_location_term_fallback_for_free_form_locations(self) -> None:
        generator = FlagGenerator()

        payload = {
            "section_11": [
                {
                    "from_date": "2022-01-01",
                    "to_date": "2022-08-01",
                    "location": "Naval Base San Diego housing",
                }
            ],
            "section_23": [
                {
                    "from_date": "2022-05-10",
                    "to_date": "2022-05-11",
                    "location": "San Diego Naval Base parking lot",
                }
            ],
        }

        results = generator.generate(payload)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].context["match_basis"], "shared_location_terms")


if __name__ == "__main__":
    unittest.main()
