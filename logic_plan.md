# SF-85/86 Validator Master Plan

## 1. Core Logic: The "10-Year Gap" Engine
- **Constraint:** Scan all entries in Section 11 (Residence), 12 (Education), and 13 (Employment).
- **Rule:** Flag any gap between a "To" date and the next "From" date that exceeds 30 days.
- **Rule:** Flag any overlapping dates where a physical residence and a full-time school/job are in different geographic regions without explanation.

## 2. Section-Specific Validation
### Section 11: Residence
- **Must Have:** Physical address (No P.O. Boxes).
- **Special Case:** If APO/FPO is used, require Base/Post name and Unit info.
- **Verifier:** Ensure verifier address is NOT the same as the applicant's current address.

### Section 13: Employment
- **Logic:** No "Unemployed" periods over 30 days without a verifier.
- **Military:** Ensure any "Military Duty" entries include the rank and supervisor contact.

## 3. The "Ever" Flag System
- Scan Sections 21-29 for any "Yes" answers.
- **Action:** If "Yes", create a high-priority "Review Required" tag for local drive export.

## 4. Technical Stack
- **Language:** Python
- **Storage:** Local drive (No cloud caching of form data).
- **Input Format:** JSON
