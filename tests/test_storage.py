import threading

from app.storage.db import get_connection, init_db
from app.storage.repository import get_latest_assessment, save_assessment


def test_save_and_get_latest_assessment(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    save_assessment(db_path, "rb", "CONG TY A", "0100000001", {"recommendation": "PROCEED_FOR_HUMAN_REVIEW"})
    second_id = save_assessment(
        db_path, "rb", "CONG TY A", "0100000001", {"recommendation": "ADDITIONAL_DOCUMENTS_REQUIRED"}
    )

    latest = get_latest_assessment(db_path, "rb")
    assert latest is not None
    assert latest["id"] == second_id
    assert latest["result"]["recommendation"] == "ADDITIONAL_DOCUMENTS_REQUIRED"
    assert latest["customer_name"] == "CONG TY A"


def test_get_latest_assessment_returns_none_when_empty(tmp_path):
    db_path = str(tmp_path / "empty.db")
    init_db(db_path)
    assert get_latest_assessment(db_path, "eb") is None


def test_agent_types_are_isolated(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    save_assessment(db_path, "rb", "KH RB", "111", {"x": 1})
    assert get_latest_assessment(db_path, "eb") is None


def test_concurrent_writes_do_not_corrupt_or_lose_rows(tmp_path):
    db_path = str(tmp_path / "concurrent.db")
    init_db(db_path)
    n_writers = 10
    errors = []

    def write(i: int) -> None:
        try:
            save_assessment(db_path, "rb", f"KH {i}", str(i), {"seq": i})
        except Exception as exc:  # noqa: BLE001 - captured for the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(i,)) for i in range(n_writers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    conn = get_connection(db_path)
    row = conn.execute("SELECT COUNT(*) AS c FROM assessments").fetchone()
    assert row["c"] == n_writers
    conn.close()
