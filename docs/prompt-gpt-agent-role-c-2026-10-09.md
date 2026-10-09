# Prompt cho GPT agent — hoàn thiện phần việc của Người C (Trần Xuân Vũ)

Ngày lập: 2026-10-09. Kế hoạch gốc: [ke-hoach-hoan-thien-sau-cham-diem-2026-10-08.md](ke-hoach-hoan-thien-sau-cham-diem-2026-10-08.md), mục 6.C.

## 1. Cấu hình chạy

| Mục | Giá trị khuyến nghị | Ghi chú |
|---|---|---|
| Công cụ | **OpenAI Codex CLI** (`codex`) chạy ở thư mục gốc repo | Cần agent đọc/sửa file và chạy lệnh, không dùng ChatGPT web |
| Model | **`gpt-5.2-codex`** hoặc model *-codex mới nhất mà tài khoản có trong `/model` | Chọn bản Codex vì chuyên sửa repo nhiều file. Nếu không có bản Codex thì dùng `gpt-5.2` |
| Reasoning effort | **`high`** cho Đợt 1–2 (graph, eval) · **`medium`** cho Đợt 3–4 (dữ liệu, tài liệu) | `xhigh` chỉ khi agent sửa sai 2 lần liên tiếp cùng một test. `low` không đủ cho việc đọc nhiều module |
| Sandbox | `workspace-write` | Agent chỉ ghi trong repo |
| Approval | `on-request` | Duyệt tay khi agent xin chạy lệnh ra ngoài sandbox |
| Mạng | Tắt | Không cần mạng: mọi test chạy StubLLM. Eval LLM thật **bạn tự chạy** |

Lưu ý: tên model đổi nhanh. Mở `/model` trong Codex để xem danh sách thật của tài khoản. Dùng bản mới nhất thuộc dòng Codex, mức reasoning như trên.

Lệnh mở phiên (PowerShell, tại thư mục gốc repo):

```bash
codex --model gpt-5.2-codex -c model_reasoning_effort="high" --sandbox workspace-write --ask-for-approval on-request
```

## 2. Việc cần làm trước khi dán prompt

1. Đang có thay đổi chưa commit trong `src/graph_state.py` (xóa 2 comment) và `.env.example`. Hãy commit hoặc `git stash` chúng trước để agent không trộn vào commit của nó.
2. Kiểm tra `.env` không bị track: `git ls-files .env` phải không in gì.
3. Chạy test một lần để biết trạng thái hiện tại: `python -m unittest discover tests "test_*.py"`.
4. Chạy theo **4 đợt** (mục 4). Mỗi đợt dán prompt chung (mục 3) **một lần đầu phiên**, sau đó dán prompt của đợt. Hết đợt thì đọc báo cáo của agent, chạy lại test, rồi mới sang đợt tiếp theo. Nên mở phiên mới cho mỗi đợt để context gọn.

---

## 3. Prompt chung (dán đầu mỗi phiên)

````text
Bạn là kỹ sư phần mềm làm việc trong repo Python "Procurement-Intelligence-Negotiation-Agent" (đồ án cuối khóa AI Guru AEF1, nhóm 3 người). Tôi là Người C (Trần Xuân Vũ). Nhiệm vụ: hoàn thiện phần việc của Người C theo nhận xét của giảng viên. Trả lời tôi bằng tiếng Việt; code, tên hàm, commit message giữ tiếng Anh. Comment trong code viết tiếng Việt không dấu như code hiện có.

## Đọc trước khi làm (bắt buộc, theo thứ tự)
1. CLAUDE.md — quy ước dự án, lệnh chạy, bảng sở hữu module.
2. docs/ke-hoach-hoan-thien-sau-cham-diem-2026-10-08.md — kế hoạch. Phần của bạn là mục 6.C, mục 5 (thiết kế eval), mục 7 (hợp đồng), mục 9 (định nghĩa xong).
3. interface-contracts.md — NGUỒN SỰ THẬT cho mọi field/action giữa các module.
4. SYSTEM-RULES.md và architecture.md (mục 2 và 5).
5. Các file bạn sẽ sửa: src/graph.py, src/nodes/tools.py, src/nodes/respond.py, src/tools/supplier_tools.py, src/tools/dataset_builder.py, src/eval/scoring.py, scripts/run_autoeval.py, scripts/run_loadtest.py, src/logging_utils/tracer.py, src/llm.py, và test tương ứng trong tests/.

