import unittest

from src.reasoning.planner import (
    MAX_REPLAN_COUNT,
    PlanningError,
    ReplanLimitReached,
    make_plan,
    make_replan,
    propose_replan,
    propose_tool_replan,
)


def valid_state() -> dict:
    return {
        "session_id": "sess_001",
        "hard_constraints": {
            "product_type": "ghế văn phòng",
            "quantity": 50,
            "budget_max": 200_000_000,
            "delivery_deadline_days": 14,
        },
        "soft_constraints": {
            "material_preference": "gỗ tự nhiên",
            "region_preference": "Hà Nội",
            "min_trust_score": 4.0,
        },
    }


class PlannerTests(unittest.TestCase):
    def test_make_plan_matches_plan_and_tool_contracts(self) -> None:
        plan = make_plan(valid_state())

        self.assertEqual(plan["session_id"], "sess_001")
        self.assertEqual(plan["status"], "draft")
        self.assertEqual(plan["replan_count"], 0)
        self.assertIsNone(plan["replan_reason"])
        self.assertTrue(plan["plan_id"].startswith("plan_"))
        self.assertEqual(
            plan["steps"][0]["params"],
            {"product_type": "ghế văn phòng"},
        )
        self.assertEqual(plan["steps"][0]["action"], "search_suppliers")

    def test_missing_required_constraint_is_not_silently_inferred(self) -> None:
        state = valid_state()
        del state["hard_constraints"]["budget_max"]

        with self.assertRaisesRegex(PlanningError, "budget_max"):
            make_plan(state)

    def test_invalid_quantity_is_rejected(self) -> None:
        state = valid_state()
        state["hard_constraints"]["quantity"] = 0

        with self.assertRaisesRegex(PlanningError, "quantity"):
            make_plan(state)

    def test_replan_has_new_id_reason_and_does_not_mutate_previous_plan(self) -> None:
        old_plan = make_plan(valid_state())
        old_snapshot = dict(old_plan)

        new_plan = make_replan(valid_state(), old_plan, "search tool returned no_match")

        self.assertNotEqual(new_plan["plan_id"], old_plan["plan_id"])
        self.assertEqual(new_plan["replan_count"], 1)
        self.assertEqual(new_plan["replan_reason"], "search tool returned no_match")
        self.assertEqual(old_plan, old_snapshot)

    def test_replan_stops_after_agreed_limit(self) -> None:
        plan = make_plan(
            valid_state(),
            replan_count=MAX_REPLAN_COUNT,
            replan_reason="previous recovery attempts failed",
        )

        with self.assertRaises(ReplanLimitReached):
            make_replan(valid_state(), plan, "try again")

    def test_replan_proposal_diagnoses_inventory_moq_and_delivery(self) -> None:
        plan = make_plan(valid_state())
        rejected = [{
            "supplier_id": "NCC001",
            "violations": [
                {"code": "stock_below_quantity"},
                {"code": "quantity_below_moq"},
                {"code": "delivery_deadline_unmet"},
            ],
        }]

        proposal = propose_replan(plan, rejected)

        self.assertEqual(proposal["status"], "needs_replan")
        self.assertTrue(proposal["requires_user_confirmation"])
        self.assertEqual(proposal["next_replan_count"], 1)
        self.assertGreaterEqual(len(proposal["alternatives"]), 3)

    def test_replan_proposal_gracefully_fails_at_limit(self) -> None:
        plan = make_plan(
            valid_state(),
            replan_count=MAX_REPLAN_COUNT,
            replan_reason="all prior alternatives failed",
        )

        proposal = propose_replan(plan, [])

        self.assertEqual(proposal["status"], "graceful_failure")
        self.assertFalse(proposal["requires_user_confirmation"])

    def test_tool_error_becomes_auditable_replan_proposal(self) -> None:
        plan = make_plan(valid_state())

        proposal = propose_tool_replan(plan, {
            "error": True,
            "error_type": "timeout",
            "message": "search timed out",
        })

        self.assertEqual(proposal["status"], "needs_replan")
        self.assertEqual(proposal["tool_error"]["error_type"], "timeout")
        self.assertTrue(any("Retry" in option for option in proposal["alternatives"]))

    def test_compare_specific_plan_calls_compare_price(self) -> None:
        state = {
            "session_id": "sess_compare",
            "hard_constraints": {"quantity": 12},
        }

        plan = make_plan(
            state,
            intent="compare_specific",
            supplier_ids=["NCC001", "NCC006"],
        )

        self.assertEqual(plan["intent"], "compare_specific")
        self.assertEqual(plan["steps"][0]["action"], "compare_price")
        self.assertEqual(plan["steps"][0]["params"]["quantity"], 12)

    def test_supplier_detail_plan_does_not_require_procurement_constraints(self) -> None:
        plan = make_plan(
            {"session_id": "sess_detail"},
            intent="supplier_detail",
            supplier_id="NCC001",
        )

        self.assertEqual(plan["steps"][0]["action"], "get_supplier_detail")
        self.assertEqual(plan["steps"][0]["params"], {"supplier_id": "NCC001"})

    def test_out_of_scope_plan_has_no_tool_call(self) -> None:
        plan = make_plan({"session_id": "sess_oos"}, intent="out_of_scope")

        self.assertEqual(plan["intent"], "out_of_scope")
        self.assertEqual(plan["steps"], [])
        self.assertEqual(plan["workflow"][0]["name"], "respond_limits")

    def test_compare_specific_requires_supplier_ids(self) -> None:
        with self.assertRaisesRegex(PlanningError, "supplier_ids"):
            make_plan(
                {"session_id": "sess_compare", "hard_constraints": {"quantity": 10}},
                intent="compare_specific",
            )


if __name__ == "__main__":
    unittest.main()
