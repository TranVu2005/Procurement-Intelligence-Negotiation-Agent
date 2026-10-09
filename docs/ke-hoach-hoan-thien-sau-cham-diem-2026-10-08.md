# Kế hoạch hoàn thiện sau chấm điểm — Nhóm 2

Ngày lập: 2026-10-08 · Hạn gửi lại: 14 ngày kể từ ngày nhận mail (kế hoạch này tính **08/10 → 22/10/2026**; sửa lại mốc nếu ngày nhận mail khác).

Nguồn: *Phiếu chấm tóm tắt* + *Nhận xét chi tiết* của giảng viên, đối chiếu với code ở `main` (commit `e922015`).

Phân vai giữ nguyên như `CLAUDE.md`:

| Vai | Người | Phạm vi sở hữu |
|---|---|---|
| A | Nguyễn Thị Hiền | `src/perception/`, `src/memory/`, node `perceive` |
| B | Vũ Hoàng Diệu Linh | `src/reasoning/`, nodes `plan`/`filter_hard`/`score_rank`/`verify_output`/`diagnose`/`replan`/`graceful_fail`, prompt `respond`, `app.py` (Streamlit) |
| C | Trần Xuân Vũ | `src/tools/`, `src/logging_utils/`, nodes `tool_*`/`confirm_gate`, `src/graph.py`, `src/llm.py`, `src/eval/`, `scripts/run_autoeval.py` |

---

## 1. Điểm hiện tại và chỗ mất điểm

| # | Mục | Điểm | Mất | Lý do giảng viên nêu |
|---|---|---|---|---|
| 1 | Perception | 4.1/5 | 0.9 | Khả năng hiểu câu khó của **LLM thật chưa được đo** |
| 2 | Memory | 4.2/5 | 0.8 | Chưa test **cô lập phiên** và **loại bỏ hoàn toàn kết quả cũ** |
| 3 | Reasoning & Planning | 8.9/10 | 1.1 | **Trọng số cố định**, không theo ưu tiên người dùng; luồng tìm NCC mới **còn trả null** |
| 4 | Action & Tool Use | 8.8/10 | 1.2 | Dữ liệu phần lớn mô phỏng, **crawl một lần**; **chưa xử lý an toàn khi kết quả rỗng** |
| 5 | Feedback & Evaluation | 6.8/10 | **3.2** | Số 100% chỉ đo lớp deterministic trên StubLLM; task success 64,71% **chưa chạy LLM thật**; **thiếu latency và chi phí** |
| | **Tổng** | **32.8/40** (8.2/10) | 7.2 | |

**Mục 5 mất nhiều nhất (3.2 điểm) và là ưu tiên số 1 của giảng viên.** Mọi việc khác phải phục vụ được cho báo cáo evaluation cuối cùng.

## 2. Đề xuất của giảng viên → việc cụ thể → người làm

| Đề xuất | Việc | Chính | Phụ |
|---|---|---|---|
| Chạy lại evaluation với LLM thật, vài chục case tiếng Việt tự nhiên | Bộ ~40 case real-LLM, chạy Gemini `--repeat 3` | C | A, B viết case |
| Tách chỉ số deterministic và chỉ số năng lực LLM | Báo cáo 2 tầng (mục 5.1 bên dưới) | C | — |
| Task success theo nhóm tình huống (đủ thông tin, thiếu, ngoài phạm vi, đổi ngân sách) | `aggregate()` chia theo `category` | C | — |
| Case tìm NCC mới trả null thành regression test | Tái hiện, sửa, thêm test + eval case | B (luồng rỗng), C (graph) | A (perceive) |
| Trọng số theo ưu tiên người dùng, hiển thị bộ trọng số đang dùng | Trích ưu tiên → preset trọng số → hiển thị | B | A (trích xuất) |
| 5–10 báo giá B2B thật | Thu thập, nạp vào dataset với `nguon_type` riêng, so với giá web | C | A, B mỗi người thu 3 báo giá |
| Kết quả rỗng: báo rõ + đề nghị nới điều kiện, nối với nhánh dừng an toàn | `diagnose`/`graceful_fail` sinh gợi ý nới ràng buộc | B | C (tool trả no_match có cấu trúc) |
| Làm mới dữ liệu theo lịch, lưu thời điểm cập nhật từng bản ghi | Script refresh + cảnh báo dữ liệu cũ | C | — |
| Dùng tracing báo cáo latency end-to-end, số lần gọi LLM/tool, p50/p95 | Mở rộng báo cáo AutoEval + load test | C | — |
| Test cô lập phiên, loại bỏ kết quả cũ | Bộ test memory mới | A | C (nếu lỗi nằm ở `confirm_gate`) |

