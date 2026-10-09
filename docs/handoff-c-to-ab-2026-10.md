# Bàn giao C → A/B — 2026-10

## A — Perception và Memory

- `src/perception/parser.py::parse_request`, `update_state`: mọi exception sau khi gọi LLM cần mang `partial_state`, `tokens_in`, `tokens_out` đã đo; kể cả `InvalidProductTypeError`, `ValueError`. C đã đọc an toàn các thuộc tính này tại `guard_perceive`, không đoán intent/token khi thiếu. Test đề xuất: mock AIMessage có usage, thiếu quantity → final needs_input còn intent/req và token > 0; lượt sau bổ sung phải giữ session.
- Test nền `test_parse_memory_suite.TestParserConstants.test_llm_model_name_is_current_value` kỳ vọng `gemini-3.6-flash`, nhưng cấu hình hiện dùng `gemini-3.5-flash-lite`. A xác nhận/cập nhật kỳ vọng phù hợp cấu hình, C không đổi model chỉ để làm xanh test.
- Hai file `tests/test_gemini_*_live.py` import pytest gây lỗi discover stdlib khi pytest không cài. A chuyển live test sang unittest và skip khi AGENT_LLM=stub; không chạy live test trong suite offline.
- Viết cases_a.jsonl (22 case theo mục 5.2) có `tier="llm"`, oracle `must_extract`; test cô lập phiên và bỏ kết quả cũ khi đổi yêu cầu. File cases.jsonl cũ chưa có oracle được runner cảnh báo, không dùng đánh giá E2E.

## B — Reasoning, trọng số, phản hồi khi rỗng

- `src/nodes/reasoning.py::diagnose`, `graceful_fail`: đọc `state.get("filter_stats")` hoặc `tool_results[*].result.filter_stats`. Dùng count sau product/material/region xác định nút thắt, sinh `relax_suggestions`; count null nghĩa là chưa đo được, không tự nới ràng buộc. Input/output thử nghiệm ghi trong mục ĐỀ XUẤT cuối interface-contracts.md.
- `score_rank` trả `weights_used={preset,weights,reason}` theo ưu tiên do A trích. C đã khai báo channel để LangGraph giữ hai field weights_used/relax_suggestions; chưa tự sinh các field này. Test đề xuất: 4 preset, mặc định balanced không đổi thứ hạng; yêu cầu no_match phải có gợi ý list không rỗng.
- Test nền `test_reasoning_tools_integration...test_real_mock_data_runs_from_plan_to_recommendation`: dữ liệu hiện cho `evidence_conflict` thay vì success. B kiểm tra nguồn xung đột và tiêu chí test; C không chỉnh logic/test B.
- Fan-out: giảm số get_supplier_detail cần batch tool hoặc search trả full record, đều thay hợp đồng. Đề xuất này chưa code; giữ args_schema hiện có.
- So sánh giá B2B là thử nghiệm thay riêng giá, giữ thuộc tính ngoài giá và request cố định. `price_source_url`/`field_sources` lưu nguồn giá và nguồn từng field; `verify_output` của B đang dùng một URL chung cho toàn NCC. B cần xét field_sources để không gán nguồn quote cho business field từ web. C chỉ xuất thứ hạng/dữ liệu so sánh có hai nguồn, không xuất lời khuyên mua từ scenario.

## Báo giá B2B — A và B mỗi người thu 3 báo giá

Sao chép header `src/tools/mock_data/sources/b2b_quotes_template.csv` vào file CSV riêng cùng thư mục (bỏ dòng chú thích). Điền NCC/sản phẩm đã có giá web, `nguon_type=b2b_quote`, `quote_date`, `quote_quantity`, `quote_channel` cùng giá VND số thuần. `source_url` là URL bằng chứng được phép chia sẻ (bản báo giá đã che thông tin cá nhân); không điền số điện thoại/email cá nhân người bán. Trường không được báo giá xác nhận để trống, generator ghi nguồn mô phỏng theo chính sách. Chạy generator rồi `scripts/compare_b2b_vs_web.py --llm stub` để so sánh.

## Cả nhóm cần xác nhận

- Các field trong “ĐỀ XUẤT 2026-10 — chờ A/B xác nhận”, đặc biệt phạm vi số lượng báo giá B2B.
- Sau khi A/B tích hợp, chạy LLM thật khoảng 40 case × 3 lần, điền giá token từ trang chính thức có nguồn/ngày. Số stub chỉ kiểm tra implementation.
