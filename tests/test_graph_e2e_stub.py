import unittest

from src.graph import run_request
from src.graph_state import MAX_REPLAN


def fake_perceive(intent, req=None):
    def node(state):
        return {"intent": intent, "req": req or {}, "llm_calls": 1}
    return node


def fake_respond(state):
    return {"answer": "cau tra loi", "status": "success", "llm_calls": 1}


def pass_through(state):
    return {}


# perceive va respond deu bi thay bang node gia o moi test duoi day: hai node
# that goi LLM that, va confirm_gate that se chan lai khi chua co xac nhan.
# Test nay do WIRING cua graph, khong do noi dung cua tung node.
BASE_OVERRIDES = {"respond": fake_respond, "confirm_gate": pass_through}


def fake_plan(state):
    count = state.get("replan_count", 0)
    return {"plan": {
        "plan_id": f"plan_fake_{count}",
        "session_id": state.get("session_id", ""),
        "replan_count": count,
        "steps": [{"step_id": 1, "action": "search_suppliers", "params": {},
                   "reason": "wiring test", "depends_on": []}],
    }}


def fake_filter(state):
    return {"candidates": list(state.get("candidates") or []), "rejected": []}


def fake_replan(state):
    count = state.get("replan_count", 0) + 1
    return {"plan": {"plan_id": f"plan_fake_{count}", "replan_count": count,
                     "steps": []}, "replan_count": count}


# Day la test WIRING, nen cac node noi dung cua B cung duoc thay bang ham toi thieu.
BASE_OVERRIDES.update({
    "plan": fake_plan,
    "filter_hard": fake_filter,
    "score_rank": lambda s: {"ranked": list(s.get("candidates") or [])},
    "verify_output": lambda s: {
        "verdict": {"passed": True, "violations": [], "claims": []}
    },
    "diagnose": lambda s: {"replan_reason": "wiring_test"},
    "replan": fake_replan,
})


class HappyPathTests(unittest.TestCase):
    def test_search_new_reaches_respond_with_exactly_two_llm_calls(self) -> None:
        final = run_request(
            "Can 50 ghe van phong",
            overrides={
                **BASE_OVERRIDES,
                "perceive": fake_perceive("search_new"),
                "tool_search": lambda s: {"candidates": [{"MaNCC": "NCC001"}], "tool_results": []},
            },
        )
        self.assertEqual(final["status"], "success")
        self.assertEqual(final["llm_calls"], 2)
        self.assertTrue(final["answer"])

    def test_out_of_scope_ends_without_touching_any_tool(self) -> None:
        final = run_request("Dat ve may bay di Da Nang",
                            overrides={**BASE_OVERRIDES,
                                       "perceive": fake_perceive("out_of_scope")})
        self.assertEqual(final["status"], "out_of_scope")
        self.assertEqual(final["tool_results"], [])
        self.assertEqual(final["llm_calls"], 1)  # chi perceive, khong goi respond


class ReplanLoopTests(unittest.TestCase):
    def test_empty_candidates_loops_then_fails_gracefully_at_the_cap(self) -> None:
        calls = {"n": 0}

        def always_empty(state):
            calls["n"] += 1
            return {"candidates": [], "tool_results": []}

        final = run_request(
            "Can 50 ghe van phong",
            overrides={**BASE_OVERRIDES, "perceive": fake_perceive("search_new"),
                       "tool_search": always_empty},
        )
        self.assertEqual(final["status"], "graceful_fail")
        self.assertEqual(final["replan_count"], MAX_REPLAN)
        self.assertEqual(calls["n"], MAX_REPLAN + 1)  # 1 lan dau + MAX_REPLAN lan replan
        self.assertTrue(final["answer"])


class ResilienceTests(unittest.TestCase):
    def test_exception_inside_a_node_becomes_graceful_fail_not_a_crash(self) -> None:
        def boom(state):
            raise RuntimeError("node hong")

        final = run_request("x", overrides={**BASE_OVERRIDES, "perceive": boom})
        self.assertEqual(final["status"], "graceful_fail")
        self.assertIn("RuntimeError", final["error"])

    def test_latency_is_always_recorded(self) -> None:
        final = run_request("x", overrides={**BASE_OVERRIDES,
                                            "perceive": fake_perceive("out_of_scope")})
        self.assertIsInstance(final["latency_ms"], float)


if __name__ == "__main__":
    unittest.main()
