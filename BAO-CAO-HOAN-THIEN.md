# Báo cáo hoàn thiện sau chấm điểm — 2026-10

A/B/C đã hợp nhất vào `main` ngày 2026-10-09. Yêu cầu gốc giữ tại
[ke-hoach-hoan-thien-sau-cham-diem](docs/ke-hoach-hoan-thien-sau-cham-diem-2026-10-08.md).
Sau refactor/dọn repository: suite offline chạy 472 test, 455 pass và 17 live test
skip theo cơ chế opt-in; không có failure/import error. Bảng dưới mô tả trạng thái
implementation, không quy đổi số liệu stub thành chất lượng NLP thật.

| Nhận xét giảng viên / điểm hiện tại | Thay đổi | Trạng thái | Bằng chứng |
|---|---|---|---|
| Perception 4.1/5: chưa đo câu khó bằng LLM thật | Grader must_extract, field accuracy theo trường, phân tầng | A parser/22 case và C grader đã merge; chờ chạy real | src/eval/scoring.py; tests/test_c_eval_extensions.py |
| Memory 4.2/5: thiếu cô lập phiên và loại kết quả cũ | Test session isolation/đổi ràng buộc | Test A đã merge, pass trong suite stub | tests/test_session_isolation_advanced.py |
| Reasoning 8.9/10: trọng số cố định | Grader expect_priority, channel weights_used; preset theo ưu tiên và UI | Code A/B/C đã merge; chờ eval real | tests/test_c_eval_extensions.py; src/graph_state.py |
| Reasoning: search_new còn null | guard_perceive giữ intent/req/token từ exception; regression nhánh rỗng | C xong khi partial_state có; chờ A mang token/partial ở mọi exception | tests/test_c_core_regressions.py |
| Action 8.8/10: dữ liệu phần lớn mô phỏng, crawl một lần | Template/validate B2B, giới hạn số lượng, refresh + VERSION + stale | C xong code; chờ thu báo giá và chạy refresh có mạng | tests/test_c_data_refresh.py; scripts/refresh_sources.py |
| Action: kết quả rỗng chưa an toàn | filter_stats, không compare batch rỗng, kết thúc có status/answer | C guard và B diễn giải/gợi ý đã merge; C03 smoke pass | tests/test_c_core_regressions.py; cases_c.jsonl C03 |
| Evaluation 6.8/10: 100% chỉ là deterministic trên stub | Tách báo cáo pipeline và llm, cảnh báo lớn khi stub tầng 2 | C xong | scripts/run_autoeval.py; tests/test_c_eval_extensions.py |
| Task success 64.71% chưa chạy LLM thật | 9 case C mới; oracle declarative, không hard-code case | Khung xong; kết quả real còn chờ | tests/eval_set/cases_c_llm.jsonl |
| Cần vài chục câu Việt tự nhiên và lặp 3 lần | tier lọc case, repeat/spread, sleep giữa mọi request | Runner và case A/B/C đã merge; chờ chạy real ×3 | tests/test_c_eval_extensions.py; README.md |
| Task success theo nhóm đủ/thiếu/ngoài phạm vi/đổi ngân sách | by_category, intent routing, no_null_fields, không đo được khi thiếu field | Grader và bộ case A/B/C đã merge, tương thích oracle | src/eval/scoring.py |
| 5–10 báo giá B2B thật và so với web | CSV không liên hệ cá nhân; script chênh giá và hạng pipeline 2 nguồn | A có 3 dòng cần xác minh/bổ sung metadata quote; C xong khung | scripts/compare_b2b_vs_web.py; template; fixture TEST |
| Làm mới theo lịch và ngày từng bản ghi | refresh web, không sửa ngày quote; hướng dẫn lập lịch ngoài repository, stale 14 ngày | C xong code; lịch chưa tạo, fetch thật chưa chạy | README.md; tests/test_c_data_refresh.py |
| Thiếu latency/chi phí, tracing p50/p95, LLM/tool calls | Token/request, cost placeholder, llm/tool/other time; stub load 1/5/10 CCU | C xong khung; latency/cost real còn chờ | tests/test_c_latency.py; scripts/run_loadtest.py |

## Kết quả LLM thật

Chưa có benchmark AutoEval LLM thật ×3. Demo tương tác với LLM thật đã kiểm tra
đổi ưu tiên giá → giao hàng và ngân sách không khả thi; đây là kiểm tra thủ công,
không thay thế bảng task success/field accuracy từ AutoEval. Kịch bản tái hiện:
[docs/demo.md](docs/demo.md). Điền kết quả benchmark từ `reports/autoeval_<...>.json`
sau khi chạy lệnh trong README.
Không ghi số stub vào bảng này. Token price phải có URL pricing chính thức
và ngày tra cứu. Chưa có báo giá B2B đã xác minh theo schema C; không tạo số liệu thay thế.

## Kiểm tra và bằng chứng thực thi

Kiểm tra ngày 2026-10-09:

```powershell
$env:AGENT_LLM="stub"
$env:AGENT_STUB_LATENCY_MEAN_S="0"
$env:AGENT_STUB_LATENCY_STDDEV_S="0"
$env:RUN_LIVE_TESTS=""
.venv\Scripts\python.exe -m unittest discover tests "test_*.py"
```

Kết quả: `Ran 472 tests` / `OK (skipped=17)`; 17 test API thật được giữ và chỉ
chạy khi bật RUN_LIVE_TESTS=1. Log kiểm tra local: `reports/cleanup-tests.txt`.
Lỗi discover do thiếu pytest đã giải quyết bằng unittest; test model kiểm tra
factory dùng cấu hình canonical, không đổi model để khớp literal cũ.

Refactor gom đường compare/evidence của search và compare, bỏ generator dữ liệu
ngẫu nhiên không còn dùng và output sample/eval legacy. Dataset runtime, VERSION,
CSV nguồn, fixture và eval case được giữ nguyên. Dữ liệu JSON legacy giữ tại
`data/archive/`; đề bài và tài liệu thuyết trình được sắp xếp vào `docs/`.
Prompt/handoff/kế hoạch tác nghiệp cũ và artifact demo đã gỡ khỏi cây main.
README và hướng dẫn demo là điểm vào hiện hành; report/log sinh mới chỉ nằm local.

## Việc còn mở

- Parser: giữ token/partial ở mọi exception; không suy ra số đo khi thiếu.
- Thu/xác minh 5–10 báo giá B2B thật, bổ sung metadata của ba dòng A hiện có.
- Chạy refresh có mạng; cấu hình pricing có nguồn/ngày; chạy case LLM thật ×3
  và điền kết quả benchmark vào báo cáo.
- Fan-out detail cần batch/full search theo hợp đồng; gợi ý no-match cần loại
  phương án không thay đổi ngưỡng và đánh giá tính khả thi tổng thể.
- Verification B2B cần nguồn từng field khi giá từ quote còn business field từ web.
- `.env` không track; không sửa lịch sử Git hoặc gửi email trong phiên này.
