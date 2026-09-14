"""Cac node tool - Owner: Nguoi C. Dang la NODE GIA, thay ruot o Task 7-9."""

from src.graph_state import AgentState, tool_result_entry


def _stub_entry(tool: str, state: AgentState) -> dict:
    return tool_result_entry(
        tool=tool,
        params={},
        status="ok",
        result={},
        latency_ms=0.0,
        trace_id=state.get("trace_id", ""),
    )


def tool_search(state: AgentState) -> dict:
    return {"tool_results": [_stub_entry("search_suppliers", state)], "candidates": []}


def tool_compare(state: AgentState) -> dict:
    return {"tool_results": [_stub_entry("compare_price", state)], "candidates": []}


def tool_detail(state: AgentState) -> dict:
    return {"tool_results": [_stub_entry("get_supplier_detail", state)], "candidates": []}


def confirm_gate(state: AgentState) -> dict:
    return {"pending_confirmation": None}


for _node in (tool_search, tool_compare, tool_detail, confirm_gate):
    _node.__stub__ = True
