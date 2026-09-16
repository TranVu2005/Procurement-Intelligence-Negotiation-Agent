"""Memory module — quản lý state qua SQLite.

Owner: Nguoi A

Cung cấp:
- init_db()            : tạo bảng theo schema.sql
- save_session()       : upsert toàn bộ state (ghi đè nếu đã tồn tại)
- load_session()       : load state theo session_id
- session_exists()     : kiểm tra session_id có tồn tại không
- delete_session()     : xóa toàn bộ dữ liệu 1 phiên (sessions + history + decisions)
- list_sessions()      : liệt kê tất cả session_id hiện có
- append_conversation(): ghi thêm 1 turn hội thoại
- load_conversation()  : đọc lịch sử hội thoại
- save_decision()      : ghi nhận NCC đã được chốt
- load_decisions()     : lấy danh sách NCC đã chốt trong phiên

Metrics (architecture.md §3.2, §5.5):
- start_run()          : tạo bản ghi run mới, trả về run_id
- finish_run()         : cập nhật status, latency, LLM/tool call counts
- save_artifact()      : lưu plan / tool_results / verdict theo session + run
- load_artifacts()     : đọc lại artifacts của 1 phiên
- load_runs()          : đọc metrics của các runs theo session
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "state.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


# ---------------------------------------------------------------------------
# Kết nối
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """Trả về connection với row_factory = sqlite3.Row để truy cập theo tên cột."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Tạo tất cả bảng theo schema.sql. Gọi 1 lần khi khởi động."""
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Trả về timestamp hiện tại dạng ISO 8601 (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

def save_session(session_id: str, state: dict) -> None:
    """Upsert toàn bộ state dict vào bảng sessions.

    Nếu session_id đã tồn tại → cập nhật updated_at và state_json.
    Nếu chưa tồn tại → insert mới.

    Args:
        session_id: ID phiên làm việc (thường là UUID).
        state:      Dict theo schema SYSTEM-RULES §2.1.
    """
    now = _now_iso()
    state_copy = dict(state)
    state_copy["updated_at"] = now
    state_json = json.dumps(state_copy, ensure_ascii=False)

    with get_connection() as conn:
        # Kiểm tra session đã tồn tại chưa
        existing = conn.execute(
            "SELECT session_id FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE sessions SET updated_at = ?, state_json = ? WHERE session_id = ?",
                (now, state_json, session_id),
            )
        else:
            created_at = state.get("created_at", now)
            conn.execute(
                "INSERT INTO sessions (session_id, created_at, updated_at, state_json) VALUES (?, ?, ?, ?)",
                (session_id, created_at, now, state_json),
            )


def load_session(session_id: str) -> Optional[dict]:
    """Load state theo session_id.

    Returns:
        Dict state nếu tìm thấy, None nếu không có.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT state_json FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()

    if row is None:
        return None
    return json.loads(row["state_json"])


def session_exists(session_id: str) -> bool:
    """Kiểm tra session_id có tồn tại không."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    return row is not None


def delete_session(session_id: str) -> bool:
    """Xóa toàn bộ dữ liệu của 1 phiên (sessions, conversation_history, decisions_made).

    Dùng để reset phiên hoặc kiểm tra session isolation — đảm bảo dữ liệu của
    phiên này không rò sang phiên khác sau khi xóa.

    Args:
        session_id: ID phiên cần xóa.

    Returns:
        True nếu session tồn tại và đã xóa, False nếu không tìm thấy.
    """
    with get_connection() as conn:
        # Xóa theo thứ tự để không vi phạm foreign key constraint
        conn.execute("DELETE FROM session_artifacts WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM runs WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM decisions_made WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM conversation_history WHERE session_id = ?", (session_id,))
        result = conn.execute(
            "DELETE FROM sessions WHERE session_id = ?", (session_id,)
        )
        return result.rowcount > 0


def list_sessions() -> list[str]:
    """Liệt kê tất cả session_id hiện có trong DB, sắp xếp theo created_at.

    Dùng chủ yếu để debug và kiểm tra session isolation.

    Returns:
        List[str] — danh sách session_id theo thứ tự thời gian tạo.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT session_id FROM sessions ORDER BY created_at ASC"
        ).fetchall()
    return [r["session_id"] for r in rows]


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------

def append_conversation(session_id: str, role: str, content: str) -> None:
    """Ghi thêm 1 turn hội thoại vào conversation_history.

    Args:
        session_id: ID phiên làm việc.
        role:       'user' hoặc 'agent'.
        content:    Nội dung tin nhắn.

    Raises:
        ValueError: Nếu role không hợp lệ.
    """
    if role not in ("user", "agent"):
        raise ValueError(f"role phải là 'user' hoặc 'agent', nhận được: {role!r}")

    now = _now_iso()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO conversation_history (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now),
        )


def load_conversation(session_id: str) -> list[dict]:
    """Load toàn bộ lịch sử hội thoại của 1 phiên, sắp xếp theo thời gian.

    Returns:
        List[{"role": str, "content": str, "timestamp": str}]
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content, timestamp FROM conversation_history "
            "WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

def save_decision(session_id: str, supplier_id: str) -> None:
    """Ghi nhận 1 quyết định chốt NCC.

    Args:
        session_id:  ID phiên làm việc.
        supplier_id: MaNCC đã được xác nhận.
    """
    now = _now_iso()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO decisions_made (session_id, supplier_id, confirmed_at) VALUES (?, ?, ?)",
            (session_id, supplier_id, now),
        )


