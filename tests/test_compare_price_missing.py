import unittest
from unittest.mock import patch

from src.graph_state import new_state
from src.nodes.respond import build_evidence_block
from src.tools.supplier_tools import compare_price

BASE = {"TenNCC": "NCC", "LoaiSanPham": "sofa", "ChatLieu": None, "DonViTinh": "bo",
        "TonKho": 10, "ThoiGianGiao": 7, "BaoHanh": None, "ChietKhauTheoSoLuong": [],
        "DiemUyTin": None, "KhuVuc": "TP.HCM", "nguon_url": "https://vi.du",
        "simulated_fields": []}
FAKE_DATA = [
    {**BASE, "MaNCC": "OK1", "Gia": 1_000_000, "MOQ": 1},
    {**BASE, "MaNCC": "NOPRICE", "Gia": None, "MOQ": 1},
    {**BASE, "MaNCC": "NOMOQ", "Gia": 2_000_000, "MOQ": None},
]


class ComparePriceMissingFieldTests(unittest.TestCase):
    def test_null_price_or_moq_errors_only_that_element(self) -> None:
        with patch("src.tools.supplier_tools._load_data", return_value=FAKE_DATA):
            out = compare_price(["OK1", "NOPRICE", "NOMOQ"], quantity=2)
        by_id = {item["MaNCC"]: item for item in out["comparisons"]}
        self.assertEqual(by_id["OK1"]["total_price"], 2_000_000)
        for sid, field in (("NOPRICE", "Gia"), ("NOMOQ", "MOQ")):
            with self.subTest(sid=sid):
                self.assertTrue(by_id[sid]["error"])
                self.assertEqual(by_id[sid]["error_type"], "tool_unavailable")
                self.assertIn(field, by_id[sid]["message"])


class ToolDetailSupplierIdTests(unittest.TestCase):
    def test_singular_supplier_id_from_the_parser_is_used(self) -> None:
        from src.nodes.tools import tool_detail
        state = {**new_state("Cho xem NCC006"),
                 "req": {"supplier_id": "NCC006", "supplier_ids": [], "target_supplier_ids": []}}
        out = tool_detail(state)
        self.assertNotIn("status", out)
        self.assertEqual([c["MaNCC"] for c in out["candidates"]], ["NCC006"])

    def test_no_code_at_all_still_asks_the_user(self) -> None:
        from src.nodes.tools import tool_detail
        out = tool_detail({**new_state("Cho xem chi tiet"), "req": {}})
        self.assertEqual(out["status"], "needs_input")


class EvidenceProductNameTests(unittest.TestCase):
    def test_product_name_is_part_of_the_evidence(self) -> None:
        state = {**new_state("x"), "ranked": [{
            "MaNCC": "SRC001", "TenNCC": "Noi That Linco", "TenSanPham": "Sofa KT62 Cornwall",
            "unit_price": 9_400_000, "total_price": 9_400_000, "nguon_url": "https://vi.du",
        }], "verdict": {}}
        self.assertIn("san_pham=Sofa KT62 Cornwall", build_evidence_block(state))


if __name__ == "__main__":
    unittest.main()
