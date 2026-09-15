import unittest
from unittest.mock import patch

import src.agent as agent


class RenderTests(unittest.TestCase):
    def test_render_shows_answer_and_audit_counters(self) -> None:
        text = agent.render({
            "answer": "Ket qua day",
            "status": "success",
            "llm_calls": 2,
            "tool_results": [{"tool": "search_suppliers"}, {"tool": "compare_price"}],
            "latency_ms": 1234.5,
            "trace_id": "deadbeef",
        })
        self.assertIn("Ket qua day", text)
        self.assertIn("llm_calls=2", text)
        self.assertIn("tool_calls=2", text)
        self.assertIn("deadbeef", text)

    def test_render_handles_missing_keys_without_crashing(self) -> None:
        self.assertIsInstance(agent.render({}), str)


class MainLoopTests(unittest.TestCase):
    def test_quit_exits_before_calling_run_request(self) -> None:
        with patch("builtins.input", side_effect=["quit"]), \
             patch("src.agent.run_request") as run:
            agent.main()
        run.assert_not_called()

    def test_session_id_is_reused_across_turns(self) -> None:
        final = {"answer": "ok", "status": "success", "session_id": "sess_x", "trace_id": "t"}
        with patch("builtins.input", side_effect=["cau 1", "cau 2", "quit"]), \
             patch("src.agent.run_request", return_value=final) as run:
            agent.main()
        self.assertEqual(run.call_count, 2)
        self.assertIsNone(run.call_args_list[0].kwargs["session_id"])
        self.assertEqual(run.call_args_list[1].kwargs["session_id"], "sess_x")


if __name__ == "__main__":
    unittest.main()
