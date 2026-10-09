# Procurement Intelligence & Negotiation Agent — Nội thất

Dự án cuối khóa AI Guru AEF1. Agent nhận yêu cầu mua sắm nội thất bằng tiếng
Việt tự nhiên, tìm/so sánh nhà cung cấp mock, và đề xuất chiến lược đàm phán
kèm leverage score.

Ba tài liệu chi phối, theo thứ tự ưu tiên:

- [interface-contracts.md](interface-contracts.md) — nguồn sự thật cho mọi
  field/action trao đổi giữa 3 module.
- [SYSTEM-RULES.md](SYSTEM-RULES.md) — rule hành vi chung.
- [architecture.md](architecture.md) — thiết kế pipeline đã thống nhất.

## Kiến trúc

Pipeline là **LangGraph `StateGraph`** xác định (không còn ReAct
`AgentExecutor`), LLM chỉ được gọi ở 2 node `perceive` và `respond` — mọi node
khác là Python thuần. Entrypoint: `src/graph.py::run_request()`; `src/agent.py`
chỉ là REPL mỏng gọi hàm này.

3 nhánh intent dùng chung scoring/verification: `search_new`
(`plan → tool_search → filter_hard → score_rank → verify_output`),
`compare_specific` (`tool_compare`), `supplier_detail` (`tool_detail`),
`out_of_scope` (`respond_limits`). Khi `verify_output` fail, `diagnose` +
`replan` chạy tối đa 3 lần trước khi `graceful_fail`.

| Module | Owner |
|---|---|
| `src/perception/`, `src/memory/`, node `perceive` | Người A |
| `src/reasoning/`, node `plan`/`filter_hard`/`score_rank`/`verify_output`/`diagnose`/`replan` | Người B |
| `src/tools/`, `src/logging_utils/`, node `tool_*`/`confirm_gate`, wiring `respond` | Người C |
| `src/agent.py`, `src/graph.py`, `src/graph_state.py`, `src/llm.py` | Người C |

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows; POSIX: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # điền GOOGLE_API_KEY
```

Không có `GOOGLE_API_KEY` thật vẫn chạy được: set `AGENT_LLM=stub` để dùng
`StubLLM` (không gọi mạng, trả JSON/text cố định) cho cả perceive lẫn respond.

```bash
# PowerShell
$env:AGENT_LLM="stub"
# POSIX
export AGENT_LLM=stub
```

## Dùng OpenRouter (free) thay vì Gemini

Không muốn xin `GOOGLE_API_KEY` mà vẫn muốn LLM thật (không phải stub): set
`LLM_PROVIDER=openrouter` + `OPENROUTER_API_KEY` (lấy miễn phí tại
[openrouter.ai/keys](https://openrouter.ai/keys), không cần thẻ). `AGENT_LLM=stub`
vẫn thắng tuyệt đối nếu set — bỏ biến đó đi để dùng OpenRouter thật.

```bash
# PowerShell
$env:LLM_PROVIDER="openrouter"
$env:OPENROUTER_API_KEY="sk-or-..."
# POSIX
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY=sk-or-...
```

Model mặc định: `openrouter/free` (auto-router giữa các model free, tránh bị
kẹt khi 1 model cụ thể bị rate-limit — đã gặp `google/gemma-4-31b-it:free`
kẹt `429` shared pool khi test 2026-09-17). Đổi bằng `OPENROUTER_MODEL`.
Model free khác đáng cân nhắc (data live từ `openrouter.ai/api/v1/models`,
kiểm tra 2026-09-17 — danh sách free của OpenRouter đổi liên tục, kiểm tra
lại trước khi dùng lâu dài):

| Model | Context | Ghi chú |
|---|---|---|
| `openrouter/free` (default) | 200K | Auto-router giữa các model free — không bị kẹt khi 1 model cụ thể hết quota/rate-limit |
| `google/gemma-4-31b-it:free` | 262K | Đa ngôn ngữ mạnh, cùng họ Google với Gemini đang dùng; nhưng shared pool dễ bị `429` giờ cao điểm |
| `z-ai/glm-5.2:free` | 32K | JSON/tool-use tốt nhưng context ngắn — rủi ro với prompt dài của project |
| `nvidia/nemotron-3-super-120b-a12b:free` | 262K | Model lớn hơn, lý luận mạnh hơn, chậm hơn |

Free tier OpenRouter giới hạn 20 request/phút, 50 request/ngày (không nạp
credit) hoặc 1000 request/ngày (đã nạp tối thiểu $10).

## Chạy agent (REPL)

```bash
python -m src.agent
```

## Chạy giao diện web

```bash
streamlit run app.py
```

Giao diện giữ lịch sử theo session, hiển thị bảng xếp hạng, link nguồn, trường
mô phỏng, trace/metric và nút xác nhận chốt đơn. Cấu hình LLM vẫn đọc từ
`.env` giống REPL; không đưa API key vào giao diện hoặc commit lên Git.

## Chạy test

```bash
# Toàn bộ test suite — PHẢI chạy -s tests -t . (tests/ không có __init__.py,
# "-s tests -t ." khác sẽ lỗi ImportError: Start directory is not importable)
python -m unittest discover tests "test_*.py"

