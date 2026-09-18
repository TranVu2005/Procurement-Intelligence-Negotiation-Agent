# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Agent that takes a natural-language furniture procurement request, searches mock
suppliers, compares them, and proposes a negotiation strategy with a leverage score.
Course final project (AI Guru AEF1), split across 3 owners — see "Module ownership".

Three documents govern the work, in this order of authority:

- [interface-contracts.md](interface-contracts.md) — **source of truth** for every field
  and action exchanged between modules. Never rename a field or an action without
  updating this file and getting the other two owners to re-confirm (`SYSTEM-RULES.md` §7).
  This is the rule the team has already broken once; it caused the merge mess of Sept 13.
- [SYSTEM-RULES.md](SYSTEM-RULES.md) — behavioural rules (see the summary at the bottom).
- [architecture.md](architecture.md) — the agreed execution design and work split.
  Status: awaiting group sign-off on the three decisions in §8.

The implementation plan for the C role lives at
[docs/superpowers/plans/2026-09-14-role-c-implementation.md](docs/superpowers/plans/2026-09-14-role-c-implementation.md)
(16 tasks, each with tests and exact commands).

## Commands

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows; POSIX: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # fill in GOOGLE_API_KEY

python -m unittest discover tests "test_*.py"   # full suite, run from the repo root
python -m unittest tests.test_tools -v          # one test module
python -m src.agent                             # run the agent (REPL)
python generate_mock_data.py                    # regenerate the mock dataset
sqlite3 src/memory/state.db < src/memory/schema.sql          # (re)init SQLite state DB
python scripts/run_autoeval.py --eval-set tests/eval_set/cases.jsonl
```

Note the discover invocation: `-s tests -t .` fails with `ImportError: Start directory
is not importable` because `tests/` has no `__init__.py`.

Tests are stdlib `unittest`, not pytest — pytest is not installed and is not in
`requirements.txt`. There is no linter wired up.

## Current state

- Pipeline LangGraph chạy end-to-end (`src/graph.py::run_request`); `src/agent.py` là REPL mỏng.
- Test: chạy `python -m unittest discover tests "test_*.py"` để lấy con số hiện tại — không ghi
  cứng số lượng ở đây vì nó đổi mỗi task.
- Dữ liệu: 32 bản ghi legacy mô phỏng (`NCC###`), 6 edge case (`EDGE*`), cộng bản ghi thật
  `SRC###` sinh từ `src/tools/mock_data/sources/*.csv`. Phiên bản ở `src/tools/mock_data/VERSION`.
- AutoEval: `python scripts/run_autoeval.py --eval-set tests/eval_set --llm real --repeat 3`;
  báo cáo mới nhất nằm trong `reports/`. `tests/run_autoeval.py` là file khác (tầng unit test).
- Việc đang chờ A/B: xem `HANDOFF-C-2026-09-18.md`.

## Architecture

The agreed design (architecture.md §2) replaces the ReAct `AgentExecutor` loop with a
**deterministic LangGraph `StateGraph` pipeline**. The LLM is called exactly twice per
successful request — `perceive` and `respond`; every node between them is plain Python,
so "average LLM calls per request" is a fixed, countable number. Re-planning costs no
extra LLM call.

Three intent branches share the scoring and verification stages: `search_new`
(`plan → tool_search`), `compare_specific` (`tool_compare`), `supplier_detail`
(`tool_detail`), and `out_of_scope` (`respond_limits`, which states the system's limits
rather than guessing).

Modules:

- **`src/perception/`** — parses free text into the **State Schema**: a dict with
  `hard_constraints` (product_type, quantity, budget_max, delivery_deadline_days) and
  `soft_constraints` (material_preference, region_preference, min_trust_score), plus
  `conversation_history` and `decisions_made`. On a change of mind, fields are
  **overwritten in place**, never kept as parallel old/new versions.
- **`src/memory/`** — SQLite persistence for the state above (`schema.sql` / `db.py`).
  Never mix data across `session_id`s.
