"""Perception module — parse natural-language procurement request into structured state.

Owner: Nguoi A

State schema contract (SYSTEM-RULES.md §2.1):
{
    "session_id":   str,                    # UUID
    "created_at":   str,                    # ISO 8601
    "updated_at":   str,                    # ISO 8601
    "intent":       str,                    # search_new | compare_specific | supplier_detail | out_of_scope
    "hard_constraints": {
        "product_type":           str,      # enum: xem VALID_PRODUCT_TYPES
        "quantity":               int,      # > 0
        "budget_max":             float,    # VND, > 0
        "delivery_deadline_days": int       # > 0
    },
    "soft_constraints": {
        "material_preference":  str | None,
        "region_preference":    str | None,
        "min_trust_score":      float | None  # 1–5
    },
    "conversation_history": [...],
    "decisions_made": [...]
}

Quy tắc:
- Không hard-code input mẫu vào logic xử lý (SYSTEM-RULES §3).
- Nếu field bắt buộc còn thiếu → raise MissingFieldError để agent hỏi lại người dùng.
  Ngoại lệ: intent=compare_specific hoặc supplier_detail chỉ cần MaNCC, không cần hard constraints đầy đủ.
- Nếu product_type không nằm trong enum → raise InvalidProductTypeError.
- Dùng src.llm.get_llm() (JSON mode) — không regex, không keyword matching cứng.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Literal

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from src.llm import get_llm, usage_of

load_dotenv()

# ---------------------------------------------------------------------------
# Hằng số
# ---------------------------------------------------------------------------

VALID_PRODUCT_TYPES = {
    "ghế văn phòng",
    "bàn làm việc",
    "tủ hồ sơ",
    "kệ",
    "sofa",
}

VALID_INTENTS = frozenset({"search_new", "compare_specific", "supplier_detail", "out_of_scope"})

# Intent không cần full hard constraints (chỉ cần MaNCC hoặc thông tin cụ thể)
_INTENT_SKIP_HARD_VALIDATION: frozenset[str] = frozenset({"compare_specific", "supplier_detail"})

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class MissingFieldError(ValueError):
    """Raise khi input thiếu field bắt buộc (hard constraint).

    Agent nên bắt lỗi này và hỏi lại người dùng thay vì tự điền ngầm.
    """

    def __init__(self, missing_fields: list[str], partial_state: dict | None = None):
        self.missing_fields = missing_fields
        self.partial_state = partial_state
        super().__init__(
            f"Thiếu thông tin bắt buộc: {', '.join(missing_fields)}. "
            "Vui lòng cung cấp thêm để tiếp tục."
        )


class InvalidProductTypeError(ValueError):
    """Raise khi product_type không thuộc enum hợp lệ."""

    def __init__(self, value: str):
        super().__init__(
            f"Loại sản phẩm '{value}' không có trong danh mục. "
            f"Chỉ hỗ trợ: {', '.join(sorted(VALID_PRODUCT_TYPES))}."
        )


# ---------------------------------------------------------------------------
# Prompt — gom intent vào cùng lần gọi LLM (architecture.md §3.1)
# ---------------------------------------------------------------------------

_EXTRACT_SYSTEM_PROMPT = """Bạn là trợ lý trích xuất thông tin từ yêu cầu mua sắm nội thất.

Nhiệm vụ: Đọc câu yêu cầu và trích xuất thông tin vào JSON với cấu trúc sau:
{
  "intent": "search_new | compare_specific | supplier_detail | out_of_scope",
  "product_type": "loại sản phẩm hoặc null",
  "quantity": số_nguyên_hoặc_null,
  "budget_max": số_VND_hoặc_null,
  "delivery_deadline_days": số_nguyên_hoặc_null,
  "material_preference": "chất liệu hoặc null",
  "region_preference": "khu vực hoặc null",
  "min_trust_score": số_thực_1_5_hoặc_null,
  "supplier_ids": ["MaNCC1", ...] hoặc [],
  "supplier_id": "MaNCC_cu_the hoặc null"
}

