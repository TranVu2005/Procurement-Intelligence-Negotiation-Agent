# Nội dung 20 Slide — Procurement Intelligence & Negotiation Agent
**Môn học:** AI Guru AEF1 — Final Project  
**Nhóm:** 3 thành viên (A, B, C)  
**Dự án:** Agent mua sắm nội thất thông minh  

---

## SLIDE 1 — Trang tiêu đề (Title Slide)

**Tiêu đề chính:**  
# Procurement Intelligence & Negotiation Agent  
### AI Agent Mua Sắm Nội Thất Thông Minh

**Phụ tiêu đề:**  
Tìm kiếm — So sánh — Đề xuất chiến lược đàm phán tự động bằng tiếng Việt tự nhiên

**Thông tin nhóm:**  
- Người A: Perception & Memory  
- Người B: Reasoning & Planning  
- Người C: Tools, Logging & Pipeline  

**Course:** AI Guru AEF1 · Ngày: 2026-09-21

---

## SLIDE 2 — Bối cảnh & Vấn đề cần giải quyết

**Tiêu đề:** Bài toán đặt ra

**Nội dung:**

🏢 **Vấn đề thực tế:**  
Doanh nghiệp mua sắm nội thất văn phòng phải:
- Tìm kiếm nhà cung cấp thủ công trên nhiều nguồn
- So sánh giá và điều kiện từng nhà cung cấp mất nhiều thời gian
- Thiếu công cụ hỗ trợ ra quyết định đàm phán có bằng chứng

**📌 Câu hỏi cốt lõi:**  
*"Làm thế nào để agent tự động hóa toàn bộ quy trình: từ nhận yêu cầu bằng tiếng Việt → tìm nhà cung cấp → so sánh → đề xuất chiến lược đàm phán — mà vẫn kiểm chứng được từng bước?"*

**🎯 Mục tiêu dự án:**
- Nhận yêu cầu tự nhiên tiếng Việt
- Tìm & lọc nhà cung cấp theo ràng buộc cứng/mềm
- Tính leverage score và đề xuất chiến lược đàm phán
- Mọi con số đều có nguồn gốc truy vết được

---

## SLIDE 3 — Tổng quan kiến trúc hệ thống

**Tiêu đề:** Kiến trúc: Deterministic LangGraph Pipeline

**Nội dung:**

**🏗️ Lựa chọn kiến trúc:**  
Từ ReAct `AgentExecutor` → **LangGraph `StateGraph` Pipeline tất định**

```
START → [perceive LLM#1] → route theo intent
    ├── search_new   → plan → tool_search → filter_hard
    ├── compare_specific → tool_compare → filter_hard  
    ├── supplier_detail → tool_detail → filter_hard
    └── out_of_scope → respond_limits → END
                            ↓
                     score_rank → verify_output
                            ↓                ↓ fail
                       respond LLM#2    diagnose → replan (tối đa 3x)
                            ↓                           ↓ quá 3x
                      confirm_gate → END          graceful_fail → END
```

**⚡ Tại sao chọn cách này?**
- LLM chỉ gọi **đúng 2 lần** trên đường thành công (perceive + respond)
- Mọi node giữa = Python tất định → kiểm chứng được, không dao động
- Re-plan **không tốn thêm LLM call** nào

---

## SLIDE 4 — Module Ownership & Phân công nhóm

**Tiêu đề:** Ai làm gì? Phân công 3 module rõ ràng

**Nội dung:**

| Module | Owner | Nội dung chính |
|---|---|---|
| `src/perception/` + `src/memory/` | **Người A** | Parse tiếng Việt → State Schema, SQLite session |
| `src/reasoning/` | **Người B** | Planner, Leverage Score, Verify Output, Re-plan |
| `src/tools/` + `src/logging_utils/` + pipeline wiring | **Người C** | Tool contract, mock data, tracer, graph.py |

**📋 Interface Contract:**  
- `interface-contracts.md` = **nguồn sự thật duy nhất** cho mọi field trao đổi giữa 3 module
- Không ai được tự ý đổi field/tên mà không cập nhật và báo 2 người còn lại
- *"Đây là rule nhóm đã vấp một lần ở lần merge tháng 9"* → rút kinh nghiệm: chốt contract trước, code sau

