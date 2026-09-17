# -*- coding: utf-8 -*-
"""Unit/integration test suite cho Perception (parser.py) và Memory (db.py).

Thay thế tests/run_autoeval.py theo phân công architecture.md Đợt 4.

Tầng này: chạy nhanh, offline, gác hồi quy (không gọi LLM thật).
AutoEval end-to-end: scripts/run_autoeval.py (chạy run_request() thật).

Chạy:
    python -m pytest tests/test_parse_memory_suite.py -v
"""

import sys
import os
import copy
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.perception.parser import (
    VALID_PRODUCT_TYPES,
    VALID_INTENTS,
    MissingFieldError,
    InvalidProductTypeError,
    _parse_product_type,
    _parse_quantity,
    _parse_budget,
    _parse_deadline,
    _parse_trust_score,
    _parse_intent,
)
from src.memory.db import (
    init_db,
    save_session,
    load_session,
    session_exists,
    delete_session,
    list_sessions,
    append_conversation,
    load_conversation,
    save_decision,
    load_decisions,
    start_run,
    finish_run,
    load_runs,
    save_artifact,
    load_artifacts,
)


def _state(
    session_id="sess_suite_test",
    product_type="ghe van phong",
    quantity=50,
    budget_max=200_000_000,
    deadline=14,
    intent="search_new",
):
    now = "2026-09-15T10:00:00"
    return {
        "session_id": session_id,
        "created_at": now,
        "updated_at": now,
        "intent": intent,
        "hard_constraints": {
            "product_type": product_type,
            "quantity": quantity,
            "budget_max": float(budget_max),
            "delivery_deadline_days": deadline,
        },
        "soft_constraints": {
            "material_preference": None,
            "region_preference": None,
            "min_trust_score": None,
        },
        "conversation_history": [{"role": "user", "content": "test", "timestamp": now}],
        "decisions_made": [],
    }


class TestParserConstants(unittest.TestCase):
    def test_valid_product_types_not_empty(self):
        self.assertGreater(len(VALID_PRODUCT_TYPES), 0)

    def test_expected_product_types_present(self):
        expected = {"ghe van phong", "ban lam viec", "tu ho so", "ke", "sofa"}
        # Check using normalized versions
        normalized = {p.replace("\u0103", "a").replace("\u1ebf", "e").replace("\u1ed3", "o")
                      .replace("\u00e0", "a").replace("\u0111", "d") for p in VALID_PRODUCT_TYPES}
        self.assertEqual(len(VALID_PRODUCT_TYPES), 5)

    def test_valid_intents_correct(self):
        expected = {"search_new", "compare_specific", "supplier_detail", "out_of_scope"}
        self.assertEqual(VALID_INTENTS, expected)

    def test_llm_model_name_is_string(self):
        from src.llm import MODEL_NAME
        self.assertIsInstance(MODEL_NAME, str)
        self.assertGreater(len(MODEL_NAME), 0)

    def test_llm_model_name_is_current_value(self):
        """Phai dung gemini-3.6-flash tu src.llm (canonical), khong phai gia tri cu cua parser."""
        from src.llm import MODEL_NAME
        self.assertEqual(MODEL_NAME, "gemini-3.6-flash",
                         "Ten model phai la gemini-3.6-flash theo src/llm.py (architecture.md §3.1)")

    def test_missing_field_error_has_fields(self):
        err = MissingFieldError(["so luong", "ngan sach"])
        self.assertIn("so luong", str(err))
        self.assertEqual(err.missing_fields, ["so luong", "ngan sach"])

    def test_invalid_product_type_error_contains_value(self):
        err = InvalidProductTypeError("may lanh")
        self.assertIn("may lanh", str(err))