## 3. Phát hiện khi đọc code (bằng chứng để bắt đầu)

Những điểm này tìm được khi đối chiếu nhận xét với repo; mỗi người kiểm tra lại phần của mình trước khi sửa.

1. **"Trả null" có dấu vết thật.** Trong `reports/demo_run_2026-09-22.json`, 5 lượt `needs_input` có `intent: null` và `hard_constraints: null`. Nguyên nhân: `guard_perceive` ở `src/graph.py` khi bắt `MissingFieldError`/`ValueError` chỉ trả `status` + `answer`, bỏ mất `intent` và phần constraint đã trích được (`exc.partial_state`). Ngoài ra cần thử thêm luồng `search_new` không có kết quả (xem mục 6.B.1) — đây có thể là case giảng viên thấy.
2. **Thông báo khi rỗng quá chung chung.** `graceful_fail` (`src/nodes/reasoning.py:230`) chỉ nói "Không tìm được nhà cung cấp thỏa mãn ràng buộc sau 3 lần lặp kế hoạch lại", không nói ràng buộc nào là nút thắt, không gợi ý nới.
3. **Trọng số cố định.** `WEIGHTS` ở `src/reasoning/scoring.py:15` (giá 0.30, MOQ 0.15, giao 0.20, bảo hành 0.15, uy tín 0.20); parser không có trường ưu tiên.
4. **Chi phí không đo được.** Lượt `needs_input` ghi `llm_calls: 1` nhưng `tokens_in/out: 0` (đường exception trong `guard_perceive` làm rơi token). `aggregate()` trong `src/eval/scoring.py` không tổng hợp token, chi phí, số tool call.
5. **Eval LLM thật cũ và nhỏ.** Lần chạy real duy nhất (`reports/autoeval_20260917_223157.md`) là 10 case × 1 lần, trước khi đổi sang dữ liệu `SRC###`. Hiện `tests/eval_set/cases_c.jsonl` có 19 case có oracle (slide ghi 17). `tests/eval_set/cases.jsonl` có 19 case cũ **không có `oracle`** nên runner bỏ qua hoàn toàn.
6. **Task success không chia theo nhóm.** `aggregate()` chỉ ra một con số tổng.
7. **Fan-out tool lớn.** Một request `search_new` gọi `get_supplier_detail` cho từng NCC (log thấy 29 tool call/request). Ảnh hưởng latency và Tool Call Success Rate.
8. **`reports/` nằm trong `.gitignore`.** Báo cáo mới sẽ không lên GitHub nếu không `git add -f`. Nộp bài cần báo cáo đi kèm.
9. **`fetched_at` đã có trên từng bản ghi** (`suppliers.json`) — phần "lưu thời điểm cập nhật" đã xong một nửa, chỉ thiếu dùng nó (cảnh báo dữ liệu cũ) và refresh theo lịch.

## 4. Nguyên tắc làm việc trong 14 ngày

- **Hợp đồng trước, code sau.** Các trường mới (mục 7) phải ghi vào `interface-contracts.md` và cả 3 người xác nhận trước khi code (`SYSTEM-RULES.md` §7).
- Mỗi người một nhánh (`hien/`, `linh/`, `vu/`), **merge vào `main` cuối mỗi phase**, không để nhánh trôi (bài học 13/09).
- Không hard-code case eval vào logic. Case là dữ liệu JSONL.
- Mỗi sửa lỗi kèm test hồi quy. Chạy `python -m unittest discover tests "test_*.py"` trước khi merge.
- Mọi con số trong báo cáo cuối phải dẫn được về một file trong `reports/` (đúng tinh thần citation của chính dự án).

## 5. Thiết kế evaluation mới (khung chung, C chịu trách nhiệm)

### 5.1 Báo cáo hai tầng

