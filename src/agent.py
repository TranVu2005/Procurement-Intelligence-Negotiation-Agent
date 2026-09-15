"""Agent entry point — REPL mỏng gọi run_request().

Owner: C (architecture.md §2.6)

A chỉ cập nhật file này để phản ánh đúng quyền sở hữu và đảm bảo
giao tiếp qua run_request() thay vì AgentExecutor đã bị bỏ.

Chạy:
    python -m src.agent

Yêu cầu:
    GOOGLE_API_KEY đã set trong .env hoặc biến môi trường.
    langchain==1.4.0 (AgentExecutor đã bị bỏ — dùng LangGraph StateGraph).
    Xem architecture.md §2 để hiểu thiết kế pipeline.
"""

import sys
import io

# Force UTF-8 stdout trên Windows
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()


def main() -> None:
    """REPL mỏng: nhận input từ người dùng, gọi run_request(), in kết quả.

    Tách run_request() ra khỏi vòng lặp input() để AutoEval và load test
    có thể gọi trực tiếp mà không cần giả lập terminal (architecture.md §2.5).
    """
    # Import ở đây để tránh circular import và cho phép unit test import module mà không cần env
    try:
        from src.graph import run_request  # noqa: F401 — C sở hữu, import ở đây
    except ImportError:
        # graph.py chưa được C tạo — fallback để A test được parser/db độc lập
        def run_request(user_input: str, session_id: str | None = None, _inject: dict | None = None) -> dict:
            """Stub cho đến khi C hoàn thành src/graph.py."""
            return {
                "answer": f"[STUB] Chưa có graph.py. Input: {user_input}",
                "status": "stub",
                "session_id": session_id or "stub_session",
            }

    print("\n" + "=" * 60)
    print("  Procurement Intelligence & Negotiation Agent")
    print("  (Goc: LangGraph pipeline — architecture.md §2)")
    print("  Nhap 'quit' hoac 'exit' de thoat")
    print("=" * 60 + "\n")

    session_id: str | None = None

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

        result = run_request(user_input, session_id=session_id)
        session_id = result.get("session_id", session_id)
        print(f"\nAgent: {result.get('answer', result)}\n")


if __name__ == "__main__":
    main()
