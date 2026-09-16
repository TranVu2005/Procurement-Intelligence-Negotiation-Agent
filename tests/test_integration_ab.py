# -*- coding: utf-8 -*-
"""Integration test A→B pipeline — offline, không cần LLM.

Chứng minh rằng output của Người A (parse_request / update_state) tương thích
trực tiếp với input của Người B (make_plan / make_replan / validate_state).

Chạy:
    python -m unittest discover -s tests -p "test_integration_ab.py" -v
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.reasoning.planner import (
    PlanningError,
    ReplanLimitReached,
    make_plan,
    make_replan,
    validate_state,
    MAX_REPLAN_COUNT,
)


# ---------------------------------------------------------------------------
# Helper: tạo state mock theo đúng schema của A — không cần LLM
# ---------------------------------------------------------------------------

def _state(
    session_id="sess_ab_test",
    product_type="ghế văn phòng",
    quantity=50,
    budget_max=200_000_000,
    deadline=14,
    material=None,
    region=None,
    min_trust=None,
):
    now = "2026-09-12T10:00:00"
    return {
        "session_id": session_id,
        "created_at": now,
        "updated_at": now,
        "hard_constraints": {
            "product_type":           product_type,
            "quantity":               quantity,
            "budget_max":             float(budget_max),
            "delivery_deadline_days": deadline,
        },
        "soft_constraints": {
            "material_preference": material,
            "region_preference":   region,
            "min_trust_score":     min_trust,
        },
        "conversation_history": [
            {"role": "user", "content": "test input", "timestamp": now}
        ],
        "decisions_made": [],
    }


# ---------------------------------------------------------------------------
# Test class 1: A's state → B's make_plan()
# ---------------------------------------------------------------------------

class TestAStateFeedsIntoMakePlan(unittest.TestCase):
    """Kiểm tra rằng state đúng schema của A có thể feed trực tiếp vào B's make_plan()."""

    def test_happy_path_full_state(self):
        """State đầy đủ (kịch bản mẫu buổi họp 3) → plan hợp lệ."""
        state = _state(
            product_type="ghế văn phòng",
            quantity=50,
            budget_max=200_000_000,
            deadline=14,
            material="gỗ tự nhiên",
            region="Hà Nội",
            min_trust=4.0,
        )
        plan = make_plan(state)

        self.assertEqual(plan["session_id"], "sess_ab_test")
        self.assertEqual(plan["status"], "draft")
        self.assertEqual(plan["replan_count"], 0)
        self.assertIsNone(plan["replan_reason"])
        self.assertTrue(plan["plan_id"].startswith("plan_"))

        # Step đầu tiên phải là search_suppliers
        step = plan["steps"][0]
        self.assertEqual(step["action"], "search_suppliers")
        self.assertEqual(step["params"]["product_type"], "ghế văn phòng")

        # Decision §8.1: material/region are omitted entirely from the tool params
        # to avoid incorrectly turning soft constraints into hard filters.
        # Soft constraints (material, region, min_trust) are applied downstream
        # by evaluate_candidates() after raw results are fetched.
        self.assertEqual(step["params"], {"product_type": "ghế văn phòng"})

    def test_state_without_soft_constraints_still_makes_plan(self):
        """State không có soft constraints vẫn tạo được plan."""
        state = _state(material=None, region=None, min_trust=None)
        plan = make_plan(state)

        step = plan["steps"][0]
        self.assertEqual(step["params"], {"product_type": "ghế văn phòng"})

    def test_all_furniture_product_types_are_plannable(self):
        """Mọi product_type trong catalog của A đều tạo được plan."""
        for pt in ("ghế văn phòng", "bàn làm việc", "tủ hồ sơ", "kệ", "sofa"):
            with self.subTest(product_type=pt):
                state = _state(product_type=pt)
                plan = make_plan(state)
                self.assertEqual(plan["steps"][0]["params"]["product_type"], pt)

    def test_missing_session_id_from_a_causes_planning_error(self):
        """Nếu A quên gắn session_id → B phải raise PlanningError, không crash ngầm."""
        state = _state()
        del state["session_id"]
        with self.assertRaises(PlanningError):
            make_plan(state)

    def test_missing_hard_constraint_causes_planning_error(self):
        """Nếu A thiếu quantity (lỗi validation) → B nhận ra ngay và raise PlanningError."""
        state = _state()
        del state["hard_constraints"]["quantity"]
        with self.assertRaises(PlanningError):
            make_plan(state)

    def test_invalid_quantity_from_a_causes_planning_error(self):
        """quantity = 0 từ A (vi phạm contract) → B phải reject."""
        state = _state(quantity=0)
        with self.assertRaises(PlanningError):
            make_plan(state)

    def test_validate_state_passes_on_valid_a_output(self):
        """validate_state() của B phải pass khi nhận đúng output của A."""
        state = _state()
        # Không raise = pass
        validate_state(state)


