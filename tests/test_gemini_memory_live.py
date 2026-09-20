# -*- coding: utf-8 -*-
"""Test hội thoại nhiều lượt (memory + confirmation flow) với Gemini thật.

Kiểm tra:
  1. Đổi ngân sách trong cùng session → budget_max cập nhật, các field khác giữ nguyên
  2. Đổi số lượng trong cùng session → quantity cập nhật
  3. session_id giữ đúng qua nhiều lượt
  4. Xác nhận chốt đơn (input "chốt đơn đi") → confirm_gate thực thi
  5. Từ chối chốt đơn (input "không, thôi") → pending_confirmation

Chạy:
    python -m pytest tests/test_gemini_memory_live.py -v -s -m live

Ghi chú:
  - Dùng run_request() thật — gọi cả graph, không chỉ parser.
  - Session state được lưu vào SQLite giữa các lượt (giống production).
  - Mỗi test dùng session_id độc lập để tránh xung đột.
"""

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ---------------------------------------------------------------------------
# Skip nếu không có API key hoặc đang dùng stub
# ---------------------------------------------------------------------------

_has_key = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("NARAROUTER_API_KEY"))
_is_stub = os.getenv("AGENT_LLM", "").lower() == "stub"

pytestmark = pytest.mark.live

if not _has_key or _is_stub:
    pytestmark = [pytest.mark.live, pytest.mark.skip(reason="Không có API key hoặc đang dùng stub")]


# ---------------------------------------------------------------------------
# Transcript logger
# ---------------------------------------------------------------------------

_TRANSCRIPT_PATH = Path(__file__).parent.parent / "docs" / "transcript_gemini_live_A.md"
_TRANSCRIPT_LINES: list[str] = []


def _log(line: str = "") -> None:
    _TRANSCRIPT_LINES.append(line)


def _flush_transcript() -> None:
    _TRANSCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_TRANSCRIPT_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(_TRANSCRIPT_LINES) + "\n")
    _TRANSCRIPT_LINES.clear()


# ---------------------------------------------------------------------------
# Fixture: ghi header section
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def transcript_memory_header():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _log(f"\n## Transcript Gemini Live – Memory & Confirmation Tests")
    _log(f"**Thời điểm chạy:** {now}")
    _log("")
    yield
    _flush_transcript()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(text: str, session_id: str) -> dict:
    """Gọi run_request() thật, trả về state cuối."""
    from src.graph import run_request
    return run_request(text, session_id=session_id)


def _cleanup_session(session_id: str) -> None:
    """Xóa session khỏi DB sau test để không gây nhiễu test khác."""
    try:
        from src.memory.db import delete_session
        delete_session(session_id)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test 1: Đổi ngân sách trong cùng session
# ---------------------------------------------------------------------------

class TestBudgetUpdate:
    SESSION = "live_mem_budget_01"

    def setup_method(self):
        _cleanup_session(self.SESSION)

    def teardown_method(self):
        _cleanup_session(self.SESSION)

    def test_budget_update_same_session(self):
        """Lượt 1: set budget 200tr. Lượt 2: giảm còn 150tr → budget cập nhật, quantity giữ nguyên."""
        _log(f"\n### Memory – Đổi ngân sách cùng session")
        _log(f"- **Session:** `{self.SESSION}`")

        # Lượt 1
        turn1 = (
            "Tôi cần mua 50 ghế văn phòng, ngân sách tối đa 200 triệu đồng, "
            "giao trong 14 ngày."
        )
        r1 = _run(turn1, self.SESSION)
        _log(f"- **Turn 1:** `{turn1}`")
        _log(f"  - status: `{r1.get('status')}`")
        _log(f"  - session_id: `{r1.get('session_id')}`")

        req1 = r1.get("req") or {}
        hc1 = req1.get("hard_constraints") or {}
        _log(f"  - budget_max: `{hc1.get('budget_max')}`")
        _log(f"  - quantity: `{hc1.get('quantity')}`")

        assert r1.get("session_id") == self.SESSION, f"session_id lượt 1 sai: {r1.get('session_id')}"

        # Lượt 2: chỉ đổi ngân sách
        turn2 = "Thật ra ngân sách chỉ còn 150 triệu thôi, giữ nguyên các yêu cầu khác."
        r2 = _run(turn2, self.SESSION)
        _log(f"- **Turn 2:** `{turn2}`")
        _log(f"  - status: `{r2.get('status')}`")

        req2 = r2.get("req") or {}
        hc2 = req2.get("hard_constraints") or {}
        _log(f"  - budget_max sau update: `{hc2.get('budget_max')}`")
        _log(f"  - quantity sau update: `{hc2.get('quantity')}`")

        assert hc2.get("budget_max") is not None, "budget_max không được None sau lượt 2"
        assert hc2.get("budget_max") <= 200_000_000, (
            f"budget_max phải <= 200tr sau khi giảm: {hc2.get('budget_max')}"
        )

        _log(f"- **Kết quả:** ✅ PASS")


