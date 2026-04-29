"""HTTP interface for session-only SF-85/SF-86 validation."""

from __future__ import annotations

import atexit
import base64
import hmac
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import signal
from typing import Any, Dict, Optional, Tuple, Union

from .cli import run_validation
from .ledger import build_ledger_payload, clear_all_session_material, clear_expired_session_material, clear_session_material
from .pdf_audit import audit_pdf
from .schema import SchemaValidationError, input_schema


DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _privacy_headers(content_type: str, content_length: int, clear_site_data: bool = False) -> Dict[str, str]:
    headers = {
        "Content-Type": content_type,
        "Content-Length": str(content_length),
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0, private",
        "Pragma": "no-cache",
        "Expires": "0",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        "Content-Security-Policy": "default-src 'self'; base-uri 'none'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'; img-src 'self' data:; object-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    }
    if clear_site_data:
        headers["Clear-Site-Data"] = '"cache", "storage"'
    return headers


def _auth_credentials() -> Tuple[str, str]:
    return (
        os.environ.get("SF_VALIDATOR_AUTH_USERNAME", "").strip(),
        os.environ.get("SF_VALIDATOR_AUTH_PASSWORD", ""),
    )


def _auth_enabled() -> bool:
    username, password = _auth_credentials()
    return bool(username and password)


def _authorized(headers: Optional[Dict[str, str]]) -> bool:
    username, password = _auth_credentials()
    if not username or not password:
        return True
    auth_value = _header_value(headers, "Authorization", "")
    if not auth_value.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(auth_value.split(" ", 1)[1], validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    supplied_username, separator, supplied_password = decoded.partition(":")
    if not separator:
        return False
    return hmac.compare_digest(supplied_username, username) and hmac.compare_digest(supplied_password, password)


def _json_response(status: int, payload: Dict[str, Any]) -> Tuple[int, bytes]:
    body = json.dumps(payload, indent=2).encode("utf-8")
    return status, body


def _html_response(status: int, body: str) -> Tuple[int, bytes, str]:
    return status, body.encode("utf-8"), "text/html; charset=utf-8"


def _cleanup_server_state() -> None:
    clear_all_session_material()
    _clear_private_temp_dir(create=False)


def _max_request_body_bytes() -> int:
    raw_value = os.environ.get("SF_VALIDATOR_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
    try:
        return max(1, int(raw_value))
    except ValueError:
        return DEFAULT_MAX_UPLOAD_BYTES


def _clear_bytes(buffer: bytearray) -> None:
    for index in range(len(buffer)):
        buffer[index] = 0


def _private_temp_dir() -> Optional[Path]:
    configured = os.environ.get("SF_VALIDATOR_TEMP_DIR", "").strip()
    if not configured:
        return None
    path = Path(configured).expanduser().resolve()
    unsafe_paths = {Path("/").resolve(), Path("/tmp").resolve(), Path.home().resolve()}
    if path in unsafe_paths:
        raise RuntimeError("SF_VALIDATOR_TEMP_DIR must point to an app-specific directory")
    return path


def _clear_private_temp_dir(create: bool) -> None:
    path = _private_temp_dir()
    if path is None:
        return
    shutil.rmtree(path, ignore_errors=True)
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.environ["TMPDIR"] = str(path)


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
      min-height: 320px;
      max-height: 420px;
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
      const pdfBuffer = await file.arrayBuffer();
      try {
        const response = await fetch('/validate-pdf', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/pdf',
            'X-Form-Type': formType,
            'X-Session-Id': activeSessionId
          },
          body: pdfBuffer,
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
      } finally {
        new Uint8Array(pdfBuffer).fill(0);
      }
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

    function releaseSelectedPdfFile(message = 'PDF released from browser memory after validation.') {
      selectedPdfFile = null;
      pdfFile.value = '';
      fileName.textContent = message;
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
        releaseSelectedPdfFile('PDF released from browser memory after failed validation.');
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
        releaseSelectedPdfFile('PDF released from browser memory after failed validation.');
        setStatus('Validation failed.', 'bad');
        reviewList.innerHTML = `<div class="review-item"><div class="review-item-title">Request Error</div><div>${result.body.error || 'Unknown error'}</div></div>`;
        return;
      }

      releaseSelectedPdfFile();
      const findings = result.body.findings || [];
      totalFlags.textContent = String(result.body.finding_count || findings.length);
      renderReviewItems(findings);
      setStatus(`Validation complete for ${requestFormType}.`, 'good');
    }

    function clearSessionOnPageHide() {
      if (navigator.sendBeacon) {
        navigator.sendBeacon('/clear-session', activeSessionId);
      }
    }

    sf85Btn.addEventListener('click', () => setFormType('SF85'));
    sf86Btn.addEventListener('click', () => setFormType('SF86'));
    validateBtn.addEventListener('click', runValidation);
    clearBtn.addEventListener('click', () => {
      void clearReviewSession();
    });
    window.addEventListener('pagehide', clearSessionOnPageHide);
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


def _session_id(headers: Dict[str, str], body: Union[bytes, bytearray] = b"") -> str:
    raw_session_id = _header_value(headers, "X-Session-Id", "")
    if not raw_session_id and body:
        raw_session_id = bytes(body).decode("utf-8", errors="ignore").strip()
    return raw_session_id if SESSION_ID_RE.fullmatch(raw_session_id) else ""


def handle_request(method: str, path: str, body: Union[bytes, bytearray] = b"", headers: Optional[Dict[str, str]] = None) -> Tuple[int, Dict[str, Any]]:
    headers = headers or {}
    clear_expired_session_material()
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
            session_id = _session_id(headers)
            if session_id:
                result["ledger_proof"] = build_ledger_payload(result, session_id)
        except Exception as exc:
            return HTTPStatus.BAD_REQUEST, {"error": f"PDF audit error: {exc}"}
        return HTTPStatus.OK, result
    if method == "POST" and path == "/clear-session":
        session_id = _session_id(headers, body)
        cleared = clear_session_material(session_id) if session_id else False
        return HTTPStatus.OK, {"cleared": cleared}
    return HTTPStatus.NOT_FOUND, {"error": "Not found"}


class ValidatorRequestHandler(BaseHTTPRequestHandler):
    server_version = "SF86Validator/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health" and not _authorized({key: value for key, value in self.headers.items()}):
            self._send_unauthorized()
            return
        if self.path == "/":
            status, body, content_type = _html_response(HTTPStatus.OK, _index_page())
            self._send_bytes(status, body, content_type)
            return
        status, payload = handle_request("GET", self.path)
        self._send_json(status, payload)

    def do_POST(self) -> None:  # noqa: N802
        if not _authorized({key: value for key, value in self.headers.items()}):
            self._send_unauthorized()
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid Content-Length"})
            return

        if content_length > _max_request_body_bytes():
            self.close_connection = True
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": "Request body exceeds the configured upload limit"},
            )
            return

        raw = bytearray(self.rfile.read(content_length))
        try:
            status, payload = handle_request("POST", self.path, raw, headers={key: value for key, value in self.headers.items()})
        finally:
            _clear_bytes(raw)
            del raw
        self._send_json(status, payload, clear_site_data=self.path == "/clear-session")

    def log_message(self, format: str, *args: object) -> None:
        """Suppress request logging to avoid copying request payload context to logs."""
        return

    def _send_json(self, status: int, payload: Dict[str, Any], clear_site_data: bool = False) -> None:
        code, body = _json_response(status, payload)
        self._send_bytes(code, body, "application/json", clear_site_data=clear_site_data)

    def _send_unauthorized(self) -> None:
        code, body = _json_response(HTTPStatus.UNAUTHORIZED, {"error": "Authentication required"})
        self.send_response(code)
        for key, value in _privacy_headers("application/json", len(body)).items():
            self.send_header(key, value)
        self.send_header("WWW-Authenticate", 'Basic realm="SF-85/86 Validator", charset="UTF-8"')
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, status: int, body: bytes, content_type: str, clear_site_data: bool = False) -> None:
        self.send_response(status)
        for key, value in _privacy_headers(content_type, len(body), clear_site_data=clear_site_data).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


def serve() -> None:
    _clear_private_temp_dir(create=True)
    port = int(os.environ.get("PORT", "8000"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), ValidatorRequestHandler)
    atexit.register(_cleanup_server_state)
    signal.signal(signal.SIGTERM, lambda _signum, _frame: (_cleanup_server_state(), httpd.shutdown()))
    print("Serving SF-85/86 validator on port %s" % port)
    try:
        httpd.serve_forever()
    finally:
        _cleanup_server_state()


if __name__ == "__main__":
    serve()