# Một module test riêng
python -m unittest tests.test_tools -v
```

Test dùng `unittest` chuẩn (không phải pytest — pytest không có trong
`requirements.txt`). Không có linter wired sẵn.

## Dữ liệu mock

```bash
python generate_mock_data.py
```

Sinh lại `src/tools/mock_data/suppliers.json` (106 bản ghi: 100 bản ghi `SRC###` từ
trang sản phẩm của các công ty nội thất văn phòng thật tại Việt Nam + 6 edge
case thủ công `EDGE00x`; xem `src/tools/mock_data/VERSION`). Tên
công ty, khu vực và `nguon_url` là thật (website chính thức từng công ty,
verify qua WebSearch); mọi field số (`Gia`, `MOQ`, `TonKho`, `ThoiGianGiao`,
`BaoHanh`, `ChietKhauTheoSoLuong`, `DiemUyTin`) là dữ liệu mô phỏng, được khai
báo rõ trong `simulated_fields` của từng record — agent phải trích dẫn
`simulated_fields` khi trả lời, không được trình bày như số liệu thật. 6 record
`EDGE00x` là công ty hư cấu dùng để test hành vi cụ thể (ngân sách mâu thuẫn
MOQ, thiếu `DiemUyTin`, hết hàng, dữ liệu mâu thuẫn…) — `nguon_url` của chúng
trỏ về chính `generate_mock_data.py` trong repo, không phải domain thật.

## Memory / State

```bash
sqlite3 src/memory/state.db < src/memory/schema.sql   # (re)init SQLite state DB
```

`src/memory/db.py` lưu state theo `session_id`; `src/graph.py` gọi `init_db()`
1 lần khi import module (idempotent, `CREATE TABLE IF NOT EXISTS`).

## AutoEval

```bash
python scripts/run_autoeval.py --eval-set tests/eval_set --llm stub --tier pipeline
# Chạy thủ công sau khi A/B tích hợp và đã cấu hình API key:
python scripts/run_autoeval.py --eval-set tests/eval_set --llm real --tier llm --repeat 3 --sleep-between 4
```

Xuất `reports/autoeval_<timestamp>.json` và `.md`; `--out-dir` đổi nơi lưu.
`--tier pipeline|llm|all` mặc định `all`. `--sleep-between` áp dụng giữa request,
kể cả giữa lượt trong case nhiều lượt. JSON giữ kết quả từng case, trace ID từng
request, hai bảng tổng hợp theo tầng và spread min/max/stdev khi `--repeat > 1`.

- **Tầng 1:** constraint satisfaction, citation correctness, failure recovery,
  tool call success. Kiểm tra implementation, KHÔNG chứng minh năng lực hiểu ngôn ngữ.
- **Tầng 2:** task success theo nhóm, intent routing accuracy, field accuracy theo
  tên field, no-invented-numbers. Số này chỉ có giá trị khi `llm_mode=real`.
- **Vận hành:** avg/p50/p95/max latency, LLM/tool calls, tokens/request, chi phí
  tổng/trung bình. Case nhiều lượt tính mọi lượt cho số đo vận hành, chấm task
  success ở state cuối. Percentile dùng nearest-rank.
- Case chưa có field A/B yêu cầu được ghi **không đo được**, không tính là pass.
  Field mới đang chờ xác nhận tại cuối `interface-contracts.md`.
- Bảng giá trong `src/eval/scoring.py::MODEL_PRICING` có nguồn và ngày kiểm tra;
  giá chưa xác minh để `None` và báo **chưa cấu hình giá**, vẫn báo token.

Lưu ý: `--llm stub` không làm NLP thật (`perceive` luôn trả về đúng 1 JSON cố
định bất kể câu hỏi), nên các case adversarial cần phân loại intent đúng
(hỏi ngoài phạm vi, ngân sách bất khả thi, hỏi thông tin agent không biết) sẽ
luôn trượt ở chế độ stub — chỉ đo được chính xác bằng `--llm real` (cần
`GOOGLE_API_KEY` thật). `tests/eval_set/cases.jsonl` là file case cũ chưa có
`oracle`, script cảnh báo số dòng bị bỏ qua và tên file; dùng `cases_c.jsonl` hoặc thư mục `tests/eval_set/`
để chạy toàn bộ case có oracle.

`tests/run_parse_and_memory.py` là runner parse/memory cũ của A, khác với AutoEval E2E.

## Load test

```bash
python scripts/run_loadtest.py --levels 1,5,10 --requests-per-level 10 --llm stub --out-dir reports
```

