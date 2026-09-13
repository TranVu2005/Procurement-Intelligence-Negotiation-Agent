"""Entrypoint: khoi tao AgentExecutor, rap perception + reasoning + tools.

Cach chay:
    python -m src.agent

Luu y:
    Can dat GOOGLE_API_KEY trong .env truoc khi chay.
    Chat vong lap don gian: nhap 'quit' hoac 'exit' de thoat.
"""

import sys
import io
import os

# Force UTF-8 stdout tren Windows
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.perception.parser import (
    parse_request,
    update_state,
    MissingFieldError,
    InvalidProductTypeError,
)
from src.memory.db import init_db, save_session, load_session
from src.reasoning.planner import make_plan, make_replan, PlanningError, ReplanLimitReached
from src.tools.supplier_tools import (
    search_suppliers_tool,
    get_supplier_detail_tool,
    compare_price_tool,
)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """Ban la tro ly mua sam noi that thong minh (Procurement Intelligence Agent).

Nhiem vu: giup nguoi dung tim nha cung cap noi that phu hop voi yeu cau cua ho
(loai san pham, so luong, ngan sach, thoi han giao hang, uu tien chat lieu/khu vuc/uy tin).

Nguyen tac:
1. KHONG tu dien thong tin con thieu — hoi lai nguoi dung neu thieu field bat buoc.
2. Su dung tool de tim va so sanh nha cung cap thuc su — KHONG bịa du lieu.
3. Bao cao rang buoc bi vi pham ro rang (MOQ, ngan sach, deadline).
4. Chi de xuat NCC da duoc kiem tra du rang buoc cung truoc.
5. Moi hanh dong "chot don" phai co xac nhan truoc khi thuc thi.

Catalog san pham ho tro: ghe van phong, ban lam viec, tu ho so, ke, sofa.
"""

_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PROMPT),
    MessagesPlaceholder("chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

# ---------------------------------------------------------------------------
# Build AgentExecutor
# ---------------------------------------------------------------------------

def _build_agent() -> AgentExecutor:
    """Khoi tao LangChain AgentExecutor voi cac tool cua C."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY chua duoc set. Tao file .env voi GOOGLE_API_KEY=your_key."
        )

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0,
    )

    tools = [search_suppliers_tool, get_supplier_detail_tool, compare_price_tool]
    agent = create_tool_calling_agent(llm, tools, _PROMPT_TEMPLATE)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True,
    )


# ---------------------------------------------------------------------------
# Chat loop
# ---------------------------------------------------------------------------

def main() -> None:
    """Vong lap chat don gian: Perception (A) → Planner (B) → AgentExecutor (B+C)."""
    print("\n" + "=" * 60)
    print("  Procurement Intelligence & Negotiation Agent")
    print("  Nhan 'quit' hoac 'exit' de thoat")
    print("=" * 60 + "\n")

    init_db()
    executor = _build_agent()

    session_state = None
    current_plan = None
    chat_history = []

    while True:
        try:
            user_input = input("Ban: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTam biet!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "thoat"):
            print("Tam biet!")
            break

        # ── A: Perception — parse / update state ────────────────────────────
        try:
            if session_state is None:
                session_state = parse_request(user_input)
                save_session(session_state["session_id"], session_state)
                print(f"\n[A] Session: {session_state['session_id']}")
                print(f"[A] Hard: {session_state['hard_constraints']}")
                print(f"[A] Soft: {session_state['soft_constraints']}\n")
            else:
                session_state = update_state(session_state, user_input)
                save_session(session_state["session_id"], session_state)
                print(f"\n[A] State updated: {session_state['hard_constraints']}\n")

        except MissingFieldError as e:
            print(f"\nAgent: De tim nha cung cap, toi can them thong tin:\n  → {e}\n")
            continue
        except InvalidProductTypeError as e:
            print(f"\nAgent: {e}\n")
            continue
        except ValueError as e:
            print(f"\nAgent: Thong tin khong hop le — {e}\n")
            continue

        # ── B: Reasoning — make_plan / make_replan ──────────────────────────
        try:
            if current_plan is None:
                current_plan = make_plan(session_state)
            else:
                current_plan = make_replan(session_state, current_plan, "user updated requirements")
            print(f"[B] Plan: {current_plan['plan_id']} (replan #{current_plan['replan_count']})\n")
        except ReplanLimitReached:
            print("\nAgent: Da thu lai toi da 3 lan ma khong tim duoc giai phap phu hop. "
                  "Vui long dieu chinh yeu cau (ngan sach, so luong hoac thoi han) de toi co the giup tiep.\n")
            current_plan = None
            continue
        except PlanningError as e:
            print(f"\nAgent: Loi lap ke hoach — {e}\n")
            continue

        # ── B+C: AgentExecutor — thuc thi plan qua tool ─────────────────────
        try:
            response = executor.invoke({
                "input": user_input,
                "chat_history": chat_history,
            })
            answer = response.get("output", "")
            print(f"\nAgent: {answer}\n")

            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": answer})

        except Exception as e:
            print(f"\nAgent: Xay ra loi khi xu ly — {e}\n")


if __name__ == "__main__":
    main()
