# Báo cáo hoàn thiện sau chấm điểm — 2026-10

Phần C thực hiện trên `c/hoan-thien-2026-10`. Kế hoạch gốc:
`docs/ke-hoach-hoan-thien-sau-cham-diem-2026-10-08.md` (mục 1–2).
Chưa commit: baseline có 4 lỗi thuộc A/B; điều kiện trong prompt yêu cầu full
suite pass trước commit. Diff hiện tại là bằng chứng review, chưa push/merge.

| Nhận xét giảng viên / điểm hiện tại | Thay đổi | Trạng thái | Bằng chứng |
|---|---|---|---|
| Perception 4.1/5: chưa đo câu khó bằng LLM thật | Grader must_extract, field accuracy theo trường, phân tầng | C xong khung; chờ A viết 22 case và sửa parser; chờ chạy real | src/eval/scoring.py; tests/test_c_eval_extensions.py |
| Memory 4.2/5: thiếu cô lập phiên và loại kết quả cũ | Yêu cầu test session isolation/đổi ràng buộc | chờ A | docs/handoff-c-to-ab-2026-10.md |
| Reasoning 8.9/10: trọng số cố định | Grader expect_priority, channel weights_used; preset theo ưu tiên và UI | C xong khung; chờ A/B logic/UI | tests/test_c_eval_extensions.py; src/graph_state.py |
| Reasoning: search_new còn null | guard_perceive giữ intent/req/token từ exception; regression nhánh rỗng | C xong khi partial_state có; chờ A mang token/partial ở mọi exception | tests/test_c_core_regressions.py |
| Action 8.8/10: dữ liệu phần lớn mô phỏng, crawl một lần | Template/validate B2B, giới hạn số lượng, refresh + VERSION + stale | C xong code; chờ thu báo giá và chạy refresh có mạng | tests/test_c_data_refresh.py; scripts/refresh_sources.py |
| Action: kết quả rỗng chưa an toàn | filter_stats, không compare batch rỗng, kết thúc có status/answer | C xong; chờ B diễn giải nút thắt/gợi ý có bằng chứng | tests/test_c_core_regressions.py; cases_c.jsonl C03 |
| Evaluation 6.8/10: 100% chỉ là deterministic trên stub | Tách báo cáo pipeline và llm, cảnh báo lớn khi stub tầng 2 | C xong | scripts/run_autoeval.py; tests/test_c_eval_extensions.py |
| Task success 64.71% chưa chạy LLM thật | 9 case C mới; oracle declarative, không hard-code case | Khung xong; kết quả real còn chờ | tests/eval_set/cases_c_llm.jsonl |
| Cần vài chục câu Việt tự nhiên và lặp 3 lần | tier lọc case, repeat/spread, sleep giữa mọi request | C xong runner; chờ A/B đủ khoảng 40 case, chạy real | tests/test_c_eval_extensions.py; README.md |
| Task success theo nhóm đủ/thiếu/ngoài phạm vi/đổi ngân sách | by_category, intent routing, no_null_fields, không đo được khi thiếu A/B | C xong; chờ bộ case A/B | src/eval/scoring.py |
| 5–10 báo giá B2B thật và so với web | CSV không liên hệ cá nhân; script chênh giá và hạng pipeline 2 nguồn | C xong khung; chưa có báo giá thật | scripts/compare_b2b_vs_web.py; template; fixture TEST |
| Làm mới theo lịch và ngày từng bản ghi | refresh web, không sửa ngày quote; hướng dẫn schtasks/cron, stale 14 ngày | C xong code; lịch chưa tạo, fetch thật chưa chạy | README.md; tests/test_c_data_refresh.py |
| Thiếu latency/chi phí, tracing p50/p95, LLM/tool calls | Token/request, cost placeholder, llm/tool/other time; stub load 1/5/10 CCU | C xong khung; latency/cost real còn chờ | tests/test_c_latency.py; scripts/run_loadtest.py |

## Kết quả LLM thật

TODO(C): lấy từ reports/autoeval_<...>.json sau khi chạy LLM thật.
Không ghi số stub vào bảng này. Token price phải có URL pricing chính thức
và ngày tra cứu. Chưa có báo giá B2B thật; không tạo số liệu thay thế.

## Kiểm tra và bằng chứng thực thi

Baseline chuẩn với TEMP/TMP được phép ghi: 384 test, 2 failures + 2 errors.
Sau 4 đợt: xem số cuối, đường dẫn report và markdown đầy đủ trong
`docs/role-c-execution-2026-10.md`. Full suite còn lỗi nền nên không khẳng định
đã pass trên main. Các report stub ở thư mục tạm ngoài repo, không force-add.

## Việc mở theo mục 9 — định nghĩa xong

- A: exception giữ token/partial ở mọi nhánh; 22 case câu khó/thiếu/đổi ngân
  sách; isolation và loại kết quả cũ; xử lý live test stdlib/model expectation.
- B: rỗng có nút thắt và gợi ý dẫn nguồn; preset theo ưu tiên và hiển thị UI;
  case priority/no_match; sửa/xác minh evidence conflict của test nền; slide.
- C/cả nhóm: xác nhận field đề xuất; thu 5–10 báo giá thật (A/B mỗi người 3);
  chạy refresh có mạng; điền pricing; chạy ~40 case real ×3; điền báo cáo;
  full suite pass; chọn report add-f; review diff, merge/push và duyệt email.
- Secret: kết quả rà file track được ghi ở ledger; `.env` không track.
  Chưa xóa lịch sử Git hoặc gửi email.
