# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

LangChain agent that takes a natural-language furniture procurement request, searches
mock suppliers, compares them, and proposes a negotiation strategy with a leverage
score. Course final project (AI Guru AEF1), split across 3 owners — see "Module
ownership" below.

## Commands

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # fill in GOOGLE_API_KEY

python -m src.agent                                          # run the agent
sqlite3 src/memory/state.db < src/memory/schema.sql           # (re)init SQLite state DB
python scripts/run_autoeval.py --eval-set tests/eval_set/cases.jsonl   # run AutoEval
```

No test framework/linter is wired up yet — `tests/eval_set/cases.jsonl` is a JSONL
eval set consumed by `scripts/run_autoeval.py`, not a pytest suite.

## Architecture

Three modules communicate only through the contracts frozen in
[interface-contracts.md](interface-contracts.md) (source of truth; `PROJECT-SETUP.md`
has a shorter duplicate). **Never rename a field or action without updating that file
and getting the other two owners to re-confirm** (see `SYSTEM-RULES.md` §7).

- **`src/perception/`** — parses free-text input into the **State Schema**: a dict with
  `hard_constraints` (product_type, quantity, budget_max, delivery_deadline_days) and
  `soft_constraints` (material_preference, region_preference, min_trust_score), plus
  `conversation_history` and `decisions_made`. On a change of mind, fields are
  **overwritten in place**, never kept as parallel old/new versions.
- **`src/memory/`** — SQLite persistence for the state above (`schema.sql` /
  `db.py`). Never mix data across `session_id`s.
- **`src/reasoning/`** — `planner.py` turns state into a **Plan** (ordered `steps`, each
  with `action`/`params`/`reason`/`depends_on`); `action` names must match tool names
  in `src/tools/` exactly. `scoring.py` computes the leverage score. Re-planning creates
  a new `plan_id` and increments `replan_count` instead of overwriting the old plan
  (audit trail); capped at 3 re-plans per request.
- **`src/tools/`** — LangChain `Tool` wrappers (`supplier_tools.py`) over the mock
  dataset (`mock_data/suppliers.json`, ~15-20 suppliers with fields `MaNCC, TenNCC,
  LoaiSanPham, ChatLieu, Gia, DonViTinh, MOQ, TonKho, ThoiGianGiao, BaoHanh,
  ChietKhauTheoSoLuong, DiemUyTin, KhuVuc`). Tools return structured JSON only, never
  free text; every error uses the shared shape
  `{"error": true, "error_type": "no_match|timeout|invalid_input|tool_unavailable", "message": "..."}`.
  A bad element in a batch call (e.g. one bad `supplier_id` in `compare_price`) must
  error only that element, not fail the whole response.
- **`src/logging_utils/tracer.py`** — trace-ID logging; `redact()` must be used on any
  logged payload so API keys/secrets never hit logs.
- **`src/agent.py`** — entrypoint wiring perception + reasoning + tools into a LangChain
  `AgentExecutor`. Currently a stub (`NotImplementedError`), like most of `src/`.

## User context

The user operating Claude Code in this repo is **Nguoi C** — owns `src/tools/` and
`src/logging_utils/`. Frame explanations and suggestions from that vantage point
(tool contract, mock dataset, tracing/logging), and flag before touching
`src/perception/`, `src/memory/`, or `src/reasoning/` since those belong to A/B.

## Module ownership

Don't edit another owner's field/logic without their sign-off (`SYSTEM-RULES.md` §1).

| Module | Owner |
|---|---|
| `src/perception/`, `src/memory/` | Nguoi A |
| `src/reasoning/` | Nguoi B |
| `src/tools/`, `src/logging_utils/` | Nguoi C |
| `tests/eval_set/`, `scripts/run_autoeval.py` | all 3 |

## Project-specific rules (`SYSTEM-RULES.md`)

- Timestamps: ISO 8601. Currency: VND as plain numbers (no "đ"/commas).
- No hard-coding sample inputs into processing logic.
- The agent must never silently fill in missing important info — ask the user or state
  the assumption explicitly. Conflicting constraints (e.g. budget too low for MOQ) must
  be surfaced, never silently dropped.
- High-consequence actions (e.g. confirming an order) require an explicit confirmation
  step, never auto-executed.
- AutoEval reports at least 5 metrics: Task Success Rate, Constraint Satisfaction Rate,
  Tool Call Success Rate, Citation/Evidence Correctness, Failure Recovery Rate.
