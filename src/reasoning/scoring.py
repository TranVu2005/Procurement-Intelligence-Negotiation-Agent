"""Deterministic supplier filtering, leverage scoring and explanations.

The LLM may phrase a final response, but it must not invent the numeric decision.
Every score and rejection produced here is traceable to state and tool output.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from typing import Any


WEIGHTS = {
    "price": 0.30,
    "moq": 0.15,
    "delivery": 0.20,
    "warranty": 0.15,
    "trust": 0.20,
}


class ScoringError(ValueError):
    """Raised when required evidence is absent or malformed."""


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.replace("đ", "d").replace("Đ", "D")
    value = unicodedata.normalize("NFD", value)
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return " ".join(value.replace("_", " ").casefold().split())


def _number(record: dict[str, Any], field: str) -> float:
    value = record.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ScoringError(f"missing or invalid numeric evidence: {field}")
    return float(value)


def _clip(value: float) -> float:
    return max(0.0, min(100.0, value))


def score_breakdown(supplier: dict[str, Any], hard_constraints: dict[str, Any]) -> dict[str, float | None]:
    """Return transparent 0-100 component scores.

    A missing optional trust/warranty value remains ``None``. The final score
    re-normalizes available weights instead of silently inventing a value.
    """

    quantity = _number(hard_constraints, "quantity")
    budget = _number(hard_constraints, "budget_max")
    deadline = _number(hard_constraints, "delivery_deadline_days")
    total_price = _number(supplier, "total_price")
    moq = _number(supplier, "MOQ")
    delivery = _number(supplier, "ThoiGianGiao")
    if quantity <= 0 or budget <= 0 or deadline <= 0 or moq <= 0:
        raise ScoringError("quantity, budget, deadline and MOQ must be positive")

    # Price headroom: spending the full budget gives 0; larger savings improve
    # buyer leverage. Hard filtering is responsible for rejecting over-budget bids.
    price_score = _clip((budget - total_price) / budget * 100)

    # An order exactly at MOQ gets 50. Reaching 2x MOQ gives the maximum,
    # representing more room to negotiate a volume discount.
    moq_score = _clip((quantity / moq) * 50)

    # Meeting the deadline exactly gets 50. Earlier delivery increases the score.
    delivery_score = _clip(50 + ((deadline - delivery) / deadline) * 50)

    warranty_value = supplier.get("BaoHanh")
    warranty_score = None
    if isinstance(warranty_value, (int, float)) and not isinstance(warranty_value, bool):
        warranty_score = _clip(float(warranty_value) / 36 * 100)

    trust_value = supplier.get("DiemUyTin")
    trust_score = None
    if isinstance(trust_value, (int, float)) and not isinstance(trust_value, bool):
        trust_score = _clip(float(trust_value) / 5 * 100)

    return {
        "price": round(price_score, 2),
        "moq": round(moq_score, 2),
        "delivery": round(delivery_score, 2),
        "warranty": None if warranty_score is None else round(warranty_score, 2),
        "trust": None if trust_score is None else round(trust_score, 2),
    }


def leverage_score(supplier: dict[str, Any], hard_constraints: dict[str, Any]) -> float:
    """Calculate a reproducible 0-100 score using the agreed five factors."""

    breakdown = score_breakdown(supplier, hard_constraints)
    available_weight = sum(WEIGHTS[name] for name, value in breakdown.items() if value is not None)
    if available_weight == 0:
        raise ScoringError("no evidence is available for leverage scoring")
    weighted_score = sum(
        WEIGHTS[name] * value
        for name, value in breakdown.items()
        if value is not None
    ) / available_weight
    return round(weighted_score, 2)


def merge_supplier_evidence(
    supplier_details: Iterable[dict[str, Any]],
    price_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Join C's detail and price outputs by ``MaNCC`` without losing evidence."""

    comparisons = price_result.get("comparisons") if isinstance(price_result, dict) else None
    if not isinstance(comparisons, list):
        raise ScoringError("compare_price output must contain a comparisons list")
    price_by_id = {
        item.get("MaNCC"): item
        for item in comparisons
        if isinstance(item, dict) and item.get("MaNCC")
    }

    merged = []
    for detail in supplier_details:
        if not isinstance(detail, dict):
            continue
        supplier_id = detail.get("MaNCC")
        record = dict(detail)
        comparison = price_by_id.get(supplier_id)
        if comparison:
            record.update(comparison)
        merged.append(record)
    return merged