| Tầng | Đo cái gì | Chạy bằng | Chỉ số |
|---|---|---|---|
| **Tầng 1 — Kiểm thử pipeline (deterministic)** | Code có thực thi đúng quy tắc không | StubLLM + failure injection | Constraint Satisfaction, Citation Correctness, Failure Recovery, Tool Call Success |
| **Tầng 2 — Năng lực LLM thật** | Hệ thống có hiểu và trả lời đúng yêu cầu tiếng Việt tự nhiên không | Gemini (model ghi rõ trong báo cáo), `--repeat 3` | Perception field accuracy, Intent routing accuracy, Task Success **theo nhóm**, Không bịa số, latency p50/p95, LLM calls/request, tool calls/request, tokens/request, chi phí ước tính/request |

Báo cáo ghi rõ câu: *"Tầng 1 kiểm tra implementation, không chứng minh năng lực hiểu ngôn ngữ."* — đúng điều giảng viên yêu cầu diễn giải.

### 5.2 Bộ case real-LLM (~40 case, mỗi case 1 dòng JSONL có `oracle`)

| Nhóm (category) | Số case | Người viết |
|---|---|---|
| `full_info` — đủ thông tin | 6 | A |
| `missing_info` — thiếu thông tin | 5 | A |
| `budget_change` — đổi ngân sách/số lượng giữa chừng (nhiều lượt) | 5 | A |
| `hard_phrasing` — câu khó: "50tr", "2 tuần", "vài chục cái", không dấu, viết tắt, nhiều ý trong 1 câu | 6 | A |
| `priority` — người dùng nói rõ ưu tiên giá/tốc độ/chất lượng | 5 | B |
| `no_match` — không có phương án, phải gợi ý nới | 4 | B |
| `out_of_scope` | 3 | C |
| `adversarial` — prompt injection, ép chốt đơn | 3 | C |
| `tool_failure` — timeout/unavailable (inject) | 3 | C |

Câu nhập phải là câu tự nhiên do người viết, **không** chép từ prompt mẫu trong code. Mỗi người viết case của mình vào file riêng: `tests/eval_set/cases_a.jsonl`, `cases_b.jsonl`, `cases_c.jsonl` (runner đã đọc `cases*.jsonl`).

### 5.3 Chi phí API

40 case × 3 lần × ~2 lần gọi LLM ≈ 240 lần gọi. Với Gemini free tier cần throttle (C thêm `--sleep-between`), chạy tầng 2 **một lần duy nhất vào cuối phase 2**, các lần thử trước dùng `--repeat 1` trên tập con.

## 6. Kế hoạch từng người

### 6.A — Nguyễn Thị Hiền (Perception + Memory)

Mục tiêu: lấy lại 0.9 (Perception) + 0.8 (Memory).

**A.1 — Đo khả năng hiểu câu khó của LLM thật** *(Perception, ưu tiên cao)*
- Viết 22 case nhóm `full_info`, `missing_info`, `budget_change`, `hard_phrasing` (mục 5.2) vào `tests/eval_set/cases_a.jsonl`, mỗi case có `expected` cho từng trường `hard_constraints`/`soft_constraints`.
- Thêm oracle `must_extract` (C hỗ trợ grader) để chấm **field-level accuracy**: mỗi trường đúng/sai, tính riêng `product_type`, `quantity`, `budget_max`, `delivery_deadline_days`, soft fields.
- Chạy trên Gemini, ghi lại các câu parser sai → sửa prompt/normalize trong `src/perception/parser.py` (ví dụ "50tr" → 50000000, "2 tuần" → 14). **Không** thêm `if` cho câu cụ thể.
- Chuyển 19 case cũ trong `tests/eval_set/cases.jsonl` (không có oracle) sang dạng có oracle, hoặc ghi rõ trong README rằng file đó chỉ dành cho `tests/run_parse_and_memory.py`.
- Nghiệm thu: báo cáo tầng 2 có bảng accuracy theo từng trường, có ít nhất một ví dụ câu khó parser hiểu đúng và một ví dụ còn sai (nêu giới hạn).

