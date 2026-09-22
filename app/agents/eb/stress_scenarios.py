import json

from app.storage.db import get_connection


def save_scenario(
    db_path: str, case_id: str, name: str, created_by: str,
    report_period: str | None, request: dict, response: dict,
) -> int:
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO eb_stress_scenarios (case_id, name, created_by, report_period, request_json, response_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (case_id, name, created_by, report_period, json.dumps(request, ensure_ascii=False), json.dumps(response, ensure_ascii=False)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_scenarios(db_path: str, case_id: str) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM eb_stress_scenarios WHERE case_id = ? ORDER BY id DESC", (case_id,),
        ).fetchall()
        return [
            {
                "id": row["id"], "case_id": row["case_id"], "name": row["name"],
                "created_by": row["created_by"], "created_at": row["created_at"],
                "report_period": row["report_period"],
                "request": json.loads(row["request_json"]), "response": json.loads(row["response_json"]),
            }
            for row in rows
        ]
    finally:
        conn.close()
