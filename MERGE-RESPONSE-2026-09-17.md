# Response của A (hien) — MERGE-NOTES-2026-09-16

Người viết: A (hien). Ngày: 2026-09-17.  
Viết sau khi đã pull `main` → merge vào nhánh `hien`, kiểm tra code thực tế,
và thực hiện xong toàn bộ action items thuộc phần A.

---

## Trạng thái sau merge

Merge `origin/main` vào `hien` thành công (fast-forward, 46 files, +7784 dòng).  
Kết quả test cuối: **34 passed, 0 failed** ✅

---

## Mục 1 — Node LangGraph vẫn dùng stub

### ✅ ĐÃ XỬ LÝ — `src/nodes/perceive.py`

Đã wire `perceive` node vào `src/perception/parser.py` thật:

- **Xóa** `perceive.__stub__ = True` (dòng 41 cũ).
- Gọi `parse_request()` ở turn đầu; gọi `update_state()` ở các turn tiếp theo
  (multi-turn detection qua `conversation_history`).
- Xử lý `req["target_supplier_ids"]` cho intent `compare_specific` /
  `supplier_detail` — lấy từ `supplier_ids` mà parser trả về,
  khớp với `tools.py` dòng 128 và 161 của C.
- Giữ nguyên chữ ký trả về: `intent`, `req`, `llm_calls`, `tokens_in`, `tokens_out`.

**`reasoning.py` vẫn còn stub** — là phần của B, A không chạm.

---

## Mục 2 — `src/memory/db.py` chưa được nối vào graph

### ⏳ Chờ thống nhất với C

`src/agent.py` đã có `init_db()` (dòng 23, 48). `graph.py` chưa import memory.  
Sẽ liên hệ C để chốt điểm inject trong `graph.py` trước khi chỉnh.
C là owner `graph.py` — không tự sửa một chiều.

---

## Mục 3 — Decision 1

### ✅ ĐÃ XỬ LÝ — `tests/test_integration_ab.py`

**Chốt Decision 1:** `material` và `region` là soft constraint,
**không** nằm trong `params` của `make_plan` — theo đúng hướng `linh` đã code.

Đã sửa 2 assertion fail:

| Dòng cũ | Assertion cũ (FAIL) | Assertion mới (PASS) |
|---------|---------------------|----------------------|
| 99 | `assertIn("material", step["params"])` | `assertNotIn("material", step["params"])` + kiểm tra `state["soft_constraints"]` |
| 100 | `assertIn("region", step["params"])` | `assertNotIn("region", step["params"])` |
| 108 | `assertIsNone(step["params"]["material"])` → KeyError | `assertNotIn("material", step["params"])` + kiểm tra `soft_constraints` |
| 109 | `assertIsNone(step["params"]["region"])` → KeyError | `assertNotIn("region", step["params"])` |

---

## Mục 4 — Xác nhận conflict đã resolve

### ✅ `src/agent.py`

Đã xem lại bản C giữ. Đồng ý — không cần can thiệp.

### ⏳ `tests/eval_set/cases.jsonl`

Chưa rà lại. Sẽ làm trước 2026-09-19.

---

## Mục 5 — Ghi nhận thực tế

| # | Ghi nhận | Trạng thái |
|---|----------|-----------|
| 5a | `MODEL_NAME` → `gemini-3.6-flash` | ✅ Biết rồi |
| 5b | `perceive` cần `req["target_supplier_ids"]` cho `compare_specific`/`supplier_detail` | ✅ **Đã xử lý** trong wire perceive |
| 5c | `filter_hard` giữ nhánh ngoại lệ `intent == "supplier_detail"` (dòng 46–47) | ✅ Code đã có sẵn — **B giữ khi wire thật** |
| 5d | `score_rank`/`verify_output` dùng 4 field nguồn gốc để dựng `verdict.claims` | 📌 Phần của B |
| 5e | **Task 10** chưa ai nhận | ❓ Cần C + B quyết định |

---

## Mục 6 — Trạng thái test sau khi A xử lý

> **34 passed, 0 failed** ✅

Bao gồm cả việc cập nhật `tests/test_node_stubs.py`:
- Đánh dấu `perceive` là done (không còn stub).
- Đổi `test_perceive_stub_sets_intent_and_req` → `test_perceive_returns_correct_shape`
  để kiểm tra shape thay vì giá trị hardcode (node thật gọi LLM, không cần giá trị cố định).

---

## Action items của A — trạng thái cuối

| Priority | Task | Trạng thái |
|----------|------|-----------|
| 🔴 P0 | Wire `perceive` node → `parser.py` thật, xóa stub, xử lý `target_supplier_ids` | ✅ Xong |
| 🔴 P0 | Sửa 2 assertion fail trong `test_integration_ab.py` (Decision 1) | ✅ Xong |
| 🟠 P1 | Thống nhất với C điểm inject `memory/db.py` vào `run_request()` | ⏳ Chờ C |
| 🟠 P1 | Rà lại `cases.jsonl` — xác nhận category labels | ⏳ Deadline 2026-09-19 |
