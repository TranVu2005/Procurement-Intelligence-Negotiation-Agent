"""Nha may LLM dung chung cho ca perceive (A) va respond (C).

Owner: Nguoi C. Muc dich: mot cho duy nhat khai bao ten model va cach dem
token, de so lieu "Average LLM Calls / Request" va chi phi trong bao cao
truy duoc ve cung mot nguon (architecture.md muc 2.3, 5.7).

Bat stub bang bien moi truong AGENT_LLM=stub -> khong goi mang, dung cho
load test muc 10-50 CCU (architecture.md muc 5.6).
"""

import json
import os
import random
import time

from langchain_core.messages import AIMessage

MODEL_NAME = "gemini-3.6-flash"

# JSON co dinh cho StubLLM sau .bind(response_format=...) - dung cho Perception
# (src/perception/parser.py::_call_llm, json.loads(response.content)). Gia tri
# khop voi bo 4 hard constraint stub cu (Task 3) de khong doi baseline AutoEval
# --llm stub hien co. Stub khong lam NLP that: moi request deu ra cung 1 JSON,
# bat ke user_input la gi - dung de do chi phi/latency pipeline, khong do chat
# luong Perception (do bang --llm real).
_STUB_PERCEPTION_JSON = json.dumps({
    "intent": "search_new",
    "product_type": "ghế văn phòng",
    "quantity": 50,
    "budget_max": 200_000_000,
    "delivery_deadline_days": 14,
    "material_preference": None,
    "region_preference": None,
    "min_trust_score": None,
    "supplier_ids": [],
    "supplier_id": None,
}, ensure_ascii=False)

# Do tre gia lap cua stub. Do thuc te bang scripts/run_loadtest.py --levels 1
# --requests-per-level 5 --llm real (Task 16 buoc 6): p50=17542ms, p95=20966ms
# tren gemini-3.6-flash, CCU=1, ngay 2026-09-14.
STUB_LATENCY_MEAN_S = 17.5
STUB_LATENCY_STDDEV_S = 1.7

_STUB_TEXT = (
    "[STUB] Da tim duoc nha cung cap phu hop. Day la phan hoi co dinh dung cho "
    "load test, khong goi mo hinh that."
)


class StubLLM:
    """Thay the ChatGoogleGenerativeAI trong load test.

    Tra dung mot cau co dinh va sleep theo phan phoi do tre da do duoc, de
    so lieu throughput/P95 phan anh chi phi cua pipeline chu khong phai cua
    duong mang toi Gemini.
    """

    def __init__(self, latency_s: float | None = None) -> None:
        self._latency_s = latency_s

    def _sleep(self) -> None:
        if self._latency_s is not None:
            delay = self._latency_s
        else:
            delay = random.gauss(STUB_LATENCY_MEAN_S, STUB_LATENCY_STDDEV_S)
        if delay > 0:
            time.sleep(delay)

    @staticmethod
    def _message() -> AIMessage:
        return AIMessage(
            content=_STUB_TEXT,
            usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )

    def invoke(self, messages, **_kwargs) -> AIMessage:
        self._sleep()
        return self._message()

    def stream(self, messages, **_kwargs):
        self._sleep()
        words = _STUB_TEXT.split(" ")
        for index, word in enumerate(words):
            suffix = "" if index == len(words) - 1 else " "
            yield AIMessage(content=word + suffix)
        yield AIMessage(
            content="",
            usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )

    def bind(self, **_kwargs) -> "StubLLM":
        """Nhai .bind(response_format=...) cua ChatGoogleGenerativeAI (LangChain
        Runnable). parser.py goi _get_llm().bind(response_format={"type":
        "json_object"}) roi .invoke() - khong co bind() se AttributeError khi
        A doi sang dung get_llm() chung. Tra ve bien the JSON, khong phai self,
        vi noi dung tra ve khac (JSON thay vi cau van cho respond)."""
        return _StubPerceptionLLM(latency_s=self._latency_s)


class _StubPerceptionLLM(StubLLM):
    """StubLLM sau .bind() - danh cho Perception (parser.py). Tra JSON hop le
    theo dung schema _EXTRACT_SYSTEM_PROMPT/_UPDATE_SYSTEM_PROMPT mong doi, de
    json.loads() khong crash. Xem _STUB_PERCEPTION_JSON o dau file."""

    @staticmethod
    def _message() -> AIMessage:
        return AIMessage(
            content=_STUB_PERCEPTION_JSON,
            usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )


def get_llm(streaming: bool = False, temperature: float = 0.0):
    """Tra ve client LLM. AGENT_LLM=stub -> StubLLM, khong can API key."""
    if os.getenv("AGENT_LLM", "").lower() == "stub":
        return StubLLM()

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY chua duoc set. Tao file .env voi GOOGLE_API_KEY=your_key, "
            "hoac dat AGENT_LLM=stub de chay khong can mang."
        )

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        google_api_key=api_key,
        temperature=temperature,
        disable_streaming=not streaming,
    )


def usage_of(message) -> tuple[int, int]:
    """(tokens_in, tokens_out) tu usage_metadata; (0, 0) neu provider khong tra."""
    usage = getattr(message, "usage_metadata", None) or {}
    return int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0)
