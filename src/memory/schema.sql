-- SQLite schema — Procurement Intelligence & Negotiation Agent
-- Owner: Nguoi A
-- Theo SYSTEM-RULES.md §2.1 — State Schema

-- ─────────────────────────────────────────────────────────────────────────────
-- Bảng chính: mỗi phiên hội thoại = 1 row
-- state_json lưu toàn bộ state theo đúng format SYSTEM-RULES §2.1
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL,   -- ISO 8601
    updated_at   TEXT NOT NULL,   -- ISO 8601, cập nhật mỗi khi state thay đổi
    state_json   TEXT NOT NULL    -- JSON blob theo schema §2.1
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Lịch sử hội thoại từng turn
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversation_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    role         TEXT NOT NULL CHECK(role IN ('user', 'agent')),
    content      TEXT NOT NULL,
    timestamp    TEXT NOT NULL,   -- ISO 8601
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Các quyết định đã chốt (chọn NCC)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS decisions_made (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    supplier_id  TEXT NOT NULL,
    confirmed_at TEXT NOT NULL,   -- ISO 8601
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Metrics mỗi request — nguồn số liệu cho AutoEval và báo cáo hiệu năng
-- architecture.md §3.2 và §5.5
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL UNIQUE,   -- UUID hex
    session_id   TEXT NOT NULL,
    trace_id     TEXT,                   -- từ tracer.py (new_trace_id())
    intent       TEXT,                   -- search_new|compare_specific|supplier_detail|out_of_scope
    status       TEXT NOT NULL DEFAULT 'running',
                                         -- running|success|graceful_fail|error
    llm_calls    INTEGER NOT NULL DEFAULT 0,
    tool_calls   INTEGER NOT NULL DEFAULT 0,
    tokens_in    INTEGER NOT NULL DEFAULT 0,
    tokens_out   INTEGER NOT NULL DEFAULT 0,
    latency_ms   REAL,                   -- end-to-end latency (ms)
    ttft_ms      REAL,                   -- time to first token (ms), NULL nếu không stream
    started_at   TEXT NOT NULL,          -- ISO 8601
    finished_at  TEXT,                   -- ISO 8601, NULL khi đang chạy
    error_msg    TEXT                    -- nếu status=error
    -- Không dùng FK → sessions để runs có thể ghi khi session chưa lưu DB
    -- (AutoEval, load test). Xóa sạch trong delete_session() bằng tay.
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Artifacts theo session: plan, tool_results, verdict để truy vết
-- architecture.md §3.2
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS session_artifacts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    run_id        TEXT,                  -- liên kết với bảng runs (nullable)
    artifact_type TEXT NOT NULL,         -- 'plan' | 'tool_results' | 'verdict'
    artifact_json TEXT NOT NULL,         -- JSON blob
    created_at    TEXT NOT NULL          -- ISO 8601
    -- Không dùng FK → sessions để artifact có thể ghi độc lập với session lifecycle
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Index để tăng tốc query theo session
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_conv_session      ON conversation_history(session_id);
CREATE INDEX IF NOT EXISTS idx_dec_session       ON decisions_made(session_id);
CREATE INDEX IF NOT EXISTS idx_runs_session      ON runs(session_id);
CREATE INDEX IF NOT EXISTS idx_runs_run_id       ON runs(run_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_session ON session_artifacts(session_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_run     ON session_artifacts(run_id);
