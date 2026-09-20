"""Pure helpers that turn AgentState into safe UI view models. Owner: Nguoi B.

The Streamlit app deliberately keeps formatting here so null values, provenance
and simulated-field labels can be unit-tested without starting a web server.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def format_currency(value: Any) -> str:
    """Format a numeric VND value; never invent a value for missing evidence."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "Chưa có dữ liệu"
    return f"{value:,.0f} ₫"


def format_optional(value: Any, suffix: str = "") -> str:
    if value is None or value == "":
        return "Chưa có dữ liệu"
    return f"{value}{suffix}"


def safe_source_url(value: Any) -> str | None:
    """Only expose HTTP(S) provenance links to the browser."""
    if not isinstance(value, str):
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value.strip()


def supplier_view_models(ranked: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Return display-ready supplier cards while preserving ranking order."""
    cards: list[dict[str, Any]] = []
    for index, record in enumerate(ranked or [], start=1):
        simulated = record.get("simulated_fields")
        simulated_fields = [str(item) for item in simulated] if isinstance(simulated, list) else []
        source_url = safe_source_url(record.get("nguon_url"))
        cards.append({
            "rank": index,
            "supplier_id": record.get("MaNCC") or "Chưa có mã",
            "supplier_name": record.get("TenNCC") or "Nhà cung cấp chưa rõ tên",
            "product_type": format_optional(record.get("LoaiSanPham")),
            "unit_price": format_currency(record.get("unit_price", record.get("Gia"))),
            "total_price": format_currency(record.get("total_price")),
            "delivery": format_optional(record.get("ThoiGianGiao"), " ngày"),
            "trust": format_optional(record.get("DiemUyTin"), "/5"),
            "score": format_optional(record.get("leverage_score"), "/100"),
            "source_url": source_url,
            "source_type": record.get("nguon_type") or "Chưa phân loại",
            "simulated_fields": simulated_fields,
            "data_label": "Có trường mô phỏng" if simulated_fields else "Không có trường mô phỏng",
            "score_breakdown": (record.get("explanation") or {}).get("score_breakdown") or {},
            "strengths": (record.get("explanation") or {}).get("strengths") or [],
            "trade_offs": (record.get("explanation") or {}).get("trade_offs") or [],
        })
    return cards


def run_metrics(final: dict[str, Any] | None) -> dict[str, Any]:
    state = final or {}
    verdict = state.get("verdict") or {}
    return {
        "status": state.get("status") or "unknown",
        "intent": state.get("intent") or "unknown",
        "llm_calls": state.get("llm_calls", 0),
        "tool_calls": len(state.get("tool_results") or []),
        "replan_count": state.get("replan_count", 0),
        "latency_ms": state.get("latency_ms", 0),
        "verifier_passed": verdict.get("passed"),
        "trace_id": state.get("trace_id") or "",
    }
