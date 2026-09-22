from app.storage.db import init_db
from app.storage.repository import list_recent_assessments, save_assessment


def _db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def test_list_recent_assessments_returns_newest_first(tmp_path):
    db_path = _db_path(tmp_path)
    save_assessment(db_path, "eb", "Cong ty A", "0100000001", {"credit_readiness": "READY"})
    save_assessment(db_path, "eb", "Cong ty B", "0100000002", {"credit_readiness": "NOT_READY"})

    items = list_recent_assessments(db_path, "eb")
    assert len(items) == 2
    assert items[0]["customer_name"] == "Cong ty B"
    assert items[1]["customer_name"] == "Cong ty A"


def test_list_recent_assessments_filters_by_agent_type(tmp_path):
    db_path = _db_path(tmp_path)
    save_assessment(db_path, "eb", "Cong ty A", "0100000001", {})
    save_assessment(db_path, "rb", "Ong B", "0100000002", {})

    items = list_recent_assessments(db_path, "eb")
    assert len(items) == 1
    assert items[0]["customer_name"] == "Cong ty A"


def test_list_recent_assessments_respects_limit(tmp_path):
    db_path = _db_path(tmp_path)
    for i in range(7):
        save_assessment(db_path, "eb", f"Cong ty {i}", "0100000001", {})

    items = list_recent_assessments(db_path, "eb", limit=3)
    assert len(items) == 3
    assert items[0]["customer_name"] == "Cong ty 6"


def test_list_recent_assessments_empty_when_none_saved(tmp_path):
    db_path = _db_path(tmp_path)
    assert list_recent_assessments(db_path, "eb") == []


def test_list_recent_assessments_includes_result_and_created_at(tmp_path):
    db_path = _db_path(tmp_path)
    save_assessment(db_path, "eb", "Cong ty A", "0100000001", {"credit_readiness": "READY"})

    items = list_recent_assessments(db_path, "eb")
    assert items[0]["result"] == {"credit_readiness": "READY"}
    assert items[0]["created_at"]
    assert items[0]["tax_id"] == "0100000001"
