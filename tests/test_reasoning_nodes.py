import unittest

from src.graph_state import new_state
from src.nodes.reasoning import (
    diagnose,
    filter_hard,
    plan,
    replan,
    score_rank,
    verify_output,
)


REQ = {
    "session_id": "sess_nodes",
    "intent": "search_new",
    "hard_constraints": {
        "product_type": "ghế văn phòng",
        "quantity": 20,
        "budget_max": 40_000_000,
        "delivery_deadline_days": 10,
    },
    "soft_constraints": {
        "material_preference": "lưới",
        "region_preference": "Hà Nội",
        "min_trust_score": 4.0,
    },
}


def supplier(**overrides):
    record = {
        "MaNCC": "NCC001",
        "TenNCC": "Nhà cung cấp thử nghiệm",
        "LoaiSanPham": "ghế văn phòng",
        "ChatLieu": "lưới",
        "KhuVuc": "Hà Nội",
        "Gia": 1_600_000,
        "MOQ": 5,
        "TonKho": 100,
        "ThoiGianGiao": 6,
        "BaoHanh": 24,
        "DiemUyTin": 4.5,
        "unit_price": 1_600_000,
        "total_price": 32_000_000,
        "nguon_url": "https://example.test/ncc001",
        "nguon_type": "public_listing",
        "simulated_fields": ["Gia", "MOQ", "TonKho"],
    }
    record.update(overrides)
    return record


def state_with(**updates):
    state = new_state("Cần mua ghế", session_id="sess_nodes")
    state.update({"intent": "search_new", "req": REQ})
    state.update(updates)
    return state


class ReasoningNodeTests(unittest.TestCase):
    def test_plan_calls_real_planner_and_keeps_soft_preferences_out_of_params(self):
        patch = plan(state_with())

        self.assertTrue(patch["plan"]["plan_id"].startswith("plan_"))
        self.assertEqual(
            patch["plan"]["steps"][0]["params"],
            {"product_type": "ghế văn phòng"},
        )

    def test_search_nodes_filter_rank_and_verify_real_evidence(self):
        candidate = supplier()
        filtered = filter_hard(state_with(candidates=[candidate]))
        self.assertEqual(len(filtered["candidates"]), 1)

        ranked = score_rank(state_with(candidates=filtered["candidates"]))["ranked"]
        self.assertIn("leverage_score", ranked[0])
        self.assertIn("negotiation_strategy", ranked[0])

        tool_results = [
            {"tool": "get_supplier_detail", "status": "ok", "result": candidate},
            {"tool": "compare_price", "status": "ok", "result": {
                "comparisons": [{
                    "MaNCC": "NCC001",
                    "unit_price": 1_600_000,
                    "total_price": 32_000_000,
                    "nguon_url": "https://example.test/ncc001",
                    "nguon_type": "public_listing",
                }],
            }},
        ]
        verdict = verify_output(state_with(ranked=ranked, tool_results=tool_results))["verdict"]

        self.assertTrue(verdict["passed"])
        self.assertTrue(verdict["claims"])

    def test_filter_rejects_hard_constraint_violation(self):
        patch = filter_hard(state_with(candidates=[supplier(ThoiGianGiao=15)]))

        self.assertEqual(patch["candidates"], [])
        self.assertEqual(
            patch["rejected"][0]["violations"][0]["code"],
            "delivery_deadline_unmet",
        )

    def test_diagnose_and_replan_preserve_audit_chain(self):
        initial = plan(state_with())["plan"]
        rejected = [{
            "supplier_id": "NCC001",
            "violations": [{"code": "delivery_deadline_unmet"}],
        }]
        state = state_with(plan=initial, rejected=rejected)

        reason = diagnose(state)["replan_reason"]
        patch = replan(state)

        self.assertIn("delivery_deadline_unmet", reason)
        self.assertNotEqual(patch["plan"]["plan_id"], initial["plan_id"])
        self.assertEqual(patch["replan_count"], 1)

    def test_supplier_detail_bypasses_procurement_constraints(self):
        detail_req = {
            "session_id": "sess_nodes",
            "intent": "supplier_detail",
            "hard_constraints": {
                "product_type": None, "quantity": None,
                "budget_max": None, "delivery_deadline_days": None,
            },
        }
        detail = supplier()
        detail.pop("unit_price")
        detail.pop("total_price")
        state = state_with(intent="supplier_detail", req=detail_req, candidates=[detail])

        filtered = filter_hard(state)
        ranked = score_rank({**state, **filtered})["ranked"]
        verdict = verify_output({
            **state,
            "ranked": ranked,
            "tool_results": [{"tool": "get_supplier_detail", "status": "ok", "result": detail}],
        })["verdict"]

        self.assertEqual(filtered["candidates"], [detail])
        self.assertTrue(verdict["passed"])

    def test_compare_specific_with_only_quantity_ranks_by_total_price(self):
        compare_req = {
            "session_id": "sess_nodes",
            "intent": "compare_specific",
            "hard_constraints": {
                "product_type": None, "quantity": 20,
                "budget_max": None, "delivery_deadline_days": None,
            },
        }
        expensive = supplier(MaNCC="NCC002", total_price=35_000_000, unit_price=1_750_000)
        cheap = supplier()
        state = state_with(intent="compare_specific", req=compare_req,
                           candidates=[expensive, cheap])

        filtered = filter_hard(state)
        ranked = score_rank({**state, **filtered})["ranked"]

        self.assertEqual([item["MaNCC"] for item in ranked], ["NCC001", "NCC002"])


if __name__ == "__main__":
    unittest.main()
