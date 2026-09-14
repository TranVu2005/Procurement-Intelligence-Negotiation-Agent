"""Node respond - LLM #2, lan goi mo hinh cuoi cung cua 1 request.

Owner: Nguoi C (rap va dem token); noi dung SYSTEM_PROMPT do B soan.

Nguyen tac: LLM chi DIEN DAT LAI bang chung da co trong state, khong duoc
tu them con so nao. Bang chung duoc dung tat dinh o build_evidence_block(),
moi con so deu di kem MaNCC va nguon_url de nguoi doc truy nguoc duoc
(architecture.md muc 4.1).

LLM hong (mat mang, rate limit) khong duoc lam sap request: rot xuong cau
tra loi tat dinh dung tu chinh bang chung do.
"""

import time

from src.graph_state import AgentState
from src.llm import get_llm, usage_of

SYSTEM_PROMPT = """Ban la tro ly mua sam noi that. Nhiem vu cua ban la trinh bay lai
KET QUA DA DUOC TINH SAN ben duoi thanh cau tra loi tieng Viet ngan gon cho nguoi mua.

Quy tac bat buoc:
1. CHI dung nhung con so co trong phan BANG CHUNG. Khong duoc tu tinh, tu lam tron,
   tu suy ra con so moi.
2. Moi con so neu ra phai kem ma nha cung cap (MaNCC) va duong dan nguon.
3. Neu mot truong nam trong simulated_fields, phai noi ro do la so lieu mo phong.
4. Khong hua hen, khong tu chot don. Viec chot don do nguoi dung quyet dinh o buoc sau.
5. Neu phan BANG CHUNG ghi "KHONG CO BANG CHUNG", hay noi ro la khong co du lieu de
   khuyen nghi, va khong duoc goi y bat ky nha cung cap nao.

Tien te: VND, viet dang so thuan."""

_NO_EVIDENCE = "KHONG CO BANG CHUNG"


def _format_supplier(item: dict) -> str:
    simulated = ", ".join(item.get("simulated_fields") or []) or "khong co"
    strategy = item.get("negotiation_strategy") or {}
    return (
        f"- {item.get('TenNCC')} (MaNCC={item.get('MaNCC')})\n"
        f"  don_gia_sau_chiet_khau={item.get('unit_price')} VND\n"
        f"  tong_tien={item.get('total_price')} VND\n"
        f"  thoi_gian_giao={item.get('ThoiGianGiao')} ngay | MOQ={item.get('MOQ')}"
        f" | diem_uy_tin={item.get('DiemUyTin')}\n"
        f"  leverage_score={item.get('leverage_score')}\n"
        f"  chien_luoc_dam_phan={strategy}\n"
        f"  nguon={item.get('nguon_url')}\n"
        f"  truong_mo_phong=[{simulated}]"
    )


def build_evidence_block(state: AgentState) -> str:
    """Bang chung tat dinh dua vao prompt. Khong goi LLM o day."""
    ranked = state.get("ranked") or []
    if not ranked:
        return _NO_EVIDENCE

    lines = [_format_supplier(item) for item in ranked[:5]]
    claims = (state.get("verdict") or {}).get("claims") or []
    if claims:
        lines.append("Cac khang dinh da duoc kiem chung:")
        lines.extend(f"- {c.get('claim')}: {c.get('value')} (nguon: {c.get('evidence')})"
                     for c in claims)
    return "\n".join(lines)


def _deterministic_answer(evidence: str) -> str:
    """Duong lui khi LLM khong dung duoc - van dung bang chung, khong bia them."""
    return ("Ket qua tot nhat theo du lieu hien co (trinh bay tu dong, khong qua mo hinh "
            "ngon ngu):\n" + evidence)


def respond(state: AgentState) -> dict:
    evidence = build_evidence_block(state)

    if evidence == _NO_EVIDENCE:
        # Khong co bang chung thi khong goi LLM va khong khuyen nghi ai ca
        return {
            "answer": ("Toi khong tim duoc nha cung cap nao co du bang chung de khuyen nghi "
                       "cho yeu cau nay."),
            "status": "graceful_fail",
            "llm_calls": 0,
        }

    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", f"Yeu cau cua nguoi dung:\n{state.get('user_input', '')}\n\n"
                  f"BANG CHUNG:\n{evidence}"),
    ]

    started = time.perf_counter()
    ttft_ms = None
    parts: list[str] = []
    tokens_in = tokens_out = 0

    try:
        llm = get_llm(streaming=True)
        for chunk in llm.stream(messages):
            if ttft_ms is None:
                ttft_ms = round((time.perf_counter() - started) * 1000, 2)
            if chunk.content:
                parts.append(chunk.content)
            chunk_in, chunk_out = usage_of(chunk)
            tokens_in += chunk_in
            tokens_out += chunk_out
    except Exception:  # noqa: BLE001 - LLM hong khong duoc lam sap ca request
        return {
            "answer": _deterministic_answer(evidence),
            "status": "success",
            "llm_calls": 0,
            "ttft_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    answer = "".join(parts).strip() or _deterministic_answer(evidence)
    return {
        "answer": answer,
        "status": "success",
        "llm_calls": 1,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "ttft_ms": ttft_ms if ttft_ms is not None else 0.0,
    }
