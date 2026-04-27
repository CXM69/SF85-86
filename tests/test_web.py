import unittest

from sf_validator.web import handle_request


class WebTests(unittest.TestCase):
    def test_health_endpoint(self) -> None:
        status, body = handle_request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")

    def test_validate_endpoint(self) -> None:
        status, body = handle_request("POST", "/validate", b'{"section_21": {"illegal_drug_use": "Yes"}}')
        self.assertEqual(status, 200)
        self.assertEqual(body["export_summary"]["review_required_count"], 1)

    def test_validate_endpoint_rejects_invalid_schema(self) -> None:
        status, body = handle_request("POST", "/validate", b'{"section_11": {"city": "Austin"}}')
        self.assertEqual(status, 400)
        self.assertIn("Validation error:", body["error"])
