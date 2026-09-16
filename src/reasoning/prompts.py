"""Prompt contract owned by Reasoning for the final response nodes.

The LangGraph/LLM wiring belongs to the orchestration layer.  Keeping prompt
construction here lets that layer consume only a recommendation that already
passed deterministic verification.
"""

from __future__ import annotations

import json
from typing import Any


RESPONSE_SYSTEM_PROMPT = """Bạn là trợ lý phân tích mua sắm nội thất.

Chỉ dùng dữ liệu trong VERIFIED_CONTEXT; không bổ sung kiến thức, giá hoặc thông số
từ trí nhớ. Mọi con số về nhà cung cấp phải ghi kèm MaNCC và nguon_url. Nếu field nằm
trong simulated_fields, phải nói rõ đó là dữ liệu mô phỏng dùng cho bài tập, không phải
dữ liệu thị trường đã xác thực.

Trình bày ngắn gọn: phương án đề xuất, lý do đáp ứng ràng buộc cứng, trade-off của
ưu tiên mềm, và chiến lược đàm phán. Không tuyên bố đã đặt/chốt đơn. Chỉ mời người dùng
xác nhận; hành động xác nhận phải đi qua confirm_gate của hệ thống.
"""


LIMITS_SYSTEM_PROMPT = """Bạn là trợ lý mua sắm nội thất.

Yêu cầu hiện nằm ngoài phạm vi catalog của hệ thống. Giải thích giới hạn một cách ngắn
gọn, không gọi tool, không bịa nhà cung cấp hay thông số. Nêu catalog được hỗ trợ nếu
thông tin đó có trong LIMITS_CONTEXT và mời người dùng diễn đạt lại yêu cầu phù hợp.
"""


def build_verified_response_messages(
    recommendation: dict[str, Any],
    verdict: dict[str, Any],
) -> list[dict[str, str]]:
    """Build model messages only for a fully verified recommendation."""

    if not isinstance(verdict, dict) or verdict.get("passed") is not True:
        raise ValueError("cannot build a recommendation response from a failed verdict")

    claims = verdict.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("verified verdict must contain evidence claims")
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("every response claim must be a dictionary")
        evidence = claim.get("evidence")
        if claim.get("supported") is not True or not isinstance(evidence, dict) or not evidence.get("nguon_url"):
            raise ValueError("every response claim must be supported and cite nguon_url")

    context = {
        "recommendation": recommendation,
        "verified_claims": claims,
    }
    return [
        {"role": "system", "content": RESPONSE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "VERIFIED_CONTEXT:\n" + json.dumps(context, ensure_ascii=False, default=str),
        },
    ]


def build_limits_messages(
    user_request: str,
    supported_catalog: list[str],
) -> list[dict[str, str]]:
    """Build messages for out-of-scope requests without supplier evidence."""

    context = {"user_request": user_request, "supported_catalog": supported_catalog}
    return [
        {"role": "system", "content": LIMITS_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "LIMITS_CONTEXT:\n" + json.dumps(context, ensure_ascii=False),
        },
    ]
