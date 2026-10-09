# Thực hiện kế hoạch C — 2026-10-09

Kế hoạch: `docs/prompt-gpt-agent-role-c-2026-10-09.md`, đối chiếu `docs/ke-hoach-hoan-thien-sau-cham-diem-2026-10-08.md`.

- Nhánh: `c/hoan-thien-2026-10`, từ main. Hai thay đổi trước phiên ở `.env.example` và `src/graph_state.py` được bảo toàn trong stash `pre-role-c-existing-edits-2026-10-09`. File chưa track giữ nguyên.
- Baseline: 384 test; 2 failures và 18 errors trong sandbox mặc định (gồm lỗi thư mục tạm). Chạy lại với TEMP/TMP trong thư mục được phép ghi để xác định lỗi nền.
- Chỉ dùng StubLLM, latency giả lập bằng 0; không chạy fetch thật, không push/merge/gửi email.
- Quyết định: thực hiện liên tục 4 đợt theo yêu cầu hiện tại; không dừng ở dòng “chờ prompt từng đợt” trong tài liệu hướng dẫn phiên CLI.
- Quyết định: dùng nhánh được yêu cầu trong checkout hiện có; không tạo worktree mới vì venv và file kế hoạch chưa track đang ở checkout này.
- Quyết định: field mới ghi ở mục ĐỀ XUẤT, đọc an toàn khi A/B chưa triển khai; không sửa logic A/B.
- Quyết định: không commit nếu full suite còn lỗi nền; lưu diff và báo cáo để người dùng review. Không sửa test A/B để làm xanh.
- Phụ thuộc: đợt 1 tạo filter_stats cho B; đợt 2 grader đọc req/weights_used/relax_suggestions; đợt 3 stale đi qua evidence sang respond; đợt 4 thêm số đo nội bộ cho báo cáo đợt 2. Không đổi tên field hiện có.

## Tiến độ

- Đợt 1: code/test C xong; partial token trên exception thật còn chờ A.
- Đợt 2: code/test xong; số LLM thật/pricing chưa chạy, để TODO.
- Đợt 3: code/test xong; chưa fetch thật/tạo lịch/thu báo giá B2B.
- Đợt 4: đo stub và tài liệu xong; full suite còn đúng 4 lỗi nền, chưa commit.

## Kiểm chứng thực tế

Mọi lệnh test dùng `.venv\Scripts\python.exe`, stdlib unittest. TEMP/TMP trỏ
đến thư mục được phép ghi ngoài repo; AGENT_LLM=stub, hai biến latency stub=0.

| Lượt | Kết quả từ output thật | Log ngoài repo |
|---|---|---|
| Baseline sau sửa TEMP/TMP | 384 tests; 2 failures + 2 errors | role-c/baseline-clean-temp.txt |
| Đợt 1 RED → GREEN | 7 tests; 4 failures + 4 errors → OK | phase1-red.txt / phase1-green.txt |
| Đợt 2 RED → GREEN | 8 tests; 4 failures + 4 errors → OK | phase2-red.txt / phase2-green.txt |
| Đợt 3 RED → GREEN | 10 tests; 7 failures + 8 errors (subtests) → OK | phase3-red.txt / phase3-green.txt |
| Đợt 4 RED → GREEN | 3 tests; 1 failure + 2 errors → OK sau giữ độ chính xác timing | phase4-red.txt / suite-final.txt |
| Sửa sau review RED → GREEN | 5 tests; 2 failures + 1 error → OK | review-red.txt / review-green.txt |
| C mới tổng cộng | 33 tests, OK | c-tests-final.txt |
| Toàn bộ sau sửa | 417 tests; 2 failures + 2 errors, giống baseline | suite-final.txt |

Root bằng chứng ngoài repo:
`C:/Users/Admin/.codex/visualizations/2026/10/09/01a11ed5-c2e8-7bb3-93af-6b58c84a9e02/role-c/`.
Lệnh full suite: `.venv\Scripts\python.exe -m unittest discover tests "test_*.py"`.
Không có commit mới (HEAD nền `e922015`); không push/merge. Thay đổi có sẵn được
áp lại bằng patch từ stash vì `stash apply` không cho ghi đè graph_state đang sửa.
Stash vẫn được giữ làm bản sao; `.env.example` không phải thay đổi của C.

### Tình trạng theo từng việc

