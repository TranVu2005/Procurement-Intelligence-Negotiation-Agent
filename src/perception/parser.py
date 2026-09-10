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

_configure_gemini()

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
    """
    if session_id is None:
        session_id = f"sess_{uuid.uuid4().hex[:8]}"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # --- Gọi Gemini để trích xuất ---
    extracted = _call_gemini(_EXTRACT_SYSTEM_PROMPT, text)

    # --- Validate hard constraints ---
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

    # --- Validate product_type ---
    product_type = str(extracted["product_type"]).strip().lower()
    if product_type not in VALID_PRODUCT_TYPES:
        raise InvalidProductTypeError(extracted["product_type"])

    # --- Validate numeric fields ---
    quantity = int(extracted["quantity"])
    if quantity <= 0:
        raise ValueError(f"quantity phải > 0, nhận được: {quantity}")

    budget_max = float(extracted["budget_max"])
    if budget_max <= 0:
        raise ValueError(f"budget_max phải > 0, nhận được: {budget_max}")

    delivery_deadline_days = int(extracted["delivery_deadline_days"])
    if delivery_deadline_days <= 0:
        raise ValueError(f"delivery_deadline_days phải > 0, nhận được: {delivery_deadline_days}")

    # --- Validate soft constraints ---
    min_trust = extracted.get("min_trust_score")
    if min_trust is not None:
        min_trust = float(min_trust)
        if not (1.0 <= min_trust <= 5.0):
            min_trust = None  # Bỏ qua giá trị ngoài range thay vì crash

    # --- Xây dựng state dict theo SYSTEM-RULES §2.1 ---
    state = {
        "session_id": session_id,
        "created_at": now,
        "updated_at": now,
        "hard_constraints": {
            "product_type": product_type,
            "quantity": quantity,
            "budget_max": budget_max,
            "delivery_deadline_days": delivery_deadline_days,
        },
        "soft_constraints": {
            "material_preference": extracted.get("material_preference"),
            "region_preference": extracted.get("region_preference"),
            "min_trust_score": min_trust,
        },
        "conversation_history": [
            {"role": "user", "content": text, "timestamp": now}
        ],
        "decisions_made": [],
    }

    return state


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
        State dict đã được cập nhật.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # Trích xuất thông tin thay đổi
    extracted = _call_gemini(_UPDATE_SYSTEM_PROMPT, new_text)

    # Ghi đè chỉ những field có giá trị mới (không None)
    updated_hard = dict(existing_state["hard_constraints"])
    if extracted.get("product_type") is not None:
        p = str(extracted["product_type"]).strip().lower()
        if p not in VALID_PRODUCT_TYPES:
            raise InvalidProductTypeError(extracted["product_type"])
        updated_hard["product_type"] = p
    if extracted.get("quantity") is not None:
        updated_hard["quantity"] = int(extracted["quantity"])
    if extracted.get("budget_max") is not None:
        updated_hard["budget_max"] = float(extracted["budget_max"])
    if extracted.get("delivery_deadline_days") is not None:
        updated_hard["delivery_deadline_days"] = int(extracted["delivery_deadline_days"])

    updated_soft = dict(existing_state["soft_constraints"])
    if extracted.get("material_preference") is not None:
        updated_soft["material_preference"] = extracted["material_preference"]
    if extracted.get("region_preference") is not None:
        updated_soft["region_preference"] = extracted["region_preference"]
    if extracted.get("min_trust_score") is not None:
        updated_soft["min_trust_score"] = float(extracted["min_trust_score"])

    # Append turn mới vào conversation_history
    history = list(existing_state.get("conversation_history", []))
    history.append({"role": "user", "content": new_text, "timestamp": now})

    updated_state = {
        **existing_state,
        "updated_at": now,
        "hard_constraints": updated_hard,
        "soft_constraints": updated_soft,
        "conversation_history": history,
    }

    return updated_state
