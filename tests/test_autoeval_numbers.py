import sys
import unittest
from pathlib import Path

from src.eval.scoring import METRIC_NAMES, grade_case, invented_numbers, round_spread

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_autoeval  # noqa: E402

TOOL_RESULTS = [{"tool": "compare_price", "status": "ok", "result": {"comparisons": [
    {"MaNCC": "NCC001", "unit_price": 1_626_836, "total_price": 81_341_800,
     "discount_applied": "3%"}]}}]


def final_with(answer, **kwargs):
    return {"answer": answer, "tool_results": TOOL_RESULTS,
            "req": {"hard_constraints": {"quantity": 50, "budget_max": 200_000_000}},
            "status": "success", "intent": "search_new", **kwargs}


class InventedNumberTests(unittest.TestCase):
    def test_numbers_copied_from_tool_results_are_grounded(self) -> None:
        answer = "NCC001 bao gia 1.626.836 VND/cai, tong 81,341,800 VND, giam 3%."
        self.assertEqual(invented_numbers(final_with(answer)), [])

    def test_rounded_million_display_is_accepted_within_one_percent(self) -> None:
        self.assertEqual(invented_numbers(final_with("Tong khoang 81,3 triệu, ngan sach 200 triệu.")), [])

    def test_a_number_that_appears_nowhere_is_reported(self) -> None:
        self.assertEqual(invented_numbers(final_with("Doanh thu nam ngoai la 5 tỷ.")), ["5 tỷ"])

    def test_small_numbers_and_supplier_codes_are_ignored(self) -> None:
        self.assertEqual(invented_numbers(final_with("NCC001 giao trong 7 ngay, top 3.")), [])

    def test_grade_case_fails_on_invented_numbers_only_when_asked(self) -> None:
        case = {"id": "X", "category": "adversarial", "turns": ["x"],
                "oracle": {"expect_status": "success", "must_not_invent_numbers": True}}
        final = final_with("Doanh thu 987.654.321 VND")
        result = grade_case(case, final)
        self.assertFalse(result["passed"])
        self.assertTrue(any("must_not_invent_numbers" in f for f in result["failures"]))
        lenient = {**case, "oracle": {"expect_status": "success"}}
        self.assertTrue(grade_case(lenient, final)["passed"])


class MustAskUserTests(unittest.TestCase):
    CASE = {"id": "X", "category": "missing_info", "turns": ["x"],
            "oracle": {"expect_status": "needs_input", "must_ask_user": True}}

    def test_needs_input_satisfies_must_ask_user(self) -> None:
        self.assertTrue(grade_case(self.CASE, final_with("Ban can mua bao nhieu?",
                                                         status="needs_input"))["passed"])

    def test_any_other_status_fails_must_ask_user(self) -> None:
        result = grade_case(self.CASE, final_with("x", status="graceful_fail"))
        self.assertTrue(any("must_ask_user" in f for f in result["failures"]))


class SpreadTests(unittest.TestCase):
    def test_min_max_stdev_per_metric_across_rounds(self) -> None:
        rounds = [{"metrics": {name: None for name in METRIC_NAMES}} for _ in range(2)]
        rounds[0]["metrics"]["task_success_rate"] = 0.8
        rounds[1]["metrics"]["task_success_rate"] = 0.9
        spread = round_spread(rounds)
        self.assertEqual(spread["task_success_rate"], {"min": 0.8, "max": 0.9, "stdev": 0.05})
        self.assertIsNone(spread["failure_recovery_rate"])

    def test_markdown_shows_spread_when_repeated(self) -> None:
        report = {
            "generated_at": "t", "dataset_version": "v", "total_cases": 2, "repeat": 2,
            "llm_mode": "stub", "metrics": {name: 0.5 for name in METRIC_NAMES},
            "avg_llm_calls": 2.0, "latency_p50_ms": 1.0, "latency_p95_ms": 2.0,
            "failed_cases": [],
            "spread": {name: {"min": 0.4, "max": 0.6, "stdev": 0.1} for name in METRIC_NAMES},
        }
        text = run_autoeval.to_markdown(report)
        self.assertIn("## Do dao dong qua cac lan chay", text)
        self.assertIn("| task_success_rate | 0.4 | 0.6 | 0.1 |", text)


if __name__ == "__main__":
    unittest.main()
