SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    format TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    indexed_at TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS daily_usage (
    telegram_user_id INTEGER NOT NULL,
    usage_date TEXT NOT NULL,
    query_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (telegram_user_id, usage_date)
);

CREATE TABLE IF NOT EXISTS query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL,
    tokens_input INTEGER,
    tokens_output INTEGER,
    sources_cited TEXT,
    latency_ms INTEGER,
    question_length INTEGER
);

CREATE INDEX IF NOT EXISTS idx_query_logs_user_ts ON query_logs (telegram_user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_query_logs_timestamp ON query_logs (timestamp);

CREATE TABLE IF NOT EXISTS query_details (
    query_log_id INTEGER PRIMARY KEY REFERENCES query_logs(id) ON DELETE CASCADE,
    question_text TEXT,
    question_hash TEXT NOT NULL,
    category TEXT NOT NULL,
    max_similarity REAL,
    topic_cluster TEXT
);

CREATE TABLE IF NOT EXISTS daily_stats (
    stats_date TEXT PRIMARY KEY,
    total_queries INTEGER NOT NULL DEFAULT 0,
    unique_users INTEGER NOT NULL DEFAULT 0,
    tokens_input INTEGER NOT NULL DEFAULT 0,
    tokens_output INTEGER NOT NULL DEFAULT 0,
    by_status TEXT NOT NULL DEFAULT '{}',
    by_category TEXT NOT NULL DEFAULT '{}',
    top_sources TEXT NOT NULL DEFAULT '[]',
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_type TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    anomalies_json TEXT,
    stats_snapshot TEXT NOT NULL,
    llm_tokens_used INTEGER,
    delivery_status TEXT NOT NULL DEFAULT 'pending',
    delivered_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_period
    ON analytics_reports (period_type, period_start);

CREATE TABLE IF NOT EXISTS anomaly_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at TEXT NOT NULL,
    stats_date TEXT NOT NULL,
    telegram_user_id INTEGER,
    anomaly_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    description TEXT NOT NULL,
    metadata_json TEXT,
    acknowledged INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_anomaly_date_user
    ON anomaly_flags (stats_date, telegram_user_id);

CREATE TABLE IF NOT EXISTS invites (
    id TEXT PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    label TEXT,
    created_by INTEGER NOT NULL,
    max_uses INTEGER NOT NULL DEFAULT 1,
    use_count INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registered_users (
    telegram_user_id INTEGER PRIMARY KEY,
    username TEXT,
    display_name TEXT,
    invite_id TEXT REFERENCES invites(id),
    registered_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    blocked_at TEXT,
    blocked_by INTEGER
);

CREATE TABLE IF NOT EXISTS invite_redemptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invite_id TEXT NOT NULL REFERENCES invites(id),
    telegram_user_id INTEGER NOT NULL,
    redeemed_at TEXT NOT NULL,
    UNIQUE (invite_id, telegram_user_id)
);

CREATE TABLE IF NOT EXISTS password_attempts (
    telegram_user_id INTEGER NOT NULL,
    invite_id TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    window_start TEXT NOT NULL,
    PRIMARY KEY (telegram_user_id, invite_id)
);

CREATE INDEX IF NOT EXISTS idx_invites_token ON invites (token);
CREATE INDEX IF NOT EXISTS idx_invites_status ON invites (status);
CREATE INDEX IF NOT EXISTS idx_registered_users_active ON registered_users (is_active);
"""
