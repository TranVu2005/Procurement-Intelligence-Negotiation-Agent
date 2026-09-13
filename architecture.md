# Thiết kế kiến trúc & kế hoạch thực hiện — Procurement Intelligence & Negotiation Agent

Ngày: 2026-09-13
Trạng thái: chờ nhóm phê duyệt
Phạm vi: chốt kiến trúc thực thi, các thay đổi trên code hiện có, cách dựng mock data, bộ AutoEval và phân công cho ba thành viên.

---

## 1. Bối cảnh

Ba nhánh `feat/human-c`, `hien`, `linh` đã merge vào `main` (commit `8ff8f1a`). Sau khi merge, 86 unit test chạy được 85 test đạt. Phần lớn logic nghiệp vụ đã hoàn thành, nhưng ba mảng chưa được nối vào đường chạy thật:

- `src/reasoning/scoring.py` (leverage score, xếp hạng, chiến lược đàm phán) không được `src/agent.py` import.
- `confirm_order` trong `src/tools/supplier_tools.py` không nằm trong danh sách tool truyền cho agent.
- `plan` do `src/reasoning/planner.py` sinh ra chỉ được in ra màn hình, không điều khiển việc thực thi.

Ngoài ra `src/agent.py` không chạy được vì `requirements.txt` không ghim phiên bản, môi trường kéo về `langchain==1.4.0` — bản này đã bỏ `AgentExecutor`.

Rubric của môn học (mục 2.2.1) nêu rõ: *"Không bắt buộc một framework hay mô hình cụ thể. Chấm chất lượng quyết định và khả năng kiểm chứng, không chấm theo độ phức tạp kiến trúc."* Rubric cũng chấp nhận mock data: *"có request/response hoặc mock có hợp đồng tương đương; nguồn được gắn với kết quả"*. Hai câu này định hướng toàn bộ thiết kế dưới đây: ưu tiên tính tất định và khả năng truy vết, không chạy theo kiến trúc phức tạp, không bắt buộc phải tích hợp web search thật.

---

## 2. Quyết định kiến trúc

Hệ thống chuyển từ vòng lặp ReAct (`AgentExecutor`) sang **pipeline tất định dựng bằng LangGraph `StateGraph`**. `langgraph 1.2.11` đã có sẵn trong môi trường (đi kèm `langchain 1.4`), nên không cần hạ phiên bản để lấy lại `AgentExecutor`.

Mô hình ngôn ngữ chỉ được gọi ở hai đầu pipeline. Toàn bộ phần ở giữa là Python tất định.

### 2.1 State dùng chung

```python
class AgentState(TypedDict, total=False):
    session_id: str
    user_input: str
    intent: Literal["search_new", "compare_specific", "supplier_detail", "out_of_scope"]
    req: dict                                          # state schema của A
    plan: dict                                         # plan của B
    tool_results: Annotated[list[dict], operator.add]  # audit trail, reducer cộng dồn
    candidates: list[dict]
    rejected: list[dict]
    ranked: list[dict]
    verdict: dict
    replan_count: int
    answer: str
    pending_confirmation: dict | None
```

### 2.2 Sơ đồ luồng

```
START → perceive  [LLM #1: parse + phân loại intent]
          │
          ├─ out_of_scope ───────────────────────→ respond_limits → END
          ├─ supplier_detail ──→ tool_detail ──┐
          ├─ compare_specific ─→ tool_compare ─┤
          └─ search_new → plan → tool_search ──┴→ filter_hard
                                                     │
                        ┌── rỗng & replan_count<3 ───┤
                        ▼                            ▼ còn ứng viên
                    diagnose → replan              score_rank
                        │  (đã 3 lần)                 ▼
                        ▼                        verify_output
                  graceful_fail → END            │        │
                                            fail ┘        ▼ pass
                                       (quay lại diagnose)  respond  [LLM #2]
                                                              ▼
                                                        confirm_gate → END
```

### 2.3 Ngân sách gọi LLM

Đường thành công gọi LLM **đúng hai lần**: `perceive` và `respond`. Các node còn lại — `plan`, `tool_*`, `filter_hard`, `score_rank`, `verify_output`, `diagnose`, `replan`, `confirm_gate` — là Python thuần. Re-plan không tốn thêm lần gọi LLM nào.

