import os
import tempfile

from fastapi import APIRouter, File, Form, UploadFile

from app.config import get_settings
from app.extraction.pipeline import extract_document
from app.storage.repository import save_assessment

from .assembler import assemble_response
from .statement_parser import any_table_has_simulated_balance_marker, parse_statement_documents

router = APIRouter(prefix="/api/crosssell", tags=["crosssell"])


@router.post("/assess")
async def assess(
    customer_name: str = Form(...),
    tax_id: str = Form(...),
    files: list[UploadFile] = File(...),
    opening_balance: float | None = Form(default=None),
    closing_balance: float | None = Form(default=None),
    receivables_131_current_vnd: float | None = Form(default=None),
    payables_331_vnd: float | None = Form(default=None),
    total_receivable_credit_131_vnd: float | None = Form(default=None),
) -> dict:
    with tempfile.TemporaryDirectory() as tmp_dir:
        saved_files: list[tuple[str, str]] = []
        for upload in files:
            path = os.path.join(tmp_dir, upload.filename)
            content = await upload.read()
            with open(path, "wb") as out:
                out.write(content)
            saved_files.append((path, upload.filename))

        # Extract file-by-file, as RB's router does: one corrupt/mislabeled/
        # unsupported file must not sink the whole assessment (extract_document
        # raises ValueError for those cases; other parser libraries can raise
        # their own exception types for a genuinely broken file, so this catches
        # broadly at this one boundary).
        documents = []
        extraction_warnings: list[str] = []
        for path, name in saved_files:
            try:
                documents.append(extract_document(path, name))
            except Exception as exc:  # noqa: BLE001 - see comment above
                extraction_warnings.append(f"{name}: không đọc được nội dung file ({exc})")

        transactions = parse_statement_documents(documents)
        simulated_marker = any_table_has_simulated_balance_marker(documents)

        computed = assemble_response(
            customer_name=customer_name,
            tax_id=tax_id,
            raw_transactions=transactions,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            receivables_131_current_vnd=receivables_131_current_vnd,
            payables_331_vnd=payables_331_vnd,
            total_receivable_credit_131_vnd=total_receivable_credit_131_vnd,
            documents_have_simulated_marker=simulated_marker,
        )
        computed["extraction_warnings"] = extraction_warnings

        save_assessment(get_settings().db_path, "crosssell", customer_name, tax_id, computed)
        return computed
