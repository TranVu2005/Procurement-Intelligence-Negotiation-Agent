"""Task decomposition and bounded re-planning for procurement requests.

This module only owns reasoning/planning. It reads A's state contract and emits
tool calls from C's tool contract without changing either contract.
"""

from __future__ import annotations

from copy import deepcopy
from collections import Counter
from typing import Any
from uuid import uuid4


MAX_REPLAN_COUNT = 3
SUPPORTED_INTENTS = {"search_new", "compare_specific", "supplier_detail", "out_of_scope"}

# Only stages marked ``tool`` become plan steps because SYSTEM-RULES requires
# each step action to exactly match a tool owned by C.
WORKFLOW_STAGES: tuple[dict[str, str], ...] = (
    {"name": "validate_state", "kind": "reasoning"},
    {"name": "search_suppliers", "kind": "tool"},
    {"name": "filter_hard_constraints", "kind": "reasoning"},
    {"name": "compare_price", "kind": "tool"},
    {"name": "rank_candidates", "kind": "reasoning"},
    {"name": "calculate_leverage_score", "kind": "reasoning"},
    {"name": "generate_recommendation", "kind": "reasoning"},
    {"name": "verify_output", "kind": "reasoning"},
)

_INTENT_WORKFLOWS: dict[str, tuple[dict[str, str], ...]] = {
    "search_new": WORKFLOW_STAGES,
    "compare_specific": (
        {"name": "validate_state", "kind": "reasoning"},
        {"name": "compare_price", "kind": "tool"},
        {"name": "rank_candidates", "kind": "reasoning"},
        {"name": "verify_output", "kind": "reasoning"},
    ),
    "supplier_detail": (
        {"name": "validate_state", "kind": "reasoning"},
        {"name": "get_supplier_detail", "kind": "tool"},
        {"name": "verify_output", "kind": "reasoning"},
    ),
    "out_of_scope": (
        {"name": "respond_limits", "kind": "reasoning"},
    ),
}

_REQUIRED_HARD_CONSTRAINTS = (
    "product_type",
    "quantity",
    "budget_max",
    "delivery_deadline_days",
)


class PlanningError(ValueError):
    """Raised when the state cannot safely be turned into a plan."""


class ReplanLimitReached(PlanningError):
    """Raised when another re-plan would exceed the agreed safety limit."""


def validate_state(state: dict[str, Any], intent: str = "search_new") -> None:
    """Validate the subset of A's state that planning depends on.

    Missing important information is reported instead of silently inferred.
    """

    if not isinstance(state, dict):
        raise PlanningError("state must be a dictionary")

    if intent not in SUPPORTED_INTENTS:
        raise PlanningError(f"unsupported intent: {intent}")

    session_id = state.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise PlanningError("missing or invalid session_id")

    if intent in {"supplier_detail", "out_of_scope"}:
        return

    hard = state.get("hard_constraints")
    if not isinstance(hard, dict):
        raise PlanningError("hard_constraints must be a dictionary")

    required = _REQUIRED_HARD_CONSTRAINTS if intent == "search_new" else ("quantity",)
    missing = [name for name in required if hard.get(name) is None]
    if missing:
        raise PlanningError(f"missing hard constraints: {', '.join(missing)}")

    if intent == "search_new" and (
        not isinstance(hard["product_type"], str) or not hard["product_type"].strip()
    ):
        raise PlanningError("product_type must be a non-empty string")
    if not isinstance(hard["quantity"], int) or isinstance(hard["quantity"], bool) or hard["quantity"] <= 0:
        raise PlanningError("quantity must be a positive integer")
    if intent == "search_new":
        if not isinstance(hard["budget_max"], (int, float)) or isinstance(hard["budget_max"], bool) or hard["budget_max"] <= 0:
            raise PlanningError("budget_max must be a positive number")
        if (
            not isinstance(hard["delivery_deadline_days"], int)
            or isinstance(hard["delivery_deadline_days"], bool)
            or hard["delivery_deadline_days"] <= 0
        ):
            raise PlanningError("delivery_deadline_days must be a positive integer")

    soft = state.get("soft_constraints", {})
    if soft is not None and not isinstance(soft, dict):
        raise PlanningError("soft_constraints must be a dictionary")


