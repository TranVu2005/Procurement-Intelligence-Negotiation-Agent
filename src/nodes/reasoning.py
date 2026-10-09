"""Cac node suy luan tat dinh - Owner: Nguoi B."""

from src.graph_state import AgentState
from src.reasoning.planner import PlanningError, ReplanLimitReached, make_plan, make_replan
from src.reasoning.scoring import (
    ScoringError,
    build_relax_suggestions,
    diagnose as diagnose_rejections,
    filter_hard_constraints,
    rank_suppliers,
    resolve_weights,
    verify_output as verify_recommendation,
)


_FULL_HARD_FIELDS = (
    "product_type",
    "quantity",
    "budget_max",
    "delivery_deadline_days",
)


def _req_with_session(state: AgentState) -> dict:
    req = dict(state.get("req") or {})
    req.setdefault("session_id", state.get("session_id") or "")
    return req


def _partial_compare_filter(candidates: list[dict], quantity) -> dict:
    """Filter only constraints known in a standalone compare request."""

    eligible, rejected = [], []
    for supplier in candidates:
        violations = []
        if supplier.get("error"):
            violations.append({
                "code": "tool_result_error",
                "field": "error_type",
                "actual": supplier.get("error_type"),
                "required": "successful evidence",
            })
        moq = supplier.get("MOQ")
        if isinstance(quantity, int) and not isinstance(quantity, bool):
            if not isinstance(moq, (int, float)) or isinstance(moq, bool):
                violations.append({
                    "code": "missing_moq_evidence", "field": "MOQ",
                    "actual": moq, "required": "numeric value",
                })
            elif quantity < moq:
                violations.append({
                    "code": "quantity_below_moq", "field": "MOQ",
                    "actual": quantity, "required": f">= {moq}",
                })
            stock = supplier.get("TonKho")
            if not isinstance(stock, (int, float)) or isinstance(stock, bool):
                violations.append({
                    "code": "missing_stock_evidence", "field": "TonKho",
                    "actual": stock, "required": f">= {quantity}",
                })
            elif stock < quantity:
                violations.append({
                    "code": "stock_below_quantity", "field": "TonKho",
                    "actual": stock, "required": f">= {quantity}",
                })
        if violations:
            rejected.append({
                "supplier_id": supplier.get("MaNCC"),
                "violations": violations,
                "evidence": supplier,
            })
        else:
            eligible.append(dict(supplier))
    return {"eligible": eligible, "rejected": rejected}


def _diagnosis_for(state: AgentState) -> dict:
    rejected = list(state.get("rejected") or [])
    verdict_violations = (state.get("verdict") or {}).get("violations") or []
    if verdict_violations:
        supplier_id = ((state.get("ranked") or [{}])[0]).get("MaNCC")
        rejected.append({"supplier_id": supplier_id, "violations": verdict_violations})

    for entry in state.get("tool_results") or []:
        if entry.get("status") != "error":
            continue
        result = entry.get("result") or {}
        rejected.append({
            "supplier_id": None,
            "violations": [{
                "code": "tool_result_error",
                "field": "error_type",
                "actual": entry.get("error_type") or result.get("error_type"),
                "required": "successful evidence",
            }],
        })
    return diagnose_rejections(rejected)


def plan(state: AgentState) -> dict:
    """Tra ve: {"plan": dict}. Goi make_plan/make_replan cua planner.py."""
    req = _req_with_session(state)
    intent = state.get("intent") or req.get("intent") or "search_new"
    try:
        return {"plan": make_plan(req, intent=intent)}
    except PlanningError as exc:
        return {
            "plan": {},
            "status": "needs_input",
            "answer": f"Chưa thể lập kế hoạch: {exc}",
        }


def filter_hard(state: AgentState) -> dict:
    """Tra ve: {"candidates": [dat], "rejected": [loai]}.

    Goi filter_hard_constraints(); GHI DE state["candidates"] bang phan
    eligible. Router route_after_filter doc chinh khoa nay.

    NGOAI LE BAT BUOC (B phai giu khi viet node that): voi
    state["intent"] == "supplier_detail", nguoi dung chi hoi thong tin, khong
    co rang buoc cung nao de doi chieu. Cho record di thang qua, KHONG goi
    filter_hard_constraints - neu goi, moi record se bi loai vi thieu
    total_price va vong re-plan se chay vo ich cho den khi cham tran 3 lan.
    """
    candidates = list(state.get("candidates") or [])
    if state.get("intent") == "supplier_detail":
        return {"candidates": candidates, "rejected": []}

    hard = (state.get("req") or {}).get("hard_constraints") or {}
    if state.get("intent") == "compare_specific" and not all(
        hard.get(field) is not None for field in _FULL_HARD_FIELDS
    ):
        filtered = _partial_compare_filter(candidates, hard.get("quantity"))
    else:
        try:
            filtered = filter_hard_constraints(candidates, hard)
        except (KeyError, TypeError, ValueError) as exc:
            rejected = [{
                "supplier_id": item.get("MaNCC"),
                "violations": [{
                    "code": "invalid_constraint_state",
                    "field": "hard_constraints",
                    "actual": hard,
                    "required": str(exc),
                }],
                "evidence": item,
            } for item in candidates]
            filtered = {"eligible": [], "rejected": rejected}
    return {"candidates": filtered["eligible"], "rejected": filtered["rejected"]}


