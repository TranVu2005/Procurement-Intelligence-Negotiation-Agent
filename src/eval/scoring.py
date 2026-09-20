"""Cham diem AutoEval. Owner: Nguoi C.

Runner doc `oracle` cua tung case va cham bang mot ham chung. Them case moi
chi la them mot dong JSONL, khong sua code - day la thu rubric phat khi thay
`if case_id == ...` (architecture.md muc 5.1, 5.2).
"""

import re
import statistics
from typing import Any

METRIC_NAMES = (
    "task_success_rate",
    "constraint_satisfaction_rate",
    "tool_call_success_rate",
    "citation_correctness",
    "failure_recovery_rate",
)

# Trang thai duoc coi la "ket thuc co kiem soat" khi tinh Failure Recovery Rate
_RECOVERED_STATUSES = {"success", "graceful_fail", "needs_input", "needs_confirmation"}


def _called_tools(final: dict) -> list[str]:
    """Tool that su da duoc GOI. 'blocked' la bi chan co chu dich, khong tinh."""
    return [e.get("tool") for e in (final.get("tool_results") or [])
            if e.get("status") != "blocked"]


def _subject_record(final: dict) -> dict:
    """Ban ghi ma cau tra loi dua vao: ranked[0], hoac candidate duy nhat con lai."""
    ranked = final.get("ranked") or []
    if ranked:
        return ranked[0]
    candidates = final.get("candidates") or []
    return candidates[0] if candidates else {}


def _check_constraints(constraints: dict, record: dict, final: dict) -> list[str]:
    failures = []
    quantity = ((final.get("req") or {}).get("hard_constraints") or {}).get("quantity")

    total = record.get("total_price")
    if "total_price_lte" in constraints:
        if not isinstance(total, (int, float)) or total > constraints["total_price_lte"]:
            failures.append(f"total_price={total} vuot {constraints['total_price_lte']}")

    delivery = record.get("ThoiGianGiao")
    if "delivery_lte" in constraints:
        if not isinstance(delivery, (int, float)) or delivery > constraints["delivery_lte"]:
            failures.append(f"ThoiGianGiao={delivery} vuot {constraints['delivery_lte']}")

    if constraints.get("quantity_gte_moq"):
        moq = record.get("MOQ")
        if quantity is not None and isinstance(moq, (int, float)) and quantity < moq:
            failures.append(f"quantity={quantity} duoi MOQ={moq}")
        elif record.get("meets_moq") is False:
            failures.append("meets_moq=False")
    return failures


def _evidence_index(final: dict) -> list[dict]:
    """Gom moi ban ghi tung xuat hien trong tool_results de doi chieu claim."""
    records = []
    for entry in final.get("tool_results") or []:
        result = entry.get("result")
        if not isinstance(result, dict):
            continue
        if "suppliers" in result:
            records.extend(r for r in result["suppliers"] if isinstance(r, dict))
        elif "comparisons" in result:
            records.extend(r for r in result["comparisons"] if isinstance(r, dict))
        elif result.get("MaNCC"):
            records.append(result)
    return records


def _claim_is_grounded(claim: dict, records: list[dict]) -> bool:
    """Claim dung khi co ban ghi cung MaNCC mang dung field va dung gia tri."""
    evidence = claim.get("evidence") or {}
    supplier_id, field = evidence.get("MaNCC"), evidence.get("field")
    if not supplier_id or not field:
        return False
    for record in records:
        if record.get("MaNCC") != supplier_id or field not in record:
            continue
        if claim.get("value") is None or record[field] == claim["value"]:
            return True
    return False


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


