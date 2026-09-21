import pytest

from app.extraction.pdf_parser import extract_pdf, get_pdf_page_texts, render_pdf_pages_to_images


def test_extract_pdf_with_text_layer(fixtures_dir):
    doc = extract_pdf(str(fixtures_dir / "sample_text.pdf"), "sample_text.pdf")
    assert "MSB CREDITPILOT TEST DOCUMENT" in doc.text
    assert doc.extraction_method == "text_layer"
    assert doc.confidence == 1.0
    assert doc.warnings == []


def test_extract_pdf_without_text_layer_flags_no_text_layer(fixtures_dir):
    doc = extract_pdf(str(fixtures_dir / "sample_scanned.pdf"), "sample_scanned.pdf")
    assert doc.extraction_method == "no_text_layer"
    assert doc.confidence == 0.0
    assert any("raster" in w.lower() or "ocr" in w.lower() for w in doc.warnings)


def test_render_pdf_pages_to_images_returns_one_png_per_page(fixtures_dir):
    images = render_pdf_pages_to_images(str(fixtures_dir / "sample_scanned.pdf"))
    assert len(images) == 1
    assert images[0][:8] == b"\x89PNG\r\n\x1a\n"  # PNG file signature


def test_get_pdf_page_texts_returns_one_entry_per_page(fixtures_dir):
    texts = get_pdf_page_texts(str(fixtures_dir / "sample_mixed.pdf"))
    assert len(texts) == 2
    assert "Trang mot co chu that" in texts[0]
    assert texts[1].strip() == ""


def test_extract_pdf_raises_value_error_on_corrupt_file(tmp_path):
    bogus = tmp_path / "corrupt.pdf"
    bogus.write_bytes(b"not a real pdf at all")
    with pytest.raises(ValueError, match="PDF"):
        extract_pdf(str(bogus), "corrupt.pdf")
