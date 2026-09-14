"""Cac node tool. Owner: Nguoi C.

tool_search thuc thi plan cua B (khong de LLM tu chon tool). Sau buoc
search_suppliers, node tu bo sung get_supplier_detail cho tung MaNCC roi
goi compare_price - dung nhu docstring make_plan cua planner.py yeu cau,
vi search_suppliers chi tra 6 field tom tat, thieu TonKho/LoaiSanPham ma
hard_constraint_violations cua B doc.
"""

from src.graph_state import AgentState, tool_result_entry
from src.nodes.tool_exec import run_tool
from src.reasoning.scoring import merge_supplier_evidence

_NEED_QUANTITY = (
    "Toi can biet số lượng du kien dat mua truoc khi so sanh gia va kiem tra MOQ. "
    "Ban muon mua bao nhieu san pham?"
)
_NEED_PLAN = (
    "Ke hoach thuc thi khong co buoc tim nha cung cap nen toi khong the tra loi "
    "yeu cau nay. Vui long neu lai loai san pham can mua."
)
_NEED_SUPPLIER_IDS = (
    "Yeu cau nay can ma nha cung cap (MaNCC) cu the, vi du 'NCC001'. "
    "Ban muon xem hoac so sanh nhung nha cung cap nao?"
)


def _clean_params(params: dict | None) -> dict:
    """Bo cac khoa co gia tri None.

    Quyet dinh 1 cua nhom: material/region la soft preference, khong duoc loc
    cung o search_suppliers. Plan co the con gui None - bo di truoc khi goi tool.
    """
    return {k: v for k, v in (params or {}).items() if v is not None}


def _step_for(state: AgentState, action: str) -> dict | None:
    for step in (state.get("plan") or {}).get("steps") or []:
        if step.get("action") == action:
            return step
    return None


def _blocked_confirm_entries(state: AgentState) -> list[dict]:
    """Plan khong duoc phep chot don. Ghi lai de audit nhung khong thuc thi."""
    entries = []
    for step in (state.get("plan") or {}).get("steps") or []:
        if step.get("action") != "confirm_order":
            continue
        entries.append(tool_result_entry(
            tool="confirm_order",
            params=step.get("params") or {},
            status="blocked",
            result={
                "error": True,
                "error_type": "invalid_input",
                "message": "Plan khong duoc tu chot don; phai di qua node confirm_gate.",
            },
            latency_ms=0.0,
            trace_id=state.get("trace_id", ""),
            error_type="invalid_input",
            step_id=step.get("step_id"),
        ))
    return entries


def _fetch_details(state: AgentState, supplier_ids: list[str],
                   step_id: int | None = None) -> tuple[list[dict], list[dict]]:
    """Lay full record cho tung MaNCC. Mot ma loi chi bo qua ma do, khong dung ca vong."""
    details, entries = [], []
    for supplier_id in supplier_ids:
        result, entry = run_tool(state, "get_supplier_detail",
                                 {"supplier_id": supplier_id}, step_id=step_id)
        entries.append(entry)
        if not (isinstance(result, dict) and result.get("error")):
            details.append(result)
    return details, entries


def tool_search(state: AgentState) -> dict:
    entries = _blocked_confirm_entries(state)
    hard = (state.get("req") or {}).get("hard_constraints") or {}

    search_step = _step_for(state, "search_suppliers")
    if search_step is None:
        return {"tool_results": entries, "candidates": [],
                "status": "needs_input", "answer": _NEED_PLAN}

    params = _clean_params(search_step.get("params"))
    params.setdefault("product_type", hard.get("product_type"))
    result, entry = run_tool(state, "search_suppliers", params,
                             step_id=search_step.get("step_id"))
    entries.append(entry)
    if result.get("error"):
        return {"tool_results": entries, "candidates": []}

    supplier_ids = [s["MaNCC"] for s in result.get("suppliers", [])]
    details, detail_entries = _fetch_details(state, supplier_ids)
    entries.extend(detail_entries)

    compare_step = _step_for(state, "compare_price")
    quantity = (compare_step or {}).get("params", {}).get("quantity") or hard.get("quantity")
    if not quantity:
        # Khong duoc tu gia dinh so luong (SYSTEM-RULES.md)
        return {"tool_results": entries, "candidates": [],
                "status": "needs_input", "answer": _NEED_QUANTITY}

    price_result, price_entry = run_tool(
        state, "compare_price", {"supplier_ids": supplier_ids, "quantity": quantity},
        step_id=(compare_step or {}).get("step_id"),
    )
    entries.append(price_entry)
    if price_result.get("error"):
        return {"tool_results": entries, "candidates": []}

    return {"tool_results": entries,
            "candidates": merge_supplier_evidence(details, price_result)}


def tool_compare(state: AgentState) -> dict:
    """Nhanh compare_specific: so sanh dung danh sach MaNCC nguoi dung neu ra."""
    req = state.get("req") or {}
    hard = req.get("hard_constraints") or {}
    supplier_ids = list(req.get("target_supplier_ids") or [])

    if not supplier_ids:
        return {"tool_results": [], "candidates": [],
                "status": "needs_input", "answer": _NEED_SUPPLIER_IDS}

    details, entries = _fetch_details(state, supplier_ids)

    quantity = hard.get("quantity")
    if not quantity:
        return {"tool_results": entries, "candidates": [],
                "status": "needs_input", "answer": _NEED_QUANTITY}

    found_ids = [d["MaNCC"] for d in details]
    if not found_ids:
        return {"tool_results": entries, "candidates": []}

    price_result, price_entry = run_tool(
        state, "compare_price", {"supplier_ids": found_ids, "quantity": quantity})
    entries.append(price_entry)
    if price_result.get("error"):
        return {"tool_results": entries, "candidates": []}

    return {"tool_results": entries,
            "candidates": merge_supplier_evidence(details, price_result)}


def tool_detail(state: AgentState) -> dict:
    """Nhanh supplier_detail: tra full record cua DUNG 1 NCC.

    get_supplier_detail chi nhan 1 MaNCC moi lan goi (interface-contracts.md
    muc 3), nen chi lay ma dau tien.
    """
    supplier_ids = list((state.get("req") or {}).get("target_supplier_ids") or [])
    if not supplier_ids:
        return {"tool_results": [], "candidates": [],
                "status": "needs_input", "answer": _NEED_SUPPLIER_IDS}

    details, entries = _fetch_details(state, supplier_ids[:1])
    return {"tool_results": entries, "candidates": details}


def confirm_gate(state: AgentState) -> dict:
    return {"pending_confirmation": None}


confirm_gate.__stub__ = True
