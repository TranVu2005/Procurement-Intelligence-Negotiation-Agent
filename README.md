# Procurement Intelligence & Negotiation Agent — Nội thất

Dự án cuối khóa AI Guru AEF1. Xem chi tiết kiến trúc, hợp đồng interface giữa 3
module tại [interface-contracts.md](interface-contracts.md), rule chung hệ
thống tại [SYSTEM-RULES.md](SYSTEM-RULES.md).

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # điền ANTHROPIC_API_KEY và GOOGLE_API_KEY
```

`src/agent.py` (entrypoint AgentExecutor) vẫn đang stub, chưa ráp xong 3
module. Dùng các lệnh dưới đây để chạy/test từng phần đã có tới hôm nay.

## Chạy test

```bash
python -m unittest tests.test_planner -v      # Reasoning (B)
python tests/test_parse_and_memory.py         # Perception + Memory (A) — chạy trực
                                               # tiếp, không qua unittest discover (script
                                               # tự sys.exit(), gọi Gemini API thật nên có
                                               # thể dao động nếu bị rate-limit)
```

## Demo 3 tool (Action/Tool Use — search_suppliers, get_supplier_detail, compare_price)

```bash
python -m src.tools.supplier_tools
```

## Demo end-to-end 1 câu hỏi mẫu (Perception → Reasoning → Tool)

```bash
python -m scripts.demo_e2e
```

Nếu chưa có `GOOGLE_API_KEY` thật trong `.env`, script tự fallback sang state
mẫu (`session_states_sample.json`) để vẫn demo được phần Reasoning + Tool.