**A.2 — Trích xuất ưu tiên người dùng** *(phục vụ B.2, cần chốt hợp đồng trước)*
- Thêm `soft_constraints.priority` (giá trị trong `{"price", "delivery", "quality", "balanced"}`, mặc định `"balanced"` và **ghi rõ là mặc định**, không tự đoán) — xem mục 7.
- Cập nhật prompt perceive để trích các cụm như "rẻ nhất có thể", "cần gấp", "ưu tiên chất lượng/bảo hành", "uy tín".
- Đổi ý giữa chừng ("thôi ưu tiên giao nhanh") phải **ghi đè** priority, đúng quy tắc overwrite hiện tại.
- Test: `tests/test_parse_memory_suite.py` thêm case trích priority + đổi priority ở lượt 2.

**A.3 — Test cô lập phiên và loại bỏ kết quả cũ** *(Memory)*
- Test 2 phiên xen kẽ (S1 lượt 1 → S2 lượt 1 → S1 lượt 2 đổi ngân sách → S2 lượt 2): kiểm tra `req`, `conversation_history`, `decisions_made` của S2 không bị S1 ảnh hưởng, kể cả khi cùng `product_type`.
- Test "kết quả cũ bị loại hoàn toàn": sau khi đổi ngân sách ở lượt 2, `ranked`/`candidates`/`pending_confirmation` của lượt 1 không còn xuất hiện; NCC vượt ngân sách mới không còn trong đề xuất; nếu người dùng nói "chốt" ở lượt 3 thì `confirm_gate` dùng xếp hạng mới chứ không dùng xếp hạng cũ.
- Test xóa phiên (`delete_session`) rồi dùng lại `session_id` → bắt đầu sạch.
- Nếu test lộ lỗi ở `confirm_gate` hoặc `graph.py` → báo C sửa, A giữ test.
- Thêm 2 case `budget_change` dạng AutoEval nhiều lượt để chỉ số này có trong báo cáo, không chỉ trong unit test.
- Nghiệm thu: test mới pass; báo cáo cuối có dòng "Session isolation: N/N".

**A.4 — Không còn `intent: null` ở lượt thiếu thông tin** *(cùng C)*
- Đảm bảo `MissingFieldError.partial_state` luôn mang `intent` và các constraint đã trích được; C dùng nó trong `guard_perceive`.
- Đảm bảo token của lần gọi LLM bị lỗi vẫn được trả về (để C cộng chi phí).

**A.5 — Thu 3 báo giá B2B thật** (xem C.4 về định dạng).

### 6.B — Vũ Hoàng Diệu Linh (Reasoning + Scoring + Respond + UI)

Mục tiêu: lấy lại 1.1 (Reasoning) và góp phần mục 4 (kết quả rỗng).

**B.1 — Sửa luồng tìm NCC mới trả null** *(ưu tiên cao nhất của B, làm ngày 1–3)*
- Tái hiện trước khi sửa: chạy `run_request` với (a) ràng buộc không thỏa ("100 sofa da thật, ngân sách 5 triệu, giao 2 ngày"), (b) loại sản phẩm có nhưng khu vực/chất liệu không có, (c) `search_suppliers` trả `no_match`, (d) câu thiếu thông tin. Ghi lại trường nào là `null`/`None` trong state cuối (`intent`, `ranked`, `answer`, `status`, `verdict`…).
- Viết test hồi quy **trước** khi sửa (`tests/test_no_match_flow.py`), test phải đỏ.
- Sửa để mọi nhánh kết thúc với `status` xác định + `answer` không rỗng; không có trường đầu ra quan trọng nào là `null` mà không giải thích.
- Thêm eval case `no_match` (mục 5.2).

**B.2 — Thông báo rõ khi không có phương án + gợi ý nới ràng buộc**
- Trong `diagnose`/`graceful_fail`: dùng `rejected` (lý do loại từng NCC) để đếm ràng buộc nào loại nhiều ứng viên nhất.
- Sinh gợi ý cụ thể, tính từ dữ liệu: ví dụ "Nếu tăng ngân sách lên X (giá thấp nhất hiện có × số lượng) thì có N nhà cung cấp phù hợp", "Nếu nới thời hạn giao lên Y ngày…". Mỗi con số trong gợi ý phải có `MaNCC` làm căn cứ.
- **Không tự nới** ràng buộc — chỉ đề nghị, người dùng quyết định (SYSTEM-RULES).
- Đưa gợi ý vào trường có cấu trúc (ví dụ `relax_suggestions`, xem mục 7) để UI và eval đọc được.
- Nghiệm thu: case `no_match` pass với oracle `must_suggest_relax: true`.

