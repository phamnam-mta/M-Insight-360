import pytest

from app.extraction import pipeline


def test_extract_document_routes_docx(fixtures_dir):
    doc = pipeline.extract_document(str(fixtures_dir / "sample.docx"), "sample.docx")
    assert doc.doc_type == "docx"


def test_extract_document_routes_xlsx(fixtures_dir):
    doc = pipeline.extract_document(str(fixtures_dir / "sample.xlsx"), "sample.xlsx")
    assert doc.doc_type == "xlsx"


def test_extract_document_routes_csv(fixtures_dir):
    doc = pipeline.extract_document(str(fixtures_dir / "sample.csv"), "sample.csv")
    assert doc.doc_type == "csv"


def test_extract_document_pdf_with_text_layer_skips_ocr(fixtures_dir):
    doc = pipeline.extract_document(str(fixtures_dir / "sample_text.pdf"), "sample_text.pdf")
    assert doc.extraction_method == "text_layer"


def test_extract_document_rejects_unsupported_extension(fixtures_dir, tmp_path):
    bogus = tmp_path / "photo.jpg"
    bogus.write_bytes(b"not a real jpg")
    with pytest.raises(ValueError, match="không được hỗ trợ"):
        pipeline.extract_document(str(bogus), "photo.jpg")


def test_extract_document_scanned_pdf_falls_back_to_ocr(fixtures_dir, monkeypatch):
    calls = []

    def fake_ocr_image(image_bytes, model=None):
        calls.append(image_bytes)
        return "Noi dung da OCR tu anh"

    monkeypatch.setattr(pipeline, "ocr_image", fake_ocr_image)

    doc = pipeline.extract_document(str(fixtures_dir / "sample_scanned.pdf"), "sample_scanned.pdf")
    assert doc.extraction_method == "vision_llm"
    assert "Noi dung da OCR tu anh" in doc.text
    assert len(calls) == 1


def test_extract_document_scanned_pdf_ocr_failure_is_captured_as_warning(fixtures_dir, monkeypatch):
    def failing_ocr_image(image_bytes, model=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(pipeline, "ocr_image", failing_ocr_image)

    doc = pipeline.extract_document(str(fixtures_dir / "sample_scanned.pdf"), "sample_scanned.pdf")
    assert doc.extraction_method == "ocr_failed"
    assert any("network down" in w for w in doc.warnings)


def test_extract_documents_processes_a_batch(fixtures_dir):
    files = [
        (str(fixtures_dir / "sample.docx"), "sample.docx"),
        (str(fixtures_dir / "sample.csv"), "sample.csv"),
    ]
    docs = pipeline.extract_documents(files)
    assert [d.doc_type for d in docs] == ["docx", "csv"]


def test_extract_document_mixed_pdf_keeps_digital_page_and_ocrs_scanned_page(fixtures_dir, monkeypatch):
    calls = []

    def fake_ocr_image(image_bytes, model=None):
        calls.append(image_bytes)
        return "Noi dung trang scan da OCR"

    monkeypatch.setattr(pipeline, "ocr_image", fake_ocr_image)

    doc = pipeline.extract_document(str(fixtures_dir / "sample_mixed.pdf"), "sample_mixed.pdf")
    assert "Trang mot co chu that" in doc.text
    assert "Noi dung trang scan da OCR" in doc.text
    assert doc.extraction_method == "mixed"
    assert len(calls) == 1
    assert doc.warnings == []


def test_extract_document_two_page_scan_partial_ocr_failure_keeps_other_page(fixtures_dir, monkeypatch):
    call_count = {"n": 0}

    def flaky_ocr_image(image_bytes, model=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "Trang 1 scan OCR thanh cong"
        raise RuntimeError("network down")

    monkeypatch.setattr(pipeline, "ocr_image", flaky_ocr_image)

    doc = pipeline.extract_document(str(fixtures_dir / "sample_scanned_2page.pdf"), "sample_scanned_2page.pdf")
    assert "Trang 1 scan OCR thanh cong" in doc.text
    assert any("network down" in w for w in doc.warnings)
    assert doc.extraction_method == "mixed"
    assert call_count["n"] == 2
    assert 0.0 < doc.confidence < 0.7  # proportional to the 1-of-2 pages that actually succeeded
