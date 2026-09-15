"""Bo thuc thi tool dung chung cho moi node tool. Owner: Nguoi C.

Moi lan goi tool deu di qua day de bao dam ba thu:
  1. retry dung chinh sach o src/tools/retry.py,
  2. failure injection cua AutoEval khong phai sua code tool,
  3. mot phan tu audit trail duoc ghi vao state["tool_results"].

confirm_order CO Y khong nam trong TOOL_REGISTRY: plan khong duoc phep chot
don. Hanh dong hau qua cao chi di qua node confirm_gate (SYSTEM-RULES.md muc 3).
"""

import time

from src.graph_state import AgentState, tool_result_entry
from src.logging_utils.tracer import log_event, new_trace_id
from src.tools.retry import call_with_retry
from src.tools.supplier_tools import compare_price, get_supplier_detail, search_suppliers

TOOL_REGISTRY = {
    "search_suppliers": search_suppliers,
    "get_supplier_detail": get_supplier_detail,
    "compare_price": compare_price,
}

# error_type hop le de inject - dung dung 4 gia tri cua hop dong loi.
# Anh xa 4 tinh huong PDF muc 2.1.3:
#   timeout            -> tool qua han
#   tool_unavailable   -> HTTP 429/5xx, nguon khong truy cap duoc
#   no_match           -> nguon tra du lieu rong
#   invalid_input      -> tham so sai
INJECTABLE_ERROR_TYPES = {"timeout", "tool_unavailable", "no_match", "invalid_input"}


def run_tool(state: AgentState, tool_name: str, params: dict,
             step_id: int | None = None) -> tuple[dict, dict]:
    """Goi 1 tool, tra ve (ket qua tool, phan tu audit trail).

    Ham nay khong bao gio raise: loi ha tang duoc bien thanh loi dung format
    hop dong de B re-plan duoc thay vi lam sap ca graph.
    """
    trace_id = state.get("trace_id") or new_trace_id()
    tool_func = TOOL_REGISTRY.get(tool_name)

    if tool_func is None:
        result = {
            "error": True,
            "error_type": "tool_unavailable",
            "message": f"Khong co tool ten '{tool_name}' trong TOOL_REGISTRY",
        }
        entry = tool_result_entry(tool_name, params, "error", result, 0.0, trace_id,
                                  error_type="tool_unavailable", step_id=step_id)
        log_event(trace_id, "tool_unknown", tool=tool_name)
        return result, entry

    call_kwargs = dict(params)
    injected = (state.get("inject") or {}).get(tool_name)
    if injected in INJECTABLE_ERROR_TYPES:
        call_kwargs["_simulate_error"] = injected
        log_event(trace_id, "failure_injected", tool=tool_name, error_type=injected)

    stats: dict = {}
    started = time.perf_counter()
    try:
        result = call_with_retry(tool_func, stats=stats, **call_kwargs)
    except Exception as exc:  # noqa: BLE001 - tool hong van phai tra dung format loi
        result = {
            "error": True,
            "error_type": "tool_unavailable",
            "message": f"{tool_name} nem ngoai le: {exc.__class__.__name__}: {exc}",
        }

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    is_error = isinstance(result, dict) and result.get("error") is True
    entry = tool_result_entry(
        tool=tool_name,
        params=params,
        status="error" if is_error else "ok",
        result=result,
        latency_ms=latency_ms,
        trace_id=trace_id,
        attempts=stats.get("attempts", 1),
        error_type=result.get("error_type") if is_error else None,
        step_id=step_id,
    )
    return result, entry
