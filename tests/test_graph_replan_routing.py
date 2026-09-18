import unittest
from unittest.mock import patch

from src.graph import run_request


def fake_perceive(intent):
    def node(state):
        return {"intent": intent, "req": {}, "llm_calls": 1}
    return node


def fake_respond(state):
    return {"answer": "cau tra loi", "status": "success", "llm_calls": 1}


def fake_replan(state):
    count = state.get("replan_count", 0) + 1
    return {"plan": {"plan_id": f"plan_fake_{count}", "replan_count": count, "steps": []},
            "replan_count": count}


# Test WIRING: node noi dung cua B thay bang ham toi thieu.
BASE = {
    "plan": lambda s: {"plan": {"plan_id": "p0", "replan_count": 0, "steps": []}},
    "filter_hard": lambda s: {"candidates": list(s.get("candidates") or []), "rejected": []},
    "score_rank": lambda s: {"ranked": list(s.get("candidates") or [])},
    "verify_output": lambda s: {"verdict": {"passed": True, "violations": [], "claims": []}},
    "diagnose": lambda s: {"replan_reason": "wiring_test"},
    "replan": fake_replan,
    "respond": fake_respond,
    "confirm_gate": lambda s: {},
}


class ReplanReturnsToTheIntentToolTests(unittest.TestCase):
    def _run(self, intent):
        calls = {"tool_search": 0, "tool_compare": 0, "tool_detail": 0}

        def make(name):
            def node(state):
                calls[name] += 1
                # Lan dau rong -> ep di diagnose/replan; lan sau co ung vien
                candidates = [] if calls[name] == 1 else [{"MaNCC": "NCC001"}]
                return {"candidates": candidates, "tool_results": []}
            return node

        overrides = {**BASE, "perceive": fake_perceive(intent),
                     **{name: make(name) for name in calls}}
        final = run_request("x", overrides=overrides)
        return final, calls

    def test_compare_specific_replans_back_into_tool_compare(self) -> None:
        final, calls = self._run("compare_specific")
        self.assertEqual(calls, {"tool_search": 0, "tool_compare": 2, "tool_detail": 0})
        self.assertEqual(final["status"], "success")

    def test_supplier_detail_replans_back_into_tool_detail(self) -> None:
        final, calls = self._run("supplier_detail")
        self.assertEqual(calls, {"tool_search": 0, "tool_compare": 0, "tool_detail": 2})
        self.assertEqual(final["status"], "success")

    def test_search_new_still_replans_into_tool_search(self) -> None:
        final, calls = self._run("search_new")
        self.assertEqual(calls, {"tool_search": 2, "tool_compare": 0, "tool_detail": 0})
        self.assertEqual(final["status"], "success")


class RealNodesCompareTests(unittest.TestCase):
    """Node that cua B va C, chi thay perceive/respond. Ma NCC khong ton tai."""

    def test_compare_with_unknown_ids_never_falls_into_search(self) -> None:
        def perceive(state):
            return {"intent": "compare_specific", "llm_calls": 1, "req": {
                "session_id": "sess_cmp", "intent": "compare_specific",
                "supplier_ids": ["NCC998", "NCC999"],
                "target_supplier_ids": ["NCC998", "NCC999"],
                "hard_constraints": {"product_type": None, "quantity": 20,
                                     "budget_max": None, "delivery_deadline_days": None},
                "soft_constraints": {},
                "conversation_history": [{"role": "user", "content": "x"}],
            }}

        with patch("src.graph.save_session"), patch("src.graph.append_conversation"):
            final = run_request("So sanh NCC998 va NCC999",
                                overrides={"perceive": perceive, "respond": fake_respond})
        tools = [entry["tool"] for entry in final["tool_results"]]
        self.assertNotIn("search_suppliers", tools)
        self.assertIn(final["status"], {"graceful_fail", "needs_input"})
        self.assertNotIn("khong co buoc tim nha cung cap", final["answer"])


if __name__ == "__main__":
    unittest.main()
