# Phản hồi của Người C cho `RESPONSE-B-MERGE-NOTES-2026-09-17.md`

Người viết: Người C (qua Claude Code). Ngày: 2026-09-17.

## 1. Việc B giao cho C — cả 2 đã xong

- **`RECURSION_LIMIT`**: đổi từ hardcode `25` sang công thức
  `6 * (MAX_REPLAN + 1) + 16 = 40`, bám theo đường lặp dài nhất thật của graph
  (`tool_search → filter_hard → score_rank → verify_output → diagnose → replan`).
  Đã tái hiện đúng case B báo lỗi (ngân sách bất khả thi): trước fix
  `GraphRecursionError` ở mức 25, sau fix chạy hết vòng lặp, kết thúc `graceful_fail`
  đúng ý đồ, `replan_count=3`.
- **`replan_reason`**: thêm vào `AgentState` — trước đây `diagnose()` đã trả field này
  đúng hợp đồng nhưng state không khai báo nên bị rơi mất khỏi audit trail.
- Commit `e449506`, đã push lên `origin/role-c-implementation`.
- Kiểm tra riêng: `tests.test_reasoning_nodes`, `test_planner`, `test_verification`,
  `test_graph_routing`, `test_graph_e2e_stub` — **41/41 pass**, không có gì trong phần
  Reasoning/scoring của B bị ảnh hưởng bởi 2 fix trên.

## 2. Tin tốt ngoài dự kiến — supplier ID contract tự giải quyết

Sau khi merge nhánh `hien` (`b0dd6cf`, A wire `perceive` thật):
[`src/nodes/perceive.py:41-42`](src/nodes/perceive.py#L41) tự map
`target_supplier_ids` từ `supplier_ids` mà parser trả về. Không cần B/A/C họp chốt tên
field nữa — nhánh `compare_specific`/`supplier_detail` không còn vướng chỗ này.

## 3. Bug mới chặn việc B nhờ ở mục 5.4 (chạy lại E2E/AutoEval)

Sau merge: **237 test, 2 error** (không liên quan phần B — xác nhận ở mục 1). Lỗi:

```
GoogleModelNotFoundError: Error calling model 'gemini-2.5-flash' (NOT_FOUND)
This model models/gemini-2.5-flash is no longer available... use models/gemini-3.6-flash
```

Xảy ra kể cả khi set `AGENT_LLM=stub`. Nguyên nhân: `src/perception/parser.py` (A) tự
khai báo `ChatGoogleGenerativeAI` riêng với model cũ, không dùng chung
`get_llm()`/`MODEL_NAME` của `src/llm.py` (đã đúng `gemini-3.6-flash`, đã hỗ trợ stub).
Đã ping A sửa (`STATUS-UPDATE-C-2026-09-17.md` mục 5.2), C không tự sửa file của A.

**Ảnh hưởng tới B:** mục 5.4 trong note của B ("chạy lại E2E cho 4 intent, AutoEval,
load test") **chưa chạy được với `perceive` thật** cho tới khi A fix bug này — bất kỳ
request nào đi qua `perceive` thật đều crash ở bước gọi LLM, không phải do reasoning/
scoring của B.

## 4. Việc vẫn đang chờ (không đổi so với note trước)

- **Memory trong graph:** A chưa chốt semantics (khi nào load session cũ, khi nào dùng
  `update_state` vs `parse_request`) → C chưa nối được `src/memory/db.py` vào
  `run_request()`.
- **Task 10 — data nguồn thật (`sources.csv`):** vẫn chưa ai nhận, đúng như B nêu ở
  mục 6. C đang crawl thử (`scripts/crawl_sources_draft.py`,
  `src/tools/mock_data/sources_draft.csv`, chưa commit, chưa đạt target 50-55 record) —
  chưa phải là câu trả lời cho yêu cầu "thu thập tay dữ liệu thật" của B, cần B+C bàn
  thêm ai làm phần đối chiếu nguồn/URL thật.

## 5. Tóm tắt cho B

Phần B giao cho C: **xong cả 2, đã push**. Việc B tự làm (reasoning nodes) không bị ảnh
hưởng gì bởi merge hay 2 fix trên. Việc B muốn làm tiếp (rerun E2E/AutoEval) đang bị chặn
bởi bug model-name trong `parser.py` (A), không phải lỗi từ phía B hay C.

---

## 6. Cập nhật — đã chốt quyết định thiết kế mục 4 (phần C) và implement

Đã xác nhận lại kỹ thuật claim #3 của B (StubLLM không có `.bind()`, trả prose chứ
không phải JSON) — **đúng**, đọc thẳng code xác nhận.

**Chọn Option 1** (khuyến nghị của B): mở rộng `src/llm.py` thay vì để runner override
node `perceive` bằng fixture — vì override sẽ làm mất luôn phần latency giả lập cho
bước LLM #1 mà load test đang cần đo (`STUB_LATENCY_MEAN_S` trong `llm.py` được hiệu
chỉnh từ số đo thật, dùng cho cả hai LLM call chứ không riêng `respond`).

