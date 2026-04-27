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
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
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
