"""Memory module — quản lý state qua SQLite.

Owner: Nguoi A

Cung cấp:
- init_db()            : tạo bảng theo schema.sql
- save_session()       : upsert toàn bộ state (ghi đè nếu đã tồn tại)
- load_session()       : load state theo session_id
- append_conversation(): ghi thêm 1 turn hội thoại
- save_decision()      : ghi nhận NCC đã được chốt
- load_decisions()     : lấy danh sách NCC đã chốt trong phiên
"""

import json
import sqlite3
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
