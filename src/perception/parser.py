"""Perception module — parse natural-language procurement request into structured state.

Owner: Nguoi A
State schema contract (see PROJECT-SETUP.md section 5):
{
    "session_id": str,
    "hard_constraints": {"budget_max": int, "quantity": int, "delivery_deadline_days": int},
    "soft_constraints": {"material_preference": str, ...},
    "history": [str, ...]
}
"""


def parse_request(text: str, session_id: str) -> dict:
    raise NotImplementedError
