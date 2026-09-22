"""Loi cua C tim thay khi chay kich ban demo 2026-09-22 (docs/demo-scenarios-2026-09-22.md)."""

import unittest
from unittest.mock import patch

from src.graph import run_request
from src.graph_state import new_state
from src.nodes.respond import build_evidence_block, respond
from src.nodes.tool_exec import run_tool
from src.nodes.tools import confirm_gate
from src.perception.parser import MissingFieldError

FAKE_DATA = [{
    "MaNCC": "T001", "TenNCC": "NCC Mot", "LoaiSanPham": "ghế văn phòng",
    "ChatLieu": "vai_boc", "Gia": 1_000_000, "DonViTinh": "cái", "MOQ": 10,
    "TonKho": 100, "ThoiGianGiao": 7, "BaoHanh": 12,
    "ChietKhauTheoSoLuong": [], "DiemUyTin": 4.5, "KhuVuc": "Ha Noi",
}]

RANKED = [{
    "MaNCC": "T001", "TenNCC": "NCC Mot", "unit_price": 950_000,
    "total_price": 19_000_000, "ThoiGianGiao": 7, "MOQ": 10, "TonKho": 100,
    "DiemUyTin": 4.5, "BaoHanh": 12, "KhuVuc": "Ha Noi", "ChatLieu": "vai_boc",
    "leverage_score": 82.0, "nguon_url": "https://vi.du/nguon", "simulated_fields": ["MOQ"],
}]


def confirm_turn_state(user_input="ok chot don di", decisions=None):
    history = [{"role": "user", "content": f"luot {i}"} for i in range(2)]
    return {
        **new_state(user_input),
        "intent": "search_new",
        "req": {"hard_constraints": {"quantity": 20}, "conversation_history": history,
                "decisions_made": decisions or []},
        "ranked": RANKED,
        "verdict": {"passed": True, "violations": [], "claims": []},
    }


class MissingFieldKeepsSessionTests(unittest.TestCase):
    """P0-3: luot bo sung sau needs_input phai tiep tuc dung session cu."""

    def test_session_of_the_partial_state_reaches_the_final_state(self) -> None:
        def perceive(_state):
            raise MissingFieldError(["số lượng"], partial_state={"session_id": "sess_partial"})

        with patch("src.graph.save_session"), patch("src.graph.append_conversation"):
            final = run_request("Toi muon mua ban lam viec", overrides={"perceive": perceive})
        self.assertEqual(final["status"], "needs_input")
        self.assertEqual(final["session_id"], "sess_partial")


class ConfirmTurnTests(unittest.TestCase):
    """P0-5 / P1-3: luot chot don khong duoc tu mau thuan, khong tao don trung."""

    def test_respond_skips_the_llm_on_an_explicit_confirmation_turn(self) -> None:
        with patch("src.nodes.respond.get_llm") as get_llm:
            out = respond(confirm_turn_state())
        get_llm.assert_not_called()
        self.assertEqual(out["llm_calls"], 0)

    def test_respond_still_calls_the_llm_on_a_normal_turn(self) -> None:
        class OneChunk:
            def stream(self, _messages):
                from langchain_core.messages import AIMessage
                yield AIMessage(content="De xuat T001")

        with patch("src.nodes.respond.get_llm", return_value=OneChunk()):
            out = respond(confirm_turn_state("tang len 30 cai"))
        self.assertEqual(out["llm_calls"], 1)

    def test_confirmed_answer_is_a_summary_not_the_previous_text(self) -> None:
        state = {**confirm_turn_state(), "answer": "Toi khong the tu dong chot don giup ban."}
        with patch("src.tools.supplier_tools._load_data", return_value=FAKE_DATA):
            out = confirm_gate(state)
        self.assertEqual(out["status"], "success")
        self.assertNotIn("khong the tu dong chot", out["answer"])
        self.assertIn("T001", out["answer"])
        self.assertIn("19000000", out["answer"])
        self.assertIn("https://vi.du/nguon", out["answer"])

    def test_repeating_the_confirmation_does_not_place_a_second_order(self) -> None:
        state = confirm_turn_state(decisions=[{"supplier_id": "T001",
                                               "confirmed_at": "2026-09-22T09:00:00"}])
        with patch("src.tools.supplier_tools._load_data", return_value=FAKE_DATA):
            out = confirm_gate(state)
        self.assertEqual(out.get("tool_results", []), [])
        self.assertEqual(out["status"], "success")
        self.assertIn("2026-09-22T09:00:00", out["answer"])


class EvidenceBlockFieldsTests(unittest.TestCase):
    """P0-6 / P1-7: LLM phai thay khu vuc, chat lieu, ton kho va ly do loai."""

    def test_region_material_stock_and_warranty_are_in_the_evidence(self) -> None:
        block = build_evidence_block({**new_state("x"), "ranked": RANKED})
        for text in ("Ha Noi", "vai_boc", "ton_kho=100", "bao_hanh=12"):
            self.assertIn(text, block)

    def test_rejected_suppliers_are_listed_with_the_reason(self) -> None:
        rejected = [{"supplier_id": "T009", "violations": [{
            "code": "stock_below_quantity", "field": "TonKho", "actual": 24, "required": ">= 30",
        }]}]
        block = build_evidence_block({**new_state("x"), "ranked": RANKED, "rejected": rejected})
        self.assertIn("T009", block)
        self.assertIn("stock_below_quantity", block)
        self.assertIn("24", block)

    def test_long_rejection_lists_are_capped(self) -> None:
        rejected = [{"supplier_id": f"R{i:03d}", "violations": [{
            "code": "budget_exceeded", "field": "total_price", "actual": 1, "required": "<= 0",
        }]} for i in range(30)]
        block = build_evidence_block({**new_state("x"), "ranked": RANKED, "rejected": rejected})
        self.assertIn("R000", block)
        self.assertNotIn("R029", block)
        self.assertIn("20 NCC khac", block)


class TransientInjectionTests(unittest.TestCase):
    """P1-5: loi thoang qua phai cho thay retry phuc hoi duoc."""

    def test_error_on_the_first_attempt_only_is_recovered_by_retry(self) -> None:
        state = {**new_state("x"), "inject": {"search_suppliers": "timeout:1"}}
        with patch("src.tools.retry.time.sleep"):
            result, entry = run_tool(state, "search_suppliers", {"product_type": "ghế văn phòng"})
        self.assertFalse(result.get("error"))
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["attempts"], 2)

    def test_more_failures_than_retries_still_ends_in_the_error(self) -> None:
        state = {**new_state("x"), "inject": {"search_suppliers": "tool_unavailable:5"}}
        with patch("src.tools.retry.time.sleep"):
            result, entry = run_tool(state, "search_suppliers", {"product_type": "ghế văn phòng"})
        self.assertTrue(result["error"])
        self.assertEqual(entry["attempts"], 3)


if __name__ == "__main__":
    unittest.main()
