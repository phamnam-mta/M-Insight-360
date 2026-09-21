import os
import tempfile
from dataclasses import asdict

from fastapi import APIRouter, File, Form, UploadFile

from app.config import get_settings
from app.engine.core.types import RuleResult
from app.extraction.pipeline import extract_document

from .credit_engine import run_credit_engine
from .document_classifier import classify_document
from .loan_inputs import extract_loan_inputs
from .mandatory_check import check_mandatory_documents
from .narrative import generate_narrative
from .profile_checks import check_tax_id_consistency
from .readiness import determine_readiness
from .risk_flags import compute_risk_flags
from app.storage.repository import save_assessment

router = APIRouter(prefix="/api/rb", tags=["rb"])


def _serialize_risk_flag(flag: RuleResult) -> dict:
    data = asdict(flag)
    # web/components/ResultPanel.tsx renders f.impact for each risk flag; RuleResult
    # has no "impact" field, so alias it from the human-readable comment here at the
    # HTTP boundary rather than growing the shared RuleResult type for one consumer.
    data["impact"] = flag.comment
    return data


@router.post("/assess")
async def assess(
    customer_name: str = Form(...),
    tax_id: str = Form(...),
    files: list[UploadFile] = File(...),
) -> dict:
    with tempfile.TemporaryDirectory() as tmp_dir:
        saved_files: list[tuple[str, str]] = []
        for upload in files:
            path = os.path.join(tmp_dir, upload.filename)
            content = await upload.read()
            with open(path, "wb") as out:
                out.write(content)
            saved_files.append((path, upload.filename))

        # Extract file-by-file: one corrupt/mislabeled/unsupported file must not
        # sink the whole assessment (extract_document raises ValueError for those
        # cases; other parser libraries can raise their own exception types for a
        # genuinely broken file, so this catches broadly at this one boundary).
        documents = []
        extraction_warnings: list[str] = []
        for path, name in saved_files:
            try:
                documents.append(extract_document(path, name))
            except Exception as exc:  # noqa: BLE001 - see comment above
                extraction_warnings.append(f"{name}: không đọc được nội dung file ({exc})")

        classified = [classify_document(doc) for doc in documents]
        mandatory_check = check_mandatory_documents(classified)
        tax_id_result = check_tax_id_consistency(tax_id, documents)

        loan_inputs = extract_loan_inputs(documents)
        engine_metrics = run_credit_engine(loan_inputs, loan_inputs.existing_monthly_obligation_vnd)

        risk_flags = compute_risk_flags(
            mandatory_check,
            tax_id_result,
            engine_metrics["dti"],
            classified_documents=[
                (doc.filename, doc_type, confidence)
                for doc, (doc_type, confidence) in zip(documents, classified)
            ],
        )
        if extraction_warnings:
            risk_flags.append(
                RuleResult(
                    rule_id="LOW_OCR_CONFIDENCE",
                    rule_name="Một số tệp tải lên không đọc được",
                    status="KÍCH HOẠT",
                    severity="LOW",
                    evidence=extraction_warnings,
                    comment=(
                        "Một số tệp tải lên không đọc được nội dung (file hỏng hoặc sai "
                        "định dạng) và đã bị bỏ qua khi thẩm định."
                    ),
                    recommended_action="Yêu cầu khách hàng tải lại các tệp này ở định dạng hợp lệ.",
                )
            )

        credit_readiness, recommendation = determine_readiness(mandatory_check, risk_flags)

        computed = {
            "case_id": f"RB-{tax_id}",
            "customer_profile": {"customer_name": customer_name, "tax_id": tax_id},
            "document_status": {
                "legal": [dt for dt, _ in classified if dt in ("LEGAL_IDENTITY", "BUSINESS_REGISTRATION", "TAX_DOCUMENT")],
                "income": [dt for dt, _ in classified if dt in ("BANK_STATEMENT", "INCOME_DOCUMENT", "ECOMMERCE_REVENUE")],
                "loan_request": [dt for dt, _ in classified if dt == "LOAN_REQUEST"],
            },
            "mandatory_document_check": mandatory_check,
            "document_authenticity": {
                "status": tax_id_result.status,
                "signals": [tax_id_result.comment] if tax_id_result.comment else [],
                "action": tax_id_result.recommended_action or "",
            },
            "credit_engine": {name: asdict(metric) for name, metric in engine_metrics.items()},
            "risk_flags": [_serialize_risk_flag(flag) for flag in risk_flags],
            "missing_data": mandatory_check["missing"],
            "credit_readiness": credit_readiness,
            "recommendation": recommendation,
            "export_available": False,
        }

        narrative_result = generate_narrative(computed)
        computed["why"] = narrative_result["why"]
        computed["credit_memo"] = narrative_result["credit_memo"]

        save_assessment(get_settings().db_path, "rb", customer_name, tax_id, computed)
        return computed
