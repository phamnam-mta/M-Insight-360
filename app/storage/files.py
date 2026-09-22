from pathlib import Path

from .db import get_connection


def _case_dir(base_dir: str, case_id: str) -> Path:
    return Path(base_dir) / case_id


def save_case_file(base_dir: str, case_id: str, file_id: str, filename: str, content: bytes) -> str:
    case_dir = _case_dir(base_dir, case_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    path = case_dir / f"{file_id}__{filename}"
    path.write_bytes(content)
    return str(path)


def get_case_file_path(base_dir: str, case_id: str, file_id: str, filename: str) -> Path | None:
    path = _case_dir(base_dir, case_id) / f"{file_id}__{filename}"
    return path if path.exists() else None


def record_case_file(
    db_path: str, case_id: str, file_id: str, filename: str,
    content_type: str | None, size_bytes: int, storage_path: str,
) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO case_files (case_id, file_id, filename, content_type, size_bytes, storage_path) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (case_id, file_id, filename, content_type, size_bytes, storage_path),
        )
        conn.commit()
    finally:
        conn.close()
