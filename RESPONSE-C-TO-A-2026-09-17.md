# Phản hồi của Người C cho A — 2026-09-17

Người viết: Người C (qua Claude Code). Đã kiểm tra trên `origin/role-c-implementation@da80c11`.

## 1. Xác nhận việc A đã làm — tốt

- Merge `b0dd6cf` (`feat(perception): wire perceive node to parser.py real impl`) đã
  được C merge vào `role-c-implementation`, không conflict với phần C.
- **Supplier ID contract tự giải quyết:** [`src/nodes/perceive.py:41-42`](src/nodes/perceive.py#L41)
  tự map `target_supplier_ids` từ `supplier_ids` mà parser trả về. Không cần họp chốt
  tên field nữa — nhánh `compare_specific`/`supplier_detail` hết vướng chỗ này.

## 2. Blocker còn lại — chỉ còn 1 việc nhỏ ở `parser.py`

Sau merge, full suite: **241 test, 2 error**, cả 2 đều ở `tests/test_node_stubs.py` khi
gọi `perceive()` thật:

```
GoogleModelNotFoundError: Error calling model 'gemini-2.5-flash' (NOT_FOUND)
This model models/gemini-2.5-flash is no longer available... use models/gemini-3.6-flash
```

Xảy ra **kể cả khi set `AGENT_LLM=stub`** — vì [`src/perception/parser.py:51,54-66`](src/perception/parser.py#L51)
tự khai báo `LLM_MODEL_NAME`/`_get_llm()`/`ChatGoogleGenerativeAI` riêng, không đọc
`AGENT_LLM` và không dùng `src/llm.py` (nhà máy LLM chung, C sở hữu, đã đúng
`gemini-3.6-flash`). Đây đúng là điều Task 2 của plan role-c-implementation đã cảnh báo
trước khi viết `parser.py` (architecture.md §3.1 — "hai file đang lệch tên model"),
nhưng chưa được nối.

## 3. C đã dọn sẵn đường — A chỉ cần đổi 1 chỗ

B chỉ ra thêm: đổi mỗi `_get_llm()` → `get_llm()` là chưa đủ, vì `parser.py` gọi
`_get_llm().bind(response_format={"type": "json_object"}).invoke(...)` mà `StubLLM` cũ
không có `.bind()` và trả prose chứ không phải JSON — đổi xong sẽ crash kiểu khác
(`AttributeError`/`JSONDecodeError`) khi chạy `AGENT_LLM=stub`.

C đã sửa xong phần này (commit `84e941b`, đã push):

- `StubLLM.bind(**kwargs)` — trả về biến thể trả JSON đúng 10 field mà
  `_EXTRACT_SYSTEM_PROMPT`/`_UPDATE_SYSTEM_PROMPT` của `parser.py` cần
  (`intent`, `product_type`, `quantity`, `budget_max`, `delivery_deadline_days`,
  `material_preference`, `region_preference`, `min_trust_score`, `supplier_ids`,
  `supplier_id`).
- Đã verify bằng monkeypatch `parser._get_llm = get_llm` rồi chạy `parse_request()` +
  `update_state()` dưới `AGENT_LLM=stub` — chạy hết, không crash.

**Việc A cần làm, chỉ còn:**

1. Trong `src/perception/parser.py`: xoá `LLM_MODEL_NAME` và `_get_llm()` tự khai báo.
2. Thay bằng `from src.llm import get_llm, MODEL_NAME`, gọi `get_llm()` ở chỗ
   `_call_llm()` đang gọi `_get_llm()`.
3. Không cần viết gì thêm cho nhánh stub/JSON — `.bind()` đã có sẵn ở `src/llm.py`, tự
   hoạt động đúng.
4. Chạy lại `AGENT_LLM=stub python -m unittest discover tests "test_*.py"` — kỳ vọng
   241/241 pass.

## 4. Lưu ý nhỏ — không cần làm ngay, chỉ để A biết

`interface-contracts.md` §1 (state schema, A sở hữu) chưa liệt kê `intent`,
`supplier_ids`, `supplier_id` — 3 field parser đang thực sự trả về trong `req`. C không
tự sửa vì đây là tài liệu của A, chỉ ghi nhận để tránh lặp lại kiểu lệch hợp đồng đã gây
vụ merge 13/9. Tiện lúc nào cập nhật thì cập nhật, không chặn việc gì hiện tại.

## 5. Việc vẫn chờ A (không đổi)

- Chốt semantics memory (khi nào load session cũ, khi nào dùng `update_state()` thay vì
  `parse_request()`, lưu gì mỗi lượt) để C nối `src/memory/db.py` vào `run_request()`.