## Ranh giới sở hữu (KHÔNG được vi phạm)
Bạn CHỈ được sửa: src/tools/, src/logging_utils/, src/graph.py, src/graph_state.py, src/llm.py, src/agent.py, src/nodes/tools.py, src/nodes/tool_exec.py, src/nodes/respond.py (chỉ phần wiring, KHÔNG sửa nội dung prompt), src/eval/, scripts/, tests/ (file test của C hoặc file test mới), tests/eval_set/cases_c*.jsonl, generate_mock_data.py, README.md, docs/.

Bạn KHÔNG được sửa: src/perception/, src/memory/, src/reasoning/ (kể cả prompts.py), src/nodes/perceive.py, src/nodes/reasoning.py, app.py, src/ui_viewmodel.py. Nếu việc của bạn cần thay đổi ở đó, KHÔNG sửa. Ghi yêu cầu cụ thể (file, hàm, input/output mong muốn, test đề xuất) vào docs/handoff-c-to-ab-2026-10.md, rồi làm phần của mình theo cách chịu được khi phía A/B chưa xong (đọc field bằng .get(), thiếu thì báo "không đo được", không crash).

## Quy tắc dự án (bắt buộc)
- interface-contracts.md: field MỚI chỉ được thêm vào một mục "ĐỀ XUẤT 2026-10 — chờ A/B xác nhận" ở cuối file. Không đổi tên hay xóa field cũ.
- Không hard-code input mẫu hay id case eval vào logic (`if case_id == ...` bị cấm). Case eval là dữ liệu JSONL.
- Không tự điền thông tin thiếu, không tự nới ràng buộc. Mọi con số trong câu trả lời phải truy được về kết quả tool kèm MaNCC và nguon_url.
- Lỗi tool luôn theo shape {"error": true, "error_type": "no_match|timeout|invalid_input|tool_unavailable", "message": "..."}. Lỗi một phần tử trong batch chỉ làm lỗi phần tử đó.
- Giữ nguyên các `args_schema` Pydantic (là bằng chứng chấm điểm).
- Mọi payload ghi log phải qua `redact()`. Không in, không ghi, không commit API key.
- Thời gian ISO 8601. Tiền VND là số thuần.
- KHÔNG BAO GIỜ bịa số liệu: không bịa báo giá B2B, không bịa giá token của model, không bịa kết quả eval. Chỗ nào cần số thật mà chưa có thì để placeholder `TODO(C): ...` và báo tôi.

## Cách làm việc
- Môi trường: Windows, PowerShell, venv ở .venv. Python: `.venv\Scripts\python.exe`.
- Test là stdlib unittest, KHÔNG có pytest. Chạy toàn bộ: `.venv\Scripts\python.exe -m unittest discover tests "test_*.py"` (không dùng `-s tests -t .`). Chạy một module: `.venv\Scripts\python.exe -m unittest tests.test_xxx -v`.
- Mọi lần chạy pipeline/eval đều dùng StubLLM và tắt độ trễ giả lập: đặt `$env:AGENT_LLM="stub"; $env:AGENT_STUB_LATENCY_MEAN_S="0"; $env:AGENT_STUB_LATENCY_STDDEV_S="0"`. KHÔNG chạy với LLM thật (tốn quota, cần key). Eval LLM thật tôi tự chạy.
- TDD: với mỗi lỗi hoặc tính năng, viết test trước, chạy cho thấy test ĐỎ, rồi mới sửa cho XANH.
- Trước mỗi commit, toàn bộ suite phải pass. Nếu có test đỏ từ trước, báo tôi, không tự sửa test của người khác cho xanh.
- Làm trên nhánh `c/hoan-thien-2026-10`, tạo từ `main` nếu chưa có. Mỗi việc một commit, Conventional Commits (`fix(graph): ...`, `feat(eval): ...`). Dùng `git add <file cụ thể>`, không `git add -A`. KHÔNG push, KHÔNG merge vào main, KHÔNG sửa git config.
- `reports/` và `logs/` đang bị .gitignore. Chỉ `git add -f` file report khi tôi yêu cầu.
- Gặp quyết định thiết kế không có trong kế hoạch: chọn phương án đơn giản nhất phù hợp hợp đồng, ghi lý do vào báo cáo cuối đợt. Chỉ dừng hỏi khi bắt buộc phải sửa file ngoài quyền hoặc đổi field hợp đồng đã có.

