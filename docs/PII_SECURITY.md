# PII Security Boundary

This validator is designed for session-only review of SF-85/SF-86 material.

## Data Handling

- Uploaded PDFs are read from the HTTP request body and audited in memory.
- Uploaded PDF bytes are not written by the application to disk.
- The browser clears the selected PDF file reference after validation and on `Clear`.
- The server zeroes the request byte buffer and the internal PDF parsing buffer on a best-effort basis after each request.
- Findings returned to the browser can include short snippets from the uploaded form so the reviewer can identify the issue.

## Cache and Session Cleanup

- Every HTTP response includes `Cache-Control: no-store`, `Pragma: no-cache`, and `Expires: 0`.
- The `Clear` action calls `/clear-session`, rotates the browser session ID, and sends `Clear-Site-Data: "cache", "storage"`.
- Browser tab close sends a best-effort `/clear-session` beacon.
- Server ledger salts and signing keys are held in memory only.
- Server session material expires automatically after `SF_VALIDATOR_SESSION_TTL_SECONDS` seconds of inactivity.
- Server startup and shutdown clear the app-specific temp directory set by `SF_VALIDATOR_TEMP_DIR`.

## Access Control

- Set `SF_VALIDATOR_AUTH_USERNAME` and `SF_VALIDATOR_AUTH_PASSWORD` to require HTTP Basic Auth for all non-health routes.
- Leave both variables unset only for local, private development.
- Use HTTPS whenever Basic Auth is enabled, because Basic Auth credentials are not encrypted without TLS.

## Operational Requirements

- Run behind HTTPS when exposed beyond localhost.
- Do not enable reverse-proxy request body logging.
- Keep the app temp directory scoped to this service only.
- Prefer the Docker/Compose deployment because it runs as a non-root user, disables Python bytecode writes, uses no pip cache, and mounts `/tmp` as tmpfs.
