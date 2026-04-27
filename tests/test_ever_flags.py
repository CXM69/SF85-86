import unittest

from sf_validator import EverFlagScanner


class EverFlagScannerTests(unittest.TestCase):
    def test_flags_yes_answers(self) -> None:
        scanner = EverFlagScanner()
        payload = {"section_21": {"illegal_drug_use": "Yes"}}

        results = scanner.generate(payload)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].export_tag, "Review Required")
