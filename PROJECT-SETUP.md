# Procurement Intelligence & Negotiation Agent — Nội thất

Dự án cuối khóa AI Guru AEF1 — Agent nhận yêu cầu mua sắm nội thất, chủ động tìm
kiếm nhà cung cấp (NCC), so sánh theo nhiều tiêu chí, chấm điểm đòn bẩy đàm phán
(leverage score) và đề xuất phương án + chiến lược đàm phán.

## 1. Tech stack

| Thành phần | Lựa chọn |
|---|---|
| Ngôn ngữ | Python 3.10+ |
| Agent framework | LangChain (`AgentExecutor` + `Tool` / `StructuredTool`) |
| Lưu state | SQLite |
| Nguồn dữ liệu (giai đoạn 1) | Mock dataset (JSON), web search thật thêm sau |
| LLM provider | Anthropic Claude (qua `langchain-anthropic`) — đổi sang OpenAI nếu nhóm có key khác |

## 2. Cấu trúc thư mục

```
procurement-agent/
├── src/
│   ├── perception/          # A — parse input tự nhiên -> structured state
│   │   └── parser.py
│   ├── memory/              # A — quản lý state qua SQLite
│   │   ├── db.py
│   │   └── schema.sql
│   ├── reasoning/           # B — task decomposition, leverage score, re-plan
│   │   ├── planner.py
│   │   └── scoring.py
│   ├── tools/               # C — LangChain Tool wrappers, đọc mock dataset
│   │   ├── supplier_tools.py
│   │   └── mock_data/
│   │       └── suppliers.json
│   ├── logging_utils/       # C — trace ID, logging, che dữ liệu nhạy cảm
│   │   └── tracer.py
│   └── agent.py             # entrypoint: khởi tạo AgentExecutor, ráp A+B+C
├── tests/
│   └── eval_set/            # bộ test AutoEval (happy path, edge case...)
│       └── cases.jsonl
├── scripts/
│   └── run_autoeval.py
├── requirements.txt
├── .env.example
└── README.md
```

## 3. Cài đặt môi trường

```bash
# 1. Tạo virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Cài dependency
pip install -r requirements.txt
```

**`requirements.txt`** (khởi điểm, bổ sung thêm khi cần):
```
langchain
langchain-community
langchain-anthropic
python-dotenv
pydantic
```

**`.env.example`** (copy thành `.env`, điền key thật, KHÔNG commit `.env`):
```
ANTHROPIC_API_KEY=your_key_here
```

```bash
cp .env.example .env
# rồi sửa .env, điền API key
```

## 4. Khởi tạo dữ liệu

### 4.1 SQLite — khởi tạo DB state

`src/memory/schema.sql` (bản nháp — A chỉnh lại theo nhu cầu thực tế):
```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    created_at   TEXT
);

CREATE TABLE IF NOT EXISTS constraints (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT,
    type         TEXT,     -- 'hard' hoặc 'soft'
    field        TEXT,     -- vd: 'budget', 'material', 'delivery_deadline'
    value        TEXT,
    updated_at   TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS conversation_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT,
    role         TEXT,     -- 'user' hoặc 'agent'
    content      TEXT,
    timestamp    TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

Khởi tạo:
```bash
sqlite3 src/memory/state.db < src/memory/schema.sql
```

### 4.2 Mock dataset nhà cung cấp nội thất

`src/tools/mock_data/suppliers.json` — mỗi bản ghi theo field đã chốt:

```json
[
  {
    "MaNCC": "NCC001",
    "TenNCC": "Nội Thất Hòa Phát",
    "LoaiSanPham": "Ghế văn phòng",
    "ChatLieu": "Nhựa + khung thép",
    "Gia": 850000,
    "DonViTinh": "cái",
    "MOQ": 20,
    "TonKho": 150,
    "ThoiGianGiao": 10,
    "BaoHanh": 24,
    "ChietKhauTheoSoLuong": "5% cho đơn >=50 cái",
    "DiemUyTin": 4.5,
    "KhuVuc": "Hà Nội"
  }
]
```

Tạo khoảng 15–20 bản ghi tương tự, đa dạng loại sản phẩm (ghế, bàn, tủ, kệ), khoảng
giá, thời gian giao và điểm uy tín để bộ test có đủ tình huống so sánh.

## 5. Hợp đồng giao diện giữa 3 module (đã chốt buổi họp 1)

**State schema (A xuất ra, B/C đọc vào)** — dict/JSON dạng:
```json
{
  "session_id": "abc123",
  "hard_constraints": {"budget_max": 200000000, "quantity": 50, "delivery_deadline_days": 14},
  "soft_constraints": {"material_preference": "gỗ tự nhiên"},
  "history": ["..."]
}
```

**Plan format (B xuất ra, C đọc vào)** — danh sách bước có rationale:
```json
{
  "steps": [
    {"action": "search_suppliers", "params": {"product_type": "ghế văn phòng"}, "reason": "lọc theo hard constraint số lượng/ngân sách"},
    {"action": "compare_price", "params": {"supplier_ids": ["NCC001", "NCC002"]}, "reason": "tính leverage score"}
  ]
}
```

**Tool contract (C định nghĩa, B gọi qua LangChain Tool)** — mỗi tool nhận structured
input theo schema Pydantic, trả JSON có field rõ ràng, không trả text tự do để B dễ
parse kết quả.

## 6. Chạy thử agent

```bash
python src/agent.py
```

## 7. Chạy AutoEval

```bash
python scripts/run_autoeval.py --eval-set tests/eval_set/cases.jsonl
```

Script cần xuất ra tối thiểu 5 chỉ số: Task Success Rate, Constraint Satisfaction
Rate, Tool Call Success Rate, Citation/Evidence Correctness, Failure Recovery Rate.

## 8. Phân công module (tham chiếu)

| Module | Phụ trách |
|---|---|
| `perception/`, `memory/` | Người A |
| `reasoning/` | Người B |
| `tools/`, `logging_utils/` | Người C |
| `tests/eval_set/`, `scripts/run_autoeval.py` | Cả 3 |

## 9. Lưu ý bảo mật khi setup

- Không commit file `.env` hoặc bất kỳ API key nào lên git — thêm `.env` vào `.gitignore`.
- Log (`logging_utils/tracer.py`) phải che các field nhạy cảm (API key, thông tin cá nhân nếu có) trước khi ghi ra file/console.
