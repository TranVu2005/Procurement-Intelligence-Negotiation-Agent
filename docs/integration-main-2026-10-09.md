# Hợp nhất main — 2026-10-09

Yêu cầu tiếp theo của người dùng: merge code các nhánh vào main rồi xóa nhánh
`c/hoan-thien-2026-10`, repo GitHub của dự án. Yêu cầu này thay điều kiện dừng
commit/merge ở phiên triển khai C trước đó; các lỗi nền vẫn phải báo trung thực.

- Base main: `e922015`.
- Fetch GitHub trước khi tích hợp: A có `d4c5dfb`, `9807238` mới; B có `7fce3d4` mới.
- Các nhánh demo C/role-c-implementation cũ đã là ancestor của main.
- Trước merge: 417 tests, 2 failures + 2 import errors, giống baseline đã báo.
- Chỉ dùng StubLLM/latency 0 khi kiểm tra; không chạy eval/API LLM thật.
- Hai thay đổi có sẵn `.env.example` và phần xóa comment ở graph_state được
  giữ riêng, không trộn vào commit C; sẽ phục hồi trên main sau tích hợp.
- File ngoài phạm vi trước phiên (.claude, .playwright-mcp, ghi chú/slide chưa
  track) giữ nguyên. Không force-add logs/reports, không xóa stash bảo toàn.

## Kết quả tích hợp

- C: `bc9e993`; merge A `6fb6d61`, merge B `dc700bf`, merge C `0c84f67`.
- Guard perception dùng helper C giữ intent/req/session của A và token nếu
  exception có số đo. Hợp nhất category oracle A/B/C, bỏ annotation state trùng.
- Sửa tương thích oracle A: boolean `no_null_fields: true` kiểm bốn field
  request bắt buộc; không kiểm các field tùy chọn được phép null. Case trích
  field/intent không bắt buộc khai báo status. Hợp đồng ghi ở interface-contracts.
- Hai test hồi quy tái hiện `TypeError: bool is not iterable` trước sửa;
  tất cả oracle A/B/C được chấm không crash sau sửa.
- Review độc lập phát hiện oracle B06–B09 đòi ranked/verdict không rỗng dù
  nhánh no-match hợp lệ giữ list/dict rỗng; B09 đòi gợi ý dù search rỗng.
  Test hồi quy tái hiện 4 false failures. Sửa oracle B bỏ các field cố ý rỗng,
  vẫn giữ must_suggest_relax ở B06–B08 và mọi ràng buộc status/intent/tool.
  Sau sửa **20 test grader/schema/no-match pass**.
- Full suite offline sau sửa: **454 tests, 1 failure + 2 errors**:
  `test_gemini_intent_live` và `test_gemini_memory_live` thiếu `pytest` khi import;
  `test_parse_memory_suite.TestParserConstants.test_llm_model_name_is_current_value`
  kỳ vọng `gemini-3.6-flash` nhưng code dùng `gemini-3.5-flash-lite`.
  Test evidence-conflict nền trước đó đã pass với logic B mới.
- Smoke 3 case A/B/C với stub tạo report, C03 pass; A06/B01 fail vì stub trả
  priority balanced. Đây là kiểm tra đường chạy/báo cáo, không là điểm LLM thật.
- Bằng chứng ngoài repo: thư mục `role-c` dưới workspace visualization của
  phiên, gồm `integration-red.txt`, `integration-green.txt`,
  `merged-final-suite.txt`, `integration-smoke/autoeval_20261009_114355.json`.
- `a_b2b_quotes.csv` của A có 3 dòng nhưng thiếu nguon_type, quote_date,
  quote_quantity, quote_channel theo schema C. Giữ file gốc; cần xác minh
  provenance/bổ sung metadata trước import quote và so sánh, không tạo giá thay.

Main được đồng bộ lên origin; chỉ xóa nhánh local `c/hoan-thien-2026-10`
sau khi kiểm tra commit C đã là ancestor main. Nhánh này không có trên origin;
giữ các nhánh nhóm `hien`, `linh` và các nhánh C cũ.
