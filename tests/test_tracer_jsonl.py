import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.logging_utils import tracer


class JsonlTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(tracer, "LOG_DIR", Path(self._tmp.name))
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    def test_log_event_appends_a_readable_jsonl_line(self) -> None:
        tracer.log_event("trace123", "tool_call_start", tool_name="search_suppliers")
        path = Path(self._tmp.name) / "trace123.jsonl"
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        record = json.loads(lines[0])
        self.assertEqual(record["trace_id"], "trace123")
        self.assertEqual(record["event"], "tool_call_start")
        self.assertEqual(record["tool_name"], "search_suppliers")
        self.assertIn("ts", record)

    def test_two_events_produce_two_lines_in_order(self) -> None:
        tracer.log_event("t", "first")
        tracer.log_event("t", "second")
        lines = (Path(self._tmp.name) / "t.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual([json.loads(l)["event"] for l in lines], ["first", "second"])

    def test_secrets_never_reach_the_file(self) -> None:
        tracer.log_event("t", "boot", google_api_key="AIza-REAL-SECRET")
        text = (Path(self._tmp.name) / "t.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("AIza-REAL-SECRET", text)
        self.assertIn("***", text)

    def test_unserialisable_payload_is_logged_as_text_not_dropped(self) -> None:
        tracer.log_event("t", "odd", value=object())
        text = (Path(self._tmp.name) / "t.jsonl").read_text(encoding="utf-8")
        self.assertIn("odd", text)


class RunRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch.object(tracer, "LOG_DIR", Path(self._tmp.name))
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    def test_run_record_captures_every_metric_the_report_needs(self) -> None:
        tracer.write_run_record({
            "trace_id": "t", "session_id": "s", "intent": "search_new",
            "status": "success", "llm_calls": 2, "tokens_in": 900, "tokens_out": 300,
            "latency_ms": 1500.0, "replan_count": 0,
            "tool_results": [{"tool": "search_suppliers", "status": "ok"}],
        })
        record = json.loads((Path(self._tmp.name) / "runs.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(record["llm_calls"], 2)
        self.assertEqual(record["tool_calls"], 1)
        self.assertEqual(record["tokens_in"], 900)
        self.assertEqual(record["status"], "success")
        self.assertIn("ts", record)

    def test_run_record_never_stores_the_full_tool_payloads(self) -> None:
        tracer.write_run_record({
            "trace_id": "t", "status": "success",
            "tool_results": [{"tool": "x", "status": "ok", "result": {"huge": "x" * 10_000}}],
        })
        text = (Path(self._tmp.name) / "runs.jsonl").read_text(encoding="utf-8")
        self.assertLess(len(text), 2_000)


if __name__ == "__main__":
    unittest.main()