def load_decisions(session_id: str) -> list[dict]:
    """Load danh sách NCC đã chốt trong phiên.

    Returns:
        List[{"supplier_id": str, "confirmed_at": str}]
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT supplier_id, confirmed_at FROM decisions_made "
            "WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return [{"supplier_id": r["supplier_id"], "confirmed_at": r["confirmed_at"]} for r in rows]


# ---------------------------------------------------------------------------
# Runs — metrics mỗi request (architecture.md §3.2, §5.5)
# ---------------------------------------------------------------------------


def start_run(
    session_id: str,
    intent: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> str:
    """Tạo bản ghi run mới với status='running', trả về run_id.

    Gọi ngay khi bắt đầu xử lý 1 request để đảm bảo audit trail hoàn chỉnh
    kể cả khi request thất bại giữa chừng.

    Args:
        session_id: ID phiên làm việc.
        intent:     Intent đã phân loại (search_new / compare_specific / ...).
        trace_id:   Trace ID từ tracer.py (nếu có).

    Returns:
        run_id (str): UUID hex dùng để gọi finish_run() sau.
    """
    run_id = uuid.uuid4().hex
    now = _now_iso()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO runs
               (run_id, session_id, trace_id, intent, status, started_at)
               VALUES (?, ?, ?, ?, 'running', ?)""",
            (run_id, session_id, trace_id, intent, now),
        )
    return run_id


def finish_run(
    run_id: str,
    *,
    status: str = "success",
    llm_calls: int = 0,
    tool_calls: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: Optional[float] = None,
    ttft_ms: Optional[float] = None,
    error_msg: Optional[str] = None,
) -> None:
    """Cập nhật kết quả và metrics khi request hoàn thành hoặc thất bại.

    Args:
        run_id:     run_id nhận được từ start_run().
        status:     'success' | 'graceful_fail' | 'error'.
        llm_calls:  Số lần gọi LLM (kỳ vọng = 2 cho happy path).
        tool_calls: Số lần gọi tool.
        tokens_in:  Tổng token input (sum qua tất cả LLM calls).
        tokens_out: Tổng token output.
        latency_ms: End-to-end latency (ms).
        ttft_ms:    Time to first token (ms), None nếu không stream.
        error_msg:  Mô tả lỗi nếu status='error'.
    """
    valid_statuses = {"success", "graceful_fail", "error"}
    if status not in valid_statuses:
        raise ValueError(f"status phải là một trong {valid_statuses}, nhận được: {status!r}")

    now = _now_iso()
    with get_connection() as conn:
        conn.execute(
            """UPDATE runs SET
               status=?, llm_calls=?, tool_calls=?, tokens_in=?, tokens_out=?,
               latency_ms=?, ttft_ms=?, finished_at=?, error_msg=?
               WHERE run_id=?""",
            (status, llm_calls, tool_calls, tokens_in, tokens_out,
             latency_ms, ttft_ms, now, error_msg, run_id),
        )


def load_runs(session_id: str, *, limit: int = 50) -> list[dict]:
    """Đọc danh sách runs (metrics) của 1 phiên, mới nhất trước.

    Args:
        session_id: ID phiên cần xem.
        limit:      Số bản ghi tối đa trả về (default 50).

    Returns:
        List[dict] với các key: run_id, trace_id, intent, status, llm_calls,
        tool_calls, tokens_in, tokens_out, latency_ms, ttft_ms, started_at,
        finished_at, error_msg.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT run_id, trace_id, intent, status, llm_calls, tool_calls,
                      tokens_in, tokens_out, latency_ms, ttft_ms,
                      started_at, finished_at, error_msg
               FROM runs WHERE session_id = ?
               ORDER BY id DESC LIMIT ?""",
            (session_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Session artifacts — plan, tool_results, verdict (architecture.md §3.2)
# ---------------------------------------------------------------------------


def save_artifact(
    session_id: str,
    artifact_type: str,
    artifact: dict,
    run_id: Optional[str] = None,
) -> None:
    """Lưu 1 artifact (plan/tool_results/verdict) theo session và run.

    Mỗi lần re-plan hoặc tool trả kết quả mới tạo 1 bản ghi riêng để giữ
    đầy đủ audit trail như rubric yêu cầu.

    Args:
        session_id:    ID phiên.
        artifact_type: 'plan' | 'tool_results' | 'verdict'.
        artifact:      Dict cần lưu.
        run_id:        Liên kết với bảng runs (có thể None).
    """
    valid_types = {"plan", "tool_results", "verdict"}
    if artifact_type not in valid_types:
        raise ValueError(f"artifact_type phải là một trong {valid_types}")

    now = _now_iso()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO session_artifacts
               (session_id, run_id, artifact_type, artifact_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, run_id, artifact_type, json.dumps(artifact, ensure_ascii=False), now),
        )


def load_artifacts(
    session_id: str,
    artifact_type: Optional[str] = None,
    run_id: Optional[str] = None,
) -> list[dict]:
    """Đọc artifacts của 1 phiên, tùy chọn lọc theo loại hoặc run.

    Args:
        session_id:    ID phiên.
        artifact_type: Lọc theo loại ('plan'/'tool_results'/'verdict'). None = tất cả.
        run_id:        Lọc theo run cụ thể. None = tất cả.

    Returns:
        List[dict] với keys: id, run_id, artifact_type, artifact (dict), created_at.
    """
    query = "SELECT id, run_id, artifact_type, artifact_json, created_at FROM session_artifacts WHERE session_id = ?"
    params: list = [session_id]

    if artifact_type is not None:
        query += " AND artifact_type = ?"
        params.append(artifact_type)
    if run_id is not None:
        query += " AND run_id = ?"
        params.append(run_id)

    query += " ORDER BY id ASC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        {
            "id":            r["id"],
            "run_id":        r["run_id"],
            "artifact_type": r["artifact_type"],
            "artifact":      json.loads(r["artifact_json"]),
            "created_at":    r["created_at"],
        }
        for r in rows
    ]
