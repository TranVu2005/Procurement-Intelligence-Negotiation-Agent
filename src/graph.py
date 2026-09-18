"""Dung LangGraph StateGraph va diem vao run_request(). Owner: Nguoi C.

So do luong: architecture.md muc 2.2. LLM chi duoc goi o perceive va respond;
moi node con lai la Python thuan, nen so lan goi LLM tren 1 request la con so
co dinh dem duoc.
"""

import time
import json
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from src.graph_state import MAX_REPLAN, AgentState, new_state
from src.logging_utils.tracer import log_event, write_run_record
from src.memory.db import (
    append_conversation,
    init_db,
    load_session,
    save_session,
    session_exists,
)
from src.nodes.perceive import perceive
from src.perception.parser import InvalidProductTypeError, MissingFieldError
from src.nodes.reasoning import (
    diagnose, filter_hard, graceful_fail, plan, replan, respond_limits, score_rank, verify_output,
)
from src.nodes.respond import respond
from src.nodes.tools import confirm_gate, tool_compare, tool_detail, tool_search

# Khoi tao DB 1 lan khi module nap — CREATE TABLE IF NOT EXISTS, idempotent.
# Loi DB khong duoc lam gay import hay pipeline.
try:
    init_db()
except Exception:  # noqa: BLE001
    pass

# Duong dai nhat: tool_search -> filter_hard -> score_rank -> verify_output ->
# diagnose -> replan (6 node) lap (MAX_REPLAN + 1) lan (1 lan dau + MAX_REPLAN lan
# replan) truoc khi cham tran va di graceful_fail, cong perceive/plan/graceful_fail/
# confirm_gate o hai dau. Smoke test thuc te (ngan sach bat kha thi) cham
# GraphRecursionError o muc cu (25) vi duong nay dai dung 25-26 buoc; de bien do cho
# cac nhanh khac (confirm_gate, respond), dat cao hon han muc toi thieu do duoc.
RECURSION_LIMIT = 6 * (MAX_REPLAN + 1) + 16

_INTENT_ENTRY = {
    "search_new": "plan",
    "compare_specific": "tool_compare",
    "supplier_detail": "tool_detail",
    "out_of_scope": "respond_limits",
}

# Sau replan phai quay lai DUNG node tool cua intent (PHAN-CONG-CON-LAI muc 5.1).
# Intent khong co trong bang (out_of_scope, intent la) -> khong goi tool nao.
_REPLAN_ENTRY = {
    "search_new": "tool_search",
    "compare_specific": "tool_compare",
    "supplier_detail": "tool_detail",
}

_NODES = {
    "perceive": perceive,
    "plan": plan,
    "tool_search": tool_search,
    "tool_compare": tool_compare,
    "tool_detail": tool_detail,
    "filter_hard": filter_hard,
    "score_rank": score_rank,
    "verify_output": verify_output,
    "diagnose": diagnose,
    "replan": replan,
    "respond": respond,
    "respond_limits": respond_limits,
    "graceful_fail": graceful_fail,
    "confirm_gate": confirm_gate,
}


def route_intent(state: AgentState) -> str:
    """Intent la gi cung phai ra mot node hop le. Intent la -> neu gioi han.

    Perception bao thieu/sai thong tin (status=needs_input) -> dung lai hoi
    nguoi dung, khong goi tool nao.
    """
    if state.get("status") == "needs_input":
        return "graceful_fail"
    return _INTENT_ENTRY.get(state.get("intent"), "respond_limits")


def guard_perceive(func):
    """Boc node perceive cua A ma khong sua file cua A.

    1. Loi do NGUOI DUNG (thieu field, san pham ngoai catalog, so <= 0) -> hoi
       lai (status=needs_input), khong bien thanh loi he thong. SYSTEM-RULES
       muc 3: khong tu dien thong tin con thieu.
    2. Chep req["session_id"] (parser tu sinh o luot dau) len state, de
       run_request luu dung phien va tra session_id cho luot sau.
    JSONDecodeError (LLM tra JSON hong) la loi he thong -> nem tiep cho
    run_request bien thanh graceful_fail.
    """
    def node(state: AgentState) -> dict:
        try:
            out = dict(func(state) or {})
        except (MissingFieldError, InvalidProductTypeError) as exc:
            return {"status": "needs_input", "answer": str(exc), "llm_calls": 1}
        except json.JSONDecodeError:
            raise
        except ValueError as exc:
            return {"status": "needs_input",
                    "answer": f"Thong tin chua hop le: {exc}. Vui long nhap lai.",
                    "llm_calls": 1}
        req = out.get("req") or {}
        if not state.get("session_id") and req.get("session_id"):
            out["session_id"] = req["session_id"]
        return out
    return node


def route_after_filter(state: AgentState) -> str:
    if state.get("status") == "needs_input":
        # Thieu thong tin phai do nguoi dung cung cap; re-plan khong the tu bu
        return "graceful_fail"
    if state.get("candidates"):
        return "score_rank"
    if state.get("replan_count", 0) < MAX_REPLAN:
        return "diagnose"
    return "graceful_fail"


