import unittest

from sf_validator.pdf_audit import audit_pdf


def build_simple_pdf(page_text: str) -> bytes:
    return build_multi_page_pdf([page_text])


def build_multi_page_pdf(page_texts: list[str]) -> bytes:
    objects = []

    def add_obj(body: str) -> None:
        objects.append(body.encode("latin-1"))

    add_obj("<< /Type /Catalog /Pages 2 0 R >>")
    page_object_numbers = []
    content_object_numbers = []
    next_object_number = 3

    for _ in page_texts:
        page_object_numbers.append(next_object_number)
        content_object_numbers.append(next_object_number + 1)
        next_object_number += 2

    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    add_obj(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_texts)} >>")

    for page_object_number, content_object_number, page_text in zip(page_object_numbers, content_object_numbers, page_texts):
        escaped = page_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        add_obj(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_object_number} 0 R /Resources << /Font << /F1 {next_object_number} 0 R >> >> >>"
        )
        stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1")
        add_obj(f"<< /Length {len(stream)} >>\nstream\n{stream.decode('latin-1')}\nendstream")

    add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode("latin-1"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    out.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("latin-1"))
    return bytes(out)


class PdfAuditTests(unittest.TestCase):
    def test_pdf_audit_returns_findings(self) -> None:
        pdf_bytes = build_simple_pdf("Section 11 Residence P.O. Box 44 Austin TX")
        result = audit_pdf(pdf_bytes, form_type="SF85")

        self.assertEqual(result["page_count"], 1)
        self.assertEqual(result["form_type"], "SF85")
        self.assertEqual(result["review_profile"]["name"], "Public Trust")
        self.assertEqual(result["findings"][0]["code"], "PDF_SECTION_11_PO_BOX")
        self.assertEqual(result["findings"][0]["subsection"], "11")
        self.assertEqual(result["findings"][0]["screening_protocol"], "Physical Address Verification")
        self.assertEqual(result["findings"][0]["section_title"], "Residence Activities")

    def test_section11_po_box_in_verifier_block_does_not_flag_residence_address(self) -> None:
        pdf_bytes = build_simple_pdf(
            "Section 11 Residence Activities 123 Main St Austin TX verifier P.O. Box 44 Austin TX"
        )

        result = audit_pdf(pdf_bytes, form_type="SF85")

        codes = [finding["code"] for finding in result["findings"]]
        self.assertNotIn("PDF_SECTION_11_PO_BOX", codes)

    def test_sf85_disables_sf86_ever_scan(self) -> None:
        pdf_bytes = build_simple_pdf("Section 21 Yes")

        result = audit_pdf(pdf_bytes, form_type="SF85")

        self.assertEqual(result["finding_count"], 0)

    def test_rejects_unsupported_form_type(self) -> None:
        pdf_bytes = build_simple_pdf("Section 11 Residence P.O. Box 44 Austin TX")

        with self.assertRaises(ValueError):
            audit_pdf(pdf_bytes, form_type="SF-89")

    def test_sf86_yes_without_supporting_detail_is_marked_incomplete(self) -> None:
        pdf_bytes = build_simple_pdf("Section 20C Foreign Travel Selected Yes")

        result = audit_pdf(pdf_bytes, form_type="SF86")

        codes = [finding["code"] for finding in result["findings"]]
        self.assertIn("PDF_EVER_FLAG_REVIEW_REQUIRED", codes)
        self.assertIn("PDF_EVER_FLAG_INCOMPLETE", codes)
        self.assertEqual(result["findings"][0]["section"], "20C")
        self.assertEqual(result["findings"][0]["section_title"], "Foreign Travel")
        self.assertIn("Review the entry", result["findings"][0]["message"])
        incomplete = next(f for f in result["findings"] if f["code"] == "PDF_EVER_FLAG_INCOMPLETE")
        self.assertIn("travel dates", incomplete["message"])

    def test_lettered_subsection_page_header_is_detected(self) -> None:
        pdf_bytes = build_simple_pdf("20C.1 Selected Yes")

        result = audit_pdf(pdf_bytes, form_type="SF86")

        self.assertEqual(result["findings"][0]["section"], "20C")
        self.assertEqual(result["findings"][0]["subsection"], "20C.1")

    def test_bare_page_number_is_not_used_as_subsection(self) -> None:
        pdf_bytes = build_simple_pdf(
            "5\nSection 10 Relatives Entry #1 Relative's Name Relationship Date of Birth Citizenship Address Country"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        self.assertEqual(result["findings"][0]["section"], "10")
        self.assertEqual(result["findings"][0]["subsection"], "10")
        self.assertEqual(result["findings"][0]["section_title"], "Relatives")

    def test_sf86_missing_selection_flags_incomplete_section(self) -> None:
        pdf_bytes = build_simple_pdf("Section 24 Use of Alcohol Yes No")

        result = audit_pdf(pdf_bytes, form_type="SF86")

        self.assertEqual(result["finding_count"], 0)

    def test_sf86_missing_selection_requires_user_detail_not_just_labels(self) -> None:
        pdf_bytes = build_simple_pdf(
            "Section 24 Use of Alcohol Yes No 2019-01-01 counseling issue"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        self.assertEqual(result["finding_count"], 1)
        self.assertEqual(result["findings"][0]["code"], "PDF_EVER_FLAG_SELECTION_MISSING")
        self.assertEqual(result["findings"][0]["section"], "24")
        self.assertEqual(result["findings"][0]["section_title"], "Use of Alcohol")

    def test_section23_followup_page_is_classified_and_flagged_incomplete(self) -> None:
        pdf_bytes = build_simple_pdf(
            "23.1 Entry #2 Provide the type of drug or controlled substance. "
            "Provide an estimate of the month and year of first use. "
            "Provide an estimate of the month and year of most recent use. "
            "Provide nature of use, frequency, and number of times used. "
            "Section 23 - Illegal Use of Drugs and Drug Activity"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        codes = [finding["code"] for finding in result["findings"]]
        self.assertIn("PDF_SECTION_23_REVIEW_REQUIRED", codes)
        self.assertIn("PDF_SECTION_23_INCOMPLETE", codes)
        self.assertEqual(result["findings"][0]["section"], "23")
        self.assertEqual(result["findings"][0]["subsection"], "23.1")
        self.assertEqual(result["findings"][0]["entry_number"], 2)
        self.assertEqual(result["findings"][0]["screening_protocol"], "Drug Use Disclosure Review")
        self.assertEqual(result["findings"][0]["section_title"], "Illegal Use of Drugs and Drug Activity")

    def test_section23_prompt_only_page_does_not_count_as_completed_detail(self) -> None:
        pdf_bytes = build_simple_pdf(
            "23.1 Entry #2 Provide the type of drug or controlled substance. "
            "Provide an estimate of the month and year of first use. "
            "Provide an estimate of the month and year of most recent use. "
            "Provide nature of use, frequency, and number of times used. "
            "Was your use while possessing a security clearance? YES NO "
            "Do you intend to use this drug or controlled substance in the future? YES NO "
            "Provide explanation of why you intend or do not intend to use this drug or controlled substance in the future. "
            "Section 23 - Illegal Use of Drugs and Drug Activity"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        entry_findings = [finding for finding in result["findings"] if finding["entry_number"] == 2]
        codes = [finding["code"] for finding in entry_findings]
        self.assertIn("PDF_SECTION_23_INCOMPLETE", codes)

    def test_section23_multiple_entries_are_screened_independently(self) -> None:
        pdf_bytes = build_simple_pdf(
            "23.2 Entry #1 Provide the type of drug or controlled substance. "
            "Provide an estimate of the month and year of first use. "
            "Provide nature of use, frequency, and number of times used. "
            "Entry #2 Provide the type of drug or controlled substance. "
            "Provide an estimate of the month and year of first use. "
            "Provide nature of use, frequency, and number of times used. "
            "Section 23 - Illegal Use of Drugs and Drug Activity"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        entry_numbers = [finding["entry_number"] for finding in result["findings"] if finding["code"] == "PDF_SECTION_23_REVIEW_REQUIRED"]
        self.assertEqual(entry_numbers, [1, 2])
        subsections = {finding["subsection"] for finding in result["findings"]}
        self.assertEqual(subsections, {"23.2"})

    def test_section23_single_detail_signal_still_flags_incomplete(self) -> None:
        pdf_bytes = build_simple_pdf(
            "23.2 Entry #1 Marijuana Section 23 - Illegal Use of Drugs and Drug Activity "
            "Provide the type of drug or controlled substance. "
            "Provide an estimate of the month and year of first use. "
            "Provide nature of use, frequency, and number of times used."
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        entry_findings = [finding for finding in result["findings"] if finding["entry_number"] == 1]
        codes = [finding["code"] for finding in entry_findings]
        self.assertIn("PDF_SECTION_23_INCOMPLETE", codes)
        incomplete = next(f for f in entry_findings if f["code"] == "PDF_SECTION_23_INCOMPLETE")
        self.assertIn("drug type", incomplete["message"])

    def test_section20c_prompt_only_page_still_flags_incomplete(self) -> None:
        pdf_bytes = build_simple_pdf(
            "Section 20C Foreign Travel Selected Yes Country From To Purpose Provide explanation"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        codes = [finding["code"] for finding in result["findings"]]
        self.assertIn("PDF_EVER_FLAG_REVIEW_REQUIRED", codes)
        self.assertIn("PDF_EVER_FLAG_INCOMPLETE", codes)

    def test_early_section_blank_page_is_flagged(self) -> None:
        pdf_bytes = build_simple_pdf(
            "Section 1 Identifying Information Social Security Number Date of Birth Place of Birth Citizenship"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        self.assertEqual(result["findings"][0]["code"], "PDF_SECTION_DATA_MISSING")
        self.assertEqual(result["findings"][0]["section"], "1")
        self.assertEqual(result["findings"][0]["section_title"], "Identifying Information")

    def test_early_section_with_iso_dates_is_not_marked_blank(self) -> None:
        pdf_bytes = build_simple_pdf(
            "Section 3 Places of Residence John Smith 2018-01-01 2020-12-31 Austin Texas USA"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        codes = [finding["code"] for finding in result["findings"]]
        self.assertNotIn("PDF_SECTION_DATA_MISSING", codes)

    def test_section12_blank_page_is_flagged(self) -> None:
        pdf_bytes = build_simple_pdf(
            "Section 12 Education Activities School Name From To Degree/Diploma Address"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        self.assertEqual(result["findings"][0]["code"], "PDF_SECTION_DATA_MISSING")
        self.assertEqual(result["findings"][0]["section"], "12")
        self.assertEqual(result["findings"][0]["section_title"], "Where You Went To School")

    def test_section19_blank_page_is_flagged(self) -> None:
        pdf_bytes = build_simple_pdf(
            "Section 19 Foreign Contacts Name Relationship Country Frequency Address"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        self.assertEqual(result["findings"][0]["code"], "PDF_SECTION_DATA_MISSING")
        self.assertEqual(result["findings"][0]["section"], "19")
        self.assertEqual(result["findings"][0]["section_title"], "Foreign Contacts")

    def test_section12_can_be_inferred_without_literal_section_number(self) -> None:
        pdf_bytes = build_simple_pdf(
            "Where You Went To School School Name From To Degree/Diploma Address"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        self.assertEqual(result["findings"][0]["code"], "PDF_SECTION_DATA_MISSING")
        self.assertEqual(result["findings"][0]["section"], "12")
        self.assertEqual(result["findings"][0]["section_title"], "Where You Went To School")

    def test_section13_can_be_inferred_without_literal_section_number(self) -> None:
        pdf_bytes = build_simple_pdf(
            "Employment Activities Employer Name From To Supervisor Position Title Reason for Leaving"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        self.assertEqual(result["findings"][0]["code"], "PDF_SECTION_DATA_MISSING")
        self.assertEqual(result["findings"][0]["section"], "13")
        self.assertEqual(result["findings"][0]["section_title"], "Employment Activities")

    def test_section14_can_be_inferred_without_literal_section_number(self) -> None:
        pdf_bytes = build_simple_pdf(
            "Selective Service Record Have you registered with the Selective Service System Registration Number"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        self.assertEqual(result["findings"][0]["code"], "PDF_SECTION_DATA_MISSING")
        self.assertEqual(result["findings"][0]["section"], "14")
        self.assertEqual(result["findings"][0]["section_title"], "Selective Service Record")

    def test_section8_can_be_inferred_without_literal_section_number(self) -> None:
        pdf_bytes = build_simple_pdf(
            "Foreign Contacts and Activities Name Country Relationship Frequency Address"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        self.assertEqual(result["findings"][0]["code"], "PDF_SECTION_DATA_MISSING")
        self.assertEqual(result["findings"][0]["section"], "8")
        self.assertEqual(result["findings"][0]["section_title"], "Foreign Contacts and Activities")

    def test_section10_can_be_inferred_without_literal_section_number(self) -> None:
        pdf_bytes = build_simple_pdf(
            "Relatives Relative's Name Relationship Date of Birth Citizenship Address Country"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        self.assertEqual(result["findings"][0]["code"], "PDF_SECTION_DATA_MISSING")
        self.assertEqual(result["findings"][0]["section"], "10")
        self.assertEqual(result["findings"][0]["section_title"], "Relatives")

    def test_cover_page_text_does_not_hallucinate_section29(self) -> None:
        pdf_bytes = build_simple_pdf(
            "QUESTIONNAIRE FOR NATIONAL SECURITY POSITIONS Standard Form 86 Revised November 2016 "
            "U.S. Office of Personnel Management Enter your Social Security Number before going to the next page"
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        self.assertEqual(result["finding_count"], 0)

    def test_unknown_page_does_not_inherit_previous_section_without_evidence(self) -> None:
        pdf_bytes = build_multi_page_pdf(
            [
                "Section 11 Residence Activities 123 Main St Austin TX",
                "Generic page with no section cues at all",
            ]
        )

        result = audit_pdf(pdf_bytes, form_type="SF85")

        self.assertEqual(result["finding_count"], 0)

    def test_sequence_gap_between_main_sections_is_flagged(self) -> None:
        pdf_bytes = build_multi_page_pdf(
            [
                "Section 5 Employment Activities Employer Name From To Supervisor",
                "Section 20 Psychological and Emotional Health Selected Yes",
            ]
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        gap_sections = [finding["section"] for finding in result["findings"] if finding["code"] == "PDF_SECTION_SEQUENCE_GAP"]
        self.assertIn("6", gap_sections)
        self.assertIn("19", gap_sections)
        self.assertIn("1", gap_sections)
        self.assertIn("29", gap_sections)

    def test_sequence_gap_uses_highest_seen_section_when_page_regresses(self) -> None:
        pdf_bytes = build_multi_page_pdf(
            [
                "Section 1 Identifying Information Social Security Number Date of Birth Place of Birth",
                "Section 2 Citizenship Citizenship Status Country of Citizenship",
                "Section 3 Places of Residence Street Address City State Zip Code Country",
                "Section 4 Education School Name From To Degree/Diploma Address",
                "Section 5 Employment Activities Employer Name From To Supervisor",
                "Section 6 People Who Know You Well Name Relationship From To Address",
                "Section 7 Military History Branch From To Service Number Rank Type of Discharge",
                "Section 5 Employment Activities Employer Name From To Supervisor",
                "Section 11 Residence Activities 123 Main St Austin TX",
            ]
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        gap_sections = [finding["section"] for finding in result["findings"] if finding["code"] == "PDF_SECTION_SEQUENCE_GAP"]
        self.assertIn("8", gap_sections)
        self.assertIn("9", gap_sections)
        self.assertIn("10", gap_sections)
        self.assertNotIn("6", gap_sections)
        self.assertNotIn("7", gap_sections)

    def test_sequence_gap_into_lettered_subsection_is_flagged(self) -> None:
        pdf_bytes = build_multi_page_pdf(
            [
                "Section 11 Residence Activities 123 Main St Austin TX",
                "20A Counseling or Treatment Yes No",
            ]
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        gap_sections = [finding["section"] for finding in result["findings"] if finding["code"] == "PDF_SECTION_SEQUENCE_GAP"]
        self.assertIn("12", gap_sections)
        self.assertIn("19", gap_sections)

    def test_findings_are_sorted_in_section_order(self) -> None:
        pdf_bytes = build_multi_page_pdf(
            [
                "Section 5 Employment Activities Employer Name From To Supervisor",
                "Section 20 Psychological and Emotional Health Selected Yes",
            ]
        )

        result = audit_pdf(pdf_bytes, form_type="SF86")

        sections = [finding["section"] for finding in result["findings"][:5]]
        self.assertEqual(sections[:4], ["1", "2", "3", "4"])
