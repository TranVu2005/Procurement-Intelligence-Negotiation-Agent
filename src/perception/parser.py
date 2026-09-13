"""Perception module — parse natural-language procurement request into structured state.

Owner: Nguoi A

State schema contract (SYSTEM-RULES.md §2.1):
{
    "session_id":   str,                    # UUID
    "created_at":   str,                    # ISO 8601
    "updated_at":   str,                    # ISO 8601
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
- Nếu product_type không nằm trong enum → raise InvalidProductTypeError.
- Dùng LLM (Google Gemini) để parse — không regex, không keyword matching cứng.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv

# Load .env
load_dotenv()

# ---------------------------------------------------------------------------
# Cấu hình Gemini
# ---------------------------------------------------------------------------

def _configure_gemini() -> None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY chưa được set. "
            "Tạo file .env với GOOGLE_API_KEY=your_key hoặc export biến môi trường."
        )
    genai.configure(api_key=api_key)

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

_GEMINI_MODEL = "gemini-3.6-flash"

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class MissingFieldError(ValueError):
    """Raise khi input thiếu field bắt buộc (hard constraint).

    Agent nên bắt lỗi này và hỏi lại người dùng thay vì tự điền ngầm.
    """

    def __init__(self, missing_fields: list[str]):
        self.missing_fields = missing_fields
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
# Prompt & schema cho Gemini JSON mode
# ---------------------------------------------------------------------------

_EXTRACT_SYSTEM_PROMPT = """Bạn là trợ lý trích xuất thông tin từ yêu cầu mua sắm nội thất.

Nhiệm vụ: Đọc câu yêu cầu và trích xuất thông tin vào JSON với cấu trúc sau:
{
  "product_type": "loại sản phẩm hoặc null",
  "quantity": số_nguyên_hoặc_null,
  "budget_max": số_VND_hoặc_null,
  "delivery_deadline_days": số_nguyên_hoặc_null,
  "material_preference": "chất liệu hoặc null",
  "region_preference": "khu vực hoặc null",
  "min_trust_score": số_thực_1_5_hoặc_null
}

Quy tắc bắt buộc:
1. Chỉ điền giá trị khi khách đề cập RÕ RÀNG trong câu.
2. KHÔNG suy diễn hoặc tự điền giá trị mặc định.
3. Nếu không tìm thấy thông tin → dùng null.
4. budget_max: chuyển về số VND thuần (VD: "200 triệu" → 200000000, "5 tỷ" → 5000000000).
5. delivery_deadline_days: chuyển về số ngày (VD: "2 tuần" → 14, "1 tháng" → 30).
6. product_type: normalize về đúng 1 trong {ghế văn phòng, bàn làm việc, tủ hồ sơ, kệ, sofa} nếu nhận ra, hoặc trả null nếu không thuộc danh mục này.
7. Chỉ trả JSON thuần, không giải thích thêm.
"""

_UPDATE_SYSTEM_PROMPT = """Bạn là trợ lý cập nhật yêu cầu mua sắm nội thất khi khách thay đổi thông tin.

Nhiệm vụ: Đọc tin nhắn và trích xuất CÁC THÔNG TIN ĐƯỢC ĐỀ CẬP vào JSON:
{
  "product_type": "loại sản phẩm hoặc null",
  "quantity": số_nguyên_hoặc_null,
  "budget_max": số_VND_hoặc_null,
  "delivery_deadline_days": số_nguyên_hoặc_null,
  "material_preference": "chất liệu hoặc null",
  "region_preference": "khu vực hoặc null",
  "min_trust_score": số_thực_1_5_hoặc_null
}

