# -*- coding: utf-8 -*-
"""Script test thu cong cho buoi hop 2.

Chay: python tests/test_parse_and_memory.py

Kiểm tra:
  1. parse_request() trả đúng schema với câu đầy đủ
  2. parse_request() raise MissingFieldError khi thiếu field
  3. parse_request() raise InvalidProductTypeError khi sản phẩm không hợp lệ
  4. save_session() + load_session() roundtrip
  5. append_conversation() + load_conversation()
  6. save_decision() + load_decisions()
  7. update_state() ghi đè đúng field
"""

import sys
import os
import io

# Force UTF-8 stdout tren Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Thêm thư mục gốc vào path để import src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env TRUOC KHI import bat ky gi dung LLM
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from src.memory.db import (
    init_db,
    save_session,
    load_session,
    session_exists,
    append_conversation,
    load_conversation,
    save_decision,
    load_decisions,
)
from src.perception.parser import (
    parse_request,
    update_state,
    MissingFieldError,
    InvalidProductTypeError,
)

# ─────────────────────────────────────────────
# Màu terminal
# ─────────────────────────────────────────────
GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW= "\033[93m"
RESET = "\033[0m"
BOLD  = "\033[1m"

passed = 0
failed = 0


def ok(msg: str):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str, err: str = ""):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {msg}")
    if err:
        print(f"    {RED}{err}{RESET}")


def section(title: str):
    print(f"\n{BOLD}{YELLOW}== {title} =={RESET}")


# ─────────────────────────────────────────────
# Init DB
# ─────────────────────────────────────────────
section("0. Khởi tạo DB")
try:
    init_db()
    ok("init_db() không lỗi")
except Exception as e:
    fail("init_db() lỗi", str(e))

# ─────────────────────────────────────────────
# Test 1: parse_request — câu đầy đủ
# ─────────────────────────────────────────────
section("1. parse_request() — câu đầy đủ")
INPUT_1 = "Tôi cần mua 50 ghế văn phòng, ngân sách tối đa 200 triệu đồng, giao hàng trong vòng 14 ngày, ưu tiên chất liệu gỗ tự nhiên, khu vực Hà Nội."
state1 = None
try:
    state1 = parse_request(INPUT_1, session_id="sess_test01")

    # Kiểm tra schema
    for key in ["session_id", "created_at", "updated_at", "hard_constraints", "soft_constraints", "conversation_history", "decisions_made"]:
        if key in state1:
            ok(f"Có field: {key}")
        else:
            fail(f"Thiếu field: {key}")

    hc = state1["hard_constraints"]
    sc = state1["soft_constraints"]

    # Hard constraints
    assert hc["product_type"] == "ghế văn phòng", f"product_type sai: {hc['product_type']}"
    ok(f"product_type = {hc['product_type']!r}")

    assert hc["quantity"] == 50, f"quantity sai: {hc['quantity']}"
    ok(f"quantity = {hc['quantity']}")

    assert hc["budget_max"] == 200_000_000, f"budget_max sai: {hc['budget_max']}"
    ok(f"budget_max = {hc['budget_max']:,.0f} VND")

    assert hc["delivery_deadline_days"] == 14, f"deadline sai: {hc['delivery_deadline_days']}"
    ok(f"delivery_deadline_days = {hc['delivery_deadline_days']} ngày")

    # Soft constraints
    assert sc["material_preference"] is not None, "material_preference nên có giá trị"
    ok(f"material_preference = {sc['material_preference']!r}")

    assert sc["region_preference"] is not None, "region_preference nên có giá trị"
    ok(f"region_preference = {sc['region_preference']!r}")

    # Conversation history
    assert len(state1["conversation_history"]) == 1
    ok(f"conversation_history có {len(state1['conversation_history'])} turn")

except MissingFieldError as e:
    fail("MissingFieldError không mong muốn", str(e))
except AssertionError as e:
    fail("Assert thất bại", str(e))
except Exception as e:
    fail("Lỗi không mong muốn", str(e))

# ─────────────────────────────────────────────
# Test 2: parse_request — câu thiếu field
# ─────────────────────────────────────────────
section("2. parse_request() — câu thiếu field bắt buộc")
INPUT_2 = "Tôi muốn mua bàn làm việc gỗ tự nhiên."
try:
    parse_request(INPUT_2, session_id="sess_test02")
    fail("Phải raise MissingFieldError nhưng không raise")
except MissingFieldError as e:
    ok(f"MissingFieldError đúng: {e.missing_fields}")
except Exception as e:
    fail("Raise sai loại lỗi", f"{type(e).__name__}: {e}")

# ─────────────────────────────────────────────
# Test 3: parse_request — sản phẩm không hợp lệ
# ─────────────────────────────────────────────
section("3. parse_request() — sản phẩm không trong catalog")
INPUT_3 = "Tôi cần 10 máy lạnh, ngân sách 50 triệu, giao trong 7 ngày."
try:
    parse_request(INPUT_3, session_id="sess_test03")
    fail("Phải raise InvalidProductTypeError nhưng không raise")
except InvalidProductTypeError as e:
    ok(f"InvalidProductTypeError đúng: {e}")
