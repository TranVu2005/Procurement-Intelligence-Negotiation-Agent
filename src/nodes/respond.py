"""Node respond - LLM #2. Owner: Nguoi C (prompt do B soan).

Dang la NODE GIA, thay ruot o Task 13.
"""

from src.graph_state import AgentState


def respond(state: AgentState) -> dict:
    return {
        "answer": "[stub] cau tra loi mau",
        "status": "success",
        "llm_calls": 1,
        "tokens_in": 0,
        "tokens_out": 0,
    }


respond.__stub__ = True
