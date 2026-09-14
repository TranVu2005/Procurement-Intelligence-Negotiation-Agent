import unittest

from src.eval.scoring import METRIC_NAMES, aggregate, grade_case


def final_with(**kwargs):
    base = {
        "intent": "search_new",
        "status": "success",
        "tool_results": [
            {"tool": "search_suppliers", "status": "ok", "result": {"suppliers": []}},
            {"tool": "compare_price", "status": "ok", "result": {"comparisons": []}},
        ],
        "ranked": [{"MaNCC": "T001", "total_price": 19_000_000, "ThoiGianGiao": 7, "MOQ": 10}],
        "verdict": {"passed": True, "violations": [], "claims": []},
        "replan_count": 0,
        "answer": "ok",
    }
    return {**base, **kwargs}


HAPPY_CASE = {
    "id": "X01", "category": "happy_path", "turns": ["x"], "inject": None,
    "oracle": {
        "must_reach_intent": "search_new",
        "must_call_tools": ["search_suppliers", "compare_price"],
        "must_not_call_tools": ["confirm_order"],
        "constraints": {"total_price_lte": 200_000_000, "delivery_lte": 14, "quantity_gte_moq": True},
        "must_cite": False,
        "expect_status": "success",
    },
}


class GradeCaseTests(unittest.TestCase):
    def test_a_fully_matching_run_passes(self) -> None:
        result = grade_case(HAPPY_CASE, final_with())
        self.assertTrue(result["passed"], result["failures"])

    def test_wrong_status_fails_with_a_named_reason(self) -> None:
        result = grade_case(HAPPY_CASE, final_with(status="graceful_fail"))
        self.assertFalse(result["passed"])
        self.assertTrue(any("expect_status" in f for f in result["failures"]))

    def test_a_forbidden_tool_call_fails_the_case(self) -> None:
        final = final_with()
        final["tool_results"] = final["tool_results"] + [{"tool": "confirm_order", "status": "ok"}]
        result = grade_case(HAPPY_CASE, final)
        self.assertFalse(result["passed"])
        self.assertTrue(any("confirm_order" in f for f in result["failures"]))

    def test_a_blocked_confirm_order_is_not_a_forbidden_call(self) -> None:
        final = final_with()
        final["tool_results"] = final["tool_results"] + [
            {"tool": "confirm_order", "status": "blocked"}
        ]
        self.assertTrue(grade_case(HAPPY_CASE, final)["passed"])

    def test_budget_violation_fails_constraint_satisfaction(self) -> None:
        final = final_with(ranked=[{"MaNCC": "T001", "total_price": 999_000_000,
                                    "ThoiGianGiao": 7, "MOQ": 10}])
        result = grade_case(HAPPY_CASE, final)
        self.assertFalse(result["signals"]["constraints_ok"])

    def test_must_cite_requires_traceable_claims(self) -> None:
        case = {**HAPPY_CASE, "oracle": {**HAPPY_CASE["oracle"], "must_cite": True}}
        result = grade_case(case, final_with())
        self.assertFalse(result["passed"])
        self.assertTrue(any("cite" in f for f in result["failures"]))


class CitationTests(unittest.TestCase):
    def test_a_claim_backed_by_a_tool_result_counts_as_correct(self) -> None:
        final = final_with(verdict={
            "passed": True, "violations": [],
            "claims": [{"claim": "tong tien", "value": 19_000_000,
                        "evidence": {"MaNCC": "T001", "field": "total_price",
                                     "nguon_url": "https://vi.du"}}],
        })
        final["tool_results"] = [{
            "tool": "compare_price", "status": "ok",
            "result": {"comparisons": [{"MaNCC": "T001", "total_price": 19_000_000,
                                        "nguon_url": "https://vi.du"}]},
        }]
        result = grade_case({**HAPPY_CASE,
                             "oracle": {**HAPPY_CASE["oracle"], "must_call_tools": ["compare_price"],
                                        "must_cite": True}}, final)
        self.assertEqual(result["signals"]["claims_total"], 1)
        self.assertEqual(result["signals"]["claims_grounded"], 1)

    def test_a_claim_with_no_matching_tool_result_is_not_grounded(self) -> None:
        final = final_with(verdict={
            "passed": True, "violations": [],
            "claims": [{"claim": "doanh thu", "value": 42,
                        "evidence": {"MaNCC": "T999", "field": "doanh_thu", "nguon_url": ""}}],
        })
        result = grade_case(HAPPY_CASE, final)
        self.assertEqual(result["signals"]["claims_grounded"], 0)


class AggregateTests(unittest.TestCase):
    def test_reports_all_five_required_metrics(self) -> None:
        report = aggregate([grade_case(HAPPY_CASE, final_with())])
        for name in METRIC_NAMES:
            self.assertIn(name, report["metrics"])
        self.assertEqual(len(METRIC_NAMES), 5)

    def test_task_success_rate_is_the_share_of_passing_cases(self) -> None:
        results = [grade_case(HAPPY_CASE, final_with()),
                   grade_case(HAPPY_CASE, final_with(status="graceful_fail"))]
        self.assertEqual(aggregate(results)["metrics"]["task_success_rate"], 0.5)

    def test_tool_call_success_rate_ignores_blocked_calls(self) -> None:
        final = final_with()
        final["tool_results"] = [
            {"tool": "search_suppliers", "status": "ok"},
            {"tool": "compare_price", "status": "error"},
            {"tool": "confirm_order", "status": "blocked"},
        ]
        report = aggregate([grade_case(HAPPY_CASE, final)])
        self.assertEqual(report["metrics"]["tool_call_success_rate"], 0.5)

    def test_a_metric_with_no_applicable_case_is_none_not_zero(self) -> None:
        # Khong co case nao co inject -> Failure Recovery Rate khong do duoc
        report = aggregate([grade_case(HAPPY_CASE, final_with())])
        self.assertIsNone(report["metrics"]["failure_recovery_rate"])


if __name__ == "__main__":
    unittest.main()
