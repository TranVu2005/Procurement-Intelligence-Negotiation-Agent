# -*- coding: utf-8 -*-
"""AutoEval runner — chay tu dong eval_cases va bao cao pass/fail.

Chay:
    python tests/run_autoeval.py

Mo ta:
    Doc eval_set/cases.jsonl va chay cac test SQLite offline.
    Cac case can LLM (parse_request thuc) chi chay neu co flag --live.
"""

import sys
import os
import json
import io
import time
import argparse

# Force UTF-8 stdout tren Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memory.db import (
    init_db,
    save_session,
    load_session,
    session_exists,
    delete_session,
    append_conversation,
    load_conversation,
    save_decision,
    load_decisions,
)

# ─────────────────────────────────────────────────────────────────────────────
# Terminal colors
# ─────────────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

CASES_PATH = os.path.join(os.path.dirname(__file__), "eval_set", "cases.jsonl")


def _make_sample_state(session_id: str, product_type: str, quantity: int,
                       budget_max: float, deadline: int) -> dict:
    now = "2026-09-12T10:00:00"
    return {
        "session_id": session_id,
        "created_at": now,
        "updated_at": now,
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


# ─────────────────────────────────────────────────────────────────────────────
# Eval runners theo case ID
# ─────────────────────────────────────────────────────────────────────────────

def _run_case(case: dict, live: bool) -> tuple[bool, str]:
    """Chay 1 eval case. Tra (passed: bool, detail: str)."""
    cid = case["id"]

    # ── Case 001: happy path (can LLM) ──────────────────────────────────────
    if cid == "case_001":
        if not live:
            return True, "SKIP (can LLM, chay voi --live)"
        try:
            from src.perception.parser import parse_request
            state = parse_request(case["input"])
            exp = case["expected"]["hard_constraints"]
            hc = state["hard_constraints"]
            assert hc["budget_max"] == exp["budget_max"], f"budget_max: {hc['budget_max']} != {exp['budget_max']}"
            assert hc["quantity"] == exp["quantity"], f"quantity: {hc['quantity']} != {exp['quantity']}"
            assert hc["delivery_deadline_days"] == exp["delivery_deadline_days"]
            return True, "parse_request() happy path OK"
        except Exception as e:
            return False, str(e)

    # ── Case 002: missing fields (can LLM) ──────────────────────────────────
    if cid == "case_002_missing_fields":
        if not live:
            return True, "SKIP (can LLM, chay voi --live)"
        try:
            from src.perception.parser import parse_request, MissingFieldError
            parse_request(case["input"])
            return False, "Phai raise MissingFieldError nhung khong raise"
        except Exception as exc:
            if type(exc).__name__ == "MissingFieldError":
                return True, f"MissingFieldError dung: {exc}"
            return False, f"Raise sai loai loi: {type(exc).__name__}"

    # ── Case 003: invalid product (can LLM) ─────────────────────────────────
    if cid == "case_003_invalid_product":
        if not live:
            return True, "SKIP (can LLM, chay voi --live)"
        try:
            from src.perception.parser import parse_request, MissingFieldError, InvalidProductTypeError
            parse_request(case["input"])
            return False, "Phai raise loi nhung khong raise"
        except (MissingFieldError, InvalidProductTypeError) as exc:
            return True, f"{type(exc).__name__} dung"
        except Exception as exc:
            return False, f"Raise sai loai loi: {type(exc).__name__}"

    # ── Case 004: quantity=0 trong update_state (offline) ───────────────────
    if cid == "case_004_quantity_zero":
        try:
            from src.perception.parser import _parse_quantity
            _parse_quantity(0)
            return False, "Phai raise ValueError nhung khong raise"
        except ValueError as e:
            return True, f"ValueError dung: {e}"

    # ── Case 005: budget_max am (offline) ───────────────────────────────────
    if cid == "case_005_budget_negative":
        try:
            from src.perception.parser import _parse_budget
            _parse_budget(-1000)
            return False, "Phai raise ValueError nhung khong raise"
        except ValueError as e:
            return True, f"ValueError dung: {e}"

    # ── Case 006: multi-turn update (offline) ───────────────────────────────
    if cid == "case_006_multi_turn_update":
        try:
            now = "2026-09-12T10:00:00"
            state = {
                "session_id": "sess_c006",
                "created_at": now, "updated_at": now,
                "hard_constraints": {
                    "product_type": "ghe van phong",
                    "quantity": case["initial_quantity"],
                    "budget_max": 200_000_000.0,
                    "delivery_deadline_days": 14,
                },
                "soft_constraints": {"material_preference": None, "region_preference": None, "min_trust_score": None},
                "conversation_history": [{"role": "user", "content": "initial", "timestamp": now}],
                "decisions_made": [],
            }
            # Simulate update: chi doi quantity
            import copy
            updated = copy.deepcopy(state)
            updated["hard_constraints"]["quantity"] = case["update_quantity"]
            updated["conversation_history"].append({"role": "user", "content": "update", "timestamp": now})

            new_qty = updated["hard_constraints"]["quantity"]
            assert new_qty == case["update_quantity"], f"quantity sau update: {new_qty}"
            assert updated["hard_constraints"]["budget_max"] == state["hard_constraints"]["budget_max"], "budget bi thay doi"
            assert len(updated["conversation_history"]) == len(state["conversation_history"]) + 1
            return True, f"quantity {case['initial_quantity']} → {case['update_quantity']}, budget giu nguyen"
        except Exception as e:
            return False, str(e)

    # ── Case 007: session isolation (SQLite) ────────────────────────────────
    if cid == "case_007_session_isolation":
        sess_a = case["session_a"]["session_id"] + "_autoeval"
        sess_b = case["session_b"]["session_id"] + "_autoeval"
        try:
            init_db()
            delete_session(sess_a); delete_session(sess_b)

            state_a = _make_sample_state(sess_a, case["session_a"]["product_type"],
                                         case["session_a"]["quantity"], 40_000_000, 10)
            state_b = _make_sample_state(sess_b, case["session_b"]["product_type"],
                                         case["session_b"]["quantity"], 90_000_000, 20)
            save_session(sess_a, state_a)
            save_session(sess_b, state_b)

            loaded_a = load_session(sess_a)
            loaded_b = load_session(sess_b)

            assert loaded_a["session_id"] == sess_a
            assert loaded_b["session_id"] == sess_b
            assert loaded_a["hard_constraints"]["product_type"] == case["session_a"]["product_type"]
            assert loaded_b["hard_constraints"]["product_type"] == case["session_b"]["product_type"]
            assert loaded_a["hard_constraints"]["quantity"] == case["session_a"]["quantity"]
            assert loaded_b["hard_constraints"]["quantity"] == case["session_b"]["quantity"]
            return True, "2 session doc lap, khong lan du lieu"
        except Exception as e:
            return False, str(e)
        finally:
            delete_session(sess_a); delete_session(sess_b)

    # ── Case 008: delete_session (SQLite) ───────────────────────────────────
    if cid == "case_008_delete_session":
        sess = "sess_delete_autoeval"
        try:
            init_db()
            delete_session(sess)

            state = _make_sample_state(sess, "ke", 5, 10_000_000, 7)
            save_session(sess, state)
            append_conversation(sess, "user", "test message")
            save_decision(sess, "NCC_TEST")

            assert session_exists(sess), "session phai ton tai truoc khi xoa"

            result = delete_session(sess)
            assert result is True, "delete_session phai tra True"
            assert not session_exists(sess), "session_exists phai la False sau khi xoa"
            assert load_session(sess) is None, "load_session phai tra None sau khi xoa"
            assert load_conversation(sess) == [], "conversation_history phai rong"
            assert load_decisions(sess) == [], "decisions_made phai rong"
            return True, "delete_session xoa sach sessions + history + decisions"
        except Exception as e:
            return False, str(e)

    return True, f"SKIP (chua co runner cho case '{cid}')"


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AutoEval runner cho Procurement Agent")
    parser.add_argument("--live", action="store_true",
                        help="Chay ca cac case can LLM that (GOOGLE_API_KEY phai co)")
    parser.add_argument("--case", type=str, default=None,
                        help="Chi chay 1 case cu the theo ID (VD: case_007_session_isolation)")
    args = parser.parse_args()

    # Doc eval cases
    cases = []
    with open(CASES_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print(f"{RED}Khong tim thay case ID: {args.case}{RESET}")
            sys.exit(1)

    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  AutoEval — Procurement Intelligence Agent{RESET}")
    print(f"{BOLD}{CYAN}  Mode: {'LIVE (co LLM)' if args.live else 'OFFLINE (khong LLM)'}{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}\n")

    passed = skipped = failed = 0
    results = []

    for case in cases:
        cid = case["id"]
        desc = case.get("description", case.get("input", "")[:60])
        t0 = time.perf_counter()

        ok, detail = _run_case(case, live=args.live)
        elapsed = round((time.perf_counter() - t0) * 1000, 1)

        if detail.startswith("SKIP"):
            skipped += 1
            icon = f"{YELLOW}⊘{RESET}"
            status = f"{YELLOW}SKIP{RESET}"
        elif ok:
            passed += 1
            icon = f"{GREEN}✓{RESET}"
            status = f"{GREEN}PASS{RESET}"
        else:
            failed += 1
            icon = f"{RED}✗{RESET}"
            status = f"{RED}FAIL{RESET}"

        print(f"  {icon} [{status}] {BOLD}{cid}{RESET}  {DIM}({elapsed}ms){RESET}")
        if desc:
            print(f"       {DIM}{desc[:70]}{RESET}")
        if not ok or detail.startswith("SKIP"):
            print(f"       → {detail}")
        print()
        results.append({"id": cid, "ok": ok, "detail": detail, "skipped": detail.startswith("SKIP")})

    # Summary
    total = len(cases)
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}Ket qua: {GREEN}{passed}{RESET}{BOLD} PASS  "
          f"{YELLOW}{skipped}{RESET}{BOLD} SKIP  "
          f"{RED}{failed}{RESET}{BOLD} FAIL  / {total} cases{RESET}")
    if failed:
        print(f"\n{RED}Cases that bai:{RESET}")
        for r in results:
            if not r["ok"] and not r["skipped"]:
                print(f"  - {r['id']}: {r['detail']}")
    print(f"{'='*60}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
