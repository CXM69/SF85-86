import contextlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from sf_validator.cli import main, run_validation


class CliTests(unittest.TestCase):
    def test_run_validation_returns_flags_and_export_summary(self) -> None:
        payload = {
            "section_11": [{"street1": "P.O. Box 5", "city": "Austin", "state": "TX"}],
            "section_21": {"illegal_drug_use": "Yes"},
        }

        result = run_validation(payload)

        self.assertIn("flags", result)
        self.assertIn("export_summary", result)
        self.assertEqual(result["export_summary"]["review_required_count"], 1)

    def test_main_reads_file_and_prints_json(self) -> None:
        payload = {
            "section_13": [
                {"employment_type": "Unemployed", "from_date": "2020-01-01", "to_date": "2020-03-01"}
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "input.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main([str(path)])

        self.assertEqual(code, 0)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["flags"][0]["code"], "SECTION_13_UNEMPLOYED_NO_VERIFIER")

    def test_main_rejects_invalid_schema(self) -> None:
        payload = {"section_11": {"city": "Austin"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "input.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main([str(path)])

        self.assertEqual(code, 1)
        self.assertIn("Validation error:", stderr.getvalue())
