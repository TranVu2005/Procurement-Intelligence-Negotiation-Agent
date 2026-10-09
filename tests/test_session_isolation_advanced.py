# -*- coding: utf-8 -*-
"""Tests nâng cao cho session isolation và loại bỏ kết quả cũ (A.3).

Kế hoạch hoàn thiện 2026-10-08 mục A.3:
- Test 2 phiên xen kẽ (S1/S2): kiểm tra req, conversation_history, decisions_made cô lập
- Test kết quả cũ bị loại hoàn toàn khi đổi ngân sách ở lượt 2
- Test delete_session rồi dùng lại session_id → bắt đầu sạch

Nghiệm thu: tests này pass → báo cáo cuối có dòng "Session isolation: N/N".
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memory.db import (
    init_db,
    save_session,
    load_session,
    session_exists,
    delete_session,
    append_conversation,
    load_conversation,
    save_decision,
    load_decisions,
    start_run,
    finish_run,
    load_runs,
    save_artifact,
    load_artifacts,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(session_id: str, product_type: str, quantity: int, budget_max: float,
                deadline: int = 14, intent: str = "search_new",
                ranked: list | None = None) -> dict:
    """Tạo state dict theo đúng schema SYSTEM-RULES §2.1."""
    now = "2026-10-08T10:00:00"
    return {
        "session_id":       session_id,
        "created_at":       now,
        "updated_at":       now,
        "intent":           intent,
        "hard_constraints": {
            "product_type":           product_type,
            "quantity":               quantity,
            "budget_max":             float(budget_max),
            "delivery_deadline_days": deadline,
        },
        "soft_constraints": {
            "material_preference": None,
            "region_preference":   None,
            "min_trust_score":     None,
            "priority":            "balanced",
            "priority_is_default": True,
        },
        "conversation_history": [
            {"role": "user", "content": f"yeu cau dau tien {session_id}", "timestamp": now}
        ],
        "decisions_made":   [],
        # Trường mô phỏng kết quả đã xếp hạng (để test "kết quả cũ bị loại")
        "_ranked_snapshot": ranked or [],
    }


class TestInterleavedSessions(unittest.TestCase):
    """A.3: 2 phiên xen kẽ không ảnh hưởng nhau."""

    S1 = "sess_a3_s1_interleave"
    S2 = "sess_a3_s2_interleave"

    def setUp(self):
        init_db()
        delete_session(self.S1)
        delete_session(self.S2)

    def tearDown(self):
        delete_session(self.S1)
        delete_session(self.S2)

    def test_interleaved_state_isolation(self):
        """S1 lượt 1 → S2 lượt 1 → S1 lượt 2 đổi ngân sách → S2 lượt 2.
        State của S2 không bị ảnh hưởng bởi thay đổi ở S1.
        """
        # S1 lượt 1
        s1_state = _make_state(self.S1, "ghế văn phòng", quantity=50,
                               budget_max=200_000_000, deadline=14)
        save_session(self.S1, s1_state)
        append_conversation(self.S1, "user", "Can mua ghe van phong, 200tr, 14 ngay")

        # S2 lượt 1
        s2_state = _make_state(self.S2, "sofa", quantity=5,
                               budget_max=100_000_000, deadline=20)
        save_session(self.S2, s2_state)
        append_conversation(self.S2, "user", "Can mua sofa, 100tr, 20 ngay")

        # S1 lượt 2: đổi ngân sách
        s1_updated = {
            **s1_state,
            "hard_constraints": {
                **s1_state["hard_constraints"],
                "budget_max": 150_000_000,
            },
            "conversation_history": s1_state["conversation_history"] + [
                {"role": "user", "content": "Giam ngan sach xuong 150tr", "timestamp": "2026-10-08T10:05:00"}
            ],
        }
        save_session(self.S1, s1_updated)

        # S2 lượt 2: không thay đổi
        append_conversation(self.S2, "user", "Luot 2 cua S2")

        # Kiểm tra S2 không bị ảnh hưởng
        loaded_s2 = load_session(self.S2)
        self.assertIsNotNone(loaded_s2)
        self.assertEqual(
            loaded_s2["hard_constraints"]["budget_max"], 100_000_000.0,
            "budget_max của S2 không được thay đổi theo S1"
        )
        self.assertEqual(
            loaded_s2["hard_constraints"]["product_type"], "sofa",
            "product_type của S2 phải giữ nguyên là sofa"
        )
        self.assertEqual(
            loaded_s2["hard_constraints"]["quantity"], 5,
            "quantity của S2 phải giữ nguyên là 5"
        )

        # Kiểm tra conversation_history của S2 chỉ có tin nhắn của S2
        s2_history = load_conversation(self.S2)
        self.assertTrue(
            all("S2" in m["content"] or "sofa" in m["content"].lower() or "Luot 2" in m["content"]
                for m in s2_history),
            "Conversation history S2 không được chứa tin nhắn của S1"
        )
        s2_contents = [m["content"] for m in s2_history]
        self.assertFalse(
            any("ghe van phong" in c.lower() or "ngan sach" in c.lower() for c in s2_contents),
            "Conversation history S2 không được chứa nội dung về ghế văn phòng hay ngân sách S1"
        )

    def test_req_fields_isolated_same_product_type(self):
        """2 phiên cùng product_type nhưng khác quantity — state không trộn lẫn."""
        s1 = _make_state(self.S1, "ghế văn phòng", quantity=20, budget_max=80_000_000)
        s2 = _make_state(self.S2, "ghế văn phòng", quantity=100, budget_max=500_000_000)
        save_session(self.S1, s1)
        save_session(self.S2, s2)

        loaded_s1 = load_session(self.S1)
        loaded_s2 = load_session(self.S2)

        self.assertEqual(loaded_s1["hard_constraints"]["quantity"], 20)
        self.assertEqual(loaded_s2["hard_constraints"]["quantity"], 100)
        self.assertNotEqual(
            loaded_s1["hard_constraints"]["budget_max"],
            loaded_s2["hard_constraints"]["budget_max"],
        )

    def test_decisions_isolated_interleaved(self):
        """Chốt NCC ở S1 không xuất hiện trong decisions của S2."""
        save_session(self.S1, _make_state(self.S1, "kệ", 10, 50_000_000))
        save_session(self.S2, _make_state(self.S2, "bàn làm việc", 3, 30_000_000))

        save_decision(self.S1, "NCC_S1_ONLY")
        save_decision(self.S1, "NCC_S1_ALSO")

        self.assertEqual(load_decisions(self.S2), [],
                         "decisions của S2 phải rỗng, không bị S1 ảnh hưởng")

    def test_conversation_history_isolated_interleaved(self):
        """Tin nhắn của S1 không xuất hiện trong conversation_history của S2."""
        save_session(self.S1, _make_state(self.S1, "tủ hồ sơ", 5, 20_000_000))
        save_session(self.S2, _make_state(self.S2, "sofa", 2, 60_000_000))

        append_conversation(self.S1, "user", "tin nhan chi co trong S1 XYZ123")
        append_conversation(self.S2, "agent", "tra loi cho S2 ABC456")

        s2_conv = load_conversation(self.S2)
        contents_s2 = [m["content"] for m in s2_conv]
        self.assertFalse(
            any("XYZ123" in c for c in contents_s2),
            "Tin nhắn XYZ123 của S1 không được xuất hiện trong conversation S2"
        )


class TestOldResultsCleared(unittest.TestCase):
    """A.3: Kết quả cũ bị loại hoàn toàn khi đổi ngân sách."""

    SID = "sess_a3_budget_change"

    def setUp(self):
        init_db()
        delete_session(self.SID)

    def tearDown(self):
        delete_session(self.SID)

    def test_budget_change_overwrites_state(self):
        """Sau khi đổi ngân sách, state mới phải ghi đè state cũ."""
        # Lượt 1: tìm ghế văn phòng 200tr
        state_v1 = _make_state(self.SID, "ghế văn phòng", 50, 200_000_000, 14)
        save_session(self.SID, state_v1)

        # Lượt 2: đổi ngân sách xuống 100tr
        state_v2 = {
            **state_v1,
            "hard_constraints": {
                **state_v1["hard_constraints"],
                "budget_max": 100_000_000,
            },
            "conversation_history": state_v1["conversation_history"] + [
                {"role": "user", "content": "giam ngan sach con 100tr", "timestamp": "T2"}
            ],
        }
        save_session(self.SID, state_v2)

        loaded = load_session(self.SID)
        self.assertEqual(
            loaded["hard_constraints"]["budget_max"], 100_000_000.0,
            "budget_max phải được ghi đè thành 100tr"
        )
        # Quantity không thay đổi
        self.assertEqual(loaded["hard_constraints"]["quantity"], 50)
        # Conversation history phải có 2 lượt
        saved_history = loaded["conversation_history"]
        self.assertEqual(len(saved_history), 2,
                         "conversation_history phải có đúng 2 lượt sau khi save lại")

    def test_save_overwrites_previous_state_completely(self):
        """save_session() phải ghi đè hoàn toàn — không merge hay giữ field cũ thừa."""
        state_v1 = _make_state(self.SID, "sofa", 10, 300_000_000, 30)
        state_v1["extra_field_v1"] = "should_not_appear"
        save_session(self.SID, state_v1)

        state_v2 = _make_state(self.SID, "sofa", 10, 150_000_000, 30)
        # extra_field_v1 KHÔNG có trong v2
        save_session(self.SID, state_v2)

        loaded = load_session(self.SID)
        # extra_field_v1 không còn (overwrite hoàn toàn)
        self.assertNotIn("extra_field_v1", loaded,
                         "save_session() phải ghi đè hoàn toàn, không merge")
        self.assertEqual(loaded["hard_constraints"]["budget_max"], 150_000_000.0)

    def test_no_supplier_above_new_budget_in_state(self):
        """State sau khi cập nhật budget_max không còn chứa NCC vượt ngân sách mới.

        Note: Test này kiểm tra logic của state, không phải scoring (scoring là B).
        Ở đây kiểm tra rằng khi save state mới (sau ranking/filtering), NCC vượt
        ngân sách mới không còn xuất hiện trong ranked/candidates.
        """
        # Mô phỏng: lượt 1 tìm được 3 NCC, 2 trong đó trong ngân sách 200tr
        candidates_v1 = [
            {"MaNCC": "NCC001", "Gia": 3_000_000, "total_price": 150_000_000},  # trong budget
            {"MaNCC": "NCC002", "Gia": 3_500_000, "total_price": 175_000_000},  # trong budget
            {"MaNCC": "NCC003", "Gia": 4_500_000, "total_price": 225_000_000},  # ngoài budget 200tr
        ]
        state_v1 = _make_state(self.SID, "ghế văn phòng", 50, 200_000_000, 14,
                               ranked=candidates_v1)
        save_session(self.SID, state_v1)

        # Lượt 2: giảm budget xuống 160tr → NCC002 cũng bị loại
        new_budget = 160_000_000
        filtered_v2 = [c for c in candidates_v1 if c["total_price"] <= new_budget]
        state_v2 = {
            **state_v1,
            "hard_constraints": {**state_v1["hard_constraints"], "budget_max": float(new_budget)},
            "_ranked_snapshot": filtered_v2,
        }
        save_session(self.SID, state_v2)

        loaded = load_session(self.SID)
        ranked = loaded.get("_ranked_snapshot", [])
        above_budget = [c for c in ranked if c["total_price"] > new_budget]
        self.assertEqual(
            len(above_budget), 0,
            f"Không được có NCC vượt ngân sách mới ({new_budget:,}đ) trong ranked: {above_budget}"
        )
        self.assertEqual(
            len(ranked), 1,
            "Chỉ còn 1 NCC (NCC001) nằm trong ngân sách 160tr"
        )


class TestDeleteAndReuseSessionId(unittest.TestCase):
    """A.3: delete_session rồi dùng lại session_id → bắt đầu sạch."""

    SID = "sess_a3_reuse"

    def setUp(self):
        init_db()
        delete_session(self.SID)

    def tearDown(self):
        delete_session(self.SID)

    def test_delete_then_save_new_starts_clean(self):
        """Sau delete_session(), save lại với cùng ID phải bắt đầu hoàn toàn sạch."""
        # Phiên cũ
        old_state = _make_state(self.SID, "sofa", 10, 500_000_000, 30)
        save_session(self.SID, old_state)
        append_conversation(self.SID, "user", "noi dung cu")
        save_decision(self.SID, "NCC_OLD")

        # Xóa và tạo lại
        result = delete_session(self.SID)
        self.assertTrue(result, "delete_session() phải trả True khi session tồn tại")
        self.assertFalse(session_exists(self.SID))
        self.assertIsNone(load_session(self.SID))
        self.assertEqual(load_conversation(self.SID), [])
        self.assertEqual(load_decisions(self.SID), [])

        # Tạo lại với cùng session_id
        new_state = _make_state(self.SID, "bàn làm việc", 5, 30_000_000, 7)
        save_session(self.SID, new_state)

        loaded = load_session(self.SID)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["hard_constraints"]["product_type"], "bàn làm việc",
                         "State mới phải là product_type mới, không phải sofa cũ")
        self.assertEqual(loaded["hard_constraints"]["quantity"], 5)

    def test_delete_removes_runs_and_artifacts(self):
        """delete_session() phải xóa cả runs và artifacts liên quan."""
        save_session(self.SID, _make_state(self.SID, "kệ", 3, 10_000_000))
        rid = start_run(self.SID, intent="search_new")
        finish_run(rid, status="success", llm_calls=2, tokens_in=100, tokens_out=50)
        save_artifact(self.SID, "plan", {"plan_id": "p1"}, run_id=rid)

        delete_session(self.SID)

        self.assertEqual(load_runs(self.SID), [],
                         "Runs phải bị xóa sau delete_session()")
        self.assertEqual(load_artifacts(self.SID), [],
                         "Artifacts phải bị xóa sau delete_session()")

    def test_deleted_session_not_in_list(self):
        """Sau delete_session(), session_id không còn trong list_sessions()."""
        from src.memory.db import list_sessions
        save_session(self.SID, _make_state(self.SID, "ghế văn phòng", 20, 60_000_000))
        self.assertIn(self.SID, list_sessions())

        delete_session(self.SID)
        self.assertNotIn(self.SID, list_sessions())

    def test_reused_session_id_no_old_conversation(self):
        """Sau khi xóa và tạo lại session, conversation history của phiên cũ không lộ ra."""
        old_state = _make_state(self.SID, "tủ hồ sơ", 2, 15_000_000)
        save_session(self.SID, old_state)
        append_conversation(self.SID, "user", "tin nhan cu SECRET_CONTENT")

        delete_session(self.SID)

        new_state = _make_state(self.SID, "ghế văn phòng", 10, 50_000_000)
        save_session(self.SID, new_state)
        append_conversation(self.SID, "user", "tin nhan moi sau khi tao lai")

        conv = load_conversation(self.SID)
        contents = [m["content"] for m in conv]
        self.assertFalse(
            any("SECRET_CONTENT" in c for c in contents),
            "Tin nhắn cũ không được xuất hiện sau khi tạo lại session"
        )
        self.assertTrue(
            any("moi sau khi tao lai" in c for c in contents),
            "Tin nhắn mới phải có trong conversation"
        )


class TestGuardPerceivePreservesIntent(unittest.TestCase):
    """A.4: guard_perceive giữ lại intent từ MissingFieldError.partial_state."""

    def test_missing_field_error_preserves_intent_in_graph(self):
        """Khi graph bắt MissingFieldError, intent phải có trong state cuối."""
        from unittest.mock import patch
        from src.graph import build_graph, new_state
        from src.perception.parser import MissingFieldError

        # Mô phỏng perceive raise MissingFieldError với partial_state có intent
        partial = {
            "session_id":       "sess_a4_test",
            "intent":           "search_new",
            "hard_constraints": {"product_type": "ghế văn phòng", "quantity": None,
                                 "budget_max": None, "delivery_deadline_days": None},
            "soft_constraints": {"material_preference": None, "region_preference": None,
                                 "min_trust_score": None, "priority": "balanced",
                                 "priority_is_default": True},
            "conversation_history": [],
            "decisions_made":   [],
        }

        def fake_perceive(state):
            raise MissingFieldError(["số lượng", "ngân sách tối đa"], partial_state=partial)

        graph = build_graph(overrides={"perceive": fake_perceive})
        state = new_state("Cần ghế văn phòng", session_id="sess_a4_test")
        final = graph.invoke(state, config={"recursion_limit": 20})

        self.assertEqual(final.get("status"), "needs_input",
                         "status phải là needs_input khi thiếu thông tin")
        self.assertEqual(final.get("intent"), "search_new",
                         "intent phải được giữ lại từ partial_state, không được là None")
        req = final.get("req")
        self.assertIsNotNone(req, "req phải có trong state cuối (partial_state được giữ)")
        if req:
            self.assertEqual(req.get("intent"), "search_new")


if __name__ == "__main__":
    unittest.main()