# ---------------------------------------------------------------------------
# Test class 2: Multi-turn update → re-plan
# ---------------------------------------------------------------------------

class TestMultiTurnUpdateTriggersReplan(unittest.TestCase):
    """Kiểm tra rằng sau khi A update state, B có thể tạo plan mới (re-plan)."""

    def _simulate_update(self, state, new_quantity=None, new_budget=None):
        """Mô phỏng update_state() từ A — không cần LLM."""
        import copy
        updated = copy.deepcopy(state)
        updated["updated_at"] = "2026-09-12T11:00:00"
        if new_quantity is not None:
            updated["hard_constraints"]["quantity"] = new_quantity
        if new_budget is not None:
            updated["hard_constraints"]["budget_max"] = float(new_budget)
        updated["conversation_history"].append(
            {"role": "user", "content": "đổi yêu cầu", "timestamp": "2026-09-12T11:00:00"}
        )
        return updated

    def test_update_then_new_plan_uses_latest_state(self):
        """Sau khi A update quantity, plan mới phải reflect số lượng mới."""
        state_v1 = _state(quantity=50)
        plan_v1 = make_plan(state_v1)

        state_v2 = self._simulate_update(state_v1, new_quantity=80)
        plan_v2 = make_plan(state_v2)

        # Cả 2 plan đều valid nhưng khác nhau
        self.assertNotEqual(plan_v1["plan_id"], plan_v2["plan_id"])
        self.assertEqual(plan_v1["replan_count"], 0)
        self.assertEqual(plan_v2["replan_count"], 0)

    def test_tool_error_triggers_replan_with_reason(self):
        """Khi tool lỗi, B gọi make_replan() với reason → plan mới có audit trail."""
        state = _state()
        plan_v1 = make_plan(state)

        plan_v2 = make_replan(state, plan_v1, "search_suppliers returned no_match")

        self.assertNotEqual(plan_v2["plan_id"], plan_v1["plan_id"])
        self.assertEqual(plan_v2["replan_count"], 1)
        self.assertEqual(plan_v2["replan_reason"], "search_suppliers returned no_match")
        # plan_v1 không bị mutate
        self.assertEqual(plan_v1["replan_count"], 0)
        self.assertIsNone(plan_v1["replan_reason"])

    def test_replan_chain_stops_at_max(self):
        """Chuỗi re-plan phải dừng sau MAX_REPLAN_COUNT lần."""
        state = _state()
        plan = make_plan(state)

        for i in range(MAX_REPLAN_COUNT):
            plan = make_replan(state, plan, f"retry {i+1}")

        self.assertEqual(plan["replan_count"], MAX_REPLAN_COUNT)

        with self.assertRaises(ReplanLimitReached):
            make_replan(state, plan, "one more try")

    def test_replan_without_reason_is_rejected(self):
        """B phải reject re-plan nếu không có lý do rõ ràng."""
        state = _state()
        plan = make_plan(state)

        with self.assertRaises(PlanningError):
            make_replan(state, plan, "")

    def test_plan_contains_workflow_stages(self):
        """Plan phải chứa đủ workflow stages theo REASONING-PLANNING.md."""
        state = _state()
        plan = make_plan(state)

        stage_names = [s["name"] for s in plan["workflow"]]
        for expected in ("validate_state", "search_suppliers", "filter_hard_constraints",
                         "compare_price", "rank_candidates", "generate_recommendation"):
            self.assertIn(expected, stage_names, f"Thiếu stage: {expected}")

    def test_session_id_propagates_from_a_through_b_plan(self):
        """session_id của A phải đi qua không đổi vào plan của B."""
        state = _state(session_id="sess_propagation_test")
        plan = make_plan(state)
        self.assertEqual(plan["session_id"], "sess_propagation_test")


if __name__ == "__main__":
    unittest.main()