Quy tắc:
1. Trả null cho field KHÔNG được đề cập (sẽ được giữ nguyên từ yêu cầu trước).
2. Chuyển đổi đơn vị: triệu→VND, tuần→ngày.
3. Chỉ trả JSON thuần.
"""


def _call_gemini(system_prompt: str, user_text: str) -> dict:
    """Gọi Gemini với JSON output mode, trả về dict đã parse."""
    _configure_gemini()
    model = genai.GenerativeModel(
        model_name=_GEMINI_MODEL,
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    response = model.generate_content(user_text)
    raw = response.text.strip()
    return json.loads(raw)


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


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def parse_request(text: str, session_id: Optional[str] = None) -> dict:
    """Parse câu yêu cầu tự nhiên của khách thành structured state.

    Dùng Google Gemini với JSON mode để trích xuất thông tin — không hard-code
    keyword hay regex theo ý chủ quan.

    Args:
        text:       Câu yêu cầu của khách hàng (ngôn ngữ tự nhiên).
        session_id: UUID phiên làm việc. Nếu None → tự sinh UUID mới.

    Returns:
        Dict đúng schema SYSTEM-RULES §2.1.

    Raises:
        MissingFieldError:       Nếu thiếu ≥1 hard constraint bắt buộc.
        InvalidProductTypeError: Nếu product_type không thuộc enum hợp lệ.
        ValueError:              Nếu numeric field có giá trị không hợp lệ (≤ 0).
    """
    if session_id is None:
        session_id = f"sess_{uuid.uuid4().hex[:8]}"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # --- Gọi Gemini để trích xuất ---
    extracted = _call_gemini(_EXTRACT_SYSTEM_PROMPT, text)

    # --- Kiểm tra field bắt buộc còn thiếu ---
    missing = []
    if not extracted.get("product_type"):
        missing.append("loại sản phẩm (ghế văn phòng, bàn làm việc, tủ hồ sơ, kệ, sofa)")
    if extracted.get("quantity") is None:
        missing.append("số lượng")
    if extracted.get("budget_max") is None:
        missing.append("ngân sách tối đa")
    if extracted.get("delivery_deadline_days") is None:
        missing.append("thời hạn giao hàng (số ngày)")

    if missing:
        raise MissingFieldError(missing)

    # --- Validate & build hard constraints ---
    hard = {
        "product_type":           _parse_product_type(extracted["product_type"]),
        "quantity":               _parse_quantity(extracted["quantity"]),
        "budget_max":             _parse_budget(extracted["budget_max"]),
        "delivery_deadline_days": _parse_deadline(extracted["delivery_deadline_days"]),
    }

    # --- Validate & build soft constraints ---
    raw_trust = extracted.get("min_trust_score")
    soft = {
        "material_preference": extracted.get("material_preference"),
        "region_preference":   extracted.get("region_preference"),
        "min_trust_score":     _parse_trust_score(raw_trust) if raw_trust is not None else None,
    }

    return {
        "session_id":           session_id,
        "created_at":           now,
        "updated_at":           now,
        "hard_constraints":     hard,
        "soft_constraints":     soft,
        "conversation_history": [{"role": "user", "content": text, "timestamp": now}],
        "decisions_made":       [],
    }


# ---------------------------------------------------------------------------
# Update state khi khách thay đổi yêu cầu
# ---------------------------------------------------------------------------


def update_state(existing_state: dict, new_text: str) -> dict:
    """Cập nhật state hiện có khi khách đổi yêu cầu trong cùng phiên.

    Theo SYSTEM-RULES §2.1: ghi đè field liên quan, không giữ song song bản cũ.
    Chỉ các field được đề cập trong new_text mới bị thay đổi.

    Args:
        existing_state: State dict hiện tại (đã load từ DB).
        new_text:       Câu yêu cầu mới của khách.

    Returns:
        State dict đã được cập nhật (không mutate existing_state).

    Raises:
        InvalidProductTypeError: Nếu product_type mới không thuộc enum hợp lệ.
        ValueError:              Nếu numeric field có giá trị không hợp lệ (≤ 0).
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # Trích xuất thông tin thay đổi từ LLM
    extracted = _call_gemini(_UPDATE_SYSTEM_PROMPT, new_text)

    # Ghi đè chỉ những field được đề cập (không None) — dùng helper để validate
    updated_hard = dict(existing_state["hard_constraints"])
    _HARD_PARSERS = {
        "product_type":           _parse_product_type,
        "quantity":               _parse_quantity,
        "budget_max":             _parse_budget,
        "delivery_deadline_days": _parse_deadline,
    }
    for field, parser in _HARD_PARSERS.items():
        if extracted.get(field) is not None:
            updated_hard[field] = parser(extracted[field])

    updated_soft = dict(existing_state["soft_constraints"])
    for field in ("material_preference", "region_preference"):
        if extracted.get(field) is not None:
            updated_soft[field] = extracted[field]
    if extracted.get("min_trust_score") is not None:
        parsed = _parse_trust_score(extracted["min_trust_score"])
        if parsed is not None:  # chỉ ghi đè khi giá trị hợp lệ; ngoài range giữ nguyên
            updated_soft["min_trust_score"] = parsed

    # Append turn mới vào conversation_history
    history = list(existing_state.get("conversation_history", []))
    history.append({"role": "user", "content": new_text, "timestamp": now})

    return {
        **existing_state,
        "updated_at":           now,
        "hard_constraints":     updated_hard,
        "soft_constraints":     updated_soft,
        "conversation_history": history,
    }

