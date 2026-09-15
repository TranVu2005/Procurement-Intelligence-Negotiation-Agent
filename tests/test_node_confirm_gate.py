import unittest
from unittest.mock import patch

from src.graph_state import new_state
from src.nodes.tools import confirm_gate

FAKE_DATA = [
    {
        "MaNCC": "T001", "TenNCC": "NCC Mot", "LoaiSanPham": "ghế văn phòng",
        "ChatLieu": "vai_boc", "Gia": 1_000_000, "DonViTinh": "cái", "MOQ": 10,
        "TonKho": 100, "ThoiGianGiao": 7, "BaoHanh": 12,
        "ChietKhauTheoSoLuong": [], "DiemUyTin": 4.5, "KhuVuc": "Ha Noi",
    },
]


def patch_data():
    return patch("src.tools.supplier_tools._load_data", return_value=FAKE_DATA)


def state_with(user_input, ranked=True):
    return {
        **new_state(user_input),
        "req": {"hard_constraints": {"quantity": 20}},
        "ranked": [{"MaNCC": "T001", "TenNCC": "NCC Mot", "total_price": 20_000_000}] if ranked else [],
        "answer": "Toi de xuat NCC Mot.",
        "status": "success",
    }


class GateBlocksTests(unittest.TestCase):
    def test_a_normal_search_request_is_never_auto_confirmed(self) -> None:
        with patch_data():
            out = confirm_gate(state_with("Can 20 ghe van phong gia tot"))
        self.assertIsNotNone(out["pending_confirmation"])
        self.assertEqual(out["pending_confirmation"]["supplier_id"], "T001")
        self.assertEqual(out["status"], "needs_confirmation")
        self.assertNotIn("order_confirmed", str(out))

    def test_pending_answer_asks_for_explicit_confirmation(self) -> None:
        with patch_data():
            out = confirm_gate(state_with("Can 20 ghe van phong"))
        self.assertIn("xac nhan", out["answer"].lower())
        self.assertIn("T001", out["answer"])

    def test_no_ranked_supplier_means_nothing_to_confirm(self) -> None:
        out = confirm_gate(state_with("chot don di", ranked=False))
        self.assertIsNone(out["pending_confirmation"])
        self.assertEqual(out["status"], "success")
        self.assertEqual(out.get("tool_results", []), [])


class GateConfirmsTests(unittest.TestCase):
    def test_explicit_confirmation_executes_the_order(self) -> None:
        with patch_data():
            out = confirm_gate(state_with("ok chot don di"))
        self.assertIsNone(out["pending_confirmation"])
        self.assertEqual(out["status"], "success")
        entry = out["tool_results"][0]
        self.assertEqual(entry["tool"], "confirm_order")
        self.assertEqual(entry["status"], "ok")
        self.assertTrue(entry["result"]["order_confirmed"])
        self.assertIn("T001", out["answer"])

    def test_confirmation_uses_quantity_from_state_not_a_guess(self) -> None:
        with patch_data():
            out = confirm_gate(state_with("dong y chot"))
        self.assertEqual(out["tool_results"][0]["result"]["quantity"], 20)

    def test_a_refusal_is_not_read_as_a_confirmation(self) -> None:
        with patch_data():
            out = confirm_gate(state_with("khong dong y, tim cho khac"))
        self.assertEqual(out["status"], "needs_confirmation")
        self.assertEqual(out.get("tool_results", []), [])


if __name__ == "__main__":
    unittest.main()
