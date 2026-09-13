"""Trace ID, logging, che du lieu nhay cam.

Owner: Nguoi C
"""

import logging
import time
import uuid

SENSITIVE_KEYS = {
    "api_key", "google_api_key", "anthropic_api_key",
    "password", "token", "access_token", "refresh_token", "secret",
}

logger = logging.getLogger("procurement_agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(name)s:%(message)s")


def new_trace_id() -> str:
    return uuid.uuid4().hex


def redact(payload: dict) -> dict:
    return {k: ("***" if k.lower() in SENSITIVE_KEYS else v) for k, v in payload.items()}


def log_event(trace_id: str, event: str, **fields) -> None:
    logger.info("[%s] %s %s", trace_id, event, redact(fields))


def audit_entry(trace_id: str, tool: str, params: dict, status: str, latency_ms: float, **extra) -> dict:
    """Audit log entry chuan cho 1 lan goi tool (SYSTEM-RULES.md muc 6). params/extra
    luon di qua redact() truoc khi tra ve/ghi log."""
    entry = {
        "trace_id": trace_id,
        "tool": tool,
        "params": redact(params or {}),
        "status": status,
        "latency_ms": latency_ms,
    }
    entry.update(redact(extra))
    return entry


def log_tool_call(trace_id: str, tool: str, start: float, status: str, params: dict | None = None,
                   **extra) -> dict:
    """Tinh latency tu `start` (time.perf_counter()), ghi 1 audit log entry cho tool_call_end
    va tra ve entry do (de test/truy vet)."""
    entry = audit_entry(trace_id, tool, params, status, round((time.perf_counter() - start) * 1000, 2), **extra)
    logger.info("[%s] tool_call_end %s", trace_id, entry)
    return entry
