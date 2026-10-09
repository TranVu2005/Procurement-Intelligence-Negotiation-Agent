# Báo cáo QA Reasoning của Người B — 2026-09-19

## Phạm vi đã kiểm tra

Chạy riêng 43 test liên quan trực tiếp đến phần B:

```powershell
$env:AGENT_LLM="stub"
.\.venv\Scripts\python.exe -m unittest `
  tests.test_scoring `
  tests.test_verification `
  tests.test_graph_routing `
  tests.test_integration_ab `
  tests.test_b_real_sources -v
```

Kết quả: **43/43 pass**.

## Ma trận kết quả

| Nhóm | Nội dung kiểm tra | Kết quả |
|---|---|---|
| Planning | State hợp lệ/thiếu trường, soft constraint, workflow stages | Pass |
| Hard-filter | Ngân sách, MOQ, tồn kho, giao hàng và nhiều lý do loại | Pass |
| Missing/null | Không tự tạo giá hoặc điểm uy tín khi thiếu bằng chứng | Pass |
| Scoring | 5 thành phần điểm, kết quả lặp lại được | Pass |
| Ranking | Xếp tốt nhất trước, có giải thích ưu tiên mềm/đánh đổi | Pass |
| Verification | Citation thiếu, tổng tiền sai, vi phạm hard constraint | Pass |
| Diagnosis | Mã nguyên nhân chính và danh sách nhà cung cấp bị ảnh hưởng | Pass |
| Replanning | Có lý do/audit trail, dừng ở giới hạn tối đa | Pass |
| Routing | Verifier fail đi diagnose; hết lượt đi graceful fail | Pass |
| Dữ liệu B | Đủ tủ hồ sơ/kệ, giá dương, HTTPS, trường chưa rõ để thiếu | Pass |

Full suite sau khi thêm phần B: **256/256 pass** với `AGENT_LLM=stub`.

## Kiểm tra giao diện

- Streamlit `1.64.0` khởi động thành công ở chế độ headless.
- `/_stcore/health` trả `ok`.
- `streamlit.testing.v1.AppTest` render `app.py` không có exception, có tiêu đề
  và chat input.

## Giới hạn cần nói rõ

`data/sources_b_tu_ke.csv` là file nguồn bàn giao, chưa phải dataset runtime.
Do đó kết quả trên xác nhận thuật toán B và chất lượng file handoff, chưa phải
đánh giá cuối trên dataset thật đã tích hợp. C cần import dữ liệu A/B/C vào
schema chung trước; sau đó B phải chạy lại cùng ma trận test và một lượt Gemini
thật trước khi chốt số liệu báo cáo.

## Phụ lục final — 2026-10-09

- Thêm preset `balanced`, `price`, `delivery`, `quality`; tổng mỗi preset bằng 1.
- Preset thiếu/không hợp lệ fallback về `balanced`, giữ tương thích demo cũ.
- `weights_used` được trả trong state/ranked record và hiển thị trên Streamlit.
- Thêm `relax_suggestions` có số liệu và `MaNCC` căn cứ cho no-match.
- Sửa false-positive conflict giữa các model khác nhau của cùng NCC bằng
  `TenSanPham` trong grouping key.
- Thêm `tests/test_no_match_flow.py` và các test preset/ranking/UI.
- Thêm 9 case ở `tests/eval_set/cases_b.jsonl`: 5 priority, 4 no-match.

### Trọng số có còn cố định không?

Không. Mặc định vẫn là bộ cũ `balanced`, nhưng khi A trích được ưu tiên tường
minh thì B chọn `price`, `delivery` hoặc `quality`. LLM không tự đặt trọng số;
toàn bộ preset nằm trong code, có test và được xuất qua `weights_used` để audit.

### Gợi ý nới có phải LLM bịa không?

Không. `build_relax_suggestions` đọc `actual` trong violations và evidence của
NCC bị loại. Mọi gợi ý số đều mang `supplier_ids` và source nếu có. Nếu không có
record, hệ thống không đưa ra con số. Gợi ý cũng không tự động thay constraint.

### Vì sao cùng một NCC có nhiều giá không còn luôn là conflict?

Vì một NCC có thể bán nhiều model trong cùng nhóm sản phẩm. Conflict chỉ hợp lý
khi hai record nói về cùng product identity. Key mới thêm `TenSanPham`; record
khác model được tách, còn hai phiên bản cùng model vẫn bị kiểm tra.
