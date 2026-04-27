"""HTTP interface for session-only SF-85/SF-86 validation."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from typing import Any, Dict, Tuple

from .cli import run_validation
from .schema import SchemaValidationError, input_schema


def _json_response(status: int, payload: Dict[str, Any]) -> Tuple[int, bytes]:
    body = json.dumps(payload, indent=2).encode("utf-8")
    return status, body


def _html_response(status: int, body: str) -> Tuple[int, bytes, str]:
    return status, body.encode("utf-8"), "text/html; charset=utf-8"


def _index_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SF-85/86 Validator</title>
  <style>
    :root {
      --bg: #f5f1e8;
      --panel: #fffaf0;
      --ink: #1f2937;
      --muted: #6b7280;
      --accent: #1d4ed8;
      --border: #d6d3d1;
      --danger: #991b1b;
    }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
      background: linear-gradient(180deg, #efe7d6 0%, var(--bg) 100%);
      color: var(--ink);
    }
    .wrap {
      max-width: 980px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.08);
      padding: 24px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 2rem;
    }
    p {
      margin: 0 0 16px;
      color: var(--muted);
      line-height: 1.5;
    }
    textarea {
      width: 100%;
      min-height: 320px;
      box-sizing: border-box;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
      font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
      background: white;
      color: var(--ink);
      resize: vertical;
    }
    .row {
      display: flex;
      gap: 12px;
      align-items: center;
      margin: 16px 0;
      flex-wrap: wrap;
    }
    button {
      background: var(--accent);
      color: white;
      border: 0;
      border-radius: 999px;
      padding: 12px 18px;
      font-weight: 600;
      cursor: pointer;
    }
    button.secondary {
      background: transparent;
      color: var(--ink);
      border: 1px solid var(--border);
    }
    .note {
      font-size: 0.95rem;
      color: var(--muted);
    }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      background: #111827;
      color: #f9fafb;
      padding: 16px;
      border-radius: 12px;
      min-height: 180px;
      overflow: auto;
    }
    .error {
      color: var(--danger);
      font-weight: 600;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <h1>SF-85/86 Validator</h1>
      <p>Paste form JSON below and click <strong>Validate</strong>. Validation runs in memory only for this session and is not stored by the service.</p>
      <textarea id="payload">{
  "section_11": [
    {
      "from_date": "2020-01-01",
      "to_date": "2020-12-31",
      "street1": "P.O. Box 15",
      "city": "Austin",
      "state": "TX",
      "country": "USA",
      "is_current": true,
      "verifier": {
        "address": "P.O. Box 15",
        "city": "Austin",
        "state": "TX"
      }
    }
  ],
  "section_13": [
    {
      "employment_type": "Unemployed",
      "from_date": "2021-01-01",
      "to_date": "2021-03-15",
      "city": "Denver",
      "state": "CO",
      "country": "USA"
    }
  ],
  "section_21": {
    "illegal_drug_use": "Yes"
  },
  "section_23": [
    {
      "street1": "P.O. Box 15",
      "city": "Austin",
      "state": "TX",
      "country": "USA",
      "from_date": "2020-05-01",
      "to_date": "2020-05-10"
    }
  ]
}</textarea>
      <div class="row">
        <button id="validateBtn">Validate</button>
        <button id="schemaBtn" class="secondary">View Schema</button>
        <span class="note">Nothing is saved. Refresh clears the page state.</span>
      </div>
      <div id="status" class="note"></div>
      <pre id="output">Validation output will appear here.</pre>
    </div>
  </div>
  <script>
    const payloadEl = document.getElementById('payload');
    const outputEl = document.getElementById('output');
    const statusEl = document.getElementById('status');
    const validateBtn = document.getElementById('validateBtn');
    const schemaBtn = document.getElementById('schemaBtn');

    async function callApi(path, options = {}) {
      const response = await fetch(path, options);
      const text = await response.text();
      let parsed;
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = { raw: text };
      }
      return { ok: response.ok, status: response.status, body: parsed };
    }

    validateBtn.addEventListener('click', async () => {
      statusEl.textContent = 'Validating...';
      statusEl.className = 'note';
      outputEl.textContent = '';
      const result = await callApi('/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payloadEl.value
      });
      if (!result.ok) {
        statusEl.textContent = 'Request failed.';
        statusEl.className = 'error';
      } else {
        statusEl.textContent = 'Validation complete.';
      }
      outputEl.textContent = JSON.stringify(result.body, null, 2);
    });

    schemaBtn.addEventListener('click', async () => {
      statusEl.textContent = 'Loading schema...';
      statusEl.className = 'note';
      const result = await callApi('/schema');
      outputEl.textContent = JSON.stringify(result.body, null, 2);
      statusEl.textContent = result.ok ? 'Schema loaded.' : 'Could not load schema.';
    });
  </script>
</body>
</html>"""


def handle_request(method: str, path: str, body: bytes = b"") -> Tuple[int, Dict[str, Any]]:
    if method == "GET" and path == "/health":
        return HTTPStatus.OK, {"status": "ok"}
    if method == "GET" and path == "/schema":
        return HTTPStatus.OK, input_schema()
    if method == "POST" and path == "/validate":
        try:
            payload = json.loads(body.decode("utf-8"))
            result = run_validation(payload)
        except json.JSONDecodeError as exc:
            return HTTPStatus.BAD_REQUEST, {"error": f"Invalid JSON: {exc.msg}"}
        except SchemaValidationError as exc:
            return HTTPStatus.BAD_REQUEST, {"error": f"Validation error: {exc}"}
        return HTTPStatus.OK, result
    return HTTPStatus.NOT_FOUND, {"error": "Not found"}


class ValidatorRequestHandler(BaseHTTPRequestHandler):
    server_version = "SF86Validator/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            status, body, content_type = _html_response(HTTPStatus.OK, _index_page())
            self._send_bytes(status, body, content_type)
            return
        status, payload = handle_request("GET", self.path)
        self._send_json(status, payload)

    def do_POST(self) -> None:  # noqa: N802
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid Content-Length"})
            return

        raw = self.rfile.read(content_length)
        status, payload = handle_request("POST", self.path, raw)
        self._send_json(status, payload)

    def log_message(self, format: str, *args: object) -> None:
        """Suppress request logging to avoid copying request payload context to logs."""
        return

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        code, body = _json_response(status, payload)
        self._send_bytes(code, body, "application/json")

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve() -> None:
    port = int(os.environ.get("PORT", "8000"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), ValidatorRequestHandler)
    print("Serving SF-85/86 validator on port %s" % port)
    httpd.serve_forever()


if __name__ == "__main__":
    serve()
