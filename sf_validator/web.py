"""HTTP interface for session-only SF-85/SF-86 validation."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from typing import Any, Dict, Optional, Tuple

from .cli import run_validation
from .ledger import build_ledger_payload, clear_session_material
from .pdf_audit import audit_pdf
from .schema import SchemaValidationError, input_schema


def _privacy_headers(content_type: str, content_length: int) -> Dict[str, str]:
    return {
        "Content-Type": content_type,
        "Content-Length": str(content_length),
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0, private",
        "Pragma": "no-cache",
        "Expires": "0",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
    }


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
      --bg: #edf3f9;
      --panel: #ffffff;
      --ink: #152235;
      --muted: #5c6f86;
      --line: #d8e1ec;
      --accent: #1d4f91;
      --accent-soft: #eaf2fc;
      --warn: #8b5a1f;
      --warn-bg: #f8f3ea;
      --good: #1d6b45;
      --good-bg: #edf8f2;
      --bad: #9a2438;
      --bad-bg: #fcf0f2;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, #f8fbff 0%, transparent 30%),
        linear-gradient(180deg, #f7fafe 0%, var(--bg) 100%);
    }
    .page {
      max-width: 940px;
      margin: 0 auto;
      padding: 28px 18px 48px;
    }
    .hero {
      margin-bottom: 18px;
    }
    .eyebrow {
      font-size: 0.76rem;
      font-weight: 700;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 10px;
    }
    h1 {
      margin: 0 0 10px;
      font-size: 2.35rem;
      line-height: 1.05;
    }
    .hero p {
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
      max-width: 720px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: 0 16px 34px rgba(16, 32, 56, 0.08);
      padding: 24px;
    }
    .panel + .panel {
      margin-top: 18px;
    }
    h2 {
      margin: 0 0 12px;
      font-size: 1.08rem;
    }
    .selector {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 18px;
    }
    .hotbutton {
      border: 1px solid var(--line);
      border-radius: 999px;
      background: white;
      color: var(--ink);
      padding: 12px 18px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      transition: 120ms ease;
    }
    .hotbutton.active {
      background: var(--accent);
      border-color: var(--accent);
      color: white;
      transform: translateY(-1px);
    }
    .dropzone {
      border: 2px dashed #b7c7db;
      border-radius: 18px;
      background: linear-gradient(180deg, #ffffff 0%, #f7fafe 100%);
      padding: 28px 20px;
      text-align: center;
      transition: 120ms ease;
    }
    .dropzone.active {
      border-color: var(--accent);
      background: var(--accent-soft);
    }
    .dropzone strong {
      display: block;
      font-size: 1.05rem;
      margin-bottom: 8px;
    }
    .dropzone p {
      margin: 0 0 12px;
      color: var(--muted);
    }
    .file-input {
      max-width: 340px;
      margin: 0 auto;
    }
    input[type="file"] {
      width: 100%;
      font: inherit;
    }
    .file-name {
      margin-top: 12px;
      font-size: 0.95rem;
      color: var(--muted);
      min-height: 1.35em;
    }
    .actions {
      margin-top: 20px;
      display: flex;
      justify-content: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .primary {
      border: 0;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      padding: 14px 28px;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
      min-width: 180px;
    }
    .primary:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    .secondary {
      border: 1px solid var(--line);
      border-radius: 999px;
      background: white;
      color: var(--ink);
      padding: 14px 22px;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
    }
    .status {
      margin-top: 14px;
      min-height: 1.35em;
      text-align: center;
      font-size: 0.96rem;
      color: var(--muted);
    }
    .status.good { color: var(--good); font-weight: 700; }
    .status.bad { color: var(--bad); font-weight: 700; }
    .results-head {
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 16px;
      align-items: stretch;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      background: #fff;
    }
    .metric-label {
      color: var(--muted);
      font-size: 0.92rem;
      margin-bottom: 8px;
    }
    .metric-value {
      font-size: 2.4rem;
      font-weight: 800;
      line-height: 1;
    }
    .review-box {
      border: 1px solid #d8e1ec;
      border-radius: 18px;
      background: linear-gradient(180deg, #fcfdff 0%, #f3f7fc 100%);
      padding: 18px;
      min-height: 142px;
      max-height: 220px;
      overflow: auto;
    }
    .review-box h3 {
      margin: 0 0 10px;
      font-size: 1rem;
    }
    .review-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .guardrail-note {
      margin-top: 14px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #f7fafe;
      padding: 12px 14px;
      color: var(--muted);
      font-size: 0.93rem;
      line-height: 1.45;
    }
    .review-item {
      border: 1px solid rgba(29, 79, 145, 0.14);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.94);
      padding: 12px 14px;
    }
    .review-item-title {
      font-weight: 800;
      margin-bottom: 6px;
      color: #1d4f91;
    }
    .review-item-subtitle {
      font-size: 0.92rem;
      font-weight: 700;
      color: var(--muted);
      margin-bottom: 8px;
    }
    .review-item-meta {
      font-size: 0.9rem;
      color: var(--muted);
      margin-bottom: 8px;
    }
    .review-empty {
      border: 1px solid #b8ddc2;
      border-radius: 14px;
      background: var(--good-bg);
      padding: 14px;
      color: var(--good);
      font-weight: 700;
    }
    @media (max-width: 760px) {
      .results-head {
        grid-template-columns: 1fr;
      }
      h1 {
        font-size: 1.9rem;
      }
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <div class="eyebrow">Session-Only Review</div>
      <h1>SF-85 / SF-86 Validator</h1>
      <p>Choose the form type, load the full PDF, and run validation. The service analyzes the uploaded document in memory for this session only and returns the sections and issues that need review.</p>
    </div>

    <div class="panel">
      <h2>Form Type</h2>
      <div class="selector">
        <button id="sf85Btn" class="hotbutton" type="button">SF-85 Public Trust</button>
        <button id="sf86Btn" class="hotbutton active" type="button">SF-86 National Security</button>
      </div>

      <h2>Load Form PDF</h2>
      <div id="dropZone" class="dropzone">
        <strong>Drag and drop the full SF form here</strong>
        <p>or choose the PDF file below</p>
        <div class="file-input">
          <input id="pdfFile" type="file" accept="application/pdf">
        </div>
        <div id="fileName" class="file-name">No file selected.</div>
      </div>
      <div id="guardrailNote" class="guardrail-note">SF-86 selected. National security review items are enabled.</div>

      <div class="actions">
        <button id="validateBtn" class="primary" type="button">Validate</button>
        <button id="clearBtn" class="secondary" type="button">Clear</button>
      </div>
      <div id="status" class="status">Ready for document review.</div>
    </div>

    <div class="panel">
      <h2>Results</h2>
      <div class="results-head">
        <div class="metric">
          <div class="metric-label">Total Flags</div>
          <div id="totalFlags" class="metric-value">0</div>
        </div>
        <div class="review-box">
          <h3>Review Required</h3>
          <div id="reviewList" class="review-list">
            <div class="review-empty">Load a form and click Validate to see flagged sections and issues here.</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let selectedFormType = 'SF86';
    let selectedPdfFile = null;
    let activeSessionId = (window.crypto && window.crypto.randomUUID)
      ? window.crypto.randomUUID()
      : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    let activeAuditId = 0;
    let activeAuditController = null;

    const sf85Btn = document.getElementById('sf85Btn');
    const sf86Btn = document.getElementById('sf86Btn');
    const dropZone = document.getElementById('dropZone');
    const pdfFile = document.getElementById('pdfFile');
    const validateBtn = document.getElementById('validateBtn');
    const clearBtn = document.getElementById('clearBtn');
    const fileName = document.getElementById('fileName');
    const guardrailNote = document.getElementById('guardrailNote');
    const statusEl = document.getElementById('status');
    const totalFlags = document.getElementById('totalFlags');
    const reviewList = document.getElementById('reviewList');

    function setFormType(formType) {
      selectedFormType = formType;
      sf85Btn.classList.toggle('active', formType === 'SF85');
      sf86Btn.classList.toggle('active', formType === 'SF86');
      guardrailNote.textContent = formType === 'SF85'
        ? 'SF-85 selected. Public trust guardrails are active and SF-86 national security sections are not scanned.'
        : 'SF-86 selected. National security review items are enabled.';
      if (selectedPdfFile) {
        setStatus(`Ready to validate ${selectedFormType} PDF.`, '');
      }
    }

    function setStatus(message, kind = '') {
      statusEl.textContent = message;
      statusEl.className = `status ${kind}`.trim();
    }

    function setSelectedFile(file) {
      selectedPdfFile = file || null;
      if (selectedPdfFile) {
        fileName.textContent = selectedPdfFile.name;
        setStatus(`Ready to validate ${selectedFormType} PDF.`, '');
      } else {
        fileName.textContent = 'No file selected.';
        setStatus('Ready for document review.', '');
      }
    }

    async function callPdfAudit(file, formType, signal) {
      const response = await fetch('/validate-pdf', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/pdf',
          'X-Form-Type': formType,
          'X-Session-Id': activeSessionId
        },
        body: await file.arrayBuffer(),
        signal
      });
      const text = await response.text();
      let parsed;
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = { raw: text };
      }
      return { ok: response.ok, status: response.status, body: parsed };
    }

    async function clearServerSession() {
      try {
        await fetch('/clear-session', {
          method: 'POST',
          headers: {
            'X-Session-Id': activeSessionId
          }
        });
      } catch {
        // Best effort only. The client state still clears locally.
      }
      activeSessionId = (window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID()
        : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    function renderReviewItems(findings) {
      if (!findings.length) {
        reviewList.innerHTML = '<div class="review-empty">No review items were returned for this document.</div>';
        return;
      }

      reviewList.innerHTML = findings.map((item) => {
        const scope = item.subsection && item.subsection !== item.section ? item.subsection : item.section;
        const location = item.page ? `Section ${scope} · Page ${item.page}` : `Section ${scope}`;
        const entry = item.entry_number ? `Entry #${item.entry_number}` : '';
        const protocol = item.screening_protocol || '';
        const meta = [entry, protocol].filter(Boolean).join(' · ');
        return `
          <div class="review-item">
            <div class="review-item-title">${location}</div>
            <div class="review-item-subtitle">${item.section_title || 'Review Item'}</div>
            ${meta ? `<div class="review-item-meta">${meta}</div>` : ''}
            <div>${item.message}</div>
          </div>
        `;
      }).join('');
    }

    async function clearReviewSession() {
      activeAuditId += 1;
      if (activeAuditController) {
        activeAuditController.abort();
        activeAuditController = null;
      }
      await clearServerSession();
      setSelectedFile(null);
      pdfFile.value = '';
      validateBtn.disabled = false;
      totalFlags.textContent = '0';
      reviewList.innerHTML = '<div class="review-empty">Load a form and click Validate to see flagged sections and issues here.</div>';
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, '', window.location.pathname);
      }
      setStatus('Ready for document review.', '');
    }

    async function runValidation() {
      const file = selectedPdfFile || (pdfFile.files && pdfFile.files[0]);
      if (!file) {
        setStatus('Choose a PDF before validating.', 'bad');
        return;
      }

      const requestId = activeAuditId + 1;
      activeAuditId = requestId;
      if (activeAuditController) {
        activeAuditController.abort();
      }
      activeAuditController = new AbortController();
      const requestFormType = selectedFormType;
      validateBtn.disabled = true;
      setStatus(`Reviewing ${requestFormType} PDF...`, '');
      totalFlags.textContent = '0';
      reviewList.innerHTML = '<div class="review-empty">Validation is running.</div>';

      let result;
      try {
        result = await callPdfAudit(file, requestFormType, activeAuditController.signal);
      } catch (error) {
        if (requestId !== activeAuditId) {
          return;
        }
        validateBtn.disabled = false;
        activeAuditController = null;
        if (error && error.name === 'AbortError') {
          return;
        }
        setStatus('Validation failed.', 'bad');
        reviewList.innerHTML = '<div class="review-item"><div class="review-item-title">Request Error</div><div>Unable to complete PDF validation.</div></div>';
        return;
      }

      if (requestId !== activeAuditId) {
        return;
      }

      validateBtn.disabled = false;
      activeAuditController = null;

      if (!result.ok) {
        setStatus('Validation failed.', 'bad');
        reviewList.innerHTML = `<div class="review-item"><div class="review-item-title">Request Error</div><div>${result.body.error || 'Unknown error'}</div></div>`;
        return;
      }

      const findings = result.body.findings || [];
      totalFlags.textContent = String(result.body.finding_count || findings.length);
      renderReviewItems(findings);
      setStatus(`Validation complete for ${requestFormType}.`, 'good');
    }

    sf85Btn.addEventListener('click', () => setFormType('SF85'));
    sf86Btn.addEventListener('click', () => setFormType('SF86'));
    validateBtn.addEventListener('click', runValidation);
    clearBtn.addEventListener('click', () => {
      void clearReviewSession();
    });
    pdfFile.addEventListener('change', () => {
      setSelectedFile(pdfFile.files && pdfFile.files[0] ? pdfFile.files[0] : null);
    });

    ['dragenter', 'dragover'].forEach((eventName) => {
      dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.add('active');
      });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
      dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.remove('active');
      });
    });

    dropZone.addEventListener('drop', (event) => {
      const files = event.dataTransfer.files;
      if (files && files.length) {
        setSelectedFile(files[0]);
      }
    });
  </script>
</body>
</html>"""


