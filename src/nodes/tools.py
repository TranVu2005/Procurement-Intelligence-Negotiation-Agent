"""Cac node tool. Owner: Nguoi C.

tool_search thuc thi plan cua B (khong de LLM tu chon tool). Sau buoc
search_suppliers, node tu bo sung get_supplier_detail cho tung MaNCC roi
goi compare_price - dung nhu docstring make_plan cua planner.py yeu cau,
vi search_suppliers chi tra 6 field tom tat, thieu TonKho/LoaiSanPham ma
hard_constraint_violations cua B doc.
"""

import time
import unicodedata

from src.graph_state import AgentState, tool_result_entry
from src.nodes.tool_exec import run_tool
from src.reasoning.scoring import merge_supplier_evidence
from src.tools.supplier_tools import confirm_order

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


# Cum xac nhan tuong minh. Cac cum phu dinh phai duoc kiem TRUOC (xem _is_confirmed).
CONFIRM_WORDS = ("chot don", "dong y", "ok chot", "xac nhan dat", "dat hang di", "chot luon")
_REFUSAL_WORDS = ("khong dong y", "khong chot", "chua chot", "khoan da", "de sau")


def _fold(text: str) -> str:
    """Bo dau tieng Viet, ha thuong - chi de so khop, khong doi du lieu goc."""
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


def _is_confirmed(user_input: str) -> bool:
    """True chi khi nguoi dung xac nhan tuong minh o CHINH luot nay.

    Khong bao gio suy dien tu ngu canh truoc do (SYSTEM-RULES.md muc 3:
    hanh dong hau qua cao phai co xac nhan ro rang).
    """
    folded = _fold(user_input)
    if any(word in folded for word in _REFUSAL_WORDS):
        return False
    return any(word in folded for word in CONFIRM_WORDS)


def confirm_gate(state: AgentState) -> dict:
    """Chan buoc chot don lai, cho den khi nguoi dung xac nhan tuong minh."""
    ranked = state.get("ranked") or []
    if not ranked:
        return {"pending_confirmation": None, "status": state.get("status") or "success"}

    top = ranked[0]
    supplier_id = top.get("MaNCC")
    quantity = ((state.get("req") or {}).get("hard_constraints") or {}).get("quantity")

    if not _is_confirmed(state.get("user_input", "")) or not supplier_id or not quantity:
        return {
            "pending_confirmation": {
                "supplier_id": supplier_id,
                "supplier_name": top.get("TenNCC"),
                "quantity": quantity,
                "total_price": top.get("total_price"),
            },
            "status": "needs_confirmation",
            "answer": (
                f"{state.get('answer', '')}\n\n"
                f"Ban co muon chot don voi {top.get('TenNCC')} ({supplier_id}), "
                f"so luong {quantity}? Toi chi thuc hien khi ban xac nhan ro rang "
                f"(vi du: 'chot don di')."
            ).strip(),
        }

    started = time.perf_counter()
    result = confirm_order(supplier_id=supplier_id, quantity=quantity, confirmed=True)
    entry = tool_result_entry(
        tool="confirm_order",
        params={"supplier_id": supplier_id, "quantity": quantity, "confirmed": True},
        status="error" if result.get("error") else "ok",
        result=result,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
        trace_id=state.get("trace_id", ""),
        error_type=result.get("error_type"),
    )

    if result.get("error"):
        return {"tool_results": [entry], "pending_confirmation": None,
                "status": "graceful_fail",
                "answer": f"Khong chot duoc don: {result.get('message')}"}

    return {
        "tool_results": [entry],
        "pending_confirmation": None,
        "status": "success",
        "answer": (
            f"{state.get('answer', '')}\n\n"
            f"Da chot don voi {top.get('TenNCC')} ({supplier_id}), so luong {quantity}, "
            f"luc {result['confirmed_at']}."
        ).strip(),
    }
