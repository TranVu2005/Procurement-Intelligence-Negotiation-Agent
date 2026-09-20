import os
import unittest
from unittest.mock import patch

from src.graph_state import new_state
from src.nodes.perceive import perceive
from src.nodes.reasoning import (
    diagnose, filter_hard, graceful_fail, plan, replan, respond_limits,
    score_rank, verify_output,
)
from src.nodes.respond import respond
from src.nodes.tools import confirm_gate, tool_compare, tool_detail, tool_search

# Gia tri parse_request() tra ve khi dung stub — co kiem soat, khong goi mang
# (RESPONSE-B-TO-C-AND-A §4 Phan A item 2)
_STUB_REQ = {
    "session_id": "sess_test",
    "created_at": "2026-09-17T00:00:00",
    "updated_at": "2026-09-17T00:00:00",
    "intent": "search_new",
    "supplier_ids": [],
    "supplier_id": None,
    "hard_constraints": {
        "product_type": "gh\u1ebf v\u0103n ph\u00f2ng",
        "quantity": 50,
        "budget_max": 200_000_000.0,
        "delivery_deadline_days": 14,
    },
    "soft_constraints": {
        "material_preference": None,
        "region_preference": None,
        "min_trust_score": None,
    },
    "conversation_history": [{"role": "user", "content": "x", "timestamp": "2026-09-17T00:00:00"}],
    "decisions_made": [],
}

ALL_NODES = [
    perceive, plan, tool_search, tool_compare, tool_detail, filter_hard,
    score_rank, verify_output, diagnose, replan, respond, respond_limits,
    graceful_fail, confirm_gate,
]


class NodeContractTests(unittest.TestCase):
    def test_every_node_returns_a_dict_patch_not_full_state(self) -> None:
        state = new_state("Can 50 ghe van phong, ngan sach 200 trieu, giao 14 ngay")
        # Monkeypatch parse_request cho perceive de khong goi mang trong contract test
        with patch("src.nodes.perceive.parse_request", return_value=(_STUB_REQ, 100, 50)):
            for node in ALL_NODES:
                with self.subTest(node=node.__name__):
                    patch_result = node(state)
                    self.assertIsInstance(patch_result, dict)
                    self.assertNotIn("user_input", patch_result, "node khong duoc ghi de user_input")

    def test_every_node_is_marked_as_stub_for_now(self) -> None:
        # Node da lam that thi bo khoi danh sach nay.
        done = {
            "plan", "filter_hard", "score_rank", "verify_output", "diagnose", "replan",
            "respond_limits", "graceful_fail", "tool_search", "tool_compare", "tool_detail",
            "confirm_gate", "respond", "perceive",
        }
        for node in ALL_NODES:
            if node.__name__ in done:
                continue
            with self.subTest(node=node.__name__):
                self.assertTrue(getattr(node, "__stub__", False))


class StubShapeTests(unittest.TestCase):
    """Kiem tra shape cua perceive bang monkeypatch — khong goi mang.

    Theo RESPONSE-B-TO-C-AND-A §4 Phan A item 2: unit test cua perceive phai
    mock parse_request()/update_state() voi JSON co kiem soat, khong goi mang.
    """

    def test_perceive_returns_correct_shape(self) -> None:
        """perceive (node that) phai tra ve dung cac khoa hop dong.

        Dung monkeypatch parse_request de kiem soat gia tri tra ve va dam bao
        test khong phu thuoc AGENT_LLM hay GOOGLE_API_KEY.
        """
        with patch("src.nodes.perceive.parse_request", return_value=(_STUB_REQ, 100, 50)):
            patch_dict = perceive(new_state("Can 50 ghe van phong, ngan sach 200 trieu, giao 14 ngay"))
        self.assertIn("intent", patch_dict)
        self.assertIn("req", patch_dict)
        self.assertIn("llm_calls", patch_dict)
        self.assertIn("hard_constraints", patch_dict["req"])
        self.assertIn("soft_constraints", patch_dict["req"])

    def test_perceive_multiturn_calls_update_state(self) -> None:
        """Multi-turn: perceive phai goi update_state() (khong phai parse_request)."""
        update_result = {**_STUB_REQ, "hard_constraints": {**_STUB_REQ["hard_constraints"], "budget_max": 300_000_000.0}}
        existing_state = new_state("x", req=_STUB_REQ)
        with patch("src.nodes.perceive.update_state", return_value=(update_result, 100, 50)) as mock_update:
            patch_dict = perceive(existing_state)
        mock_update.assert_called_once()
        self.assertEqual(patch_dict["req"]["hard_constraints"]["budget_max"], 300_000_000.0)


    def test_verify_output_stub_returns_structured_verdict_not_boolean(self) -> None:
        patch = verify_output(new_state("x"))
        verdict = patch["verdict"]
        self.assertIsInstance(verdict, dict)
        self.assertEqual(set(verdict), {"passed", "violations", "claims"})

    def test_respond_without_evidence_calls_no_llm(self) -> None:
        self.assertEqual(respond(new_state("x"))["llm_calls"], 0)


@unittest.skipUnless(
    os.getenv("GOOGLE_API_KEY"),
    "Bo qua integration test: can GOOGLE_API_KEY de goi LLM that "
    "(RESPONSE-B-TO-C-AND-A §4 Phan A item 3)",
)
class IntegrationPerceiveTests(unittest.TestCase):
    """Test real-model cho perceive — chi chay khi co GOOGLE_API_KEY.

    Day la integration test, khong thuoc nhom unit test chay trong CI stub.
    Chay tay: GOOGLE_API_KEY=xxx python -m unittest tests.test_node_stubs.IntegrationPerceiveTests
    """

    def test_perceive_real_model_search_new(self) -> None:
        """Kiem tra parse_request() that voi input ro rang cho search_new."""
        patch_dict = perceive(new_state(
            "Can mua 20 ban lam viec, ngan sach 100 trieu, giao trong 7 ngay"
        ))
        self.assertEqual(patch_dict["intent"], "search_new")
        self.assertIn("hard_constraints", patch_dict["req"])
        hard = patch_dict["req"]["hard_constraints"]
        self.assertIsNotNone(hard.get("product_type"))
        self.assertGreater(hard.get("quantity", 0), 0)
        self.assertGreater(hard.get("budget_max", 0), 0)
        self.assertGreater(hard.get("delivery_deadline_days", 0), 0)


if __name__ == "__main__":
    unittest.main()
