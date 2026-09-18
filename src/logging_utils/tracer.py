"""Trace ID, logging, che du lieu nhay cam.

Owner: Nguoi C
"""

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

SENSITIVE_KEYS = {
    "api_key", "google_api_key", "anthropic_api_key", "openrouter_api_key",
    "password", "token", "access_token", "refresh_token", "secret",
    "authorization", "x-api-key", "api-key",
}

# Chuoi co hinh dang API key (Google, OpenRouter/OpenAI, Anthropic) - che ca khi
# nam giua van ban tu do, vd nguoi dung dan key vao cau hoi.
# Chan chu/so dung truoc: slug URL nhu ".../task-ban-lam-viec-go-..." khong duoc bi che.
_SECRET_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:AIza[0-9A-Za-z_\-]{30,}|sk-(?:or-|ant-)?[0-9A-Za-z_\-]{20,})"
)

logger = logging.getLogger("procurement_agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(name)s:%(message)s")

# Ghi ra file de doc lai duoc sau khi chay - stdout khong tai lap duoc
# (architecture.md muc 3.6). Doi cho ghi bang bien moi truong AGENT_LOG_DIR.
LOG_DIR = Path(os.getenv("AGENT_LOG_DIR") or (Path(__file__).resolve().parents[2] / "logs"))


def new_trace_id() -> str:
    return uuid.uuid4().hex


def _redact_value(value):
    if isinstance(value, dict):
        return {
            key: ("***" if isinstance(key, str) and key.lower() in SENSITIVE_KEYS
                  else _redact_value(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return _SECRET_PATTERN.sub("***", value)
    return value


def redact(payload: dict) -> dict:
    """Ban sao da che secret: key nhay cam o moi cap long nhau va chuoi co
    hinh dang API key. Khong sua payload goc."""
    return _redact_value(payload)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _append_jsonl(path: Path, record: dict) -> Path:
    """Ghi 1 dong JSON. Loi ghi file khong duoc lam gay request dang chay."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError as exc:  # noqa: BLE001 - log hong thi van phai tra loi nguoi dung
        logger.warning("khong ghi duoc log file %s: %s", path, exc)
    return path


def write_jsonl(trace_id: str, event: str, payload: dict) -> Path:
    """Noi them 1 dong vao logs/<trace_id>.jsonl. payload da phai qua redact()."""
    record = {"ts": _now_iso(), "trace_id": trace_id, "event": event, **payload}
    return _append_jsonl(LOG_DIR / f"{trace_id}.jsonl", record)


def write_run_record(final: dict) -> Path:
    """Mot dong tong ket cho 1 request, ghi vao logs/runs.jsonl.

    Day la nguon so lieu cho P50/P95, so lan goi LLM trung binh va chi phi
    (architecture.md muc 5.5, 5.7). Chi ghi so dem, khong ghi payload tool.
    """
    tool_results = final.get("tool_results") or []
    record = {
        "ts": _now_iso(),
        "trace_id": final.get("trace_id"),
        "session_id": final.get("session_id"),
        "intent": final.get("intent"),
        "status": final.get("status"),
        "llm_calls": final.get("llm_calls", 0),
        "tool_calls": len(tool_results),
        "tool_errors": sum(1 for e in tool_results if e.get("status") == "error"),
        "replan_count": final.get("replan_count", 0),
        "tokens_in": final.get("tokens_in", 0),
        "tokens_out": final.get("tokens_out", 0),
        "latency_ms": final.get("latency_ms"),
        "ttft_ms": final.get("ttft_ms"),
    }
    return _append_jsonl(LOG_DIR / "runs.jsonl", record)


def log_event(trace_id: str, event: str, **fields) -> None:
    payload = redact(fields)
    logger.info("[%s] %s %s", trace_id, event, payload)
    write_jsonl(trace_id, event, payload)


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
