import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_loadtest  # noqa: E402


class PercentileTests(unittest.TestCase):
    def test_p50_and_p95_of_a_known_series(self) -> None:
        values = [float(n) for n in range(1, 101)]
        self.assertEqual(run_loadtest.percentile(values, 50), 50.0)
        self.assertEqual(run_loadtest.percentile(values, 95), 95.0)

    def test_empty_series_returns_none(self) -> None:
        self.assertIsNone(run_loadtest.percentile([], 50))

    def test_single_value_series(self) -> None:
        self.assertEqual(run_loadtest.percentile([7.0], 95), 7.0)


class RunLevelTests(unittest.TestCase):
    def test_every_request_is_issued_and_counted(self) -> None:
        calls = {"n": 0}

        def fake_run_request(user_input, session_id=None, _inject=None):
            calls["n"] += 1
            return {"status": "success", "latency_ms": 10.0}

        with patch.object(run_loadtest, "run_request", fake_run_request):
            result = run_loadtest.run_level("x", concurrency=4, requests_per_level=8)

        self.assertEqual(calls["n"], 8)
        self.assertEqual(result["concurrency"], 4)
        self.assertEqual(result["requests"], 8)
        self.assertEqual(result["error_rate"], 0.0)
        self.assertGreater(result["throughput_rps"], 0)

    def test_failures_are_counted_not_raised(self) -> None:
        def boom(user_input, session_id=None, _inject=None):
            raise RuntimeError("sap")

        with patch.object(run_loadtest, "run_request", boom):
            result = run_loadtest.run_level("x", concurrency=2, requests_per_level=4)
        self.assertEqual(result["error_rate"], 1.0)

    def test_graceful_fail_counts_as_an_error_for_load_reporting(self) -> None:
        with patch.object(run_loadtest, "run_request",
                          lambda *a, **k: {"status": "graceful_fail", "latency_ms": 5.0}):
            result = run_loadtest.run_level("x", concurrency=1, requests_per_level=2)
        self.assertEqual(result["error_rate"], 1.0)

    def test_cpu_and_ram_are_reported(self) -> None:
        with patch.object(run_loadtest, "run_request",
                          lambda *a, **k: {"status": "success", "latency_ms": 1.0}):
            result = run_loadtest.run_level("x", concurrency=1, requests_per_level=1)
        self.assertIn("cpu_percent", result)
        self.assertIn("rss_mb", result)


class MarkdownReportTests(unittest.TestCase):
    REPORT = {
        "generated_at": "2026-09-18T10:00:00", "llm_mode": "stub", "prompt": "x",
        "stub_latency": {"mean_s": 9.2, "stddev_s": 1.1},
        "levels": [{"concurrency": 10, "requests": 20, "elapsed_s": 30.0,
                    "throughput_rps": 0.667, "latency_p50_ms": 18500.0,
                    "latency_p95_ms": 21000.0, "error_rate": 0.0,
                    "cpu_percent": 12.5, "rss_mb": 180.2}],
    }

    def test_stub_parameters_are_stated_in_the_report(self) -> None:
        text = run_loadtest.to_markdown(self.REPORT)
        self.assertIn("stub", text)
        self.assertIn("mean=9.2s", text)

    def test_every_level_is_a_table_row(self) -> None:
        text = run_loadtest.to_markdown(self.REPORT)
        self.assertIn("| 10 | 20 | 0.667 | 18500.0 | 21000.0 | 0.0 | 12.5 | 180.2 |", text)

    def test_real_mode_has_no_stub_line(self) -> None:
        report = {**self.REPORT, "llm_mode": "real"}
        report.pop("stub_latency")
        self.assertIn("- LLM: real", run_loadtest.to_markdown(report))


if __name__ == "__main__":
    unittest.main()
