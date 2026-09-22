from pathlib import Path

from app.storage.files import get_case_file_path, save_case_file


def test_save_and_read_back_file(tmp_path):
    base_dir = str(tmp_path / "eb_files")
    path = save_case_file(base_dir, "EB-001-abcd1234", "f1", "bctc.pdf", b"%PDF-1.4 fake content")
    assert Path(path).exists()
    assert Path(path).read_bytes() == b"%PDF-1.4 fake content"


def test_get_case_file_path_resolves_saved_file(tmp_path):
    base_dir = str(tmp_path / "eb_files")
    save_case_file(base_dir, "EB-001-abcd1234", "f1", "bctc.pdf", b"content")
    resolved = get_case_file_path(base_dir, "EB-001-abcd1234", "f1", "bctc.pdf")
    assert resolved is not None
    assert resolved.read_bytes() == b"content"


def test_get_case_file_path_returns_none_for_unknown_file(tmp_path):
    base_dir = str(tmp_path / "eb_files")
    assert get_case_file_path(base_dir, "EB-001-abcd1234", "missing", "x.pdf") is None
