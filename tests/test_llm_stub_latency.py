import os
import time
import unittest
from unittest.mock import patch

from src import llm


class StubLatencyTests(unittest.TestCase):
    def test_defaults_come_from_the_module_constants(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AGENT_STUB_LATENCY_MEAN_S", None)
            os.environ.pop("AGENT_STUB_LATENCY_STDDEV_S", None)
            settings = llm.stub_latency_settings()
        self.assertEqual(settings, {"mean_s": llm.STUB_LATENCY_MEAN_S,
                                    "stddev_s": llm.STUB_LATENCY_STDDEV_S})

    def test_environment_overrides_the_constants(self) -> None:
        with patch.dict(os.environ, {"AGENT_STUB_LATENCY_MEAN_S": "0.5",
                                     "AGENT_STUB_LATENCY_STDDEV_S": "0.1"}):
            self.assertEqual(llm.stub_latency_settings(), {"mean_s": 0.5, "stddev_s": 0.1})

    def test_zero_latency_stub_returns_immediately(self) -> None:
        with patch.dict(os.environ, {"AGENT_STUB_LATENCY_MEAN_S": "0",
                                     "AGENT_STUB_LATENCY_STDDEV_S": "0"}):
            started = time.perf_counter()
            llm.StubLLM().invoke([])
        self.assertLess(time.perf_counter() - started, 1.0)


if __name__ == "__main__":
    unittest.main()