Số đo `llm_ms` là thời gian node perceive + respond, gồm parse/wiring quanh
LLM; `tool_ms` là tổng thời gian audit tool, gồm retry/backoff; `other_ms` là
phần còn lại. Trace `logs/<trace_id>.jsonl` có `node_end`, còn `logs/runs.jsonl`
có tổng kết từng request. Stub latency 0 không đại diện hiệu năng API thật.

## Làm mới dữ liệu và lịch chạy

```powershell
.venv\Scripts\python.exe scripts/refresh_sources.py --dry-run
# Có mạng: verify/apply các CSV web rồi generate suppliers.json và VERSION.
.venv\Scripts\python.exe scripts/refresh_sources.py --cache-dir reports/source_cache
```

Dry-run chỉ validate/lập danh sách, không fetch/ghi file. Refresh giữ nguyên
báo giá B2B thu tay; không cập nhật ngày báo giá chỉ vì URL còn truy cập được.
Cache của refresh là snapshot riêng cho mỗi lần chạy và mỗi CSV; luôn fetch mới,
không dùng HTML cũ rồi đóng dấu ngày hiện tại.
`DATA_STALE_DAYS` mặc định 14. Thiếu/sai `fetched_at` hoặc ngày tương lai được
đánh stale kèm lý do; respond nối cảnh báo ngày/URL bằng logic deterministic.

Ví dụ lập lịch **tự chạy thủ công**, phiên làm việc của C không tạo task:

```powershell
$TaskRun = '"D:\Study\AIGURU\FINAL_PROJECT\Procurement-Intelligence-Negotiation-Agent\.venv\Scripts\python.exe" "D:\Study\AIGURU\FINAL_PROJECT\Procurement-Intelligence-Negotiation-Agent\scripts\refresh_sources.py"'
schtasks /Create /TN "ProcurementRefresh" /TR $TaskRun /SC WEEKLY /D MON /ST 08:00
```

Cron trên máy POSIX (thay `/path/to/repo` bằng đường dẫn thật):

```cron
0 8 * * 1 cd /path/to/repo && .venv/bin/python scripts/refresh_sources.py >> /path/to/repo/reports/refresh.log 2>&1
```

## Nạp báo giá B2B thật

Sao chép header `src/tools/mock_data/sources/b2b_quotes_template.csv` vào CSV
riêng trong cùng thư mục; bỏ dòng chú thích. A/B mỗi người thu 3 báo giá;
ghi `nguon_type=b2b_quote`, `quote_date`, `quote_quantity`, `quote_channel`, giá
VND số thuần, URL bằng chứng đã che thông tin cá nhân. Không thêm số điện thoại
hay email cá nhân. Trường chưa có bằng chứng vẫn ghi trong `simulated_fields`;
warranty/trust chưa biết giữ null. Fixture `tests/fixtures/b2b_quotes_test.csv`
chỉ dùng test, không được đưa vào nguồn production.

```powershell
.venv\Scripts\python.exe generate_mock_data.py
.venv\Scripts\python.exe scripts/compare_b2b_vs_web.py --llm stub
```

Báo giá chỉ dùng ở đúng `quote_quantity`. Mã QTE tách khỏi SRC để không đổi mã
web khi nạp báo giá. So sánh chỉ ghép khi trùng NCC, loại và tên sản phẩm duy
nhất; hai scenario dùng cùng điều kiện và thuộc tính ngoài giá từ web, chỉ thay
giá bằng báo B2B. Provenance giá lưu riêng; không xuất lời khuyên mua từ scenario.
Trường hợp không khớp/thiếu giá ghi không đo được. Khi chưa có báo giá,
script in “chưa có báo giá b2b_quote nào” và thoát 0.

## Giới hạn còn lại (2026-10)

- Chưa có kết quả LLM thật mới, chưa cấu hình giá token chính thức, chưa có
  báo giá B2B thật. Không dùng số stub thay thế các bằng chứng này.
- A/B còn trích ưu tiên, weights_used, relax_suggestions, case mới và test
  cô lập phiên/bỏ kết quả cũ. Xem `docs/handoff-c-to-ab-2026-10.md`.
- Exception của parser A chưa mang token: C giữ được nếu có, còn thiếu thì
  không đo được; không tự suy ra token.
- Fan-out detail giữ nguyên vì batch/full search cần đổi hợp đồng và A/B xác nhận.
- Grader số hiện có là heuristic cho số >=100; không bao quát toàn bộ số nhỏ
  hoặc chứng minh mọi con số trong văn bản đều gắn URL đúng.
- Baseline stdlib còn 4 lỗi A/B: hai import pytest của live test, một kỳ vọng
  model cũ và một evidence conflict. C không sửa test/logic A/B để làm xanh.
- Báo cáo/log bị gitignore; chỉ add-f từng report cuối sau khi cả nhóm duyệt.