def grade_case(case: dict, final: dict) -> dict:
    """Cham 1 case theo oracle khai bao. Tra ve ket qua + cac tin hieu de tong hop."""
    oracle: dict[str, Any] = case.get("oracle") or {}
    failures: list[str] = []
    called = _called_tools(final)

    expected_status = oracle.get("expect_status")
    if expected_status and final.get("status") != expected_status:
        failures.append(f"expect_status={expected_status} nhung nhan {final.get('status')}")

    if oracle.get("must_reach_intent") and final.get("intent") != oracle["must_reach_intent"]:
        failures.append(
            f"must_reach_intent={oracle['must_reach_intent']} nhung nhan {final.get('intent')}")

    for tool in oracle.get("must_call_tools") or []:
        if tool not in called:
            failures.append(f"must_call_tools: thieu {tool}")

    for tool in oracle.get("must_not_call_tools") or []:
        if tool in called:
            failures.append(f"must_not_call_tools: da goi {tool}")

    if "max_replan" in oracle and final.get("replan_count", 0) > oracle["max_replan"]:
        failures.append(f"replan_count={final.get('replan_count')} vuot {oracle['max_replan']}")

    constraints = oracle.get("constraints") or {}
    constraint_failures = _check_constraints(constraints, _subject_record(final), final) \
        if constraints else []
    failures.extend(constraint_failures)

    records = _evidence_index(final)
    claims = (final.get("verdict") or {}).get("claims") or []
    grounded = sum(1 for claim in claims if _claim_is_grounded(claim, records))

    if oracle.get("must_cite"):
        if not claims:
            failures.append("must_cite: verdict.claims rong")
        elif grounded < len(claims):
            failures.append(f"must_cite: {len(claims) - grounded} claim khong truy duoc nguon")

    if oracle.get("must_explain_failure") and not (final.get("answer") or "").strip():
        failures.append("must_explain_failure: khong co cau tra loi giai thich")

    if oracle.get("must_state_limits") and "pham vi" not in (final.get("answer") or "").lower():
        failures.append("must_state_limits: cau tra loi khong neu gioi han he thong")

    if oracle.get("must_ask_user") and final.get("status") != "needs_input":
        failures.append(f"must_ask_user: status={final.get('status')}, khong hoi lai nguoi dung")

    if oracle.get("must_not_invent_numbers"):
        invented = invented_numbers(final)
        if invented:
            failures.append(f"must_not_invent_numbers: so khong truy duoc {invented}")

    tool_entries = final.get("tool_results") or []
    counted = [e for e in tool_entries if e.get("status") != "blocked"]
    return {
        "id": case.get("id"),
        "category": case.get("category"),
        "passed": not failures,
        "failures": failures,
        "signals": {
            "has_constraints": bool(constraints),
            "constraints_ok": not constraint_failures,
            "tool_calls": len(counted),
            "tool_calls_ok": sum(1 for e in counted if e.get("status") == "ok"),
            "claims_total": len(claims),
            "claims_grounded": grounded,
            "injected": bool(case.get("inject")),
            "recovered": final.get("status") in _RECOVERED_STATUSES,
            "llm_calls": final.get("llm_calls", 0),
            "latency_ms": final.get("latency_ms"),
        },
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    """None khi khong co case nao ap dung - khac han voi 0.0 (co ma sai het)."""
    return round(numerator / denominator, 4) if denominator else None


def aggregate(results: list[dict]) -> dict:
    """Tong hop 5 metric bat buoc (architecture.md muc 5.3)."""
    signals = [r["signals"] for r in results]

    with_constraints = [s for s in signals if s["has_constraints"]]
    injected = [s for s in signals if s["injected"]]

    metrics = {
        "task_success_rate": _ratio(sum(1 for r in results if r["passed"]), len(results)),
        "constraint_satisfaction_rate": _ratio(
            sum(1 for s in with_constraints if s["constraints_ok"]), len(with_constraints)),
        "tool_call_success_rate": _ratio(
            sum(s["tool_calls_ok"] for s in signals), sum(s["tool_calls"] for s in signals)),
        "citation_correctness": _ratio(
            sum(s["claims_grounded"] for s in signals), sum(s["claims_total"] for s in signals)),
        "failure_recovery_rate": _ratio(
            sum(1 for s in injected if s["recovered"]), len(injected)),
    }

    latencies = sorted(s["latency_ms"] for s in signals if s["latency_ms"] is not None)
    return {
        "total_cases": len(results),
        "metrics": metrics,
        "avg_llm_calls": _ratio(sum(s["llm_calls"] for s in signals), len(signals)),
        "latency_p50_ms": latencies[len(latencies) // 2] if latencies else None,
        "latency_p95_ms": latencies[int(len(latencies) * 0.95)] if latencies else None,
        "failed_cases": [{"id": r["id"], "category": r["category"], "failures": r["failures"]}
                         for r in results if not r["passed"]],
    }


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
