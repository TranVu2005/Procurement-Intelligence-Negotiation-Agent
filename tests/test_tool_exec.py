import unittest
from unittest.mock import patch

from src.graph_state import new_state
from src.nodes.tool_exec import TOOL_REGISTRY, run_tool

FAKE_DATA = [
    {
        "MaNCC": "T001", "TenNCC": "Test NCC", "LoaiSanPham": "ghế văn phòng",
        "ChatLieu": "gỗ tự nhiên", "Gia": 1_000_000, "DonViTinh": "cái", "MOQ": 10,
        "TonKho": 100, "ThoiGianGiao": 7, "BaoHanh": 12,
        "ChietKhauTheoSoLuong": [{"tu_so_luong": 10, "phan_tram_giam": 5}],
        "DiemUyTin": 4.5, "KhuVuc": "Hà Nội",
    },
]


def patch_data():
    return patch("src.tools.supplier_tools._load_data", return_value=FAKE_DATA)


class RegistryTests(unittest.TestCase):
    def test_confirm_order_is_not_callable_from_a_plan(self) -> None:
        # Hanh dong hau qua cao chi di qua confirm_gate (SYSTEM-RULES.md muc 3)
        self.assertNotIn("confirm_order", TOOL_REGISTRY)
        self.assertEqual(
            set(TOOL_REGISTRY), {"search_suppliers", "get_supplier_detail", "compare_price"}
        )


class RunToolTests(unittest.TestCase):
    def test_success_produces_ok_entry_with_latency(self) -> None:
        with patch_data():
            result, entry = run_tool(new_state("x"), "search_suppliers",
                                     {"product_type": "ghế văn phòng"}, step_id=1)
        self.assertEqual(len(result["suppliers"]), 1)
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["tool"], "search_suppliers")
        self.assertEqual(entry["step_id"], 1)
        self.assertEqual(entry["attempts"], 1)
        self.assertGreaterEqual(entry["latency_ms"], 0)

    def test_unknown_tool_name_returns_error_not_exception(self) -> None:
        result, entry = run_tool(new_state("x"), "khong_ton_tai", {})
        self.assertTrue(result["error"])
        self.assertEqual(result["error_type"], "tool_unavailable")
        self.assertEqual(entry["status"], "error")

    def test_injected_timeout_is_retried_then_reported(self) -> None:
        state = {**new_state("x"), "inject": {"search_suppliers": "timeout"}}
        with patch_data(), patch("time.sleep"):
            result, entry = run_tool(state, "search_suppliers", {"product_type": "ghế văn phòng"})
        self.assertEqual(result["error_type"], "timeout")
        self.assertEqual(entry["status"], "error")
        self.assertEqual(entry["attempts"], 3)  # 1 lan dau + 2 lan retry

    def test_injected_no_match_is_not_retried(self) -> None:
        state = {**new_state("x"), "inject": {"search_suppliers": "no_match"}}
        with patch_data(), patch("time.sleep"):
            _result, entry = run_tool(state, "search_suppliers", {"product_type": "ghế văn phòng"})
        self.assertEqual(entry["attempts"], 1)

    def test_injection_targets_only_the_named_tool(self) -> None:
        state = {**new_state("x"), "inject": {"compare_price": "timeout"}}
        with patch_data():
            _result, entry = run_tool(state, "search_suppliers", {"product_type": "ghế văn phòng"})
        self.assertEqual(entry["status"], "ok")

    def test_compare_price_supports_injection_too(self) -> None:
        state = {**new_state("x"), "inject": {"compare_price": "tool_unavailable"}}
        with patch_data(), patch("time.sleep"):
            result, _entry = run_tool(state, "compare_price",
                                      {"supplier_ids": ["T001"], "quantity": 10})
        self.assertEqual(result["error_type"], "tool_unavailable")

    def test_a_tool_that_raises_becomes_a_contract_shaped_error(self) -> None:
        # Tham so la -> search_suppliers nem TypeError. Graph khong duoc sap;
        # loi phai tro ve dung shape hop dong de B re-plan duoc.
        with patch_data():
            result, entry = run_tool(new_state("x"), "search_suppliers",
                                     {"product_type": "ghế văn phòng", "khoa_la": 1})
        self.assertTrue(result["error"])
        self.assertEqual(result["error_type"], "tool_unavailable")
        self.assertEqual(entry["status"], "error")


if __name__ == "__main__":
    unittest.main()