Quy tắc bắt buộc:
1. Chỉ điền giá trị khi khách đề cập RÕ RÀNG trong câu.
2. KHÔNG suy diễn hoặc tự điền giá trị mặc định.
3. Nếu không tìm thấy thông tin → dùng null hoặc [].
4. budget_max: chuyển về số VND thuần (VD: "200 triệu" → 200000000, "5 tỷ" → 5000000000).
5. delivery_deadline_days: chuyển về số ngày (VD: "2 tuần" → 14, "1 tháng" → 30).
6. product_type: normalize về đúng 1 trong {ghế văn phòng, bàn làm việc, tủ hồ sơ, kệ, sofa} nếu nhận ra.
7. intent:
   - "search_new": khách muốn TÌM nhà cung cấp mới theo yêu cầu (cần đầy đủ hard constraints). Nếu câu có kèm hỏi ngoài lề nhưng VẪN CÓ nhu cầu mua sắm, chọn search_new thay vì out_of_scope.
   - "compare_specific": khách nêu tên/mã NCC cụ thể muốn so sánh (chỉ cần supplier_ids + quantity).
   - "supplier_detail": khách hỏi chi tiết về một NCC cụ thể (chỉ cần supplier_id).
   - "out_of_scope": câu hỏi HOÀN TOÀN nằm ngoài phạm vi mua sắm nội thất.
8. Chỉ trả JSON thuần, không giải thích thêm.
"""

_UPDATE_SYSTEM_PROMPT = """Bạn là trợ lý cập nhật yêu cầu mua sắm nội thất khi khách thay đổi thông tin.

Nhiệm vụ: Đọc tin nhắn và trích xuất CÁC THÔNG TIN ĐƯỢC ĐỀ CẬP vào JSON:
{
  "intent": "search_new | compare_specific | supplier_detail | out_of_scope | null",
  "product_type": "loại sản phẩm hoặc null",
  "quantity": số_nguyên_hoặc_null,
  "budget_max": số_VND_hoặc_null,
  "delivery_deadline_days": số_nguyên_hoặc_null,
  "material_preference": "chất liệu hoặc null",
  "region_preference": "khu vực hoặc null",
  "min_trust_score": số_thực_1_5_hoặc_null,
  "supplier_ids": ["MaNCC1", ...] hoặc [],
  "supplier_id": "MaNCC_cu_the hoặc null"
}

