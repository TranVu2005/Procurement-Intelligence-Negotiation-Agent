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
