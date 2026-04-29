"""Hash-only ledger proof helpers for session-scoped validation reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from typing import Any, Dict, Mapping


SECTION_IDS = tuple(str(number) for number in range(1, 30))
DEFAULT_SESSION_TTL_SECONDS = 60 * 60


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _zeroize(buffer: bytearray) -> None:
    for index in range(len(buffer)):
        buffer[index] = 0


@dataclass
class _SessionSecrets:
    salt: bytearray
    signing_key: bytearray
    last_accessed: float

    @property
    def key_fingerprint(self) -> str:
        return _sha256_hex(bytes(self.signing_key))[:16]

    def clear(self) -> None:
        _zeroize(self.salt)
        _zeroize(self.signing_key)


class LedgerSessionStore:
    """Holds per-session salt and signing material in memory only."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, _SessionSecrets] = {}
        self._ttl_seconds = _session_ttl_seconds()

    def get_or_create(self, session_id: str) -> _SessionSecrets:
        with self._lock:
            self._clear_expired_locked()
            secrets_state = self._sessions.get(session_id)
            if secrets_state is None:
                secrets_state = _SessionSecrets(
                    salt=bytearray(secrets.token_bytes(32)),
                    signing_key=bytearray(secrets.token_bytes(32)),
                    last_accessed=time.monotonic(),
                )
                self._sessions[session_id] = secrets_state
            else:
                secrets_state.last_accessed = time.monotonic()
            return secrets_state

    def clear(self, session_id: str) -> bool:
        with self._lock:
            secrets_state = self._sessions.pop(session_id, None)
        if secrets_state is None:
            return False
        secrets_state.clear()
        return True

    def clear_all(self) -> int:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for secrets_state in sessions:
            secrets_state.clear()
        return len(sessions)

    def clear_expired(self) -> int:
        with self._lock:
            return self._clear_expired_locked()

    def _clear_expired_locked(self) -> int:
        if self._ttl_seconds <= 0:
            return 0
        cutoff = time.monotonic() - self._ttl_seconds
        expired_ids = [
            session_id
            for session_id, secrets_state in self._sessions.items()
            if secrets_state.last_accessed < cutoff
        ]
        for session_id in expired_ids:
            self._sessions.pop(session_id).clear()
        return len(expired_ids)


def _session_ttl_seconds() -> int:
    raw_value = os.environ.get("SF_VALIDATOR_SESSION_TTL_SECONDS", str(DEFAULT_SESSION_TTL_SECONDS))
    try:
        return max(0, int(raw_value))
    except ValueError:
        return DEFAULT_SESSION_TTL_SECONDS


SESSION_STORE = LedgerSessionStore()


def _section_findings(report: Mapping[str, Any], section_id: str) -> list[Mapping[str, Any]]:
    findings = report.get("findings", [])
    if not isinstance(findings, list):
        return []
    return [
        finding
        for finding in findings
        if isinstance(finding, Mapping) and str(finding.get("section", "")).startswith(section_id)
    ]


def _section_payload(report: Mapping[str, Any], section_id: str) -> Dict[str, Any]:
    findings = _section_findings(report, section_id)
    return {
        "form_type": report.get("form_type"),
        "section": section_id,
        "finding_count": len(findings),
        "findings": findings,
    }


def build_report_hash(report: Mapping[str, Any]) -> str:
    return _sha256_hex(_canonical_json(report))


def build_section_hashes(report: Mapping[str, Any], salt: bytes) -> Dict[str, str]:
    section_hashes: Dict[str, str] = {}
    for section_id in SECTION_IDS:
        payload = _section_payload(report, section_id)
        section_hashes[section_id] = _sha256_hex(salt + _canonical_json(payload))
    return section_hashes


def build_ledger_payload(report: Mapping[str, Any], session_id: str) -> Dict[str, Any]:
    session_secrets = SESSION_STORE.get_or_create(session_id)
    payload: Dict[str, Any] = {
        "algorithm": "sha256+hmac-sha256",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "form_type": report.get("form_type", "unknown"),
        "report_hash_sha256": build_report_hash(report),
        "section_hashes": build_section_hashes(report, bytes(session_secrets.salt)),
        "key_fingerprint": session_secrets.key_fingerprint,
    }
    payload_bytes = _canonical_json(payload)
    payload["signature"] = hmac.new(bytes(session_secrets.signing_key), payload_bytes, hashlib.sha256).hexdigest()
    return payload


def clear_session_material(session_id: str) -> bool:
    return SESSION_STORE.clear(session_id)


def clear_all_session_material() -> int:
    return SESSION_STORE.clear_all()


def clear_expired_session_material() -> int:
    return SESSION_STORE.clear_expired()