**B.3 — Trọng số theo ưu tiên người dùng**
- Thay `WEIGHTS` cố định bằng các preset (ví dụ, cần nhóm duyệt):

  | Preset | Giá | MOQ | Giao | Bảo hành | Uy tín |
  |---|---|---|---|---|---|
  | `balanced` (mặc định, = hiện tại) | 0.30 | 0.15 | 0.20 | 0.15 | 0.20 |
  | `price` | 0.45 | 0.15 | 0.15 | 0.10 | 0.15 |
  | `delivery` | 0.20 | 0.10 | 0.40 | 0.10 | 0.20 |
  | `quality` | 0.20 | 0.10 | 0.15 | 0.25 | 0.30 |

- Chọn preset theo `soft_constraints.priority` (A.2). Tổng trọng số luôn = 1; giữ cơ chế chuẩn hóa lại khi thiếu dữ liệu.
- Trả `weights_used` + tên preset trong state/kết quả (mục 7); prompt `respond` và Streamlit hiển thị bộ trọng số đang dùng và lý do chọn ("vì bạn nói *cần gấp*").
- Test: cùng một tập ứng viên, preset `price` và `delivery` cho thứ hạng khác nhau theo đúng hướng; preset mặc định cho kết quả giống hệt hiện tại (không làm hỏng demo cũ).
- Thêm 5 case `priority` (mục 5.2) với oracle kiểm tra preset được chọn.

**B.4 — Cập nhật slide và tài liệu reasoning**
- Slide 10: thêm dòng "Trọng số theo ưu tiên người dùng (4 preset), hiển thị trong câu trả lời".
- Slide 11: thay bảng 4 dòng hiện tại bằng bảng 2 tầng (lấy số từ báo cáo của C, không tự gõ).
- Cập nhật `docs/reasoning.md`, `BAO-CAO-HOAN-THIEN.md`.

**B.5 — Thu 3 báo giá B2B thật** (xem C.4).

### 6.C — Trần Xuân Vũ (Tools + Graph + Eval + Data)

Mục tiêu: lấy lại phần lớn 3.2 điểm Evaluation và 1.2 điểm Action & Tool Use. Là người tổng hợp báo cáo cuối.

**C.1 — Mở rộng AutoEval thành báo cáo 2 tầng** *(ưu tiên cao nhất, làm ngày 1–5)*
- `src/eval/scoring.py`:
  - `aggregate()` thêm `by_category` (task success, số case, số pass cho từng `category`).
  - Thêm grader cho oracle mới: `must_extract` (A.1), `must_suggest_relax` (B.2), `expect_priority` (B.3), `no_null_fields` (B.1).
  - Thêm intent routing accuracy (so `must_reach_intent` với intent thực tế) thành chỉ số riêng.
- `scripts/run_autoeval.py`:
  - Thêm `--tier {pipeline,llm}`; báo cáo ghi rõ tầng, model, ngày, `dataset_version`.
  - Thêm `--sleep-between` để không vượt rate limit Gemini.
  - Báo cáo thêm: tokens_in/out trung bình/request, chi phí ước tính/request (bảng giá model để trong một hằng số có ghi nguồn và ngày tra cứu), tool calls/request, p50/p95/max latency.
  - Markdown có bảng task success theo nhóm và phần "Diễn giải" cố định nói rõ tầng nào đo gì.
- Viết 9 case `out_of_scope`/`adversarial`/`tool_failure` mới cho tầng 2 (mục 5.2).
- Test: `tests/test_autoeval_metrics.py` thêm test cho `by_category`, chi phí, grader mới.

**C.2 — Sửa token/chi phí bị mất và `intent: null`** *(cùng A.4)*
- `guard_perceive` (`src/graph.py`): khi bắt exception, lấy `intent`, `req` tạm (từ `exc.partial_state`) và token của lần gọi LLM, thay vì chỉ trả `status`/`answer`.
- Kiểm tra `respond` và `perceive` đều cộng token đúng với Gemini và OpenRouter (`usage_of` trong `src/llm.py`).
- Test hồi quy: lượt `needs_input` có `intent` khác `None` và `tokens_in > 0` khi LLM giả trả usage.

