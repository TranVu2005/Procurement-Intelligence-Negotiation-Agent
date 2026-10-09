import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.graph import run_request
from src.logging_utils import tracer
from src.eval.scoring import aggregate, grade_case
from scripts import run_loadtest


class ComponentLatencyTests(unittest.TestCase):
    def test_request_tracks_components_and_trace_events(self):
        def perceive(state):
            return {"intent": "out_of_scope", "llm_calls": 1, "tokens_in": 5}
        with patch("src.graph.log_event") as events:
            final = run_request("x", overrides={"perceive": perceive})
        for key in ("llm_ms", "tool_ms", "other_ms"):
            self.assertGreaterEqual(final[key], 0)
        self.assertGreater(final["llm_ms"], 0)
        self.assertEqual(final["tool_ms"], 0)
        self.assertAlmostEqual(final["latency_ms"], final["llm_ms"] + final["tool_ms"] + final["other_ms"], delta=0.02)
        self.assertTrue(any(call.args[1] == "node_end" for call in events.call_args_list))

    def test_run_record_redacts_identifiers_and_keeps_components(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(tracer, "LOG_DIR", Path(tmp)):
            path = tracer.write_run_record({"trace_id": "TEST", "session_id": "sk-" + "a" * 30,
                "llm_ms": 10, "tool_ms": 20, "other_ms": 5})
            record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(record["session_id"], "***")
        self.assertEqual(record["llm_ms"], 10)
        self.assertEqual(record["tool_ms"], 20)

    def test_eval_and_loadtest_component_percentiles(self):
        final = {"status": "success", "llm_ms": 10, "tool_ms": 20, "other_ms": 5}
        report = aggregate([grade_case({"id": "TEST", "oracle": {}}, final)])
        self.assertEqual(report["llm_p50_ms"], 10)
        self.assertEqual(report["tool_p95_ms"], 20)
        with patch.object(run_loadtest, "run_request", return_value=final):
            load = run_loadtest.run_level("x", 1, 2)
        self.assertEqual(load["llm_p50_ms"], 10)
        self.assertEqual(load["tool_p95_ms"], 20)