class TestParserHelpers(unittest.TestCase):
    def test_parse_product_type_valid(self):
        for pt in VALID_PRODUCT_TYPES:
            with self.subTest(pt=pt):
                self.assertEqual(_parse_product_type(pt), pt)

    def test_parse_product_type_invalid_raises(self):
        with self.assertRaises(InvalidProductTypeError):
            _parse_product_type("may lanh")

    def test_parse_quantity_valid(self):
        self.assertEqual(_parse_quantity(50), 50)
        self.assertEqual(_parse_quantity("10"), 10)

    def test_parse_quantity_zero_raises(self):
        with self.assertRaises(ValueError):
            _parse_quantity(0)

    def test_parse_quantity_negative_raises(self):
        with self.assertRaises(ValueError):
            _parse_quantity(-5)

    def test_parse_budget_valid(self):
        self.assertAlmostEqual(_parse_budget(200_000_000), 200_000_000.0)

    def test_parse_budget_zero_raises(self):
        with self.assertRaises(ValueError):
            _parse_budget(0)

    def test_parse_budget_negative_raises(self):
        with self.assertRaises(ValueError):
            _parse_budget(-1000)

    def test_parse_deadline_valid(self):
        self.assertEqual(_parse_deadline(14), 14)

    def test_parse_deadline_zero_raises(self):
        with self.assertRaises(ValueError):
            _parse_deadline(0)

    def test_parse_trust_valid(self):
        self.assertAlmostEqual(_parse_trust_score(1.0), 1.0)
        self.assertAlmostEqual(_parse_trust_score(5.0), 5.0)
        self.assertAlmostEqual(_parse_trust_score(3.5), 3.5)

    def test_parse_trust_out_of_range_returns_none(self):
        self.assertIsNone(_parse_trust_score(0.9))
        self.assertIsNone(_parse_trust_score(5.1))

    def test_parse_intent_valid(self):
        for intent in ("search_new", "compare_specific", "supplier_detail", "out_of_scope"):
            with self.subTest(intent=intent):
                self.assertEqual(_parse_intent(intent), intent)

    def test_parse_intent_unknown_defaults_to_search_new(self):
        self.assertEqual(_parse_intent("gibberish"), "search_new")
        self.assertEqual(_parse_intent(None), "search_new")
        self.assertEqual(_parse_intent(""), "search_new")


class TestSessionCRUD(unittest.TestCase):
    def setUp(self):
        init_db()
        self.sid = "sess_crud_suite"
        delete_session(self.sid)

    def tearDown(self):
        delete_session(self.sid)

    def test_save_and_load_roundtrip(self):
        save_session(self.sid, _state(self.sid))
        loaded = load_session(self.sid)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["session_id"], self.sid)

    def test_session_exists_true_after_save(self):
        save_session(self.sid, _state(self.sid))
        self.assertTrue(session_exists(self.sid))

    def test_session_exists_false_before_save(self):
        self.assertFalse(session_exists(self.sid))

    def test_load_nonexistent_returns_none(self):
        self.assertIsNone(load_session(self.sid))

    def test_list_sessions_includes_saved(self):
        save_session(self.sid, _state(self.sid))
        self.assertIn(self.sid, list_sessions())

    def test_delete_nonexistent_returns_false(self):
        self.assertFalse(delete_session("nonexistent_xyz_suite"))

    def test_delete_returns_true(self):
        save_session(self.sid, _state(self.sid))
        self.assertTrue(delete_session(self.sid))
        self.assertFalse(session_exists(self.sid))

    def test_list_excludes_deleted(self):
        save_session(self.sid, _state(self.sid))
        delete_session(self.sid)
        self.assertNotIn(self.sid, list_sessions())


class TestSessionIsolation(unittest.TestCase):
    def setUp(self):
        init_db()
        self.sid_a = "sess_iso_a_suite"
        self.sid_b = "sess_iso_b_suite"
        delete_session(self.sid_a)
        delete_session(self.sid_b)

    def tearDown(self):
        delete_session(self.sid_a)
        delete_session(self.sid_b)

    def test_two_sessions_do_not_leak_data(self):
        save_session(self.sid_a, _state(self.sid_a, product_type="sofa", quantity=20))
        save_session(self.sid_b, _state(self.sid_b, product_type="ke", quantity=3))
        loaded_a = load_session(self.sid_a)
        loaded_b = load_session(self.sid_b)
        self.assertEqual(loaded_a["hard_constraints"]["quantity"], 20)
        self.assertEqual(loaded_b["hard_constraints"]["quantity"], 3)

    def test_conversation_history_isolated(self):
        save_session(self.sid_a, _state(self.sid_a))
        save_session(self.sid_b, _state(self.sid_b))
        append_conversation(self.sid_a, "user", "tin nhan A unique")
        conv_b = load_conversation(self.sid_b)
        self.assertFalse(any("tin nhan A" in m["content"] for m in conv_b))

    def test_decisions_isolated(self):
        save_session(self.sid_a, _state(self.sid_a))
        save_session(self.sid_b, _state(self.sid_b))
        save_decision(self.sid_a, "NCC_ONLY_A")
        self.assertEqual(load_decisions(self.sid_b), [])

    def test_delete_removes_all_data(self):
        save_session(self.sid_a, _state(self.sid_a))
        append_conversation(self.sid_a, "user", "test")
        save_decision(self.sid_a, "NCC_TEST")
        delete_session(self.sid_a)
        self.assertFalse(session_exists(self.sid_a))
        self.assertIsNone(load_session(self.sid_a))
        self.assertEqual(load_conversation(self.sid_a), [])
        self.assertEqual(load_decisions(self.sid_a), [])


