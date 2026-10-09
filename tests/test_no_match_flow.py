import unittest

from src.graph import run_request
from src.graph_state import new_state
from src.nodes.reasoning import diagnose, graceful_fail


REQ = {
    "session_id": "sess_no_match",
    "intent": "search_new",
    "hard_constraints": {
        "product_type": "sofa",
        "quantity": 100,
        "budget_max": 5_000_000,
        "delivery_deadline_days": 2,
    },
    "soft_constraints": {"priority": "price"},
}


class NoMatchFlowTests(unittest.TestCase):
    def test_end_to_end_impossible_constraints_return_explained_non_null_result(self):
        def perceive_without_llm(_state):
            return {
                "session_id": REQ["session_id"],
                "intent": "search_new",
                "req": REQ,
                "llm_calls": 0,
                "tokens_in": 0,
                "tokens_out": 0,
            }

        final = run_request(
            "Cần 100 sofa, ngân sách 5 triệu, giao 2 ngày",
            session_id=REQ["session_id"],
            overrides={"perceive": perceive_without_llm},
        )

        self.assertEqual(final["intent"], "search_new")
        self.assertEqual(final["status"], "graceful_fail")
        self.assertIsInstance(final["ranked"], list)
        self.assertIsInstance(final["verdict"], dict)
        self.assertTrue(final["answer"].strip())
        self.assertTrue(final["relax_suggestions"])

    def test_diagnose_returns_structured_relax_suggestions(self):
        state = new_state("Cần 100 sofa", session_id="sess_no_match", req=REQ)
        state.update({
            "intent": "search_new",
            "rejected": [{
                "supplier_id": "SRC_SOFA",
                "violations": [
                    {
                        "code": "budget_exceeded", "field": "total_price",
                        "actual": 15_000_000, "required": "<= 5000000",
                    },
                    {
                        "code": "delivery_deadline_unmet", "field": "ThoiGianGiao",
                        "actual": 7, "required": "<= 2",
                    },
                ],
                "evidence": {
                    "MaNCC": "SRC_SOFA", "total_price": 15_000_000,
                    "ThoiGianGiao": 7, "nguon_url": "https://example.test/sofa",
                },
            }],
        })

        patch = diagnose(state)

        self.assertIn("budget_exceeded", patch["replan_reason"])
        self.assertTrue(patch["relax_suggestions"])
        self.assertTrue(all(item["supplier_ids"] for item in patch["relax_suggestions"]))

    def test_graceful_fail_has_non_empty_answer_and_preserves_structured_suggestions(self):
        state = new_state("Cần 100 sofa", session_id="sess_no_match", req=REQ)
        state.update({
            "intent": "search_new",
            "replan_count": 3,
            "rejected": [{
                "supplier_id": "SRC_SOFA",
                "violations": [{
                    "code": "budget_exceeded", "field": "total_price",
                    "actual": 15_000_000, "required": "<= 5000000",
                }],
                "evidence": {
                    "MaNCC": "SRC_SOFA", "total_price": 15_000_000,
                    "nguon_url": "https://example.test/sofa",
                },
            }],
            "ranked": [],
            "verdict": {},
        })

        patch = graceful_fail(state)

        self.assertEqual(patch["status"], "graceful_fail")
        self.assertTrue(patch["answer"].strip())
        self.assertIn("SRC_SOFA", patch["answer"])
        self.assertEqual(patch["relax_suggestions"][0]["suggested"], 15_000_000)

    def test_empty_tool_result_ends_with_explicit_generic_explanation(self):
        state = new_state("Cần sản phẩm không có", session_id="sess_no_match", req=REQ)
        state.update({
            "intent": "search_new",
            "replan_count": 3,
            "tool_results": [{
                "tool": "search_suppliers", "status": "error", "error_type": "no_match",
                "result": {"error": True, "error_type": "no_match", "message": "Không có kết quả"},
            }],
        })

        patch = graceful_fail(state)

        self.assertEqual(patch["status"], "graceful_fail")
        self.assertIn("không có", patch["answer"].lower())
        self.assertEqual(patch["relax_suggestions"], [])


if __name__ == "__main__":
    unittest.main()
