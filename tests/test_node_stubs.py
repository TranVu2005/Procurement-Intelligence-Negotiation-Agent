import unittest

from src.graph_state import new_state
from src.nodes.perceive import perceive
from src.nodes.reasoning import (
    diagnose, filter_hard, graceful_fail, plan, replan, respond_limits,
    score_rank, verify_output,
)
from src.nodes.respond import respond
from src.nodes.tools import confirm_gate, tool_compare, tool_detail, tool_search

ALL_NODES = [
    perceive, plan, tool_search, tool_compare, tool_detail, filter_hard,
    score_rank, verify_output, diagnose, replan, respond, respond_limits,
    graceful_fail, confirm_gate,
]


class NodeContractTests(unittest.TestCase):
    def test_every_node_returns_a_dict_patch_not_full_state(self) -> None:
        state = new_state("Can 50 ghe van phong, ngan sach 200 trieu, giao 14 ngay")
        for node in ALL_NODES:
            with self.subTest(node=node.__name__):
                patch = node(state)
                self.assertIsInstance(patch, dict)
                self.assertNotIn("user_input", patch, "node khong duoc ghi de user_input")

    def test_every_node_is_marked_as_stub_for_now(self) -> None:
        for node in ALL_NODES:
            with self.subTest(node=node.__name__):
                self.assertTrue(getattr(node, "__stub__", False))


class StubShapeTests(unittest.TestCase):
    def test_perceive_stub_sets_intent_and_req(self) -> None:
        patch = perceive(new_state("x"))
        self.assertEqual(patch["intent"], "search_new")
        self.assertIn("hard_constraints", patch["req"])

    def test_verify_output_stub_returns_structured_verdict_not_boolean(self) -> None:
        patch = verify_output(new_state("x"))
        verdict = patch["verdict"]
        self.assertIsInstance(verdict, dict)
        self.assertEqual(set(verdict), {"passed", "violations", "claims"})

    def test_tool_nodes_append_exactly_one_audit_entry(self) -> None:
        for node in (tool_search, tool_compare, tool_detail):
            with self.subTest(node=node.__name__):
                self.assertEqual(len(node(new_state("x"))["tool_results"]), 1)

    def test_respond_stub_counts_one_llm_call(self) -> None:
        self.assertEqual(respond(new_state("x"))["llm_calls"], 1)


if __name__ == "__main__":
    unittest.main()