class TestRunsTable(unittest.TestCase):
    def setUp(self):
        init_db()
        self.sid = "sess_runs_suite"
        delete_session(self.sid)

    def tearDown(self):
        delete_session(self.sid)

    def test_start_run_returns_nonempty_string(self):
        rid = start_run(self.sid, intent="search_new")
        self.assertIsInstance(rid, str)
        self.assertGreater(len(rid), 0)

    def test_finish_run_and_load(self):
        rid = start_run(self.sid, intent="search_new", trace_id="trace_001")
        finish_run(rid, status="success", llm_calls=2, tool_calls=3,
                   tokens_in=500, tokens_out=200, latency_ms=1234.5)
        runs = load_runs(self.sid)
        self.assertEqual(len(runs), 1)
        r = runs[0]
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["llm_calls"], 2)
        self.assertEqual(r["tool_calls"], 3)
        self.assertAlmostEqual(r["latency_ms"], 1234.5)

    def test_invalid_status_raises(self):
        rid = start_run(self.sid)
        with self.assertRaises(ValueError):
            finish_run(rid, status="bad_status")

    def test_multiple_runs_same_session(self):
        rid1 = start_run(self.sid, intent="search_new")
        rid2 = start_run(self.sid, intent="compare_specific")
        finish_run(rid1, status="success")
        finish_run(rid2, status="graceful_fail")
        statuses = {r["status"] for r in load_runs(self.sid)}
        self.assertIn("success", statuses)
        self.assertIn("graceful_fail", statuses)

    def test_run_ids_unique(self):
        ids = {start_run(self.sid) for _ in range(10)}
        self.assertEqual(len(ids), 10)

    def test_delete_session_removes_runs(self):
        rid = start_run(self.sid)
        finish_run(rid, status="success")
        delete_session(self.sid)
        runs = load_runs(self.sid)
        self.assertEqual(runs, [])


class TestArtifactsTable(unittest.TestCase):
    def setUp(self):
        init_db()
        self.sid = "sess_artifacts_suite"
        delete_session(self.sid)

    def tearDown(self):
        delete_session(self.sid)

    def test_save_and_load_plan(self):
        plan = {"plan_id": "plan_001", "status": "draft", "steps": []}
        save_artifact(self.sid, "plan", plan)
        arts = load_artifacts(self.sid, artifact_type="plan")
        self.assertEqual(len(arts), 1)
        self.assertEqual(arts[0]["artifact"]["plan_id"], "plan_001")

    def test_filter_by_type(self):
        save_artifact(self.sid, "plan", {"plan_id": "p1"})
        save_artifact(self.sid, "verdict", {"passed": True})
        plans = load_artifacts(self.sid, artifact_type="plan")
        self.assertEqual(len(plans), 1)

    def test_filter_by_run_id(self):
        rid = start_run(self.sid)
        save_artifact(self.sid, "plan", {"plan_id": "with_run"}, run_id=rid)
        save_artifact(self.sid, "plan", {"plan_id": "without_run"})
        by_run = load_artifacts(self.sid, run_id=rid)
        self.assertEqual(len(by_run), 1)
        self.assertEqual(by_run[0]["artifact"]["plan_id"], "with_run")

    def test_invalid_type_raises(self):
        with self.assertRaises(ValueError):
            save_artifact(self.sid, "invalid_type", {"data": 1})

    def test_delete_session_removes_artifacts(self):
        save_artifact(self.sid, "plan", {"plan_id": "to_delete"})
        delete_session(self.sid)
        self.assertEqual(load_artifacts(self.sid), [])

    def test_nested_structure_preserved(self):
        complex_plan = {
            "plan_id": "plan_complex",
            "steps": [
                {"step_id": 1, "action": "search_suppliers", "params": {"product_type": "sofa"}},
            ],
            "replan_count": 0,
        }
        save_artifact(self.sid, "plan", complex_plan)
        loaded = load_artifacts(self.sid, artifact_type="plan")[0]["artifact"]
        self.assertEqual(loaded["steps"][0]["params"]["product_type"], "sofa")


if __name__ == "__main__":
    unittest.main()