**Đã làm** (commit `84e941b`, đã push):

- `StubLLM.bind(**kwargs)` — trả về biến thể `_StubPerceptionLLM` thay vì `self`
  (không đổi hành vi stub cũ dùng cho `respond`).
- `_StubPerceptionLLM._message()` trả `AIMessage` với `content` là JSON cố định đúng 10
  field mà `_EXTRACT_SYSTEM_PROMPT`/`_UPDATE_SYSTEM_PROMPT` của `parser.py` yêu cầu
  (`intent`, `product_type`, `quantity`, `budget_max`, `delivery_deadline_days`,
  `material_preference`, `region_preference`, `min_trust_score`, `supplier_ids`,
  `supplier_id`) — giá trị mặc định giữ nguyên bộ 4 hard constraint cũ (`ghế văn phòng`,
  50, 200 triệu, 14 ngày) để không đổi baseline AutoEval `--llm stub` hiện có.
- Test mới trong `tests/test_llm_factory.py` (4 test, tổng suite giờ 241 test).
- **Đã verify thật**, không chỉ đoán: monkeypatch `parser._get_llm = get_llm` rồi chạy
  `parse_request()` + `update_state()` dưới `AGENT_LLM=stub` — chạy hết, không crash.

**Lưu ý quan trọng — chưa hết chặn:** đây mới chỉ mở khóa phía `llm.py`. `parser.py` vẫn
tự khai báo `_get_llm()`/`LLM_MODEL_NAME` riêng, chưa gọi `src.llm.get_llm()`. Full suite
hiện tại vẫn **241 test, 2 error** giống hệt 2 lỗi cũ (`test_node_stubs.py` gọi API thật)
— đúng như dự đoán, vì phần còn thiếu là của A (đã ping ở `STATUS-UPDATE-C-2026-09-17.md`
mục 5.2, giờ bổ sung rõ: A chỉ cần đổi `_get_llm()` → `get_llm()` và xoá
`LLM_MODEL_NAME`/client riêng, `.bind()` giờ đã có sẵn ở phía C, không cần A tự viết gì
thêm cho JSON mode).

**Stub JSON có phản ánh đúng nội dung user_input không?** Không — stub trả cố định bất kể
input, giống triết lý stub hiện có của `respond`. Đây là giới hạn đã biết, không phải
bug: `--llm stub` đo chi phí/latency pipeline, `--llm real` mới đo đúng chất lượng
Perception. B nên giữ nguyên khuyến nghị "strict verifier, không tắt gate" ở mục 6 note
trước — không liên quan tới thay đổi này.

**Việc chưa làm (ngoài scope quyết định này):** `interface-contracts.md` §1 (state
schema) chưa liệt kê `intent`, `supplier_ids`, `supplier_id` — field A đang trả thật
trong `req`. Không sửa vì đây là tài liệu A sở hữu, chỉ ghi nhận để A/B biết khi nào
tiện thì cập nhật, tránh lặp lại kiểu lệch hợp đồng đã từng gây vụ merge 13/9.
