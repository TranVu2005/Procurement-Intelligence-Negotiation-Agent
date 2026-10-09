# Procurement Intelligence & Negotiation Agent

Agent mua sắm nội thất bằng tiếng Việt: trích yêu cầu, tìm nhà cung cấp, lọc ràng buộc, xếp hạng và đề xuất đàm phán. Pipeline LangGraph dùng Python cho tool, scoring, kiểm chứng và re-plan; LLM xử lý perception và diễn đạt phản hồi. Memory SQLite tách theo session, tracing ghi theo request.

## Cài đặt và chạy

Chạy từ thư mục gốc repository. Bộ dependency được ghim trong `requirements.txt`; môi trường kiểm tra hiện tại dùng Python 3.14.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Điền API key trong .env, sau đó:
.venv\Scripts\python.exe -m streamlit run app.py
# Hoặc giao diện dòng lệnh:
.venv\Scripts\python.exe -m src.agent
```

Web mặc định tại http://127.0.0.1:8501/. SQLite được khởi tạo tự động. `.env`, database, log, cache và báo cáo sinh ra được Git bỏ qua.

`src/llm.py` là nơi cấu hình model. `LLM_PROVIDER` hỗ trợ `gemini` (mặc định, `GOOGLE_API_KEY`), `openrouter` (`OPENROUTER_API_KEY`, tùy chọn `OPENROUTER_MODEL`) và `nararouter` (`NARAROUTER_API_KEY`, tùy chọn `NARAROUTER_MODEL`). Dùng `.env.example` làm mẫu; không ghi key vào mã nguồn hoặc báo cáo.

Demo offline:

```powershell
$env:AGENT_LLM="stub"
$env:AGENT_STUB_LATENCY_MEAN_S="0"
$env:AGENT_STUB_LATENCY_STDDEV_S="0"
.venv\Scripts\python.exe -m streamlit run app.py
```

Stub trả JSON perception cố định và phản hồi cố định; dùng để kiểm tra wiring, không đánh giá khả năng hiểu tiếng Việt. Xóa biến `AGENT_LLM` khi chuyển lại LLM thật.

## Kiểm thử

Toàn bộ test dùng stdlib `unittest`, không cần pytest:

```powershell
$env:AGENT_LLM="stub"
$env:AGENT_STUB_LATENCY_MEAN_S="0"
$env:AGENT_STUB_LATENCY_STDDEV_S="0"
.venv\Scripts\python.exe -m unittest discover tests "test_*.py"
.venv\Scripts\python.exe -m unittest tests.test_tools -v
```

Hai module `tests/test_gemini_*_live.py` chỉ chạy khi bật `RUN_LIVE_TESTS=1`, có API key và không dùng stub. Chúng gọi API thật, ghi transcript vào `reports/`:

```powershell
Remove-Item Env:AGENT_LLM -ErrorAction SilentlyContinue
$env:RUN_LIVE_TESTS="1"
.venv\Scripts\python.exe -m unittest tests.test_gemini_intent_live tests.test_gemini_memory_live -v
Remove-Item Env:RUN_LIVE_TESTS
```

## AutoEval và load test

```powershell
.venv\Scripts\python.exe scripts/run_autoeval.py --eval-set tests/eval_set --llm stub --tier pipeline
# Sau khi cấu hình API key, đánh giá NLP thật:
.venv\Scripts\python.exe scripts/run_autoeval.py --eval-set tests/eval_set --llm real --tier llm --repeat 3 --sleep-between 4
.venv\Scripts\python.exe scripts/run_loadtest.py --levels 1,5,10 --requests-per-level 10 --llm stub --out-dir reports
```

- Tầng `pipeline`: constraint satisfaction, citation correctness, failure recovery, tool success; kiểm tra implementation.
- Tầng `llm`: task success theo nhóm, intent routing, field accuracy và no-invented-numbers. Chỉ kết quả với `llm_mode=real` có giá trị đánh giá NLP.
- Báo cáo giữ latency avg/p50/p95/max, LLM/tool calls, token và chi phí nếu có pricing đã xác minh. Case thiếu field cần chấm được ghi không đo được.
- `--repeat` giữ từng lượt và spread; `--sleep-between` áp dụng giữa mọi request. `--out-dir` đổi thư mục báo cáo.
- `tests/eval_set/cases.jsonl` là bộ legacy chưa có oracle; runner cảnh báo và bỏ qua. Các file A/B/C có oracle là bộ đánh giá hiện hành.

`llm_ms` gồm perceive/respond và wiring; `tool_ms` gồm retry/backoff; `other_ms` là phần còn lại. Load test stub không đại diện tốc độ API thật. Các output nằm trong `reports/` và `logs/`.

## Dataset và nguồn

Dataset runtime: `src/tools/mock_data/suppliers.json`; hash/ngày build/số bản ghi: `src/tools/mock_data/VERSION`. Dữ liệu nguồn ở `src/tools/mock_data/sources/`; schema được validate trong `src/tools/dataset_builder.py`, mẫu báo giá là `b2b_quotes_template.csv`.

```powershell
.venv\Scripts\python.exe generate_mock_data.py
.venv\Scripts\python.exe -m unittest tests.test_dataset_builder tests.test_dataset_files -v
```

Generator chỉ sinh dataset và VERSION. Bản hiện tại có 100 record `SRC` từ nguồn web và 6 fixture `EDGE`. Giá có nguồn được giữ nguyên; các field nghiệp vụ mô phỏng được khai báo trong `simulated_fields`. Bảo hành/uy tín chưa có bằng chứng giữ null. Fixture EDGE là dữ liệu giả lập có chủ đích. JSON legacy được giữ ở `data/archive/real_data_ghe_ban.json`, không dùng trong runtime.

Làm mới nguồn web:

```powershell
.venv\Scripts\python.exe scripts/refresh_sources.py --dry-run
# Có mạng, verify/apply nguồn web rồi build dataset:
.venv\Scripts\python.exe scripts/refresh_sources.py --cache-dir reports/source_cache
```

Dry-run không fetch/ghi file. Mỗi lần refresh dùng snapshot mới theo từng CSV, không đóng dấu ngày hiện tại cho HTML cache cũ. Báo giá B2B thu tay giữ ngày báo giá riêng. `DATA_STALE_DAYS` mặc định 14; thiếu/sai ngày hoặc ngày tương lai có cảnh báo và lý do.

Để chạy định kỳ, lập lịch lệnh refresh từ thư mục gốc bằng Windows Task Scheduler hoặc cron. Repository không tự tạo lịch.

Báo giá B2B: dùng header `b2b_quotes_template.csv`, bỏ dòng chú thích, ghi `nguon_type=b2b_quote`, `quote_date`, `quote_quantity`, `quote_channel`, giá VND số thuần và URL bằng chứng đã che thông tin cá nhân. Trường chưa xác minh phải giữ trong `simulated_fields`. Fixture test không nhập vào nguồn runtime.

```powershell
.venv\Scripts\python.exe scripts/compare_b2b_vs_web.py --llm stub
```

Báo giá chỉ dùng tại đúng `quote_quantity`; mã QTE tách khỏi SRC. So sánh ghép duy nhất theo NCC, loại và tên sản phẩm, giữ request/thuộc tính ngoài giá từ web và ghi provenance riêng cho giá. Thiếu hoặc không khớp dữ liệu được ghi không đo được; script không xuất lời khuyên mua từ scenario.

## Cấu trúc

| Đường dẫn | Nội dung |
|---|---|
| `src/perception/`, `src/memory/` | Trích yêu cầu và lưu phiên |
| `src/reasoning/`, `src/nodes/` | Planning, orchestration, ranking, verification, phản hồi |
| `src/tools/`, `src/logging_utils/` | Tool có schema, dataset builder, retry, tracing/redaction |
| `src/eval/`, `tests/` | Grader và regression/eval case |
| `scripts/` | AutoEval, load test, crawl/verify/refresh nguồn, demo và so sánh B2B |
| `docs/reference/`, `data/` | Đề bài PDF và dữ liệu tham chiếu |

`README.md` là file Markdown duy nhất được đưa lên GitHub. Tài liệu và ghi chú Markdown khác giữ local; report/log sinh mới nằm trong các thư mục được Git bỏ qua.

## Giới hạn còn lại

Chưa có AutoEval LLM thật ×3 và pricing token đã xác minh. `a_b2b_quotes.csv` có 3 dòng cần xác minh/bổ sung metadata trước khi build/so sánh B2B. Exception parser chưa luôn mang token; thiếu số đo phải báo không đo được. Fan-out detail còn lớn; grader số dùng heuristic cho số ≥100. Gợi ý no-match cần kiểm tra tính hữu ích trước khi thay đổi ràng buộc; agent luôn cần xác nhận chốt đơn.
