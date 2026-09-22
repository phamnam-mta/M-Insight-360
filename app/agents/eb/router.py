import datetime
import os
import tempfile
import time
import uuid
from dataclasses import asdict

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from app.config import get_settings
from app.engine.core.timing import narrative_budget_exceeded
from app.engine.core.types import RuleResult
from app.extraction.pipeline import extract_document
from app.storage.db import get_connection, init_db
from app.storage.files import get_case_file_path, record_case_file, save_case_file
from app.storage.repository import save_assessment

from .cashflow_flags import evaluate_rf02_negative_cfo
from .contract_financing import compute_output_contract_financing_ratio
from .crosssell_adapter import evaluate_crosssell_opportunities
from .document_check import MANDATORY_DOC_TYPES, classify_documents, missing_from_classified
from .document_status import build_document_status_list
from .dsp_reconciliation import evaluate_rf04_dsp_mismatch
from .financial_inputs import extract_financial_inputs
from .leverage import compute_short_term_debt_ratio, evaluate_rf03_short_term_debt_ratio
from .liquidity import compute_current_ratio, compute_nwc, evaluate_rf01_capital_imbalance
from .mb02_export import build_mb02_docx
from .narrative import generate_narrative
from .overview import evaluate_overview
from .policy_check import run_policy_check
from .repayment_capacity import compute_dscr, compute_icr, evaluate_rf05_weak_repayment_capacity
from .stress_test import run_stress_test

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
    proposed_limit_vnd: float | None = Form(default=None),
    eligible_contract_value_vnd: float | None = Form(default=None),
    qd_eb_039_method: str | None = Form(default=None),
) -> dict:
    request_start = time.monotonic()
    assessed_at = datetime.datetime.now(datetime.UTC).isoformat()
    settings = get_settings()
    case_id = f"EB-{tax_id}-{uuid.uuid4().hex[:8]}"
    init_db(settings.db_path)

    with tempfile.TemporaryDirectory() as tmp_dir:
        saved_files: list[tuple[str, str, str]] = []
        for upload in files:
            file_id = uuid.uuid4().hex[:10]
            path = os.path.join(tmp_dir, upload.filename)
            content = await upload.read()
            with open(path, "wb") as out:
                out.write(content)
            storage_path = save_case_file(settings.case_files_dir, case_id, file_id, upload.filename, content)
            record_case_file(
                settings.db_path, case_id, file_id, upload.filename,
                upload.content_type, len(content), storage_path,
            )
            saved_files.append((path, upload.filename, file_id))

        # Extract file-by-file, as RB's router does: one corrupt/mislabeled/
        # unsupported file must not sink the whole assessment (extract_document
        # raises ValueError for those cases; other parser libraries can raise
        # their own exception types for a genuinely broken file, so this catches
        # broadly at this one boundary).
        documents = []
        extraction_warnings: list[str] = []
        for path, name, file_id in saved_files:
            try:
                documents.append(extract_document(path, name, file_id=file_id))
            except Exception as exc:  # noqa: BLE001 - see comment above
                extraction_warnings.append(f"{name}: không đọc được nội dung file ({exc})")

        classified = classify_documents(documents)
        missing = missing_from_classified(classified)

        financial_inputs, field_evidence = extract_financial_inputs(documents)

        nwc = compute_nwc(financial_inputs, field_evidence)
        current_ratio = compute_current_ratio(financial_inputs, field_evidence)
        short_term_debt_ratio = compute_short_term_debt_ratio(financial_inputs, field_evidence)
        dscr = compute_dscr(financial_inputs, field_evidence)
        icr = compute_icr(financial_inputs, field_evidence)
        output_contract_ratio = compute_output_contract_financing_ratio(
            proposed_limit_vnd, eligible_contract_value_vnd, qd_eb_039_method,
        )

        risk_flags = [
            evaluate_rf01_capital_imbalance(financial_inputs, nwc, field_evidence),
            evaluate_rf02_negative_cfo(financial_inputs, field_evidence),
            evaluate_rf03_short_term_debt_ratio(short_term_debt_ratio, field_evidence),
            evaluate_rf04_dsp_mismatch(financial_inputs, field_evidence),
            evaluate_rf05_weak_repayment_capacity(dscr, icr, field_evidence),
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

        overview_rows, overview_summary = evaluate_overview(documents)
        metrics_by_name = {
            "nwc": nwc, "current_ratio": current_ratio,
            "short_term_debt_ratio": short_term_debt_ratio, "dscr": dscr, "icr": icr,
            "output_contract_financing_ratio": output_contract_ratio,
        }
        opportunities = evaluate_crosssell_opportunities(documents)

        if missing:
            credit_readiness, recommendation = "NOT_READY", "ADDITIONAL_DOCUMENTS_REQUIRED"
        elif any(f.severity in ("HIGH", "CRITICAL") for f in activated_flags):
            credit_readiness, recommendation = "MANUAL_REVIEW_REQUIRED", "REQUIRES_CREDIT_OFFICER_REVIEW"
        elif activated_flags:
            credit_readiness, recommendation = "READY_WITH_CONDITIONS", "PROCEED_WITH_CONDITIONS"
        else:
            credit_readiness, recommendation = "READY", "PROCEED_FOR_HUMAN_REVIEW"

        overall_conclusion = (
            "Chưa đủ căn cứ xác định điều kiện áp dụng" if overview_summary["pending"] > 0 else None
        )

        computed = {
            "case_id": case_id,
            "assessed_at": assessed_at,
            "customer_profile": {"customer_name": customer_name, "tax_id": tax_id},
            "mandatory_document_check": {"required": MANDATORY_DOC_TYPES, "missing": missing},
            "credit_engine": {name: asdict(metric) for name, metric in metrics_by_name.items()},
            "risk_flags": [_serialize_rule_result(f) for f in risk_flags],
            "policy_eligibility": [_serialize_rule_result(r) for r in run_policy_check()],
            "missing_data": missing,
            "credit_readiness": credit_readiness,
            "recommendation": recommendation,
            "overview": [asdict(r) for r in overview_rows],
            "overview_summary": overview_summary,
            "overall_conclusion": overall_conclusion,
            "documents": build_document_status_list(documents, extraction_warnings, overview_rows, metrics_by_name),
            "opportunities": opportunities,
            "export_available": True,
        }

        # GreenNode's gateway has an unconfigurable hard timeout in front of
        # this container; if OCR already used most of the budget, skip the
        # (non-essential) narrative call rather than risk a 502 that would
        # discard the already-computed, already-correct numbers above.
        if narrative_budget_exceeded(request_start):
            narrative_result = {"why": [], "credit_memo": ""}
        else:
            narrative_result = generate_narrative(computed)
        computed["why"] = narrative_result.get("why", [])
        computed["credit_memo"] = narrative_result.get("credit_memo", "") or DISCLAIMER

        save_assessment(settings.db_path, "eb", customer_name, tax_id, computed)
        return computed


@router.post("/export")
async def export(computed: dict) -> Response:
    docx_bytes = build_mb02_docx(computed)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=to-trinh-mb02-du-thao.docx"},
    )


