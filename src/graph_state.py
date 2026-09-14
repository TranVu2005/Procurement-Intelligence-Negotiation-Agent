"""State dung chung cho LangGraph pipeline (architecture.md muc 2.1).

Owner: Nguoi C. A va B chi DOC cac khoa nay; muon them khoa moi thi bao C
truoc va cap nhat interface-contracts.md (SYSTEM-RULES.md muc 7).

Khoa nao co reducer `operator.add` thi node phai tra ve PHAN CONG THEM,
khong tra ve gia tri tuyet doi:
    return {"llm_calls": 1}        # dung  -> cong them 1
    return {"llm_calls": total}    # sai   -> cong don hai lan
"""

import operator
from typing import Annotated, Any, Literal, TypedDict

from src.logging_utils.tracer import new_trace_id, redact
from src.reasoning.planner import MAX_REPLAN_COUNT as MAX_REPLAN

Intent = Literal["search_new", "compare_specific", "supplier_detail", "out_of_scope"]

# status cuoi cung cua 1 request - AutoEval doc truong nay (oracle.expect_status)
Status = Literal["success", "graceful_fail", "needs_confirmation", "needs_input", "out_of_scope"]


class AgentState(TypedDict, total=False):
    session_id: str
    trace_id: str
    user_input: str
    intent: Intent
    req: dict                                          # state schema cua A
    plan: dict                                         # plan cua B
    tool_results: Annotated[list[dict], operator.add]  # audit trail, cong don
    candidates: list[dict]
    rejected: list[dict]
    ranked: list[dict]
    verdict: dict
    replan_count: int
    answer: str
    pending_confirmation: dict | None
    status: Status
    inject: dict                                       # failure injection cho AutoEval
    llm_calls: Annotated[int, operator.add]
    tokens_in: Annotated[int, operator.add]
    tokens_out: Annotated[int, operator.add]


def new_state(
    user_input: str,
    session_id: str | None = None,
    trace_id: str | None = None,
    inject: dict | None = None,
) -> AgentState:
    """State khoi tao cho 1 request. Moi khoa co reducer deu bat dau tu 0/[]."""
    return {
        "session_id": session_id or "",
        "trace_id": trace_id or new_trace_id(),
        "user_input": user_input,
        "req": {},
        "plan": {},
        "tool_results": [],
        "candidates": [],
        "rejected": [],
        "ranked": [],
        "verdict": {},
        "replan_count": 0,
        "answer": "",
        "pending_confirmation": None,
        "inject": inject or {},
        "llm_calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
    }


def tool_result_entry(
    tool: str,
    params: dict,
    status: str,
    result: Any,
    latency_ms: float,
    trace_id: str,
    attempts: int = 1,
    error_type: str | None = None,
    step_id: int | None = None,
) -> dict:
    """Mot phan tu cua state['tool_results'].

    Day la don vi AutoEval dem de tinh Tool Call Success Rate va la noi
    verify_output truy nguoc bang chung ve. Doi shape nay = doi hop dong,
    phai bao A va B (interface-contracts.md muc 3).

    status: "ok" | "error" | "blocked"
        - "blocked": tool bi chan co chu dich (confirm_order chua duoc xac nhan).
          KHONG tinh la that bai khi do Tool Call Success Rate.
    """
    return {
        "step_id": step_id,
        "tool": tool,
        "params": redact(params or {}),
        "status": status,
        "latency_ms": latency_ms,
        "attempts": attempts,
        "error_type": error_type,
        "result": result,
        "trace_id": trace_id,
    }