def route_after_verify(state: AgentState) -> str:
    if (state.get("verdict") or {}).get("passed"):
        return "respond"
    if state.get("replan_count", 0) < MAX_REPLAN:
        return "diagnose"
    return "graceful_fail"


def route_after_replan(state: AgentState) -> str:
    if state.get("status") == "needs_input":
        # replan khong lap duoc ke hoach moi -> can nguoi dung, khong goi tool lai
        return "graceful_fail"
    return _REPLAN_ENTRY.get(state.get("intent"), "graceful_fail")


def build_graph(overrides: dict | None = None):
    """overrides: {ten_node: ham} de test thay node that bang node gia."""
    nodes = {**_NODES, **(overrides or {})}

    graph = StateGraph(AgentState)
    for name, func in nodes.items():
        graph.add_node(name, guard_perceive(func) if name == "perceive" else func)

    graph.add_edge(START, "perceive")
    graph.add_conditional_edges("perceive", route_intent, {
        "plan": "plan",
        "tool_compare": "tool_compare",
        "tool_detail": "tool_detail",
        "respond_limits": "respond_limits",
        "graceful_fail": "graceful_fail",
    })

    graph.add_edge("plan", "tool_search")
    for entry in ("tool_search", "tool_compare", "tool_detail"):
        graph.add_edge(entry, "filter_hard")

    graph.add_conditional_edges("filter_hard", route_after_filter, {
        "score_rank": "score_rank",
        "diagnose": "diagnose",
        "graceful_fail": "graceful_fail",
    })
    graph.add_edge("diagnose", "replan")
    graph.add_conditional_edges("replan", route_after_replan, {
        "tool_search": "tool_search",
        "tool_compare": "tool_compare",
        "tool_detail": "tool_detail",
        "graceful_fail": "graceful_fail",
    })

    graph.add_edge("score_rank", "verify_output")
    graph.add_conditional_edges("verify_output", route_after_verify, {
        "respond": "respond",
        "diagnose": "diagnose",
        "graceful_fail": "graceful_fail",
    })

    graph.add_edge("respond", "confirm_gate")
    graph.add_edge("confirm_gate", END)
    graph.add_edge("respond_limits", END)
    graph.add_edge("graceful_fail", END)

    return graph.compile()


@lru_cache(maxsize=1)
def get_graph():
    return build_graph()


def run_request(
    user_input: str,
    session_id: str | None = None,
    _inject: dict | None = None,
    overrides: dict | None = None,
) -> dict:
    """Chay 1 request tu dau den cuoi, tra ve state cuoi cung.

    _inject: {"<ten_tool>": "<error_type>"} - bat loi gia lap cho AutoEval
    (architecture.md muc 5.4), khong dung o duong chay that.
    Ham nay khong bao gio raise: moi exception duoc bat thanh graceful_fail
    de mot case hong khong lam gay ca luot AutoEval hoac load test.

    Memory semantics (A chot, 2026-09-17):
    - Neu session_id da ton tai trong DB: load req cu -> perceive goi update_state()
    - Neu session moi / None: perceive goi parse_request() tao state moi
    - Sau moi luot: save req va ghi agent answer vao DB
    """
    graph = build_graph(overrides) if overrides else get_graph()

    # Load session cu neu co
    existing_req: dict = {}
    if session_id:
        try:
            if session_exists(session_id):
                existing_req = load_session(session_id) or {}
        except Exception:  # noqa: BLE001
            existing_req = {}  # DB loi thi coi nhu turn dau, khong gay crash

    state = new_state(user_input, session_id=session_id, inject=_inject, req=existing_req)
    log_event(state["trace_id"], "request_start", session_id=state["session_id"],
              user_input=user_input)

    started = time.perf_counter()
    try:
        final = dict(graph.invoke(state, config={"recursion_limit": RECURSION_LIMIT}))
    except Exception as exc:  # noqa: BLE001 - bien loi thanh ket qua, khong lam gay eval
        final = dict(state)
        final["status"] = "graceful_fail"
        final["error"] = f"{exc.__class__.__name__}: {exc}"
        final["answer"] = (
            "He thong gap loi khi xu ly yeu cau nay va da dung lai thay vi tra ket qua "
            "khong dang tin."
        )

    final["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    final.setdefault("status", "graceful_fail")
    log_event(state["trace_id"], "request_end", status=final["status"],
              llm_calls=final.get("llm_calls", 0), tool_calls=len(final.get("tool_results", [])),
              latency_ms=final["latency_ms"])
    write_run_record(final)

    # Luu state va agent answer vao DB (best-effort — khong duoc lam gay response)
    sid = final.get("session_id") or session_id or ""
    if sid:
        try:
            req_to_save = final.get("req")
            if req_to_save:
                save_session(sid, req_to_save)
            agent_answer = final.get("answer", "")
            if agent_answer:
                append_conversation(sid, "agent", agent_answer)
        except Exception:  # noqa: BLE001
            pass  # DB loi khong duoc lam gay response tra ve nguoi dung

    return final
