import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from .docx_parser import extract_docx
from .ocr_vision import ocr_image
from .pdf_parser import MIN_CHARS_FOR_TEXT_LAYER, get_pdf_page_texts, render_pdf_pages_to_images
from .types import ExtractedDocument
from .xlsx_csv_parser import extract_csv, extract_xlsx

# .xls (legacy BIFF8) is intentionally excluded: openpyxl cannot read it and
# raises a non-ValueError exception, so a supported-but-broken format would
# either silently fail or 500 past the pipeline boundary. Revisit if xlrd is
# added.
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".csv"}

# OCR calls are I/O-bound network requests, so running them concurrently
# turns "N pages x up to 60s each" into roughly one call's worth of wall
# time instead of N. Sequential OCR of a real multi-page scanned document
# (an 8-page all-scanned BCTC) exceeded the deploy platform's gateway
# timeout in production (502), even though every individual OCR call
# succeeded - this is the fix for that.
MAX_OCR_CONCURRENCY = 12
# A hard cap on how many pages get OCR'd per document, so a pathological
# huge scan can't hang a request indefinitely regardless of concurrency.
MAX_OCR_PAGES = 30


def extract_document(file_path: str, filename: str) -> ExtractedDocument:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Định dạng file không được hỗ trợ: {ext}")

    if ext == ".pdf":
        return _extract_pdf_document(file_path, filename)
    if ext == ".docx":
        return extract_docx(file_path, filename)
    if ext == ".xlsx":
        return extract_xlsx(file_path, filename)
    return extract_csv(file_path, filename)  # ext == ".csv"


def _extract_pdf_document(file_path: str, filename: str) -> ExtractedDocument:
    page_texts = get_pdf_page_texts(file_path)
    n_pages = len(page_texts)
    ocr_needed_idx = [i for i, t in enumerate(page_texts) if len(t.strip()) < MIN_CHARS_FOR_TEXT_LAYER]

    if not ocr_needed_idx:
        text = "\n".join(f"[Trang {i + 1}]\n{t}" for i, t in enumerate(page_texts))
        return ExtractedDocument(
            filename=filename,
            doc_type="pdf",
            text=text,
            tables=[],
            extraction_method="text_layer",
            confidence=1.0,
            warnings=[],
        )

    warnings: list[str] = []
    if len(ocr_needed_idx) > MAX_OCR_PAGES:
        skipped = len(ocr_needed_idx) - MAX_OCR_PAGES
        warnings.append(
            f"Vượt giới hạn OCR tối đa ({MAX_OCR_PAGES} trang) — đã bỏ qua {skipped} trang cuối."
        )
        ocr_needed_idx = ocr_needed_idx[:MAX_OCR_PAGES]

    try:
        images = render_pdf_pages_to_images(file_path)
    except ValueError as exc:
        images = []
        warnings.append(str(exc))

    final_texts = list(page_texts)
    ocr_success_idx: list[int] = []
    pages_to_ocr = [i for i in ocr_needed_idx if i < len(images)]
    if pages_to_ocr:
        with ThreadPoolExecutor(max_workers=min(MAX_OCR_CONCURRENCY, len(pages_to_ocr))) as executor:
            future_to_idx = {executor.submit(ocr_image, images[i]): i for i in pages_to_ocr}
            for future in as_completed(future_to_idx):
                i = future_to_idx[future]
                try:
                    final_texts[i] = future.result()
                    ocr_success_idx.append(i)
                except Exception as exc:  # noqa: BLE001 - one page's OCR failure must not sink the batch
                    warnings.append(f"OCR trang {i + 1} thất bại: {exc}")

    text = "\n".join(f"[Trang {i + 1}]\n{t}" for i, t in enumerate(final_texts))
    all_pages_needed_ocr = len(ocr_needed_idx) == n_pages
    ocr_success_count = len(ocr_success_idx)

    if ocr_success_count == 0:
        method = "ocr_failed" if all_pages_needed_ocr else "mixed"
        confidence = 0.0
    elif all_pages_needed_ocr and ocr_success_count == n_pages:
        method = "vision_llm"
        confidence = 0.7
    else:
        method = "mixed"
        confidence = round(0.7 * ocr_success_count / len(ocr_needed_idx), 2)

    return ExtractedDocument(
        filename=filename,
        doc_type="pdf",
        text=text,
        tables=[],
        extraction_method=method,
        confidence=confidence,
        warnings=warnings,
    )


def extract_documents(files: list[tuple[str, str]]) -> list[ExtractedDocument]:
    return [extract_document(path, name) for path, name in files]
