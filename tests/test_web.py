import unittest
from pathlib import Path

from sf_validator.web import _clear_bytes, _index_page, _privacy_headers, handle_request


class WebTests(unittest.TestCase):
    def tearDown(self) -> None:
        triage_path = Path("/Users/mountainman/SF85-86/triage_report.json")
        if triage_path.exists():
            triage_path.unlink()

    def test_health_endpoint(self) -> None:
        status, body = handle_request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")

    def test_index_page_renders(self) -> None:
        html = _index_page()
        self.assertIn("SF-85 / SF-86 Validator", html)
        self.assertIn("SF-85 Public Trust", html)
        self.assertIn("SF-86 National Security", html)
        self.assertIn("Validate", html)
        self.assertIn("Clear", html)
        self.assertIn("Review Required", html)
        self.assertIn("section_title", html)
        self.assertIn("screening_protocol", html)
        self.assertNotIn("rawOutput", html)
        self.assertIn("AbortController", html)
        self.assertIn("activeAuditId", html)
        self.assertIn("randomUUID", html)
        self.assertIn("/clear-session", html)
        self.assertIn("sendBeacon", html)
        self.assertIn("releaseSelectedPdfFile", html)
        self.assertIn("new Uint8Array(pdfBuffer).fill(0)", html)

    def test_privacy_headers_disable_caching(self) -> None:
        headers = _privacy_headers("application/json", 42)
        self.assertEqual(headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0, private")
        self.assertEqual(headers["Pragma"], "no-cache")
        self.assertEqual(headers["Expires"], "0")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
        self.assertNotIn("Clear-Site-Data", headers)

    def test_clear_session_headers_clear_browser_storage(self) -> None:
        headers = _privacy_headers("application/json", 20, clear_site_data=True)
        self.assertEqual(headers["Clear-Site-Data"], '"cache", "storage"')

    def test_clear_bytes_zeroes_request_buffer(self) -> None:
        buffer = bytearray(b"sensitive-pdf-bytes")
        _clear_bytes(buffer)
        self.assertEqual(buffer, bytearray(len(buffer)))

    def test_validate_endpoint(self) -> None:
        status, body = handle_request("POST", "/validate", b'{"section_21": {"illegal_drug_use": "Yes"}}')
        self.assertEqual(status, 200)
        self.assertEqual(body["export_summary"]["review_required_count"], 1)

    def test_validate_endpoint_rejects_invalid_schema(self) -> None:
        status, body = handle_request("POST", "/validate", b'{"section_11": {"city": "Austin"}}')
        self.assertEqual(status, 400)
        self.assertIn("Validation error:", body["error"])

    def test_validate_pdf_endpoint(self) -> None:
        from tests.test_pdf_audit import build_simple_pdf

        status, body = handle_request(
            "POST",
            "/validate-pdf",
            build_simple_pdf("Section 11 Residence P.O. Box 8"),
            headers={"X-Form-Type": "SF85", "X-Session-Id": "session-a"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["form_type"], "SF85")
        self.assertEqual(body["findings"][0]["code"], "PDF_SECTION_11_PO_BOX")
        self.assertIn("ledger_proof", body)
        self.assertNotIn("findings", body["ledger_proof"])
        self.assertEqual(len(body["ledger_proof"]["section_hashes"]), 29)
        self.assertFalse(Path("/Users/mountainman/SF85-86/triage_report.json").exists())

    def test_validate_pdf_endpoint_honors_lowercase_form_type_header(self) -> None:
        from tests.test_pdf_audit import build_simple_pdf

        status, body = handle_request(
            "POST",
            "/validate-pdf",
            build_simple_pdf("Section 21 Yes"),
            headers={"x-form-type": "sf85"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["form_type"], "SF85")
        self.assertEqual(body["finding_count"], 0)

    def test_validate_pdf_endpoint_honors_underscore_form_type_header(self) -> None:
        from tests.test_pdf_audit import build_simple_pdf

        status, body = handle_request(
            "POST",
            "/validate-pdf",
            build_simple_pdf("Section 21 Yes"),
            headers={"x_form_type": "sf85"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["form_type"], "SF85")
        self.assertEqual(body["finding_count"], 0)

    def test_clear_session_endpoint_rotates_ledger_key(self) -> None:
        from tests.test_pdf_audit import build_simple_pdf

        status, body = handle_request(
            "POST",
            "/validate-pdf",
            build_simple_pdf("Section 11 Residence P.O. Box 8"),
            headers={"X-Form-Type": "SF85", "X-Session-Id": "session-b"},
        )
        self.assertEqual(status, 200)
        first_fingerprint = body["ledger_proof"]["key_fingerprint"]

        status, body = handle_request("POST", "/clear-session", headers={"X-Session-Id": "session-b"})
        self.assertEqual(status, 200)
        self.assertTrue(body["cleared"])

        status, body = handle_request(
            "POST",
            "/validate-pdf",
            build_simple_pdf("Section 11 Residence P.O. Box 8"),
            headers={"X-Form-Type": "SF85", "X-Session-Id": "session-b"},
        )
        self.assertEqual(status, 200)
        self.assertNotEqual(first_fingerprint, body["ledger_proof"]["key_fingerprint"])

    def test_clear_session_endpoint_accepts_beacon_body(self) -> None:
        from tests.test_pdf_audit import build_simple_pdf

        status, body = handle_request(
            "POST",
            "/validate-pdf",
            build_simple_pdf("Section 11 Residence P.O. Box 8"),
            headers={"X-Form-Type": "SF85", "X-Session-Id": "session-c"},
        )
        self.assertEqual(status, 200)
        first_fingerprint = body["ledger_proof"]["key_fingerprint"]

        status, body = handle_request("POST", "/clear-session", b"session-c")
        self.assertEqual(status, 200)
        self.assertTrue(body["cleared"])

        status, body = handle_request(
            "POST",
            "/validate-pdf",
            build_simple_pdf("Section 11 Residence P.O. Box 8"),
            headers={"X-Form-Type": "SF85", "X-Session-Id": "session-c"},
        )
        self.assertEqual(status, 200)
        self.assertNotEqual(first_fingerprint, body["ledger_proof"]["key_fingerprint"])