## Báo cáo cuối mỗi đợt (bắt buộc)
1. Danh sách commit (hash + message).
2. Số test trước và sau (lấy từ output thật, không ước lượng).
3. Mỗi mục của đợt: Xong / Một phần / Chưa, kèm lý do.
4. Yêu cầu đã ghi cho A/B trong docs/handoff-c-to-ab-2026-10.md.
5. Việc cần tôi làm tay (điền số, chạy LLM thật, thu báo giá...).

Đọc xong thì trả lời ngắn: tóm tắt 5 dòng hiểu biết của bạn về kiến trúc và phạm vi của C. Sau đó chờ prompt của đợt.
````

---

## 4. Prompt từng đợt

### Đợt 1 — Sửa lõi graph và tool (effort `high`)

````text
ĐỢT 1: thực hiện mục C.2 và C.3 trong kế hoạch.

### Việc 1.1 — Không còn `intent: null` và không mất token ở lượt thiếu thông tin (C.2)
Bằng chứng: trong reports/demo_run_2026-09-22.json, 5 lượt có status "needs_input" mang `intent: null`, `hard_constraints: null`, `tokens_in: 0` dù `llm_calls: 1`. Nguyên nhân: `guard_perceive` trong src/graph.py khi bắt MissingFieldError / InvalidProductTypeError / ValueError chỉ trả status + answer + llm_calls.
- Viết test trước (tests/test_graph_perceive_guard.py hoặc file mới): node perceive giả ném MissingFieldError có `partial_state` chứa intent/hard_constraints → state cuối phải có `intent` khác None (nếu partial_state có), có `req` tạm, và token được cộng nếu exception mang thông tin token.
- Sửa `guard_perceive`: đọc `getattr(exc, "partial_state", None)` và các thuộc tính token nếu có (getattr an toàn). Không sửa src/perception/. Nếu exception của A không mang token, ghi yêu cầu vào docs/handoff-c-to-ab-2026-10.md (đề xuất A gắn `tokens_in/tokens_out` vào exception), phía C xử lý được cả khi chưa có.
- Kiểm tra `usage_of` trong src/llm.py và cách perceive/respond cộng token cho Gemini và OpenRouter (dùng mock message có `usage_metadata`). Thêm test nếu chưa có.

### Việc 1.2 — Kết quả rỗng an toàn ở tầng tool (C.3)
- Trong src/nodes/tools.py, khi `search_suppliers` trả `no_match` hoặc danh sách rỗng: trả thêm thông tin có cấu trúc để Người B dùng gợi ý nới ràng buộc. Đề xuất field `filter_stats` (bộ lọc đã áp: product_type, material, region; số bản ghi khớp product_type trước khi lọc material/region; số còn lại sau từng bộ lọc). Đây là field mới → thêm vào mục ĐỀ XUẤT của interface-contracts.md, không tự coi là đã chốt. Có thể cần sửa src/tools/supplier_tools.py để lỗi `no_match` mang thêm field này; shape lỗi chung vẫn giữ nguyên các key cũ.
- Bảo đảm `compare_price` không bao giờ được gọi với `supplier_ids=[]` (test).
- Rà mọi nhánh return trong tool_search/tool_compare/tool_detail: state cuối của cả request không được có `status` None hoặc `answer` rỗng. Viết test end-to-end bằng `run_request(...)` với stub và `overrides` (xem tests/test_graph_e2e_stub.py) cho: search no_match, search rỗng, compare toàn id lỗi, detail id không tồn tại. Thông báo cuối do `graceful_fail` của B sinh. Bạn chỉ kiểm tra nó không rỗng/không None, không sửa nội dung thông báo.
- Eval case C03_search_returns_empty trong tests/eval_set/cases_c.jsonl phải vẫn pass. Kiểm tra bằng `.venv\Scripts\python.exe scripts/run_autoeval.py --eval-set tests/eval_set/cases_c.jsonl --llm stub --out-dir <thư mục tạm ngoài repo>`.

### Việc 1.3 (tùy chọn, chỉ làm khi 1.1–1.2 xong và không phải đổi hợp đồng) — Giảm fan-out tool
Hiện một request search_new gọi get_supplier_detail riêng cho từng NCC (~29 tool call/request). Tìm cách giảm mà KHÔNG đổi input/output của 4 tool hiện có trong interface-contracts.md. Nếu bắt buộc phải đổi hợp đồng (ví dụ thêm tool batch), chỉ ghi đề xuất vào mục ĐỀ XUẤT và báo lại, không code.

