"""Node perceive - LLM #1: parse input + phan loai intent.

Owner: Nguoi A.
"""

from src.graph_state import AgentState
from src.perception.parser import parse_request, update_state


def perceive(state: AgentState) -> dict:
    """Goi parser.py that de parse user_input thanh req co cau truc.

    Tra ve: {"intent": Intent, "req": dict, "llm_calls": 1,
    "tokens_in": int, "tokens_out": int}.

    - Neu day la turn dau (conversation_history trong req chua co gi):
      goi parse_request() de tao state moi.
    - Neu da co req tu turn truoc (multi-turn):
      goi update_state() de ghi de chi cac field thay doi.
    - Voi intent compare_specific / supplier_detail: req se co
      target_supplier_ids (lay tu supplier_ids cua parser) de
      tool_compare va tool_detail (C) su dung.

    Raises lan bao MissingFieldError / InvalidProductTypeError neu thieu
    thong tin bat buoc — graph.py / caller xu ly.
    """
    user_input: str = state.get("user_input") or ""
    session_id: str | None = state.get("session_id") or None
    existing_req: dict = state.get("req") or {}

    is_multi_turn = bool(existing_req.get("conversation_history"))

    if is_multi_turn:
        req = update_state(existing_req, user_input)
    else:
        req = parse_request(user_input, session_id=session_id)

    intent: str = req.get("intent", "search_new")

    # Gan target_supplier_ids vao req de tool_compare / tool_detail doc duoc
    if intent in ("compare_specific", "supplier_detail"):
        req.setdefault("target_supplier_ids", req.get("supplier_ids") or [])

    return {
        "intent": intent,
        "req": req,
        # parser.py goi LLM 1 lan; token count chua duoc do nen ghi 0 tam thoi
        "llm_calls": 1,
        "tokens_in": 0,
        "tokens_out": 0,
    }
