CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    created_at   TEXT
);

CREATE TABLE IF NOT EXISTS constraints (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT,
    type         TEXT,     -- 'hard' hoac 'soft'
    field        TEXT,     -- vd: 'budget', 'material', 'delivery_deadline'
    value        TEXT,
    updated_at   TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS conversation_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT,
    role         TEXT,     -- 'user' hoac 'agent'
    content      TEXT,
    timestamp    TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