---

## SLIDE 5 — Perception Module (Module A)

**Tiêu đề:** Module A — Perception & Memory: Hiểu tiếng Việt tự nhiên

**Nội dung:**

**Nhiệm vụ:**  
Biến câu tiếng Việt tự do → **Structured State Schema** có thể kiểm chứng

**Ví dụ thực tế:**
```
Input:  "Mua 50 ghế văn phòng, ngân sách 200 triệu,
         giao trong 14 ngày, ưu tiên chất liệu gỗ tự nhiên, Hà Nội"
         
Output (State Schema):
{
  "intent": "search_new",
  "hard_constraints": {
    "product_type": "ghế văn phòng",
    "quantity": 50,
    "budget_max": 200000000,
    "delivery_deadline_days": 14
  },
  "soft_constraints": {
    "material_preference": "gỗ tự nhiên",
    "region_preference": "Hà Nội",
    "min_trust_score": null
  }
}
```

**Memory (SQLite):**
- Lưu state theo `session_id` — không bao giờ trộn dữ liệu giữa 2 session
- Khi khách đổi yêu cầu: **ghi đè** field, không giữ bản cũ song song
- Bảng `runs`: lưu `llm_calls`, `tokens_in/out`, `latency_ms` để báo cáo hiệu năng

---

## SLIDE 6 — Reasoning & Planning Module (Module B)

**Tiêu đề:** Module B — Reasoning & Planning: Ra quyết định có bằng chứng

**Nội dung:**

**Leverage Score — 5 yếu tố:**

| Yếu tố | Trọng số | Cách tính |
|---|---|---|
| Giá | 30% | Dư địa ngân sách: `(budget - total) / budget × 100` |
| MOQ | 15% | Tỷ lệ đặt hàng/tối thiểu: `(qty/moq) × 50` |
| Giao hàng | 20% | Sớm hơn deadline: `50 + (deadline-delivery)/deadline × 50` |
| Bảo hành | 15% | Chuẩn hóa 0–100 trên 36 tháng |
| Uy tín | 20% | Chuẩn hóa 0–100 trên thang 1–5 |

**Planner:**
- `make_plan()` → sinh `steps` theo intent, không hard-code
- `make_replan()` → tạo `plan_id` mới + ghi `replan_reason` (audit trail)
- Giới hạn 3 lần re-plan, sau đó `graceful_fail`

**Verify Output:**  
`verdict = { "passed": bool, "violations": [...], "claims": [{MaNCC, nguon_url}] }`  
→ Mọi con số phải truy ngược về tool_results. Không truy được → chặn, không cho trả lời.

---

## SLIDE 7 — Tools & Data Module (Module C)

**Tiêu đề:** Module C — Tools, Data & Logging: Nền tảng thực thi

**Nội dung:**

**4 Tools (LangChain StructuredTool + Pydantic args_schema):**

| Tool | Input | Output |
|---|---|---|
| `search_suppliers` | product_type, material?, region? | Danh sách nhà cung cấp |
| `compare_price` | supplier_ids, quantity | Giá sau chiết khấu, total_price |
| `get_supplier_detail` | supplier_id | Full record 13 field |
| `confirm_order` | supplier_id, quantity | Chốt đơn (cần xác nhận tường minh) |

**Mock Dataset:**  
- 38 bản ghi: 32 từ **14 công ty nội thất thật** tại Việt Nam + 6 edge case
- Mỗi record có: `nguon_url` (website thật), `nguon_type`, `simulated_fields`
- **Tính minh bạch:** field nào mô phỏng được khai báo rõ → agent phải trích dẫn

**Error Contract (bất biến):**
```json
{
  "error": true,
  "error_type": "timeout|no_match|invalid_input|tool_unavailable",
  "message": "mô tả ngắn"
}
```
→ Lỗi 1 phần tử trong batch call không fail cả response

---

## SLIDE 8 — Dữ liệu Mock — Thiết kế & Tính minh bạch

**Tiêu đề:** Dữ liệu: Thật đủ mức, mô phỏng rõ ràng

**Nội dung:**

