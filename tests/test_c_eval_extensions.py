import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.eval.scoring import aggregate, grade_case, round_spread
from scripts import run_autoeval as runner


def grade(oracle=None, **final):
    return grade_case({"id": "TEST", "category": "happy_path", "oracle": oracle or {}},
                      {"status": "success", "intent": "search_new", "answer": "ok", **final})


class ExtensionGradingTests(unittest.TestCase):
    def test_extraction_checks_fields_and_reports_accuracy(self):
        result = grade({"must_extract": {"hard_constraints": {"quantity": 10, "budget_max": 20}}},
                       req={"hard_constraints": {"quantity": 10, "budget_max": 30}})
        self.assertFalse(result["passed"])
        report = aggregate([result])
        self.assertEqual(report["metrics"]["field_accuracy"], 0.5)
        self.assertEqual(report["by_field"]["hard_constraints.quantity"]["accuracy"], 1)

    def test_unimplemented_fields_are_unmeasurable_and_never_pass(self):
        for oracle in ({"expect_priority": "price"}, {"must_suggest_relax": True},
                       {"must_extract": {"soft_constraints": {"priority": "price"}}},
                       {"no_null_fields": ["weights_used"]}):
            result = grade(oracle)
            self.assertIsNone(result["passed"])
            self.assertTrue(result["unmeasurable"])
            self.assertIsNone(aggregate([result])["metrics"]["task_success_rate"])

    def test_empty_fields_fail_and_correct_priority_relaxation_pass(self):
        self.assertFalse(grade({"no_null_fields": ["answer"]}, answer="")["passed"])
        self.assertFalse(grade({"must_suggest_relax": True}, relax_suggestions=[])["passed"])
        self.assertTrue(grade({"expect_priority": "price", "must_suggest_relax": True},
                              weights_used={"preset": "price"},
                              relax_suggestions=[{"constraint": "budget_max"}])["passed"])

    def test_category_intent_latency_tokens_and_cost(self):
        a = grade({"must_reach_intent": "search_new"}, latency_ms=10, tokens_in=100,
                  tokens_out=50, llm_calls=2, model="TEST_MODEL")
        b = grade({"must_reach_intent": "out_of_scope"}, latency_ms=30, tokens_in=200,
                  tokens_out=100, llm_calls=1, model="TEST_MODEL")
        report = aggregate([a, b], pricing={"TEST_MODEL": {
            "input_usd_per_million": 1, "output_usd_per_million": 2}})
        self.assertEqual(report["by_category"]["happy_path"]["total_cases"], 2)
        self.assertEqual(report["metrics"]["intent_routing_accuracy"], 0.5)
        self.assertEqual(report["latency_avg_ms"], 20)
        self.assertEqual(report["latency_max_ms"], 30)
        self.assertEqual(report["avg_tokens_in"], 150)
        self.assertAlmostEqual(report["estimated_cost_total_usd"], 0.0006)
        self.assertIsNone(aggregate([a])["estimated_cost_total_usd"])

    def test_operations_count_each_turn_as_a_request(self):
        result = grade(_requests=[{"latency_ms": 10, "tokens_in": 50, "llm_calls": 1},
                                 {"latency_ms": 30, "tokens_in": 150, "llm_calls": 2}])
        report = aggregate([result])
        self.assertEqual(report["total_requests"], 2)
        self.assertEqual(report["avg_tokens_in"], 100)

    def test_spread_covers_new_metrics_and_operations(self):
        spread = round_spread([aggregate([grade(tokens_in=10)]),
                               aggregate([grade(tokens_in=30)])])
        self.assertEqual(spread["avg_tokens_in"]["min"], 10)
        self.assertEqual(spread["avg_tokens_in"]["max"], 30)


class TierRunnerTests(unittest.TestCase):
    def test_loader_warns_about_legacy_cases_and_filters_tiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.jsonl"
            path.write_text('\n'.join(json.dumps(c) for c in [
                {"id": "OLD"}, {"id": "P", "tier": "pipeline", "oracle": {}},
                {"id": "L", "tier": "llm", "oracle": {}}, {"id": "B", "oracle": {}}]), encoding="utf-8")
            stream = io.StringIO()
            with contextlib.redirect_stderr(stream):
                cases = runner.load_cases(path, tier="llm")
            self.assertEqual([c["id"] for c in cases], ["L", "B"])
            self.assertIn("1", stream.getvalue())
            self.assertIn("cases.jsonl", stream.getvalue())

    def test_two_tier_markdown_and_stub_warning(self):
        report = {"generated_at": "2026-10-09T00:00:00+07:00", "dataset_version": "TEST",
                  "llm_mode": "stub", "model": "StubLLM", "tier": "llm", "repeat": 1,
                  **aggregate([grade()]), "tiers": {"pipeline": aggregate([]), "llm": aggregate([grade()])}}
        md = runner.to_markdown(report)
        for phrase in ("Tầng 1", "Tầng 2", "Vận hành", "Diễn giải", "CẢNH BÁO", "chưa cấu hình giá"):
            self.assertIn(phrase, md)
