# Ghi chú sau khi merge role-c-implementation + hien + linh vào main (2026-09-16)

Người viết: Nguoi C (qua Claude Code). Mục đích: liệt kê các vấn đề phát sinh/còn tồn
đọng sau đợt merge để A và B nắm và quyết định hướng xử lý. Không có vấn đề nào trong
danh sách này bị tự sửa một chiều — chỉ ghi nhận.

## 1. Node LangGraph vẫn chạy DATA GIẢ dù module logic thật đã có

Đây là vấn đề quan trọng nhất: pipeline thật (`python -m src.agent`, `run_request()`)
hiện tại **không** dùng logic thật của A và B, dù code thật đã nằm trong `main`.

- **`src/nodes/perceive.py`** — vẫn `perceive.__stub__ = True`. Luôn trả cứng
  `intent="search_new"`, `product_type="ghế văn phòng"`, `quantity=50`,
  `budget_max=200_000_000`, `delivery_deadline_days=14`, bất kể input thật của người
  dùng là gì. Không gọi LLM (dù vẫn báo `llm_calls: 1` — số liệu ảo).
  `src/perception/parser.py` (A) đã có đủ extract/validate/multi-turn nhưng **chưa được
  node gọi tới**.
- **`src/nodes/reasoning.py`** — `plan`, `filter_hard`, `score_rank`, `verify_output`,
  `diagnose`, `replan` đều còn `__stub__ = True`.
  - `score_rank` chỉ pass-through candidates, **không gọi** `rank_suppliers()` /
    `generate_negotiation_strategy()` trong `src/reasoning/scoring.py` (B) — nghĩa là
    leverage score và chiến lược đàm phán (yêu cầu bắt buộc của đề bài §1.5) **chưa chạy
    được end-to-end**.
  - `plan` chưa gọi `src/reasoning/planner.py` thật (bản mới nhất nằm trong nhánh
    `linh`/`hien` vừa merge).
  - `verify_output` luôn trả `passed: True, claims: []` — Citation/Evidence Correctness
    của AutoEval sẽ luôn rỗng cho tới khi verify thật được nối.

**Cần A và B:** thay ruột từng hàm trong 2 file trên, gọi đúng vào
`src/perception/parser.py`, `src/reasoning/planner.py`, `src/reasoning/scoring.py`, rồi
xóa dòng `__stub__` tương ứng. Giữ đúng chữ ký/khóa trả về đã ghi trong docstring từng
hàm — `src/graph.py` và toàn bộ test node (`tests/test_node_stubs.py`,
`tests/test_graph_e2e_stub.py`, `tests/test_graph_routing.py`) đang dựa vào đúng các khóa
đó.

## 2. `src/memory/db.py` (A, đã có code thật) chưa được nối vào graph

`graph.py` không import `src/memory`. `src/agent.py` chỉ gọi `init_db()` một lần lúc
khởi động REPL rồi không dùng gì thêm — session/state không được lưu SQLite trong luồng
`run_request()` thật, nên multi-turn qua nhiều lần gọi hiện không có bộ nhớ thật.

## 3. `test_integration_ab.py` — "Decision 1" giờ là 2 lỗi thay vì 1

Trước merge, CLAUDE.md ghi nhận 1 lỗi đã biết (tranh chấp `material`/`region` có nằm
trong params của `make_plan` hay không). Sau khi merge nhánh `linh` (planner.py thật đã
code theo hướng loại `material` khỏi params — khớp với ghi chú trong
`src/nodes/reasoning.py::filter_hard` rằng material/region là soft constraint), số lỗi
tăng lên 2 (1 fail + 1 error), cùng gốc:

```
FAIL  test_happy_path_full_state — assertIn("material", step["params"]) thất bại
ERROR test_state_without_soft_constraints_still_makes_plan — KeyError: 'material'
```

**Cần A và B:** chốt Decision 1 (architecture.md §8) rồi cập nhật lại
`tests/test_integration_ab.py` cho khớp hướng đã chọn. Không tự sửa vì đây là tranh chấp
hợp đồng giữa 2 module, không phải bug một bên.

## 4. Conflict đã resolve khi merge — cần A/B xác nhận lại

- **`src/agent.py`** (conflict giữa `role-c-implementation` và `hien`): giữ bản
  `role-c-implementation` — gọi `init_db()`, `render()` in kèm `trace_id`/`latency_ms`,
  bỏ nhánh fallback stub `run_request` (không cần nữa vì `src/graph.py` đã tồn tại thật).
  Nếu `hien` có ý đồ khác với `src/agent.py`, cần nói lại vì C là owner file này theo
  bảng phân quyền CLAUDE.md.
- **`tests/eval_set/cases.jsonl`** (conflict giữa `hien` và `linh`): hai bên rẽ nhánh từ
  chung tổ tiên rồi thêm case khác nhau, trùng ID `case_009`–`case_012` nhưng nội dung
  khác. Đã **union cả hai**, giữ `case_001`–`015` (bản có field `category`, case về
  memory/multi-turn) và đánh số lại case về reasoning (`diagnose`/`verify`/`plan`) của
  `linh` từ `009`–`012` thành `016`–`019` để không mất dữ liệu test của ai. Nhờ A/B rà lại
  xem nội dung case có còn đúng ý đồ gốc không (đặc biệt field `category` mới thêm cho
  4 case đó — tôi tự suy đoán `happy_path`/`conflict`, có thể sai).

## 5. Việc khác cần A và B biết (chưa phải lỗi, chỉ là thông báo)

- `MODEL_NAME` trong `src/llm.py` đã đổi từ `gemini-2.5-flash` (Google ngừng hỗ trợ)
  sang `gemini-3.6-flash`.
- Node `perceive` thật (A viết) cần đọc `req["target_supplier_ids"]` khi
  `intent` là `compare_specific`/`supplier_detail` — `tool_compare`/`tool_detail`
  (C) đã yêu cầu field này.
- `filter_hard` thật (B viết) **bắt buộc giữ** nhánh ngoại lệ: khi
  `intent == "supplier_detail"`, bỏ qua `filter_hard_constraints()` — nếu không, mọi
  record sẽ bị loại vì thiếu `total_price` và vòng re-plan sẽ chạy vô ích tới khi chạm
  trần 3 lần.
- `src/tools/supplier_tools.py` (C) đã có sẵn 4 field nguồn gốc dữ liệu trên mỗi record:
  `nguon_url`, `nguon_type`, `fetched_at`, `simulated_fields` — `score_rank`/
  `verify_output` thật nên dùng các field này để dựng `verdict.claims` (Citation/Evidence
  Correctness).
- **Task 10** (thu thập tay dữ liệu nhà cung cấp thật cho `sources.csv` +
  `generate_mock_data.py`) vẫn đang **bị bỏ qua có chủ đích** theo yêu cầu trước đó — chưa
  ai làm. Cần quyết định ai làm và khi nào.

## 6. Trạng thái test hiện tại

231 test, 2 fail (mục 3 ở trên, cùng 1 nguyên nhân, không phải lỗi mới do merge gây ra
ngoài dự kiến — là hệ quả trực tiếp của việc `linh` đã code thật phần đang tranh chấp).
