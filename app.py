"""Streamlit demo UI for the Procurement Intelligence Agent.

Run from the repository root:
    streamlit run app.py
"""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Load local configuration before importing the graph/LLM modules.
from src.graph import run_request  # noqa: E402
from src.ui_viewmodel import run_metrics, supplier_view_models  # noqa: E402

st.set_page_config(
    page_title="Procurement Intelligence Agent",
    page_icon="📦",
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container {max-width: 1180px; padding-top: 2rem;}
      [data-testid="stMetricValue"] {font-size: 1.2rem;}
      .data-note {color: #64748b; font-size: 0.86rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _init_state() -> None:
    st.session_state.setdefault("session_id", None)
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("latest_state", None)


def _reset() -> None:
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.latest_state = None


def _run_turn(prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.spinner("Agent đang phân tích yêu cầu và kiểm tra nguồn dữ liệu..."):
        final = run_request(prompt, session_id=st.session_state.session_id)
    st.session_state.session_id = final.get("session_id") or st.session_state.session_id
    st.session_state.latest_state = final
    st.session_state.messages.append({
        "role": "assistant",
        "content": final.get("answer") or "Không có câu trả lời.",
        "state": final,
    })


def _render_cards(final: dict) -> None:
    cards = supplier_view_models(final.get("ranked"))
    if not cards:
        return
    st.subheader("Phương án được xếp hạng")
    for card in cards:
        with st.container(border=True):
            title_col, score_col = st.columns([4, 1])
            title_col.markdown(
                f"### #{card['rank']} · {card['supplier_name']} "
                f"`{card['supplier_id']}`"
            )
            score_col.metric("Điểm", card["score"])
            price_col, total_col, delivery_col, trust_col = st.columns(4)
            price_col.metric("Đơn giá", card["unit_price"])
            total_col.metric("Tổng tiền", card["total_price"])
            delivery_col.metric("Giao hàng", card["delivery"])
            trust_col.metric("Uy tín", card["trust"])

            if card["source_url"]:
                st.link_button("Mở nguồn dữ liệu", card["source_url"])
            else:
                st.warning("Bản ghi chưa có URL nguồn HTTP(S) hợp lệ.")

            st.caption(
                f"Loại nguồn: {card['source_type']} · "
                f"Trạng thái: {card['data_label']}"
            )
            if card["simulated_fields"]:
                st.caption(
                    "Dữ liệu mô phỏng: " + ", ".join(card["simulated_fields"])
                )
            else:
                st.caption("Bản ghi không khai báo trường mô phỏng.")

            with st.expander("Giải thích điểm và đánh đổi"):
                st.json(card["score_breakdown"])
                for item in card["strengths"]:
                    st.markdown(f"- ✅ {item}")
                for item in card["trade_offs"]:
                    st.markdown(f"- ⚠️ {item}")


def _render_metrics(final: dict) -> None:
    metrics = run_metrics(final)
    with st.expander("Trace và chỉ số lần chạy"):
        cols = st.columns(4)
        cols[0].metric("Status", metrics["status"])
        cols[1].metric("Intent", metrics["intent"])
        cols[2].metric("LLM calls", metrics["llm_calls"])
        cols[3].metric("Tool calls", metrics["tool_calls"])
        detail_cols = st.columns(3)
        detail_cols[0].metric("Latency", f"{metrics['latency_ms']} ms")
        detail_cols[1].metric("Replan", metrics["replan_count"])
        verifier = metrics["verifier_passed"]
        detail_cols[2].metric(
            "Verifier",
            "PASS" if verifier is True else "FAIL" if verifier is False else "N/A",
        )
        st.code(f"trace_id={metrics['trace_id']}")


def _render_message(message: dict) -> None:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        final = message.get("state")
        if isinstance(final, dict):
            _render_cards(final)
            _render_metrics(final)


_init_state()

with st.sidebar:
    st.header("Cấu hình demo")
    provider = "Stub" if os.getenv("AGENT_LLM", "").lower() == "stub" else os.getenv("LLM_PROVIDER", "gemini").title()
    st.write(f"LLM: **{provider}**")
    st.write(f"Session: `{st.session_state.session_id or 'chưa tạo'}`")
    st.info("Giá trị có trong `simulated_fields` không phải dữ liệu thị trường đã xác minh.")
    if st.button("Bắt đầu phiên mới", use_container_width=True):
        _reset()
        st.rerun()

st.title("Procurement Intelligence Agent")
st.caption("Tìm kiếm · So sánh · Xác minh nguồn · Hỗ trợ thương lượng")

if not st.session_state.messages:
    st.info(
        "Thử nhập: Cần mua 50 ghế văn phòng, ngân sách 200 triệu, "
        "giao trong 14 ngày."
    )

for chat_message in st.session_state.messages:
    _render_message(chat_message)

latest = st.session_state.latest_state or {}
if latest.get("status") == "needs_confirmation" and latest.get("pending_confirmation"):
    pending = latest["pending_confirmation"]
    st.warning(
        f"Đang chờ xác nhận: {pending.get('supplier_name')} · "
        f"{pending.get('quantity')} sản phẩm."
    )
    if st.button("Xác nhận chốt đơn", type="primary"):
        _run_turn("chốt đơn đi")
        st.rerun()

if prompt := st.chat_input("Nhập yêu cầu mua sắm..."):
    _run_turn(prompt)
    st.rerun()
