"""Canonical section and entry schema for SF-85/SF-86 review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


@dataclass(frozen=True)
class SectionSchema:
    section_id: str
    title: str
    cue_phrases: Tuple[str, ...] = ()
    expected_fields: Tuple[str, ...] = ()
    field_label_anchors: Tuple[str, ...] = ()
    blank_review_enabled: bool = False
    entry_based: bool = False
    answer_gated: bool = False
    detail_signal_min: int = 1
    require_drug_context: bool = False
    review_protocol: str = "Section Review"
    completeness_protocol: str = "Section Completeness Review"
    missing_selection_protocol: str = "Selection Review"


def _schema(
    section_id: str,
    title: str,
    cue_phrases: Iterable[str] = (),
    expected_fields: Iterable[str] = (),
    field_label_anchors: Iterable[str] = (),
    *,
    blank_review_enabled: bool = False,
    entry_based: bool = False,
    answer_gated: bool = False,
    detail_signal_min: int = 1,
    require_drug_context: bool = False,
    review_protocol: str = "Section Review",
    completeness_protocol: str = "Section Completeness Review",
    missing_selection_protocol: str = "Selection Review",
) -> SectionSchema:
    return SectionSchema(
        section_id=section_id,
        title=title,
        cue_phrases=tuple(cue_phrases),
        expected_fields=tuple(expected_fields),
        field_label_anchors=tuple(field_label_anchors),
        blank_review_enabled=blank_review_enabled,
        entry_based=entry_based,
        answer_gated=answer_gated,
        detail_signal_min=detail_signal_min,
        require_drug_context=require_drug_context,
        review_protocol=review_protocol,
        completeness_protocol=completeness_protocol,
        missing_selection_protocol=missing_selection_protocol,
    )


SECTION_SCHEMAS: Dict[str, SectionSchema] = {
    "1": _schema(
        "1",
        "Identifying Information",
        ("identifying information", "social security number", "date of birth", "place of birth"),
        ("full name", "social security number", "date of birth", "place of birth"),
        ("last name", "first name", "middle name", "social security number", "date of birth", "place of birth"),
        blank_review_enabled=True,
        review_protocol="Identity Review",
    ),
    "2": _schema(
        "2",
        "Citizenship",
        ("citizenship", "born", "naturalized", "documentation"),
        ("citizenship status", "supporting documentation", "country of citizenship"),
        ("citizenship status", "born in the u.s.", "naturalized", "documentation", "country of citizenship"),
        blank_review_enabled=True,
        review_protocol="Citizenship Review",
    ),
    "3": _schema(
        "3",
        "Places of Residence",
        ("places of residence", "residence", "address", "from", "to"),
        ("from date", "to date", "physical address", "city/state/country"),
        ("from", "to", "street address", "city", "state", "zip code", "country"),
        blank_review_enabled=True,
        entry_based=True,
        review_protocol="Residence History Review",
    ),
    "4": _schema(
        "4",
        "Education",
        ("education", "school", "degree", "diploma", "attendance"),
        ("school name", "attendance dates", "degree or diploma", "location"),
        ("school name", "from", "to", "degree/diploma", "city", "state", "country"),
        blank_review_enabled=True,
        entry_based=True,
        review_protocol="Education History Review",
    ),
    "5": _schema(
        "5",
        "Employment Activities",
        ("employment", "employer", "supervisor", "from", "to"),
        ("employer name", "employment dates", "supervisor", "location"),
        ("employer name", "from", "to", "supervisor", "address", "telephone number", "position title"),
        blank_review_enabled=True,
        entry_based=True,
        review_protocol="Employment History Review",
    ),
    "6": _schema(
        "6",
        "People Who Know You Well",
        ("people who know you well", "reference", "known you", "contact"),
        ("reference name", "relationship", "years known", "contact information"),
        ("name", "relationship", "from", "to", "address", "telephone number", "email address"),
        blank_review_enabled=True,
        entry_based=True,
        review_protocol="Reference Review",
    ),
    "7": _schema(
        "7",
        "Military History",
        ("military", "service", "branch", "discharge"),
        ("branch", "service dates", "service number", "discharge status"),
        ("branch", "from", "to", "service number", "rank", "type of discharge"),
        blank_review_enabled=True,
        entry_based=True,
        review_protocol="Military History Review",
    ),
    "8": _schema(
        "8",
        "Foreign Contacts and Activities",
        ("foreign contacts", "foreign", "country", "citizenship"),
        ("contact name", "country", "relationship", "dates or frequency"),
        ("name", "country", "relationship", "frequency", "address", "telephone number"),
        blank_review_enabled=True,
        entry_based=True,
        review_protocol="Foreign Contact Review",
    ),
    "9": _schema(
        "9",
        "Marital Status",
        ("marital status", "spouse", "widowed", "divorced"),
        ("current marital status", "spouse or former spouse details", "dates"),
        ("current marital status", "spouse's name", "date married", "date divorced", "date widowed"),
        blank_review_enabled=True,
        review_protocol="Marital Status Review",
    ),
    "10": _schema(
        "10",
        "Relatives",
        ("relatives", "mother", "father", "relative", "birth"),
        ("relative name", "relationship", "date of birth", "citizenship or location"),
        ("relative's name", "relationship", "date of birth", "citizenship", "address", "country"),
        blank_review_enabled=True,
        entry_based=True,
        review_protocol="Relative Review",
    ),
    "11": _schema("11", "Residence Activities", ("residence", "address", "apo", "fpo"), ("physical address", "dates", "location", "verifier"), ("street address", "city", "state", "zip code", "country", "verifier"), entry_based=True, review_protocol="Physical Address Verification"),
    "12": _schema(
        "12",
        "Where You Went To School",
        (
            "where you went to school",
            "education activities",
            "education",
            "school",
            "degree",
            "diploma",
            "attendance",
        ),
        ("school", "dates", "degree", "location"),
        (
            "where you went to school",
            "school name",
            "from",
            "to",
            "degree/diploma",
            "address",
            "city",
            "state",
            "country",
        ),
        blank_review_enabled=True,
        entry_based=True,
        review_protocol="Education Timeline Review",
        completeness_protocol="Education Completeness Review",
    ),
    "13": _schema(
        "13",
        "Employment Activities",
        (
            "employment activities",
            "employment record",
            "employment",
            "military",
            "unemployed",
            "employer",
            "supervisor",
            "reason for leaving",
        ),
        ("employer", "dates", "supervisor or verifier", "location"),
        (
            "employment activities",
            "employer name",
            "from",
            "to",
            "supervisor",
            "rank",
            "verifier",
            "address",
            "reason for leaving",
            "position title",
        ),
        blank_review_enabled=True,
        entry_based=True,
        review_protocol="Employment Verifier Review",
        completeness_protocol="Employment Completeness Review",
    ),
    "14": _schema(
        "14",
        "Selective Service Record",
        (
            "selective service record",
            "selective service",
            "registration number",
            "registered with the selective service system",
            "born after december 31, 1959",
        ),
        expected_fields=("registration status", "registration number or explanation"),
        field_label_anchors=(
            "selective service record",
            "have you registered with the selective service system",
            "registration number",
            "born after december 31, 1959",
            "explanation",
        ),
        blank_review_enabled=True,
        review_protocol="Selective Service Review",
        completeness_protocol="Selective Service Completeness Review",
    ),
    "15": _schema("15", "Military Record", ("military record", "branch", "service", "discharge"), expected_fields=("branch", "dates", "discharge information"), field_label_anchors=("branch", "from", "to", "service number", "type of discharge"), blank_review_enabled=True, entry_based=True, review_protocol="Military Record Review", completeness_protocol="Military Record Completeness Review"),
    "16": _schema("16", "People Who Know You Well", ("people who know you well", "reference", "relationship", "telephone"), expected_fields=("name", "relationship", "dates known", "contact information"), field_label_anchors=("name", "relationship", "from", "to", "telephone number", "email address"), blank_review_enabled=True, entry_based=True, review_protocol="Reference Review", completeness_protocol="Reference Completeness Review"),
    "17": _schema("17", "Marital / Cohabitant Status", ("marital", "cohabitant", "spouse", "divorced"), expected_fields=("status", "name", "dates", "location"), field_label_anchors=("current marital status", "cohabitant", "date married", "date divorced", "address"), blank_review_enabled=True, review_protocol="Marital Status Review", completeness_protocol="Marital Status Completeness Review"),
    "18": _schema("18", "Relatives", ("relatives", "mother", "father", "citizenship", "address"), expected_fields=("name", "relationship", "citizenship", "location"), field_label_anchors=("name", "relationship", "citizenship", "date of birth", "address"), blank_review_enabled=True, entry_based=True, review_protocol="Relative Review", completeness_protocol="Relative Completeness Review"),
    "19": _schema("19", "Foreign Contacts", ("foreign contacts", "foreign", "country", "relationship", "frequency"), expected_fields=("name", "relationship", "country", "dates or frequency"), field_label_anchors=("name", "relationship", "country", "frequency", "address"), blank_review_enabled=True, entry_based=True, review_protocol="Foreign Contact Review", completeness_protocol="Foreign Contact Completeness Review"),
    "20": _schema("20", "Psychological and Emotional Health", expected_fields=("provider or facility", "dates", "narrative explanation"), field_label_anchors=("yes", "no", "provide explanation", "from", "to", "provider", "facility"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
    "20A": _schema("20A", "Counseling or Treatment", expected_fields=("provider", "dates", "explanation"), field_label_anchors=("provide the name of the counselor", "provide the dates", "provide explanation", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
    "20B": _schema("20B", "Hospitalization", expected_fields=("facility", "dates", "reason or explanation"), field_label_anchors=("facility", "from", "to", "provide explanation", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
    "20C": _schema("20C", "Foreign Travel", expected_fields=("travel dates", "country or location", "purpose or explanation"), field_label_anchors=("country", "from", "to", "purpose", "provide explanation", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
    "20D": _schema("20D", "Illegal Use of Controlled Substances While Cleared", expected_fields=("substance", "dates", "explanation"), field_label_anchors=("substance", "from", "to", "provide explanation", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
    "20E": _schema("20E", "Other Mental Health Information", expected_fields=("dates", "authority or provider", "explanation"), field_label_anchors=("from", "to", "provider", "authority", "provide explanation", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
    "21": _schema("21", "Foreign Contacts", expected_fields=("contact name", "country", "relationship", "dates or frequency"), field_label_anchors=("name", "country", "relationship", "frequency", "provide explanation", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
    "22": _schema("22", "Police Record", expected_fields=("offense or issue", "date", "location or court", "disposition"), field_label_anchors=("charge", "date", "court", "disposition", "provide explanation", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
    "23": _schema("23", "Illegal Use of Drugs and Drug Activity", expected_fields=("drug type", "first and most recent use dates", "frequency or number of times", "future-use explanation"), field_label_anchors=("provide the type of drug or controlled substance", "provide an estimate of the month and year of first use", "provide an estimate of the month and year of most recent use", "provide nature of use, frequency, and number of times used", "was your use while possessing a security clearance", "do you intend to use this drug or controlled substance in the future", "provide explanation of why you intend or do not intend to use this drug or controlled substance in the future", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, require_drug_context=True, review_protocol="Drug Use Disclosure Review", completeness_protocol="Drug Use Follow-Up Completeness Review", missing_selection_protocol="Drug Use Disclosure Selection Review"),
    "24": _schema("24", "Use of Alcohol", expected_fields=("incident or concern", "date", "treatment or counseling detail", "explanation"), field_label_anchors=("incident", "date", "treatment", "counseling", "provide explanation", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
    "25": _schema("25", "Investigations and Clearance Record", expected_fields=("agency or investigation", "date", "status or outcome", "explanation"), field_label_anchors=("agency", "investigation", "date", "outcome", "provide explanation", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
    "26": _schema("26", "Financial Record", expected_fields=("debt or issue", "amount", "date", "resolution or explanation"), field_label_anchors=("creditor", "amount", "date", "resolution", "provide explanation", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
    "27": _schema("27", "Use of Information Technology Systems", expected_fields=("system misuse detail", "date", "authority or employer", "explanation"), field_label_anchors=("date", "system", "employer", "provide explanation", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
    "28": _schema("28", "Handling Protected Information", expected_fields=("information type", "date", "incident detail", "resolution or explanation"), field_label_anchors=("date", "information", "incident", "resolution", "provide explanation", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
    "29": _schema("29", "Associations", expected_fields=("organization or association", "dates", "role or activity", "explanation"), field_label_anchors=("organization", "association", "from", "to", "role", "provide explanation", "yes", "no"), entry_based=True, answer_gated=True, detail_signal_min=2, review_protocol="SF-86 Disclosure Review", completeness_protocol="SF-86 Disclosure Completeness Review", missing_selection_protocol="SF-86 Disclosure Selection Review"),
}


def get_section_schema(section_id: str) -> SectionSchema:
    return SECTION_SCHEMAS.get(section_id, _schema(section_id, "Review Item"))
