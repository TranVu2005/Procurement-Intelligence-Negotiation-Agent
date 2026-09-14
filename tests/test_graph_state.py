import unittest

from src.graph_state import MAX_REPLAN, new_state, tool_result_entry


class NewStateTests(unittest.TestCase):
    def test_defaults_are_zero_not_none(self) -> None:
        state = new_state("Can 50 ghe van phong")
        self.assertEqual(state["user_input"], "Can 50 ghe van phong")
        self.assertEqual(state["replan_count"], 0)
        self.assertEqual(state["llm_calls"], 0)
        self.assertEqual(state["tokens_in"], 0)
        self.assertEqual(state["tokens_out"], 0)
        self.assertEqual(state["tool_results"], [])
        self.assertIsNone(state["pending_confirmation"])

    def test_trace_id_is_generated_and_unique(self) -> None:
        first = new_state("a")["trace_id"]
        second = new_state("a")["trace_id"]
        self.assertNotEqual(first, second)
        self.assertEqual(len(first), 32)

    def test_session_id_and_inject_are_passed_through(self) -> None:
        state = new_state("a", session_id="sess_001", inject={"search_suppliers": "timeout"})
        self.assertEqual(state["session_id"], "sess_001")
        self.assertEqual(state["inject"], {"search_suppliers": "timeout"})

    def test_inject_defaults_to_empty_dict_not_none(self) -> None:
        # Node tool goi .get() tren state["inject"] -> khong duoc la None
        self.assertEqual(new_state("a")["inject"], {})


class ToolResultEntryTests(unittest.TestCase):
    def test_entry_has_every_field_autoeval_reads(self) -> None:
        entry = tool_result_entry(
            tool="search_suppliers",
            params={"product_type": "ghe van phong"},
            status="ok",
            result={"suppliers": []},
            latency_ms=12.5,
            trace_id="abc",
        )
        self.assertEqual(
            set(entry),
            {"step_id", "tool", "params", "status", "latency_ms", "attempts",
             "error_type", "result", "trace_id"},
        )
        self.assertEqual(entry["attempts"], 1)
        self.assertIsNone(entry["error_type"])
        self.assertIsNone(entry["step_id"])

    def test_params_are_redacted(self) -> None:
        entry = tool_result_entry(
            tool="search_suppliers",
            params={"product_type": "ke", "api_key": "SECRET"},
            status="ok",
            result={},
            latency_ms=1.0,
            trace_id="abc",
        )
        self.assertEqual(entry["params"]["api_key"], "***")
        self.assertEqual(entry["params"]["product_type"], "ke")

    def test_max_replan_matches_planner(self) -> None:
        from src.reasoning.planner import MAX_REPLAN_COUNT
        self.assertEqual(MAX_REPLAN, MAX_REPLAN_COUNT)


if __name__ == "__main__":
    unittest.main()
