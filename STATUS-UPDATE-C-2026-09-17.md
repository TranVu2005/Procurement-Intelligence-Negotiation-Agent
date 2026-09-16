# Cập nhật tình trạng từ Người C — 2026-09-17

Người viết: Người C (qua Claude Code). Gửi A và B để nắm tình trạng sau khi C đồng bộ
branch với `main` và hoàn thành 2 việc B giao trong `RESPONSE-B-MERGE-NOTES-2026-09-17.md`.

## 1. Đã làm

- Merge `main` (`d445a2a`, có phần Reasoning thật của B) vào `role-c-implementation` —
  không conflict, vì 6 commit của B/A và 9 commit crawl-data của C không đụng file nhau.
- Hoàn thành 2 việc B giao cho C:
  - **`RECURSION_LIMIT`**: đổi từ hardcode `25` sang công thức
    `6 * (MAX_REPLAN + 1) + 16 = 40`, bám theo đường lặp dài nhất thật của graph
    (`tool_search → filter_hard → score_rank → verify_output → diagnose → replan`).
    Đã tái hiện đúng case B báo lỗi (ngân sách bất khả thi) — trước đây
    `GraphRecursionError` ở mức 25, giờ chạy hết vòng lặp, kết thúc `graceful_fail`
    đúng ý đồ.
  - **`replan_reason`**: thêm vào `AgentState` (trước đây `diagnose()` đã trả field này
    theo hợp đồng nhưng state không khai báo → bị rơi mất khỏi audit trail).
  - Commit `e449506`, đã push lên `origin/role-c-implementation`.
- Test suite sau khi merge + fix: **237/237 pass**.

## 2. Đã tự kiểm tra lại — xác nhận 2 blocker cũ vẫn còn

Không chỉ đọc note, C đã chạy `run_request()` thật để verify:

- Input `"So sanh gia may bay Ha Noi Sai Gon"` (rõ ràng ngoài phạm vi hệ thống) vẫn bị
  nhận `intent=search_new` — xác nhận `src/nodes/perceive.py` **vẫn còn
  `perceive.__stub__ = True`**, chưa gọi `parser.py` thật. (A đã nhận task này,
  deadline 19/9 — ping này chỉ để xác nhận trạng thái hiện tại, không thúc deadline.)
- `src/graph.py` vẫn chưa `import` gì từ `src/memory` — memory chưa nối vào
  `run_request()`, đúng như B ghi nhận.

## 3. Vẫn đang chờ / cần quyết định

- **Supplier ID contract (A + C):** `src/perception/parser.py` trả `supplier_ids` /
  `supplier_id`, còn `src/nodes/tools.py` (`tool_compare`, `tool_detail`) đọc
  `target_supplier_ids`. Hai nhánh `compare_specific` / `supplier_detail` sẽ không chạy
  end-to-end được cho tới khi hai bên chọn 1 tên field và cập nhật
  `interface-contracts.md`.
- **Memory semantics (A → C):** cần A chốt khi nào load session cũ, khi nào dùng
  `update_state()` thay vì `parse_request()`, lưu gì mỗi lượt — C mới nối được vào
  `run_request()`.
- **Task 10 — data nguồn thật (`sources.csv`):** vẫn chưa ai nhận. C đang có
  `scripts/crawl_sources_draft.py` + `src/tools/mock_data/sources_draft.csv` làm dở
  (chưa commit, chưa đạt target 50-55 record), nhưng đây là việc riêng của C, không
  thay thế yêu cầu "thu thập tay dữ liệu thật" mà B nhắc trong note trước.

## 4. Kết luận tại thời điểm viết mục 1-3

Pipeline kỹ thuật (graph/tools/reasoning) đã chạy được end-to-end với dữ liệu giả ở
perceive. Chưa gọi là MVP chạy thật được vì thiếu đầu vào thật (perceive) — mọi câu trả
lời hiện tại không phản ánh đúng yêu cầu người dùng nhập vào. Mốc tiếp theo: A xong
perceive (19/9) + A/C chốt supplier ID contract.

---

## 5. Cập nhật cùng ngày — sau khi merge nhánh `hien` (`b0dd6cf`)

A đã push `feat(perception): wire perceive node to parser.py real impl + resolve merge
conflicts`. C đã merge vào `role-c-implementation` (commit `05fa69b`) và chạy lại test.

### 5.1 Tin tốt — supplier ID contract đã tự giải quyết

[`src/nodes/perceive.py:41-42`](src/nodes/perceive.py#L41) giờ tự map:

```python
if intent in ("compare_specific", "supplier_detail"):
    req.setdefault("target_supplier_ids", req.get("supplier_ids") or [])
```

Không cần A/C họp chốt tên field nữa — mục 3 (supplier ID contract) trong note trước coi
như **đã xong**.

### 5.2 Bug mới — `parser.py` không dùng chung LLM factory, gọi thẳng API thật kể cả khi bật stub

Sau merge: **237 test, 2 error** (không phải PASS như A báo trong
`MERGE-RESPONSE-2026-09-17.md`, có thể do A test trên máy có sẵn stub/mock khác, hoặc
model `gemini-3.6-flash` mới bị Google chặn sau khi A test). Lỗi:

```
GoogleModelNotFoundError: Error calling model 'gemini-2.5-flash' (NOT_FOUND)
This model models/gemini-2.5-flash is no longer available... use models/gemini-3.6-flash
```

Đã xác minh cả khi set `AGENT_LLM=stub` — vẫn lỗi y hệt. Nguyên nhân:
[`src/perception/parser.py:51,54-62`](src/perception/parser.py#L51) tự khai báo client
`ChatGoogleGenerativeAI` riêng:

```python
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")

def _get_llm() -> ChatGoogleGenerativeAI:
    ...
```

thay vì import `get_llm()` / `MODEL_NAME` từ [`src/llm.py`](src/llm.py) (nhà máy LLM dùng
chung của C, đã đúng `gemini-3.6-flash` và đã hỗ trợ `AGENT_LLM=stub`). Đây đúng là điều
Task 2 của plan role-c-implementation đã cảnh báo trước khi A viết `parser.py`
("architecture.md §3.1 — hiện hai file đang lệch tên model"), nhưng chưa được nối.

Hệ quả: `tests/test_node_stubs.py` (và bất kỳ test nào chạy `perceive` thật) hiện **gọi
thẳng API Google thật**, tốn quota, cần mạng, và không tôn trọng cờ `AGENT_LLM=stub` dùng
cho load test/CI.

**C không tự sửa `parser.py`** (thuộc `src/perception/`, phần A). Cần A đổi `_get_llm()`
trong `parser.py` sang gọi `from src.llm import get_llm, MODEL_NAME` thay vì tự khai báo
`ChatGoogleGenerativeAI` + `LLM_MODEL_NAME` riêng.

### 5.3 Trạng thái test hiện tại

**237 test, 2 error** (mục 5.2), không còn lỗi nào khác. Không phải regression từ merge —
lỗi có sẵn trong code A vừa push, chỉ lộ ra khi C chạy full suite không stub LLM ở tầng
parser.

### 5.4 Kết luận cập nhật

- Supplier ID contract: xong, không cần A/C họp nữa (mục 5.1).
- Memory semantics + inject vào `graph.py`: vẫn chờ A (mục 3, chưa đổi).
- Task 10 (data nguồn thật): vẫn chưa ai nhận (mục 3, chưa đổi).
- **Blocker mới trước khi chạy MVP thật:** A nối `parser.py` vào `src/llm.py` chung
  (mục 5.2) — nếu không, mọi lần chạy `perceive` thật đều crash vì model bị Google khai tử.