Hệ quả: chỉ số "Average LLM Calls / Request" (PDF mục 2.1.4) là một con số cố định, đếm được, gần như không dao động giữa các lần chạy. Đây là lợi thế cần nêu trong báo cáo.

### 2.4 Ba nhánh intent

Rubric mục 2.2.1 nói giảng viên sẽ đưa một yêu cầu mới tại chỗ để kiểm tra khả năng tổng quát hóa. Một pipeline một đường duy nhất dễ gãy ở tình huống này. Thiết kế chia ba nhánh, dùng chung các stage chấm điểm và kiểm tra đầu ra:

| Intent | Ý nghĩa | Node đầu |
|---|---|---|
| `search_new` | Tìm nhà cung cấp mới theo ràng buộc | `plan → tool_search` |
| `compare_specific` | So sánh một danh sách `MaNCC` cụ thể | `tool_compare` |
| `supplier_detail` | Hỏi chi tiết một nhà cung cấp | `tool_detail` |
| `out_of_scope` | Ngoài phạm vi | `respond_limits` |

Nhánh `out_of_scope` trả lời bằng cách nêu rõ giới hạn của hệ thống thay vì cố đoán. Rubric có 1.5 điểm cho *"nhóm giải thích được vì sao cần agent/workflow và các giới hạn của thiết kế"*, nên việc từ chối có lý do vẫn được tính điểm.

### 2.5 Điểm vào mới

```python
def run_request(user_input: str, session_id: str | None = None, _inject: dict | None = None) -> dict
def main() -> None   # REPL mỏng, chỉ bọc quanh run_request
```

`main()` hiện tại là vòng `input()` chặn nên không thể chạy song song. Tách `run_request` là điều kiện bắt buộc để chạy AutoEval và load test nhiều luồng (PDF mục 2.1.2).

### 2.6 Quyền sở hữu module (cập nhật)

| Thành phần | Chủ |
|---|---|
| `src/perception/`, `src/memory/`, node `perceive` | A |
| `src/reasoning/`, các node `plan`/`filter_hard`/`score_rank`/`verify_output`/`diagnose`/`replan`, prompt của `respond` | B |
| `src/tools/`, `src/logging_utils/`, các node `tool_*`, `confirm_gate` | C |
| `src/graph_state.py`, `src/graph.py`, `run_request`, `src/agent.py` | **C** (thay đổi so với bảng cũ) |
| `scripts/`, `tests/eval_set/` | cả ba |

Lý do chuyển phần wiring về C: C đang giữ vai trò tích hợp, còn A tập trung cho perception và memory. Thay đổi này cần ghi vào `CLAUDE.md` và `interface-contracts.md`.

---

## 3. Thay đổi trên code hiện có

Nguyên tắc: giữ tối đa. Phần lớn code đang đúng, vấn đề nằm ở chỗ chưa được nối vào đường chạy.

### 3.1 `src/perception/parser.py` — A

- **Giữ**: `parse_request()`, `update_state()`, hai lớp exception, toàn bộ validation. Schema state không đổi.
- **Sửa (bắt buộc)**: hiện luôn ném `MissingFieldError` nếu thiếu một trong bốn hard constraint. Nhánh `compare_specific` và `supplier_detail` chỉ cần `MaNCC`, nên validation phải phụ thuộc intent.
- **Thêm**: trường `intent` vào chính prompt JSON đang dùng, để phân loại intent không tốn thêm lần gọi LLM.
- **Sửa**: tên model đang lệch giữa hai file (`parser.py` dùng `gemini-3.6-flash`, `agent.py` dùng `gemini-2.5-flash`). Gom về một chỗ cấu hình.
- **Sửa**: bỏ `google.generativeai` (package đã ngừng hỗ trợ, đang phát cảnh báo `FutureWarning`), dùng chung `ChatGoogleGenerativeAI` với node `respond`.

### 3.2 `src/memory/db.py` — A