Kết thúc: báo cáo theo mẫu ở prompt chung.
````

### Đợt 2 — AutoEval hai tầng (effort `high`)

````text
ĐỢT 2: thực hiện mục C.1 và thiết kế eval ở mục 5 của kế hoạch. Đây là phần quan trọng nhất: mục Evaluation mất 3.2/10 điểm vì các số 100% chỉ đo lớp deterministic trên StubLLM, không có số LLM thật theo nhóm tình huống, thiếu latency và chi phí.

### Việc 2.1 — Phân tầng case
- Thêm field `tier` cho mỗi case: `"pipeline"`, `"llm"` hoặc `["pipeline","llm"]`. Quy tắc: case có `inject` → `pipeline`; case mà kết quả phụ thuộc LLM hiểu câu (out_of_scope, adversarial, happy_path, missing_info, multi_turn) → có `llm`. Áp cho 19 case trong tests/eval_set/cases_c.jsonl. Case thiếu `tier` mặc định là cả hai, để file case của A/B viết sau không bị bỏ qua.
- `scripts/run_autoeval.py`: thêm `--tier {pipeline,llm,all}` (mặc định all) để lọc case. Thêm `--sleep-between <giây>` (mặc định 0) để chạy LLM thật không vượt rate limit.
- tests/eval_set/cases.jsonl (19 case cũ không có oracle) đang bị runner bỏ qua im lặng. Thêm dòng cảnh báo in ra số case bị bỏ qua và tên file. Không xóa file đó (thuộc A).

### Việc 2.2 — Chỉ số mới trong src/eval/scoring.py
- `aggregate()` thêm `by_category`: với mỗi `category` có số case, số pass, task_success_rate.
- Thêm `intent_routing_accuracy`: tỉ lệ case có `must_reach_intent` mà intent thực tế khớp.
- Thêm thống kê vận hành: avg/p50/p95/max của latency_ms; avg llm_calls, tool_calls, tokens_in, tokens_out mỗi request; chi phí ước tính mỗi request và tổng.
- Chi phí: bảng giá đặt trong một hằng số/dict theo tên model (USD/1M token input, output) KÈM nguồn và ngày tra cứu. KHÔNG điền giá từ trí nhớ: để `None` + `TODO(C): điền giá từ trang pricing chính thức`. Khi giá là None, báo cáo ghi "chưa cấu hình giá" cho chi phí nhưng vẫn in token.
- Grader cho oracle mới (mục 7 kế hoạch). Field phía A/B chưa có thì grader trả "không đo được" cho case đó, không crash:
  - `no_null_fields: [list field]` — các field trong state cuối không được None/rỗng.
  - `must_extract: {hard_constraints: {...}, soft_constraints: {...}}` — so từng field với `final["req"]`. Tính thêm chỉ số `field_accuracy` = số field đúng / tổng field được kiểm, và chi tiết theo tên field.
  - `expect_priority: "price|delivery|quality|balanced"` — so với `final["weights_used"]["preset"]` (field B sẽ thêm).
  - `must_suggest_relax: true` — `final["relax_suggestions"]` (field B sẽ thêm) phải là list không rỗng.
- Test cho từng thứ trên trong tests/test_autoeval_metrics.py (hoặc file mới) bằng dữ liệu kết quả giả, không chạy pipeline thật.

### Việc 2.3 — Báo cáo markdown hai tầng
- Header ghi: tầng, llm_mode, tên model (đọc từ env đúng như src/llm.py chọn provider, KHÔNG ghi key), dataset_version, số case, số lần lặp, ngày giờ ISO 8601.
- Bảng "Tầng 1 — Kiểm thử pipeline": constraint_satisfaction, citation_correctness, failure_recovery, tool_call_success.
- Bảng "Tầng 2 — Năng lực LLM": task_success theo nhóm (by_category), intent_routing_accuracy, field_accuracy, no-invented-numbers.
- Bảng "Vận hành": latency p50/p95/max, LLM calls, tool calls, tokens, chi phí.
- Mục "Diễn giải" cố định, nói rõ: số tầng 1 kiểm tra implementation, KHÔNG chứng minh năng lực hiểu ngôn ngữ; số tầng 2 chỉ có giá trị khi llm_mode=real. Khi chạy stub mà chọn tầng llm, in cảnh báo to ở đầu báo cáo.
- Giữ phần spread (min/max/stdev) khi --repeat > 1, mở rộng cho chỉ số mới.
- JSON report chứa đủ mọi số trên (các tài liệu sau sẽ trích từ JSON).