def _header_value(headers: Optional[Dict[str, str]], name: str, default: str = "") -> str:
    if not headers:
        return default
    normalized_name = name.lower().replace("_", "-")
    normalized_headers = {
        key.lower().replace("_", "-"): value
        for key, value in headers.items()
    }
    return normalized_headers.get(normalized_name, default)


def handle_request(method: str, path: str, body: bytes = b"", headers: Optional[Dict[str, str]] = None) -> Tuple[int, Dict[str, Any]]:
    headers = headers or {}
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
    if method == "POST" and path == "/validate-pdf":
        try:
            result = audit_pdf(body, form_type=_header_value(headers, "X-Form-Type", "SF86"))
            session_id = _header_value(headers, "X-Session-Id", "")
            if session_id:
                result["ledger_proof"] = build_ledger_payload(result, session_id)
        except Exception as exc:
            return HTTPStatus.BAD_REQUEST, {"error": f"PDF audit error: {exc}"}
        return HTTPStatus.OK, result
    if method == "POST" and path == "/clear-session":
        session_id = _header_value(headers, "X-Session-Id", "")
        cleared = clear_session_material(session_id) if session_id else False
        return HTTPStatus.OK, {"cleared": cleared}
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
        status, payload = handle_request("POST", self.path, raw, headers={key: value for key, value in self.headers.items()})
        del raw
        self._send_json(status, payload)

    def log_message(self, format: str, *args: object) -> None:
        """Suppress request logging to avoid copying request payload context to logs."""
        return

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        code, body = _json_response(status, payload)
        self._send_bytes(code, body, "application/json")

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        for key, value in _privacy_headers(content_type, len(body)).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


def serve() -> None:
    port = int(os.environ.get("PORT", "8000"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), ValidatorRequestHandler)
    print("Serving SF-85/86 validator on port %s" % port)
    httpd.serve_forever()


if __name__ == "__main__":
    serve()
