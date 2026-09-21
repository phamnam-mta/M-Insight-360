import os

from .docx_parser import extract_docx
from .ocr_vision import ocr_image
from .pdf_parser import extract_pdf, render_pdf_pages_to_images
from .types import ExtractedDocument
from .xlsx_csv_parser import extract_csv, extract_xlsx

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".csv"}


def extract_document(file_path: str, filename: str) -> ExtractedDocument:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Định dạng file không được hỗ trợ: {ext}")

    if ext == ".pdf":
        doc = extract_pdf(file_path, filename)
        if doc.extraction_method == "no_text_layer":
            return _ocr_pdf(file_path, filename, doc)
        return doc
    if ext == ".docx":
        return extract_docx(file_path, filename)
    if ext in (".xlsx", ".xls"):
        return extract_xlsx(file_path, filename)
    return extract_csv(file_path, filename)  # ext == ".csv"


def _ocr_pdf(file_path: str, filename: str, base_doc: ExtractedDocument) -> ExtractedDocument:
    images = render_pdf_pages_to_images(file_path)
    texts: list[str] = []
    warnings = list(base_doc.warnings)
    for i, image_bytes in enumerate(images):
        try:
            texts.append(ocr_image(image_bytes))
        except Exception as exc:  # noqa: BLE001 - deliberately broad: one page must not sink the batch
            warnings.append(f"OCR trang {i + 1} thất bại: {exc}")

    return ExtractedDocument(
        filename=filename,
        doc_type="pdf",
        text="\n".join(texts),
        tables=[],
        extraction_method="vision_llm" if texts else "ocr_failed",
        confidence=0.7 if texts else 0.0,
        warnings=warnings,
    )


def extract_documents(files: list[tuple[str, str]]) -> list[ExtractedDocument]:
    return [extract_document(path, name) for path, name in files]
