# Demo và kiểm tra cải thiện

Chạy từ thư mục gốc theo [README](../README.md). Web: http://127.0.0.1:8501/.

## Kịch bản tương tác với LLM thật

1. Nhập: “Tôi cần mua 50 ghế văn phòng, ngân sách tối đa 200 triệu đồng, giao trong 14 ngày, ưu tiên giá.” Kiểm tra ràng buộc, bảng xếp hạng, nguồn, field mô phỏng, `weights_used`, verifier, trace và latency.
2. Trong cùng phiên: “Giữ nguyên yêu cầu, đổi sang ưu tiên giao hàng nhanh.” Kiểm tra priority thành delivery, trọng số giao hàng 40%, giá 20%, thứ hạng được tính lại và các hard constraint giữ nguyên.
3. Trong cùng phiên: “Giảm ngân sách xuống 1 triệu đồng.” Kiểm tra trạng thái thất bại có giải thích/gợi ý, không so sánh batch rỗng, không tự nới ngân sách hoặc chốt đơn. Gợi ý phải được đối chiếu với evidence trước khi áp dụng.
4. Mở phiên mới, nhập yêu cầu thiếu số lượng/ngân sách/deadline. Kiểm tra câu hỏi bổ sung và không rò rỉ dữ liệu phiên trước.

Kết quả phụ thuộc dataset VERSION và model hiện dùng. Stub không thực hiện các lượt đổi ý theo NLP; dùng suite regression để kiểm tra logic offline.

## Chạy kịch bản và lưu bằng chứng

```powershell
# Sau khi cấu hình API key; script gọi LLM thật nếu không bật stub:
.venv\Scripts\python.exe scripts/run_demo_scenarios.py
# Chỉ chọn ID/prefix:
.venv\Scripts\python.exe scripts/run_demo_scenarios.py KB1 T1
```

Output: `reports/demo-run-<ngày>.md`, `reports/demo_run_<ngày>.json`; tracing tại `logs/`. Các thư mục này được Git bỏ qua. Script chấm theo expect_status/top/absent/tools đã khai báo; transcript demo không thay thế AutoEval NLP ×3.

## Regression offline

```powershell
$env:AGENT_LLM="stub"
$env:AGENT_STUB_LATENCY_MEAN_S="0"
$env:AGENT_STUB_LATENCY_STDDEV_S="0"
.venv\Scripts\python.exe -m unittest tests.test_demo_fixes_c tests.test_no_match_flow tests.test_graph_e2e_stub tests.test_session_isolation_advanced -v
```

Không dùng số đo stub để báo cáo chất lượng ngôn ngữ hoặc tốc độ API thật. Xem [báo cáo cuối](../BAO-CAO-HOAN-THIEN.md) để biết các kiểm tra đã thực hiện và việc còn mở.