- **`src/reasoning/`** — `planner.py` turns state into a **Plan** (ordered `steps`, each
  with `action`/`params`/`reason`/`depends_on`); `action` names must match tool names in
  `src/tools/` exactly. `scoring.py` computes the leverage score, ranks candidates and
  generates the negotiation strategy. Re-planning creates a new `plan_id` and increments
  `replan_count` instead of overwriting the old plan (audit trail); capped at 3 re-plans.
  `make_plan` deliberately emits only the search step — supplier IDs for `compare_price`
  do not exist until search returns, so the orchestrator appends the dependent calls.
- **`src/tools/`** — `StructuredTool` wrappers with Pydantic `args_schema`
  (`supplier_tools.py`) over the mock dataset (`mock_data/suppliers.json`: 38 records
  today, target 50–55, fields `MaNCC, TenNCC, LoaiSanPham, ChatLieu, Gia, DonViTinh, MOQ,
  TonKho, ThoiGianGiao, BaoHanh, ChietKhauTheoSoLuong, DiemUyTin, KhuVuc`). Tools return
  structured JSON only, never free text; every error uses the shared shape
  `{"error": true, "error_type": "no_match|timeout|invalid_input|tool_unavailable", "message": "..."}`.
  A bad element in a batch call (e.g. one bad `supplier_id` in `compare_price`) must
  error only that element, not fail the whole response. `retry.py` retries only
  `timeout`/`tool_unavailable`; deterministic errors are never retried. The `args_schema`
  definitions are graded evidence — do not delete them to "simplify".
- **`src/logging_utils/tracer.py`** — trace-ID logging; `redact()` must be used on any
  logged payload so API keys/secrets never hit logs. The rubric scores 0 for a leaked
  secret, so treat this as load-bearing.
- **`src/agent.py`** — entrypoint. Being reduced to a thin REPL around `run_request()`;
  the pipeline itself moves to `src/graph.py` + `src/graph_state.py`, with per-owner node
  modules under `src/nodes/`.

`generate_mock_data.py` derives `suppliers.json` from hand-collected real data. Company
names, regions and source URLs are real; every numeric field is simulated and must be
labelled as such per record (`simulated_fields`), not only in a comment — the agent has
to cite sources and AutoEval has to check those citations.

## User context

The user operating Claude Code in this repo is **Nguoi C** — owns `src/tools/`,
`src/logging_utils/`, and (pending Decision 3) the graph wiring. Frame explanations and
suggestions from that vantage point, and flag before touching `src/perception/`,
`src/memory/`, or `src/reasoning/` since those belong to A/B.

## Module ownership

Don't edit another owner's field/logic without their sign-off (`SYSTEM-RULES.md` §1).

| Module | Owner |
|---|---|
| `src/perception/`, `src/memory/`, node `perceive` | Nguoi A |
| `src/reasoning/`, nodes `plan`/`filter_hard`/`score_rank`/`verify_output`/`diagnose`/`replan`, the `respond` prompt | Nguoi B |
| `src/tools/`, `src/logging_utils/`, nodes `tool_*`, `confirm_gate`, `respond` wiring | Nguoi C |
| `src/agent.py`, `src/graph.py`, `src/graph_state.py`, `src/llm.py` | Nguoi C (Decision 3, pending sign-off) |
| `tests/eval_set/`, `scripts/` | all 3 |

Everyone merges into `main` at the end of each phase. The Sept 13 merge cost 9 conflicted
files because a branch sat unmerged from a very old commit — don't repeat it.

## Project-specific rules (`SYSTEM-RULES.md`)

- Timestamps: ISO 8601. Currency: VND as plain numbers (no "đ"/commas).
- No hard-coding sample inputs into processing logic. Eval cases are data, not `if` branches.
- The agent must never silently fill in missing important info — ask the user or state
  the assumption explicitly. Conflicting constraints (e.g. budget too low for MOQ) must
  be surfaced, never silently dropped.
- High-consequence actions (e.g. confirming an order) require an explicit confirmation
  step, never auto-executed. The agent must not infer consent from context.
- Every number in an answer must trace back to a tool result, with `MaNCC` and source URL.
- AutoEval reports at least 5 metrics: Task Success Rate, Constraint Satisfaction Rate,
  Tool Call Success Rate, Citation/Evidence Correctness, Failure Recovery Rate.
