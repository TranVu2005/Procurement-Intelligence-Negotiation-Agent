import unittest

from src.reasoning.planner import make_plan, propose_replan
from src.reasoning.scoring import evaluate_candidates
from src.tools.supplier_tools import compare_price, get_supplier_detail, search_suppliers


class ReasoningToolIntegrationTests(unittest.TestCase):
    def test_real_mock_data_runs_from_plan_to_recommendation(self) -> None:
        state = {
            "session_id": "integration_001",
            "hard_constraints": {
                "product_type": "ghế văn phòng",
                "quantity": 20,
                "budget_max": 40_000_000,
                "delivery_deadline_days": 10,
            },
            "soft_constraints": {
                "material_preference": "vai_boc",
                "region_preference": "Ha Noi",
                "min_trust_score": 4.0,
            },
        }
        plan = make_plan(state)
        search_result = search_suppliers(**plan["steps"][0]["params"])
        supplier_ids = [item["MaNCC"] for item in search_result["suppliers"]]
        details = [get_supplier_detail(supplier_id) for supplier_id in supplier_ids]
        prices = compare_price(supplier_ids, state["hard_constraints"]["quantity"])

        decision = evaluate_candidates(state, details, prices)

        self.assertEqual(decision["status"], "success")
        self.assertIsNotNone(decision["recommended_supplier_id"])
        self.assertGreater(len(decision["ranked_suppliers"]), 0)
        for item in decision["ranked_suppliers"]:
            self.assertLessEqual(item["total_price"], 40_000_000)
            self.assertLessEqual(item["ThoiGianGiao"], 10)

    def test_edge_supplier_produces_replan_reasons(self) -> None:
        state = {
            "session_id": "integration_edge",
            "hard_constraints": {
                "product_type": "ghế văn phòng",
                "quantity": 20,
                "budget_max": 40_000_000,
                "delivery_deadline_days": 10,
            },
            "soft_constraints": {},
        }
        plan = make_plan(state)
        detail = get_supplier_detail("EDGE001")
        prices = compare_price(["EDGE001"], 20)

        decision = evaluate_candidates(state, [detail], prices)
        proposal = propose_replan(plan, decision["rejected_suppliers"])
        codes = {cause["code"] for cause in proposal["causes"]}

        self.assertEqual(decision["status"], "no_eligible_supplier")
        self.assertIn("quantity_below_moq", codes)
        self.assertIn("budget_exceeded", codes)
        self.assertIn("delivery_deadline_unmet", codes)
        self.assertTrue(proposal["requires_user_confirmation"])

    def test_conflicting_mock_records_are_not_recommended(self) -> None:
        state = {
            "session_id": "integration_conflict",
            "hard_constraints": {
                "product_type": "sofa",
                "quantity": 2,
                "budget_max": 50_000_000,
                "delivery_deadline_days": 20,
            },
            "soft_constraints": {},
        }
        supplier_ids = ["EDGE004A", "EDGE004B"]
        details = [get_supplier_detail(supplier_id) for supplier_id in supplier_ids]
        prices = compare_price(supplier_ids, 2)

        decision = evaluate_candidates(state, details, prices)

        self.assertEqual(decision["status"], "evidence_conflict")
        self.assertIsNone(decision["recommended_supplier_id"])
        self.assertEqual(len(decision["evidence_conflicts"]), 1)


if __name__ == "__main__":
    unittest.main()
