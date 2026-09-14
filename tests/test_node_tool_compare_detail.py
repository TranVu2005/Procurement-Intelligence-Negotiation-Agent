import unittest
from unittest.mock import patch

from src.graph_state import new_state
from src.nodes.tools import tool_compare, tool_detail

FAKE_DATA = [
    {
        "MaNCC": "T001", "TenNCC": "NCC Mot", "LoaiSanPham": "ghế văn phòng",
        "ChatLieu": "vai_boc", "Gia": 1_000_000, "DonViTinh": "cái", "MOQ": 10,
        "TonKho": 100, "ThoiGianGiao": 7, "BaoHanh": 12,
        "ChietKhauTheoSoLuong": [{"tu_so_luong": 10, "phan_tram_giam": 5}],
        "DiemUyTin": 4.5, "KhuVuc": "Ha Noi",
    },
]


def patch_data():
    return patch("src.tools.supplier_tools._load_data", return_value=FAKE_DATA)


def state_with(target_ids, quantity=20):
    hard = {"product_type": "ghế văn phòng", "budget_max": 100_000_000,
            "delivery_deadline_days": 14}
    if quantity is not None:
        hard["quantity"] = quantity
    return {**new_state("x"),
            "req": {"target_supplier_ids": target_ids, "hard_constraints": hard}}


class ToolCompareTests(unittest.TestCase):
    def test_fetches_details_then_compares_the_named_suppliers(self) -> None:
        with patch_data():
            out = tool_compare(state_with(["T001"]))
        self.assertEqual([e["tool"] for e in out["tool_results"]],
                         ["get_supplier_detail", "compare_price"])
        self.assertEqual(out["candidates"][0]["unit_price"], 950_000)
        self.assertEqual(out["candidates"][0]["TonKho"], 100)

    def test_missing_target_ids_asks_the_user(self) -> None:
        out = tool_compare(state_with([]))
        self.assertEqual(out["status"], "needs_input")
        self.assertIn("MaNCC", out["answer"])
        self.assertEqual(out["candidates"], [])

    def test_missing_quantity_asks_the_user(self) -> None:
        with patch_data():
            out = tool_compare(state_with(["T001"], quantity=None))
        self.assertEqual(out["status"], "needs_input")
        self.assertNotIn("compare_price", [e["tool"] for e in out["tool_results"]])

    def test_one_bad_id_does_not_kill_the_whole_call(self) -> None:
        with patch_data():
            out = tool_compare(state_with(["T001", "KHONG_TON_TAI"]))
        self.assertEqual([c["MaNCC"] for c in out["candidates"]], ["T001"])
        failed = [e for e in out["tool_results"]
                  if e["tool"] == "get_supplier_detail" and e["status"] == "error"]
        self.assertEqual(len(failed), 1)


class ToolDetailTests(unittest.TestCase):
    def test_returns_the_full_thirteen_field_record(self) -> None:
        with patch_data():
            out = tool_detail(state_with(["T001"]))
        self.assertEqual([e["tool"] for e in out["tool_results"]], ["get_supplier_detail"])
        self.assertEqual(out["candidates"][0]["BaoHanh"], 12)

    def test_only_the_first_id_is_used(self) -> None:
        # get_supplier_detail chi nhan 1 MaNCC moi lan goi (interface-contracts.md muc 3)
        with patch_data():
            out = tool_detail(state_with(["T001", "T001"]))
        self.assertEqual(len(out["tool_results"]), 1)
        self.assertEqual(len(out["candidates"]), 1)

    def test_unknown_id_ends_with_no_candidate_and_an_error_entry(self) -> None:
        with patch_data():
            out = tool_detail(state_with(["KHONG_TON_TAI"]))
        self.assertEqual(out["candidates"], [])
        self.assertEqual(out["tool_results"][0]["error_type"], "no_match")

    def test_missing_target_ids_asks_the_user(self) -> None:
        out = tool_detail(state_with([]))
        self.assertEqual(out["status"], "needs_input")


if __name__ == "__main__":
    unittest.main()
