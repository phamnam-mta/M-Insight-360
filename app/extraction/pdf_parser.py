import fitz  # pymupdf

from .types import ExtractedDocument

MIN_CHARS_FOR_TEXT_LAYER = 20


def get_pdf_page_texts(file_path: str) -> list[str]:
    try:
        doc = fitz.open(file_path)
    except Exception as exc:  # noqa: BLE001 - corrupt/mislabeled files raise library-specific errors
        raise ValueError(f"Không thể đọc file PDF (có thể bị hỏng hoặc sai định dạng): {exc}") from exc
    try:
        return [page.get_text() for page in doc]
    finally:
        doc.close()


def extract_pdf(file_path: str, filename: str) -> ExtractedDocument:
    text = "\n".join(get_pdf_page_texts(file_path))

    has_text_layer = len(text.strip()) >= MIN_CHARS_FOR_TEXT_LAYER
    return ExtractedDocument(
        filename=filename,
        doc_type="pdf",
        text=text,
        tables=[],
        extraction_method="text_layer" if has_text_layer else "no_text_layer",
        confidence=1.0 if has_text_layer else 0.0,
        warnings=[] if has_text_layer else [
            "PDF không có lớp chữ (đã raster hoá hoặc là ảnh scan) — cần chạy OCR."
        ],
    )


def render_pdf_pages_to_images(file_path: str, dpi: int = 150) -> list[bytes]:
    try:
        doc = fitz.open(file_path)
    except Exception as exc:  # noqa: BLE001 - corrupt/mislabeled files raise library-specific errors
        raise ValueError(f"Không thể đọc file PDF (có thể bị hỏng hoặc sai định dạng): {exc}") from exc
    try:
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            images.append(pix.tobytes("png"))
        return images
    finally:
        doc.close()
