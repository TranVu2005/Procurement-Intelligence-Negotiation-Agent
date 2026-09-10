-- SQLite schema — Procurement Intelligence & Negotiation Agent
-- Owner: Nguoi A
-- Theo SYSTEM-RULES.md §2.1 — State Schema

-- Bảng chính: mỗi phiên hội thoại = 1 row
-- state_json lưu toàn bộ state theo đúng format SYSTEM-RULES §2.1
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL,   -- ISO 8601
    updated_at   TEXT NOT NULL,   -- ISO 8601, cập nhật mỗi khi state thay đổi
    state_json   TEXT NOT NULL    -- JSON blob theo schema §2.1
);

-- Lịch sử hội thoại từng turn
CREATE TABLE IF NOT EXISTS conversation_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    role         TEXT NOT NULL CHECK(role IN ('user', 'agent')),
    content      TEXT NOT NULL,
    timestamp    TEXT NOT NULL,   -- ISO 8601
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Các quyết định đã chốt (chọn NCC)
CREATE TABLE IF NOT EXISTS decisions_made (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    supplier_id  TEXT NOT NULL,
    confirmed_at TEXT NOT NULL,   -- ISO 8601
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Index để tăng tốc query theo session
CREATE INDEX IF NOT EXISTS idx_conv_session ON conversation_history(session_id);
CREATE INDEX IF NOT EXISTS idx_dec_session  ON decisions_made(session_id);