**C.3 — Xử lý an toàn khi kết quả rỗng ở tầng tool** *(Action & Tool Use)*
- `tool_search`/`tool_compare`/`tool_detail` (`src/nodes/tools.py`): khi `search_suppliers` trả `no_match` hoặc danh sách rỗng, trả kèm thông tin có cấu trúc cho B (bộ lọc nào đã áp, số bản ghi trước/sau lọc) thay vì chỉ `candidates: []`.
- Đảm bảo `compare_price` không bao giờ được gọi với `supplier_ids=[]`.
- Gom `get_supplier_detail` thành một lần gọi batch (hoặc lấy detail từ kết quả search) để giảm ~29 tool call/request — giữ `args_schema` và shape lỗi theo hợp đồng.
- Test: `tests/test_node_tool_search.py` thêm case rỗng; eval case `C03_search_returns_empty` vẫn pass.

**C.4 — Dữ liệu: báo giá B2B thật + làm mới theo lịch**
- Định dạng nhập báo giá: thêm dòng vào `src/tools/mock_data/sources/` với `nguon_type="b2b_quote"`, ngày báo giá, số lượng hỏi, giá/đơn vị, MOQ, thời gian giao, bảo hành — **không** đưa số điện thoại/email cá nhân của người bán lên repo. Trường nào vẫn mô phỏng thì vẫn ghi vào `simulated_fields`.
- Mỗi người thu 3 báo giá (tổng 9, đủ khoảng 5–10 giảng viên gợi ý) cho cùng 1–2 mặt hàng có sẵn giá web (ví dụ ghế văn phòng 50 cái).
- Viết `reports/b2b_vs_web_<ngày>.md`: chênh lệch giá báo B2B so với giá web theo từng NCC; chạy pipeline trên các bản ghi này và ghi lại thứ hạng có đổi không.
- Làm mới dữ liệu: `scripts/refresh_sources.py` (dựa trên `scripts/verify_sources.py`) cập nhật `fetched_at`, ghi `VERSION` mới; hướng dẫn lập lịch bằng Windows Task Scheduler/cron trong README (không cần chạy server thật).
- Cảnh báo dữ liệu cũ: nếu `fetched_at` quá N ngày (cấu hình, mặc định 14), tool đánh dấu `stale: true` và `respond` nói "giá lấy ngày …, có thể đã thay đổi".
- Test: `tests/test_tools_source_fields.py` thêm case `stale`.

**C.5 — Latency và tải**
- Chạy lại `scripts/run_loadtest.py` (stub) cho 1/5/10 CCU, và tầng 2 có p50/p95 thật từ Gemini.
- Báo cáo tách: thời gian LLM vs thời gian tool vs tổng (đọc từ trace JSONL).

**C.6 — Tổng hợp, GitHub, phản hồi giảng viên**
- `reports/` đang bị `.gitignore` → `git add -f` các báo cáo cuối (chỉ file được trích trong tài liệu, không add cả thư mục log).
- Rà secret trước khi push: `.env` không bị track, log đã `redact()`, `.env.example` chỉ có giá trị mẫu.
- Cập nhật `README.md`: cách chạy 2 tầng eval, bảng kết quả mới, giới hạn còn lại.
- Viết `BAO-CAO-HOAN-THIEN.md`: bảng *Góp ý → Thay đổi → Bằng chứng (commit, test, file report)* cho từng ý của giảng viên.
- Soạn mail trả lời theo luồng cũ (cả nhóm duyệt trước khi gửi).

## 7. Thay đổi hợp đồng cần chốt (ngày 1–2, cả 3 người)

Ghi vào `interface-contracts.md` trước khi code:

| Trường | Ai ghi | Ai đọc | Mô tả |
|---|---|---|---|
| `soft_constraints.priority` | A | B | `"price" \| "delivery" \| "quality" \| "balanced"`; mặc định `"balanced"`, kèm cờ cho biết là mặc định hay người dùng nói |
| `weights_used` (state) | B | C (respond, eval), UI | `{"preset": str, "weights": {price, moq, delivery, warranty, trust}, "reason": str}` |
| `relax_suggestions` (state) | B | C (respond, eval), UI | Danh sách `{constraint, current, suggested, supplier_ids}`; rỗng nếu có kết quả |
| `tool_results[i].result.filter_stats` (khi rỗng) | C | B | Số bản ghi trước/sau từng bộ lọc |
| Record dataset: `stale` | C | B, respond | `true` nếu `fetched_at` quá ngưỡng |
| Oracle mới: `must_extract`, `must_suggest_relax`, `expect_priority`, `no_null_fields` | C | A, B (viết case) | Định nghĩa trong `src/eval/scoring.py` |