def score_rank(state: AgentState) -> dict:
    """Tra ve: {"ranked": [...]}. Goi rank_suppliers() cua scoring.py."""
    candidates = list(state.get("candidates") or [])
    intent = state.get("intent")
    req = state.get("req") or {}
    hard = req.get("hard_constraints") or {}
    weights_used = resolve_weights(req)

    if intent == "supplier_detail":
        return {"ranked": candidates, "weights_used": weights_used}
    if intent == "compare_specific" and not all(
        hard.get(field) is not None for field in _FULL_HARD_FIELDS
    ):
        ranked = sorted(
            candidates,
            key=lambda item: (
                not isinstance(item.get("total_price"), (int, float)),
                item.get("total_price", float("inf")),
                str(item.get("MaNCC", "")),
            ),
        )
        return {"ranked": ranked, "weights_used": weights_used}
    try:
        return {"ranked": rank_suppliers(candidates, req), "weights_used": weights_used}
    except (KeyError, TypeError, ScoringError):
        return {"ranked": [], "weights_used": weights_used}


def verify_output(state: AgentState) -> dict:
    """Tra ve: {"verdict": {"passed": bool, "violations": [...], "claims": [...]}}.

    claims[i] = {"claim": str, "value": Any,
                 "evidence": {"MaNCC": str, "field": str, "nguon_url": str}}
    AutoEval tinh Citation/Evidence Correctness tu claims -> KHONG duoc tra boolean.
    """
    verdict = verify_recommendation(
        state.get("ranked") or [],
        state.get("req") or {},
        state.get("tool_results") or [],
    )
    return {"verdict": verdict}


def diagnose(state: AgentState) -> dict:
    """Tra ve: {"replan_reason": str} - ma nguyen nhan lay tu
    hard_constraint_violations() va tu loi trong tool_results."""
    diagnosis = _diagnosis_for(state)
    suggestions = build_relax_suggestions(
        state.get("rejected") or [], state.get("req") or {},
    )
    return {
        "replan_reason": diagnosis["replan_reason"],
        "relax_suggestions": suggestions,
    }


def replan(state: AgentState) -> dict:
    """Tra ve: {"plan": plan moi, "replan_count": so nguyen TUYET DOI}.

    replan_count KHONG co reducer -> tra ve gia tri moi, khong tra ve so cong them.
    """
    previous_plan = state.get("plan") or {}
    reason = _diagnosis_for(state)["replan_reason"]
    req = _req_with_session(state)
    try:
        new_plan = make_replan(req, previous_plan, reason)
    except (PlanningError, ReplanLimitReached) as exc:
        return {
            "plan": previous_plan,
            "replan_count": state.get("replan_count", 0) + 1,
            "status": "needs_input",
            "answer": f"Không thể lập lại kế hoạch: {exc}",
        }
    return {"plan": new_plan, "replan_count": new_plan["replan_count"]}


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
        return {
            "status": state.get("status") or "graceful_fail",
            "relax_suggestions": state.get("relax_suggestions") or [],
        }

    diagnosis = _diagnosis_for(state)
    suggestions = list(state.get("relax_suggestions") or [])
    if not suggestions:
        suggestions = build_relax_suggestions(
            state.get("rejected") or [], state.get("req") or {},
        )

    lines = [
        "Không có nhà cung cấp nào đủ bằng chứng và thỏa toàn bộ ràng buộc hiện tại.",
        f"Nút thắt chính: {diagnosis['replan_reason']}.",
    ]
    for item in suggestions:
        supplier_ids = ", ".join(item.get("supplier_ids") or [])
        current = item.get("current")
        suggested = item.get("suggested")
        constraint = item.get("constraint")
        if constraint == "budget_max" and all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in (current, suggested)
        ):
            detail = f"{current:,.0f} → {suggested:,.0f} VND"
        elif constraint == "delivery_deadline_days":
            detail = f"{current} → {suggested} ngày"
        else:
            detail = f"{current} → {suggested} sản phẩm"
        lines.append(
            f"Gợi ý để bạn cân nhắc, không tự động áp dụng: nới {constraint} "
            f"từ {detail}, dựa trên {supplier_ids}."
        )
    if not suggestions:
        lines.append(
            "Chưa có số liệu ứng viên để tính một ngưỡng nới cụ thể; hãy kiểm tra lại "
            "loại sản phẩm hoặc cung cấp thêm phạm vi tìm kiếm."
        )
    return {
        "answer": "\n".join(lines),
        "status": "graceful_fail",
        "relax_suggestions": suggestions,
    }
