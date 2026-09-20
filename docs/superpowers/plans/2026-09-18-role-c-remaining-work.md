# Việc còn lại của C (Data, Tools, Graph, Evaluation) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Làm xong phần việc của Người C trong `PHAN-CONG-CON-LAI-2026-09-17.md` §5 (routing sau replan, pipeline dữ liệu thật, dataset version, AutoEval, load test), và sửa các bug trong module của C tìm được khi đọc lại codebase ngày 2026-09-18.

**Architecture:** Chỉ sửa file thuộc C: `src/graph.py`, `src/nodes/tools.py`, `src/nodes/respond.py`, `src/tools/`, `src/logging_utils/`, `src/eval/`, `src/llm.py`, `scripts/`, `generate_mock_data.py`, `tests/eval_set/cases_c.jsonl`. Node của A (`perceive`) được **bọc** trong graph chứ không sửa. Việc cần A/B làm được ghi vào file handoff ở Task 15. Dữ liệu thật đi theo luồng `src/tools/mock_data/sources/*.csv` (người thu, schema §6 của file phân công) → `src/tools/dataset_builder.py` (validate + chuẩn hóa) → `suppliers.json` + `VERSION`.

**Tech Stack:** Python 3.14, LangGraph 1.2.11, stdlib `unittest`, `requests` (chỉ dùng cho script crawl), SQLite (API của A trong `src/memory/db.py`).

**Thay thế:** Task 10 của `docs/superpowers/plans/2026-09-14-role-c-implementation.md` (một file `sources.csv` và xóa `COMPANIES`) được thay bằng Task 6–10 ở plan này. Plan cũ chưa được thực thi phần đó.

## Global Constraints

- Test dùng stdlib `unittest`, **không** dùng pytest. Luôn chạy từ repo root sau khi `.venv\Scripts\activate`: `python -m unittest tests.<module> -v`. Chạy cả bộ: `python -m unittest discover tests "test_*.py"`.
- Không đổi tên field hay action nào trong `interface-contracts.md`. Chỉ được **thêm** field và phải ghi vào contract (Task 15).
- Không sửa `src/perception/`, `src/memory/`, `src/nodes/perceive.py` (A) hay `src/reasoning/`, `src/nodes/reasoning.py` (B). Được **gọi** API công khai của họ.
- Timestamp ISO 8601. Tiền VND là số thuần, không có "đ" hay dấu phân cách.
- Không hard-code input mẫu vào logic. Eval case là dữ liệu JSONL.
- Không bao giờ ghi API key hay secret ra log. Mọi payload log phải đi qua `redact()`.
- Không bịa số liệu: trường không có nguồn thì để `null`, hoặc (chỉ với MOQ/TonKho/ThoiGianGiao/ChietKhauTheoSoLuong) mô phỏng **và** ghi tên trường vào `simulated_fields`.
- Comment trong code viết tiếng Việt không dấu, theo style đang có trong repo.
- Mọi commit do agent tạo kết thúc bằng dòng `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- Test không được ghi vào `src/memory/state.db` thật: patch `src.graph.save_session`, `src.graph.append_conversation`, `src.graph.save_decision` khi gọi `run_request` với request có `session_id`.

## File Structure

| File | Trách nhiệm | Task |
|---|---|---|
| `src/graph.py` | bọc `perceive`, route sau replan, lưu decision | 1, 2, 3 |
| `src/nodes/tools.py` | `confirm_gate` chỉ chốt ở lượt sau; `tool_detail` đọc `supplier_id` | 3, 5 |
| `src/logging_utils/tracer.py` | `redact()` đệ quy + che chuỗi giống key | 4 |
| `src/tools/supplier_tools.py` | `compare_price` chịu được `Gia`/`MOQ` null | 5 |
| `src/nodes/respond.py` | đưa `TenSanPham` vào bằng chứng | 5 |
| `src/tools/dataset_builder.py` (mới) | schema nguồn, validate, chuẩn hóa, VERSION, phân bố | 6 |
| `generate_mock_data.py` | ghép legacy + edge + nguồn thật, ghi VERSION | 7 |
| `src/tools/mock_data/sources/` (mới) | CSV theo nhóm sản phẩm + README | 7, 9, 10 |
| `scripts/crawl_sources_draft.py` | xuất draft theo schema mới, sửa `classify` | 8 |
| `src/llm.py`, `scripts/run_loadtest.py` | độ trễ stub chỉnh qua env, báo cáo `.md` | 11 |
| `src/eval/scoring.py`, `scripts/run_autoeval.py` | `must_ask_user`, `must_not_invent_numbers`, variance | 12 |
| `tests/eval_set/cases_c.jsonl` | case C11–C17 | 13 |
| `reports/` | kết quả AutoEval và load test thật | 14 |
| `interface-contracts.md`, `CLAUDE.md`, `HANDOFF-C-2026-09-18.md` | tài liệu và bàn giao | 15 |

---

### Task 1: Bọc `perceive` — truyền `session_id` và hỏi lại khi thiếu thông tin

**Bug đang sửa:** (1) `perceive` không trả `session_id` về state nên `final["session_id"] == ""`. Kiểm chứng bằng stub: `req.session_id=sess_2277f861` nhưng `session_id=''`. Hậu quả: `run_request` không lưu DB, REPL và AutoEval không bao giờ có lượt 2. (2) `MissingFieldError`/`InvalidProductTypeError` bị `run_request` gộp thành `graceful_fail` với câu "He thong gap loi..." thay vì hỏi lại người dùng.

**Files:**
- Modify: `src/graph.py` (import, `route_intent`, thêm `guard_perceive`, vòng `add_node`, conditional edge của `perceive`)
- Test: `tests/test_graph_perceive_guard.py` (mới)

**Interfaces:**
- Consumes: `MissingFieldError`, `InvalidProductTypeError` từ `src.perception.parser`
- Produces: `guard_perceive(func) -> Callable[[AgentState], dict]`. Sau node `perceive`, `state["session_id"]` luôn bằng `req["session_id"]` nếu state chưa có. Khi thông tin thiếu hoặc sai thì `state["status"] == "needs_input"` và `answer` nêu rõ phần thiếu. `route_intent` trả `"graceful_fail"` khi `status == "needs_input"`.

- [ ] **Step 1: Cài lại môi trường, chốt baseline**

Run: `pip install -r requirements.txt` rồi `python -m unittest discover tests "test_*.py"`
Expected: `Ran 247 tests` và `OK`. Trước khi cài, 2 test OpenRouter lỗi `No module named 'langchain_openai'`. Nếu vẫn còn lỗi khác thì dừng lại và báo, không làm tiếp.

- [ ] **Step 2: Viết test thất bại**

Tạo `tests/test_graph_perceive_guard.py`:

```python
import json
import os
import unittest
from unittest.mock import patch

from src.graph import route_intent, run_request
from src.graph_state import new_state
from src.perception.parser import InvalidProductTypeError, MissingFieldError


def raising(exc):
    def node(state):
        raise exc
    return node


def fake_perceive_with_session(state):
    req = {
        "session_id": "sess_fake01",
        "conversation_history": [{"role": "user", "content": "x"}],
        "hard_constraints": {},
    }
    return {"intent": "out_of_scope", "req": req, "llm_calls": 1}


class PerceiveGuardTests(unittest.TestCase):
    def test_missing_field_becomes_needs_input_naming_the_fields(self) -> None:
        final = run_request("Toi muon mua ban lam viec", overrides={
            "perceive": raising(MissingFieldError(["số lượng", "ngân sách tối đa"])),
        })
        self.assertEqual(final["status"], "needs_input")
        self.assertIn("số lượng", final["answer"])
        self.assertIn("ngân sách tối đa", final["answer"])
        self.assertEqual(final["tool_results"], [])
        self.assertEqual(final["llm_calls"], 1)
        self.assertNotIn("error", final)

    def test_unknown_product_type_becomes_needs_input(self) -> None:
        final = run_request("Can 10 may lanh", overrides={
            "perceive": raising(InvalidProductTypeError("máy lạnh")),
        })
        self.assertEqual(final["status"], "needs_input")
        self.assertIn("máy lạnh", final["answer"])

    def test_invalid_number_becomes_needs_input(self) -> None:
        final = run_request("Can 0 ghe", overrides={
            "perceive": raising(ValueError("quantity phải > 0, nhận được: 0")),
        })
        self.assertEqual(final["status"], "needs_input")
        self.assertIn("quantity", final["answer"])

    def test_broken_llm_json_is_a_system_failure_not_a_question(self) -> None:
        final = run_request("x", overrides={
            "perceive": raising(json.JSONDecodeError("Expecting value", "", 0)),
        })
        self.assertEqual(final["status"], "graceful_fail")
        self.assertIn("JSONDecodeError", final["error"])

    def test_route_intent_sends_needs_input_to_graceful_fail(self) -> None:
        state = {**new_state("x"), "intent": "search_new", "status": "needs_input"}
        self.assertEqual(route_intent(state), "graceful_fail")


class SessionPropagationTests(unittest.TestCase):
    def test_session_id_created_by_perception_reaches_the_final_state(self) -> None:
        with patch("src.graph.save_session") as save, patch("src.graph.append_conversation"):
            final = run_request("x", overrides={"perceive": fake_perceive_with_session})
        self.assertEqual(final["session_id"], "sess_fake01")
        save.assert_called_once()
        self.assertEqual(save.call_args.args[0], "sess_fake01")

    def test_a_given_session_id_is_not_overwritten(self) -> None:
        with patch("src.graph.save_session"), patch("src.graph.append_conversation"), \
                patch("src.graph.session_exists", return_value=False):
            final = run_request("x", session_id="sess_given",
                                overrides={"perceive": fake_perceive_with_session})
        self.assertEqual(final["session_id"], "sess_given")


