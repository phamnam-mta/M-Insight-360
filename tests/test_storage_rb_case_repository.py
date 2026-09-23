from app.storage.db import init_db
from app.storage.rb_case_repository import (
    add_document, create_case, get_case, list_assessment_versions, list_cases,
    list_documents, log_audit, save_assessment_version, update_case_section,
    update_case_status, update_document_status,
)


def test_create_and_get_case(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-0100000001-abc123", "NGUYEN VAN A", "0100000001")
    case = get_case(db_path, "RB-0100000001-abc123")
    assert case["case_id"] == "RB-0100000001-abc123"
    assert case["status"] == "RECEIVED"
    assert case["customer"] is None
    assert case["legal"] is None


def test_get_case_returns_none_for_unknown_id(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    assert get_case(db_path, "RB-NOPE") is None


def test_update_case_section_persists_and_merges(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    update_case_section(db_path, "RB-1", "customer", {"full_name": "A", "gender": "male"})
    case = get_case(db_path, "RB-1")
    assert case["customer"] == {"full_name": "A", "gender": "male"}

    update_case_section(db_path, "RB-1", "income", {"source_type": "business"})
    case = get_case(db_path, "RB-1")
    assert case["income"] == {"source_type": "business"}
    # customer section from the earlier PATCH must still be there
    assert case["customer"] == {"full_name": "A", "gender": "male"}


def test_update_case_status_persists(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    update_case_status(db_path, "RB-1", "DOCS_ANALYZED")
    assert get_case(db_path, "RB-1")["status"] == "DOCS_ANALYZED"


def test_update_case_section_rejects_unknown_section(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    try:
        update_case_section(db_path, "RB-1", "bogus", {})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_list_cases_orders_newest_first(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    create_case(db_path, "RB-2", "B", "222")
    cases = list_cases(db_path)
    assert [c["case_id"] for c in cases] == ["RB-2", "RB-1"]


def test_add_and_list_documents(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    doc_id = add_document(
        db_path, "RB-1", "file1", "cccd.pdf", "LEGAL", "LEGAL_IDENTITY",
        "application/pdf", 1024, "/data/RB-1/file1__cccd.pdf",
    )
    assert doc_id > 0
    docs = list_documents(db_path, "RB-1")
    assert len(docs) == 1
    assert docs[0]["filename"] == "cccd.pdf"
    assert docs[0]["status"] == "UPLOADED"

    update_document_status(db_path, "RB-1", "file1", "EXTRACTED")
    docs = list_documents(db_path, "RB-1")
    assert docs[0]["status"] == "EXTRACTED"


def test_save_and_list_assessment_versions_increment(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    v1 = save_assessment_version(db_path, "RB-1", "PRELIMINARY", {"recommendation": "INSUFFICIENT_DATA"})
    v2 = save_assessment_version(db_path, "RB-1", "PRELIMINARY", {"recommendation": "PRELIMINARY_READY"})
    assert v2 == v1 + 1
    versions = list_assessment_versions(db_path, "RB-1")
    assert [v["version"] for v in versions] == [2, 1]
    assert versions[0]["computed"]["recommendation"] == "PRELIMINARY_READY"


def test_log_audit_records_action(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    log_audit(db_path, "RB-1", "CASE_CREATED", "customer=A")
    from app.storage.db import get_connection
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM rb_case_audit WHERE case_id = 'RB-1'").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["actor"] == "RM"
    assert rows[0]["action"] == "CASE_CREATED"