**Nguồn dữ liệu:**
- **Tên công ty, khu vực, URL:** 14 công ty nội thất văn phòng thật tại Việt Nam
  - Nội Thất Hòa Phát, Xuân Hòa, Fami, 190 Office... (có `nguon_url` website chính thức)
- **Trường số (giá, MOQ, thời gian giao...):** Mô phỏng, khai báo trong `simulated_fields`

**Phân bố dataset:**

| Loại sản phẩm | Số record |
|---|---|
| Ghế văn phòng | 10 |
| Sofa | 10 |
| Tủ hồ sơ | 8 |
| Bàn làm việc | 6 |
| Kệ | 4 |

**6 Edge Cases (`EDGE00x`):**  
Công ty hư cấu, tạo ra để test hành vi cụ thể:
- Ngân sách mâu thuẫn với MOQ
- Thiếu `DiemUyTin`
- Hết hàng (`TonKho = 0`)
- Dữ liệu mâu thuẫn → `evidence_conflict`

**Quy trình:**  
`sources/*.csv` (tay thu thật) → `generate_mock_data.py` → `suppliers.json`

---

## SLIDE 9 — Pipeline Luồng Chạy Thực tế

**Tiêu đề:** Demo Luồng: Từ câu hỏi → Đề xuất đàm phán

**Nội dung:**

**Kịch bản Happy Path:**

```
Người dùng: "Mua 50 ghế văn phòng, ngân sách 200 triệu,
             giao trong 14 ngày, ưu tiên gỗ tự nhiên, Hà Nội"
```

