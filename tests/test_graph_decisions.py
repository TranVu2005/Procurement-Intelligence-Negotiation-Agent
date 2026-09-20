import unittest
from unittest.mock import patch

from src.graph import run_request

HISTORY_2 = [{"role": "user", "content": "Can 20 ghe"},
             {"role": "user", "content": "ok chot don di"}]


def fake_perceive(state):
    return {"intent": "search_new", "llm_calls": 1, "req": {
        "session_id": "sess_dec", "intent": "search_new",
        "hard_constraints": {"product_type": "ghế văn phòng", "quantity": 20,
                             "budget_max": 100_000_000, "delivery_deadline_days": 14},
        "soft_constraints": {}, "conversation_history": HISTORY_2, "decisions_made": [],
    }}


OVERRIDES = {
    "perceive": fake_perceive,
    "plan": lambda s: {"plan": {"plan_id": "p", "replan_count": 0, "steps": []}},
    "tool_search": lambda s: {"tool_results": [], "candidates": [
        {"MaNCC": "EDGE001", "TenNCC": "Noi That Cao Cap Kim Long", "total_price": 1}]},
    "filter_hard": lambda s: {"candidates": list(s.get("candidates") or []), "rejected": []},
    "score_rank": lambda s: {"ranked": list(s.get("candidates") or [])},
    "verify_output": lambda s: {"verdict": {"passed": True, "violations": [], "claims": []}},
    "respond": lambda s: {"answer": "De xuat EDGE001.", "status": "success", "llm_calls": 1},
}


class DecisionPersistenceTests(unittest.TestCase):
    def test_a_confirmed_order_is_written_to_decisions(self) -> None:
        with patch("src.graph.save_session") as save, \
                patch("src.graph.save_decision") as decide, \
                patch("src.graph.append_conversation"):
            final = run_request("ok chot don di", overrides=OVERRIDES)
        self.assertEqual(final["status"], "success")
        decide.assert_called_once_with("sess_dec", "EDGE001")
        saved_req = save.call_args.args[1]
        self.assertEqual([d["supplier_id"] for d in saved_req["decisions_made"]], ["EDGE001"])
        self.assertTrue(saved_req["decisions_made"][0]["confirmed_at"])

    def test_no_confirmation_writes_no_decision(self) -> None:
        with patch("src.graph.save_session"), \
                patch("src.graph.save_decision") as decide, \
                patch("src.graph.append_conversation"):
            final = run_request("Can 20 ghe van phong", overrides=OVERRIDES)
        self.assertEqual(final["status"], "needs_confirmation")
        decide.assert_not_called()


if __name__ == "__main__":
    unittest.main()