- **Giữ**: toàn bộ.
- **Thêm bảng `runs`**: `run_id`, `session_id`, `trace_id`, `intent`, `llm_calls`, `tool_calls`, `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `status`. Đây là nguồn số liệu cho PDF mục 2.1.1 và 2.1.4.
- **Thêm**: lưu `plan` và `tool_results` theo session để phục vụ truy vết.

### 3.3 `src/reasoning/planner.py` — B

- **Giữ**: `make_plan` / `make_replan`, giới hạn 3 lần re-plan, sinh `plan_id` mới mỗi lần.
- **Chốt tranh chấp đang làm hỏng test**: giữ thiết kế của B (soft preference không lọc cứng ở `search_suppliers`, để dành cho khâu chấm điểm). Bỏ hẳn hai khóa `material` và `region` khỏi `params` thay vì để `None`. A sửa `tests/test_integration_ab.py` theo. Ghi quyết định vào `interface-contracts.md`.
- **Thêm**: `make_plan` sinh `steps` theo intent, không chỉ một bước `search_suppliers`.

### 3.4 `src/reasoning/scoring.py` — B

- **Giữ toàn bộ.** Đây là file bám sát rubric nhất trong repo.
- **Thêm `verify_output(ranked, req, tool_results) -> verdict`**: đối chiếu schema, tổng tiền, ràng buộc cứng và trích dẫn trước khi trả lời. Rubric dành 2.0 điểm cho hạng mục này và hiện đang bỏ trống.
- **Thêm `diagnose(rejected) -> replan_reason`**: gói `hard_constraint_violations` (đã có) thành nguyên nhân re-plan có mã.

**`verdict` phải là cấu trúc, không phải boolean.** Định dạng tối thiểu:

```python
{
  "passed": bool,
  "violations": [{"code": str, "detail": str}],
  "claims": [{"claim": str, "value": Any, "evidence": {"MaNCC": str, "field": str, "nguon_url": str}}]
}
```

`claims` là thứ AutoEval dùng để tính Citation/Evidence Correctness. Nếu chỉ trả boolean thì metric này không đo được một cách đáng tin.

### 3.5 `src/tools/supplier_tools.py` — C

- **Giữ**: bốn tool, hình dạng lỗi chuẩn, cơ chế lỗi cục bộ từng phần tử, `_normalize`, `retry.py`, và cả `StructuredTool` với `args_schema` Pydantic — đây là bằng chứng cho hạng mục *"Tạo tham số đúng, xác thực input/output"* (2.0 điểm), không được xóa.
- **Thêm**: các trường nguồn vào record trả về (xem mục 4).
- **Đổi vai trò `confirm_order`**: từ tool để LLM tự gọi thành node `confirm_gate` chặn lại, chờ người dùng xác nhận tường minh.

### 3.6 `src/logging_utils/tracer.py` — C

- **Giữ**: `new_trace_id`, `redact`, `log_event`.
- **Thêm**: ghi JSONL ra file theo `trace_id` (hiện chỉ ghi stdout, không đọc lại được), kèm đếm token và số lần gọi LLM. Rubric dành 1.5 điểm cho *"Logging, observability và reproducibility"*.

### 3.7 `src/agent.py` — C

Bỏ `AgentExecutor` và `create_tool_calling_agent`. Thay bằng `src/graph.py` (dựng StateGraph) và `run_request()`. `main()` thu lại thành REPL mỏng.

### 3.8 `requirements.txt` — C

Đã ghim theo đúng môi trường chạy được thực tế (Python 3.14): `langchain==1.4.0`, `langchain-core==1.6.2`, `langgraph==1.2.11`, `langchain-google-genai==4.4.0`, `pydantic==2.13.4`, `python-dotenv==1.2.3`, `psutil==7.2.2`.

Đã bỏ `langchain-community` và `langchain-anthropic` (không nơi nào dùng). `google-generativeai==0.8.6` **tạm giữ** vì `src/perception/parser.py` còn import; gỡ sau khi A hoàn tất việc chuyển sang `ChatGoogleGenerativeAI` ở mục 3.1.

---

## 4. Mock data

`generate_mock_data.py` đã đi đúng hướng: tên công ty và khu vực lấy từ bốn nguồn tổng hợp công khai (có ghi URL ở cuối file), mọi giá trị số được ghi rõ là mock trong docstring. Vấn đề là sự minh bạch đó nằm trong comment chứ không nằm trong dữ liệu, nên agent không trích dẫn được và AutoEval không chấm được.

### 4.1 Đưa nguồn vào từng record

```json
{
  "MaNCC": "NCC001",
  "TenNCC": "Noi That Hoa Phat",
  "...": "...",
  "nguon_url": "https://mytour.vn/vi/blog/bai-viet/top-9-don-vi-...",
  "nguon_type": "public_listing",
  "fetched_at": "2026-09-13",
  "simulated_fields": ["Gia", "MOQ", "TonKho", "ThoiGianGiao", "BaoHanh", "ChietKhauTheoSoLuong", "DiemUyTin"]
}
```

`simulated_fields` là trường quan trọng nhất: nó biến câu "trường này mô phỏng, trường kia có thật" thành thứ kiểm chứng được bằng máy, và là câu trả lời sẵn cho phần vấn đáp.

Tool trả record thì truyền thẳng bốn trường này ra ngoài. Node `respond` bắt buộc gắn `MaNCC` và `nguon_url` vào mọi con số nêu ra. `verify_output` kiểm tra mọi con số trong câu trả lời phải truy được về một record trong `tool_results`; không truy được thì chặn, không cho trả lời.

Các record `EDGE*` giữ nguyên, đánh `nguon_type: "synthetic_edge_case"` và thêm trường `muc_dich` ghi rõ chúng tồn tại để kiểm tra hành vi gì. Không trình bày chúng như dữ liệu có thật.

### 4.2 Quy trình thu thập

```
mock_data/sources.csv        ← người thu tay, chỉ chứa dữ liệu THẬT
        ↓