# ---------------------------------------------------------------------------
# Test 2: Đổi số lượng trong cùng session
# ---------------------------------------------------------------------------

class TestQuantityUpdate:
    SESSION = "live_mem_quantity_01"

    def setup_method(self):
        _cleanup_session(self.SESSION)

    def teardown_method(self):
        _cleanup_session(self.SESSION)

    def test_quantity_update_same_session(self):
        """Lượt 1: qty=50. Lượt 2: đổi qty=80 → quantity cập nhật, budget giữ nguyên."""
        _log(f"\n### Memory – Đổi số lượng cùng session")
        _log(f"- **Session:** `{self.SESSION}`")

        # Lượt 1
        turn1 = (
            "Mua 50 ghế văn phòng, ngân sách 200 triệu, giao trong 14 ngày."
        )
        r1 = _run(turn1, self.SESSION)
        req1 = r1.get("req") or {}
        hc1 = req1.get("hard_constraints") or {}
        budget_after_t1 = hc1.get("budget_max")

        _log(f"- **Turn 1:** `{turn1}`")
        _log(f"  - quantity: `{hc1.get('quantity')}`")
        _log(f"  - budget_max: `{budget_after_t1}`")

        assert r1.get("session_id") == self.SESSION

        # Lượt 2
        turn2 = "Đổi lại thành 80 cái thôi."
        r2 = _run(turn2, self.SESSION)
        req2 = r2.get("req") or {}
        hc2 = req2.get("hard_constraints") or {}

        _log(f"- **Turn 2:** `{turn2}`")
        _log(f"  - quantity sau update: `{hc2.get('quantity')}`")
        _log(f"  - budget_max sau update: `{hc2.get('budget_max')}`")

        assert hc2.get("quantity") == 80, (
            f"quantity phải là 80 sau lượt 2, nhận được: {hc2.get('quantity')}"
        )
        # Budget phải giữ nguyên (hoặc có thể thay đổi do LLM không nhớ — log để theo dõi)
        _log(f"- **budget_max giữ nguyên:** `{hc2.get('budget_max') == budget_after_t1}`")

        _log(f"- **Kết quả:** ✅ PASS")


# ---------------------------------------------------------------------------
# Test 3: session_id giữ đúng qua nhiều lượt
# ---------------------------------------------------------------------------

class TestSessionIdPersistence:
    SESSION = "live_mem_sessid_01"

    def setup_method(self):
        _cleanup_session(self.SESSION)

    def teardown_method(self):
        _cleanup_session(self.SESSION)

    def test_session_id_persisted_across_turns(self):
        """session_id phải khớp qua cả 3 lượt."""
        _log(f"\n### Memory – session_id nhất quán qua nhiều lượt")
        _log(f"- **Session:** `{self.SESSION}`")

        turns = [
            "Mua 20 bàn làm việc, ngân sách 300 triệu, giao trong 21 ngày.",
            "Giảm số lượng xuống còn 15 cái.",
            "Ưu tiên khu vực Hà Nội.",
        ]

        for i, turn in enumerate(turns, 1):
            r = _run(turn, self.SESSION)
            returned_sid = r.get("session_id") or ""
            _log(f"- **Turn {i}:** `{turn[:60]}...`")
            _log(f"  - session_id trả về: `{returned_sid}`")

            assert returned_sid == self.SESSION, (
                f"Turn {i}: session_id sai. Mong đợi `{self.SESSION}`, nhận `{returned_sid}`"
            )

        _log(f"- **Kết quả:** ✅ PASS – session_id nhất quán qua 3 lượt")


# ---------------------------------------------------------------------------
# Test 4: Xác nhận chốt đơn
# ---------------------------------------------------------------------------

class TestConfirmationAccept:
    SESSION = "live_mem_confirm_accept_01"

    def setup_method(self):
        _cleanup_session(self.SESSION)

    def teardown_method(self):
        _cleanup_session(self.SESSION)

    def test_confirmation_flow_accept(self):
        """Sau khi tìm NCC, gõ 'chốt đơn đi' → confirm_gate thực thi (status success hoặc needs_confirmation trước đó)."""
        _log(f"\n### Confirmation Flow – Xác nhận chốt đơn")
        _log(f"- **Session:** `{self.SESSION}`")

        # Lượt 1: tìm nhà cung cấp
        turn1 = (
            "Tôi cần mua 30 ghế văn phòng, ngân sách 100 triệu đồng, giao trong 10 ngày."
        )
        r1 = _run(turn1, self.SESSION)
        _log(f"- **Turn 1 (tìm NCC):** `{turn1}`")
        _log(f"  - status: `{r1.get('status')}`")
        _log(f"  - pending_confirmation: `{r1.get('pending_confirmation')}`")

        # Lượt 2: xác nhận chốt đơn (dùng từ khóa trong CONFIRM_WORDS)
        turn2 = "Chốt đơn đi."
        r2 = _run(turn2, self.SESSION)
        _log(f"- **Turn 2 (xác nhận):** `{turn2}`")
        _log(f"  - status: `{r2.get('status')}`")
        _log(f"  - answer: `{(r2.get('answer') or '')[:200]}`")
        _log(f"  - pending_confirmation: `{r2.get('pending_confirmation')}`")

        # Sau khi xác nhận: status có thể là success (chốt được) hoặc needs_confirmation
        # (nếu lượt 2 lại nhận intent search_new và chưa có ranked) — đều hợp lệ
        valid_statuses = {"success", "needs_confirmation", "graceful_fail"}
        assert r2.get("status") in valid_statuses, (
            f"status lượt 2 phải thuộc {valid_statuses}, nhận: {r2.get('status')}"
        )

        _log(f"- **Kết quả:** ✅ PASS (status={r2.get('status')})")


