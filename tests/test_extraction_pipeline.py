import threading
import time

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
    # OCR calls now run concurrently, so which page's call lands first is not
    # deterministic - key success/failure off "first call to arrive" (lock-
    # protected) instead of assuming page order, and assert on the outcome
    # (one success text present, one failure warning present) rather than on
    # which page number did which.
    lock = threading.Lock()
    call_count = {"n": 0}

    def flaky_ocr_image(image_bytes, model=None):
        with lock:
            call_count["n"] += 1
            first = call_count["n"] == 1
        if first:
            return "Trang scan OCR thanh cong"
        raise RuntimeError("network down")

    monkeypatch.setattr(pipeline, "ocr_image", flaky_ocr_image)

    doc = pipeline.extract_document(str(fixtures_dir / "sample_scanned_2page.pdf"), "sample_scanned_2page.pdf")
    assert "Trang scan OCR thanh cong" in doc.text
    assert any("network down" in w for w in doc.warnings)
    assert doc.extraction_method == "mixed"
    assert call_count["n"] == 2
    assert 0.0 < doc.confidence < 0.7  # proportional to the 1-of-2 pages that actually succeeded


def test_extract_document_ocr_pages_run_concurrently_not_sequentially(fixtures_dir, monkeypatch):
    # The real bug this proves fixed: an 8-page all-scanned PDF calling OCR
    # sequentially at up to 60s/page can exceed the deploy platform's gateway
    # timeout (502), even though each individual call succeeds. If pages ran
    # truly one-at-a-time, 8 pages x 0.2s would take >= 1.6s; run
    # concurrently, it should take a small fraction of that.
    PAGE_SLEEP = 0.2

    def slow_ocr_image(image_bytes, model=None):
        time.sleep(PAGE_SLEEP)
        return "OCR ok"

    monkeypatch.setattr(pipeline, "ocr_image", slow_ocr_image)

    start = time.monotonic()
    doc = pipeline.extract_document(str(fixtures_dir / "sample_scanned_8page.pdf"), "sample_scanned_8page.pdf")
    elapsed = time.monotonic() - start

    assert doc.extraction_method == "vision_llm"
    assert elapsed < PAGE_SLEEP * 8 * 0.6  # comfortably less than sequential would take
    assert doc.warnings == []


def test_extract_document_caps_ocr_pages_and_warns_instead_of_processing_unbounded(fixtures_dir, monkeypatch):
    calls = []

    def fake_ocr_image(image_bytes, model=None):
        calls.append(image_bytes)
        return "OCR ok"

    monkeypatch.setattr(pipeline, "ocr_image", fake_ocr_image)

    doc = pipeline.extract_document(str(fixtures_dir / "sample_scanned_35page.pdf"), "sample_scanned_35page.pdf")
    assert len(calls) == pipeline.MAX_OCR_PAGES
    assert any("gioi han" in w.lower() or "giới hạn" in w for w in doc.warnings)
