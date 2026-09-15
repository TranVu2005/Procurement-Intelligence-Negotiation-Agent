import unittest
from unittest.mock import patch

from src.tools.supplier_tools import compare_price, get_supplier_detail, search_suppliers

FAKE_DATA = [
    {
        "MaNCC": "T001", "TenNCC": "NCC Mot", "LoaiSanPham": "ghế văn phòng",
        "ChatLieu": "vai_boc", "Gia": 1_000_000, "DonViTinh": "cái", "MOQ": 10,
        "TonKho": 100, "ThoiGianGiao": 7, "BaoHanh": 12,
        "ChietKhauTheoSoLuong": [], "DiemUyTin": 4.5, "KhuVuc": "Ha Noi",
        "nguon_url": "https://vi.du/nguon", "nguon_type": "public_listing",
        "fetched_at": "2026-09-13", "simulated_fields": ["Gia", "MOQ"],
    },
    {
        "MaNCC": "T002", "TenNCC": "NCC Thieu Nguon", "LoaiSanPham": "ghế văn phòng",
        "ChatLieu": "vai_boc", "Gia": 900_000, "DonViTinh": "cái", "MOQ": 5,
        "TonKho": 50, "ThoiGianGiao": 9, "BaoHanh": 6,
        "ChietKhauTheoSoLuong": [], "DiemUyTin": 4.0, "KhuVuc": "Ha Noi",
    },
]


def patch_data():
    return patch("src.tools.supplier_tools._load_data", return_value=FAKE_DATA)


class SearchSourceFieldTests(unittest.TestCase):
    def test_summary_records_carry_the_source_fields(self) -> None:
        with patch_data():
            first = search_suppliers("ghế văn phòng")["suppliers"][0]
        self.assertEqual(first["nguon_url"], "https://vi.du/nguon")
        self.assertEqual(first["nguon_type"], "public_listing")
        self.assertEqual(first["fetched_at"], "2026-09-13")
        self.assertEqual(first["simulated_fields"], ["Gia", "MOQ"])

    def test_a_record_without_source_fields_does_not_crash_the_response(self) -> None:
        with patch_data():
            second = search_suppliers("ghế văn phòng")["suppliers"][1]
        self.assertIsNone(second["nguon_url"])
        self.assertEqual(second["simulated_fields"], [])


class ComparePriceSourceFieldTests(unittest.TestCase):
    def test_successful_comparison_carries_the_citation_fields(self) -> None:
        with patch_data():
            item = compare_price(["T001"], quantity=20)["comparisons"][0]
        self.assertEqual(item["nguon_url"], "https://vi.du/nguon")
        self.assertEqual(item["simulated_fields"], ["Gia", "MOQ"])

    def test_error_elements_keep_the_plain_error_shape(self) -> None:
        with patch_data():
            item = compare_price(["KHONG_TON_TAI"], quantity=20)["comparisons"][0]
        self.assertTrue(item["error"])
        self.assertNotIn("nguon_url", item)


class DetailUnchangedTests(unittest.TestCase):
    def test_detail_already_returns_the_full_record(self) -> None:
        with patch_data():
            record = get_supplier_detail("T001")
        self.assertEqual(record["nguon_url"], "https://vi.du/nguon")


if __name__ == "__main__":
    unittest.main()
