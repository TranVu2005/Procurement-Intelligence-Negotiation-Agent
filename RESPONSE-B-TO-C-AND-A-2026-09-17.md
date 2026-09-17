# Phản hồi của Người B cho cập nhật A/C ngày 2026-09-17

**Người phản hồi:** Người B — Reasoning & Planning  
**Đã kiểm tra trên:** `origin/role-c-implementation@a00ea42`

## 1. Xác nhận phần C đã hoàn thành đúng

B đã merge branch C vào local để kiểm tra độc lập và xác nhận:

- `RECURSION_LIMIT` mới đủ cho đường lặp ba lần re-plan;
- `replan_reason` đã có trong `AgentState`;
- mapping `supplier_ids` sang `target_supplier_ids` trong node Perception đã giải
  quyết mismatch contract cho `compare_specific`/`supplier_detail`;
- phần Reasoning của B không bị regression.

Kết quả chạy lại nhóm test Reasoning/Graph: **41/41 pass**. Compile toàn bộ `src` và
`tests` cũng pass.

## 2. Xác nhận blocker parser của A

Khi đặt `AGENT_LLM=stub`, hai test gọi `perceive()` thật vẫn lỗi vì
`src/perception/parser.py` dùng client riêng và yêu cầu `GOOGLE_API_KEY`.

Lỗi tái hiện:

```text
OSError: GOOGLE_API_KEY chưa được set
```

Vì vậy chưa nên merge toàn bộ `role-c-implementation` vào `main`; branch hiện có
**237 test, 2 error** ở Perception.

## 3. Lưu ý: chỉ đổi sang `src.llm.get_llm()` vẫn chưa đủ

`parser.py` hiện gọi:

```python
_get_llm().bind(response_format={"type": "json_object"}).invoke(...)
json.loads(response.content)
```

Nhưng `src.llm.StubLLM` hiện:

- không có phương thức `bind()`;
- trả câu văn cố định `[STUB] ...`, không phải JSON;
- không thể cung cấp output phù hợp cho `json.loads()`.

Do đó, nếu A chỉ thay `_get_llm()` bằng `get_llm()`, lỗi API key sẽ biến thành lỗi
`AttributeError` hoặc `JSONDecodeError`. AutoEval và load test đều gọi `run_request()`
thật với `AGENT_LLM=stub`, nên đây không chỉ là vấn đề của unit test.

## 4. Yêu cầu A và C chốt cách sửa hoàn chỉnh

### Phần A

1. Parser phải dùng model/config chung từ `src.llm`; bỏ model name và client factory
   riêng trong `parser.py`.
2. Unit test của `perceive` phải mock `_call_llm()`/`parse_request()` với JSON có kiểm
   soát, không được gọi mạng.
3. Test real-model riêng phải được đánh dấu integration và chỉ chạy khi có API key.

### Phần C

Chọn một trong hai thiết kế cho offline AutoEval/load test:

1. **Khuyến nghị:** mở rộng LLM factory để có Perception stub trả JSON theo contract;
   node `respond` tiếp tục dùng text stub hiện tại.
2. Hoặc runner truyền override cho node `perceive` bằng deterministic fixture; phải
   công khai rằng load test đo graph/tool/reasoning, không đo chất lượng Perception.

Không nên dùng một text stub duy nhất cho cả parser JSON và response prose.

## 5. Điều kiện nghiệm thu trước khi merge vào `main`

- `AGENT_LLM=stub python -m unittest discover -s tests -q` pass toàn bộ;
- `AGENT_LLM=stub python -m scripts.run_autoeval` không gọi mạng và không lỗi parse
  JSON;
- load test stub không yêu cầu `GOOGLE_API_KEY`;
- chạy smoke test đủ bốn intent;
- real-model smoke test dùng model duy nhất từ `src.llm.MODEL_NAME`.

## 6. Các việc còn lại

- Memory trong graph: vẫn chờ A chốt semantics rồi C nối.
- Task 10 dữ liệu nguồn: vẫn cần người nhận và đối chiếu URL thật.
- Phần B: không có code cần sửa thêm ở thời điểm này; 41/41 test liên quan đều pass.

## 7. Quyết định tích hợp của B

B đã lấy code mới về local để kiểm tra nhưng **chưa push lên `main`** vì full suite
còn hai error. Khi A/C hoàn thành Perception stub contract và toàn bộ test xanh, B có
thể kiểm tra lại rồi fast-forward/merge lên `main`.
