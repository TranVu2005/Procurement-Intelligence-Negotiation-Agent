import json
import os
import unittest
from unittest.mock import patch

from src.graph import route_intent, run_request
from src.graph_state import new_state
from src.perception.parser import InvalidProductTypeError, MissingFieldError


def raising(exc):
    def node(state):
        raise exc
    return node


def fake_perceive_with_session(state):
    req = {
        "session_id": "sess_fake01",
        "conversation_history": [{"role": "user", "content": "x"}],
        "hard_constraints": {},
    }
    return {"intent": "out_of_scope", "req": req, "llm_calls": 1}


class PerceiveGuardTests(unittest.TestCase):
    def test_missing_field_becomes_needs_input_naming_the_fields(self) -> None:
        final = run_request("Toi muon mua ban lam viec", overrides={
            "perceive": raising(MissingFieldError(["số lượng", "ngân sách tối đa"])),
        })
        self.assertEqual(final["status"], "needs_input")
        self.assertIn("số lượng", final["answer"])
        self.assertIn("ngân sách tối đa", final["answer"])
        self.assertEqual(final["tool_results"], [])
        self.assertEqual(final["llm_calls"], 1)
        self.assertNotIn("error", final)

    def test_unknown_product_type_becomes_needs_input(self) -> None:
        final = run_request("Can 10 may lanh", overrides={
            "perceive": raising(InvalidProductTypeError("máy lạnh")),
        })
        self.assertEqual(final["status"], "needs_input")
        self.assertIn("máy lạnh", final["answer"])

    def test_invalid_number_becomes_needs_input(self) -> None:
        final = run_request("Can 0 ghe", overrides={
            "perceive": raising(ValueError("quantity phải > 0, nhận được: 0")),
        })
        self.assertEqual(final["status"], "needs_input")
        self.assertIn("quantity", final["answer"])

    def test_broken_llm_json_is_a_system_failure_not_a_question(self) -> None:
        final = run_request("x", overrides={
            "perceive": raising(json.JSONDecodeError("Expecting value", "", 0)),
        })
        self.assertEqual(final["status"], "graceful_fail")
        self.assertIn("JSONDecodeError", final["error"])

    def test_route_intent_sends_needs_input_to_graceful_fail(self) -> None:
        state = {**new_state("x"), "intent": "search_new", "status": "needs_input"}
        self.assertEqual(route_intent(state), "graceful_fail")


class SessionPropagationTests(unittest.TestCase):
    def test_session_id_created_by_perception_reaches_the_final_state(self) -> None:
        with patch("src.graph.save_session") as save, patch("src.graph.append_conversation"):
            final = run_request("x", overrides={"perceive": fake_perceive_with_session})
        self.assertEqual(final["session_id"], "sess_fake01")
        save.assert_called_once()
        self.assertEqual(save.call_args.args[0], "sess_fake01")

    def test_a_given_session_id_is_not_overwritten(self) -> None:
        with patch("src.graph.save_session"), patch("src.graph.append_conversation"), \
                patch("src.graph.session_exists", return_value=False):
            final = run_request("x", session_id="sess_given",
                                overrides={"perceive": fake_perceive_with_session})
        self.assertEqual(final["session_id"], "sess_given")


class RealPerceiveMultiTurnTests(unittest.TestCase):
    """Parser that + StubLLM (khong goi mang), DB thay bang dict trong bo nho."""

    def test_second_turn_reuses_the_session_and_appends_history(self) -> None:
        store: dict = {}
        with patch.dict(os.environ, {"AGENT_LLM": "stub"}), \
                patch("src.llm.STUB_LATENCY_MEAN_S", 0.0), \
                patch("src.llm.STUB_LATENCY_STDDEV_S", 0.0), \
                patch("src.graph.session_exists", side_effect=lambda sid: sid in store), \
                patch("src.graph.load_session", side_effect=lambda sid: store.get(sid)), \
                patch("src.graph.save_session",
                      side_effect=lambda sid, req: store.__setitem__(sid, req)), \
                patch("src.graph.append_conversation"):
            first = run_request("Can 50 ghe van phong, ngan sach 200 trieu, giao trong 14 ngay")
            second = run_request("Tang ngan sach len 250 trieu", session_id=first["session_id"])
        self.assertTrue(first["session_id"])
        self.assertEqual(second["session_id"], first["session_id"])
        self.assertEqual(len(second["req"]["conversation_history"]), 2)


if __name__ == "__main__":
    unittest.main()