| Bước | Node | Kết quả |
|---|---|---|
| 1 | `perceive` (LLM #1) | intent=search_new, hard/soft constraints |
| 2 | `plan` | steps: [search_suppliers(ghế văn phòng)] |
| 3 | `tool_search` | 10 nhà cung cấp phù hợp loại sản phẩm |
| 4 | `filter_hard` | 7 NCC còn lại (lọc MOQ, ngân sách, deadline) |
| 5 | `score_rank` | Xếp hạng theo leverage score |
| 6 | `verify_output` | passed=True, claims có nguon_url |
| 7 | `respond` (LLM #2) | Câu trả lời + chiến lược đàm phán |
| 8 | `confirm_gate` | Chờ xác nhận tường minh từ người dùng |

**LLM calls = đúng 2 lần** · Latency trung bình: đo được từ bảng `runs`

---

## SLIDE 10 — Xử lý Lỗi & Re-planning

**Tiêu đề:** Fail Safe: Re-plan có lý do, Graceful Fail khi cần

**Nội dung:**

**Re-plan Logic:**

| Tình huống | Mã lỗi | Hướng xử lý |
|---|---|---|
| Hết hàng | `stock_below_quantity` | Chia đơn / NCC khác |
| MOQ quá cao | `quantity_below_moq` | Gom đơn / thương lượng |
| Tất cả giao trễ | `delivery_deadline_unmet` | Nới deadline / NCC gần hơn |
| Tool timeout | `timeout` | Retry (tối đa 3 lần) |
| Dữ liệu mâu thuẫn | `evidence_conflict` | Không chọn cho đến khi xác minh |

**Quy tắc re-plan:**
- Luôn tạo `plan_id` **mới** + ghi `replan_reason` → không bao giờ sửa đè plan cũ
- Tối đa **3 lần** re-plan cho 1 yêu cầu
- Sau 3 lần: `graceful_fail` với nguyên nhân rõ ràng, không lặp vô hạn

**Graceful Fail:**  
*"Hệ thống gặp lỗi khi xử lý yêu cầu này và đã dừng lại thay vì trả kết quả không đáng tin."*  
→ Không bao giờ trả kết quả chưa xác minh như sự thật chắc chắn

---

## SLIDE 11 — Confirmation Gate & Safety

**Tiêu đề:** Safety First: Không bao giờ tự động chốt đơn

**Nội dung:**

**Confirm Gate — Design Decision:**  
`confirm_order` **không** là tool để LLM tự gọi → là **node chặn** chờ người dùng xác nhận tường minh

**Lý do quan trọng:**
- Hành động hậu quả cao (chốt đơn mua) không được tự động thực thi
- Agent không được suy luận đồng ý từ ngữ cảnh
- SYSTEM-RULES §6: *"Hành động hậu quả cao bắt buộc có bước confirmation"*

**Luồng xác nhận:**
```
respond → [chờ người dùng] → confirm_gate
    "Chốt đơn với NCC001 (Hòa Phát) - 50 ghế, 180 triệu không?"
         ↓ "Đồng ý"          ↓ "Không"
    confirm_order()      session giữ nguyên, không thực hiện
```

**Test coverage:**
- `test_node_confirm_gate.py` — 8 unit test đầy đủ
- Kịch bản xác nhận + từ chối đều có test case riêng

---

## SLIDE 12 — Memory & Session Management

**Tiêu đề:** Multi-turn Memory: Nhớ ngữ cảnh xuyên suốt hội thoại

**Nội dung:**

**SQLite State DB:**  
`src/memory/db.py` + `schema.sql` → persist state theo `session_id`

**Luồng multi-turn:**

```
Turn 1: "Mua 50 ghế văn phòng, ngân sách 200 triệu, giao 14 ngày"
        → parse_request() → lưu DB → session_id: sess_001

Turn 2: "Thật ra ngân sách chỉ 150 triệu thôi"
        → load_session(sess_001) → update_state() → ghi đè budget_max
        → 150,000,000 VND (không giữ 200,000,000 cũ)

Turn 3: "Ưu tiên khu vực Hà Nội"
        → load_session() → update region_preference
        → session_id nhất quán: sess_001 ✅
```

**Quy tắc memory:**
- Không bao giờ trộn dữ liệu giữa 2 `session_id` khác nhau
- Đổi yêu cầu → ghi đè field, không giữ song song bản cũ
- `decisions_made` lưu lịch sử chốt đơn để tránh hỏi lại

**Kiểm thử:**  
`test_gemini_memory_live.py` — 376+ LOC test toàn bộ memory flows

---

## SLIDE 13 — Observability & Logging

**Tiêu đề:** Full Observability: Mọi bước đều có dấu vết

**Nội dung:**

**Tracer (`src/logging_utils/tracer.py`):**

Mỗi tool call ghi log tối thiểu:
```json
{
  "trace_id": "trace_abc123",
  "timestamp": "2026-09-21T10:00:00",
  "tool_name": "search_suppliers",
  "input": {"product_type": "ghế văn phòng"},
  "status": "ok",
  "latency_ms": 12.5
}
```

**Bảo mật:**
- `redact()` che mọi field nhạy cảm **trước khi** ghi log
- API key/secret **không bao giờ** xuất hiện trong log
- *Rubric chấm 0 điểm nếu phát hiện secret bị lộ → đây là yêu cầu bắt buộc*

**Bảng `runs` (SQLite):**  

| Field | Ý nghĩa |
|---|---|
| `llm_calls` | Số lần gọi LLM (kỳ vọng = 2.0) |
| `tokens_in/out` | Token đầu vào/ra |
| `latency_ms` | Tổng thời gian xử lý |
| `ttft_ms` | Time to first token |
| `status` | success / graceful_fail |

**JSONL output:** Mỗi trace_id ghi ra file → đọc lại được, tái lập được

---

## SLIDE 14 — AutoEval Framework

**Tiêu đề:** AutoEval: Đánh giá tự động — Không hard-code test case

**Nội dung:**

**Thiết kế 2 tầng:**

| Tầng | File | Vai trò |
|---|---|---|
| Unit/Integration | `tests/test_*.py` | Chạy nhanh, gác hồi quy (256 test) |
| AutoEval | `scripts/run_autoeval.py` | Gọi `run_request()` end-to-end, chấm 5 metric |

**Case format (JSONL — case là dữ liệu, không phải `if` branches):**
```json
{
  "id": "E01_happy_search",
  "category": "happy_path",
  "turns": ["Cần 50 ghế văn phòng, ngân sách 200 triệu, giao 14 ngày..."],
  "oracle": {
    "must_reach_intent": "search_new",
    "must_call_tools": ["search_suppliers", "compare_price"],
    "constraints": {"total_price_lte": 200000000},
    "must_cite": true,
    "expect_status": "success"
  }
}
```

**6 nhóm case:** `happy_path`, `missing_info`, `conflict`, `tool_failure`, `adversarial`, `multi_turn`

---

## SLIDE 15 — 5 Metrics AutoEval

**Tiêu đề:** 5 Metrics — Đo lường toàn diện chất lượng Agent

**Nội dung:**

| Metric | Định nghĩa | Kết quả (stub) |
|---|---|---|
| **Task Success Rate** | `expect_status` khớp + mọi `must_*` thỏa | **70%** (7/10 case) |
| **Constraint Satisfaction Rate** | Ràng buộc cứng đúng trên `ranked[0]` | Đang đo với LLM thật |
| **Tool Call Success Rate** | Tool call không lỗi sau retry / tổng tool call | Đang đo |
| **Citation/Evidence Correctness** | Claims có `evidence.nguon_url` truy được về `tool_results` | **100%** |
| **Failure Recovery Rate** | Case `inject` kết thúc ở `success`/`graceful_fail` rõ nguyên nhân | Đang đo |

**Lưu ý quan trọng:**
- 3 case trượt (30%) đều là **adversarial** → giới hạn của StubLLM (không làm NLP thật)
- Cần `--llm real` (GOOGLE_API_KEY thật) để đo chính xác
- Citation Correctness = **1.0** trên mọi lần chạy → mọi con số đều có nguồn

**Chạy:**
```bash
python scripts/run_autoeval.py --eval-set tests/eval_set/cases_c.jsonl --llm real --repeat 3
```

---

## SLIDE 16 — Load Test & Hiệu năng

**Tiêu đề:** Load Test: Hệ thống chịu tải như thế nào?

**Nội dung:**

**Load Test Design (`scripts/run_loadtest.py`):**

| CCU Level | LLM | Mục đích |
|---|---|---|
| 1–5 CCU | Gemini thật | Đo latency thực tế, token cost |
| 10–50 CCU | StubLLM | Đo throughput, error rate không tốn API |

**Chỉ số đo:**
- **Throughput:** req/s ở mỗi mức CCU
- **Latency:** P50/P95 (đọc từ bảng `runs`)
- **Error rate:** % request kết thúc bằng `graceful_fail`
- **Resource:** CPU/RAM qua `psutil`

**Lợi thế thiết kế:**  
"LLM calls = đúng 2 lần/request" → predictable cost  
```
Cost/request = cost(perceive_tokens) + cost(respond_tokens)
Không dao động theo số lần re-plan (re-plan là Python thuần)
```

**Chạy:**
```bash
python scripts/run_loadtest.py --levels 1 --requests-per-level 5 --llm stub
```

---

## SLIDE 17 — LLM Integration & Tính linh hoạt

**Tiêu đề:** LLM Flexibility: Gemini, OpenRouter, hoặc Stub

**Nội dung:**

**3 chế độ LLM (`src/llm.py`):**

| Chế độ | Cách bật | Dùng khi nào |
|---|---|---|
| **Gemini** (mặc định) | `GOOGLE_API_KEY=...` | Production / demo thật |
| **OpenRouter** (free) | `LLM_PROVIDER=openrouter` | Không có Gemini key |
| **StubLLM** | `AGENT_LLM=stub` | CI/CD, unit test, load test |

**StubLLM — tại sao quan trọng:**
- Trả JSON/text cố định, không gọi mạng
- 256 unit test chạy hoàn toàn offline
- Load test mức 10–50 CCU không tốn API quota
- `AGENT_LLM=stub` thắng tuyệt đối nếu set — safety switch rõ ràng

**OpenRouter free models đã test:**
- `openrouter/free` — auto-router, tránh bị kẹt rate-limit
- `google/gemma-4-31b-it:free` — 262K context, đa ngôn ngữ mạnh

**Factory pattern:**  
`get_llm()` trả đúng client theo env → node `perceive` và `respond` dùng chung một factory

---

## SLIDE 18 — Kết quả Kiểm thử

**Tiêu đề:** Test Results: 256/256 Tests Pass

**Nội dung:**

**Test Suite (Python `unittest` chuẩn):**

```
python -m unittest discover tests "test_*.py"
→ 256/256 tests PASS  (AGENT_LLM=stub)
```

**Coverage theo domain:**

| Domain | File test chính | Tests |
|---|---|---|
| Perception & Parser | `test_parse_memory_suite.py` (242 LOC) | 20+ |
| Reasoning & Scoring | `test_scoring.py`, `test_verification.py` | 15+ |
| Tools | `test_tools.py`, `test_node_tool_*.py` | 30+ |
| Graph Pipeline | `test_graph_e2e_stub.py`, `test_graph_routing.py` | 25+ |
| Memory & Session | `test_gemini_memory_live.py` | 40+ |
| Intent Classification | `test_gemini_intent_live.py` | 20+ |
| Tracer & Logging | `test_tracer_jsonl.py`, `test_tracer_redact.py` | 10+ |
| Load & Eval | `test_loadtest.py`, `test_autoeval_*.py` | 15+ |

**Loại test:**
- Unit test: mỗi hàm độc lập
- Integration test: A×B, B×C chain
- E2E stub test: cả pipeline với node giả/stub
- Live test (Gemini thật): intent + memory flows

---

## SLIDE 19 — Streamlit Web Interface

**Tiêu đề:** Giao diện Web — Trực quan, đầy đủ thông tin

**Nội dung:**

**`app.py` — Streamlit UI:**

**Tính năng:**
- **Chat interface** — nhập yêu cầu tiếng Việt tự nhiên
- **Ranking table** — bảng xếp hạng nhà cung cấp với leverage score
- **Source links** — link `nguon_url` cho mọi con số
- **Simulated labels** — nhãn rõ field nào mô phỏng, field nào thật
- **Confirmation gate** — nút xác nhận chốt đơn tường minh
- **Trace/Metrics** — hiển thị LLM calls, latency, token count

**Demo kịch bản:**

| Kịch bản | Luồng |
|---|---|
| Happy path | Tìm → So sánh → Xếp hạng → Xác nhận |
| Tool failure | Retry → Re-plan → Graceful fail |
| Multi-turn | Đổi ngân sách → Update state → Tìm lại |
| Out-of-scope | Nêu rõ giới hạn hệ thống |

**Chạy:**
```bash
streamlit run app.py
```

---

## SLIDE 20 — Tổng kết & Bài học

**Tiêu đề:** Tổng kết — Những gì chúng tôi đã xây dựng

**Nội dung:**

**Đã hoàn thành:**

| Hạng mục | Trạng thái |
|---|---|
| Pipeline LangGraph end-to-end (4 intent) | Hoàn thành |
| LLM = 2 calls/request (deterministic) | Hoàn thành |
| 256 unit test pass (offline, stub) | Hoàn thành |
| Mock data 38 records + simulated_fields | Hoàn thành |
| AutoEval 5 metrics + JSONL reports | Hoàn thành |
| Tracer JSONL + redact bảo mật | Hoàn thành |
| Confirmation gate (không tự chốt đơn) | Hoàn thành |
| Multi-turn memory (SQLite) | Hoàn thành |
| Streamlit web UI | Hoàn thành |
| Load test (1–50 CCU) | Hoàn thành |

**Bài học kỹ thuật:**

1. **Contract trước, code sau** — Interface contracts là nền móng, vi phạm gây merge conflict
2. **Tất định hơn Phức tạp** — Pipeline cố định dễ kiểm chứng hơn vòng lặp dynamic
3. **Minh bạch dữ liệu** — `simulated_fields` biến "không thể kiểm chứng" thành "kiểm chứng được bằng máy"
4. **Test là bảo hiểm** — 256 test giúp merge nhánh tự tin hơn nhiều

**Giới hạn & Hướng phát triển:**
- Web search thật (hiện dùng mock) → cắm adapter khi cần
- Streaming response → TTFT có ý nghĩa hơn
- Dataset mở rộng lên 50-55 records (hiện 38)

---

*Ghi chú: Trình tự đề xuất Intro (Slide 1-3) → Architecture (Slide 4-6) → Demo (Slide 7-11) → Evaluation (Slide 14-16) → Conclusion (Slide 19-20)*
