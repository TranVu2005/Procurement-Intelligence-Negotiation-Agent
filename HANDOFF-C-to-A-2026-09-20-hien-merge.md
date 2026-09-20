# Bàn giao C → A — 2026-09-20: lỗi merge nhánh `hien`

**Người viết:** Người C
**Commit hiện tại trên `main`:** `67f0352` (đã có `linh`, chưa có `hien`)
**Mục đích:** báo lỗi phát hiện khi thử merge `hien` vào `main`, để A tự fix trên
nhánh `hien` rồi báo lại để merge tiếp.

## 1. Đã thử merge, đã revert

Đã merge thử `origin/hien` vào `main` (commit tạm `ec2112a`, **không push**), chạy
`python -m unittest discover tests "test_*.py"` thì phát sinh **15 lỗi mới** (khác
với lỗi `evidence_conflict` đã biết trước đó). Do lỗi lan ra cả `perceive`,
`test_node_stubs`, `test_parse_memory_suite`, nên đã revert lại
(`git reset --hard 67f0352`) — `main` hiện không có commit của `hien`.

## 2. Nguyên nhân chính: `_call_llm` đổi signature nhưng không khớp `main`

Trên `main` hiện tại, `src/perception/parser.py:155`:

```python
def _call_llm(system_prompt: str, user_text: str) -> dict:
    ...
    return json.loads(raw.strip())
```

Trên `hien`, `src/perception/parser.py:156`:

```python
def _call_llm(system_prompt: str, user_text: str) -> tuple[dict, int, int]:
```

và các nơi gọi (`hien` dòng 263, 364):

```python
extracted, tokens_in, tokens_out = _call_llm(_EXTRACT_SYSTEM_PROMPT, text)
...
extracted, tokens_in, tokens_out = _call_llm(_UPDATE_SYSTEM_PROMPT, new_text)
```

`hien` đã sửa `_call_llm` để trả thêm `tokens_in`/`tokens_out` — đúng hướng, khớp
việc "Cần A" mục 4 trong `HANDOFF-C-2026-09-18.md` (perceive đang ghi
`tokens_in/tokens_out = 0`). Nhưng `hien` rẽ nhánh từ một commit khá cũ
(`c4cb311`), trước rất nhiều thay đổi sau đó trên `main`. Khi merge, Git tự động
gộp file theo dòng mà không báo conflict, kết quả bị lẫn: hàm `_call_llm` giữ bản
`main` (trả `dict` đơn), còn nơi gọi lại theo bản `hien` (unpack 3 giá trị) →

```
ValueError: too many values to unpack (expected 3, got 10)
```

(10 = số key trong dict JSON trả về, vì Python unpack dict theo key khi coi nó
như iterable — không phải lỗi ngẫu nhiên, mà đúng là hai bản `_call_llm` không
tương thích).

## 3. Cần A làm trên nhánh `hien`

1. Rebase (hoặc merge) `hien` lên `main` hiện tại (`67f0352`) trước, xử lý conflict
   ngay trên nhánh của A — đừng để C merge hộ nữa vì càng cũ càng lệch nhiều.
2. Quyết định thống nhất: giữ bản `_call_llm` trả `tuple[dict, int, int]` (khớp ý
   định báo token cost), rồi sửa lại **tất cả nơi gọi** trong `parser.py` (không
   chỉ 2 chỗ ở trên — có thể có thêm) và `src/nodes/perceive.py` nếu nó cũng gọi
   trực tiếp, cho khớp signature mới.
3. Chạy `python -m unittest discover tests "test_*.py"` trên chính nhánh `hien`
   sau khi rebase — phải xanh trước khi báo C merge lại. Đặc biệt chú ý:
   `tests/test_node_stubs.py`, `tests/test_parse_memory_suite.py`.
4. File `src/tools/mock_data/real_data_ghe_ban.json` (dữ liệu `NCC###` ghi tay) A
   thêm trên `hien` **chưa được đưa vào `suppliers.json`** — C đã bỏ nó ra khỏi
   merge để giữ dataset `SRC###` hiện tại của `main`. Nếu A vẫn muốn dùng dữ liệu
   đó, cần convert sang `sources/*.csv` theo `src/tools/mock_data/sources/README.md`
   rồi chạy `python generate_mock_data.py` — không thêm file JSON rời nữa.

## 4. Trạng thái

| Việc | Trạng thái |
|---|---|
| `linh` (B) | Đã merge + push vào `main` (`67f0352`) |
| `hien` (A) | Revert, chờ A fix `_call_llm` + rebase rồi merge lại |
| Dataset `suppliers.json` | Giữ nguyên bản `SRC###` của C, không đổi |
