import unittest

from sf_validator.ledger import (
    SECTION_IDS,
    build_ledger_payload,
    clear_all_session_material,
    clear_session_material,
)


class LedgerTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_session_material("test-session")

    def test_ledger_payload_contains_hashes_only(self) -> None:
        report = {
            "form_type": "SF86",
            "finding_count": 1,
            "findings": [
                {
                    "code": "PDF_SECTION_11_PO_BOX",
                    "section": "11",
                    "subsection": "11",
                    "section_title": "Residence Activities",
                    "entry_number": 1,
                    "screening_protocol": "Physical Address Verification",
                    "page": 10,
                    "message": "Potential Section 11 issue: P.O. Box found where a physical address is expected.",
                    "snippet": "Section 11 Residence Activities Entry #1 P.O. Box 12",
                }
            ],
        }

        payload = build_ledger_payload(report, "test-session")

        self.assertEqual(payload["algorithm"], "sha256+hmac-sha256")
        self.assertEqual(set(payload["section_hashes"].keys()), set(SECTION_IDS))
        self.assertNotIn("findings", payload)
        self.assertNotIn("snippet", payload)
        self.assertNotIn("message", payload)
        self.assertRegex(payload["report_hash_sha256"], r"^[a-f0-9]{64}$")
        self.assertRegex(payload["signature"], r"^[a-f0-9]{64}$")

    def test_clear_session_material_rotates_signing_state(self) -> None:
        report = {"form_type": "SF85", "finding_count": 0, "findings": []}

        first_payload = build_ledger_payload(report, "test-session")
        cleared = clear_session_material("test-session")
        second_payload = build_ledger_payload(report, "test-session")

        self.assertTrue(cleared)
        self.assertNotEqual(first_payload["key_fingerprint"], second_payload["key_fingerprint"])
        self.assertNotEqual(first_payload["section_hashes"], second_payload["section_hashes"])

    def test_clear_all_session_material_wipes_store(self) -> None:
        report = {"form_type": "SF85", "finding_count": 0, "findings": []}

        first_payload = build_ledger_payload(report, "test-session")
        build_ledger_payload(report, "other-session")
        cleared_count = clear_all_session_material()
        second_payload = build_ledger_payload(report, "test-session")

        self.assertEqual(cleared_count, 2)
        self.assertNotEqual(first_payload["key_fingerprint"], second_payload["key_fingerprint"])
