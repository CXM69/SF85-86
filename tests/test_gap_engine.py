import unittest

from sf_validator import GapEngine


class GapEngineTests(unittest.TestCase):
    def test_flags_gap_over_30_days(self) -> None:
        engine = GapEngine()
        payload = {
            "section_11": [
                {"from_date": "2020-01-01", "to_date": "2020-03-01", "city": "Austin", "state": "TX"},
                {"from_date": "2020-05-15", "to_date": "2020-12-01", "city": "Austin", "state": "TX"},
            ]
        }

        results = engine.generate(payload)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].code, "TIMELINE_GAP_OVER_30_DAYS")

    def test_flags_unexplained_geo_overlap(self) -> None:
        engine = GapEngine()
        payload = {
            "section_11": [
                {"from_date": "2020-01-01", "to_date": "2020-12-01", "city": "Austin", "state": "TX"}
            ],
            "section_13": [
                {"from_date": "2020-03-01", "to_date": "2020-06-01", "city": "Denver", "state": "CO"}
            ],
        }

        results = engine.generate(payload)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].code, "TIMELINE_UNEXPLAINED_GEO_OVERLAP")
