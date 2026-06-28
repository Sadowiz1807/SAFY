AUDIT_SCHEMA_VERSION = 2

AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    component TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    actor_type TEXT,
    actor_id TEXT,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    risk_level TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    request_id TEXT,
    check_id TEXT,
    sql_hash TEXT,
    error_code TEXT,
    error_message TEXT,
    repair_status TEXT,
    repair_reason TEXT,
    repair_attempt_count INTEGER DEFAULT 0,
    repair_last_error TEXT,
    metadata_json TEXT NOT NULL
);
"""