def make_plan(
    state: dict[str, Any],
    *,
    intent: str | None = None,
    supplier_ids: list[str] | None = None,
    supplier_id: str | None = None,
    replan_count: int = 0,
    replan_reason: str | None = None,
) -> dict[str, Any]:
    """Create executable steps for one of the four documented intents."""

    selected_intent = intent or state.get("intent", "search_new")
    validate_state(state, selected_intent)
    if not isinstance(replan_count, int) or isinstance(replan_count, bool) or replan_count < 0:
        raise PlanningError("replan_count must be a non-negative integer")
    if replan_count > MAX_REPLAN_COUNT:
        raise ReplanLimitReached(
            f"maximum re-plan count ({MAX_REPLAN_COUNT}) has been exceeded"
        )
    if replan_count > 0 and not replan_reason:
        raise PlanningError("replan_reason is required when replan_count is greater than 0")

    hard = state.get("hard_constraints") or {}
    if selected_intent == "search_new":
        # Soft preferences deliberately remain in state for ranking/trade-off.
        # Omitting them here prevents search from treating them as hard filters.
        steps = [{
            "step_id": 1,
            "action": "search_suppliers",
            "params": {"product_type": hard["product_type"]},
            "reason": "Tìm rộng theo loại sản phẩm trước khi lọc ràng buộc cứng và chấm ưu tiên mềm.",
            "depends_on": [],
        }]
    elif selected_intent == "compare_specific":
        ids = supplier_ids if supplier_ids is not None else state.get("supplier_ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(item, str) and item for item in ids):
            raise PlanningError("compare_specific requires a non-empty supplier_ids list")
        steps = [{
            "step_id": 1,
            "action": "compare_price",
            "params": {"supplier_ids": list(ids), "quantity": hard["quantity"]},
            "reason": "So sánh giá các nhà cung cấp người dùng chỉ định với số lượng đã xác nhận.",
            "depends_on": [],
        }]
    elif selected_intent == "supplier_detail":
        selected_supplier_id = supplier_id or state.get("supplier_id")
        if not isinstance(selected_supplier_id, str) or not selected_supplier_id.strip():
            raise PlanningError("supplier_detail requires supplier_id")
        steps = [{
            "step_id": 1,
            "action": "get_supplier_detail",
            "params": {"supplier_id": selected_supplier_id.strip()},
            "reason": "Lấy bằng chứng chi tiết cho đúng nhà cung cấp được hỏi.",
            "depends_on": [],
        }]
    else:
        steps = []

    return {
        "plan_id": f"plan_{uuid4().hex[:12]}",
        "session_id": state["session_id"],
        "intent": selected_intent,
        "status": "draft",
        "replan_count": replan_count,
        "replan_reason": replan_reason,
        "workflow": deepcopy(_INTENT_WORKFLOWS[selected_intent]),
        "steps": steps,
    }


def make_replan(
    state: dict[str, Any],
    previous_plan: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    """Create a new auditable plan after state/tool/result changes.

    The previous plan is never mutated. A fresh ``plan_id`` preserves the audit
    trail required by SYSTEM-RULES.
    """

    if not isinstance(previous_plan, dict):
        raise PlanningError("previous_plan must be a dictionary")
    if not isinstance(reason, str) or not reason.strip():
        raise PlanningError("a non-empty replan reason is required")

    previous_count = previous_plan.get("replan_count", 0)
    if not isinstance(previous_count, int) or isinstance(previous_count, bool) or previous_count < 0:
        raise PlanningError("previous plan has an invalid replan_count")
    if previous_count >= MAX_REPLAN_COUNT:
        raise ReplanLimitReached(
            f"cannot re-plan more than {MAX_REPLAN_COUNT} times; graceful failure is required"
        )

    intent = previous_plan.get("intent", "search_new")
    step_params = previous_plan.get("steps", [{}])[0].get("params", {}) if previous_plan.get("steps") else {}
    return make_plan(
        state,
        intent=intent,
        supplier_ids=step_params.get("supplier_ids"),
        supplier_id=step_params.get("supplier_id"),
        replan_count=previous_count + 1,
        replan_reason=reason.strip(),
    )


_RECOVERY_OPTIONS = {
    "stock_below_quantity": [
        "Chia đơn hàng cho nhiều nhà cung cấp.",
        "Giảm số lượng giao đợt đầu và giao phần còn lại sau.",
    ],
    "quantity_below_moq": [
        "Đàm phán MOQ thấp hơn với nhà cung cấp.",
        "Gom nhu cầu mua để đạt MOQ hoặc chọn nhà cung cấp khác.",
    ],
    "delivery_deadline_unmet": [
        "Xin người dùng xác nhận nới deadline.",
        "Chia giao hàng thành nhiều đợt hoặc mở rộng khu vực nhà cung cấp.",
    ],
    "budget_exceeded": [
        "Xin xác nhận tăng ngân sách hoặc giảm số lượng.",
        "Đề xuất chất liệu/phương án tương đương có giá thấp hơn.",
    ],
    "missing_price_evidence": [
        "Gọi lại compare_price; nếu vẫn lỗi thì thông báo chưa thể xác minh tổng giá.",
    ],
    "tool_result_error": [
        "Retry có giới hạn hoặc dùng nguồn/tool fallback trước khi kết luận.",
    ],
}


def propose_replan(
    previous_plan: dict[str, Any],
    rejected_suppliers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Diagnose failed candidates and propose safe, non-automatic alternatives.

    This function never relaxes user constraints itself. A first-class new plan
    is created only after the user confirms a change and A updates the state.
    """

    previous_count = previous_plan.get("replan_count", 0)
    if not isinstance(previous_count, int) or isinstance(previous_count, bool):
        raise PlanningError("previous plan has an invalid replan_count")
    if previous_count >= MAX_REPLAN_COUNT:
        return {
            "status": "graceful_failure",
            "reason": "Đã đạt giới hạn 3 lần re-plan; chưa đủ bằng chứng/cần hỗ trợ thêm.",
            "requires_user_confirmation": False,
            "causes": [],
            "alternatives": [],
        }

    codes = Counter(
        violation.get("code")
        for rejected in rejected_suppliers
        for violation in rejected.get("violations", [])
        if violation.get("code")
    )
    alternatives: list[str] = []
    for code, _count in codes.most_common():
        for option in _RECOVERY_OPTIONS.get(code, []):
            if option not in alternatives:
                alternatives.append(option)

    if not alternatives:
        alternatives.append("Yêu cầu thêm dữ liệu hoặc hỗ trợ thủ công trước khi tiếp tục.")

    return {
        "status": "needs_replan",
        "reason": "Không có nhà cung cấp thỏa toàn bộ ràng buộc cứng.",
        "requires_user_confirmation": True,
        "next_replan_count": previous_count + 1,
        "causes": [
            {"code": code, "affected_suppliers": count}
            for code, count in codes.most_common()
        ],
        "alternatives": alternatives,
    }


def propose_tool_replan(
    previous_plan: dict[str, Any],
    tool_result: dict[str, Any],
) -> dict[str, Any]:
    """Convert C's standard tool error into a bounded recovery proposal."""

    if not isinstance(tool_result, dict) or tool_result.get("error") is not True:
        raise PlanningError("tool_result must use the standard error contract")
    rejected = [{
        "supplier_id": None,
        "violations": [{
            "code": "tool_result_error",
            "field": "error_type",
            "actual": tool_result.get("error_type"),
            "required": "successful evidence",
        }],
    }]
    proposal = propose_replan(previous_plan, rejected)
    proposal["tool_error"] = {
        "error_type": tool_result.get("error_type"),
        "message": tool_result.get("message"),
    }
    return proposal
