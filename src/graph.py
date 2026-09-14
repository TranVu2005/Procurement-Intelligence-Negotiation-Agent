"""Dung LangGraph StateGraph va diem vao run_request(). Owner: Nguoi C.

So do luong: architecture.md muc 2.2. LLM chi duoc goi o perceive va respond;
moi node con lai la Python thuan, nen so lan goi LLM tren 1 request la con so
co dinh dem duoc.
"""

import time
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from src.graph_state import MAX_REPLAN, AgentState, new_state
from src.logging_utils.tracer import log_event
from src.nodes.perceive import perceive
from src.nodes.reasoning import (
    diagnose, filter_hard, graceful_fail, plan, replan, respond_limits, score_rank, verify_output,
)
from src.nodes.respond import respond
from src.nodes.tools import confirm_gate, tool_compare, tool_detail, tool_search

# Vong lap tool_search -> filter_hard -> diagnose -> replan -> tool_search chay
# toi da MAX_REPLAN lan; 25 du rong cho ca truong hop xau nhat.
RECURSION_LIMIT = 25

_INTENT_ENTRY = {
    "search_new": "plan",
    "compare_specific": "tool_compare",
    "supplier_detail": "tool_detail",
    "out_of_scope": "respond_limits",
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
    """Intent la gi cung phai ra mot node hop le. Intent la -> neu gioi han."""
    return _INTENT_ENTRY.get(state.get("intent"), "respond_limits")


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


def build_graph(overrides: dict | None = None):
    """overrides: {ten_node: ham} de test thay node that bang node gia."""
    nodes = {**_NODES, **(overrides or {})}

    graph = StateGraph(AgentState)
    for name, func in nodes.items():
        graph.add_node(name, func)

    graph.add_edge(START, "perceive")
    graph.add_conditional_edges("perceive", route_intent, {
        "plan": "plan",
        "tool_compare": "tool_compare",
        "tool_detail": "tool_detail",
        "respond_limits": "respond_limits",
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
    graph.add_edge("replan", "tool_search")

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
    """
    graph = build_graph(overrides) if overrides else get_graph()
    state = new_state(user_input, session_id=session_id, inject=_inject)
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
    return final
