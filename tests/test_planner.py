import unittest

from src.reasoning.planner import (
    MAX_REPLAN_COUNT,
    PlanningError,
    ReplanLimitReached,
    make_plan,
    make_replan,
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
            {
                "product_type": "ghế văn phòng",
                "material": "gỗ tự nhiên",
                "region": "Hà Nội",
            },
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


if __name__ == "__main__":
    unittest.main()