def hard_constraint_violations(
    supplier: dict[str, Any],
    hard_constraints: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return machine-readable reasons why a supplier is not eligible."""

    violations: list[dict[str, Any]] = []
    quantity = hard_constraints["quantity"]
    product_type = hard_constraints["product_type"]
    budget = hard_constraints["budget_max"]
    deadline = hard_constraints["delivery_deadline_days"]

    def add(code: str, field: str, actual: Any, required: Any) -> None:
        violations.append({"code": code, "field": field, "actual": actual, "required": required})

    if _normalize(supplier.get("LoaiSanPham")) != _normalize(product_type):
        add("product_type_mismatch", "LoaiSanPham", supplier.get("LoaiSanPham"), product_type)

    moq = supplier.get("MOQ")
    if not isinstance(moq, (int, float)) or isinstance(moq, bool):
        add("missing_moq_evidence", "MOQ", moq, "numeric value")
    elif quantity < moq:
        add("quantity_below_moq", "MOQ", quantity, f">= {moq}")

    stock = supplier.get("TonKho")
    if not isinstance(stock, (int, float)) or isinstance(stock, bool):
        add("missing_stock_evidence", "TonKho", stock, f">= {quantity}")
    elif stock < quantity:
        add("stock_below_quantity", "TonKho", stock, f">= {quantity}")

    total_price = supplier.get("total_price")
    if not isinstance(total_price, (int, float)) or isinstance(total_price, bool):
        add("missing_price_evidence", "total_price", total_price, f"<= {budget}")
    elif total_price > budget:
        add("budget_exceeded", "total_price", total_price, f"<= {budget}")

    delivery = supplier.get("ThoiGianGiao")
    if not isinstance(delivery, (int, float)) or isinstance(delivery, bool):
        add("missing_delivery_evidence", "ThoiGianGiao", delivery, f"<= {deadline}")
    elif delivery > deadline:
        add("delivery_deadline_unmet", "ThoiGianGiao", delivery, f"<= {deadline}")

    if supplier.get("error"):
        add("tool_result_error", "error_type", supplier.get("error_type"), "successful evidence")
    return violations


def filter_hard_constraints(
    suppliers: Iterable[dict[str, Any]],
    hard_constraints: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Partition candidates into eligible and rejected lists with evidence."""

    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for supplier in suppliers:
        violations = hard_constraint_violations(supplier, hard_constraints)
        if violations:
            rejected.append({
                "supplier_id": supplier.get("MaNCC"),
                "violations": violations,
                "evidence": supplier,
            })
        else:
            eligible.append(dict(supplier))
    return {"eligible": eligible, "rejected": rejected}


def explain_score(
    supplier: dict[str, Any],
    state: dict[str, Any],
    breakdown: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    """Explain numeric evidence and soft-constraint trade-offs in Vietnamese."""

    hard = state["hard_constraints"]
    soft = state.get("soft_constraints") or {}
    breakdown = breakdown or score_breakdown(supplier, hard)
    quantity = hard["quantity"]
    budget = hard["budget_max"]
    deadline = hard["delivery_deadline_days"]

    strengths = [
        f"Tổng giá {supplier['total_price']:,.0f} VND, còn dư {budget - supplier['total_price']:,.0f} VND so với ngân sách.",
        f"Đơn {quantity} sản phẩm so với MOQ {supplier['MOQ']}.",
        f"Giao trong {supplier['ThoiGianGiao']} ngày, sớm hơn deadline {deadline - supplier['ThoiGianGiao']} ngày.",
    ]
    trade_offs: list[str] = []

    material = soft.get("material_preference")
    if material and _normalize(supplier.get("ChatLieu")) != _normalize(material):
        trade_offs.append(
            f"Không khớp chất liệu ưu tiên '{material}' (thực tế: '{supplier.get('ChatLieu')}')."
        )
    region = soft.get("region_preference")
    if region and _normalize(supplier.get("KhuVuc")) != _normalize(region):
        trade_offs.append(
            f"Không khớp khu vực ưu tiên '{region}' (thực tế: '{supplier.get('KhuVuc')}')."
        )
    min_trust = soft.get("min_trust_score")
    trust = supplier.get("DiemUyTin")
    if min_trust is not None:
        if trust is None:
            trade_offs.append("Chưa có dữ liệu điểm uy tín; hệ thống không tự điền giá trị.")
        elif trust < min_trust:
            trade_offs.append(f"Điểm uy tín {trust} thấp hơn mức ưu tiên {min_trust}.")
    if supplier.get("BaoHanh") is None:
        trade_offs.append("Chưa có dữ liệu bảo hành; trọng số này được bỏ khỏi phép tính.")

    return {
        "strengths": strengths,
        "trade_offs": trade_offs,
        "score_breakdown": breakdown,
    }


def rank_suppliers(
    suppliers: Iterable[dict[str, Any]],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Score eligible suppliers and return best-first, with deterministic ties."""

    ranked = []
    for supplier in suppliers:
        breakdown = score_breakdown(supplier, state["hard_constraints"])
        item = dict(supplier)
        item["leverage_score"] = leverage_score(supplier, state["hard_constraints"])
        item["explanation"] = explain_score(supplier, state, breakdown)
        ranked.append(item)
    return sorted(ranked, key=lambda item: (-item["leverage_score"], str(item.get("MaNCC", ""))))


def detect_evidence_conflicts(suppliers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag conflicting records that claim the same supplier and product.

    A conflict is surfaced for verification instead of choosing one value and
    reporting it as certain. Different products from the same supplier are not
    considered a conflict.
    """

    groups: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
    for supplier in suppliers:
        key = (_normalize(supplier.get("TenNCC")), _normalize(supplier.get("LoaiSanPham")))
        groups.setdefault(key, []).append(supplier)

    conflicts = []
    checked_fields = ("Gia", "MOQ", "TonKho", "ThoiGianGiao", "BaoHanh", "DiemUyTin")
    for (_name, _product), records in groups.items():
        if len(records) < 2:
            continue
        differing = {
            field: {record.get(field) for record in records}
            for field in checked_fields
            if len({record.get(field) for record in records}) > 1
        }
        if differing:
            conflicts.append({
                "supplier_name": records[0].get("TenNCC"),
                "product_type": records[0].get("LoaiSanPham"),
                "supplier_ids": [record.get("MaNCC") for record in records],
                "differing_fields": {
                    field: sorted(values, key=lambda value: (value is None, str(value)))
                    for field, values in differing.items()
                },
                "resolution": "Cần xác minh nguồn/bản ghi trước khi khuyến nghị.",
            })
    return conflicts


def evaluate_candidates(
    state: dict[str, Any],
    supplier_details: Iterable[dict[str, Any]],
    price_result: dict[str, Any],
) -> dict[str, Any]:
    """Run the complete deterministic B decision pipeline after C's tool calls."""

    evidence = merge_supplier_evidence(supplier_details, price_result)
    filtered = filter_hard_constraints(evidence, state["hard_constraints"])
    conflicts = detect_evidence_conflicts(filtered["eligible"])
    ranked = rank_suppliers(filtered["eligible"], state)
    status = "evidence_conflict" if conflicts else ("success" if ranked else "no_eligible_supplier")
    return {
        "status": status,
        "ranked_suppliers": ranked,
        "rejected_suppliers": filtered["rejected"],
        "evidence_conflicts": conflicts,
        "recommended_supplier_id": ranked[0]["MaNCC"] if ranked and not conflicts else None,
    }
