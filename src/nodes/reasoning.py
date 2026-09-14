"""Cac node suy luan - Owner: Nguoi B. Toan bo dang la NODE GIA.

B thay ruot tung ham o Dot 2 (goi vao src/reasoning/planner.py va
src/reasoning/scoring.py da co san), giu nguyen chu ky va cac khoa tra ve,
va xoa dong `<ten_ham>.__stub__` tuong ung.
"""

from src.graph_state import AgentState


def plan(state: AgentState) -> dict:
    """Tra ve: {"plan": dict}. Goi make_plan/make_replan cua planner.py."""
    return {
        "plan": {
            "plan_id": "plan_stub",
            "session_id": state.get("session_id", ""),
            "status": "executing",
            "replan_count": state.get("replan_count", 0),
            "replan_reason": None,
            "steps": [
                {
                    "step_id": 1,
                    "action": "search_suppliers",
                    "params": {"product_type": "ghế văn phòng"},
                    "reason": "stub",
                    "depends_on": [],
                }
            ],
        }
    }


def filter_hard(state: AgentState) -> dict:
    """Tra ve: {"candidates": [dat], "rejected": [loai]}.

    Goi filter_hard_constraints(); GHI DE state["candidates"] bang phan
    eligible. Router route_after_filter doc chinh khoa nay.
    """
    return {"candidates": list(state.get("candidates") or []), "rejected": []}


def score_rank(state: AgentState) -> dict:
    """Tra ve: {"ranked": [...]}. Goi rank_suppliers() cua scoring.py."""
    return {"ranked": list(state.get("candidates") or [])}


def verify_output(state: AgentState) -> dict:
    """Tra ve: {"verdict": {"passed": bool, "violations": [...], "claims": [...]}}.

    claims[i] = {"claim": str, "value": Any,
                 "evidence": {"MaNCC": str, "field": str, "nguon_url": str}}
    AutoEval tinh Citation/Evidence Correctness tu claims -> KHONG duoc tra boolean.
    """
    return {"verdict": {"passed": True, "violations": [], "claims": []}}


def diagnose(state: AgentState) -> dict:
    """Tra ve: {"replan_reason": str} - ma nguyen nhan lay tu
    hard_constraint_violations() va tu loi trong tool_results."""
    return {"replan_reason": "stub_no_candidate"}


def replan(state: AgentState) -> dict:
    """Tra ve: {"plan": plan moi, "replan_count": so nguyen TUYET DOI}.

    replan_count KHONG co reducer -> tra ve gia tri moi, khong tra ve so cong them.
    """
    return {
        "plan": dict(state.get("plan") or {}, plan_id="plan_stub_replan"),
        "replan_count": state.get("replan_count", 0) + 1,
    }


def respond_limits(state: AgentState) -> dict:
    """Nhanh out_of_scope: neu ro gioi han he thong thay vi doan bua."""
    return {
        "answer": (
            "Yeu cau nay nam ngoai pham vi cua he thong. He thong chi ho tro tim, "
            "so sanh va dam phan voi nha cung cap noi that van phong "
            "(ghe van phong, ban lam viec, tu ho so, ke, sofa) tren bo du lieu mock noi bo."
        ),
        "status": "out_of_scope",
    }


def graceful_fail(state: AgentState) -> dict:
    """Ket thuc that bai co ly do. Ton trong `answer` da co san (vd needs_input)."""
    if state.get("answer"):
        return {"status": state.get("status") or "graceful_fail"}
    return {
        "answer": "Khong tim duoc nha cung cap thoa man rang buoc sau 3 lan lap ke hoach lai.",
        "status": "graceful_fail",
    }


for _node in (plan, filter_hard, score_rank, verify_output, diagnose, replan,
              respond_limits, graceful_fail):
    _node.__stub__ = True