generate_mock_data.py        ← máy sinh các trường còn thiếu, gắn simulated_fields
        ↓
mock_data/suppliers.json
```

Mỗi dòng `sources.csv`: `TenNCC, KhuVuc, LoaiSanPham, Gia_niem_yet, nguon_url, fetched_at, nguoi_thu`. Cột `Gia_niem_yet` để trống nếu trang không công bố giá; khi có giá thật thì `Gia` được loại khỏi `simulated_fields`, làm trích dẫn mạnh hơn.

Tách CSV khỏi generator để bất kỳ ai cũng mở ra kiểm tra được phần nào do người thu, phần nào do máy sinh.

### 4.3 Bổ sung phân bố

Bộ dữ liệu hiện có 38 record của 19 công ty, nhưng phân bố lệch:

| Nhóm | Hiện tại | Mục tiêu |
|---|---|---|
| `ghế văn phòng` | 10 | ≥ 8 (đạt) |
| `sofa` | 10 | ≥ 8 (đạt) |
| `tủ hồ sơ` | 8 | ≥ 8 (đạt) |
| `bàn làm việc` | 6 | ≥ 8 |
| `kệ` | 4 | ≥ 8 |
| `Ha Noi` | 25 | ≥ 5 (đạt) |
| `TP.HCM` | 12 | ≥ 5 (đạt) |
| `Da Nang` | 1 | ≥ 5 |

Riêng các ngưỡng trên đã cần thêm khoảng 10 record (đưa tổng lên ~48). Mục tiêu đặt ở **50–55 record** để mỗi nhánh demo có dư ứng viên cạnh tranh, trong khi vẫn giữ được các trường hợp rỗng có chủ đích.

### 4.4 Đóng băng để tái lập

Thêm `dataset_version` và git sha vào dữ liệu (hoặc file `mock_data/VERSION`). AutoEval ghi version vào báo cáo. Dữ liệu đổi thì tăng version. Không có cơ chế này thì số liệu trong báo cáo không tái lập được, đúng chỗ rubric soi ở hạng mục *"chạy lặp, báo cáo variance"*.

### 4.5 Về web search thật

Rubric chấp nhận mock có hợp đồng tương đương, nên web search thật không bắt buộc. Tích hợp web sẽ làm tăng độ trễ, chi phí và độ dao động — đúng ba thứ PDF mục 2.1 đang chấm — và thêm một nguồn sai lệch mới. Kết luận: giữ mock làm nguồn chính, thiết kế tool dưới dạng adapter để có thể cắm nguồn web sau, chỉ làm khi đã xong toàn bộ hạng mục khác.

---

## 5. AutoEval và đo hiệu năng

### 5.1 Tách hai tầng

`tests/run_autoeval.py` hiện tại dispatch theo `if cid == "case_001"` và chỉ kiểm tra hàm module, không chạy agent end-to-end. Cách này vướng đúng điều rubric phạt (*"hard code theo test"*), đồng thời không đo được 5 metric vốn nói về hành vi của agent.

| Tầng | File | Vai trò |
|---|---|---|
| Unit / integration | `tests/test_*.py` | Chạy nhanh, gác hồi quy. Đổi `tests/run_autoeval.py` thành `tests/test_parse_memory_suite.py` để về đúng tầng này |
| AutoEval | `scripts/run_autoeval.py` | Gọi `run_request()` end-to-end, chấm 5 metric |

### 5.2 Case là dữ liệu, oracle khai báo

```jsonc
{
  "id": "E01_happy_search",
  "category": "happy_path",
  "turns": ["Cần 50 ghế văn phòng, ngân sách 200 triệu, giao trong 14 ngày, ưu tiên Hà Nội"],
  "inject": null,
  "oracle": {
    "must_reach_intent": "search_new",
    "must_call_tools": ["search_suppliers", "compare_price"],
    "must_not_call_tools": ["confirm_order"],
    "constraints": {"total_price_lte": 200000000, "delivery_lte": 14, "quantity_gte_moq": true},
    "must_cite": true,
    "must_ask_user": false,
    "expect_status": "success"
  }
}
```

Runner là một hàm chấm chung đọc `oracle`. Thêm case mới chỉ là thêm một dòng JSONL, không sửa code.

`category` phủ sáu nhóm: `happy_path`, `missing_info`, `conflict`, `tool_failure`, `adversarial`, `multi_turn`.

### 5.3 Định nghĩa pass/fail của 5 metric

| Metric | Cách tính |
|---|---|
| Task Success Rate | `expect_status` khớp và mọi điều kiện `must_*` thỏa, chia tổng số case |
| Constraint Satisfaction Rate | mọi ràng buộc trong `oracle.constraints` đúng trên `ranked[0]`, chia số case có ràng buộc. Với case không sinh `ranked` (nhánh `compare_specific`, `supplier_detail`), áp lên record mà agent nêu ra trong câu trả lời |
| Tool Call Success Rate | số tool call không trả lỗi sau retry, chia tổng số tool call, đọc từ `tool_results` |
| Citation / Evidence Correctness | số phần tử trong `verdict.claims` có `evidence` truy được về `tool_results`, chia tổng số claim |
| Failure Recovery Rate | trong nhóm case có `inject`: số case kết thúc ở `success` hoặc `graceful_fail` có nguyên nhân rõ, chia tổng số case inject |

### 5.4 Failure injection

Dùng lại `_simulate_error` trong tools và `retry.py`. Thêm đường truyền từ ngoài qua tham số `_inject` của `run_request`, để eval bật lỗi mà không phải sửa code tool. Phủ bốn tình huống PDF mục 2.1.3: timeout, HTTP 429/5xx, trả dữ liệu rỗng, một nguồn không truy cập được.

### 5.5 Hiệu năng

Wrapper quanh `run_request` ghi vào bảng `runs`: `t_start`, `t_first_token`, `t_end`, `llm_calls`, `tool_calls`, `tokens_in`, `tokens_out`. Báo cáo P50/P95 truy từ bảng.

TTFT chỉ có ý nghĩa nếu node `respond` phát theo luồng (streaming). Không bật streaming thì TTFT gần bằng end-to-end latency và con số vô nghĩa.

### 5.6 Load test

`scripts/run_loadtest.py`, dùng ThreadPool hoặc asyncio, chạy các mức 1 → 5 → 10 → 20 → 50 CCU.

- Mức 1–5 CCU: gọi Gemini thật.
- Mức 10–50 CCU: chạy với `--llm=stub`. Stub trả câu cố định và `sleep()` theo phân phối độ trễ đo được ở mức thật.
- Báo cáo ghi rõ mức nào dùng LLM thật, mức nào dùng stub.

Đo: throughput (req/s), P50/P95, error rate, CPU/RAM qua `psutil`.

### 5.7 Chi phí và độ ổn định

Từ bảng `runs`: số lần gọi LLM trung bình mỗi request (kỳ vọng đúng 2.0), số tool call trung bình, token vào/ra, chi phí ước tính theo bảng giá Gemini.

Chạy AutoEval ba lần, báo cáo variance của từng metric.

### 5.8 Đầu ra

`reports/autoeval_<timestamp>.json` và `.md`, kèm `dataset_version`, để dán thẳng vào báo cáo và truy ngược được về từng lần chạy.

---

## 6. Phân công

Không gắn deadline. Thứ tự dưới đây là thứ tự phụ thuộc: việc ở đợt trước mở khóa việc ở đợt sau. Trong cùng một đợt, ba người làm song song.

### Đợt 0 — Gỡ chặn (cả nhóm, làm trước mọi thứ)

| Việc | Ai |
|---|---|
| Họp chốt ba quyết định ở mục 8 (Quyết định cần phê duyệt) | Cả ba |
| Cập nhật `interface-contracts.md` và `CLAUDE.md` theo kết quả họp | Cả ba |
| Ghim phiên bản trong `requirements.txt`, cài lại venv | C |

Chưa chốt xong đợt này thì mọi người đều bị chặn.

### Đợt 1 — Dựng khung chạy

**C (đường găng — cả nhóm chờ):**

1. `src/graph_state.py`: định nghĩa `AgentState`.
2. `src/graph.py`: dựng StateGraph đầy đủ với **node giả** cho mọi node (trả dữ liệu cứng), wiring, conditional edge, `run_request()`. Mục tiêu là graph chạy được end-to-end ngay cả khi chưa có node thật.
3. `src/agent.py`: rút gọn thành REPL mỏng gọi `run_request`.

**A (song song, không chờ C):**

1. Thêm `intent` vào prompt JSON của `parse_request`.
2. Validation theo intent.
3. Bỏ `google.generativeai`, chuyển sang `ChatGoogleGenerativeAI`; gom cấu hình model về một chỗ.
4. Sửa `tests/test_integration_ab.py` theo quyết định ở mục 8.

**B (song song, không chờ C):**

1. `verify_output()` trong `scoring.py`, trả `verdict` có cấu trúc như mục 3.4.
2. `diagnose()` gói `hard_constraint_violations` thành `replan_reason` có mã.
3. `make_plan` sinh `steps` theo intent.

### Đợt 2 — Cắm node thật vào graph

| Việc | Ai |
|---|---|
| Node `perceive` | A |
| Node `plan`, `filter_hard`, `score_rank`, `verify_output`, `diagnose`, `replan`; prompt cho `respond` và `respond_limits` | B |
| Node `tool_search`, `tool_compare`, `tool_detail`, `confirm_gate`, `respond` (nối LLM, bật streaming) | C |

Kết thúc đợt này chạy thử một request thật end-to-end. Đây là mốc "agent sống lại".

### Đợt 3 — Dữ liệu và observability

| Việc | Ai |
|---|---|
| `mock_data/sources.csv` — thu thập tay dữ liệu thật | C (A và B hỗ trợ nếu cần khối lượng) |
| Cập nhật `generate_mock_data.py`: sinh trường nguồn, `simulated_fields`, `dataset_version`; bổ sung phân bố theo mục 4.3 | C |
| Tool truyền các trường nguồn ra ngoài | C |
| `tracer.py` ghi JSONL, đếm token và số lần gọi LLM | C |
| Bảng `runs` trong `db.py`; lưu `plan` và `tool_results` theo session | A |
| Test session isolation | A |
| `score_rank` và `verify_output` đọc các trường nguồn mới | B |

### Đợt 4 — AutoEval và đo đạc

| Việc | Ai |
|---|---|
| Chốt định dạng `oracle` (cả nhóm thống nhất trước khi viết case) | Cả ba |
| Viết eval case nhóm `missing_info`, `multi_turn` | A |
| Viết eval case nhóm `happy_path`, `conflict` | B |
| Viết eval case nhóm `tool_failure`, `adversarial` | C |
| `scripts/run_autoeval.py`: runner và 5 metric | C |
| `scripts/run_loadtest.py` và LLM stub | C |
| Sinh báo cáo `reports/*.json` và `.md` | A |
| Đổi `tests/run_autoeval.py` thành `tests/test_parse_memory_suite.py` | A |

### Đợt 5 — Báo cáo và demo

| Việc | Ai |
|---|---|
| Chạy AutoEval ba lần, tổng hợp variance | Cả ba |
| Phân tích failure mode, nguyên nhân gốc, giới hạn hệ thống | Cả ba |
| Dựng hai kịch bản demo bắt buộc: một luồng thành công, một luồng có lỗi tool hoặc re-plan | Cả ba |
| Slide, phân vai trình bày, luyện vấn đáp chéo | Cả ba |

---

## 7. Các mốc cần ping nhau

| Thời điểm | Ai báo ai | Lý do |
|---|---|---|
| Sau khi chốt ba quyết định ở mục 8 | Cả nhóm | Mọi việc phía sau phụ thuộc |
| C ghim xong `requirements.txt` | C → A, B | Cả hai phải cài lại venv, nếu không sẽ gặp lỗi import khác nhau |
| C xong `AgentState` | C → A, B | A và B viết node phải bám đúng khóa trong state |
| C xong graph với node giả | C → A, B | Mốc mở khóa: từ đây A và B cắm node thật mà không chặn nhau |
| B chốt định dạng `verdict` | B → C | `respond` và AutoEval đều đọc cấu trúc này; chốt muộn sẽ phải viết lại metric |
| A chốt schema bảng `runs` | A → C | C ghi log và số đo vào bảng này |
| A gom xong cấu hình model | A → C | Hai bên dùng chung một client LLM |
| C xong dataset có trường nguồn | C → B | `score_rank` và `verify_output` đọc các trường mới |
| Trước khi ai đó viết eval case đầu tiên | Cả nhóm | Phải thống nhất định dạng `oracle`, nếu không ba người viết ba kiểu |
| Cả ba cắm xong node thật | Cả nhóm | Chạy smoke test end-to-end cùng nhau |
| Trước khi ai đó sửa một trường hay tên action trong contract | Người sửa → hai người còn lại | Quy định sẵn tại `SYSTEM-RULES.md` mục 7; đây đúng chỗ nhóm đã vấp một lần |

---

## 8. Quyết định cần cả nhóm phê duyệt

1. **Bỏ `material` và `region` khỏi `plan.steps[0].params`.** Soft preference chuyển hết sang khâu chấm điểm. Kéo theo: A sửa `tests/test_integration_ab.py`, cập nhật `interface-contracts.md`.
2. **Thêm bốn trường nguồn vào record nhà cung cấp** (`nguon_url`, `nguon_type`, `fetched_at`, `simulated_fields`). Đổi hợp đồng tool, cần A và B xác nhận.
3. **Chuyển quyền sở hữu `src/agent.py`, `src/graph.py`, `src/graph_state.py` về C.** Cập nhật bảng ownership trong `CLAUDE.md`.

---

## 9. Rủi ro

| Rủi ro | Ảnh hưởng | Cách giảm |
|---|---|---|
| Pipeline cứng không xử lý được yêu cầu lạ giảng viên đưa tại chỗ | Mất điểm demo | Ba nhánh intent ở mục 2.4; nhánh `out_of_scope` trả lời nêu rõ giới hạn |
| B chốt `verdict` muộn | C phải viết lại metric Citation | Đưa việc chốt định dạng lên đầu đợt 1, coi là việc chặn |
| Thu thập `sources.csv` tốn thời gian hơn dự kiến | Trễ đợt 3 | Dữ liệu thật tối thiểu là tên, khu vực, dòng sản phẩm; giá niêm yết là phần thêm, thiếu vẫn chạy được |
| Gemini rate limit khi chạy AutoEval nhiều lần | Số liệu nhiễu | Cache kết quả LLM theo hash input trong lúc phát triển; load test mức cao dùng stub |
| Lặp lại tình huống mỗi người code trên một ảnh chụp `main` khác nhau | Xung đột merge lớn như lần trước | Merge vào `main` sau mỗi đợt, không giữ nhánh riêng qua nhiều đợt |

---

## 10. Ngoài phạm vi

- Tích hợp web search thật (xem mục 4.5).
- Giao diện web hoặc API HTTP. Rubric không chấm giao diện; `run_request` đã đủ cho eval và load test.
- Kiến trúc đa tác tử (Hub-and-Spoke, Blackboard, Direct Messaging, Event-Driven). Bài toán không thỏa điều kiện nào để cần multi-agent, và rubric không cộng điểm cho độ phức tạp kiến trúc.