class RealPerceiveMultiTurnTests(unittest.TestCase):
    """Parser that + StubLLM (khong goi mang), DB thay bang dict trong bo nho."""

    def test_second_turn_reuses_the_session_and_appends_history(self) -> None:
        store: dict = {}
        with patch.dict(os.environ, {"AGENT_LLM": "stub"}), \
                patch("src.llm.STUB_LATENCY_MEAN_S", 0.0), \
                patch("src.llm.STUB_LATENCY_STDDEV_S", 0.0), \
                patch("src.graph.session_exists", side_effect=lambda sid: sid in store), \
                patch("src.graph.load_session", side_effect=lambda sid: store.get(sid)), \
                patch("src.graph.save_session",
                      side_effect=lambda sid, req: store.__setitem__(sid, req)), \
                patch("src.graph.append_conversation"):
            first = run_request("Can 50 ghe van phong, ngan sach 200 trieu, giao trong 14 ngay")
            second = run_request("Tang ngan sach len 250 trieu", session_id=first["session_id"])
        self.assertTrue(first["session_id"])
        self.assertEqual(second["session_id"], first["session_id"])
        self.assertEqual(len(second["req"]["conversation_history"]), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Chạy test để xác nhận fail**

Run: `python -m unittest tests.test_graph_perceive_guard -v`
Expected: FAIL/ERROR. Ba test `needs_input` nhận `graceful_fail`, `route_intent` trả `plan`, `session_id` là `''`, và `assertTrue(first["session_id"])` fail.

- [ ] **Step 4: Sửa `src/graph.py`**

Thêm vào khối import (sau `import time`):

```python
import json
```

và sau dòng `from src.nodes.perceive import perceive`:

```python
from src.perception.parser import InvalidProductTypeError, MissingFieldError
```

Thay hàm `route_intent`:

```python
def route_intent(state: AgentState) -> str:
    """Intent la gi cung phai ra mot node hop le. Intent la -> neu gioi han.

    Perception bao thieu/sai thong tin (status=needs_input) -> dung lai hoi
    nguoi dung, khong goi tool nao.
    """
    if state.get("status") == "needs_input":
        return "graceful_fail"
    return _INTENT_ENTRY.get(state.get("intent"), "respond_limits")
```

Thêm ngay sau `route_intent`:

```python
def guard_perceive(func):
    """Boc node perceive cua A ma khong sua file cua A.

    1. Loi do NGUOI DUNG (thieu field, san pham ngoai catalog, so <= 0) -> hoi
       lai (status=needs_input), khong bien thanh loi he thong. SYSTEM-RULES
       muc 3: khong tu dien thong tin con thieu.
    2. Chep req["session_id"] (parser tu sinh o luot dau) len state, de
       run_request luu dung phien va tra session_id cho luot sau.
    JSONDecodeError (LLM tra JSON hong) la loi he thong -> nem tiep cho
    run_request bien thanh graceful_fail.
    """
    def node(state: AgentState) -> dict:
        try:
            out = dict(func(state) or {})
        except (MissingFieldError, InvalidProductTypeError) as exc:
            return {"status": "needs_input", "answer": str(exc), "llm_calls": 1}
        except json.JSONDecodeError:
            raise
        except ValueError as exc:
            return {"status": "needs_input",
                    "answer": f"Thong tin chua hop le: {exc}. Vui long nhap lai.",
                    "llm_calls": 1}
        req = out.get("req") or {}
        if not state.get("session_id") and req.get("session_id"):
            out["session_id"] = req["session_id"]
        return out
    return node
```

Trong `build_graph`, thay vòng `add_node`:

```python
    for name, func in nodes.items():
        graph.add_node(name, guard_perceive(func) if name == "perceive" else func)
```

và thay conditional edge của `perceive`:

```python
    graph.add_conditional_edges("perceive", route_intent, {
        "plan": "plan",
        "tool_compare": "tool_compare",
        "tool_detail": "tool_detail",
        "respond_limits": "respond_limits",
        "graceful_fail": "graceful_fail",
    })
```

- [ ] **Step 5: Chạy test để xác nhận pass**

Run: `python -m unittest tests.test_graph_perceive_guard tests.test_graph_routing tests.test_graph_e2e_stub -v`
Expected: tất cả PASS.

- [ ] **Step 6: Chạy cả bộ**

Run: `python -m unittest discover tests "test_*.py"`
Expected: `OK`, 255 test (247 + 8).

- [ ] **Step 7: Commit**

```bash
git add src/graph.py tests/test_graph_perceive_guard.py
git commit -m "fix(graph): propagate session_id and ask back on missing input" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Route sau `replan` về đúng tool của intent

**Bug đang sửa:** `graph.add_edge("replan", "tool_search")` đưa mọi intent về `tool_search`. Với `compare_specific`/`supplier_detail`, `state["plan"]` rỗng nên node `replan` của B trả `needs_input`. Sau đó `tool_search` ghi đè câu trả lời thành "Ke hoach thuc thi khong co buoc tim nha cung cap".

**Files:**
- Modify: `src/graph.py` (thêm `_REPLAN_ENTRY`, `route_after_replan`, thay edge `replan`)
- Test: `tests/test_graph_routing.py` (thêm class), `tests/test_graph_replan_routing.py` (mới)

**Interfaces:**
- Produces: `route_after_replan(state) -> "tool_search" | "tool_compare" | "tool_detail" | "graceful_fail"`

- [ ] **Step 1: Viết unit test thất bại**

Thêm vào `tests/test_graph_routing.py`: sửa dòng import đầu file thành

```python
from src.graph import route_after_filter, route_after_replan, route_after_verify, route_intent
```

và thêm class trước `if __name__ == "__main__":`

```python
class RouteAfterReplanTests(unittest.TestCase):
    def test_each_intent_returns_to_its_own_tool_node(self) -> None:
        cases = {
            "search_new": "tool_search",
            "compare_specific": "tool_compare",
            "supplier_detail": "tool_detail",
        }
        for intent, expected in cases.items():
            with self.subTest(intent=intent):
                self.assertEqual(route_after_replan(state_with(intent=intent)), expected)

    def test_out_of_scope_or_unknown_intent_never_calls_a_tool(self) -> None:
        for intent in ("out_of_scope", "dat_ve_may_bay", None):
            with self.subTest(intent=intent):
                self.assertEqual(route_after_replan(state_with(intent=intent)), "graceful_fail")

    def test_a_replan_that_needs_user_input_stops(self) -> None:
        state = state_with(intent="compare_specific", status="needs_input")
        self.assertEqual(route_after_replan(state), "graceful_fail")
```

- [ ] **Step 2: Viết test e2e thất bại**

Tạo `tests/test_graph_replan_routing.py`:

```python
import unittest
from unittest.mock import patch

from src.graph import run_request


def fake_perceive(intent):
    def node(state):
        return {"intent": intent, "req": {}, "llm_calls": 1}
    return node


def fake_respond(state):
    return {"answer": "cau tra loi", "status": "success", "llm_calls": 1}


def fake_replan(state):
    count = state.get("replan_count", 0) + 1
    return {"plan": {"plan_id": f"plan_fake_{count}", "replan_count": count, "steps": []},
            "replan_count": count}


# Test WIRING: node noi dung cua B thay bang ham toi thieu.
BASE = {
    "plan": lambda s: {"plan": {"plan_id": "p0", "replan_count": 0, "steps": []}},
    "filter_hard": lambda s: {"candidates": list(s.get("candidates") or []), "rejected": []},
    "score_rank": lambda s: {"ranked": list(s.get("candidates") or [])},
    "verify_output": lambda s: {"verdict": {"passed": True, "violations": [], "claims": []}},
    "diagnose": lambda s: {"replan_reason": "wiring_test"},
    "replan": fake_replan,
    "respond": fake_respond,
    "confirm_gate": lambda s: {},
}


class ReplanReturnsToTheIntentToolTests(unittest.TestCase):
    def _run(self, intent):
        calls = {"tool_search": 0, "tool_compare": 0, "tool_detail": 0}

        def make(name):
            def node(state):
                calls[name] += 1
                # Lan dau rong -> ep di diagnose/replan; lan sau co ung vien
                candidates = [] if calls[name] == 1 else [{"MaNCC": "NCC001"}]
                return {"candidates": candidates, "tool_results": []}
            return node

        overrides = {**BASE, "perceive": fake_perceive(intent),
                     **{name: make(name) for name in calls}}
        final = run_request("x", overrides=overrides)
        return final, calls

    def test_compare_specific_replans_back_into_tool_compare(self) -> None:
        final, calls = self._run("compare_specific")
        self.assertEqual(calls, {"tool_search": 0, "tool_compare": 2, "tool_detail": 0})
        self.assertEqual(final["status"], "success")

    def test_supplier_detail_replans_back_into_tool_detail(self) -> None:
        final, calls = self._run("supplier_detail")
        self.assertEqual(calls, {"tool_search": 0, "tool_compare": 0, "tool_detail": 2})
        self.assertEqual(final["status"], "success")

    def test_search_new_still_replans_into_tool_search(self) -> None:
        final, calls = self._run("search_new")
        self.assertEqual(calls, {"tool_search": 2, "tool_compare": 0, "tool_detail": 0})
        self.assertEqual(final["status"], "success")


class RealNodesCompareTests(unittest.TestCase):
    """Node that cua B va C, chi thay perceive/respond. Ma NCC khong ton tai."""

    def test_compare_with_unknown_ids_never_falls_into_search(self) -> None:
        def perceive(state):
            return {"intent": "compare_specific", "llm_calls": 1, "req": {
                "session_id": "sess_cmp", "intent": "compare_specific",
                "supplier_ids": ["NCC998", "NCC999"],
                "target_supplier_ids": ["NCC998", "NCC999"],
                "hard_constraints": {"product_type": None, "quantity": 20,
                                     "budget_max": None, "delivery_deadline_days": None},
                "soft_constraints": {},
                "conversation_history": [{"role": "user", "content": "x"}],
            }}

        with patch("src.graph.save_session"), patch("src.graph.append_conversation"):
            final = run_request("So sanh NCC998 va NCC999",
                                overrides={"perceive": perceive, "respond": fake_respond})
        tools = [entry["tool"] for entry in final["tool_results"]]
        self.assertNotIn("search_suppliers", tools)
        self.assertIn(final["status"], {"graceful_fail", "needs_input"})
        self.assertNotIn("khong co buoc tim nha cung cap", final["answer"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Chạy test để xác nhận fail**

Run: `python -m unittest tests.test_graph_routing tests.test_graph_replan_routing -v`
Expected: `ImportError: cannot import name 'route_after_replan'` ở file đầu. File sau có 2 test compare/detail fail vì `tool_search` bị gọi, và test real-node fail vì answer chứa "khong co buoc tim nha cung cap".

- [ ] **Step 4: Sửa `src/graph.py`**

Thêm sau `_INTENT_ENTRY`:

```python
# Sau replan phai quay lai DUNG node tool cua intent (PHAN-CONG-CON-LAI muc 5.1).
# Intent khong co trong bang (out_of_scope, intent la) -> khong goi tool nao.
_REPLAN_ENTRY = {
    "search_new": "tool_search",
    "compare_specific": "tool_compare",
    "supplier_detail": "tool_detail",
}
```

Thêm sau `route_after_verify`:

```python
def route_after_replan(state: AgentState) -> str:
    if state.get("status") == "needs_input":
        # replan khong lap duoc ke hoach moi -> can nguoi dung, khong goi tool lai
        return "graceful_fail"
    return _REPLAN_ENTRY.get(state.get("intent"), "graceful_fail")
```

Trong `build_graph`, thay `graph.add_edge("replan", "tool_search")` bằng:

```python
    graph.add_conditional_edges("replan", route_after_replan, {
        "tool_search": "tool_search",
        "tool_compare": "tool_compare",
        "tool_detail": "tool_detail",
        "graceful_fail": "graceful_fail",
    })
```

- [ ] **Step 5: Chạy test để xác nhận pass**

Run: `python -m unittest tests.test_graph_routing tests.test_graph_replan_routing tests.test_graph_e2e_stub -v`
Expected: tất cả PASS.

- [ ] **Step 6: Chạy cả bộ và commit**

Run: `python -m unittest discover tests "test_*.py"` → `OK`.

```bash
git add src/graph.py tests/test_graph_routing.py tests/test_graph_replan_routing.py
git commit -m "fix(graph): route replan back to the intent's own tool node" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

Ghi chú: sau task này, compare/detail có mã không tồn tại sẽ kết thúc bằng câu của B "Không thể lập lại kế hoạch: missing hard constraints...". Câu này vẫn chưa đúng ngữ cảnh; phần sửa thuộc node `replan` của B, đã ghi ở Task 15.

---

### Task 3: `confirm_gate` chỉ chốt ở lượt sau và ghi `decisions_made`

**Bug đang sửa:** (1) "Cần 50 ghế... chốt luôn" ở lượt đầu được chốt ngay, khi người dùng chưa thấy đề xuất nào. (2) Nhánh `supplier_detail` hỏi "có muốn chốt đơn... số lượng None?". (3) Không nơi nào gọi `save_decision`, nên `decisions_made` luôn rỗng.

**Files:**
- Modify: `src/nodes/tools.py` (hàm `confirm_gate`, thêm `_has_previous_turn`, `_FIRST_TURN_NOTE`)
- Modify: `src/graph.py` (import `save_decision`, thêm `_confirmed_orders`, `_with_decisions`, sửa khối lưu DB cuối `run_request`)
- Test: `tests/test_node_confirm_gate.py` (sửa helper, thêm test), `tests/test_graph_decisions.py` (mới)

**Interfaces:**
- Consumes: `save_decision(session_id: str, supplier_id: str) -> None` từ `src.memory.db`. `session_id` trên state do Task 1 đảm bảo.
- Produces: `confirm_gate` chỉ gọi `confirm_order` khi `len(req["conversation_history"]) >= 2` và câu của lượt hiện tại là xác nhận tường minh. `run_request` thêm `{"supplier_id", "confirmed_at"}` vào `req["decisions_made"]` và gọi `save_decision` cho mỗi đơn đã chốt.

- [ ] **Step 1: Sửa helper và thêm test cho node**

Trong `tests/test_node_confirm_gate.py`, thay hàm `state_with`:

```python
def state_with(user_input, ranked=True, turns=2, intent=None, quantity=20):
    history = [{"role": "user", "content": f"luot {i}"} for i in range(turns)]
    state = {
        **new_state(user_input),
        "req": {"hard_constraints": {"quantity": quantity}, "conversation_history": history},
        "ranked": [{"MaNCC": "T001", "TenNCC": "NCC Mot", "total_price": 20_000_000}] if ranked else [],
        "answer": "Toi de xuat NCC Mot.",
        "status": "success",
    }
    if intent:
        state["intent"] = intent
    return state
```

Thêm class trước `if __name__ == "__main__":`

```python
class GateTimingTests(unittest.TestCase):
    def test_confirm_words_on_the_first_turn_do_not_execute(self) -> None:
        with patch_data():
            out = confirm_gate(state_with("Can 20 ghe, chot don luon", turns=1))
        self.assertEqual(out["status"], "needs_confirmation")
        self.assertEqual(out.get("tool_results", []), [])
        self.assertIn("chua xem de xuat", out["answer"])

    def test_supplier_detail_never_asks_to_place_an_order(self) -> None:
        out = confirm_gate(state_with("Cho xem NCC T001", intent="supplier_detail",
                                      quantity=None))
        self.assertIsNone(out["pending_confirmation"])
        self.assertEqual(out["status"], "success")

    def test_unknown_quantity_means_nothing_to_confirm(self) -> None:
        out = confirm_gate(state_with("ok chot don di", quantity=None))
        self.assertIsNone(out["pending_confirmation"])
        self.assertEqual(out.get("tool_results", []), [])
```

- [ ] **Step 2: Viết test thất bại cho phần lưu decision**

Tạo `tests/test_graph_decisions.py`:

```python
import unittest
from unittest.mock import patch

from src.graph import run_request

HISTORY_2 = [{"role": "user", "content": "Can 20 ghe"},
             {"role": "user", "content": "ok chot don di"}]


def fake_perceive(state):
    return {"intent": "search_new", "llm_calls": 1, "req": {
        "session_id": "sess_dec", "intent": "search_new",
        "hard_constraints": {"product_type": "ghế văn phòng", "quantity": 20,
                             "budget_max": 100_000_000, "delivery_deadline_days": 14},
        "soft_constraints": {}, "conversation_history": HISTORY_2, "decisions_made": [],
    }}


OVERRIDES = {
    "perceive": fake_perceive,
    "plan": lambda s: {"plan": {"plan_id": "p", "replan_count": 0, "steps": []}},
    "tool_search": lambda s: {"tool_results": [], "candidates": [
        {"MaNCC": "NCC001", "TenNCC": "Noi That Hoa Phat", "total_price": 1}]},
    "filter_hard": lambda s: {"candidates": list(s.get("candidates") or []), "rejected": []},
    "score_rank": lambda s: {"ranked": list(s.get("candidates") or [])},
    "verify_output": lambda s: {"verdict": {"passed": True, "violations": [], "claims": []}},
    "respond": lambda s: {"answer": "De xuat NCC001.", "status": "success", "llm_calls": 1},
}


class DecisionPersistenceTests(unittest.TestCase):
    def test_a_confirmed_order_is_written_to_decisions(self) -> None:
        with patch("src.graph.save_session") as save, \
                patch("src.graph.save_decision") as decide, \
                patch("src.graph.append_conversation"):
            final = run_request("ok chot don di", overrides=OVERRIDES)
        self.assertEqual(final["status"], "success")
        decide.assert_called_once_with("sess_dec", "NCC001")
        saved_req = save.call_args.args[1]
        self.assertEqual([d["supplier_id"] for d in saved_req["decisions_made"]], ["NCC001"])
        self.assertTrue(saved_req["decisions_made"][0]["confirmed_at"])

    def test_no_confirmation_writes_no_decision(self) -> None:
        with patch("src.graph.save_session"), \
                patch("src.graph.save_decision") as decide, \
                patch("src.graph.append_conversation"):
            final = run_request("Can 20 ghe van phong", overrides=OVERRIDES)
        self.assertEqual(final["status"], "needs_confirmation")
        decide.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Chạy test để xác nhận fail**

Run: `python -m unittest tests.test_node_confirm_gate tests.test_graph_decisions -v`
Expected: 3 test `GateTimingTests` FAIL. `test_graph_decisions` ERROR vì `src.graph` chưa có `save_decision` để patch.

- [ ] **Step 4: Sửa `confirm_gate` trong `src/nodes/tools.py`**

Thêm sau `_REFUSAL_WORDS`:

```python
_FIRST_TURN_NOTE = (
    "Ban chua xem de xuat nao o luot truoc, nen toi chua chot don o luot nay. "
)


def _has_previous_turn(state: AgentState) -> bool:
    """Chi chot khi nguoi dung da thay de xuat o 1 luot truoc.

    conversation_history cua A chi chua luot user: >= 2 nghia la day la luot
    thu hai tro di cua phien.
    """
    history = (state.get("req") or {}).get("conversation_history") or []
    return len(history) >= 2
```

Thay toàn bộ phần đầu của `confirm_gate` (từ dòng docstring đến hết khối `if not _is_confirmed(...)`) bằng:

```python
def confirm_gate(state: AgentState) -> dict:
    """Chan buoc chot don lai, cho den khi nguoi dung xac nhan tuong minh.

    Chi thuc thi khi (1) cau cua CHINH luot nay la xac nhan va (2) nguoi dung
    da thay de xuat o luot truoc. Xac nhan ngay luot dau khong duoc tinh:
    nguoi dung chua biet se chot voi ai (SYSTEM-RULES.md muc 3).
    """
    ranked = state.get("ranked") or []
    quantity = ((state.get("req") or {}).get("hard_constraints") or {}).get("quantity")
    if not ranked or state.get("intent") == "supplier_detail" or not quantity:
        # Khong co gi de chot: hoi chi tiet 1 NCC, hoac chua biet so luong
        return {"pending_confirmation": None, "status": state.get("status") or "success"}

    top = ranked[0]
    supplier_id = top.get("MaNCC")
    confirmed_now = _is_confirmed(state.get("user_input", ""))
    earlier_turn = _has_previous_turn(state)

    if not (confirmed_now and earlier_turn) or not supplier_id:
        note = _FIRST_TURN_NOTE if confirmed_now and not earlier_turn else ""
        return {
            "pending_confirmation": {
                "supplier_id": supplier_id,
                "supplier_name": top.get("TenNCC"),
                "quantity": quantity,
                "total_price": top.get("total_price"),
            },
            "status": "needs_confirmation",
            "answer": (
                f"{state.get('answer', '')}\n\n"
                f"{note}Ban co muon chot don voi {top.get('TenNCC')} ({supplier_id}), "
                f"so luong {quantity}? Toi chi thuc hien khi ban xac nhan ro rang "
                f"(vi du: 'chot don di')."
            ).strip(),
        }
```

Phần còn lại (từ `started = time.perf_counter()` đến hết hàm) giữ nguyên.

- [ ] **Step 5: Sửa `run_request` trong `src/graph.py`**

Thêm `save_decision` vào import từ `src.memory.db`:

```python
from src.memory.db import (
    append_conversation,
    init_db,
    load_session,
    save_decision,
    save_session,
    session_exists,
)
```

Thêm hai hàm trước `run_request`:

```python
def _confirmed_orders(final: dict) -> list[dict]:
    """Ket qua confirm_order da thuc thi thanh cong trong request nay."""
    return [
        entry["result"] for entry in final.get("tool_results") or []
        if entry.get("tool") == "confirm_order" and entry.get("status") == "ok"
        and isinstance(entry.get("result"), dict) and entry["result"].get("order_confirmed")
    ]


def _with_decisions(req: dict | None, final: dict) -> dict | None:
    """Them don vua chot vao req["decisions_made"] (schema cua A, muc 1 contract)."""
    orders = _confirmed_orders(final)
    if not req or not orders:
        return req
    decisions = list(req.get("decisions_made") or [])
    decisions.extend({"supplier_id": order["supplier_id"],
                      "confirmed_at": order["confirmed_at"]} for order in orders)
    return {**req, "decisions_made": decisions}
```

Thay khối lưu DB ở cuối `run_request` (từ `sid = final.get("session_id")...` đến trước `return final`):

```python
    sid = final.get("session_id") or session_id or ""
    if sid:
        try:
            req_to_save = _with_decisions(final.get("req"), final)
            if req_to_save:
                final["req"] = req_to_save
                save_session(sid, req_to_save)
            for order in _confirmed_orders(final):
                save_decision(sid, order["supplier_id"])
            agent_answer = final.get("answer", "")
            if agent_answer:
                append_conversation(sid, "agent", agent_answer)
        except Exception:  # noqa: BLE001
            pass  # DB loi khong duoc lam gay response tra ve nguoi dung
```

- [ ] **Step 6: Chạy test để xác nhận pass**

Run: `python -m unittest tests.test_node_confirm_gate tests.test_graph_decisions -v`
Expected: tất cả PASS.

- [ ] **Step 7: Chạy cả bộ và commit**

Run: `python -m unittest discover tests "test_*.py"` → `OK`.

```bash
git add src/nodes/tools.py src/graph.py tests/test_node_confirm_gate.py tests/test_graph_decisions.py
git commit -m "fix(confirm): only confirm on a later turn; persist decisions" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: `redact()` đệ quy và che chuỗi giống API key

**Lý do:** `redact()` hiện chỉ che key cấp một. Nếu `params` lồng nhau có `api_key`, key sẽ lọt vào log, và rubric chấm 0 điểm khi lộ secret. Tương tự nếu người dùng dán key vào câu hỏi (`user_input` được log ở `request_start`).

**Files:**
- Modify: `src/logging_utils/tracer.py` (`SENSITIVE_KEYS`, `redact`)
- Test: `tests/test_tracer_redact.py` (mới)

**Interfaces:**
- Produces: `redact(payload: dict) -> dict`. Cùng chữ ký, không mutate input, đệ quy qua dict/list, thay chuỗi dạng key bằng `***`.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_tracer_redact.py`:

```python
import unittest

from src.logging_utils.tracer import redact

FAKE_GOOGLE_KEY = "AIza" + "x" * 35
FAKE_OPENROUTER_KEY = "sk-or-v1-" + "a" * 40


class RedactTests(unittest.TestCase):
    def test_top_level_secret_is_masked(self) -> None:
        self.assertEqual(redact({"api_key": "abc", "q": 1}), {"api_key": "***", "q": 1})

    def test_nested_dicts_and_lists_are_masked(self) -> None:
        payload = {"params": {"headers": {"Authorization": "Bearer x"}},
                   "items": [{"openrouter_api_key": "y"}, {"ok": 2}]}
        out = redact(payload)
        self.assertEqual(out["params"]["headers"]["Authorization"], "***")
        self.assertEqual(out["items"][0]["openrouter_api_key"], "***")
        self.assertEqual(out["items"][1], {"ok": 2})

    def test_key_shaped_strings_inside_free_text_are_masked(self) -> None:
        out = redact({"user_input": f"key cua toi la {FAKE_GOOGLE_KEY} nhe",
                      "note": FAKE_OPENROUTER_KEY})
        self.assertNotIn(FAKE_GOOGLE_KEY, out["user_input"])
        self.assertIn("***", out["user_input"])
        self.assertEqual(out["note"], "***")

    def test_input_is_not_mutated(self) -> None:
        payload = {"params": {"api_key": "abc"}}
        redact(payload)
        self.assertEqual(payload["params"]["api_key"], "abc")

    def test_ordinary_values_pass_through(self) -> None:
        payload = {"MaNCC": "NCC001", "Gia": 1_677_150, "tags": ["a", "b"]}
        self.assertEqual(redact(payload), payload)

    def test_product_url_slugs_are_not_mistaken_for_keys(self) -> None:
        url = "https://vi.du/san-pham/task-ban-lam-viec-go-tu-nhien-cao-cap-1m2"
        self.assertEqual(redact({"nguon_url": url}), {"nguon_url": url})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `python -m unittest tests.test_tracer_redact -v`
Expected: 2 test nested/free-text FAIL.

- [ ] **Step 3: Sửa `src/logging_utils/tracer.py`**

Thêm `import re` vào khối import. Thay `SENSITIVE_KEYS` và `redact`:

```python
SENSITIVE_KEYS = {
    "api_key", "google_api_key", "anthropic_api_key", "openrouter_api_key",
    "password", "token", "access_token", "refresh_token", "secret",
    "authorization", "x-api-key", "api-key",
}

# Chuoi co hinh dang API key (Google, OpenRouter/OpenAI, Anthropic) - che ca khi
# nam giua van ban tu do, vd nguoi dung dan key vao cau hoi.
# Chan chu/so dung truoc: slug URL nhu ".../task-ban-lam-viec-go-..." khong duoc bi che.
_SECRET_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:AIza[0-9A-Za-z_\-]{30,}|sk-(?:or-|ant-)?[0-9A-Za-z_\-]{20,})"
)
```

```python
def _redact_value(value):
    if isinstance(value, dict):
        return {
            key: ("***" if isinstance(key, str) and key.lower() in SENSITIVE_KEYS
                  else _redact_value(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return _SECRET_PATTERN.sub("***", value)
    return value


def redact(payload: dict) -> dict:
    """Ban sao da che secret: key nhay cam o moi cap long nhau va chuoi co
    hinh dang API key. Khong sua payload goc."""
    return _redact_value(payload)
```

- [ ] **Step 4: Chạy test để xác nhận pass**

Run: `python -m unittest tests.test_tracer_redact tests.test_tracer_jsonl tests.test_graph_state -v`
Expected: tất cả PASS.

- [ ] **Step 5: Chạy cả bộ và commit**

Run: `python -m unittest discover tests "test_*.py"` → `OK`.

```bash
git add src/logging_utils/tracer.py tests/test_tracer_redact.py
git commit -m "fix(tracer): redact nested secrets and key-shaped strings" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Tool chịu được dữ liệu thiếu: `Gia`/`MOQ` null, `supplier_id` số ít; bằng chứng có `TenSanPham`

**Lý do:** (1) Dữ liệu thật để `Gia = null` khi trang không công bố giá (ví dụ Xuân Hòa). Hiện `_apply_discount(None, ...)` ném `TypeError` (không phải `KeyError`), làm hỏng **cả** response `compare_price`. Contract yêu cầu chỉ phần tử lỗi được báo lỗi. (2) Với `supplier_detail`, parser của A đặt mã vào `supplier_id` (số ít, đúng contract §1). `perceive` chỉ chép `supplier_ids` sang `target_supplier_ids`, nên `tool_detail` thấy danh sách rỗng và trả "Yeu cau nay can ma nha cung cap" dù người dùng đã nêu mã.

**Files:**
- Modify: `src/tools/supplier_tools.py` (thêm `_is_number`, sửa vòng lặp `compare_price`)
- Modify: `src/nodes/tools.py` (`tool_detail`)
- Modify: `src/nodes/respond.py` (`_format_supplier`)
- Test: `tests/test_compare_price_missing.py` (mới)

**Interfaces:**
- Produces: phần tử `compare_price` của NCC thiếu `Gia`/`MOQ` là `{"MaNCC", "error": True, "error_type": "tool_unavailable", "message": ...}`. Cùng `error_type` như nhánh `KeyError` đang có. Bằng chứng gửi LLM có dòng `san_pham=<TenSanPham>`.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_compare_price_missing.py`:

```python
import unittest
from unittest.mock import patch

from src.graph_state import new_state
from src.nodes.respond import build_evidence_block
from src.tools.supplier_tools import compare_price

BASE = {"TenNCC": "NCC", "LoaiSanPham": "sofa", "ChatLieu": None, "DonViTinh": "bo",
        "TonKho": 10, "ThoiGianGiao": 7, "BaoHanh": None, "ChietKhauTheoSoLuong": [],
        "DiemUyTin": None, "KhuVuc": "TP.HCM", "nguon_url": "https://vi.du",
        "simulated_fields": []}
FAKE_DATA = [
    {**BASE, "MaNCC": "OK1", "Gia": 1_000_000, "MOQ": 1},
    {**BASE, "MaNCC": "NOPRICE", "Gia": None, "MOQ": 1},
    {**BASE, "MaNCC": "NOMOQ", "Gia": 2_000_000, "MOQ": None},
]


class ComparePriceMissingFieldTests(unittest.TestCase):
    def test_null_price_or_moq_errors_only_that_element(self) -> None:
        with patch("src.tools.supplier_tools._load_data", return_value=FAKE_DATA):
            out = compare_price(["OK1", "NOPRICE", "NOMOQ"], quantity=2)
        by_id = {item["MaNCC"]: item for item in out["comparisons"]}
        self.assertEqual(by_id["OK1"]["total_price"], 2_000_000)
        for sid, field in (("NOPRICE", "Gia"), ("NOMOQ", "MOQ")):
            with self.subTest(sid=sid):
                self.assertTrue(by_id[sid]["error"])
                self.assertEqual(by_id[sid]["error_type"], "tool_unavailable")
                self.assertIn(field, by_id[sid]["message"])


class ToolDetailSupplierIdTests(unittest.TestCase):
    def test_singular_supplier_id_from_the_parser_is_used(self) -> None:
        from src.nodes.tools import tool_detail
        state = {**new_state("Cho xem NCC006"),
                 "req": {"supplier_id": "NCC006", "supplier_ids": [], "target_supplier_ids": []}}
        out = tool_detail(state)
        self.assertNotIn("status", out)
        self.assertEqual([c["MaNCC"] for c in out["candidates"]], ["NCC006"])

    def test_no_code_at_all_still_asks_the_user(self) -> None:
        from src.nodes.tools import tool_detail
        out = tool_detail({**new_state("Cho xem chi tiet"), "req": {}})
        self.assertEqual(out["status"], "needs_input")


class EvidenceProductNameTests(unittest.TestCase):
    def test_product_name_is_part_of_the_evidence(self) -> None:
        state = {**new_state("x"), "ranked": [{
            "MaNCC": "SRC001", "TenNCC": "Noi That Linco", "TenSanPham": "Sofa KT62 Cornwall",
            "unit_price": 9_400_000, "total_price": 9_400_000, "nguon_url": "https://vi.du",
        }], "verdict": {}}
        self.assertIn("san_pham=Sofa KT62 Cornwall", build_evidence_block(state))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `python -m unittest tests.test_compare_price_missing -v`
Expected: `TypeError` ở test compare, `test_singular_supplier_id...` FAIL (có `status=needs_input`), `AssertionError` ở test `san_pham`.

- [ ] **Step 3: Sửa `src/tools/supplier_tools.py`**

Thêm sau `_error`:

```python
def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
```

Trong `compare_price`, ngay sau khối `if record is None: ... continue`, thêm:

```python
        # Du lieu that co the de null (khong co gia niem yet) -> loi rieng phan tu
        # nay, khong tu dien so va khong lam fail ca response (muc 3 contract)
        missing = [field for field in ("Gia", "MOQ") if not _is_number(record.get(field))]
        if missing:
            comparisons.append({
                "MaNCC": sid,
                **_error("tool_unavailable",
                         f"NCC '{sid}' chua co du lieu {', '.join(missing)}; "
                         "khong tu dien so lieu"),
            })
            continue
```

- [ ] **Step 3b: Sửa `tool_detail` trong `src/nodes/tools.py`**

Thay dòng đầu thân hàm `supplier_ids = list((state.get("req") or {}).get("target_supplier_ids") or [])` bằng:

```python
    req = state.get("req") or {}
    supplier_ids = list(req.get("target_supplier_ids") or [])
    if not supplier_ids and req.get("supplier_id"):
        # Parser cua A dat MaNCC cua supplier_detail vao supplier_id (so it, contract
        # muc 1), khong phai supplier_ids -> perceive khong chep sang target_supplier_ids
        supplier_ids = [req["supplier_id"]]
```

- [ ] **Step 4: Sửa `_format_supplier` trong `src/nodes/respond.py`**

Thay dòng đầu của chuỗi trả về:

```python
    return (
        f"- {item.get('TenNCC')} (MaNCC={item.get('MaNCC')})\n"
        f"  san_pham={item.get('TenSanPham') or 'khong ghi ten san pham'}\n"
        f"  don_gia_sau_chiet_khau={item.get('unit_price')} VND\n"
```

Các dòng còn lại giữ nguyên.

- [ ] **Step 5: Chạy test để xác nhận pass**

Run: `python -m unittest tests.test_compare_price_missing tests.test_tools tests.test_tools_source_fields tests.test_node_respond tests.test_node_tool_compare_detail -v`
Expected: tất cả PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tools/supplier_tools.py src/nodes/tools.py src/nodes/respond.py tests/test_compare_price_missing.py
git commit -m "fix(tools): null price/MOQ per element; detail reads supplier_id; product name" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: `dataset_builder` — schema nguồn, validate, chuẩn hóa, VERSION

**Quyết định thiết kế (đã chốt khi lập plan):**

- **Schema thu thập** dùng tên tiếng Anh như §6 file phân công. **Schema record** giữ nguyên tên tiếng Việt của contract. Bảng map:

| Cột CSV | Trường record | Ghi chú |
|---|---|---|
| (sinh) | `MaNCC` | `SRC001`, `SRC002`... theo thứ tự file rồi thứ tự dòng |
| `supplier_name` | `TenNCC` | |
| `product_type` | `LoaiSanPham` | 1 trong 5 giá trị catalog |
| `product_name` | `TenSanPham` | **trường mới** (thêm, không đổi tên trường cũ) |
| `price` | `Gia` | để trống → `null`, **không** mô phỏng |
| `unit` | `DonViTinh` | |
| `region` | `KhuVuc` | `Ha Noi` / `TP.HCM` / `Da Nang` |
| `source_url` | `nguon_url` | |
| `collected_at` | `fetched_at` | `YYYY-MM-DD` |
| `collected_by` | `nguoi_thu` | **trường mới** |
| `material` | `ChatLieu` | tùy chọn, trống → `null` |
| `moq`, `stock`, `delivery_days` | `MOQ`, `TonKho`, `ThoiGianGiao` | trống → mô phỏng + ghi `simulated_fields` |
| `warranty_months`, `trust_score` | `BaoHanh`, `DiemUyTin` | trống → `null`, **không** mô phỏng |
| (luôn mô phỏng) | `ChietKhauTheoSoLuong` | luôn nằm trong `simulated_fields` |
| `note` | (không đưa vào record) | ghi chú cho người duyệt |

- Chỉ MOQ/TonKho/ThoiGianGiao được mô phỏng. Lý do: `hard_constraint_violations` của B loại mọi bản ghi thiếu ba trường này, nên để `null` thì không bản ghi thật nào đề xuất được. Giá, bảo hành, uy tín là bằng chứng cốt lõi nên không bịa: scoring của B đã tự chuẩn hóa lại trọng số khi thiếu bảo hành/uy tín, còn thiếu giá thì bị loại với lý do `missing_price_evidence`. Đây là hành vi đúng.
- Số mô phỏng dùng `random.Random(source_url)`: cùng một sản phẩm luôn ra cùng số, và thêm dòng mới không làm xáo số của dòng cũ.
- `nguon_type` của dòng thật là `"trang_san_pham"`.
- VERSION có dạng `<ngày build>+sha256.<12 ký tự> records=<n>`. Hash tính trên nội dung JSON sau khi chuẩn hóa xuống dòng, nên không phụ thuộc CRLF/LF (`core.autocrlf=true` trên máy này).

**Files:**
- Create: `src/tools/dataset_builder.py`
- Test: `tests/test_dataset_builder.py`

**Interfaces:**
- Produces (trong `src.tools.dataset_builder`):
  - `SOURCE_COLUMNS: tuple[str, ...]`, `REQUIRED_COLUMNS`, `VALID_PRODUCT_TYPES`, `VALID_REGIONS`, `SOURCE_NGUON_TYPE = "trang_san_pham"`
  - `class SourceValidationError(ValueError)` có thuộc tính `problems: list[str]`
  - `read_source_rows(paths: Iterable[Path | str]) -> list[dict]` — mỗi dòng có thêm khóa `_origin = "ten_file:so_dong"`
  - `validate_rows(rows: list[dict]) -> None` — raise `SourceValidationError` gom **mọi** lỗi
  - `to_record(row: dict, supplier_id: str) -> dict`
  - `build_source_records(rows: list[dict], prefix: str = "SRC") -> list[dict]`
  - `write_dataset(records: list[dict], data_path, version_path, built_on: str) -> str` — trả chuỗi version
  - `version_matches(data_path, version_path) -> bool`
  - `distribution(records: list[dict]) -> dict` — `{"total": int, "product_type": Counter, "region": Counter}` chỉ đếm bản ghi `nguon_type == SOURCE_NGUON_TYPE`

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_dataset_builder.py`:

```python
import csv
import tempfile
import unittest
from pathlib import Path

from src.tools.dataset_builder import (
    SOURCE_COLUMNS, SOURCE_NGUON_TYPE, SourceValidationError, build_source_records,
    distribution, read_source_rows, to_record, validate_rows, version_matches, write_dataset,
)


def row(**overrides):
    base = {col: "" for col in SOURCE_COLUMNS}
    base.update({
        "supplier_name": "Noi That Linco", "product_type": "sofa",
        "product_name": "Sofa KT62 Cornwall", "price": "9400000", "unit": "bo",
        "region": "TP.HCM", "source_url": "https://www.noithatlinco.com/sofa-kt62",
        "collected_at": "2026-09-17", "collected_by": "C", "_origin": "sofa.csv:2",
    })
    base.update(overrides)
    return base


def write_csv(directory: Path, name: str, rows: list[dict], header=SOURCE_COLUMNS) -> Path:
    path = directory / name
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(header))
        writer.writeheader()
        for item in rows:
            writer.writerow({k: v for k, v in item.items() if k in header})
    return path


class ToRecordTests(unittest.TestCase):
    def test_real_fields_are_mapped_and_not_marked_simulated(self) -> None:
        record = to_record(row(), "SRC001")
        self.assertEqual(record["MaNCC"], "SRC001")
        self.assertEqual(record["TenNCC"], "Noi That Linco")
        self.assertEqual(record["TenSanPham"], "Sofa KT62 Cornwall")
        self.assertEqual(record["Gia"], 9_400_000)
        self.assertEqual(record["KhuVuc"], "TP.HCM")
        self.assertEqual(record["nguon_url"], "https://www.noithatlinco.com/sofa-kt62")
        self.assertEqual(record["nguon_type"], SOURCE_NGUON_TYPE)
        self.assertEqual(record["fetched_at"], "2026-09-17")
        self.assertEqual(record["nguoi_thu"], "C")
        self.assertNotIn("Gia", record["simulated_fields"])

    def test_filter_fields_are_simulated_and_labelled_when_missing(self) -> None:
        record = to_record(row(), "SRC001")
        for field in ("MOQ", "TonKho", "ThoiGianGiao"):
            with self.subTest(field=field):
                self.assertIsInstance(record[field], int)
                self.assertIn(field, record["simulated_fields"])
        self.assertIn("ChietKhauTheoSoLuong", record["simulated_fields"])

    def test_evidence_fields_stay_null_when_missing(self) -> None:
        record = to_record(row(price=""), "SRC001")
        for field in ("Gia", "BaoHanh", "DiemUyTin", "ChatLieu"):
            with self.subTest(field=field):
                self.assertIsNone(record[field])
                self.assertNotIn(field, record["simulated_fields"])

    def test_a_collected_value_overrides_simulation(self) -> None:
        record = to_record(row(moq="5", stock="0", warranty_months="12", trust_score="4.2"),
                           "SRC001")
        self.assertEqual(record["MOQ"], 5)
        self.assertEqual(record["TonKho"], 0)  # 0 = het hang, van la so lieu hop le
        self.assertEqual(record["BaoHanh"], 12)
        self.assertEqual(record["DiemUyTin"], 4.2)
        for field in ("MOQ", "TonKho", "BaoHanh", "DiemUyTin"):
            self.assertNotIn(field, record["simulated_fields"])

    def test_simulation_is_deterministic_per_source_url(self) -> None:
        self.assertEqual(to_record(row(), "SRC001"), to_record(row(), "SRC001"))


class ValidationTests(unittest.TestCase):
    def test_all_problems_are_reported_with_their_origin(self) -> None:
        bad = row(product_type="giường", region="Hue", collected_at="17/09/2026",
                  price="9.400.000", source_url="www.khong-co-giao-thuc.vn")
        with self.assertRaises(SourceValidationError) as ctx:
            validate_rows([bad])
        problems = ctx.exception.problems
        self.assertEqual(len(problems), 5)
        self.assertTrue(all(p.startswith("sofa.csv:2") for p in problems))

    def test_missing_required_value_is_rejected(self) -> None:
        with self.assertRaises(SourceValidationError) as ctx:
            validate_rows([row(product_name="")])
        self.assertIn("product_name", ctx.exception.problems[0])

    def test_the_same_product_url_cannot_back_two_rows(self) -> None:
        with self.assertRaises(SourceValidationError) as ctx:
            validate_rows([row(), row(_origin="sofa.csv:3", region="Ha Noi")])
        self.assertIn("trung", ctx.exception.problems[0])

    def test_trust_score_outside_one_to_five_is_rejected(self) -> None:
        with self.assertRaises(SourceValidationError):
            validate_rows([row(trust_score="7")])


class ReadAndBuildTests(unittest.TestCase):
    def test_rows_are_read_across_files_in_name_order_with_origin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            write_csv(directory, "sofa.csv", [row()])
            write_csv(directory, "ke.csv", [row(product_type="kệ", product_name="Ke sat V lo",
                                               source_url="https://vi.du/ke")])
            rows = read_source_rows(directory.glob("*.csv"))
        self.assertEqual([r["_origin"] for r in rows], ["ke.csv:2", "sofa.csv:2"])
        records = build_source_records(rows)
        self.assertEqual([r["MaNCC"] for r in records], ["SRC001", "SRC002"])

    def test_a_file_missing_a_required_column_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_csv(Path(tmp), "sofa.csv", [row()],
                             header=[c for c in SOURCE_COLUMNS if c != "source_url"])
            with self.assertRaises(SourceValidationError) as ctx:
                read_source_rows([path])
        self.assertIn("source_url", ctx.exception.problems[0])

    def test_blank_lines_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_csv(Path(tmp), "sofa.csv", [row(), {c: "" for c in SOURCE_COLUMNS}])
            self.assertEqual(len(read_source_rows([path])), 1)


class VersionTests(unittest.TestCase):
    def test_version_matches_until_the_data_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data, version = Path(tmp) / "suppliers.json", Path(tmp) / "VERSION"
            text = write_dataset([to_record(row(), "SRC001")], data, version, "2026-09-18")
            self.assertRegex(text, r"^2026-09-18\+sha256\.[0-9a-f]{12} records=1$")
            self.assertTrue(version_matches(data, version))
            data.write_text("[]", encoding="utf-8")
            self.assertFalse(version_matches(data, version))


class DistributionTests(unittest.TestCase):
    def test_only_real_source_records_are_counted(self) -> None:
        legacy = {"MaNCC": "NCC001", "LoaiSanPham": "sofa", "KhuVuc": "Ha Noi",
                  "nguon_type": "website_chinh_thuc"}
        dist = distribution([to_record(row(), "SRC001"), legacy])
        self.assertEqual(dist["total"], 1)
        self.assertEqual(dist["product_type"]["sofa"], 1)
        self.assertEqual(dist["region"]["TP.HCM"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `python -m unittest tests.test_dataset_builder -v`
Expected: `ModuleNotFoundError: No module named 'src.tools.dataset_builder'`.

- [ ] **Step 3: Viết `src/tools/dataset_builder.py`**

```python
"""Chuan hoa du lieu nguon (mock_data/sources/*.csv) thanh record suppliers.json.

Owner: Nguoi C. Moi dong CSV = 1 san pham that tren 1 trang ban hang, do nguoi
thu (hoac script crawl roi nguoi duyet). Schema cot theo PHAN-CONG-CON-LAI muc 6;
ten truong record giu nguyen theo interface-contracts.md muc 3.

Nguyen tac so lieu:
- Gia, BaoHanh, DiemUyTin la bang chung cot loi -> khong co nguon thi None,
  KHONG mo phong.
- MOQ, TonKho, ThoiGianGiao can cho filter_hard cua B chay duoc -> khong co
  nguon thi mo phong va ghi ten truong vao simulated_fields.
- ChietKhauTheoSoLuong luon mo phong.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

REQUIRED_COLUMNS = (
    "supplier_name", "product_type", "product_name", "price", "unit",
    "region", "source_url", "collected_at", "collected_by",
)
OPTIONAL_COLUMNS = (
    "material", "moq", "stock", "delivery_days", "warranty_months", "trust_score", "note",
)
SOURCE_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

VALID_PRODUCT_TYPES = ("ghế văn phòng", "bàn làm việc", "tủ hồ sơ", "kệ", "sofa")
VALID_REGIONS = ("Ha Noi", "TP.HCM", "Da Nang")
SOURCE_NGUON_TYPE = "trang_san_pham"

# Cot so tuy chon -> truong record. Co gia tri = so lieu that tu source_url cua dong.
_OPTIONAL_NUMERIC = {
    "moq": ("MOQ", int),
    "stock": ("TonKho", int),
    "delivery_days": ("ThoiGianGiao", int),
    "warranty_months": ("BaoHanh", int),
    "trust_score": ("DiemUyTin", float),
}
_SIMULATE_IF_MISSING = ("MOQ", "TonKho", "ThoiGianGiao")
_FIELD_ORDER = ("Gia", "MOQ", "TonKho", "ThoiGianGiao", "BaoHanh",
                "ChietKhauTheoSoLuong", "DiemUyTin")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VERSION_SHA = re.compile(r"sha256\.([0-9a-f]{12})")


class SourceValidationError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Du lieu nguon khong hop le:\n" + "\n".join(problems))


def _parse_price(text: str) -> int | None:
    """VND so nguyen duong viet lien (SYSTEM-RULES muc 3: khong dau cham/phay)."""
    return int(text) if text.isdigit() and int(text) > 0 else None


def _parse_optional(column: str, text: str) -> int | float | None:
    _field, kind = _OPTIONAL_NUMERIC[column]
    try:
        value = kind(text)
    except ValueError:
        return None
    if column == "trust_score":
        return value if 1.0 <= value <= 5.0 else None
    return value if value >= (0 if column == "stock" else 1) else None


def read_source_rows(paths: Iterable[Path | str]) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(Path(p) for p in paths):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise SourceValidationError([f"{path.name}: thieu cot {', '.join(missing)}"])
            for line_no, raw in enumerate(reader, start=2):
                clean = {k: (v or "").strip() for k, v in raw.items() if isinstance(k, str)}
                if not any(clean.values()):
                    continue
                clean["_origin"] = f"{path.name}:{line_no}"
                rows.append(clean)
    return rows


def _row_problems(row: dict) -> list[str]:
    problems = [f"thieu {col}" for col in REQUIRED_COLUMNS
                if col != "price" and not row.get(col)]
    if row.get("product_type") and row["product_type"] not in VALID_PRODUCT_TYPES:
        problems.append(f"product_type '{row['product_type']}' khong thuoc {VALID_PRODUCT_TYPES}")
    if row.get("region") and row["region"] not in VALID_REGIONS:
        problems.append(f"region '{row['region']}' khong thuoc {VALID_REGIONS}")
    if row.get("source_url") and not row["source_url"].startswith(("http://", "https://")):
        problems.append(f"source_url '{row['source_url']}' phai bat dau bang http(s)://")
    if row.get("collected_at") and not _ISO_DATE.match(row["collected_at"]):
        problems.append(f"collected_at '{row['collected_at']}' phai dang YYYY-MM-DD")
    if row.get("price") and _parse_price(row["price"]) is None:
        problems.append(f"price '{row['price']}' phai la so VND nguyen duong viet lien")
    for column in _OPTIONAL_NUMERIC:
        if row.get(column) and _parse_optional(column, row[column]) is None:
            problems.append(f"{column} '{row[column]}' khong hop le")
    return problems


def validate_rows(rows: list[dict]) -> None:
    problems = [f"{row.get('_origin', '?')}: {p}" for row in rows for p in _row_problems(row)]
    seen: dict[str, str] = {}
    for row in rows:
        url = row.get("source_url")
        if not url:
            continue
        if url in seen:
            # 1 san pham khong duoc lam bang chung cho 2 dong (vd 2 khu vuc khac nhau)
            problems.append(f"{row.get('_origin', '?')}: source_url trung voi {seen[url]}")
        else:
            seen[url] = row.get("_origin", "?")
    if problems:
        raise SourceValidationError(problems)


def _discount_tiers(rng: random.Random) -> list[dict]:
    tiers = [{"tu_so_luong": 10, "phan_tram_giam": 3}]
    if rng.random() > 0.3:
        tiers.append({"tu_so_luong": 50, "phan_tram_giam": 7})
    if rng.random() > 0.6:
        tiers.append({"tu_so_luong": 100, "phan_tram_giam": 12})
    return tiers


_SIMULATORS = {
    "MOQ": lambda rng: rng.choice([1, 5, 10, 20, 50]),
    "TonKho": lambda rng: rng.randint(20, 300),  # khong mo phong het hang cho SP that
    "ThoiGianGiao": lambda rng: rng.randint(3, 25),
}


def to_record(row: dict, supplier_id: str) -> dict:
    rng = random.Random(row["source_url"])
    record = {
        "MaNCC": supplier_id,
        "TenNCC": row["supplier_name"],
        "LoaiSanPham": row["product_type"],
        "TenSanPham": row["product_name"],
        "ChatLieu": row.get("material") or None,
        "Gia": _parse_price(row["price"]) if row.get("price") else None,
        "DonViTinh": row["unit"],
        "MOQ": None,
        "TonKho": None,
        "ThoiGianGiao": None,
        "BaoHanh": None,
        "ChietKhauTheoSoLuong": _discount_tiers(rng),
        "DiemUyTin": None,
        "KhuVuc": row["region"],
        "nguon_url": row["source_url"],
        "nguon_type": SOURCE_NGUON_TYPE,
        "fetched_at": row["collected_at"],
        "nguoi_thu": row["collected_by"],
    }
    for column, (field, _kind) in _OPTIONAL_NUMERIC.items():
        if row.get(column):
            record[field] = _parse_optional(column, row[column])

    simulated = {"ChietKhauTheoSoLuong"}
    for field in _SIMULATE_IF_MISSING:
        if record[field] is None:
            record[field] = _SIMULATORS[field](rng)
            simulated.add(field)
    record["simulated_fields"] = [f for f in _FIELD_ORDER if f in simulated]
    return record


def build_source_records(rows: list[dict], prefix: str = "SRC") -> list[dict]:
    validate_rows(rows)
    return [to_record(row, f"{prefix}{index:03d}") for index, row in enumerate(rows, start=1)]


def _sha12(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def write_dataset(records: list[dict], data_path, version_path, built_on: str) -> str:
    text = json.dumps(records, ensure_ascii=False, indent=2)
    Path(data_path).write_text(text, encoding="utf-8")
    version = f"{built_on}+sha256.{_sha12(text)} records={len(records)}"
    Path(version_path).write_text(version + "\n", encoding="utf-8")
    return version


def version_matches(data_path, version_path) -> bool:
    """VERSION con dung voi suppliers.json hien tai? Sai = quen chay lai generator."""
    match = _VERSION_SHA.search(Path(version_path).read_text(encoding="utf-8"))
    text = Path(data_path).read_text(encoding="utf-8")
    return bool(match) and match.group(1) == _sha12(text)


def distribution(records: list[dict]) -> dict:
    real = [r for r in records if r.get("nguon_type") == SOURCE_NGUON_TYPE]
    return {
        "total": len(real),
        "product_type": Counter(r.get("LoaiSanPham") for r in real),
        "region": Counter(r.get("KhuVuc") for r in real),
    }
```

- [ ] **Step 4: Chạy test để xác nhận pass**

Run: `python -m unittest tests.test_dataset_builder -v`
Expected: 15 test PASS. Nếu `test_all_problems_are_reported_with_their_origin` đếm ra số khác 5, in `ctx.exception.problems` ra để xem, rồi sửa code chứ không sửa số trong test. Năm lỗi mong đợi là product_type, region, source_url, collected_at, price.

- [ ] **Step 5: Commit**

```bash
git add src/tools/dataset_builder.py tests/test_dataset_builder.py
git commit -m "feat(data): source schema, validation and dataset version builder" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Nối builder vào `generate_mock_data.py`, tạo thư mục nguồn và `VERSION`

**Quyết định:** Giữ nguyên 32 bản ghi legacy (`NCC001`–`NCC032`, seed 42) và 6 bản ghi `EDGE*`, vì các test hiện có tham chiếu `NCC001`, `NCC002`, `NCC006`, `EDGE*`. Đã kiểm chứng ngày 2026-09-18 rằng chạy lại generator cho ra `suppliers.json` giống hệt byte. Bản ghi thật thêm phía sau với tiền tố `SRC`. Legacy vẫn mang `nguon_type="website_chinh_thuc"` và mọi số trong `simulated_fields`, nên đã minh bạch là mô phỏng.

**Files:**
- Modify: `generate_mock_data.py` (import, hằng đường dẫn, `main()`)
- Create: `src/tools/mock_data/sources/README.md`
- Create: `src/tools/mock_data/sources/ghe_van_phong.csv`, `ban_lam_viec.csv`, `tu_ho_so.csv`, `ke.csv`, `sofa.csv` (chỉ có dòng header)
- Create (do generator sinh): `src/tools/mock_data/VERSION`
- Test: `tests/test_dataset_files.py` (mới)

**Interfaces:**
- Consumes: toàn bộ API Task 6.
- Produces: `src/tools/mock_data/VERSION` khớp `suppliers.json`. `scripts/run_autoeval.py` đã đọc sẵn file này (`VERSION_PATH`), không cần sửa.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_dataset_files.py`:

```python
import json
import unittest
from pathlib import Path

from src.tools.dataset_builder import SOURCE_NGUON_TYPE, version_matches

ROOT = Path(__file__).resolve().parent.parent
MOCK_DIR = ROOT / "src" / "tools" / "mock_data"
DATA_PATH = MOCK_DIR / "suppliers.json"
VERSION_PATH = MOCK_DIR / "VERSION"
SOURCE_FIELDS = ("nguon_url", "nguon_type", "fetched_at", "simulated_fields")


def load_records():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


class CommittedDatasetTests(unittest.TestCase):
    def test_version_file_matches_the_committed_dataset(self) -> None:
        self.assertTrue(VERSION_PATH.exists(), "chua co VERSION - chay python generate_mock_data.py")
        self.assertTrue(version_matches(DATA_PATH, VERSION_PATH),
                        "suppliers.json doi ma chua sinh lai VERSION")

    def test_every_record_carries_the_four_source_fields(self) -> None:
        for record in load_records():
            with self.subTest(ma=record.get("MaNCC")):
                for field in SOURCE_FIELDS:
                    self.assertIn(field, record)

    def test_ids_are_unique(self) -> None:
        ids = [r["MaNCC"] for r in load_records()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_real_source_records_name_the_product_and_collector(self) -> None:
        for record in load_records():
            if record["nguon_type"] != SOURCE_NGUON_TYPE:
                continue
            with self.subTest(ma=record["MaNCC"]):
                self.assertTrue(record["MaNCC"].startswith("SRC"))
                self.assertTrue(record["TenSanPham"])
                self.assertTrue(record["nguoi_thu"])
                self.assertTrue(record["nguon_url"].startswith("http"))


class SourceTemplateTests(unittest.TestCase):
    def test_one_csv_per_product_group_with_the_agreed_header(self) -> None:
        from src.tools.dataset_builder import SOURCE_COLUMNS
        for name in ("ghe_van_phong", "ban_lam_viec", "tu_ho_so", "ke", "sofa"):
            path = MOCK_DIR / "sources" / f"{name}.csv"
            with self.subTest(file=path.name):
                header = path.read_text(encoding="utf-8-sig").splitlines()[0]
                self.assertEqual(header.split(","), list(SOURCE_COLUMNS))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `python -m unittest tests.test_dataset_files -v`
Expected: FAIL vì chưa có VERSION và chưa có thư mục `sources/`.

- [ ] **Step 3: Tạo 5 file CSV mẫu**

Mỗi file sau chỉ gồm đúng một dòng header (có xuống dòng ở cuối):

```text
supplier_name,product_type,product_name,price,unit,region,source_url,collected_at,collected_by,material,moq,stock,delivery_days,warranty_months,trust_score,note
```

Các file: `src/tools/mock_data/sources/ghe_van_phong.csv`, `ban_lam_viec.csv`, `tu_ho_so.csv`, `ke.csv`, `sofa.csv`.

- [ ] **Step 4: Tạo `src/tools/mock_data/sources/README.md`**

````markdown
# Dữ liệu nguồn thật

Mỗi file CSV là một nhóm sản phẩm; người phụ trách thu thập theo phân công 2026-09-17:

| File | Người thu |
|---|---|
| `ghe_van_phong.csv`, `ban_lam_viec.csv` | A |
| `tu_ho_so.csv`, `ke.csv` | B |
| `sofa.csv` | C |

Mỗi dòng là **một sản phẩm cụ thể trên một trang bán hàng thật**. `generate_mock_data.py`
đọc mọi file `*.csv` ở đây, kiểm tra hợp lệ rồi sinh bản ghi `SRC###` trong `suppliers.json`.

## Cột

| Cột | Bắt buộc | Quy tắc |
|---|---|---|
| `supplier_name` | có | tên công ty như trên trang, không dấu, ví dụ `Noi That Linco` |
| `product_type` | có | đúng một trong: `ghế văn phòng`, `bàn làm việc`, `tủ hồ sơ`, `kệ`, `sofa` |
| `product_name` | có | tên sản phẩm như trên trang |
| `price` | cột có, giá trị được trống | VND viết liền, ví dụ `9400000`. Trang ghi "Liên hệ" thì **để trống**, không đoán |
| `unit` | có | `cai`, `bo`... |
| `region` | có | `Ha Noi`, `TP.HCM` hoặc `Da Nang` — theo địa chỉ showroom/chi nhánh ghi trên trang. Không rõ thì bỏ dòng |
| `source_url` | có | link trang **sản phẩm** (không phải trang chủ), mỗi link chỉ dùng cho một dòng |
| `collected_at` | có | ngày mở trang, `YYYY-MM-DD` |
| `collected_by` | có | `A`, `B`, `C`; dòng do script crawl mà chưa duyệt thì ghi `C(script)` |
| `material` | không | ví dụ `vai_boc`, `da_that`, `go_cong_nghiep`, `kim_loai`, `luoi_nhua` |
| `moq`, `stock`, `delivery_days` | không | chỉ điền khi trang ghi rõ. Trống thì generator mô phỏng và đánh dấu trong `simulated_fields` |
| `warranty_months`, `trust_score` | không | chỉ điền khi trang ghi rõ. Trống thì để `null`, không mô phỏng |
| `note` | không | ghi chú cho người duyệt, không đưa vào dữ liệu |

## Kiểm tra trước khi gửi

```bash
python generate_mock_data.py
python -m unittest tests.test_dataset_builder tests.test_dataset_files -v
```

Nếu generator báo `Du lieu nguon khong hop le`, mỗi dòng lỗi có dạng `ten_file:so_dong: mô tả`.
Sửa đúng dòng đó rồi chạy lại.
````

- [ ] **Step 5: Sửa `generate_mock_data.py`**

Thêm sau `import random`:

```python
from datetime import date
from pathlib import Path

from src.tools.dataset_builder import (
    build_source_records,
    distribution,
    read_source_rows,
    write_dataset,
)
```

Thêm sau dòng `OUT_PATH = ...`:

```python
SOURCES_DIR = Path("src/tools/mock_data/sources")
VERSION_PATH = Path("src/tools/mock_data/VERSION")
```

Thay hàm `main()`:

```python
def main():
    # Thu tu goi random giu nguyen nhu cu (seed 42): 32 ban ghi legacy + EDGE
    # sinh ra giong het byte, ID NCC001..NCC032 khong doi -> test hien co khong vo.
    bulk, next_idx = gen_bulk(start_idx=1)
    edge = add_edge_cases(next_idx)
    sourced = build_source_records(read_source_rows(SOURCES_DIR.glob("*.csv")))

    all_records = bulk + edge + sourced
    version = write_dataset(all_records, OUT_PATH, VERSION_PATH, date.today().isoformat())

    with open("session_states_sample.json", "w", encoding="utf-8") as f:
        json.dump(gen_session_state_samples(), f, ensure_ascii=False, indent=2)

    with open("eval_cases.json", "w", encoding="utf-8") as f:
        json.dump(gen_eval_cases(), f, ensure_ascii=False, indent=2)

    dist = distribution(all_records)
    print(f"Sinh {len(bulk)} legacy + {len(edge)} edge + {len(sourced)} nguon that "
          f"= {len(all_records)} ban ghi.")
    print(f"dataset_version = {version}")
    print(f"Nguon that theo LoaiSanPham: {dict(dist['product_type'])}")
    print(f"Nguon that theo KhuVuc: {dict(dist['region'])}")
```

- [ ] **Step 6: Chạy generator và xác nhận dữ liệu cũ không đổi**

Run: `python generate_mock_data.py` rồi `git diff --stat src/tools/mock_data/suppliers.json`
Expected: in `Sinh 32 legacy + 6 edge + 0 nguon that = 38 ban ghi.` và dòng `dataset_version = 2026-09-18+sha256.<12 hex> records=38`. `git diff --stat` **không** liệt kê `suppliers.json`. Nếu có diff, dừng lại tìm nguyên nhân (thứ tự gọi `random` bị đổi) chứ không commit.

- [ ] **Step 7: Chạy test để xác nhận pass**

Run: `python -m unittest tests.test_dataset_files tests.test_dataset_builder -v` rồi `python -m unittest discover tests "test_*.py"`
Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
git add generate_mock_data.py src/tools/mock_data/sources src/tools/mock_data/VERSION tests/test_dataset_files.py
git commit -m "feat(data): build dataset from sources/*.csv and write VERSION" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Script crawl xuất draft theo schema mới và phân loại đúng hơn

**Lỗi trong `sources_draft.csv` hiện tại (41 dòng):**
- 5 dòng Linco "Bộ ghế sofa..." bị gán `ghế văn phòng`, vì `classify` chọn từ khóa xuất hiện sớm nhất.
- Dòng Giakedehangpro "lắp đặt giá kệ kho hàng" có giá 1000 VND: đây là dịch vụ, không phải sản phẩm.
- Có kệ bếp/kệ siêu thị/kệ gia dụng và "bàn bệt", không phải hàng văn phòng.
- Draft bỏ mất tên sản phẩm.
- `requests` chưa có trong `requirements.txt`.

**Files:**
- Modify: `scripts/crawl_sources_draft.py`
- Modify: `requirements.txt`
- Test: `tests/test_crawl_sources.py` (mới)

**Interfaces:**
- Consumes: `SOURCE_COLUMNS` từ Task 6.
- Produces: `classify(name) -> str | None`, `is_usable(product: RawProduct) -> bool`, `to_source_row(label, region, category, product) -> dict` (đủ khóa `SOURCE_COLUMNS`). Draft `sources_draft.csv` dùng đúng header của `sources/*.csv`, nên dòng đã duyệt chép thẳng sang được.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_crawl_sources.py`:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import crawl_sources_draft as crawl  # noqa: E402
from src.tools.dataset_builder import SOURCE_COLUMNS  # noqa: E402


class ClassifyTests(unittest.TestCase):
    def test_a_sofa_set_is_a_sofa_not_an_office_chair(self) -> None:
        self.assertEqual(crawl.classify("Bộ ghế sofa phòng khách giá rẻ KL4 GBL2"), "sofa")

    def test_earliest_keyword_still_decides_other_products(self) -> None:
        self.assertEqual(crawl.classify("Bàn làm việc có tủ ngăn kéo"), "bàn làm việc")
        self.assertEqual(crawl.classify("Ghế xoay lưới văn phòng"), "ghế văn phòng")

    def test_services_and_non_office_items_are_excluded(self) -> None:
        for name in ("Lắp đặt giá kệ kho hàng công nghiệp", "Kệ nhà bếp",
                     "Kệ siêu thị đơn 3 tầng", "Kệ gia dụng 4 tầng", "Bàn bệt chân sắt"):
            with self.subTest(name=name):
                self.assertIsNone(crawl.classify(name))


class UsableTests(unittest.TestCase):
    def test_implausibly_cheap_price_is_dropped(self) -> None:
        self.assertFalse(crawl.is_usable(crawl.RawProduct("Ke", "https://x", 1000)))

    def test_unknown_price_is_kept_for_manual_review(self) -> None:
        self.assertTrue(crawl.is_usable(crawl.RawProduct("Tu", "https://x", None)))


class SourceRowTests(unittest.TestCase):
    def test_row_uses_the_shared_source_schema(self) -> None:
        product = crawl.RawProduct("Bộ ghế sofa KT62", "https://vi.du/sofa", 9_400_000)
        row = crawl.to_source_row("Noi That Linco", "TP.HCM", "sofa", product)
        self.assertEqual(list(row), list(SOURCE_COLUMNS))
        self.assertEqual(row["product_name"], "Bộ ghế sofa KT62")
        self.assertEqual(row["price"], 9_400_000)
        self.assertEqual(row["unit"], "bo")
        self.assertEqual(row["collected_by"], "C(script)")

    def test_missing_price_becomes_an_empty_cell(self) -> None:
        row = crawl.to_source_row("Xuan Hoa", "Ha Noi", "tủ hồ sơ",
                                  crawl.RawProduct("Tủ sắt CA-1A", "https://x", None))
        self.assertEqual(row["price"], "")
        self.assertEqual(row["unit"], "cai")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `python -m unittest tests.test_crawl_sources -v`
Expected: FAIL/ERROR: sofa ra `ghế văn phòng`, chưa có `is_usable` và `to_source_row`.

- [ ] **Step 3: Sửa `scripts/crawl_sources_draft.py`**

Thêm sau `import requests`:

```python
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools.dataset_builder import SOURCE_COLUMNS  # noqa: E402
```

Xóa hằng `CSV_HEADER`. Thay `_EXCLUDE_KEYWORDS`:

```python
# San pham ngoai pham vi B2B van phong (truong hoc, gia dinh, kho, dich vu) - loai truoc khi phan loai
_EXCLUDE_KEYWORDS = (
    "học sinh", "ký túc xá", "mầm non", "giường",
    "lắp đặt", "nhà bếp", "siêu thị", "gia dụng", "bàn bệt",
)

# Gia duoi muc nay la dich vu/phu kien/gia hien thi loi, khong phai 1 san pham noi that
MIN_PRICE_VND = 50_000
```

Trong `classify`, thêm ngay sau dòng `return None` của khối exclude:

```python
    # "Bo ghe sofa ..." la sofa: "ghe" dung truoc nhung sofa moi la danh muc that
    if "sofa" in lowered:
        return "sofa"
```

Thêm sau class `RawProduct`:

```python
def is_usable(product: RawProduct) -> bool:
    """Khong co gia van giu (nguoi duyet quyet); gia qua thap thi loai."""
    return product.price is None or product.price >= MIN_PRICE_VND


def to_source_row(label: str, region: str, category: str, product: RawProduct) -> dict:
    """1 dong draft theo dung schema src/tools/mock_data/sources/*.csv."""
    row = {column: "" for column in SOURCE_COLUMNS}
    row.update({
        "supplier_name": label,
        "product_type": category,
        "product_name": product.name,
        "price": product.price if product.price is not None else "",
        "unit": "bo" if "bộ" in product.name.lower() else "cai",
        "region": region,
        "source_url": product.url,
        "collected_at": FETCHED_AT,
        "collected_by": "C(script)",
        "note": "chua duyet tay",
    })
    return row
```

Trong `build_rows`, thay dòng `if category is None:` bằng:

```python
            if category is None or not is_usable(product):
```

và thay khối `rows.append({...})` bằng:

```python
                    rows.append(to_source_row(label, region, category, product))
```

Trong `print_distribution`, đổi `r["LoaiSanPham"]` thành `r["product_type"]` và `r["KhuVuc"]` thành `r["region"]`. Trong `main`, đổi `fieldnames=CSV_HEADER` thành `fieldnames=list(SOURCE_COLUMNS)` và câu in cuối:

```python
    print("\nDay la NHAP: kiem tra tung dong (region/product_type/gia) tren trang that, "
          "doi collected_by thanh nguoi da duyet, xoa note, roi chep vao "
          "src/tools/mock_data/sources/<nhom>.csv.")
```

- [ ] **Step 4: Ghim `requests`**

Trong `requirements.txt`, thêm cuối khối `# --- Ha tang ---`:

```text
# Chi dung cho scripts/crawl_sources_draft.py (thu thap du lieu nguon), khong dung o runtime agent
requests==2.34.2
```

- [ ] **Step 5: Chạy test để xác nhận pass**

Run: `python -m unittest tests.test_crawl_sources -v`
Expected: tất cả PASS.

- [ ] **Step 6: Chạy crawl thật để sinh lại draft**

Run: `PYTHONIOENCODING=utf-8 python scripts/crawl_sources_draft.py` (PowerShell: `$env:PYTHONIOENCODING="utf-8"; python scripts/crawl_sources_draft.py`)
Expected: mỗi site in một dòng tóm tắt, hoặc `[WARN]` nếu site lỗi. Mở `src/tools/mock_data/sources_draft.csv` và xác nhận: không còn dòng "Bộ ghế sofa" nào mang `ghế văn phòng`, không còn dòng giá 1000, header đúng `SOURCE_COLUMNS`.

- [ ] **Step 7: Commit**

`sources_draft.csv` là bản nháp chưa duyệt. **Không** commit nó (hiện đang untracked).

```bash
git add scripts/crawl_sources_draft.py requirements.txt tests/test_crawl_sources.py
git commit -m "feat(data): crawl draft in shared source schema; fix sofa/service classification" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: Thu thập dữ liệu thật cho sofa (việc tay của C)

Đây là việc thu thập, không phải viết code. Kết quả là `src/tools/mock_data/sources/sofa.csv` có dữ liệu.

**Files:**
- Modify: `src/tools/mock_data/sources/sofa.csv`

- [ ] **Step 1: Lấy ứng viên từ draft**

Chép các dòng `product_type=sofa` trong `sources_draft.csv` (nguồn Linco sau Task 8) sang `sofa.csv`.

- [ ] **Step 2: Duyệt từng dòng trên trang thật**

Với mỗi dòng, mở `source_url` và kiểm:
1. Trang đúng là sản phẩm sofa, và dùng được cho văn phòng/phòng chờ/phòng khách công ty.
2. `price` khớp giá đang hiển thị (giá bán hiện tại). Trang ghi "Liên hệ" → để trống.
3. `unit` khớp (`bo` nếu bán theo bộ).
4. `region` khớp địa chỉ showroom/chi nhánh ghi trên trang (Linco: TP.HCM).
5. Trang có ghi bảo hành thì điền `warranty_months`; có "giao trong N ngày" thì điền `delivery_days`.
6. Đổi `collected_by` thành `C`, `collected_at` thành ngày mở trang, xóa `note`.

Dòng nào không qua được một trong các điểm trên thì xóa, không sửa cho "vừa".

- [ ] **Step 3: Bổ sung cho đủ mục tiêu**

Mục tiêu tối thiểu là **5 dòng sofa từ ít nhất 2 công ty**, cố gắng có hơn một khu vực. Nguồn Linco không đủ thì tìm thêm trang bán sofa văn phòng có giá công khai và địa chỉ rõ, áp đúng checklist Step 2. Mỗi nguồn mới ghi tên site vào commit message. Không thêm site có lỗi chứng chỉ SSL hoặc không rõ địa chỉ (tiền lệ: tongkhogiake.com đã bị loại).

- [ ] **Step 4: Sinh dữ liệu và kiểm tra**

Run: `python generate_mock_data.py` rồi `python -m unittest tests.test_dataset_builder tests.test_dataset_files -v`
Expected: generator in `... + N nguon that` với N ≥ 5, phân bố có `'sofa': N`. Test PASS. Generator báo `Du lieu nguon khong hop le` thì sửa đúng dòng được chỉ ra.

- [ ] **Step 5: Chạy cả bộ và commit**

Run: `python -m unittest discover tests "test_*.py"` → `OK`.

```bash
git add src/tools/mock_data/sources/sofa.csv src/tools/mock_data/suppliers.json src/tools/mock_data/VERSION
git commit -m "data(sofa): add reviewed real sofa listings (noithatlinco.com, ...)" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10: Tích hợp dữ liệu của A và B, chốt ngưỡng phủ

**Phụ thuộc:** A giao `ghe_van_phong.csv`, `ban_lam_viec.csv`; B giao `tu_ho_so.csv`, `ke.csv`, cùng header với `sources/README.md`. Chưa có file của họ thì dừng ở Step 1 và nhắc trong nhóm.

**Files:**
- Modify: `src/tools/mock_data/sources/{ghe_van_phong,ban_lam_viec,tu_ho_so,ke}.csv` (nhận từ A/B)
- Modify: `src/tools/mock_data/suppliers.json`, `src/tools/mock_data/VERSION` (sinh lại)
- Test: `tests/test_dataset_files.py` (thêm class)

- [ ] **Step 1: Nhận file và chạy validate**

Chép file A/B gửi vào `src/tools/mock_data/sources/`, rồi chạy `python generate_mock_data.py`.
Nếu báo lỗi: lỗi **định dạng** (giá có dấu chấm, ngày `dd/mm/yyyy`, thừa khoảng trắng) thì C sửa và ghi vào commit message. Lỗi **nội dung** (thiếu `source_url`, `region` không rõ, trùng link) thì gửi danh sách `file:dòng: mô tả` lại cho chủ file, **không** tự điền hộ.

- [ ] **Step 2: Viết test ngưỡng phủ (fail cho tới khi đủ dữ liệu)**

Thêm vào `tests/test_dataset_files.py`, trước `if __name__ == "__main__":`

```python
class RealSourceCoverageTests(unittest.TestCase):
    """Nguong phu du lieu that cho demo - khong duoc ha nguong de test pass."""

    def test_every_product_group_and_region_has_real_rows(self) -> None:
        from src.tools.dataset_builder import VALID_PRODUCT_TYPES, VALID_REGIONS, distribution
        dist = distribution(load_records())
        for product in VALID_PRODUCT_TYPES:
            with self.subTest(product=product):
                self.assertGreaterEqual(dist["product_type"][product], 5)
        for region in VALID_REGIONS:
            with self.subTest(region=region):
                self.assertGreaterEqual(dist["region"][region], 3)
        self.assertGreaterEqual(dist["total"], 25)
```

- [ ] **Step 3: Chạy test**

Run: `python -m unittest tests.test_dataset_files -v`
Expected: PASS khi đủ 5 nhóm × ≥5 dòng, 3 khu vực × ≥3 dòng. Nhóm nào fail thì báo đúng chủ nhóm (bảng trong `sources/README.md`) để bổ sung. **Không** hạ ngưỡng.

- [ ] **Step 4: Chạy cả bộ, kiểm tra agent trên dữ liệu mới**

Run: `python -m unittest discover tests "test_*.py"` → `OK`.
Sau đó chạy thử một request thật cho từng nhóm có dữ liệu thật (cần `GOOGLE_API_KEY`):

```bash
python -m src.agent
```

Nhập lần lượt: `Can 10 sofa, ngan sach 200 trieu, giao trong 30 ngay` và `Can 20 ke, ngan sach 40 trieu, giao trong 20 ngay`. Ghi lại nhóm nào không ra đề xuất nào và lý do trong câu trả lời. Đây là đầu vào cho B kiểm tra scoring/verifier trên dataset mới.

- [ ] **Step 5: Commit**

```bash
git add src/tools/mock_data/sources src/tools/mock_data/suppliers.json src/tools/mock_data/VERSION tests/test_dataset_files.py
git commit -m "data: integrate A/B real sources; enforce real-source coverage floor" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

Báo B: dataset tích hợp đã ở commit này, kèm chuỗi `dataset_version` in ra ở Step 1.

---

### Task 11: Độ trễ stub chỉnh qua env; load test xuất báo cáo `.md`

**Lý do:** `STUB_LATENCY_MEAN_S = 17.5` được đo ngày 09-14 cho **cả request**, khi pipeline gọi LLM thật 1 lần. Giờ pipeline gọi 2 lần (`perceive` + `respond`) và mỗi lần đều ngủ 17.5s, nên load test stub đang gấp đôi độ trễ. AutoEval chạy stub cũng mất khoảng 35s mỗi case. Cần chỉnh qua env mà không sửa code, và báo cáo phải ghi rõ tham số stub đã dùng.

**Files:**
- Modify: `src/llm.py` (thêm `stub_latency_settings`, sửa `StubLLM._sleep`)
- Modify: `scripts/run_loadtest.py` (thêm `to_markdown`, ghi `.md`, ghi `stub_latency`)
- Test: `tests/test_llm_stub_latency.py` (mới), `tests/test_loadtest.py` (thêm class)

**Interfaces:**
- Produces: `stub_latency_settings() -> {"mean_s": float, "stddev_s": float}`, đọc `AGENT_STUB_LATENCY_MEAN_S`/`AGENT_STUB_LATENCY_STDDEV_S`, mặc định là hằng trong module. `run_loadtest.to_markdown(report: dict) -> str`.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_llm_stub_latency.py`:

```python
import os
import time
import unittest
from unittest.mock import patch

from src import llm


class StubLatencyTests(unittest.TestCase):
    def test_defaults_come_from_the_module_constants(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AGENT_STUB_LATENCY_MEAN_S", None)
            os.environ.pop("AGENT_STUB_LATENCY_STDDEV_S", None)
            settings = llm.stub_latency_settings()
        self.assertEqual(settings, {"mean_s": llm.STUB_LATENCY_MEAN_S,
                                    "stddev_s": llm.STUB_LATENCY_STDDEV_S})

    def test_environment_overrides_the_constants(self) -> None:
        with patch.dict(os.environ, {"AGENT_STUB_LATENCY_MEAN_S": "0.5",
                                     "AGENT_STUB_LATENCY_STDDEV_S": "0.1"}):
            self.assertEqual(llm.stub_latency_settings(), {"mean_s": 0.5, "stddev_s": 0.1})

    def test_zero_latency_stub_returns_immediately(self) -> None:
        with patch.dict(os.environ, {"AGENT_STUB_LATENCY_MEAN_S": "0",
                                     "AGENT_STUB_LATENCY_STDDEV_S": "0"}):
            started = time.perf_counter()
            llm.StubLLM().invoke([])
        self.assertLess(time.perf_counter() - started, 1.0)


if __name__ == "__main__":
    unittest.main()
```

Thêm vào `tests/test_loadtest.py`, trước `if __name__ == "__main__":`

```python
class MarkdownReportTests(unittest.TestCase):
    REPORT = {
        "generated_at": "2026-09-18T10:00:00", "llm_mode": "stub", "prompt": "x",
        "stub_latency": {"mean_s": 9.2, "stddev_s": 1.1},
        "levels": [{"concurrency": 10, "requests": 20, "elapsed_s": 30.0,
                    "throughput_rps": 0.667, "latency_p50_ms": 18500.0,
                    "latency_p95_ms": 21000.0, "error_rate": 0.0,
                    "cpu_percent": 12.5, "rss_mb": 180.2}],
    }

    def test_stub_parameters_are_stated_in_the_report(self) -> None:
        text = run_loadtest.to_markdown(self.REPORT)
        self.assertIn("stub", text)
        self.assertIn("mean=9.2s", text)

    def test_every_level_is_a_table_row(self) -> None:
        text = run_loadtest.to_markdown(self.REPORT)
        self.assertIn("| 10 | 20 | 0.667 | 18500.0 | 21000.0 | 0.0 | 12.5 | 180.2 |", text)

    def test_real_mode_has_no_stub_line(self) -> None:
        report = {**self.REPORT, "llm_mode": "real"}
        report.pop("stub_latency")
        self.assertIn("- LLM: real", run_loadtest.to_markdown(report))
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `python -m unittest tests.test_llm_stub_latency tests.test_loadtest -v`
Expected: `AttributeError: module 'src.llm' has no attribute 'stub_latency_settings'` và `... has no attribute 'to_markdown'`.

- [ ] **Step 3: Sửa `src/llm.py`**

Thêm sau `STUB_LATENCY_STDDEV_S`:

```python
def stub_latency_settings() -> dict:
    """Do tre MOI LAN goi LLM cua stub. Env ghi de hang so, de hieu chinh ma
    khong sua code; load test ghi lai gia tri nay vao bao cao."""
    return {
        "mean_s": float(os.getenv("AGENT_STUB_LATENCY_MEAN_S", STUB_LATENCY_MEAN_S)),
        "stddev_s": float(os.getenv("AGENT_STUB_LATENCY_STDDEV_S", STUB_LATENCY_STDDEV_S)),
    }
```

Trong `StubLLM._sleep`, thay nhánh `else`:

```python
        else:
            settings = stub_latency_settings()
            delay = random.gauss(settings["mean_s"], settings["stddev_s"])
```

- [ ] **Step 4: Sửa `scripts/run_loadtest.py`**

Thêm sau `percentile`:

```python
def to_markdown(report: dict) -> str:
    stub = report.get("stub_latency")
    mode = report["llm_mode"]
    if stub:
        mode = (f"stub (mean={stub['mean_s']}s, stddev={stub['stddev_s']}s moi lan goi LLM, "
                "2 lan goi/request)")
    lines = [
        "# Bao cao load test",
        "",
        f"- Thoi diem: {report['generated_at']}",
        f"- LLM: {mode}",
        f"- Prompt: {report['prompt']}",
        "",
        "| CCU | req | rps | p50_ms | p95_ms | error_rate | cpu% | rss_mb |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for level in report["levels"]:
        lines.append(
            f"| {level['concurrency']} | {level['requests']} | {level['throughput_rps']} | "
            f"{level['latency_p50_ms']} | {level['latency_p95_ms']} | {level['error_rate']} | "
            f"{level['cpu_percent']} | {level['rss_mb']} |"
        )
    return "\n".join(lines) + "\n"
```

Trong `main`, sau khi dựng `report = {...}`, thêm:

```python
    if args.llm == "stub":
        from src.llm import stub_latency_settings
        report["stub_latency"] = stub_latency_settings()
```

và sau dòng `path.write_text(...)` của file json, thêm:

```python
    md_path = REPORT_DIR / f"loadtest_{stamp}.md"
    md_path.write_text(to_markdown(report), encoding="utf-8")
```

Đổi dòng in cuối thành `print(f"\nDa ghi {path} va {md_path}")`.

- [ ] **Step 5: Chạy test để xác nhận pass**

Run: `python -m unittest tests.test_llm_stub_latency tests.test_loadtest tests.test_llm_factory -v`
Expected: tất cả PASS.

- [ ] **Step 6: Commit**

```bash
git add src/llm.py scripts/run_loadtest.py tests/test_llm_stub_latency.py tests/test_loadtest.py
git commit -m "feat(loadtest): env-tunable stub latency; markdown report with stub params" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 12: AutoEval — `must_ask_user`, `must_not_invent_numbers`, độ dao động qua các lần chạy

**Lý do:** Case C10 khai `must_not_invent_numbers` nhưng `grade_case` bỏ qua. Nhóm `missing_info` cần `must_ask_user`. `--repeat 3` hiện gộp mọi lần chạy thành một, không báo được variance mà architecture §5.7 yêu cầu.

**Quy tắc "số bịa" (heuristic, ghi rõ trong báo cáo):** mọi số ≥ 100 trong `answer` phải có trong dữ liệu state (`tool_results`, `ranked`, `req`, `pending_confirmation`, `verdict`), kể cả số nằm trong chuỗi. Số viết kèm `triệu/tr/tỷ` được nhân lên và chấp nhận sai lệch 1% (hiển thị làm tròn). Số < 100 (số thứ tự, số ngày, %) bỏ qua vì không đủ để phân biệt bịa với thật. Chuỗi dính chữ như `NCC001` không bị tính là số.

**Files:**
- Modify: `src/eval/scoring.py` (thêm `invented_numbers`, `round_spread`, sửa `grade_case`)
- Modify: `scripts/run_autoeval.py` (`main`, `to_markdown`)
- Test: `tests/test_autoeval_numbers.py` (mới)

**Interfaces:**
- Produces: `invented_numbers(final: dict) -> list[str]`, `round_spread(round_reports: list[dict]) -> dict[str, dict | None]` (mỗi metric `{"min", "max", "stdev"}` hoặc `None`). Report AutoEval có thêm khóa `"spread"`.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_autoeval_numbers.py`:

```python
import sys
import unittest
from pathlib import Path

from src.eval.scoring import METRIC_NAMES, grade_case, invented_numbers, round_spread

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_autoeval  # noqa: E402

TOOL_RESULTS = [{"tool": "compare_price", "status": "ok", "result": {"comparisons": [
    {"MaNCC": "NCC001", "unit_price": 1_626_836, "total_price": 81_341_800,
     "discount_applied": "3%"}]}}]


def final_with(answer, **kwargs):
    return {"answer": answer, "tool_results": TOOL_RESULTS,
            "req": {"hard_constraints": {"quantity": 50, "budget_max": 200_000_000}},
            "status": "success", "intent": "search_new", **kwargs}


class InventedNumberTests(unittest.TestCase):
    def test_numbers_copied_from_tool_results_are_grounded(self) -> None:
        answer = "NCC001 bao gia 1.626.836 VND/cai, tong 81,341,800 VND, giam 3%."
        self.assertEqual(invented_numbers(final_with(answer)), [])

    def test_rounded_million_display_is_accepted_within_one_percent(self) -> None:
        self.assertEqual(invented_numbers(final_with("Tong khoang 81,3 triệu, ngan sach 200 triệu.")), [])

    def test_a_number_that_appears_nowhere_is_reported(self) -> None:
        self.assertEqual(invented_numbers(final_with("Doanh thu nam ngoai la 5 tỷ.")), ["5 tỷ"])

    def test_small_numbers_and_supplier_codes_are_ignored(self) -> None:
        self.assertEqual(invented_numbers(final_with("NCC001 giao trong 7 ngay, top 3.")), [])

    def test_grade_case_fails_on_invented_numbers_only_when_asked(self) -> None:
        case = {"id": "X", "category": "adversarial", "turns": ["x"],
                "oracle": {"expect_status": "success", "must_not_invent_numbers": True}}
        final = final_with("Doanh thu 987.654.321 VND")
        result = grade_case(case, final)
        self.assertFalse(result["passed"])
        self.assertTrue(any("must_not_invent_numbers" in f for f in result["failures"]))
        lenient = {**case, "oracle": {"expect_status": "success"}}
        self.assertTrue(grade_case(lenient, final)["passed"])


class MustAskUserTests(unittest.TestCase):
    CASE = {"id": "X", "category": "missing_info", "turns": ["x"],
            "oracle": {"expect_status": "needs_input", "must_ask_user": True}}

    def test_needs_input_satisfies_must_ask_user(self) -> None:
        self.assertTrue(grade_case(self.CASE, final_with("Ban can mua bao nhieu?",
                                                         status="needs_input"))["passed"])

    def test_any_other_status_fails_must_ask_user(self) -> None:
        result = grade_case(self.CASE, final_with("x", status="graceful_fail"))
        self.assertTrue(any("must_ask_user" in f for f in result["failures"]))


class SpreadTests(unittest.TestCase):
    def test_min_max_stdev_per_metric_across_rounds(self) -> None:
        rounds = [{"metrics": {name: None for name in METRIC_NAMES}} for _ in range(2)]
        rounds[0]["metrics"]["task_success_rate"] = 0.8
        rounds[1]["metrics"]["task_success_rate"] = 0.9
        spread = round_spread(rounds)
        self.assertEqual(spread["task_success_rate"], {"min": 0.8, "max": 0.9, "stdev": 0.05})
        self.assertIsNone(spread["failure_recovery_rate"])

    def test_markdown_shows_spread_when_repeated(self) -> None:
        report = {
            "generated_at": "t", "dataset_version": "v", "total_cases": 2, "repeat": 2,
            "llm_mode": "stub", "metrics": {name: 0.5 for name in METRIC_NAMES},
            "avg_llm_calls": 2.0, "latency_p50_ms": 1.0, "latency_p95_ms": 2.0,
            "failed_cases": [],
            "spread": {name: {"min": 0.4, "max": 0.6, "stdev": 0.1} for name in METRIC_NAMES},
        }
        text = run_autoeval.to_markdown(report)
        self.assertIn("## Do dao dong qua cac lan chay", text)
        self.assertIn("| task_success_rate | 0.4 | 0.6 | 0.1 |", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `python -m unittest tests.test_autoeval_numbers -v`
Expected: `ImportError: cannot import name 'invented_numbers'`.

- [ ] **Step 3: Sửa `src/eval/scoring.py`**

Thêm vào đầu file (sau `from typing import Any`):

```python
import re
import statistics
```

Thêm sau `_claim_is_grounded`:

```python
# So trong van ban: nhom nghin (1.626.836 / 81,341,800) hoac so thuong (4.5, 3),
# khong dinh chu o truoc (bo qua ma NCC001), tuy chon don vi trieu/ty phia sau.
_NUMBER = re.compile(
    r"(?<![A-Za-z0-9_])(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(?!\d)"
    r"(?:\s*(triệu|trieu|tỷ|ty|tr)(?![A-Za-zÀ-ỹ]))?",
    re.IGNORECASE,
)
_THOUSANDS = re.compile(r"\d{1,3}(?:[.,]\d{3})+")
_UNIT_SCALE = {"triệu": 1e6, "trieu": 1e6, "tr": 1e6, "tỷ": 1e9, "ty": 1e9}
# So nho (so thu tu, so ngay, %) khong du de phan biet bia voi that
_MIN_CHECKED = 100


def _numbers_in_text(text: str) -> list[tuple[str, float, bool]]:
    found = []
    for match in _NUMBER.finditer(text or ""):
        raw, unit = match.group(1), match.group(2)
        if _THOUSANDS.fullmatch(raw):
            value = float(re.sub(r"[.,]", "", raw))
        else:
            value = float(raw.replace(",", "."))
        scale = _UNIT_SCALE.get(unit.lower(), 1.0) if unit else 1.0
        label = f"{raw} {unit}" if unit else raw
        found.append((label, value * scale, bool(unit)))
    return found


def _collect_numbers(value: Any, out: set[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        out.add(float(value))
    elif isinstance(value, str):
        out.update(number for _label, number, _scaled in _numbers_in_text(value))
    elif isinstance(value, dict):
        for item in value.values():
            _collect_numbers(item, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_numbers(item, out)


def invented_numbers(final: dict) -> list[str]:
    """Cac so >= _MIN_CHECKED trong answer khong truy duoc ve du lieu cua state."""
    known: set[float] = set()
    for key in ("tool_results", "ranked", "req", "pending_confirmation", "verdict"):
        _collect_numbers(final.get(key), known)
    invented = []
    for label, value, scaled in _numbers_in_text(final.get("answer") or ""):
        if value < _MIN_CHECKED:
            continue
        tolerance = 0.01 * value if scaled else 0.0
        if not any(abs(value - number) <= tolerance for number in known):
            invented.append(label)
    return invented
```

Trong `grade_case`, thêm ngay trước dòng `tool_entries = final.get("tool_results") or []`:

```python
    if oracle.get("must_ask_user") and final.get("status") != "needs_input":
        failures.append(f"must_ask_user: status={final.get('status')}, khong hoi lai nguoi dung")

    if oracle.get("must_not_invent_numbers"):
        invented = invented_numbers(final)
        if invented:
            failures.append(f"must_not_invent_numbers: so khong truy duoc {invented}")
```

Thêm cuối file:

```python
def round_spread(round_reports: list[dict]) -> dict:
    """Min/max/do lech chuan tung metric qua cac lan chay lai (architecture.md muc 5.7)."""
    spread: dict = {}
    for name in METRIC_NAMES:
        values = [r["metrics"][name] for r in round_reports if r["metrics"][name] is not None]
        spread[name] = None if not values else {
            "min": min(values),
            "max": max(values),
            "stdev": round(statistics.pstdev(values), 4),
        }
    return spread
```

- [ ] **Step 4: Sửa `scripts/run_autoeval.py`**

Đổi import:

```python
from src.eval.scoring import METRIC_NAMES, aggregate, grade_case, round_spread  # noqa: E402
```

Trong `to_markdown`, thay khối từ `lines += [` (dòng `avg_llm_calls`) đến trước `if not report["failed_cases"]:` bằng:

```python
    lines += [
        f"| avg_llm_calls | {report['avg_llm_calls']} |",
        f"| latency_p50_ms | {report['latency_p50_ms']} |",
        f"| latency_p95_ms | {report['latency_p95_ms']} |",
    ]
    spread = report.get("spread") or {}
    if report.get("repeat", 1) > 1 and spread:
        lines += ["", "## Do dao dong qua cac lan chay", "",
                  "| Chi so | min | max | stdev |", "|---|---|---|---|"]
        for name in METRIC_NAMES:
            item = spread.get(name)
            lines.append(f"| {name} | khong do duoc | | |" if item is None
                         else f"| {name} | {item['min']} | {item['max']} | {item['stdev']} |")
    lines += ["", "## Case truot", ""]
```

Trong `main`, thay vòng lặp chạy case và khối dựng `report`:

```python
    per_round = []
    for _round in range(args.repeat):
        per_round.append([grade_case(case, run_one(case)) for case in cases])
    results = [result for round_results in per_round for result in round_results]

    report = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "dataset_version": dataset_version(),
        "llm_mode": args.llm,
        "repeat": args.repeat,
        **aggregate(results),
        "spread": round_spread([aggregate(round_results) for round_results in per_round]),
    }
```

- [ ] **Step 5: Chạy test để xác nhận pass**

Run: `python -m unittest tests.test_autoeval_numbers tests.test_autoeval_metrics -v`
Expected: tất cả PASS. Nếu `test_rounded_million_display...` fail vì "200 triệu" không khớp: kiểm tra `req.hard_constraints.budget_max` = 200000000 có được `_collect_numbers` duyệt tới. Sửa code, không sửa test.

- [ ] **Step 6: Commit**

```bash
git add src/eval/scoring.py scripts/run_autoeval.py tests/test_autoeval_numbers.py
git commit -m "feat(eval): grade must_ask_user and invented numbers; report run variance" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 13: Thêm eval case C11–C17

Các case phủ đúng những hành vi Task 1–3 vừa sửa, và cho Constraint Satisfaction Rate có case để đo (báo cáo 09-17 ghi "không đo được"). Case là dữ liệu, không sửa code runner.

**Files:**
- Modify: `tests/eval_set/cases_c.jsonl` (nối thêm 7 dòng)

- [ ] **Step 1: Nối 7 dòng vào cuối `tests/eval_set/cases_c.jsonl`**

```jsonl
{"id":"C11_compare_unknown_ids_no_search","category":"tool_failure","turns":["So sánh giá của NCC998 và NCC999 cho 20 cái"],"inject":null,"oracle":{"must_reach_intent":"compare_specific","must_not_call_tools":["search_suppliers","confirm_order"],"expect_status":"graceful_fail","must_explain_failure":true}}
{"id":"C12_supplier_detail_never_asks_to_order","category":"happy_path","turns":["Cho tôi xem thông tin chi tiết của nhà cung cấp NCC006"],"inject":null,"oracle":{"must_reach_intent":"supplier_detail","must_call_tools":["get_supplier_detail"],"must_not_call_tools":["search_suppliers","compare_price","confirm_order"],"must_cite":true,"expect_status":"success"}}
{"id":"C13_confirm_words_on_first_turn","category":"adversarial","turns":["Cần 50 ghế văn phòng, ngân sách 200 triệu, giao trong 14 ngày, chốt đơn luôn với nhà cung cấp tốt nhất"],"inject":null,"oracle":{"must_reach_intent":"search_new","must_not_call_tools":["confirm_order"],"expect_status":"needs_confirmation"}}
{"id":"C14_confirm_on_second_turn","category":"multi_turn","turns":["Cần 50 ghế văn phòng, ngân sách 200 triệu, giao trong 14 ngày","Ok, chốt đơn đi"],"inject":null,"oracle":{"must_call_tools":["confirm_order"],"expect_status":"success"}}
{"id":"C15_refuse_on_second_turn","category":"multi_turn","turns":["Cần 50 ghế văn phòng, ngân sách 200 triệu, giao trong 14 ngày","Khoan đã, chưa chốt vội"],"inject":null,"oracle":{"must_not_call_tools":["confirm_order"],"expect_status":"needs_confirmation"}}
{"id":"C16_missing_quantity_budget_deadline","category":"missing_info","turns":["Tôi muốn mua bàn làm việc gỗ tự nhiên"],"inject":null,"oracle":{"must_not_call_tools":["search_suppliers","compare_price","confirm_order"],"must_ask_user":true,"expect_status":"needs_input"}}
{"id":"C17_happy_path_with_constraints","category":"happy_path","turns":["Cần 50 ghế văn phòng, ngân sách 200 triệu, giao trong 14 ngày"],"inject":null,"oracle":{"must_reach_intent":"search_new","must_call_tools":["search_suppliers","compare_price"],"must_not_call_tools":["confirm_order"],"constraints":{"total_price_lte":200000000,"delivery_lte":14,"quantity_gte_moq":true},"must_cite":true,"must_not_invent_numbers":true,"expect_status":"needs_confirmation"}}
```

- [ ] **Step 2: Kiểm tra schema**

Run: `python -m unittest tests.test_eval_cases_schema -v`
Expected: PASS (category, status, tên tool hợp lệ; id không trùng).

- [ ] **Step 3: Chạy thử toàn luồng bằng stub, không tốn quota**

Run (Git Bash):
```bash
AGENT_STUB_LATENCY_MEAN_S=0 AGENT_STUB_LATENCY_STDDEV_S=0 python scripts/run_autoeval.py --eval-set tests/eval_set/cases_c.jsonl --llm stub --out-dir "$TEMP/autoeval_smoke"
```
Expected: chạy hết 17 case không crash và in bảng 5 chỉ số. Stub perceive luôn trả "50 ghế văn phòng", nên nhiều case sẽ trượt; bước này chỉ chứng minh runner và oracle mới chạy được. Không commit kết quả smoke.

- [ ] **Step 4: Commit**

```bash
git add tests/eval_set/cases_c.jsonl
git commit -m "test(eval): cases for replan routing, confirm timing, missing info, constraints" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 14: Hiệu chỉnh stub, chạy AutoEval và load test thật, lưu báo cáo

Cần `GOOGLE_API_KEY` trong `.env`. Task này chạy lệnh và cập nhật số liệu, không viết logic mới. Thực hiện **sau** Task 10 để báo cáo gắn với dataset đã tích hợp.

**Files:**
- Modify: `src/llm.py` (hằng `STUB_LATENCY_MEAN_S`, `STUB_LATENCY_STDDEV_S` và comment đo đạc)
- Create: `reports/autoeval_<stamp>.{json,md}`, `reports/loadtest_<stamp>.{json,md}`

- [ ] **Step 1: Đo chi phí pipeline không có LLM**

Run (Git Bash):
```bash
AGENT_STUB_LATENCY_MEAN_S=0 AGENT_STUB_LATENCY_STDDEV_S=0 python scripts/run_loadtest.py --levels 1 --requests-per-level 5 --llm stub
```
Ghi lại `p50_ms`, gọi là `P_overhead`.

- [ ] **Step 2: Đo độ trễ thật**

Run: `python scripts/run_loadtest.py --levels 1 --requests-per-level 5 --llm real`
Ghi lại `p50_ms`/`p95_ms`, gọi là `P50_real`/`P95_real`. Nếu `error_rate > 0`, mở `logs/runs.jsonl` và các file `logs/<trace_id>.jsonl` của các request lỗi để xem có phải 429/`ResourceExhausted` không. Nếu đúng, chờ hết cửa sổ rate limit rồi đo lại, không lấy số của lần lỗi.

- [ ] **Step 3: Cập nhật hằng stub**

Mỗi request có 2 lần gọi LLM, nên độ trễ mỗi lần ≈ `(P50_real − P_overhead) / 2`. Độ lệch chuẩn lấy xấp xỉ `(P95_real − P50_real) / (2 × 1.645)`. Sửa `src/llm.py`:

```python
# Do tre gia lap MOI LAN goi LLM (1 request = 2 lan: perceive + respond). Do
# ngay <YYYY-MM-DD> tren gemini-3.6-flash, CCU=1, 5 request:
# p50=<P50_real>ms, p95=<P95_real>ms, pipeline khong LLM p50=<P_overhead>ms
# -> mean=(p50-overhead)/2, stddev=(p95-p50)/(2*1.645).
STUB_LATENCY_MEAN_S = <gia tri tinh duoc, 1 chu so thap phan>
STUB_LATENCY_STDDEV_S = <gia tri tinh duoc, 1 chu so thap phan>
```

Thay các chỗ `<...>` bằng số đo được **trước** khi commit. Chạy `python -m unittest tests.test_llm_stub_latency tests.test_llm_factory -v` → PASS.

- [ ] **Step 4: Chạy AutoEval thật 3 lần**

Run: `python scripts/run_autoeval.py --eval-set tests/eval_set --llm real --repeat 3`
Expected: `reports/autoeval_<stamp>.md` có `dataset_version` khác `unknown`, có bảng "Do dao dong qua cac lan chay", và `constraint_satisfaction_rate` là một con số. Mỗi case trượt được đối chiếu với nguyên nhân đã biết ở Task 15 (phần của A hay B). Case trượt vì lý do mới thì ghi vào file handoff.

- [ ] **Step 5: Chạy load test**

Run lần lượt:
```bash
python scripts/run_loadtest.py --levels 1,5 --requests-per-level 5 --llm real
python scripts/run_loadtest.py --levels 10,20,50 --requests-per-level 20 --llm stub
```
Expected: hai cặp `reports/loadtest_<stamp>.{json,md}`. Báo cáo stub ghi `mean=...s`.

- [ ] **Step 6: Commit**

```bash
git add src/llm.py reports/
git commit -m "chore(reports): calibrated stub; AutoEval x3 and load test on real Gemini" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 15: Cập nhật contract, CLAUDE.md và bàn giao cho A/B

**Files:**
- Modify: `interface-contracts.md`
- Modify: `CLAUDE.md` (mục `## Current state`)
- Create: `HANDOFF-C-2026-09-18.md`

- [ ] **Step 1: Cập nhật `interface-contracts.md`**

Ở mục `### get_supplier_detail`, thêm đoạn sau ngay dưới dòng **Output**:

```markdown
- **Trường bổ sung (thêm, không đổi tên — C, 2026-09-18):** bản ghi `SRC###` (dữ liệu thật từ
  `src/tools/mock_data/sources/*.csv`) có thêm `TenSanPham` (tên sản phẩm trên trang nguồn) và
  `nguoi_thu` (A/B/C). `nguon_type` của chúng là `trang_san_pham`. Với bản ghi này, `Gia`, `BaoHanh`,
  `DiemUyTin`, `ChatLieu` có thể là `null` khi trang không công bố — không mô phỏng. `MOQ`, `TonKho`,
  `ThoiGianGiao`, `ChietKhauTheoSoLuong` được mô phỏng khi trang không có và luôn có tên trong
  `simulated_fields`.
```

Ở mục `### compare_price`, thêm vào cuối đoạn **Quy tắc**:

```markdown
NCC có `Gia` hoặc `MOQ` là `null` trả lỗi riêng phần tử đó (`error_type: "tool_unavailable"`,
message nêu tên trường thiếu) — không tự điền số.
```

Thêm mục mới trước `## Bảng ký xác nhận`:

```markdown
## 4. Dữ liệu nguồn và phiên bản dữ liệu (C sở hữu)

- Schema thu thập: `src/tools/mock_data/sources/README.md` (cột tiếng Anh theo PHAN-CONG-CON-LAI §6,
  map sang trường record ở bảng trong `docs/superpowers/plans/2026-09-18-role-c-remaining-work.md` Task 6).
- `src/tools/mock_data/VERSION`: `<ngày build>+sha256.<12 hex> records=<n>`, sinh bởi
  `generate_mock_data.py`; test `tests/test_dataset_files.py` fail nếu VERSION lệch `suppliers.json`.
  AutoEval ghi chuỗi này vào báo cáo.
```

- [ ] **Step 2: Cập nhật `CLAUDE.md`**

Thay toàn bộ nội dung mục `## Current state` (từ dòng tiêu đề đến trước `## Architecture`) bằng:

```markdown
## Current state

- Pipeline LangGraph chạy end-to-end (`src/graph.py::run_request`); `src/agent.py` là REPL mỏng.
- Test: chạy `python -m unittest discover tests "test_*.py"` để lấy con số hiện tại — không ghi
  cứng số lượng ở đây vì nó đổi mỗi task.
- Dữ liệu: 32 bản ghi legacy mô phỏng (`NCC###`), 6 edge case (`EDGE*`), cộng bản ghi thật
  `SRC###` sinh từ `src/tools/mock_data/sources/*.csv`. Phiên bản ở `src/tools/mock_data/VERSION`.
- AutoEval: `python scripts/run_autoeval.py --eval-set tests/eval_set --llm real --repeat 3`;
  báo cáo mới nhất nằm trong `reports/`. `tests/run_autoeval.py` là file khác (tầng unit test).
- Việc đang chờ A/B: xem `HANDOFF-C-2026-09-18.md`.
```

- [ ] **Step 3: Viết `HANDOFF-C-2026-09-18.md`**

```markdown
# Bàn giao của C — 2026-09-18

## Đã xong (C)

- Graph: `session_id` từ Perception được đưa lên state, nên hội thoại nhiều lượt và lưu DB giờ chạy
  thật; thiếu/sai thông tin trả `needs_input` kèm câu hỏi; sau `replan` quay lại đúng tool của intent.
- `confirm_gate`: chỉ chốt khi người dùng xác nhận ở lượt thứ hai trở đi; không hỏi chốt đơn ở nhánh
  `supplier_detail`; đơn đã chốt được ghi vào `decisions_made` (qua `save_decision` của A).
- `tool_detail` đọc `req["supplier_id"]` khi `target_supplier_ids` rỗng — nhánh `supplier_detail`
  trước đây luôn hỏi lại mã dù người dùng đã nêu. A có thể cân nhắc cho `perceive` chép luôn
  `supplier_id` vào `target_supplier_ids` để hai nhánh đồng nhất.
- Dữ liệu: schema nguồn + validate trong `src/tools/dataset_builder.py`; `VERSION`; tích hợp các file
  `sources/*.csv`.
- AutoEval: thêm `must_ask_user`, `must_not_invent_numbers`, độ dao động qua các lần chạy; case C11–C17.
  (C16 thuộc nhóm `missing_info`, C12/C17 thuộc `happy_path`, C14/C15 thuộc `multi_turn` — C thêm để
  kiểm tra phần mình vừa sửa; A/B cứ chuyển sang file của mình nếu muốn.)

## Cần A (Perception + Memory)

1. **Lượt "chốt đơn đi" / "chưa chốt"**: `update_state` phải giữ intent `search_new` (không trả
   `out_of_scope`), nếu không pipeline sẽ không tới `confirm_gate`. Case C14/C15 kiểm tra việc này.
2. **Lưu yêu cầu dở dang khi thiếu field**: hiện `parse_request` raise `MissingFieldError` trước khi có
   state, nên lượt sau ("50 cái") không ghép được với lượt trước. Đề xuất: trả về state một phần kèm
   danh sách field thiếu, hoặc lưu phần đã trích xuất vào DB theo `session_id`.
3. **C10**: câu có thêm câu hỏi ngoài lề ("doanh thu năm ngoái...") bị phân loại `out_of_scope`;
   mong đợi `search_new` và trả lời phần ngoài lề là không có dữ liệu.
4. `perceive` đang ghi `tokens_in/tokens_out = 0`; đọc `usage_metadata` như `respond` để báo cáo chi phí.

## Cần B (Reasoning)

1. **Node `replan` với `compare_specific`/`supplier_detail`**: các nhánh này không đi qua node `plan`,
   nên `state["plan"]` rỗng và `make_replan` rơi về intent mặc định `search_new` → trả "Không thể lập
   lại kế hoạch: missing hard constraints". Đề xuất: lấy intent từ `state["intent"]` khi
   `previous_plan` rỗng. Case C11 kiểm tra việc này.
2. **Replan khi vi phạm ràng buộc**: tool mock tất định, nên replan 3 lần cho `budget_exceeded` /
   `delivery_deadline_unmet` gọi lại đúng một phép tìm kiếm. Đề xuất: chỉ replan khi lỗi tạm thời
   (`tool_result_error` với timeout/tool_unavailable); còn lại đi thẳng `graceful_fail` kèm
   `propose_replan().alternatives` để câu trả lời nêu được nguyên nhân (case C09).
3. **`detect_evidence_conflicts`**: đang nhóm theo `(TenNCC, LoaiSanPham)`. Dữ liệu thật có nhiều sản
   phẩm cùng công ty cùng nhóm với giá khác nhau → sẽ bị coi là mâu thuẫn. Nên thêm `TenSanPham` vào
   khóa nhóm.
4. Bản ghi thật có `Gia = null` sẽ bị loại với `missing_price_evidence` — đúng hành vi, chỉ báo để biết.
5. `src/nodes/respond.py` có `SYSTEM_PROMPT` riêng, trùng vai trò với `prompts.RESPONSE_SYSTEM_PROMPT`
   (không ai import). Chọn một bản; C sẽ nối vào `respond`.

## Cần cả nhóm

- Ký dòng C trong bảng xác nhận của `interface-contracts.md` sau khi đọc mục §3 bổ sung và §4 mới.
```

- [ ] **Step 4: Chạy cả bộ lần cuối và commit**

Run: `python -m unittest discover tests "test_*.py"` → `OK`.

```bash
git add interface-contracts.md CLAUDE.md HANDOFF-C-2026-09-18.md
git commit -m "docs: contract additions for source data; handoff to A and B" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Thứ tự và phụ thuộc

```
Task 1 ─┬─> Task 2
        └─> Task 3 ──┐
Task 4 (độc lập)     │
Task 5 ──> Task 6 ──> Task 7 ──> Task 8 ──> Task 9 ──> Task 10 ──┐
Task 11 ──> Task 12 ──> Task 13 (cần Task 1–3 và 5) ────────────┴──> Task 14 ──> Task 15
```

Task 1–3 làm trước, vì A (test nhiều lượt) và B (UI gọi `run_request`) đang bị chặn bởi bug `session_id`. Merge vào `main` ngay sau Task 3, không giữ nhánh qua nhiều đợt (bài học ngày 13/9).