### Việc 2.4 — 9 case tầng 2 của C
Viết vào tests/eval_set/cases_c_llm.jsonl: 3 `out_of_scope`, 3 `adversarial` (prompt injection, ép chốt đơn ngay lượt đầu, đòi số liệu hệ thống không có), 3 `tool_failure` (có inject). Câu nhập tiếng Việt CÓ DẤU, tự nhiên, đa dạng cách nói. Không chép câu đã có trong cases_c.jsonl hay trong code. Mỗi case có oracle đầy đủ theo grader hiện có.

### Kiểm tra cuối đợt
- Chạy `scripts/run_autoeval.py --eval-set tests/eval_set --llm stub --tier all --out-dir <thư mục tạm ngoài repo>` (stub, latency 0). Dán markdown report vào báo cáo cho tôi xem. Ghi chú: số tầng 2 trên stub không có giá trị đánh giá.
- In ra lệnh chính xác để tôi tự chạy LLM thật sau này, ví dụ: `python scripts/run_autoeval.py --eval-set tests/eval_set --llm real --tier llm --repeat 3 --sleep-between 4`.
````

### Đợt 3 — Dữ liệu: dữ liệu cũ, làm mới, báo giá B2B (effort `medium`)

````text
ĐỢT 3: thực hiện mục C.4 của kế hoạch.

### Việc 3.1 — Cảnh báo dữ liệu cũ
- Mọi bản ghi trong src/tools/mock_data/suppliers.json đã có `fetched_at`. Thêm ngưỡng cấu hình qua env `DATA_STALE_DAYS` (mặc định 14). Tool trả kèm `stale: true/false` cho từng NCC trong search_suppliers / get_supplier_detail / compare_price. So sánh với ngày hiện tại phải inject được (tham số hoặc hàm `_today()` để test). Không dùng ngày cứng.
- `stale` là field mới → thêm vào mục ĐỀ XUẤT trong interface-contracts.md.
- Trong src/nodes/respond.py (phần wiring của C, KHÔNG sửa prompt trong src/reasoning/prompts.py): nếu NCC được khuyến nghị có `stale: true`, nối thêm một câu cảnh báo deterministic sau câu trả lời của LLM, ví dụ "Lưu ý: giá của <MaNCC> lấy ngày <fetched_at>, có thể đã thay đổi." Không gọi thêm LLM.
- Test: tests/test_tools_source_fields.py (và test respond) cho bản ghi mới, bản ghi cũ, bản ghi thiếu fetched_at (coi là stale, ghi rõ lý do).

### Việc 3.2 — Làm mới dữ liệu theo lịch
- Tạo scripts/refresh_sources.py bọc quy trình đang có: chạy logic của scripts/verify_sources.py (--apply), rồi generate_mock_data.py, cập nhật src/tools/mock_data/VERSION. Có cờ `--dry-run`. Script cần mạng nên trong phiên này CHỈ viết code và test với HTML cache/mocked fetch, KHÔNG chạy thật.
- README: thêm mục hướng dẫn lập lịch bằng Windows Task Scheduler (schtasks) và cron. Chỉ hướng dẫn, không tạo task thật trên máy.

### Việc 3.3 — Khung nạp báo giá B2B thật
Báo giá do người trong nhóm thu thập tay. Bạn TUYỆT ĐỐI KHÔNG tạo báo giá, giá hay NCC giả.
- Tạo src/tools/mock_data/sources/b2b_quotes_template.csv chỉ có header và 1 dòng chú thích. Cột: các cột schema nguồn hiện có (xem src/tools/mock_data/sources/README.md và src/tools/dataset_builder.py) + `quote_date`, `quote_quantity`, `quote_channel` (email/zalo/phone/web_form). Cột liên hệ cá nhân (số điện thoại, email người bán) KHÔNG được có.
- dataset_builder: chấp nhận `nguon_type="b2b_quote"`, validate các cột mới, các trường nghiệp vụ không có trong báo giá vẫn phải vào `simulated_fields`. Test bằng fixture CSV trong tests/ (fixture ghi rõ là dữ liệu test, tên NCC dạng "TEST_*"; fixture này không được vào suppliers.json).
- Tạo scripts/compare_b2b_vs_web.py: với mỗi dòng b2b_quote, tìm bản ghi web cùng NCC/sản phẩm, xuất reports/b2b_vs_web_<ngày>.md gồm giá web, giá báo B2B, chênh lệch %, và thứ hạng của NCC đó khi chạy pipeline (stub) với giá web và với giá B2B. Khi chưa có báo giá thật, script in "chưa có báo giá b2b_quote nào" và thoát mã 0.
- Ghi vào docs/handoff-c-to-ab-2026-10.md hướng dẫn ngắn cho A và B: mỗi người thu 3 báo giá theo template, điền vào đâu, không ghi thông tin cá nhân người bán.
````

