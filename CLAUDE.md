# Repository guidance

Procurement agent for Vietnamese furniture requests. Read [README.md](README.md) for setup and current commands.

## Contracts and behavior

- [interface-contracts.md](interface-contracts.md): source of truth for shared fields/actions; coordinate contract changes across modules.
- [SYSTEM-RULES.md](SYSTEM-RULES.md): behavior and evidence rules.
- [architecture.md](architecture.md): execution design.
- [docs/reasoning.md](docs/reasoning.md): planning, scoring, verification and re-plan.

LangGraph routes search, compare, detail and out-of-scope intents. Python performs tool execution, hard filtering, scoring, verification and bounded re-planning. LLM perception and response use the shared factory in `src/llm.py`. Successful recommendation paths normally call LLM twice; missing-input, confirmation and failure paths differ.

## Commands

Run from repository root with the project virtualenv:

```powershell
$env:AGENT_LLM="stub"
$env:AGENT_STUB_LATENCY_MEAN_S="0"
$env:AGENT_STUB_LATENCY_STDDEV_S="0"
.venv\Scripts\python.exe -m unittest discover tests "test_*.py"
.venv\Scripts\python.exe -m unittest tests.test_tools -v
.venv\Scripts\python.exe -m streamlit run app.py
.venv\Scripts\python.exe -m src.agent
.venv\Scripts\python.exe scripts/run_autoeval.py --eval-set tests/eval_set --llm stub --tier pipeline
```

Tests use stdlib unittest. Live tests require explicit `RUN_LIVE_TESTS=1`, API key and a real LLM. Stub perception returns fixed JSON and cannot prove NLP accuracy. Reports/logs are generated locally and ignored by Git.

## Module ownership

| Module | Owner |
|---|---|
| `src/perception/`, `src/memory/`, node `perceive` | A |
| `src/reasoning/`, reasoning nodes and response prompt | B |
| `src/tools/`, tracing, tool nodes and response wiring | C |
| Graph, shared LLM factory and entrypoints | C |
| Eval cases and scripts | A/B/C |

Coordinate changes to another module's contract or behavior. Keep behavior-preserving cleanup scoped to the user's request.

## Invariants

- Preserve session isolation; updates replace current constraints, not parallel old/new state.
- Ask for missing required fields; surface conflicts; never silently relax constraints or infer order confirmation.
- Every factual number must trace to tool evidence, supplier ID and source URL. Preserve nulls for unknown values and expose `simulated_fields`.
- Tool args_schema is required evidence. Tools return structured JSON; batch errors affect only their corresponding elements.
- Retry only transient timeout/unavailable failures. Re-plans retain audit history and are bounded.
- Redact secrets before logging; never commit `.env`, local database or private contact data.
- `suppliers.json` and VERSION must match. Generator reads source CSVs and adds explicit EDGE fixtures; archived JSON is outside runtime.
- Keep technical docs, source data, tests and final report. Avoid committing prompts, handoffs, local tool configuration or generated demo/eval artifacts.
