import os
import tempfile
from dataclasses import asdict

from fastapi import APIRouter, File, Form, UploadFile

from app.config import get_settings
from app.extraction.pipeline import extract_document
from app.storage.repository import save_assessment

from .dashboard import build_monthly_dashboard
from .flow_classification import classify_flows
from .narrative import generate_narrative
from .precheck import check_name_quality, run_precheck
from .rule1_rule6 import evaluate_rule1_payroll, evaluate_rule6_loan_elsewhere
from .rule2_partners import evaluate_rule2_top_partners, rank_top_partners
from .rule3_rule4 import evaluate_rule3_idle_balance, evaluate_rule4_fx
from .rule5_receivables import evaluate_rule5, leak_ratio_msb_share
from .statement_parser import parse_statement_documents

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

        precheck = run_precheck(transactions, opening_balance, closing_balance)
        name_quality = check_name_quality(transactions)
        flows = classify_flows(transactions)
        dashboard = build_monthly_dashboard(transactions)
        top_partners = rank_top_partners(transactions)

        # Rule 5D: tỷ lệ về MSB = operating_in(MSB) / Tổng phát sinh Có 131 — only computable
        # when the RM has also supplied the total 131 credit turnover figure (a separate
        # figure from the current receivables balance). Absent that, leak_ratio stays None
        # and evaluate_rule5 correctly omits the 5D line rather than guessing.
        leak_ratio = leak_ratio_msb_share(
            operating_in_msb_vnd=flows["operating_in"],
            total_receivable_credit_131_vnd=total_receivable_credit_131_vnd,
        ) if total_receivable_credit_131_vnd is not None else None

        opportunities = [
            evaluate_rule1_payroll(transactions),
            evaluate_rule2_top_partners(transactions),
            evaluate_rule3_idle_balance(None),  # no real balance column in this statement schema
            evaluate_rule4_fx(transactions),
            evaluate_rule5(receivables_131_current_vnd, payables_331_vnd, leak_ratio),
            evaluate_rule6_loan_elsewhere(transactions),
        ]

        max_confidence = "M" if precheck["verdict"] == "WARN" else ("LOW" if precheck["verdict"] == "BLOCK" else "HIGH")

        computed = {
            "case_id": f"CROSSSELL-{tax_id}",
            "customer_profile": {"customer_name": customer_name, "tax_id": tax_id},
            "precheck": precheck,
            "name_quality": name_quality,
            "flow_classification": flows,
            "dashboard": dashboard,
            "top_partners": top_partners[:10],
            "opportunities": [asdict(r) for r in opportunities],
            "confidence_ceiling": max_confidence,
            "extraction_warnings": extraction_warnings,
        }

        if precheck["verdict"] != "BLOCK":
            narrative_result = generate_narrative(computed)
        else:
            narrative_result = {"why": [], "credit_memo": precheck["reason"]}

        computed["why"] = narrative_result["why"]
        computed["credit_memo"] = narrative_result["credit_memo"]
        computed["export_available"] = False

        save_assessment(get_settings().db_path, "crosssell", customer_name, tax_id, computed)
        return computed
