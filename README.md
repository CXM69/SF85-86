# SF-85/86 Validator

Local, session-based SF-85/SF-86 validation utilities.

## Privacy Model

- Input is JSON.
- Validation runs in memory for the active process only.
- The validator does not write applicant form data to disk.
- Only code, tests, and build progress are tracked in this repository.

## Usage

Run against a JSON file:

```bash
.venv/bin/python -m sf_validator.cli path/to/input.json
```

Or pipe JSON through stdin:

```bash
cat input.json | .venv/bin/python -m sf_validator.cli -
```

The output is JSON with:

- `flags`: all validation flags
- `export_summary`: `Review Required` export tags derived from Sections 21-29

## HTTP Validation

Start the local service:

```bash
.venv/bin/python -m sf_validator.web
```

Endpoints:

- `GET /`
- `GET /health`
- `GET /schema`
- `POST /validate`

`/` now serves a browser UI where the reviewer can:
- choose `SF-85 Public Trust` or `SF-86 National Security`
- drag and drop a full PDF for page-based audit
- review section, subsection, entry, and protocol-level findings

Example:

```bash
curl -X POST http://127.0.0.1:8000/validate \
  -H 'Content-Type: application/json' \
  --data @examples/sample_payload.json
```

The service validates in memory and does not persist request payloads.

## PDF Audit

The browser page accepts a full uploaded PDF and audits it in memory only.

Current PDF findings include page-based flags for:
- Section 11 P.O. Box address issues
- Section 11 APO/FPO missing detail patterns
- Section 13 unemployment without nearby verifier text
- Section 13 military-duty missing nearby rank or supervisor text
- Sections 20A-29 entry-based SF-86 disclosure review
- Section 23 drug-use follow-up entry review
- Section 1-10 blank-page completeness review when no applicant data is detected

## Ledger Proof Boundary

The validator can derive a ledger-safe proof from the in-memory validation report.

- Only the SHA-256 hash of the full validation report is exported for ledger use.
- Sections `1-29` also receive salted SHA-256 hashes so the audit can be proven later without exposing section content.
- The salt and signing key are held in memory only for the active browser session.
- The browser `Clear` action calls the server to destroy that in-memory salt and signing key before resetting the page.
- No PDF bytes, applicant form values, or raw findings are sent in the ledger proof payload.

## Formal Schema Map

The validator now includes a canonical Section `1-29` schema map in
[sf_validator/form_schema.py](sf_validator/form_schema.py).

The PDF audit uses this map for:
- canonical section titles
- whether a section is entry-based
- whether the section is gated by a `Yes/No` selection
- section-specific screening protocols
- minimum detail thresholds before an entry is treated as complete

## Render

Deployment config is in [render.yaml](render.yaml). The service starts with:

```bash
python -m sf_validator.web
```

## Supported Validation Areas

- Section 11: residence checks
- Section 11/23: residence versus drug activity location overlap flags
- Section 12/13: timeline gap and unexplained geography overlap checks
- Section 13: employment checks
- Sections 21-29: "Ever" yes-answer flags
