import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_type TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    tax_id TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS case_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT,
    size_bytes INTEGER NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    storage_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eb_stress_scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    report_period TEXT,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rb_cases (
    case_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'RECEIVED',
    customer_name TEXT NOT NULL,
    tax_id TEXT NOT NULL,
    customer_json TEXT,
    legal_json TEXT,
    income_json TEXT,
    loan_json TEXT,
    collateral_json TEXT,
    other_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rb_case_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    category TEXT NOT NULL,
    document_type TEXT,
    status TEXT NOT NULL DEFAULT 'UPLOADED',
    content_type TEXT,
    size_bytes INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rb_case_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    kind TEXT NOT NULL,
    computed_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rb_case_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'RM',
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(assessments)")}
        if "case_id" not in cols:
            conn.execute("ALTER TABLE assessments ADD COLUMN case_id TEXT")
        conn.commit()
    finally:
        conn.close()