## 8. Lịch 14 ngày

| Phase | Ngày | Việc | Mốc kiểm tra |
|---|---|---|---|
| **0 — Chốt & tái hiện** | 08–09/10 | Họp 30 phút đọc nhận xét; chốt mục 7 vào `interface-contracts.md`; B tái hiện null (B.1); C chạy baseline tầng 2 hiện tại trên 19 case (`--repeat 1`) để có số "trước" | Hợp đồng có 3 xác nhận; có file report baseline |
| **1 — Sửa lõi** | 10–14/10 | A: A.2, A.3, A.4 · B: B.1, B.2 · C: C.1, C.2, C.3 · Cả nhóm: viết case JSONL (mục 5.2) | **Merge `main` 14/10**, full test suite pass |
| **2 — Tính năng & dữ liệu** | 15–18/10 | A: A.1 (sửa parser theo lỗi tầng 2) · B: B.3 · C: C.4, C.5 · Cả nhóm thu báo giá B2B | **Merge `main` 18/10**; 18/10 chạy tầng 2 đầy đủ `--repeat 3` |
| **3 — Báo cáo & nộp** | 19–22/10 | B: B.4 slide · C: C.6 · A: rà README phần perception/memory · Cả nhóm: rà `BAO-CAO-HOAN-THIEN.md` | 21/10 cả nhóm duyệt; 22/10 push GitHub + gửi mail |

Dự phòng: nếu Gemini hết quota, chạy tầng 2 bằng OpenRouter (đã có provider) và ghi rõ model trong báo cáo; không quay về StubLLM cho tầng 2.

## 9. Định nghĩa "xong" trước khi gửi mail

- [ ] Không còn trường `null` không giải thích trong state cuối ở mọi nhánh (có test hồi quy).
- [ ] Kết quả rỗng → câu trả lời nói rõ ràng buộc nào là nút thắt + gợi ý nới có số liệu dẫn nguồn.
- [ ] Trọng số đổi theo ưu tiên người dùng và hiển thị trong câu trả lời + UI.
- [ ] Test cô lập phiên và loại bỏ kết quả cũ pass.
- [ ] Báo cáo tầng 2 trên LLM thật, ~40 case × 3 lần: task success theo nhóm, field accuracy, intent accuracy, p50/p95, LLM/tool calls, tokens, chi phí ước tính.
- [ ] Báo cáo tầng 1 ghi rõ là kiểm thử implementation.
- [ ] 5–10 báo giá B2B thật trong dataset + báo cáo so sánh với giá web.
- [ ] Mọi bản ghi có `fetched_at`; có script refresh và cảnh báo dữ liệu cũ.
- [ ] `python -m unittest discover tests "test_*.py"` pass toàn bộ trên `main`.
- [ ] Không có secret trong repo/log; báo cáo cuối được `git add -f`.
- [ ] `BAO-CAO-HOAN-THIEN.md` map đủ từng ý nhận xét → bằng chứng.

## 10. Rủi ro

| Rủi ro | Ảnh hưởng | Cách xử lý |
|---|---|---|
| Kết quả tầng 2 thấp hơn số cũ | Trông "tệ hơn" | Đây là điều giảng viên muốn thấy: con số thật + phân tích lỗi theo nhóm. Báo cáo đủ "trước/sau" sửa parser |
| Rate limit / quota Gemini | Không chạy đủ 3 lần | Chạy sớm baseline, `--sleep-between`, dự phòng OpenRouter |
| Không xin được báo giá B2B | Thiếu mục dữ liệu thật | Bắt đầu xin từ phase 0 (cần vài ngày phản hồi); nếu thiếu, ghi rõ số đã thu và lý do |
| Đổi hợp đồng làm vỡ code người khác | Merge conflict như 13/09 | Chốt mục 7 trước, merge cuối mỗi phase, giữ preset `balanced` = trọng số cũ |
| Thêm `priority` làm hỏng demo cũ | Demo chạy khác | Mặc định `balanced` cho kết quả giống hệt hiện tại (có test) |
