"""
Retry/backoff cho loi tool TAM THOI (timeout/tool_unavailable). Owner: Nguoi C.

Khong sua logic ben trong tung tool (search_suppliers/get_supplier_detail/
compare_price) - wrapper nay chi goi lai nguyen ham tool khi gap loi thuoc
RETRYABLE_ERROR_TYPES. Loi xac dinh (no_match, invalid_input) KHONG duoc
retry vi goi lai voi cung input se luon ra cung loi - retry khong giup ich,
chi lam cham agent.

Het luot retry -> fallback: tra ve loi cuoi cung theo dung format chuan
(khong bia du lieu gia), de B re-plan dua tren do (interface-contracts.md
muc 3).
"""

import time
from typing import Any, Callable

from src.logging_utils.tracer import log_event, new_trace_id

RETRYABLE_ERROR_TYPES = {"timeout", "tool_unavailable"}
MAX_RETRIES = 2  # toi da 1 lan goi dau + 2 lan retry = 3 lan goi tool
BACKOFF_BASE_SECONDS = 0.2


def _is_retryable_error(result: Any) -> bool:
    return (
        isinstance(result, dict)
        and result.get("error") is True
        and result.get("error_type") in RETRYABLE_ERROR_TYPES
    )


def call_with_retry(tool_func: Callable[..., dict], *args,
                     max_retries: int = MAX_RETRIES,
                     backoff_base: float = BACKOFF_BASE_SECONDS,
                     stats: dict | None = None,
                     **kwargs) -> dict:
    """Goi tool_func(*args, **kwargs); tu dong retry voi backoff mu 2
    (backoff_base, 2*backoff_base, 4*backoff_base, ...) khi ket qua la loi
    thuoc RETRYABLE_ERROR_TYPES. Tra ve ket qua thanh cong dau tien, hoac
    loi cuoi cung sau khi het luot retry.

    stats: neu truyen vao 1 dict, ham dien stats["attempts"] = tong so lan
    da goi tool (1 = khong retry lan nao). Dung cho audit trail cua node tool.
    """
    retry_trace_id = new_trace_id()
    tool_name = getattr(tool_func, "__name__", str(tool_func))

    attempt = 0
    while True:
        result = tool_func(*args, **kwargs)
        if stats is not None:
            stats["attempts"] = attempt + 1

        if not _is_retryable_error(result):
            if attempt > 0:
                log_event(retry_trace_id, "tool_retry_recovered", tool=tool_name,
                          attempt=attempt + 1)
            return result

        if attempt >= max_retries:
            log_event(retry_trace_id, "tool_retry_exhausted", tool=tool_name,
                       attempts=attempt + 1, error_type=result.get("error_type"))
            return result

        wait_s = backoff_base * (2 ** attempt)
        log_event(retry_trace_id, "tool_retry_attempt", tool=tool_name,
                   attempt=attempt + 1, error_type=result.get("error_type"), wait_s=wait_s)
        time.sleep(wait_s)
        attempt += 1
