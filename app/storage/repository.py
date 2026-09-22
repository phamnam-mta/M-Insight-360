import json

from .db import get_connection


def save_assessment(
    db_path: str, agent_type: str, customer_name: str, tax_id: str, result: dict
) -> int:
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO assessments (agent_type, customer_name, tax_id, result_json) "
            "VALUES (?, ?, ?, ?)",
            (agent_type, customer_name, tax_id, json.dumps(result, ensure_ascii=False)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_recent_assessments(db_path: str, agent_type: str, limit: int = 5) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM assessments WHERE agent_type = ? ORDER BY id DESC LIMIT ?",
            (agent_type, limit),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "agent_type": row["agent_type"],
                "customer_name": row["customer_name"],
                "tax_id": row["tax_id"],
                "result": json.loads(row["result_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_latest_assessment(db_path: str, agent_type: str) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM assessments WHERE agent_type = ? ORDER BY id DESC LIMIT 1",
            (agent_type,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "agent_type": row["agent_type"],
            "customer_name": row["customer_name"],
            "tax_id": row["tax_id"],
            "result": json.loads(row["result_json"]),
            "created_at": row["created_at"],
        }
    finally:
        conn.close()