| Việc | Trạng thái | Ghi chú |
|---|---|---|
| 1.1 / C.2 | Một phần | C giữ partial intent/req/token nếu exception có; A chưa gắn usage trên mọi exception |
| 1.2 / C.3 | Xong phần C | filter_stats, không compare rỗng; B vẫn cần lời giải thích/gợi ý nới |
| 1.3 fan-out tùy chọn | Chỉ đề xuất | Batch/full search đổi hợp đồng, chưa code |
| 2.1 phân tầng | Xong | 19 case cũ gắn tier; thiếu tier mặc định hai tầng; warning 19 case legacy |
| 2.2 metrics/grader | Xong | Category/field/intent/operations/cost placeholders; missing A/B không pass |
| 2.3 report | Xong khung | Hai bảng tầng riêng, per-request vận hành; spread từng tầng có trong JSON |
| 2.4 case mới | Xong | 3 out_of_scope, 3 adversarial, 3 injected tool_failure; câu Việt có dấu |
| 3.1 stale | Xong | Inject clock, 14 ngày cấu hình, thiếu ngày có lý do; cảnh báo không gọi thêm LLM |
| 3.2 refresh | Xong code/test | Mocked fetch; cache snapshot mới từng run/CSV; dry-run không mạng/ghi; chưa chạy refresh thật |
| 3.3 B2B | Xong khung | Template/fixture TEST, validate/quantity scope, compare; chưa có báo giá thật |
| 4.1 latency/load | Xong stub | 1/5/10 CCU ×10 requests; chưa đo API thật |
| 4.2 docs/security | Xong tài liệu | README/report/handoff/email draft; không gửi email; chưa add-f report |

### Review độc lập

Skill executing-plans yêu cầu một final reviewer. Reviewer đọc toàn diff và
chạy 28 test C trước fix, OK; không sửa code, không gọi mạng.

- Đã sửa: stream timeout trước chunk vẫn đếm một API attempt và llm_ms; lỗi
  khởi tạo client không được đếm API call.
- Đã sửa: hai scenario B2B giữ cùng constraints/thuộc tính ngoài giá, giá quote
  có price_source_url riêng; câu trả lời mua hàng không xuất từ scenario.
- Đã sửa: cache refresh tách mỗi run và mỗi CSV, không replay HTML cũ như fetch mới.
- Minor để lại: Markdown spread chung vẫn tổng hợp mọi case; JSON tier_spread
  đã có min/max/stdev riêng từng tầng. Khi trích variance theo tầng dùng JSON.

Quyết định với phần reviewer không đánh giá: giữ lỗi/logic A/B cho chủ sở hữu;
LLM/pricing/B2B thực cần người dùng thu/chạy sau; grader citation/no-number cũ
giữ nguyên và ghi rõ giới hạn; tài liệu được rà riêng sau khi code review.
Chi phí nếu các quyết định sai: phải cập nhật A/B, chạy lại real eval hoặc
grader trước khi nộp, không coi stub là kết quả real.

### Secret và Git

Rà 116 file text được track bằng pattern AIza/sk- và assignment GOOGLE_API_KEY/
OPENROUTER_API_KEY. Không tìm thấy chuỗi key thật; `.env` không track. Một hit
ban đầu tại .env.example:1 là placeholder `your_google_ai_studio_key_here`, đã
xác minh và loại false positive. Không in giá trị key, không xóa lịch sử.
JSON bằng chứng: `role-c/secret-scan.json`.

### Việc người dùng làm tay

1. A/B xác nhận field đề xuất và sửa 4 lỗi nền; review diff rồi mới commit.
2. A/B bổ sung bộ case, field ưu tiên/gợi ý, test memory; mỗi người thu 3 báo giá.
3. Điền MODEL_PRICING từ nguồn chính thức + ngày; chạy refresh thật nếu cần.
4. Chạy LLM thật (lệnh dưới), điền BAO-CAO-HOAN-THIEN.md, duyệt report cuối.

```powershell
.venv\Scripts\python.exe scripts/run_autoeval.py --eval-set tests/eval_set --llm real --tier llm --repeat 3 --sleep-between 4
```

Chỉ các đường dẫn dưới đây là ứng viên report cuối để sao chép vào `reports/`
và `git add -f` sau khi duyệt; C chưa thực hiện sao chép/force-add:

- `reports/autoeval_20261009_112316.json` và `.md`: smoke stub 28 case, không đánh giá LLM thật.
- `reports/loadtest_20261009_112046.json` và `.md`: stub 1/5/10 CCU.
- `reports/autoeval_<timestamp-real>.json` và `.md`: TODO(C), chưa tồn tại.
- `reports/b2b_vs_web_<ngày>.md`: TODO(C), chưa tồn tại vì chưa có báo giá.

Hai report stub hiện nằm trong `role-c/final/` ở root bằng chứng ngoài repo.


## Report thực tế đã chạy (stub, không đánh giá LLM thật)

C03_search_returns_empty: pass. Runner cảnh báo bỏ qua 19 case không oracle ở cases.jsonl. Tổng 28 case; 30 requests. Pipeline 22 case, LLM tier 21 case (membership có thể chồng lấp).

### Markdown AutoEval nguyên văn

# Báo cáo AutoEval hai tầng

> **CẢNH BÁO: Tầng 2 chạy StubLLM; số này KHÔNG đánh giá năng lực LLM thật.**

- Thoi diem: 2026-10-09T11:23:16+07:00
- dataset_version: 2026-09-22+sha256.ff900067fb84 records=106
- So case: 28  |  So lan lap: 1
- LLM: stub
- Model: StubLLM | provider: stub
- Tầng chọn: all | case duy nhất: 28
- Requests: 30 | sleep-between: 0s

## Tầng 1 — Kiểm thử pipeline

| Chi so | Gia tri |
|---|---|
| constraint_satisfaction_rate | 1.0 |
| tool_call_success_rate | 0.7294 |
| citation_correctness | 1.0 |
| failure_recovery_rate | 1.0 |

## Tầng 2 — Năng lực LLM

| Nhóm | Case | Pass | Không đo được | Task success |
|---|---|---|---|---|
| adversarial | 9 | 6 | 0 | 0.6667 |
| happy_path | 2 | 1 | 0 | 0.5 |
| missing_info | 1 | 0 | 0 | 0.0 |
| multi_turn | 2 | 2 | 0 | 1.0 |
| out_of_scope | 3 | 0 | 0 | 0.0 |
| tool_failure | 4 | 3 | 0 | 0.75 |

| Chỉ số | Giá trị |
|---|---|
| task_success_rate | 0.5714 |
| intent_routing_accuracy | 0.6471 |
| field_accuracy | không đo được |
| no_invented_numbers | 1.0 |

| Trường trích xuất | Đúng | Đã kiểm | Thiếu | Accuracy |
|---|---|---|---|---|

## Vận hành

| Chỉ số | Giá trị |
|---|---|
| latency_avg_ms | 4871.491 |
| latency_p50_ms | 80.72 |
| latency_p95_ms | 65709.16 |
| latency_max_ms | 65752.73 |
| llm_p50_ms | 0.3903 |
| llm_p95_ms | 0.6944 |
| tool_p50_ms | 66.06 |
| tool_p95_ms | 65614.28 |
| other_p50_ms | 11.97 |
| avg_llm_calls | 1.7 |
| avg_tool_calls | 37.3 |
| avg_tokens_in | 170.0 |
| avg_tokens_out | 85.0 |
| estimated_cost_avg_usd | chưa cấu hình giá |
| estimated_cost_total_usd | chưa cấu hình giá |

## Diễn giải

Tầng 1 kiểm tra implementation, KHÔNG chứng minh năng lực hiểu ngôn ngữ. Số tầng 2 chỉ có giá trị khi llm_mode=real. Case thiếu field A/B được ghi không đo được, không tính là pass.
Latency/chi phí lấy trên từng request (từng lượt), task success chấm state cuối của case. Tool latency gồm retry/backoff. Percentile dùng nearest-rank.
No-invented-numbers dùng grader heuristic hiện có: chỉ kiểm số từ 100 trở lên; không chứng minh toàn bộ con số nhỏ hay sự gắn nguồn trong văn bản. Giá token cần nguồn/ngày chính thức.

## Case truot

