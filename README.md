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

`/` now serves a simple browser UI where you can paste JSON and click `Validate`.

Example:

```bash
curl -X POST http://127.0.0.1:8000/validate \
  -H 'Content-Type: application/json' \
  --data @examples/sample_payload.json
```

The service validates in memory and does not persist request payloads.

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
