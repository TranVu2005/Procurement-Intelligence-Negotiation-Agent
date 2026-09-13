# -*- coding: utf-8 -*-
"""Test automation cho phần A — Perception & Memory.

Tất cả tests đều không gọi LLM (offline). Validation logic và SQLite được test
trực tiếp bằng cách inject extracted dict vào internal helpers và gọi DB trực tiếp.

Chạy:
    python -m unittest tests/test_parser_validation.py -v
    # hoặc
    pytest tests/test_parser_validation.py -v

Owner: Nguoi A
"""

import sys
import os
import unittest

# Đảm bảo import được từ thư mục gốc
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memory.db import (
    init_db,
    save_session,
    load_session,
    session_exists,
    delete_session,
    list_sessions,
    append_conversation,
    load_conversation,
    save_decision,
    load_decisions,
)
from src.perception.parser import (
    VALID_PRODUCT_TYPES,
    InvalidProductTypeError,
    MissingFieldError,
)


# ---------------------------------------------------------------------------
# Helpers — xây dựng state và giả lập extracted dict mà không cần LLM
# ---------------------------------------------------------------------------

def _make_state(
    session_id: str = "sess_test",
    product_type: str = "ghế văn phòng",
    quantity: int = 50,
    budget_max: float = 200_000_000,
    delivery_deadline_days: int = 14,
    material: str | None = "gỗ tự nhiên",
    region: str | None = "Hà Nội",
    min_trust_score: float | None = 4.0,
) -> dict:
    """Tạo state dict hợp lệ theo SYSTEM-RULES §2.1 mà không cần LLM."""
    now = "2026-09-12T10:00:00"
    return {
        "session_id": session_id,
        "created_at": now,
        "updated_at": now,
        "hard_constraints": {
            "product_type": product_type,
            "quantity": quantity,
            "budget_max": budget_max,
            "delivery_deadline_days": delivery_deadline_days,
        },
        "soft_constraints": {
            "material_preference": material,
            "region_preference": region,
            "min_trust_score": min_trust_score,
        },
        "conversation_history": [
            {"role": "user", "content": "test input", "timestamp": now}
        ],
        "decisions_made": [],
    }


