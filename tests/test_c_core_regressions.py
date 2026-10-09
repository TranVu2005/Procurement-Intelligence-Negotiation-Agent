import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.graph import guard_perceive, run_request
from src.graph_state import new_state
from src.llm import usage_of
from src.nodes.respond import respond
from src.nodes.tools import tool_search
from src.perception.parser import MissingFieldError
from src.tools.supplier_tools import search_suppliers


class PartialPerceptionTests(unittest.TestCase):
    def test_missing_input_preserves_partial_request_and_usage(self):
        partial = {"intent": "search_new", "session_id": "TEST_PARTIAL",
                   "hard_constraints": {"product_type": "kệ", "quantity": None}}
        exc = MissingFieldError(["quantity"], partial_state=partial)
        exc.tokens_in, exc.tokens_out = 123, 27
        def fail(state):
            raise exc
        with patch("src.graph.save_session"), patch("src.graph.append_conversation"):
            final = run_request("x", overrides={"perceive": fail})
        self.assertEqual(final["intent"], "search_new")
        self.assertEqual(final["req"], partial)
        self.assertEqual(final["tokens_in"], 123)
        self.assertEqual(final["tokens_out"], 27)
        self.assertEqual(final["status"], "needs_input")

    def test_value_error_without_usage_does_not_invent_tokens(self):
        exc = ValueError("invalid")
        exc.partial_state = {"intent": "compare_specific", "hard_constraints": {}}
        def fail(state):
            raise exc
        out = guard_perceive(fail)(new_state("x"))
        self.assertEqual(out["intent"], "compare_specific")
        self.assertEqual(out["tokens_in"], 0)

    def test_gemini_and_openrouter_normalized_usage(self):
        for provider in ("gemini", "openrouter"):
            with self.subTest(provider=provider):
                self.assertEqual(usage_of(SimpleNamespace(usage_metadata={
                    "input_tokens": 31, "output_tokens": 7})), (31, 7))
        self.assertEqual(usage_of(SimpleNamespace()), (0, 0))

    def test_respond_sums_stream_usage(self):
        llm = SimpleNamespace(stream=lambda _: iter([
            SimpleNamespace(content="a", usage_metadata={"input_tokens": 5, "output_tokens": 2}),
            SimpleNamespace(content="b", usage_metadata={"input_tokens": 0, "output_tokens": 3})]))
        with patch("src.nodes.respond.get_llm", return_value=llm):
            final = respond({"ranked": [{"MaNCC": "TEST_A"}]})
        self.assertEqual((final["tokens_in"], final["tokens_out"]), (5, 5))


class EmptyToolTests(unittest.TestCase):
    def test_filters_report_where_matches_disappear(self):
        data = [{"LoaiSanPham": "kệ", "ChatLieu": "kim_loai", "KhuVuc": "Ha Noi"},
                {"LoaiSanPham": "kệ", "ChatLieu": "go", "KhuVuc": "Ha Noi"}]
        with patch("src.tools.supplier_tools._load_data", return_value=data):
            result = search_suppliers("kệ", "kim_loai", "Da Nang")
        self.assertEqual(result["error_type"], "no_match")
        self.assertEqual(result["filter_stats"]["counts"],
                         {"product_type": 2, "material": 1, "region": 0})

    def test_empty_search_never_compares_an_empty_batch(self):
        calls = []
        def fake_tool(state, tool, params, **kwargs):
            calls.append(tool)
            return {"suppliers": []}, {"tool": tool, "status": "ok", "result": {"suppliers": []}}
        state = {**new_state("x"), "req": {"hard_constraints": {"quantity": 10}},
                 "plan": {"steps": [{"action": "search_suppliers", "params": {"product_type": "kệ"}}]}}
        with patch("src.nodes.tools.run_tool", side_effect=fake_tool):
            out = tool_search(state)
        self.assertEqual(calls, ["search_suppliers"])
        self.assertIn("filter_stats", out)

    def test_all_empty_branches_have_a_final_answer(self):
        hard = {"product_type": "kệ", "quantity": 10, "budget_max": 50000000,
                "delivery_deadline_days": 20}
        cases = [("search_new", {"search_suppliers": "no_match"}),
                 ("search_new", None), ("compare_specific", None), ("supplier_detail", None)]
        for intent, inject in cases:
            with self.subTest(intent=intent, inject=inject):
                def perception(state):
                    return {"intent": intent, "req": {"session_id": "TEST_EMPTY", "hard_constraints": hard,
                            "soft_constraints": {}, "target_supplier_ids": ["TEST_MISSING"]}}
                with patch("src.tools.supplier_tools._load_data", return_value=[]):
                    final = run_request("x", _inject=inject, overrides={"perceive": perception})
                self.assertEqual(final["status"], "graceful_fail")
                self.assertTrue(final["answer"].strip())
                self.assertFalse(any(e["tool"] == "compare_price" and not e["params"]["supplier_ids"]
                                     for e in final["tool_results"]))