### Đợt 4 — Latency, tổng hợp, tài liệu (effort `medium`)

````text
ĐỢT 4: thực hiện mục C.5 và C.6 của kế hoạch.

### Việc 4.1 — Tách latency theo thành phần
- Từ trace JSONL trong logs/ (src/logging_utils/tracer.py), tính cho mỗi request: thời gian LLM (perceive + respond), tổng thời gian tool, phần còn lại. Nếu tracer chưa ghi đủ mốc thời gian để tính, thêm field vào `write_run_record` (ví dụ `llm_ms`, `tool_ms`). Đây là log nội bộ của C, không phải hợp đồng.
- Báo cáo AutoEval (đợt 2) thêm p50/p95 cho llm_ms và tool_ms.
- scripts/run_loadtest.py: thêm các field này vào báo cáo. Chạy stub 1/5/10 CCU với số request nhỏ, lưu report vào thư mục tạm ngoài repo, dán tóm tắt vào báo cáo cho tôi.

### Việc 4.2 — Tài liệu tổng hợp
- README.md: cập nhật cách chạy eval hai tầng, ý nghĩa từng tầng, lệnh refresh dữ liệu, lập lịch, nạp báo giá B2B, mục "Giới hạn còn lại" trung thực.
- Tạo BAO-CAO-HOAN-THIEN.md ở thư mục gốc: bảng "Nhận xét của giảng viên → Thay đổi → Bằng chứng (commit, file test, file report)". Liệt kê ĐỦ các ý trong mục 1–2 của kế hoạch, kể cả ý của A và B (cột trạng thái để "chờ A"/"chờ B" nếu chưa có). Mọi con số eval để placeholder `TODO(C): lấy từ reports/autoeval_<...>.json sau khi chạy LLM thật`. Không điền số từ lần chạy stub vào cột kết quả LLM.
- Rà secret: tìm trong toàn bộ file được track các chuỗi giống API key (`AIza`, `sk-`, `OPENROUTER_API_KEY=` có giá trị thật, `GOOGLE_API_KEY=` có giá trị thật). Báo kết quả. Không tự xóa lịch sử git.
- Liệt kê đường dẫn các file report cuối nên `git add -f` để tôi quyết định.
- Soạn nháp email trả lời giảng viên vào docs/draft-email-phan-hoi-2026-10.md (tiếng Việt, ngắn, liệt kê thay đổi chính và link repo GitHub https://github.com/TranVu2005/Procurement-Intelligence-Negotiation-Agent). KHÔNG gửi.

Kết thúc: báo cáo theo mẫu, kèm danh sách việc còn mở của cả 3 người theo mục 9 "Định nghĩa xong" của kế hoạch.
````

---

## 5. Sau khi agent chạy xong, bạn tự làm

1. Đọc diff từng commit (`git log -p main..c/hoan-thien-2026-10`), chạy lại toàn bộ test.
2. Gửi A và B file `docs/handoff-c-to-ab-2026-10.md` và các field trong mục ĐỀ XUẤT của `interface-contracts.md` để cả hai xác nhận.
3. Điền bảng giá token từ trang pricing chính thức (ghi ngày tra cứu).
4. Khi A và B đã merge phần của họ: chạy eval LLM thật bằng lệnh agent in ra ở đợt 2 (`--repeat 3`), điền số vào `BAO-CAO-HOAN-THIEN.md`, `git add -f` report cuối.
5. Merge vào `main` cuối mỗi phase theo lịch ở mục 8 của kế hoạch, push và gửi mail sau khi cả nhóm duyệt.
