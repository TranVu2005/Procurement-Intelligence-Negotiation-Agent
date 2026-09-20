"""Entrypoint REPL. Owner: Nguoi C.

Cach chay:
    python -m src.agent

Toan bo logic nam trong src/graph.py::run_request. File nay chi lam mot viec:
doc input, goi run_request, in ket qua. Tach nhu vay de AutoEval va load test
goi thang run_request ma khong vuong vong lap input() chan luong
(architecture.md muc 2.5).
"""

import io
import sys

from dotenv import load_dotenv

load_dotenv()

from src.graph import run_request
from src.memory.db import init_db

_EXIT_WORDS = ("quit", "exit", "thoat")


def render(final: dict) -> str:
    """In cau tra loi kem cac so do kiem chung duoc ngay tren man hinh."""
    answer = final.get("answer") or "(khong co cau tra loi)"
    footer = (
        f"[status={final.get('status', '?')} "
        f"llm_calls={final.get('llm_calls', 0)} "
        f"tool_calls={len(final.get('tool_results') or [])} "
        f"replan={final.get('replan_count', 0)} "
        f"latency_ms={final.get('latency_ms', 0)} "
        f"trace={final.get('trace_id', '')}]"
    )
    return f"{answer}\n{footer}"


def main() -> None:
    if hasattr(sys.stdout, "buffer") and getattr(sys.stdout, "encoding", "").lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("\n" + "=" * 60)
    print("  Procurement Intelligence & Negotiation Agent")
    print("  Nhan 'quit' hoac 'exit' de thoat")
    print("=" * 60 + "\n")

    init_db()
    session_id = None

    while True:
        try:
            user_input = input("Ban: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTam biet!")
            return

        if not user_input:
            continue
        if user_input.lower() in _EXIT_WORDS:
            print("Tam biet!")
            return

        final = run_request(user_input, session_id=session_id)
        session_id = final.get("session_id") or session_id
        print(f"\nAgent: {render(final)}\n")


if __name__ == "__main__":
    main()