except MissingFieldError as e:
    # Chấp nhận: LLM có thể không extract được product_type
    ok(f"MissingFieldError (cũng hợp lệ vì sản phẩm không được nhận dạng): {e.missing_fields}")
except Exception as e:
    fail("Raise sai loại lỗi", f"{type(e).__name__}: {e}")

# ─────────────────────────────────────────────
# Test 4: SQLite — save/load session roundtrip (doc lap LLM)
# ─────────────────────────────────────────────
section("4. SQLite — save_session / load_session roundtrip")

# Tao session mau truc tiep, khong phu thuoc LLM
TEST_STATE = {
    "session_id": "sess_test01",
    "created_at": "2026-09-10T00:00:00",
    "updated_at": "2026-09-10T00:00:00",
    "hard_constraints": {
        "product_type": "ghe van phong",
        "quantity": 50,
        "budget_max": 200000000.0,
        "delivery_deadline_days": 14,
    },
    "soft_constraints": {
        "material_preference": "go tu nhien",
        "region_preference": None,
        "min_trust_score": None,
    },
    "conversation_history": [],
    "decisions_made": [],
}
try:
    save_session("sess_test01", TEST_STATE)
    ok("save_session() khong loi")

    loaded = load_session("sess_test01")
    assert loaded is not None, "load_session() tra None"
    ok("load_session() tra dict")

    assert loaded["session_id"] == "sess_test01"
    ok(f"session_id khop: {loaded['session_id']}")

    assert loaded["hard_constraints"]["quantity"] == 50
    ok("quantity sau roundtrip = 50")

    assert session_exists("sess_test01")
    ok("session_exists() = True")

    assert not session_exists("sess_NOT_EXIST")
    ok("session_exists('khong ton tai') = False")

except Exception as e:
    fail("Loi SQLite roundtrip", str(e))

# Neu state1 co (LLM thanh cong), nen overwrite de verify roundtrip voi du lieu thuc
if state1:
    try:
        save_session(state1["session_id"], state1)
        loaded_real = load_session(state1["session_id"])
        assert loaded_real["hard_constraints"]["quantity"] == 50
        ok("Roundtrip voi state LLM that thanh cong")
    except Exception as e:
        fail("Roundtrip state LLM that bai", str(e))

# ─────────────────────────────────────────────
# Test 5: append/load conversation
# ─────────────────────────────────────────────
section("5. SQLite — append_conversation / load_conversation")
try:
    append_conversation("sess_test01", "agent", "Xin chào! Tôi có thể giúp gì cho bạn?")
    append_conversation("sess_test01", "user", "Tôi cần thêm thông tin về ghế da.")
    conv = load_conversation("sess_test01")

    assert len(conv) >= 2, f"Chỉ có {len(conv)} turn"
    ok(f"load_conversation() trả {len(conv)} turns")

    assert conv[-2]["role"] == "agent"
    ok(f"Turn -2: role=agent ✓")

    assert conv[-1]["role"] == "user"
    ok(f"Turn -1: role=user ✓")

except Exception as e:
    fail("Lỗi conversation", str(e))

# ─────────────────────────────────────────────
# Test 6: save/load decisions
# ─────────────────────────────────────────────
section("6. SQLite — save_decision / load_decisions")
try:
    save_decision("sess_test01", "NCC001")
    decisions = load_decisions("sess_test01")
    assert len(decisions) >= 1
    ok(f"Có {len(decisions)} quyết định")
    assert decisions[-1]["supplier_id"] == "NCC001"
    ok("supplier_id = NCC001 ✓")
except Exception as e:
    fail("Lỗi decisions", str(e))

# ─────────────────────────────────────────────
# Test 7: update_state — ghi đè đúng field
# ─────────────────────────────────────────────
section("7. update_state() — đổi số lượng, giữ nguyên field khác")
if state1:
    UPDATE_TEXT = "À, đổi lại số lượng thành 80 cái thôi."
    try:
        updated = update_state(state1, UPDATE_TEXT)
        assert updated["hard_constraints"]["quantity"] == 80, f"quantity không đổi: {updated['hard_constraints']['quantity']}"
        ok(f"quantity sau update = {updated['hard_constraints']['quantity']} ✓")

        # Budget không được thay đổi
        assert updated["hard_constraints"]["budget_max"] == state1["hard_constraints"]["budget_max"]
        ok("budget_max giữ nguyên ✓")

        # Conversation history phải có thêm 1 turn
        assert len(updated["conversation_history"]) == len(state1["conversation_history"]) + 1
        ok(f"conversation_history tăng thêm 1 turn ✓")

    except AssertionError as e:
        fail("update_state() assert thất bại", str(e))
    except Exception as e:
        fail("update_state() lỗi", str(e))
else:
    fail("Bỏ qua test 7 vì state1 chưa có")

# ─────────────────────────────────────────────
# Tổng kết
# ─────────────────────────────────────────────
total = passed + failed
print(f"\n{'='*40}")
print(f"{BOLD}Ket qua: {GREEN}{passed}{RESET}{BOLD}/{total} tests passed{RESET}")
if failed:
    print(f"{RED}         {failed} tests FAILED{RESET}")
print(f"{'='*40}")

sys.exit(0 if failed == 0 else 1)
