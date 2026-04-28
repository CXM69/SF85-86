"""In-memory PDF audit helpers for SF-85 and SF-86 forms."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import re
from typing import Any, Dict, List, Optional

from pypdf import PdfReader
from .form_schema import SECTION_SCHEMAS, SectionSchema, get_section_schema


SECTION_RE = re.compile(r"\bsection\s+(2[0-9]|1[0-9]|[1-9])(?:\s*([A-E]))?\b", re.IGNORECASE)
SUBSECTION_PAGE_RE = re.compile(
    r"^\s*((?:2[0-9]|1[0-9]|[1-9])(?:(?:[A-E])(?:\.[0-9A-Z]+)?|\.[0-9A-Z]+))\b",
    re.IGNORECASE,
)
ENTRY_RE = re.compile(r"\bentry\s*#\s*(\d+)\b", re.IGNORECASE)
PO_BOX_RE = re.compile(r"\b(p\.?\s*o\.?\s*box|post\s+office\s+box)\b", re.IGNORECASE)
APO_FPO_RE = re.compile(r"\b(APO|FPO)\b", re.IGNORECASE)
BASE_POST_UNIT_RE = re.compile(r"\b(base|post|unit)\b", re.IGNORECASE)
UNEMPLOYED_RE = re.compile(r"\bunemployed\b", re.IGNORECASE)
MILITARY_RE = re.compile(r"\bmilitary\b|\bduty\b", re.IGNORECASE)
RANK_RE = re.compile(r"\brank\b", re.IGNORECASE)
SUPERVISOR_RE = re.compile(r"\bsupervisor\b", re.IGNORECASE)
YES_RE = re.compile(r"\byes\b", re.IGNORECASE)
NO_RE = re.compile(r"\bno\b", re.IGNORECASE)
DATE_RE = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4})\b")
SECTION_TITLE_STOP_RE = re.compile(r"\b(yes|no|selected|checked|marked|page\s+\d+)\b", re.IGNORECASE)
SELECTED_YES_RE = re.compile(
    r"(?:\bselected\s+yes\b|\byes\s+selected\b|\bchecked\s+yes\b|\byes\s+checked\b|\bmarked\s+yes\b|\byes\s+marked\b|\b[x×]\s*yes\b|\byes\s*[x×]\b|☒\s*yes\b|\byes\s*☒\b)",
    re.IGNORECASE,
)
SELECTED_NO_RE = re.compile(
    r"(?:\bselected\s+no\b|\bno\s+selected\b|\bchecked\s+no\b|\bno\s+checked\b|\bmarked\s+no\b|\bno\s+marked\b|\b[x×]\s*no\b|\bno\s*[x×]\b|☒\s*no\b|\bno\s*☒\b)",
    re.IGNORECASE,
)
MONTH_YEAR_RE = re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\s/-]+\d{2,4}\b", re.IGNORECASE)
NUMBER_COUNT_RE = re.compile(r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:time|times|month|months|year|years|week|weeks|day|days)\b", re.IGNORECASE)
MONEY_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?")
EMAIL_RE = re.compile(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
DRUG_TYPE_RE = re.compile(r"\b(?:marijuana|cocaine|heroin|methamphetamine|ecstasy|mdma|lsd|psilocybin|opioid|adderall|xanax|prescription\s+drug)\b", re.IGNORECASE)
NARRATIVE_RE = re.compile(r"\b(?:because|after|during|while|when|where|reason|explain|explained)\b.{12,}", re.IGNORECASE)


@dataclass(frozen=True)
class PdfFinding:
    code: str
    severity: str
    section: str
    subsection: str
    section_title: str
    entry_number: Optional[int]
    screening_protocol: str
    page: int
    message: str
    snippet: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "section": self.section,
            "subsection": self.subsection,
            "section_title": self.section_title,
            "entry_number": self.entry_number,
            "screening_protocol": self.screening_protocol,
            "page": self.page,
            "message": self.message,
            "snippet": self.snippet,
        }


@dataclass(frozen=True)
class PageContext:
    page: int
    section: str
    subsection: str
    section_title: str
    entry_number: Optional[int]
    text: str
    snippet: str


def audit_pdf(pdf_bytes: bytes, form_type: str = "SF86") -> Dict[str, Any]:
    normalized_form_type = _normalize_form_type(form_type)
    reader = PdfReader(BytesIO(pdf_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    findings = _find_pdf_issues(pages, form_type=normalized_form_type)
    findings = sorted(findings, key=_finding_sort_key)
    return {
        "mode": "pdf",
        "form_type": normalized_form_type,
        "review_profile": _review_profile(normalized_form_type),
        "page_count": len(pages),
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
    }


def _find_pdf_issues(page_texts: List[str], form_type: str) -> List[PdfFinding]:
    page_contexts = _build_page_contexts(page_texts)
    from .main import run_pdf_audit

    return run_pdf_audit(page_contexts, form_type)


def _snippet(text: str, max_chars: int = 220) -> str:
    clean = " ".join(text.split())
    return clean[:max_chars] + ("..." if len(clean) > max_chars else "")


def _build_page_contexts(page_texts: List[str]) -> List[PageContext]:
    contexts: List[PageContext] = []
    current_section = "unknown"
    for page_number, text in enumerate(page_texts, start=1):
        section, subsection, title = _detect_section_and_title(text, current_section)
        entry_number = _detect_entry_number(text)
        current_section = section or "unknown"
        contexts.append(
            PageContext(
                page=page_number,
                section=section or "unknown",
                subsection=subsection or "unknown",
                section_title=title or "Review Item",
                entry_number=entry_number,
                text=text,
                snippet=_snippet(text),
            )
        )
    return contexts


def _sequence_gap_findings(page_contexts: List[PageContext], form_type: str) -> List[PdfFinding]:
    findings: List[PdfFinding] = []
    detected_sections = [(_main_section_number(context.section), context) for context in page_contexts]
    detected_sections = [(number, context) for number, context in detected_sections if number is not None]
    if not detected_sections:
        return findings
    distinct_detected_sections = {number for number, _context in detected_sections}
    if len(distinct_detected_sections) < 2:
        return findings

    max_expected_section = 13 if form_type == "SF85" else 29
    first_main_section, first_context = detected_sections[0]
    if first_main_section > 1:
        for missing_section in range(1, first_main_section):
            missing_schema = get_section_schema(str(missing_section))
            findings.append(
                PdfFinding(
                    code="PDF_SECTION_SEQUENCE_GAP",
                    severity="high",
                    section=str(missing_section),
                    subsection=str(missing_section),
                    section_title=missing_schema.title,
                    entry_number=None,
                    screening_protocol="Section Sequence Review",
                    page=first_context.page,
                    message=(
                        f"Potential Section {missing_section} issue: this section was not detected before "
                        f"Section {first_main_section}. Review the PDF sequence and confirm the section is present and completed."
                    ),
                    snippet=first_context.snippet,
                )
            )

    highest_main_section: Optional[int] = None

    for context in page_contexts:
        current_main = _main_section_number(context.section)
        if current_main is None:
            continue
        if highest_main_section is not None and current_main > highest_main_section + 1:
            for missing_section in range(highest_main_section + 1, current_main):
                missing_schema = get_section_schema(str(missing_section))
                findings.append(
                    PdfFinding(
                        code="PDF_SECTION_SEQUENCE_GAP",
                        severity="high",
                        section=str(missing_section),
                        subsection=str(missing_section),
                        section_title=missing_schema.title,
                        entry_number=None,
                        screening_protocol="Section Sequence Review",
                        page=context.page,
                        message=(
                            f"Potential Section {missing_section} issue: this section was not detected between "
                            f"Section {highest_main_section} and Section {current_main}. Review the PDF sequence "
                            "and confirm the section is present and completed."
                        ),
                        snippet=context.snippet,
                    )
                )
        highest_main_section = current_main if highest_main_section is None else max(highest_main_section, current_main)

    last_main_section, last_context = detected_sections[-1]
    if last_main_section < max_expected_section:
        for missing_section in range(last_main_section + 1, max_expected_section + 1):
            missing_schema = get_section_schema(str(missing_section))
            findings.append(
                PdfFinding(
                    code="PDF_SECTION_SEQUENCE_GAP",
                    severity="high",
                    section=str(missing_section),
                    subsection=str(missing_section),
                    section_title=missing_schema.title,
                    entry_number=None,
                    screening_protocol="Section Sequence Review",
                    page=last_context.page,
                    message=(
                        f"Potential Section {missing_section} issue: this section was not detected after "
                        f"Section {last_main_section}. Review the PDF sequence and confirm the section is present and completed."
                    ),
                    snippet=last_context.snippet,
                )
            )

    return findings


def _detect_section_and_title(text: str, previous_section: str = "unknown") -> tuple[Optional[str], Optional[str], Optional[str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    explicit_section: Optional[str] = None
    explicit_subsection: Optional[str] = None
    explicit_title: Optional[str] = None
    page_subsection = _detect_page_subsection(lines)

    for index, line in enumerate(lines):
        match = SECTION_RE.search(line)
        if not match:
            continue
        section_number = match.group(1)
        subsection = match.group(2).upper() if match.group(2) else ""
        section = f"{section_number}{subsection}"
        fallback_title = _section_title_fallback(section)
        if (fallback_title != "Review Item" and get_section_schema(section).blank_review_enabled) or section in {"11", "13"}:
            explicit_section = section
            explicit_subsection = page_subsection or section
            explicit_title = fallback_title
            break
        remainder = line[match.end():].strip(" .:-\t")
        title_source = remainder or (lines[index + 1] if index + 1 < len(lines) else "")
        title = _clean_section_title(title_source) or fallback_title
        explicit_section = section
        explicit_subsection = page_subsection or section
        explicit_title = title
        break

    if explicit_section:
        return explicit_section, explicit_subsection, explicit_title

    for line in lines[:8]:
        match = SUBSECTION_PAGE_RE.match(line)
        if not match:
            continue
        subsection = match.group(1).strip()
        section_match = re.match(r"(2[0-9]|1[0-9]|[1-9])([A-E])?", subsection, re.IGNORECASE)
        if not section_match:
            continue
        section = section_match.group(1)
        if section_match.group(2):
            section = f"{section}{section_match.group(2).upper()}"
        title = _section_title_fallback(section)
        return section, subsection, title

    inferred = _infer_section_from_schema(text)
    if inferred:
        return inferred, inferred, _section_title_fallback(inferred)

    continued = _infer_continuation_section(previous_section, text)
    if continued:
        return continued, continued, _section_title_fallback(continued)

    return None, None, None


def _detect_entry_number(text: str) -> Optional[int]:
    match = ENTRY_RE.search(text)
    if not match:
        return None
    return int(match.group(1))


def _split_entry_segments(text: str) -> List[tuple[Optional[int], str]]:
    matches = list(ENTRY_RE.finditer(text))
    if not matches:
        return []

    segments: List[tuple[Optional[int], str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        entry_text = text[start:end].strip()
        segments.append((int(match.group(1)), entry_text))
    return segments


def _clean_section_title(value: str) -> str:
    normalized = "".join(char if char.isprintable() and not char.isspace() else " " for char in value)
    trimmed = SECTION_TITLE_STOP_RE.split(normalized, maxsplit=1)[0]
    words = [word.strip(" -\u00ad") for word in trimmed.replace("_", " ").split() if word.strip(" -\u00ad")]
    if not words:
        return ""
    candidate = " ".join(words[:8]).strip(" .:-")
    if not re.search(r"[A-Za-z0-9]", candidate):
        return ""
    return candidate


def _main_section_number(section: str) -> Optional[int]:
    match = re.match(r"(\d+)", section or "")
    if not match:
        return None
    return int(match.group(1))


def _finding_sort_key(finding: PdfFinding) -> tuple[int, str, int, int, str]:
    main_section = _main_section_number(finding.section) or 999
    subsection = finding.subsection or finding.section or ""
    entry_number = finding.entry_number if finding.entry_number is not None else 0
    code_priority = {
        "PDF_SECTION_SEQUENCE_GAP": 0,
        "PDF_SECTION_DATA_MISSING": 1,
        "PDF_SECTION_23_REVIEW_REQUIRED": 2,
        "PDF_EVER_FLAG_REVIEW_REQUIRED": 2,
        "PDF_SECTION_23_INCOMPLETE": 3,
        "PDF_EVER_FLAG_INCOMPLETE": 3,
        "PDF_EVER_FLAG_SELECTION_MISSING": 4,
    }.get(finding.code, 5)
    return (main_section, subsection, finding.page, entry_number, code_priority, finding.code)


def _section_title_fallback(section: str) -> str:
    return get_section_schema(section).title


def _expected_field_summary(section_schema: SectionSchema) -> str:
    if not section_schema.expected_fields:
        return "the expected section details"
    if len(section_schema.expected_fields) == 1:
        return section_schema.expected_fields[0]
    if len(section_schema.expected_fields) == 2:
        return f"{section_schema.expected_fields[0]} and {section_schema.expected_fields[1]}"
    head = ", ".join(section_schema.expected_fields[:3])
    return f"{head}, and related follow-up details"


def _strip_prompt_anchors(text: str, section_schema: SectionSchema) -> str:
    normalized = " ".join(text.split())
    if not section_schema.field_label_anchors:
        return normalized

    stripped = normalized
    for anchor in sorted(section_schema.field_label_anchors, key=len, reverse=True):
        pattern = re.compile(re.escape(anchor), re.IGNORECASE)
        stripped = pattern.sub(" ", stripped)
    return " ".join(stripped.split())


def _has_supporting_detail_in_text(
    combined: str,
    section_schema: SectionSchema,
    min_signals: int = 1,
) -> bool:
    filtered = _strip_prompt_anchors(combined, section_schema)
    return _detail_signal_count(
        filtered,
        require_drug_context=section_schema.require_drug_context,
    ) >= min_signals


def _detect_answer_state_from_text(combined: str, section_schema: SectionSchema) -> str:
    has_selected_yes = bool(SELECTED_YES_RE.search(combined))
    has_selected_no = bool(SELECTED_NO_RE.search(combined))

    if has_selected_yes and not has_selected_no:
        return "yes"
    if has_selected_no and not has_selected_yes:
        return "no"
    filtered = _strip_prompt_anchors(combined, section_schema)
    if section_schema.title:
        filtered = re.sub(re.escape(section_schema.title), " ", filtered, flags=re.IGNORECASE)
        filtered = " ".join(filtered.split())
    if (YES_RE.search(combined) or NO_RE.search(combined)) and _has_meaningful_user_text(filtered):
        return "missing"
    return "unknown"


def _detect_page_subsection(lines: List[str]) -> Optional[str]:
    for line in lines[:8]:
        match = SUBSECTION_PAGE_RE.match(line)
        if match:
            return match.group(0).strip()
    return None


def _infer_section_from_schema(text: str) -> Optional[str]:
    normalized = " ".join(text.lower().split())
    best_section: Optional[str] = None
    best_score = 0
    inference_candidates = {str(number) for number in range(8, 20)}

    for section_id, schema in SECTION_SCHEMAS.items():
        if section_id not in inference_candidates:
            continue
        score = 0
        title = schema.title.lower()
        if title and title != "review item" and title in normalized:
            score += 4 + len(title.split())
        score += sum(1 for cue in schema.cue_phrases if cue and cue in normalized)
        if score > best_score and score >= 3:
            best_score = score
            best_section = section_id

    return best_section


def _infer_continuation_section(previous_section: str, text: str) -> Optional[str]:
    if previous_section == "unknown":
        return None
    schema = get_section_schema(previous_section)
    normalized = " ".join(text.lower().split())
    if schema.title and schema.title.lower() in normalized:
        return previous_section
    cue_hits = sum(1 for cue in schema.cue_phrases if cue and cue in normalized)
    anchor_hits = sum(1 for anchor in schema.field_label_anchors[:3] if anchor and anchor in normalized)
    if cue_hits + anchor_hits >= 3 and previous_section in {"11", "12", "13", "14", "15", "16", "17", "18", "19"}:
        return previous_section
    return None


def _section11_has_po_box_in_residence_address(text: str) -> bool:
    if not PO_BOX_RE.search(text):
        return False

    normalized = " ".join(text.split())
    lower = normalized.lower()
    stop_markers = [
        "verifier",
        "name of person who knew you",
        "provide the name of a person",
        "reference",
    ]
    cutoff = len(normalized)
    for marker in stop_markers:
        marker_index = lower.find(marker)
        if marker_index != -1:
            cutoff = min(cutoff, marker_index)
    address_region = normalized[:cutoff]
    return bool(PO_BOX_RE.search(address_region))


def _looks_like_section23_followup(text: str) -> bool:
    schema = get_section_schema("23")
    normalized = " ".join(text.lower().split())
    anchor_hits = sum(anchor.lower() in normalized for anchor in schema.field_label_anchors)
    return anchor_hits >= 3


def _has_section23_detail(text: str, min_signals: int) -> bool:
    schema = get_section_schema("23")
    normalized = " ".join(text.split())
    prompt_hits = sum(anchor.lower() in normalized.lower() for anchor in schema.field_label_anchors)
    if prompt_hits < 3:
        return True

    filtered = _strip_prompt_anchors(normalized, schema)
    return _detail_signal_count(filtered, require_drug_context=True) >= min_signals


def _detail_signal_count(text: str, require_drug_context: bool = False) -> int:
    normalized = " ".join(text.split())
    signals = [
        bool(DATE_RE.search(normalized) or MONTH_YEAR_RE.search(normalized)),
        bool(NUMBER_COUNT_RE.search(normalized)),
        bool(MONEY_RE.search(normalized)),
        bool(EMAIL_RE.search(normalized) or PHONE_RE.search(normalized)),
        bool(DRUG_TYPE_RE.search(normalized)) if require_drug_context else False,
        bool(NARRATIVE_RE.search(normalized)),
    ]
    return sum(1 for signal in signals if signal)


def _has_meaningful_user_text(text: str) -> bool:
    normalized = " ".join(text.split())
    if not normalized:
        return False
    if DATE_RE.search(normalized) or MONTH_YEAR_RE.search(normalized):
        return True
    if EMAIL_RE.search(normalized) or PHONE_RE.search(normalized) or MONEY_RE.search(normalized):
        return True
    words = [word for word in re.split(r"\W+", normalized) if word]
    meaningful_words = [word for word in words if len(word) > 2 and not word.isdigit()]
    return len(meaningful_words) >= 2


def _text_looks_unanswered(section_schema: SectionSchema, text: str) -> bool:
    normalized = " ".join(text.lower().split())
    cue_hits = sum(
        cue in normalized for cue in section_schema.cue_phrases
    )
    prompt_hits = sum(
        phrase in normalized for phrase in section_schema.field_label_anchors
    )
    prompt_hits += sum(
        phrase in normalized
        for phrase in ("yes no", "provide", "list", "entry #", "month/year")
    )
    title_hit = bool(section_schema.title and section_schema.title.lower() in normalized)
    if cue_hits + prompt_hits < 3 and not title_hit:
        return False
    if SELECTED_YES_RE.search(normalized) or SELECTED_NO_RE.search(normalized):
        return False
    filtered = _strip_prompt_anchors(normalized, section_schema)
    data_signals = [
        re.search(r"\b\d{3}-\d{2}-\d{4}\b", filtered),
        re.search(r"\b\d{4}-\d{2}-\d{2}\b", filtered),
        re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", filtered),
        re.search(r"\b\d{4}\b", filtered),
        MONTH_YEAR_RE.search(filtered),
        re.search(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", filtered),
        re.search(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b", filtered),
        re.search(r"\b(street|avenue|road|drive|lane|city|state|zip)\b.+\b\d{1,5}\b", filtered),
        re.search(r"\b(?:single|married|divorced|widowed)\b", filtered),
        re.search(r"\b(?:male|female)\b", filtered),
    ]
    return not any(signal is not None for signal in data_signals)


def _normalize_form_type(form_type: str) -> str:
    normalized = (form_type or "SF86").strip().upper().replace("-", "")
    if normalized not in {"SF85", "SF86"}:
        raise ValueError("Unsupported form type. Use SF85 or SF86.")
    return normalized


def _review_profile(form_type: str) -> Dict[str, Any]:
    if form_type == "SF85":
        return {
            "name": "Public Trust",
            "guardrails": [
                "Treat this document as an SF-85 public trust review.",
                "Section 21-29 national-security 'Ever' scanning is disabled for SF-85.",
                "Only public-trust-relevant PDF checks are applied in this profile.",
            ],
        }
    return {
        "name": "National Security",
        "guardrails": [
            "Treat this document as an SF-86 national security review.",
            "Section 21-29 'Ever' scanning is enabled for this profile.",
            "National-security review items should remain available for adjudication review.",
        ],
    }