- **C08_out_of_scope_request** (adversarial): expect_status=out_of_scope nhung nhan needs_confirmation; must_reach_intent=out_of_scope nhung nhan search_new; must_not_call_tools: da goi search_suppliers; must_not_call_tools: da goi compare_price; must_state_limits: cau tra loi khong neu gioi han he thong
- **C09_impossible_budget** (adversarial): expect_status=graceful_fail nhung nhan needs_confirmation
- **C10_asks_for_a_number_it_cannot_know** (adversarial): expect_status=success nhung nhan needs_confirmation
- **C11_compare_unknown_ids_no_search** (tool_failure): expect_status=graceful_fail nhung nhan needs_confirmation; must_reach_intent=compare_specific nhung nhan search_new; must_not_call_tools: da goi search_suppliers
- **C12_supplier_detail_never_asks_to_order** (happy_path): expect_status=success nhung nhan needs_confirmation; must_reach_intent=supplier_detail nhung nhan search_new; must_not_call_tools: da goi search_suppliers; must_not_call_tools: da goi compare_price
- **C16_missing_quantity_budget_deadline** (missing_info): expect_status=needs_input nhung nhan needs_confirmation; must_not_call_tools: da goi search_suppliers; must_not_call_tools: da goi compare_price; must_ask_user: status=needs_confirmation, khong hoi lai nguoi dung
- **CL01_travel_planning** (out_of_scope): expect_status=out_of_scope nhung nhan needs_confirmation; must_reach_intent=out_of_scope nhung nhan search_new; must_not_call_tools: da goi search_suppliers; must_not_call_tools: da goi get_supplier_detail; must_not_call_tools: da goi compare_price; must_state_limits: cau tra loi khong neu gioi han he thong
- **CL02_financial_advice** (out_of_scope): expect_status=out_of_scope nhung nhan needs_confirmation; must_reach_intent=out_of_scope nhung nhan search_new; must_not_call_tools: da goi search_suppliers; must_not_call_tools: da goi get_supplier_detail; must_not_call_tools: da goi compare_price; must_state_limits: cau tra loi khong neu gioi han he thong
- **CL03_software_setup** (out_of_scope): expect_status=out_of_scope nhung nhan needs_confirmation; must_reach_intent=out_of_scope nhung nhan search_new; must_not_call_tools: da goi search_suppliers; must_not_call_tools: da goi get_supplier_detail; must_not_call_tools: da goi compare_price; must_state_limits: cau tra loi khong neu gioi han he thong

### Markdown load test nguyên văn

# Bao cao load test

- Thoi diem: 2026-10-09T11:20:44+07:00
- LLM: stub (mean=0.0s, stddev=0.0s moi lan goi LLM, 2 lan goi/request)
- Prompt: Can 50 ghe van phong, ngan sach 200 trieu, giao trong 14 ngay, uu tien Ha Noi

| CCU | req | rps | p50_ms | p95_ms | error_rate | cpu% | rss_mb |
|---|---|---|---|---|---|---|---|
| 1 | 10 | 18.001 | 53.41 | 70.89 | 0.0 | 90.0 | 85.4 |
| 5 | 10 | 23.686 | 171.86 | 264.34 | 0.0 | 136.9 | 86.6 |
| 10 | 10 | 15.172 | 545.95 | 651.98 | 0.0 | 109.0 | 87.8 |

| CCU | LLM p50_ms | LLM p95_ms | Tool p50_ms | Tool p95_ms | Other p50_ms |
|---|---|---|---|---|---|
| 1 | 0.341 | 0.4497 | 38.85 | 40.49 | 7.51 |
| 5 | 0.3439 | 0.4152 | 130.3 | 159.63 | 23.93 |
| 10 | 0.5196 | 0.6311 | 356.51 | 388.37 | 68.06 |

LLM time là thời gian node perceive + respond (gồm parse/wiring); tool time gồm retry/backoff. Stub latency bằng 0 chỉ đo pipeline, không đại diện hiệu năng API thật.

### Smoke bổ sung

- `--tier pipeline --repeat 2 --sleep-between 0.01` trên một case happy_path thực trong JSONL: 2 kết quả pass, JSON có spread/tier_spread và request tokens. File: role-c/repeat-smoke/autoeval_20261009_113226.json và .md.
- Compare B2B chạy thật pipeline stub với fixture TEST: hai scenario rank=1, status=success; dữ liệu ngoài repo: role-c/b2b-fixture-smoke.md, có nhãn TEST DATA ONLY. Không đưa fixture vào suppliers.json.
- `git diff --check`: chỉ còn hai trailing whitespace tại req/plan graph_state do thay đổi có sẵn đã phục hồi từ stash; không sửa ngầm nội dung của người dùng.
