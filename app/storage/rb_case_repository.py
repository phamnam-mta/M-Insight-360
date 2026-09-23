import json

from .db import get_connection

_SECTIONS = {"customer", "legal", "income", "loan", "collateral", "other"}


def create_case(db_path: str, case_id: str, customer_name: str, tax_id: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO rb_cases (case_id, customer_name, tax_id) VALUES (?, ?, ?)",
            (case_id, customer_name, tax_id),
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_case(row) -> dict:
    return {
        "case_id": row["case_id"],
        "status": row["status"],
        "customer_name": row["customer_name"],
        "tax_id": row["tax_id"],
        "customer": json.loads(row["customer_json"]) if row["customer_json"] else None,
        "legal": json.loads(row["legal_json"]) if row["legal_json"] else None,
        "income": json.loads(row["income_json"]) if row["income_json"] else None,
        "loan": json.loads(row["loan_json"]) if row["loan_json"] else None,
        "collateral": json.loads(row["collateral_json"]) if row["collateral_json"] else None,
        "other": json.loads(row["other_json"]) if row["other_json"] else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_case(db_path: str, case_id: str) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM rb_cases WHERE case_id = ?", (case_id,)).fetchone()
        return _row_to_case(row) if row else None
    finally:
        conn.close()


def list_cases(db_path: str, limit: int = 20) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM rb_cases ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_case(r) for r in rows]
    finally:
        conn.close()


def update_case_status(db_path: str, case_id: str, status: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE rb_cases SET status = ?, updated_at = datetime('now') WHERE case_id = ?",
            (status, case_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_case_section(db_path: str, case_id: str, section: str, data: dict) -> None:
    if section not in _SECTIONS:
        raise ValueError(f"unknown section: {section}")
    conn = get_connection(db_path)
    try:
        conn.execute(
            f"UPDATE rb_cases SET {section}_json = ?, updated_at = datetime('now') WHERE case_id = ?",
            (json.dumps(data, ensure_ascii=False), case_id),
        )
        conn.commit()
    finally:
        conn.close()


def add_document(
    db_path: str, case_id: str, file_id: str, filename: str, category: str,
    document_type: str | None, content_type: str | None, size_bytes: int, storage_path: str,
) -> int:
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO rb_case_documents "
            "(case_id, file_id, filename, category, document_type, content_type, size_bytes, storage_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (case_id, file_id, filename, category, document_type, content_type, size_bytes, storage_path),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_document_status(db_path: str, case_id: str, file_id: str, status: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE rb_case_documents SET status = ? WHERE case_id = ? AND file_id = ?",
            (status, case_id, file_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_documents(db_path: str, case_id: str) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM rb_case_documents WHERE case_id = ? ORDER BY uploaded_at", (case_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_assessment_version(db_path: str, case_id: str, kind: str, computed: dict) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT MAX(version) AS m FROM rb_case_assessments WHERE case_id = ?", (case_id,)
        ).fetchone()
        next_version = (row["m"] or 0) + 1
        conn.execute(
            "INSERT INTO rb_case_assessments (case_id, version, kind, computed_json) VALUES (?, ?, ?, ?)",
            (case_id, next_version, kind, json.dumps(computed, ensure_ascii=False)),
        )
        conn.commit()
        return next_version
    finally:
        conn.close()


def list_assessment_versions(db_path: str, case_id: str) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM rb_case_assessments WHERE case_id = ? ORDER BY version DESC", (case_id,)
        ).fetchall()
        return [
            {"version": r["version"], "kind": r["kind"], "computed": json.loads(r["computed_json"]),
             "created_at": r["created_at"]}
            for r in rows
        ]
    finally:
        conn.close()


def log_audit(db_path: str, case_id: str, action: str, detail: str = "") -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO rb_case_audit (case_id, action, detail) VALUES (?, ?, ?)",
            (case_id, action, detail),
        )
        conn.commit()
    finally:
        conn.close()