Quy tắc:
1. Trả null cho field KHÔNG được đề cập (sẽ được giữ nguyên từ yêu cầu trước). Việc trả lời "chốt đơn", "chưa chốt", hay xác nhận đồng ý/từ chối đều tính là không thay đổi intent (trả null).
2. Chuyển đổi đơn vị: triệu→VND, tuần→ngày.
3. Chỉ trả JSON thuần.
"""


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _call_llm(system_prompt: str, user_text: str) -> tuple[dict, int, int]:
    """Gọi LLM với JSON output, trả về (dict đã parse, tokens_in, tokens_out).

    Dùng factory chung src.llm.get_llm() để AGENT_LLM=stub được tôn trọng
    và tên model không bị khai báo riêng ở parser (architecture.md §3.1).
    """
    llm = get_llm().bind(
        response_format={"type": "json_object"}
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_text),
    ]
    response = llm.invoke(messages)
    tokens_in, tokens_out = usage_of(response)
    raw = response.content
    if isinstance(raw, list):
        # Một số provider trả list[block]
        raw = "".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in raw)
    return json.loads(raw.strip()), tokens_in, tokens_out


# ---------------------------------------------------------------------------
# Internal validation helpers (dùng chung bởi parse_request & update_state)
# ---------------------------------------------------------------------------


def _parse_product_type(raw: str) -> str:
    """Normalize và validate product_type. Raise InvalidProductTypeError nếu không hợp lệ."""
    p = str(raw).strip().lower()
    if p not in VALID_PRODUCT_TYPES:
        raise InvalidProductTypeError(raw)
    return p


def _parse_quantity(raw) -> int:
    """Chuyển về int và đảm bảo > 0."""
    qty = int(raw)
    if qty <= 0:
        raise ValueError(f"quantity phải > 0, nhận được: {qty}")
    return qty


def _parse_budget(raw) -> float:
    """Chuyển về float và đảm bảo > 0."""
    b = float(raw)
    if b <= 0:
        raise ValueError(f"budget_max phải > 0, nhận được: {b}")
    return b


def _parse_deadline(raw) -> int:
    """Chuyển về int và đảm bảo > 0."""
    d = int(raw)
    if d <= 0:
        raise ValueError(f"delivery_deadline_days phải > 0, nhận được: {d}")
    return d


def _parse_trust_score(raw) -> "float | None":
    """Chuyển về float trong [1,5] hoặc None nếu ngoài range."""
    t = float(raw)
    return t if 1.0 <= t <= 5.0 else None


def _parse_intent(raw: str | None) -> str:
    """Normalize và validate intent. Mặc định 'search_new' nếu LLM bỏ sót."""
    if not raw or str(raw).strip() not in VALID_INTENTS:
        return "search_new"
    return str(raw).strip()


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def parse_request(text: str, session_id: Optional[str] = None) -> tuple[dict, int, int]:
    """Parse câu yêu cầu tự nhiên của khách thành structured state.

    Dùng LangChain ChatGoogleGenerativeAI với JSON mode để trích xuất thông tin —
    không hard-code keyword hay regex theo ý chủ quan.

    Validation phụ thuộc intent (architecture.md §3.1):
    - search_new: cần đầy đủ 4 hard constraints.
    - compare_specific: chỉ cần supplier_ids + quantity.
    - supplier_detail: chỉ cần supplier_id.
    - out_of_scope: không cần constraint, trả state với intent rõ.

    Args:
        text:       Câu yêu cầu của khách hàng (ngôn ngữ tự nhiên).
        session_id: UUID phiên làm việc. Nếu None → tự sinh UUID mới.

    Returns:
        tuple(Dict đúng schema SYSTEM-RULES §2.1, tokens_in, tokens_out).

    Raises:
        MissingFieldError:       Nếu thiếu ≥1 hard constraint bắt buộc (search_new).
        InvalidProductTypeError: Nếu product_type không thuộc enum hợp lệ.
        ValueError:              Nếu numeric field có giá trị không hợp lệ (≤ 0).
    """
    if session_id is None:
        session_id = f"sess_{uuid.uuid4().hex[:8]}"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # --- Gọi LLM để trích xuất (bao gồm intent) ---
    extracted, tokens_in, tokens_out = _call_llm(_EXTRACT_SYSTEM_PROMPT, text)
    intent = _parse_intent(extracted.get("intent"))

    # --- Kiểm tra field bắt buộc theo intent ---
    missing = []
    if intent == "search_new":
        if not extracted.get("product_type"):
            missing.append("loại sản phẩm (ghế văn phòng, bàn làm việc, tủ hồ sơ, kệ, sofa)")
        if extracted.get("quantity") is None:
            missing.append("số lượng")
        if extracted.get("budget_max") is None:
            missing.append("ngân sách tối đa")
        if extracted.get("delivery_deadline_days") is None:
            missing.append("thời hạn giao hàng (số ngày)")

        # Validate & build hard constraints
        hard = {
            "product_type":           _parse_product_type(extracted["product_type"]) if extracted.get("product_type") else None,
            "quantity":               _parse_quantity(extracted["quantity"]) if extracted.get("quantity") is not None else None,
            "budget_max":             _parse_budget(extracted["budget_max"]) if extracted.get("budget_max") is not None else None,
            "delivery_deadline_days": _parse_deadline(extracted["delivery_deadline_days"]) if extracted.get("delivery_deadline_days") is not None else None,
        }

    elif intent == "compare_specific":
        # Chỉ cần supplier_ids và quantity
        hard = {
            "product_type":           None,
            "quantity":               _parse_quantity(extracted["quantity"]) if extracted.get("quantity") else None,
            "budget_max":             None,
            "delivery_deadline_days": None,
        }

    elif intent == "supplier_detail":
        # Không cần bất kỳ hard constraint nào
        hard = {
            "product_type":           None,
            "quantity":               None,
            "budget_max":             None,
            "delivery_deadline_days": None,
        }

    else:  # out_of_scope
        hard = {
            "product_type":           None,
            "quantity":               None,
            "budget_max":             None,
            "delivery_deadline_days": None,
        }

    # --- Validate & build soft constraints ---
    raw_trust = extracted.get("min_trust_score")
    soft = {
        "material_preference": extracted.get("material_preference"),
        "region_preference":   extracted.get("region_preference"),
        "min_trust_score":     _parse_trust_score(raw_trust) if raw_trust is not None else None,
    }

    state_dict = {
        "session_id":           session_id,
        "created_at":           now,
        "updated_at":           now,
        "intent":               intent,
        "supplier_ids":         extracted.get("supplier_ids") or [],
        "supplier_id":          extracted.get("supplier_id"),
        "hard_constraints":     hard,
        "soft_constraints":     soft,
        "conversation_history": [{"role": "user", "content": text, "timestamp": now}],
        "decisions_made":       [],
    }

    if missing:
        raise MissingFieldError(missing, partial_state=state_dict)

    return state_dict, tokens_in, tokens_out


# ---------------------------------------------------------------------------
# Update state khi khách thay đổi yêu cầu
# ---------------------------------------------------------------------------


def update_state(existing_state: dict, new_text: str) -> tuple[dict, int, int]:
    """Cập nhật state hiện có khi khách đổi yêu cầu trong cùng phiên.

    Theo SYSTEM-RULES §2.1: ghi đè field liên quan, không giữ song song bản cũ.
    Chỉ các field được đề cập trong new_text mới bị thay đổi.

    Args:
        existing_state: State dict hiện tại (đã load từ DB).
        new_text:       Câu yêu cầu mới của khách.

    Returns:
        tuple(State dict đã được cập nhật, tokens_in, tokens_out)

    Raises:
        InvalidProductTypeError: Nếu product_type mới không thuộc enum hợp lệ.
        ValueError:              Nếu numeric field có giá trị không hợp lệ (≤ 0).
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # Trích xuất thông tin thay đổi từ LLM (bao gồm intent mới nếu đổi ngữ cảnh)
    extracted, tokens_in, tokens_out = _call_llm(_UPDATE_SYSTEM_PROMPT, new_text)

    # Cập nhật intent nếu LLM phát hiện ngữ cảnh mới
    new_intent_raw = extracted.get("intent")
    if new_intent_raw is None or new_intent_raw == "null":
        new_intent = existing_state.get("intent", "search_new")
    else:
        new_intent = _parse_intent(new_intent_raw)

    # Ghi đè chỉ những field được đề cập (không None) — dùng helper để validate
    updated_hard = dict(existing_state.get("hard_constraints", {}))
    _HARD_PARSERS = {
        "product_type":           _parse_product_type,
        "quantity":               _parse_quantity,
        "budget_max":             _parse_budget,
        "delivery_deadline_days": _parse_deadline,
    }
    for field, parser in _HARD_PARSERS.items():
        if extracted.get(field) is not None:
            updated_hard[field] = parser(extracted[field])

    updated_soft = dict(existing_state.get("soft_constraints", {}))
    for field in ("material_preference", "region_preference"):
        if extracted.get(field) is not None:
            updated_soft[field] = extracted[field]
    if extracted.get("min_trust_score") is not None:
        parsed = _parse_trust_score(extracted["min_trust_score"])
        if parsed is not None:  # chỉ ghi đè khi giá trị hợp lệ; ngoài range giữ nguyên
            updated_soft["min_trust_score"] = parsed

    # Cập nhật supplier_ids / supplier_id nếu đề cập
    updated_supplier_ids = existing_state.get("supplier_ids", [])
    if extracted.get("supplier_ids"):
        updated_supplier_ids = extracted["supplier_ids"]
    updated_supplier_id = existing_state.get("supplier_id")
    if extracted.get("supplier_id") is not None:
        updated_supplier_id = extracted["supplier_id"]

    # Append turn mới vào conversation_history
    history = list(existing_state.get("conversation_history", []))
    history.append({"role": "user", "content": new_text, "timestamp": now})

    updated_state = {
        **existing_state,
        "updated_at":           now,
        "intent":               new_intent,
        "supplier_ids":         updated_supplier_ids,
        "supplier_id":          updated_supplier_id,
        "hard_constraints":     updated_hard,
        "soft_constraints":     updated_soft,
        "conversation_history": history,
    }
    
    return updated_state, tokens_in, tokens_out
