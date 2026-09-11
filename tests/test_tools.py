import time
import unittest
from unittest.mock import patch

from src.logging_utils.tracer import audit_entry, log_tool_call, new_trace_id, redact
from src.tools.supplier_tools import compare_price, get_supplier_detail, search_suppliers

# Du lieu gia lap doc lap voi mock_data/suppliers.json that - tranh test vo tinh
# gay ra boi nguoi khac sua dataset. T002 co y thieu field MOQ de test duong loi
# "dataset thieu field" (interface-contracts.md muc 3).
FAKE_DATA = [
    {
        "MaNCC": "T001", "TenNCC": "Test NCC Du Field", "LoaiSanPham": "ghế văn phòng",
        "ChatLieu": "gỗ tự nhiên", "Gia": 1_000_000, "DonViTinh": "cái", "MOQ": 10,
        "TonKho": 100, "ThoiGianGiao": 7, "BaoHanh": 12,
        "ChietKhauTheoSoLuong": [{"tu_so_luong": 10, "phan_tram_giam": 5}],
        "DiemUyTin": 4.5, "KhuVuc": "Hà Nội",
    },
    {
        "MaNCC": "T002", "TenNCC": "Test NCC Thieu MOQ", "LoaiSanPham": "ghế văn phòng",
        "ChatLieu": "gỗ tự nhiên", "Gia": 900_000, "DonViTinh": "cái",
        "TonKho": 50, "ThoiGianGiao": 10, "BaoHanh": 12,
        "ChietKhauTheoSoLuong": [], "DiemUyTin": 4.0, "KhuVuc": "Hà Nội",
    },
]


def patch_data():
    return patch("src.tools.supplier_tools._load_data", return_value=FAKE_DATA)


class SearchSuppliersTests(unittest.TestCase):
    def test_matches_by_product_type(self) -> None:
        with patch_data():
            result = search_suppliers("ghế văn phòng")
        self.assertEqual([s["MaNCC"] for s in result["suppliers"]], ["T001", "T002"])

    def test_missing_dataset_field_becomes_null_not_crash(self) -> None:
        # T002 thieu MOQ trong dataset gia lap -> khong duoc KeyError ca response,
        # field do phai la null (contract khong co slot loi rieng cho search_suppliers).
        with patch_data():
            result = search_suppliers("ghế văn phòng")
        t002 = next(s for s in result["suppliers"] if s["MaNCC"] == "T002")
        self.assertIsNone(t002["MOQ"])

    def test_missing_product_type_is_invalid_input(self) -> None:
        result = search_suppliers("")
        self.assertEqual(result["error_type"], "invalid_input")

    def test_no_match_returns_standard_error_shape(self) -> None:
        with patch_data():
            result = search_suppliers("sofa khong ton tai")
        self.assertEqual(
            result, {"error": True, "error_type": "no_match", "message": result["message"]}
        )

    def test_simulate_error_passthrough(self) -> None:
        result = search_suppliers("ghế văn phòng", _simulate_error="timeout")
        self.assertEqual(result["error_type"], "timeout")


class GetSupplierDetailTests(unittest.TestCase):
    def test_returns_full_13_field_record(self) -> None:
        with patch_data():
            result = get_supplier_detail("T001")
        self.assertEqual(result["MaNCC"], "T001")
        self.assertEqual(len(result), 13)

    def test_unknown_id_is_no_match(self) -> None:
        with patch_data():
            result = get_supplier_detail("KHONG_TON_TAI")
        self.assertEqual(result["error_type"], "no_match")

    def test_missing_supplier_id_is_invalid_input(self) -> None:
        result = get_supplier_detail("")
        self.assertEqual(result["error_type"], "invalid_input")


class ComparePriceTests(unittest.TestCase):
    def test_valid_id_returns_discounted_price_and_moq(self) -> None:
        with patch_data():
            result = compare_price(["T001"], quantity=10)
        comparison = result["comparisons"][0]
        self.assertEqual(comparison["unit_price"], 950_000)
        self.assertEqual(comparison["discount_applied"], "5%")
        self.assertEqual(comparison["total_price"], 9_500_000)
        self.assertTrue(comparison["meets_moq"])

    def test_unknown_id_errors_only_that_element(self) -> None:
        with patch_data():
            result = compare_price(["T001", "KHONG_TON_TAI"], quantity=10)
        ok_item, bad_item = result["comparisons"]
        self.assertNotIn("error", ok_item)
        self.assertEqual(bad_item["error_type"], "no_match")

    def test_missing_dataset_field_errors_only_that_element(self) -> None:
        # T002 thieu MOQ -> phai loi tool_unavailable RIENG phan tu nay,
        # khong duoc lam crash / fail ca response (contract muc 3).
        with patch_data():
            result = compare_price(["T001", "T002"], quantity=10)
        ok_item, bad_item = result["comparisons"]
        self.assertNotIn("error", ok_item)
        self.assertEqual(bad_item["MaNCC"], "T002")
        self.assertEqual(bad_item["error_type"], "tool_unavailable")

    def test_empty_supplier_ids_is_invalid_input(self) -> None:
        result = compare_price([], quantity=10)
        self.assertEqual(result["error_type"], "invalid_input")

    def test_non_positive_quantity_is_invalid_input(self) -> None:
        result = compare_price(["T001"], quantity=0)
        self.assertEqual(result["error_type"], "invalid_input")


class TracerTests(unittest.TestCase):
    def test_redact_masks_only_sensitive_keys(self) -> None:
        redacted = redact({"api_key": "secret123", "product_type": "ghế văn phòng"})
        self.assertEqual(redacted["api_key"], "***")
        self.assertEqual(redacted["product_type"], "ghế văn phòng")

    def test_new_trace_id_is_unique_hex(self) -> None:
        a, b = new_trace_id(), new_trace_id()
        self.assertNotEqual(a, b)
        int(a, 16)  # raise ValueError neu khong phai hex

    def test_audit_entry_shape_and_redaction(self) -> None:
        entry = audit_entry(
            "t1", "compare_price", {"api_key": "x", "quantity": 5}, "ok", 12.3, result_count=2
        )
        self.assertEqual(
            entry,
            {
                "trace_id": "t1",
                "tool": "compare_price",
                "params": {"api_key": "***", "quantity": 5},
                "status": "ok",
                "latency_ms": 12.3,
                "result_count": 2,
            },
        )

    def test_log_tool_call_returns_entry_with_latency(self) -> None:
        start = time.perf_counter()
        entry = log_tool_call("t2", "search_suppliers", start, "ok", params={"product_type": "sofa"})
        self.assertGreaterEqual(entry["latency_ms"], 0)
        self.assertEqual(entry["tool"], "search_suppliers")


if __name__ == "__main__":
    unittest.main()
