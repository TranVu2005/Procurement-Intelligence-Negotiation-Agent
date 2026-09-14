import os
import unittest
from unittest.mock import patch

from src.llm import MODEL_NAME, StubLLM, get_llm, usage_of


class StubLLMTests(unittest.TestCase):
    def test_stub_returns_fixed_deterministic_text(self) -> None:
        stub = StubLLM(latency_s=0.0)
        first = stub.invoke([("human", "a")]).content
        second = stub.invoke([("human", "b")]).content
        self.assertEqual(first, second)
        self.assertTrue(first)

    def test_stub_reports_usage_metadata(self) -> None:
        message = StubLLM(latency_s=0.0).invoke([("human", "a")])
        tokens_in, tokens_out = usage_of(message)
        self.assertGreater(tokens_in, 0)
        self.assertGreater(tokens_out, 0)

    def test_stub_stream_yields_chunks_that_join_to_full_text(self) -> None:
        stub = StubLLM(latency_s=0.0)
        chunks = [c.content for c in stub.stream([("human", "a")])]
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks), stub.invoke([("human", "a")]).content)


class GetLLMTests(unittest.TestCase):
    def test_env_flag_selects_stub_without_api_key(self) -> None:
        with patch.dict(os.environ, {"AGENT_LLM": "stub"}, clear=False):
            self.assertIsInstance(get_llm(), StubLLM)

    def test_missing_api_key_raises_actionable_error(self) -> None:
        env = {k: v for k, v in os.environ.items() if k not in ("GOOGLE_API_KEY", "AGENT_LLM")}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(EnvironmentError) as ctx:
                get_llm()
        self.assertIn("GOOGLE_API_KEY", str(ctx.exception))

    def test_model_name_is_single_source_of_truth(self) -> None:
        self.assertEqual(MODEL_NAME, "gemini-3.6-flash")


class UsageOfTests(unittest.TestCase):
    def test_missing_usage_metadata_returns_zeros_not_crash(self) -> None:
        class Bare:
            content = "x"

        self.assertEqual(usage_of(Bare()), (0, 0))


if __name__ == "__main__":
    unittest.main()
