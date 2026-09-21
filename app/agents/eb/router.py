import os
import tempfile
from dataclasses import asdict

from fastapi import APIRouter, File, Form, Response, UploadFile

from app.config import get_settings
from app.engine.core.types import RuleResult
from app.extraction.pipeline import extract_document
from app.storage.db import init_db
from app.storage.repository import save_assessment

from .cashflow_flags import evaluate_rf02_negative_cfo
from .document_check import MANDATORY_DOC_TYPES, classify_documents, missing_from_classified
from .dsp_reconciliation import evaluate_rf04_dsp_mismatch
from .financial_inputs import extract_financial_inputs
from .leverage import compute_short_term_debt_ratio, evaluate_rf03_short_term_debt_ratio
from .liquidity import compute_current_ratio, compute_nwc, evaluate_rf01_capital_imbalance
from .mb02_export import build_mb02_docx
from .narrative import generate_narrative
from .policy_check import run_policy_check
from .repayment_capacity import compute_dscr, compute_icr, evaluate_rf05_weak_repayment_capacity

router = APIRouter(prefix="/api/eb", tags=["eb"])


def _serialize_rule_result(result: RuleResult) -> dict:
    data = asdict(result)
    # web/components/ResultPanel.tsx renders f.impact for each flag; RuleResult
    # has no "impact" field, so alias it from the human-readable comment here at
    # the HTTP boundary (same as RB's router) rather than growing the shared
    # RuleResult type for one consumer.
    data["impact"] = result.comment
    return data


DISCLAIMER = (
    "Agent chỉ chuẩn bị hồ sơ và kiến nghị để cán bộ có thẩm quyền xem xét; không tự phê duyệt, "
    "cam kết cấp hạn mức hoặc thay thế kết luận thẩm định của MSB."
)


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

        classified = classify_documents(documents)
        missing = missing_from_classified(classified)

        financial_inputs = extract_financial_inputs(documents)

        nwc = compute_nwc(financial_inputs)
        current_ratio = compute_current_ratio(financial_inputs)
        short_term_debt_ratio = compute_short_term_debt_ratio(financial_inputs)
        dscr = compute_dscr(financial_inputs)
        icr = compute_icr(financial_inputs)

        risk_flags = [
            evaluate_rf01_capital_imbalance(financial_inputs, nwc),
            evaluate_rf02_negative_cfo(financial_inputs),
            evaluate_rf03_short_term_debt_ratio(short_term_debt_ratio),
            evaluate_rf04_dsp_mismatch(financial_inputs),
            evaluate_rf05_weak_repayment_capacity(dscr, icr),
        ]
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
        activated_flags = [f for f in risk_flags if f.status == "KÍCH HOẠT"]

        if missing:
            credit_readiness, recommendation = "NOT_READY", "ADDITIONAL_DOCUMENTS_REQUIRED"
        elif any(f.severity in ("HIGH", "CRITICAL") for f in activated_flags):
            credit_readiness, recommendation = "MANUAL_REVIEW_REQUIRED", "REQUIRES_CREDIT_OFFICER_REVIEW"
        elif activated_flags:
            credit_readiness, recommendation = "READY_WITH_CONDITIONS", "PROCEED_WITH_CONDITIONS"
        else:
            credit_readiness, recommendation = "READY", "PROCEED_FOR_HUMAN_REVIEW"

        computed = {
            "case_id": f"EB-{tax_id}",
            "customer_profile": {"customer_name": customer_name, "tax_id": tax_id},
            "mandatory_document_check": {"required": MANDATORY_DOC_TYPES, "missing": missing},
            "credit_engine": {
                name: asdict(metric)
                for name, metric in {
                    "nwc": nwc, "current_ratio": current_ratio,
                    "short_term_debt_ratio": short_term_debt_ratio, "dscr": dscr, "icr": icr,
                }.items()
            },
            "risk_flags": [_serialize_rule_result(f) for f in risk_flags],
            "policy_eligibility": [_serialize_rule_result(r) for r in run_policy_check()],
            "missing_data": missing,
            "credit_readiness": credit_readiness,
            "recommendation": recommendation,
            "export_available": True,
        }

        narrative_result = generate_narrative(computed)
        computed["why"] = narrative_result.get("why", [])
        computed["credit_memo"] = narrative_result.get("credit_memo", "") or DISCLAIMER

        db_path = get_settings().db_path
        # Defensive: `save_assessment` requires the schema to exist. The app's
        # own startup lifespan normally creates it, but that lifespan only
        # runs under a real ASGI server or a `with TestClient(app) as ...`
        # context manager — not a plain `TestClient(app)` instantiation — so
        # this call is here to make the endpoint correct regardless of how
        # it's invoked. `init_db` is a cheap, idempotent CREATE TABLE IF NOT
        # EXISTS.
        init_db(db_path)
        save_assessment(db_path, "eb", customer_name, tax_id, computed)
        return computed


@router.post("/export")
async def export(computed: dict) -> Response:
    docx_bytes = build_mb02_docx(computed)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=to-trinh-mb02-du-thao.docx"},
    )
