import unittest

from sf_validator.form_schema import SECTION_SCHEMAS, get_section_schema


class FormSchemaTests(unittest.TestCase):
    def test_has_canonical_sections_1_through_29(self) -> None:
        for section in [str(n) for n in range(1, 30)]:
            schema = get_section_schema(section)
            self.assertNotEqual(schema.title, "Review Item")

    def test_has_lettered_sf86_disclosure_subsections(self) -> None:
        for section in ("20A", "20B", "20C", "20D", "20E"):
            schema = get_section_schema(section)
            self.assertTrue(schema.answer_gated)
            self.assertTrue(schema.entry_based)
            self.assertGreaterEqual(schema.detail_signal_min, 2)

    def test_section23_uses_stricter_drug_context_requirements(self) -> None:
        schema = get_section_schema("23")
        self.assertTrue(schema.require_drug_context)
        self.assertEqual(schema.review_protocol, "Drug Use Disclosure Review")
        self.assertEqual(schema.completeness_protocol, "Drug Use Follow-Up Completeness Review")
        self.assertIn("drug type", schema.expected_fields)

    def test_answer_gated_sections_define_expected_fields(self) -> None:
        for section_id, schema in SECTION_SCHEMAS.items():
            if schema.answer_gated:
                self.assertTrue(schema.expected_fields, section_id)
                self.assertTrue(schema.field_label_anchors, section_id)

    def test_unknown_section_falls_back_safely(self) -> None:
        schema = get_section_schema("99")
        self.assertEqual(schema.title, "Review Item")

    def test_section23_includes_real_form_label_anchors(self) -> None:
        schema = get_section_schema("23")
        self.assertIn("provide the type of drug or controlled substance", schema.field_label_anchors)
        self.assertIn("provide nature of use, frequency, and number of times used", schema.field_label_anchors)

    def test_sections_12_through_19_are_in_blank_review_path(self) -> None:
        for section in [str(n) for n in range(12, 20)]:
            schema = get_section_schema(section)
            self.assertTrue(schema.blank_review_enabled, section)