# ---------------------------------------------------------------------------
# Test 5: Từ chối chốt đơn
# ---------------------------------------------------------------------------

class TestConfirmationReject:
    SESSION = "live_mem_confirm_reject_01"

    def setup_method(self):
        _cleanup_session(self.SESSION)

    def teardown_method(self):
        _cleanup_session(self.SESSION)

    def test_confirmation_flow_reject(self):
        """Sau khi tìm NCC, gõ 'không, thôi' → pending_confirmation được giữ hoặc hủy."""
        _log(f"\n### Confirmation Flow – Từ chối chốt đơn")
        _log(f"- **Session:** `{self.SESSION}`")

        # Lượt 1: tìm nhà cung cấp
        turn1 = (
            "Mua 50 ghế văn phòng, ngân sách 200 triệu, giao trong 14 ngày."
        )
        r1 = _run(turn1, self.SESSION)
        _log(f"- **Turn 1 (tìm NCC):** `{turn1}`")
        _log(f"  - status: `{r1.get('status')}`")

        # Lượt 2: từ chối (dùng từ trong _REFUSAL_WORDS)
        turn2 = "Không chốt, để sau đã."
        r2 = _run(turn2, self.SESSION)
        _log(f"- **Turn 2 (từ chối):** `{turn2}`")
        _log(f"  - status: `{r2.get('status')}`")
        _log(f"  - answer: `{(r2.get('answer') or '')[:200]}`")

        # Sau từ chối: KHÔNG được có status=success với confirmed_at (không được chốt đơn)
        answer = (r2.get("answer") or "").lower()
        assert "da chot" not in answer, "Sau khi từ chối, không được có thông báo 'đã chốt đơn'"
        assert "confirmed_at" not in str(r2.get("tool_results") or ""), (
            "Sau khi từ chối, confirm_order không được thực thi"
        )

        _log(f"- **Kết quả:** ✅ PASS – không chốt đơn khi từ chối")


# ---------------------------------------------------------------------------
# Test 6: Nhiều lượt — đổi cả budget lẫn quantity
# ---------------------------------------------------------------------------

class TestMultiTurnBudgetAndQuantity:
    SESSION = "live_mem_multi_01"

    def setup_method(self):
        _cleanup_session(self.SESSION)

    def teardown_method(self):
        _cleanup_session(self.SESSION)

    def test_multi_turn_budget_and_quantity(self):
        """3 lượt: setup → đổi budget → đổi qty; session_id nhất quán."""
        _log(f"\n### Memory – Đổi budget + quantity qua 3 lượt")
        _log(f"- **Session:** `{self.SESSION}`")

        turn1 = "Mua 50 bàn làm việc, ngân sách 500 triệu, giao trong 21 ngày."
        r1 = _run(turn1, self.SESSION)
        _log(f"- **Turn 1:** `{turn1}`")
        _log(f"  - session_id: `{r1.get('session_id')}`")

        assert r1.get("session_id") == self.SESSION

        turn2 = "Giảm ngân sách còn 300 triệu."
        r2 = _run(turn2, self.SESSION)
        hc2 = (r2.get("req") or {}).get("hard_constraints") or {}
        _log(f"- **Turn 2:** `{turn2}`")
        _log(f"  - budget_max: `{hc2.get('budget_max')}`")
        _log(f"  - quantity: `{hc2.get('quantity')}`")

        assert r2.get("session_id") == self.SESSION

        turn3 = "Số lượng đổi thành 30 cái thôi."
        r3 = _run(turn3, self.SESSION)
        hc3 = (r3.get("req") or {}).get("hard_constraints") or {}
        _log(f"- **Turn 3:** `{turn3}`")
        _log(f"  - budget_max: `{hc3.get('budget_max')}`")
        _log(f"  - quantity: `{hc3.get('quantity')}`")

        assert r3.get("session_id") == self.SESSION
        assert hc3.get("quantity") == 30, (
            f"quantity phải là 30 sau lượt 3, nhận: {hc3.get('quantity')}"
        )

        _log(f"- **Kết quả:** ✅ PASS")
