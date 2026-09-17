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

Model mặc định: `google/gemma-4-31b-it:free`. Đổi bằng `OPENROUTER_MODEL`.
Model free khác đáng cân nhắc (data live từ `openrouter.ai/api/v1/models`,
kiểm tra 2026-09-17 — danh sách free của OpenRouter đổi liên tục, kiểm tra
lại trước khi dùng lâu dài):

| Model | Context | Ghi chú |
|---|---|---|
| `google/gemma-4-31b-it:free` (default) | 262K | Đa ngôn ngữ mạnh, cùng họ Google với Gemini đang dùng nên hành vi dễ so sánh |
| `z-ai/glm-5.2:free` | 32K | JSON/tool-use tốt nhưng context ngắn — rủi ro với prompt dài của project |
| `nvidia/nemotron-3-super-120b-a12b:free` | 262K | Model lớn hơn, lý luận mạnh hơn, chậm hơn |
| `openrouter/free` | 200K | Auto-router giữa các model free — fallback khi 1 model bị rate-limit |

Free tier OpenRouter giới hạn 20 request/phút, 50 request/ngày (không nạp
credit) hoặc 1000 request/ngày (đã nạp tối thiểu $10).

## Chạy agent (REPL)

```bash
python -m src.agent
```

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

Sinh lại `src/tools/mock_data/suppliers.json` (38 bản ghi: 32 từ 14 công ty
nội thất văn phòng thật tại Việt Nam + 6 edge case thủ công `EDGE00x`). Tên
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
python scripts/run_autoeval.py --eval-set tests/eval_set/cases_c.jsonl --llm stub
```

Xuất `reports/autoeval_<timestamp>.json` và `.md`, báo 5 chỉ số: Task Success
Rate, Constraint Satisfaction Rate, Tool Call Success Rate,
Citation/Evidence Correctness, Failure Recovery Rate.

Lưu ý: `--llm stub` không làm NLP thật (`perceive` luôn trả về đúng 1 JSON cố
định bất kể câu hỏi), nên các case adversarial cần phân loại intent đúng
(hỏi ngoài phạm vi, ngân sách bất khả thi, hỏi thông tin agent không biết) sẽ
luôn trượt ở chế độ stub — chỉ đo được chính xác bằng `--llm real` (cần
`GOOGLE_API_KEY` thật). `tests/eval_set/cases.jsonl` là file case cũ chưa có
`oracle`, script tự bỏ qua; dùng `cases_c.jsonl` hoặc thư mục `tests/eval_set/`
để chạy toàn bộ case có oracle.

`tests/run_autoeval.py` (khác file, dispatch bằng `if cid == "case_001"`)
thuộc tier unit-test cũ, không phải AutoEval báo cáo chính thức.

## Load test

```bash
python scripts/run_loadtest.py --levels 1 --requests-per-level 5 --llm stub
```

## Trạng thái hiện tại (2026-09-17)

- 243/243 unit test pass (`AGENT_LLM=stub python -m unittest discover tests
  "test_*.py"`).
- Pipeline LangGraph chạy thông cả 4 intent; `mock_data/suppliers.json` đã có
  `nguon_url`/`nguon_type`/`simulated_fields` đầy đủ nên `verify_output`
  không còn chặn vì thiếu trích dẫn (`citation_correctness = 1.0` trong
  AutoEval gần nhất).
- AutoEval (`cases_c.jsonl`, stub): task_success_rate 0.7 (7/10) — 3 case
  trượt đều là adversarial, do giới hạn của `StubLLM` (không NLP thật), cần
  `--llm real` để đo đúng.
