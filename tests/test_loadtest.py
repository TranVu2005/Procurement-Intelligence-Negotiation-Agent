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


if __name__ == "__main__":
    unittest.main()
