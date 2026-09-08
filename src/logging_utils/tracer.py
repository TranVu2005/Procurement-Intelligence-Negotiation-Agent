"""Trace ID, logging, che du lieu nhay cam.

Owner: Nguoi C
"""

import logging
import uuid

SENSITIVE_KEYS = {"api_key", "anthropic_api_key", "password", "token"}

logger = logging.getLogger("procurement_agent")
logging.basicConfig(level=logging.INFO)


def new_trace_id() -> str:
    return uuid.uuid4().hex


def redact(payload: dict) -> dict:
    return {k: ("***" if k.lower() in SENSITIVE_KEYS else v) for k, v in payload.items()}


def log_event(trace_id: str, event: str, **fields) -> None:
    logger.info("[%s] %s %s", trace_id, event, redact(fields))
