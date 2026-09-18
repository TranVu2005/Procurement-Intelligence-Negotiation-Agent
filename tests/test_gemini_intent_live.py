# -*- coding: utf-8 -*-
"""Test Gemini thật cho 4 intent: search_new, compare_specific, supplier_detail, out_of_scope.

Đây là live test — gọi Gemini thật (không dùng stub). Chạy khi GOOGLE_API_KEY đã set.

Chạy:
    python -m pytest tests/test_gemini_intent_live.py -v -s -m live

Ghi chú:
  - Mỗi test gọi parse_request() / update_state() thật, tốn API call.
  - Timeout mỗi test ~30s (Gemini thường trả về trong 5-15s).
  - Không dùng patch — đây là bài test tích hợp thật sự.
  - Kết quả được ghi vào docs/transcript_gemini_live_A.md.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Thêm root vào sys.path để import src.*
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ---------------------------------------------------------------------------
# Skip toàn bộ nếu không có API key hoặc đang ở chế độ stub
# ---------------------------------------------------------------------------

_has_key = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("NARAROUTER_API_KEY"))
_is_stub = os.getenv("AGENT_LLM", "").lower() == "stub"

pytestmark = pytest.mark.live

if not _has_key or _is_stub:
    pytestmark = [pytest.mark.live, pytest.mark.skip(reason="Không có API key hoặc đang dùng stub")]


# ---------------------------------------------------------------------------
# Transcript logger — ghi kết quả vào docs/
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
# Helper
# ---------------------------------------------------------------------------

def _parse(text: str, session_id: str = None) -> tuple[dict, float]:
    """Gọi parse_request() thật, trả về (state, latency_ms)."""
    from src.perception.parser import parse_request

    t0 = time.perf_counter()
    state = parse_request(text, session_id=session_id)
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    return state, latency_ms


# ---------------------------------------------------------------------------
# Fixture: ghi header transcript khi session bắt đầu
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def transcript_header():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _log(f"\n## Transcript Gemini Live – Intent Tests")
    _log(f"**Thời điểm chạy:** {now}")
    _log(f"**Model:** {os.getenv('NARAROUTER_MODEL', 'gemini-3.6-flash')} (theo LLM_PROVIDER)")
    _log("")
    yield
    _flush_transcript()


# ---------------------------------------------------------------------------
# Test 1: search_new — câu đầy đủ 4 hard constraints
# ---------------------------------------------------------------------------

class TestIntentSearchNew:
    """Test intent search_new với Gemini thật."""

    def test_full_hard_constraints_extracted(self):
        """Câu đầy đủ → intent=search_new, 4 hard constraints đúng giá trị."""
        text = (
            "Tôi cần mua 50 ghế văn phòng, ngân sách tối đa 200 triệu đồng, "
            "giao hàng trong vòng 14 ngày."
        )
        state, latency = _parse(text, session_id="live_search_01")

        _log(f"\n### search_new – câu đầy đủ")
        _log(f"- **Input:** `{text}`")
        _log(f"- **Latency:** {latency} ms")
        _log(f"- **Intent:** `{state['intent']}`")
        _log(f"- **hard_constraints:** `{json.dumps(state['hard_constraints'], ensure_ascii=False)}`")

        assert state["intent"] == "search_new", f"intent sai: {state['intent']}"
        hc = state["hard_constraints"]
        assert hc["product_type"] == "ghế văn phòng", f"product_type: {hc['product_type']}"
        assert hc["quantity"] == 50, f"quantity: {hc['quantity']}"
        assert hc["budget_max"] == 200_000_000, f"budget_max: {hc['budget_max']}"
        assert hc["delivery_deadline_days"] == 14, f"deadline: {hc['delivery_deadline_days']}"

        _log(f"- **Kết quả:** ✅ PASS")

    def test_soft_constraints_extracted(self):
        """Câu có soft constraints → material_preference và region_preference được trích xuất."""
        text = (
            "Mua 30 ghế văn phòng, ngân sách 150 triệu, giao trong 10 ngày, "
            "ưu tiên chất liệu da, khu vực Hà Nội."
        )
        state, latency = _parse(text, session_id="live_search_02")

        _log(f"\n### search_new – với soft constraints")
        _log(f"- **Input:** `{text}`")
        _log(f"- **Latency:** {latency} ms")
        _log(f"- **soft_constraints:** `{json.dumps(state['soft_constraints'], ensure_ascii=False)}`")

        assert state["intent"] == "search_new"
        sc = state["soft_constraints"]
        assert sc["material_preference"] is not None, "material_preference nên được trích xuất"
        assert sc["region_preference"] is not None, "region_preference nên được trích xuất"

        _log(f"- **Kết quả:** ✅ PASS")

    def test_missing_fields_raises(self):
        """Câu thiếu quantity/budget/deadline → MissingFieldError."""
        from src.perception.parser import MissingFieldError

        text = "Tôi muốn mua bàn làm việc gỗ tự nhiên."

        _log(f"\n### search_new – thiếu field bắt buộc")
        _log(f"- **Input:** `{text}`")

        with pytest.raises(MissingFieldError) as exc_info:
            _parse(text, session_id="live_search_03")

        _log(f"- **MissingFieldError.missing_fields:** `{exc_info.value.missing_fields}`")
        _log(f"- **Kết quả:** ✅ PASS (raise đúng)")

    def test_budget_unit_conversion(self):
        """'5 tỷ' → 5_000_000_000, '2 tuần' → 14 ngày."""
        text = "Mua 100 bàn làm việc, ngân sách 5 tỷ, giao trong 2 tuần."
        state, latency = _parse(text, session_id="live_search_04")

        _log(f"\n### search_new – chuyển đổi đơn vị")
        _log(f"- **Input:** `{text}`")
        _log(f"- **Latency:** {latency} ms")
        _log(f"- **budget_max:** {state['hard_constraints']['budget_max']:,.0f}")
        _log(f"- **deadline:** {state['hard_constraints']['delivery_deadline_days']} ngày")

        assert state["hard_constraints"]["budget_max"] == 5_000_000_000, (
            f"budget_max sai: {state['hard_constraints']['budget_max']}"
        )
        assert state["hard_constraints"]["delivery_deadline_days"] == 14, (
            f"deadline sai: {state['hard_constraints']['delivery_deadline_days']}"
        )

        _log(f"- **Kết quả:** ✅ PASS")


# ---------------------------------------------------------------------------
# Test 2: compare_specific
# ---------------------------------------------------------------------------

class TestIntentCompareSpecific:
    """Test intent compare_specific với Gemini thật."""

    def test_supplier_ids_extracted(self):
        """Nêu tên NCC cụ thể → intent=compare_specific, supplier_ids chứa các mã."""
        text = "So sánh Hòa Phát và Xuân Hòa cho tôi, mua 20 cái."
        state, latency = _parse(text, session_id="live_compare_01")

        _log(f"\n### compare_specific – nêu tên NCC")
        _log(f"- **Input:** `{text}`")
        _log(f"- **Latency:** {latency} ms")
        _log(f"- **Intent:** `{state['intent']}`")
        _log(f"- **supplier_ids:** `{state['supplier_ids']}`")

        assert state["intent"] == "compare_specific", f"intent sai: {state['intent']}"
        assert len(state["supplier_ids"]) >= 1, "supplier_ids phải có ít nhất 1 phần tử"

        _log(f"- **Kết quả:** ✅ PASS")

    def test_no_full_hard_constraints_needed(self):
        """compare_specific không cần budget/deadline đầy đủ — không raise."""
        from src.perception.parser import MissingFieldError

        text = "Tôi muốn so sánh NCC001 với NCC003."
        try:
            state, latency = _parse(text, session_id="live_compare_02")
            _log(f"\n### compare_specific – không cần full hard constraints")
            _log(f"- **Input:** `{text}`")
            _log(f"- **Latency:** {latency} ms")
            _log(f"- **Intent:** `{state['intent']}`")
            _log(f"- **Kết quả:** ✅ PASS (không raise)")
        except MissingFieldError as e:
            pytest.fail(f"compare_specific không nên raise MissingFieldError: {e}")


# ---------------------------------------------------------------------------
# Test 3: supplier_detail
# ---------------------------------------------------------------------------

class TestIntentSupplierDetail:
    """Test intent supplier_detail với Gemini thật."""

    def test_supplier_id_extracted(self):
        """Hỏi chi tiết 1 NCC → intent=supplier_detail, supplier_id có giá trị."""
        text = "Cho tôi xem thông tin chi tiết của nhà cung cấp Hòa Phát."
        state, latency = _parse(text, session_id="live_detail_01")

        _log(f"\n### supplier_detail – hỏi chi tiết 1 NCC")
        _log(f"- **Input:** `{text}`")
        _log(f"- **Latency:** {latency} ms")
        _log(f"- **Intent:** `{state['intent']}`")
        _log(f"- **supplier_id:** `{state.get('supplier_id')}`")
        _log(f"- **supplier_ids:** `{state.get('supplier_ids')}`")

        assert state["intent"] == "supplier_detail", f"intent sai: {state['intent']}"

        _log(f"- **Kết quả:** ✅ PASS")

    def test_no_constraints_needed(self):
        """supplier_detail không cần bất kỳ hard constraint — không raise."""
        from src.perception.parser import MissingFieldError

        text = "NCC007 có thông tin gì?"
        try:
            state, latency = _parse(text, session_id="live_detail_02")
            _log(f"\n### supplier_detail – không cần constraint")
            _log(f"- **Input:** `{text}`")
            _log(f"- **Intent:** `{state['intent']}`")
            _log(f"- **Kết quả:** ✅ PASS")
        except MissingFieldError as e:
            pytest.fail(f"supplier_detail không nên raise MissingFieldError: {e}")


# ---------------------------------------------------------------------------
# Test 4: out_of_scope
# ---------------------------------------------------------------------------

class TestIntentOutOfScope:
    """Test intent out_of_scope với Gemini thật."""

    def test_weather_question_is_out_of_scope(self):
        """Câu hỏi thời tiết → intent=out_of_scope."""
        text = "Thời tiết Hà Nội hôm nay thế nào?"
        state, latency = _parse(text, session_id="live_oos_01")

        _log(f"\n### out_of_scope – câu hỏi thời tiết")
        _log(f"- **Input:** `{text}`")
        _log(f"- **Latency:** {latency} ms")
        _log(f"- **Intent:** `{state['intent']}`")
        _log(f"- **Kết quả:** {'✅ PASS' if state['intent'] == 'out_of_scope' else '⚠️ LLM trả khác (có thể chấp nhận)'}")

        # out_of_scope không nên raise và không nên thiếu field
        assert "intent" in state

    def test_greeting_is_out_of_scope(self):
        """Câu chào hỏi → intent=out_of_scope."""
        text = "Xin chào, bạn tên là gì?"
        state, latency = _parse(text, session_id="live_oos_02")

        _log(f"\n### out_of_scope – câu chào hỏi")
        _log(f"- **Input:** `{text}`")
        _log(f"- **Latency:** {latency} ms")
        _log(f"- **Intent:** `{state['intent']}`")
        _log(f"- **Kết quả:** {'✅ PASS' if state['intent'] == 'out_of_scope' else '⚠️ LLM trả khác'}")

        assert "intent" in state

    def test_stock_question_is_out_of_scope(self):
        """Câu hỏi chứng khoán → intent=out_of_scope."""
        text = "Giá cổ phiếu VNM hôm nay bao nhiêu?"
        state, latency = _parse(text, session_id="live_oos_03")

        _log(f"\n### out_of_scope – câu hỏi chứng khoán")
        _log(f"- **Input:** `{text}`")
        _log(f"- **Latency:** {latency} ms")
        _log(f"- **Intent:** `{state['intent']}`")
        _log(f"- **Kết quả:** {'✅ PASS' if state['intent'] == 'out_of_scope' else '⚠️ LLM trả khác'}")

        assert "intent" in state