def _apply_update(existing_state: dict, extracted: dict) -> dict:
    """Áp dụng validation logic của update_state() trực tiếp lên extracted dict.

    Hàm này tái hiện phần validation trong update_state() (sau khi LLM extract)
    để test offline mà không cần gọi Gemini.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    updated_hard = dict(existing_state["hard_constraints"])
    if extracted.get("product_type") is not None:
        p = str(extracted["product_type"]).strip().lower()
        if p not in VALID_PRODUCT_TYPES:
            raise InvalidProductTypeError(extracted["product_type"])
        updated_hard["product_type"] = p
    if extracted.get("quantity") is not None:
        qty = int(extracted["quantity"])
        if qty <= 0:
            raise ValueError(f"quantity phải > 0, nhận được: {qty}")
        updated_hard["quantity"] = qty
    if extracted.get("budget_max") is not None:
        bmax = float(extracted["budget_max"])
        if bmax <= 0:
            raise ValueError(f"budget_max phải > 0, nhận được: {bmax}")
        updated_hard["budget_max"] = bmax
    if extracted.get("delivery_deadline_days") is not None:
        ddays = int(extracted["delivery_deadline_days"])
        if ddays <= 0:
            raise ValueError(f"delivery_deadline_days phải > 0, nhận được: {ddays}")
        updated_hard["delivery_deadline_days"] = ddays

    updated_soft = dict(existing_state["soft_constraints"])
    if extracted.get("material_preference") is not None:
        updated_soft["material_preference"] = extracted["material_preference"]
    if extracted.get("region_preference") is not None:
        updated_soft["region_preference"] = extracted["region_preference"]
    if extracted.get("min_trust_score") is not None:
        min_trust = float(extracted["min_trust_score"])
        if 1.0 <= min_trust <= 5.0:
            updated_soft["min_trust_score"] = min_trust
        # Nếu ngoài range [1,5] → bỏ qua, giữ nguyên giá trị cũ

    history = list(existing_state.get("conversation_history", []))
    history.append({"role": "user", "content": "[update]", "timestamp": now})

    return {
        **existing_state,
        "updated_at": now,
        "hard_constraints": updated_hard,
        "soft_constraints": updated_soft,
        "conversation_history": history,
    }


# ---------------------------------------------------------------------------
# Test class 1: Input validation trong update_state()
# ---------------------------------------------------------------------------

class TestUpdateStateValidation(unittest.TestCase):
    """Kiểm tra validation logic của update_state() — offline, không cần LLM."""

    def setUp(self):
        self.state = _make_state()

    # --- quantity ---

    def test_quantity_zero_is_rejected(self):
        """quantity = 0 phải raise ValueError (case_004)."""
        with self.assertRaises(ValueError) as ctx:
            _apply_update(self.state, {"quantity": 0})
        self.assertIn("quantity", str(ctx.exception))

    def test_quantity_negative_is_rejected(self):
        """quantity âm phải raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            _apply_update(self.state, {"quantity": -5})
        self.assertIn("quantity", str(ctx.exception))

    def test_quantity_valid_is_accepted(self):
        """quantity hợp lệ (> 0) phải được chấp nhận và cập nhật."""
        updated = _apply_update(self.state, {"quantity": 80})
        self.assertEqual(updated["hard_constraints"]["quantity"], 80)

    # --- budget_max ---

    def test_budget_zero_is_rejected(self):
        """budget_max = 0 phải raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            _apply_update(self.state, {"budget_max": 0})
        self.assertIn("budget_max", str(ctx.exception))

    def test_budget_negative_is_rejected(self):
        """budget_max âm phải raise ValueError (case_005)."""
        with self.assertRaises(ValueError) as ctx:
            _apply_update(self.state, {"budget_max": -1_000_000})
        self.assertIn("budget_max", str(ctx.exception))

    def test_budget_valid_is_accepted(self):
        """budget_max hợp lệ phải được chấp nhận."""
        updated = _apply_update(self.state, {"budget_max": 150_000_000})
        self.assertEqual(updated["hard_constraints"]["budget_max"], 150_000_000)

    # --- delivery_deadline_days ---

    def test_deadline_zero_is_rejected(self):
        """delivery_deadline_days = 0 phải raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            _apply_update(self.state, {"delivery_deadline_days": 0})
        self.assertIn("delivery_deadline_days", str(ctx.exception))

    def test_deadline_negative_is_rejected(self):
        """delivery_deadline_days âm phải raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            _apply_update(self.state, {"delivery_deadline_days": -3})
        self.assertIn("delivery_deadline_days", str(ctx.exception))

    # --- product_type ---

    def test_invalid_product_type_is_rejected(self):
        """product_type không trong catalog phải raise InvalidProductTypeError."""
        with self.assertRaises(InvalidProductTypeError):
            _apply_update(self.state, {"product_type": "máy lạnh"})

    def test_valid_product_type_is_accepted(self):
        """product_type hợp lệ phải được chấp nhận."""
        updated = _apply_update(self.state, {"product_type": "sofa"})
        self.assertEqual(updated["hard_constraints"]["product_type"], "sofa")

    # --- min_trust_score ---

    def test_min_trust_out_of_range_is_ignored(self):
        """min_trust_score ngoài [1,5] phải bị bỏ qua — giá trị cũ giữ nguyên, không crash.

        Lý do: update_state() không nên xóa mất min_trust_score hợp lệ cũ chỉ vì
        LLM trả về giá trị ngoài range trong lần update mới.
        """
        # state gốc có min_trust_score = 4.0 hợp lệ
        state_with_trust = _make_state(min_trust_score=4.0)
        updated = _apply_update(state_with_trust, {"min_trust_score": 6.0})
        # Giá trị cũ 4.0 phải còn nguyên
        self.assertEqual(updated["soft_constraints"]["min_trust_score"], 4.0)

    def test_min_trust_valid_is_accepted(self):
        """min_trust_score hợp lệ phải được cập nhật."""
        updated = _apply_update(self.state, {"min_trust_score": 3.5})
        self.assertEqual(updated["soft_constraints"]["min_trust_score"], 3.5)

    # --- Multi-turn: chỉ field được đề cập mới thay đổi ---

    def test_multi_turn_only_mentioned_fields_change(self):
        """Multi-turn: đổi quantity → budget_max và các field khác phải giữ nguyên (case_006)."""
        original_budget = self.state["hard_constraints"]["budget_max"]
        original_deadline = self.state["hard_constraints"]["delivery_deadline_days"]
        original_material = self.state["soft_constraints"]["material_preference"]

        updated = _apply_update(self.state, {"quantity": 80})

        self.assertEqual(updated["hard_constraints"]["quantity"], 80)
        self.assertEqual(updated["hard_constraints"]["budget_max"], original_budget)
        self.assertEqual(updated["hard_constraints"]["delivery_deadline_days"], original_deadline)
        self.assertEqual(updated["soft_constraints"]["material_preference"], original_material)

    def test_multi_turn_conversation_history_grows(self):
        """Mỗi lần update phải append 1 turn mới vào conversation_history."""
        original_len = len(self.state["conversation_history"])
        updated = _apply_update(self.state, {"quantity": 80})
        self.assertEqual(len(updated["conversation_history"]), original_len + 1)

    def test_multi_turn_does_not_mutate_original_state(self):
        """update_state() không được sửa đổi state gốc (immutability)."""
        original_qty = self.state["hard_constraints"]["quantity"]
        _apply_update(self.state, {"quantity": 80})
        self.assertEqual(self.state["hard_constraints"]["quantity"], original_qty)


# ---------------------------------------------------------------------------
# Test class 2: SQLite — Session isolation
# ---------------------------------------------------------------------------

class TestSessionIsolation(unittest.TestCase):
    """Kiểm tra session isolation theo SYSTEM-RULES §5 — offline, SQLite only."""

    SESS_A = "sess_iso_a_unittest"
    SESS_B = "sess_iso_b_unittest"
    SESS_DEL = "sess_iso_del_unittest"

    def setUp(self):
        init_db()
        # Xóa sạch các session test trước khi chạy
        delete_session(self.SESS_A)
        delete_session(self.SESS_B)
        delete_session(self.SESS_DEL)

    def tearDown(self):
        # Dọn dẹp sau khi test
        delete_session(self.SESS_A)
        delete_session(self.SESS_B)
        delete_session(self.SESS_DEL)

    def _save(self, session_id: str, **kwargs) -> dict:
        state = _make_state(session_id=session_id, **kwargs)
        save_session(session_id, state)
        return state

    def test_two_sessions_do_not_leak_data(self):
        """Load sess_a không được thấy dữ liệu của sess_b và ngược lại (case_007)."""
        self._save(self.SESS_A, product_type="ghế văn phòng", quantity=20)
        self._save(self.SESS_B, product_type="sofa", quantity=3)

        loaded_a = load_session(self.SESS_A)
        loaded_b = load_session(self.SESS_B)

        self.assertIsNotNone(loaded_a)
        self.assertIsNotNone(loaded_b)

        # A không chứa dữ liệu của B
        self.assertEqual(loaded_a["session_id"], self.SESS_A)
        self.assertEqual(loaded_a["hard_constraints"]["product_type"], "ghế văn phòng")
        self.assertEqual(loaded_a["hard_constraints"]["quantity"], 20)

        # B không chứa dữ liệu của A
        self.assertEqual(loaded_b["session_id"], self.SESS_B)
        self.assertEqual(loaded_b["hard_constraints"]["product_type"], "sofa")
        self.assertEqual(loaded_b["hard_constraints"]["quantity"], 3)

    def test_conversation_history_isolated_per_session(self):
        """Conversation history của sess_a không rò sang sess_b."""
        self._save(self.SESS_A, product_type="ghế văn phòng", quantity=20)
        self._save(self.SESS_B, product_type="sofa", quantity=3)

        append_conversation(self.SESS_A, "agent", "Đây là phản hồi phiên A")
        append_conversation(self.SESS_B, "agent", "Đây là phản hồi phiên B")

        conv_a = load_conversation(self.SESS_A)
        conv_b = load_conversation(self.SESS_B)

        # Nội dung không lẫn
        contents_a = [t["content"] for t in conv_a]
        contents_b = [t["content"] for t in conv_b]

        self.assertIn("phiên A", " ".join(contents_a))
        self.assertNotIn("phiên B", " ".join(contents_a))
        self.assertIn("phiên B", " ".join(contents_b))
        self.assertNotIn("phiên A", " ".join(contents_b))

    def test_decisions_isolated_per_session(self):
        """Decisions của sess_a không rò sang sess_b."""
        self._save(self.SESS_A, product_type="ghế văn phòng", quantity=20)
        self._save(self.SESS_B, product_type="sofa", quantity=3)

        save_decision(self.SESS_A, "NCC_A_ONLY")
        save_decision(self.SESS_B, "NCC_B_ONLY")

        decs_a = load_decisions(self.SESS_A)
        decs_b = load_decisions(self.SESS_B)

        ids_a = [d["supplier_id"] for d in decs_a]
        ids_b = [d["supplier_id"] for d in decs_b]

        self.assertIn("NCC_A_ONLY", ids_a)
        self.assertNotIn("NCC_B_ONLY", ids_a)
        self.assertIn("NCC_B_ONLY", ids_b)
        self.assertNotIn("NCC_A_ONLY", ids_b)

    def test_delete_session_removes_all_data(self):
        """Sau delete_session(): session_exists()=False, load_session()=None (case_008)."""
        self._save(self.SESS_DEL, product_type="kệ", quantity=5)
        append_conversation(self.SESS_DEL, "user", "tin nhắn test")
        save_decision(self.SESS_DEL, "NCC_TO_DELETE")

        self.assertTrue(session_exists(self.SESS_DEL))

        result = delete_session(self.SESS_DEL)

        self.assertTrue(result, "delete_session() phải trả True khi xóa thành công")
        self.assertFalse(session_exists(self.SESS_DEL))
        self.assertIsNone(load_session(self.SESS_DEL))
        self.assertEqual(load_conversation(self.SESS_DEL), [])
        self.assertEqual(load_decisions(self.SESS_DEL), [])

    def test_delete_nonexistent_session_returns_false(self):
        """delete_session() trên session không tồn tại phải trả False."""
        result = delete_session("sess_khong_ton_tai_xyz")
        self.assertFalse(result)

    def test_load_nonexistent_session_returns_none(self):
        """load_session() trên session không tồn tại phải trả None."""
        self.assertIsNone(load_session("sess_khong_ton_tai_xyz"))

    def test_list_sessions_includes_saved_sessions(self):
        """list_sessions() phải chứa các session đã save."""
        self._save(self.SESS_A, product_type="ghế văn phòng", quantity=20)
        self._save(self.SESS_B, product_type="sofa", quantity=3)

        sessions = list_sessions()
        self.assertIn(self.SESS_A, sessions)
        self.assertIn(self.SESS_B, sessions)

    def test_list_sessions_excludes_deleted_sessions(self):
        """Sau khi delete, session không còn trong list_sessions()."""
        self._save(self.SESS_DEL, product_type="kệ", quantity=5)
        self.assertIn(self.SESS_DEL, list_sessions())

        delete_session(self.SESS_DEL)
        self.assertNotIn(self.SESS_DEL, list_sessions())


# ---------------------------------------------------------------------------
# Test class 3: Kiểm tra constants và exceptions
# ---------------------------------------------------------------------------

class TestParserConstants(unittest.TestCase):
    """Kiểm tra constants và exception behavior của parser module."""

    def test_valid_product_types_not_empty(self):
        """VALID_PRODUCT_TYPES phải có ít nhất 1 giá trị."""
        self.assertGreater(len(VALID_PRODUCT_TYPES), 0)

    def test_expected_product_types_present(self):
        """Các loại nội thất cơ bản phải có trong enum."""
        expected = {"ghế văn phòng", "bàn làm việc", "tủ hồ sơ", "kệ", "sofa"}
        for pt in expected:
            self.assertIn(pt, VALID_PRODUCT_TYPES, f"'{pt}' thiếu trong VALID_PRODUCT_TYPES")

    def test_missing_field_error_contains_field_list(self):
        """MissingFieldError phải expose danh sách field còn thiếu."""
        err = MissingFieldError(["số lượng", "ngân sách tối đa"])
        self.assertIn("số lượng", err.missing_fields)
        self.assertIn("ngân sách tối đa", err.missing_fields)
        self.assertIn("số lượng", str(err))

    def test_invalid_product_type_error_contains_value(self):
        """InvalidProductTypeError phải mention giá trị sai trong message."""
        err = InvalidProductTypeError("máy lạnh")
        self.assertIn("máy lạnh", str(err))


if __name__ == "__main__":
    unittest.main()
