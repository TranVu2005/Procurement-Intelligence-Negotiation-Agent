"""Node perceive - LLM #1: parse input + phan loai intent.

Owner: Nguoi A. Day dang la NODE GIA. A thay ruot ham `perceive` o Dot 2,
giu nguyen chu ky va cac khoa tra ve, va xoa dong `perceive.__stub__`.
"""

from src.graph_state import AgentState


def perceive(state: AgentState) -> dict:
    """Tra ve: {"intent": Intent, "req": dict, "llm_calls": 1,
    "tokens_in": int, "tokens_out": int}.

    req la state schema cua A (interface-contracts.md muc 1) va voi intent
    compare_specific/supplier_detail phai co them target_supplier_ids.
    """
    return {
        "intent": "search_new",
        "req": {
            "session_id": state.get("session_id") or "sess_stub",
            "hard_constraints": {
                "product_type": "ghế văn phòng",
                "quantity": 50,
                "budget_max": 200_000_000,
                "delivery_deadline_days": 14,
            },
            "soft_constraints": {
                "material_preference": None,
                "region_preference": None,
                "min_trust_score": None,
            },
            "conversation_history": [],
            "decisions_made": [],
        },
        "llm_calls": 1,
        "tokens_in": 0,
        "tokens_out": 0,
    }


perceive.__stub__ = True