@router.post("/stress-test")
async def stress_test(payload: dict) -> dict:
    from .financial_inputs import EbFinancialInputs

    raw_inputs = payload.get("inputs", {})
    valid_fields = set(EbFinancialInputs.__dataclass_fields__)
    inputs = EbFinancialInputs(**{k: v for k, v in raw_inputs.items() if k in valid_fields})
    deltas = payload.get("deltas", {})
    return run_stress_test(
        inputs,
        revenue_pct=deltas.get("revenue_pct", 0.0),
        margin_pct=deltas.get("margin_pct", 0.0),
        interest_rate_pct=deltas.get("interest_rate_pct", 0.0),
        collection_speed_pct=deltas.get("collection_speed_pct", 0.0),
    )


@router.get("/files/{case_id}/{file_id}")
async def get_evidence_file(case_id: str, file_id: str) -> FileResponse:
    settings = get_settings()
    conn = get_connection(settings.db_path)
    try:
        row = conn.execute(
            "SELECT filename, content_type FROM case_files WHERE case_id = ? AND file_id = ?",
            (case_id, file_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy file")
    path = get_case_file_path(settings.case_files_dir, case_id, file_id, row["filename"])
    if path is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy file")
    return FileResponse(path, media_type=row["content_type"] or "application/octet-stream", filename=row["filename"])
