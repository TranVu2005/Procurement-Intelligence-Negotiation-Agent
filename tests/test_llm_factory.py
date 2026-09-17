import json
import os
import unittest
from unittest.mock import patch

from src.llm import MODEL_NAME, StubLLM, get_llm, usage_of


class StubLLMBindTests(unittest.TestCase):
    """parser.py (Perception) goi _get_llm().bind(response_format=...).invoke(...)
    roi json.loads(response.content) - StubLLM phai chiu duoc chuoi goi nay."""

    def test_bind_returns_object_with_invoke(self) -> None:
        bound = StubLLM(latency_s=0.0).bind(response_format={"type": "json_object"})
        message = bound.invoke([("human", "a")])
        self.assertTrue(message.content)

    def test_bound_content_is_valid_json_matching_extraction_schema(self) -> None:
        bound = StubLLM(latency_s=0.0).bind(response_format={"type": "json_object"})
        parsed = json.loads(bound.invoke([("human", "a")]).content)
        self.assertEqual(
            set(parsed),
            {"intent", "product_type", "quantity", "budget_max",
             "delivery_deadline_days", "material_preference", "region_preference",
             "min_trust_score", "supplier_ids", "supplier_id"},
        )
        self.assertIn(parsed["intent"],
                      {"search_new", "compare_specific", "supplier_detail", "out_of_scope"})

    def test_bind_ignores_kwargs_and_keeps_deterministic_latency(self) -> None:
        bound = StubLLM(latency_s=0.0).bind(response_format={"type": "json_object"},
                                             anything_else=123)
        self.assertIsInstance(bound, StubLLM)

    def test_unbound_stub_still_returns_prose_not_json(self) -> None:
        # bind() phai tra ve BIEN THE moi, khong doi hanh vi cua respond's stub
        plain = StubLLM(latency_s=0.0).invoke([("human", "a")]).content
        with self.assertRaises(json.JSONDecodeError):
            json.loads(plain)


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

    def test_openrouter_provider_missing_key_raises_actionable_error(self) -> None:
        env = {k: v for k, v in os.environ.items()
               if k not in ("OPENROUTER_API_KEY", "AGENT_LLM")}
        env["LLM_PROVIDER"] = "openrouter"
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(EnvironmentError) as ctx:
                get_llm()
        self.assertIn("OPENROUTER_API_KEY", str(ctx.exception))

    def test_openrouter_provider_builds_chat_openai_with_openrouter_base_url(self) -> None:
        env = {"LLM_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "sk-test",
               "AGENT_LLM": ""}
        with patch.dict(os.environ, env, clear=False):
            llm = get_llm()
        from langchain_openai import ChatOpenAI
        self.assertIsInstance(llm, ChatOpenAI)
        self.assertEqual(str(llm.openai_api_base), "https://openrouter.ai/api/v1")
        self.assertEqual(llm.model_name, "openrouter/free")

    def test_openrouter_model_is_overridable_via_env(self) -> None:
        env = {"LLM_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "sk-test",
               "OPENROUTER_MODEL": "z-ai/glm-5.2:free", "AGENT_LLM": ""}
        with patch.dict(os.environ, env, clear=False):
            llm = get_llm()
        self.assertEqual(llm.model_name, "z-ai/glm-5.2:free")

    def test_agent_llm_stub_wins_over_llm_provider_openrouter(self) -> None:
        env = {"LLM_PROVIDER": "openrouter", "AGENT_LLM": "stub"}
        with patch.dict(os.environ, env, clear=False):
            self.assertIsInstance(get_llm(), StubLLM)


class UsageOfTests(unittest.TestCase):
    def test_missing_usage_metadata_returns_zeros_not_crash(self) -> None:
        class Bare:
            content = "x"

        self.assertEqual(usage_of(Bare()), (0, 0))


if __name__ == "__main__":
    unittest.main()
