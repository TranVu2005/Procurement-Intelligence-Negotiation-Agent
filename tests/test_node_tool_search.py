import unittest
from unittest.mock import patch

from src.graph_state import new_state
from src.nodes.tools import tool_search

FAKE_DATA = [
    {
        "MaNCC": "T001", "TenNCC": "NCC Dat Chuan", "LoaiSanPham": "ghế văn phòng",
        "ChatLieu": "vai_boc", "Gia": 1_000_000, "DonViTinh": "cái", "MOQ": 10,
        "TonKho": 100, "ThoiGianGiao": 7, "BaoHanh": 12,
        "ChietKhauTheoSoLuong": [{"tu_so_luong": 10, "phan_tram_giam": 5}],
        "DiemUyTin": 4.5, "KhuVuc": "Ha Noi",
    },
    {
        "MaNCC": "T002", "TenNCC": "NCC Giao Cham", "LoaiSanPham": "ghế văn phòng",
        "ChatLieu": "luoi_nhua", "Gia": 800_000, "DonViTinh": "cái", "MOQ": 5,
        "TonKho": 200, "ThoiGianGiao": 30, "BaoHanh": 6,
        "ChietKhauTheoSoLuong": [], "DiemUyTin": 3.5, "KhuVuc": "TP.HCM",
    },
]

PLAN = {
    "plan_id": "plan_x",
    "steps": [
        {"step_id": 1, "action": "search_suppliers",
         "params": {"product_type": "ghế văn phòng"}, "reason": "r", "depends_on": []},
    ],
}

REQ = {
    "session_id": "sess_1",
    "hard_constraints": {
        "product_type": "ghế văn phòng", "quantity": 20,
        "budget_max": 200_000_000, "delivery_deadline_days": 14,
    },
    "soft_constraints": {},
}


def base_state(**kwargs):
    return {**new_state("x"), "req": REQ, "plan": PLAN, **kwargs}


def patch_data():
    return patch("src.tools.supplier_tools._load_data", return_value=FAKE_DATA)


class ToolSearchTests(unittest.TestCase):
    def test_runs_search_then_detail_per_hit_then_compare(self) -> None:
        with patch_data():
            out = tool_search(base_state())
        tools_called = [e["tool"] for e in out["tool_results"]]
        self.assertEqual(
            tools_called,
            ["search_suppliers", "get_supplier_detail", "get_supplier_detail", "compare_price"],
        )

    def test_candidates_carry_full_record_merged_with_price(self) -> None:
        with patch_data():
            out = tool_search(base_state())
        by_id = {c["MaNCC"]: c for c in out["candidates"]}
        self.assertEqual(set(by_id), {"T001", "T002"})
        # field cua get_supplier_detail ma search_suppliers khong tra
        self.assertEqual(by_id["T001"]["TonKho"], 100)
        self.assertEqual(by_id["T001"]["LoaiSanPham"], "ghế văn phòng")
        # field cua compare_price
        self.assertEqual(by_id["T001"]["unit_price"], 950_000)
        self.assertEqual(by_id["T001"]["total_price"], 19_000_000)
        self.assertTrue(by_id["T001"]["meets_moq"])

    def test_search_error_stops_early_with_empty_candidates(self) -> None:
        state = base_state(inject={"search_suppliers": "no_match"})
        with patch_data():
            out = tool_search(state)
        self.assertEqual(out["candidates"], [])
        self.assertEqual([e["tool"] for e in out["tool_results"]], ["search_suppliers"])
        self.assertEqual(out["tool_results"][0]["error_type"], "no_match")

    def test_compare_error_yields_empty_candidates_but_keeps_audit_trail(self) -> None:
        state = base_state(inject={"compare_price": "timeout"})
        with patch_data(), patch("time.sleep"):
            out = tool_search(state)
        self.assertEqual(out["candidates"], [])
        self.assertEqual(out["tool_results"][-1]["tool"], "compare_price")
        self.assertEqual(out["tool_results"][-1]["error_type"], "timeout")

    def test_missing_quantity_asks_the_user_instead_of_guessing(self) -> None:
        req = {**REQ, "hard_constraints": {**REQ["hard_constraints"]}}
        del req["hard_constraints"]["quantity"]
        with patch_data():
            out = tool_search(base_state(req=req))
        self.assertEqual(out["status"], "needs_input")
        self.assertIn("số lượng", out["answer"].lower())
        self.assertNotIn("compare_price", [e["tool"] for e in out["tool_results"]])

    def test_plan_without_search_step_is_reported_not_silently_skipped(self) -> None:
        out = tool_search(base_state(plan={"plan_id": "p", "steps": []}))
        self.assertEqual(out["status"], "needs_input")
        self.assertEqual(out["candidates"], [])

    def test_confirm_order_inside_a_plan_is_blocked_not_executed(self) -> None:
        plan = {
            "plan_id": "p",
            "steps": PLAN["steps"] + [
                {"step_id": 9, "action": "confirm_order",
                 "params": {"supplier_id": "T001", "quantity": 20, "confirmed": True},
                 "reason": "r", "depends_on": [1]},
            ],
        }
        with patch_data():
            out = tool_search(base_state(plan=plan))
        blocked = [e for e in out["tool_results"] if e["tool"] == "confirm_order"]
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["status"], "blocked")

    def test_none_valued_params_are_dropped_before_calling_the_tool(self) -> None:
        # Quyet dinh 1: material/region la soft preference, khong duoc loc
        # cung. Plan cu cua B co the con truyen None -> phai bi loai truoc khi goi tool.
        plan = {"plan_id": "p", "steps": [{
            "step_id": 1, "action": "search_suppliers",
            "params": {"product_type": "ghế văn phòng", "material": None, "region": None},
            "reason": "r", "depends_on": [],
        }]}
        with patch_data():
            out = tool_search(base_state(plan=plan))
        self.assertEqual(len(out["candidates"]), 2)


if __name__ == "__main__":
    unittest.main()
