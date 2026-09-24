import datetime
import os
import re
import tempfile
import time
import unicodedata
import uuid
from dataclasses import asdict, replace

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.config import get_settings
from app.engine.core.timing import narrative_budget_exceeded
from app.engine.core.types import Metric, RuleResult
from app.extraction.pipeline import extract_document
from app.storage.db import get_connection, init_db
from app.storage.files import get_case_file_path, record_case_file, save_case_file
from app.storage.repository import save_assessment

from .capital_structure import (
    compute_capital_balance_check, compute_liquidity_balance,
    compute_long_term_capital, compute_total_borrowings,
)
from .cashflow_flags import evaluate_rf02_negative_cfo
from .contract_financing import compute_output_contract_financing_ratio, compute_receivables_financing_limit
from .document_check import MANDATORY_DOC_TYPES, classify_documents, missing_from_classified
from .document_status import build_document_status_list
from .dsp_reconciliation import evaluate_rf04_dsp_mismatch
from .canonical import build_canonical
from .export_gate import evaluate_export_gate
from .financial_inputs import EbFinancialInputs, financial_inputs_by_period, select_richest_period
from .leverage import (
    compute_short_term_debt_ratio,
    evaluate_rf03_short_term_debt_ratio,
    evaluate_rf06_receivables_inventory_concentration,
    evaluate_rf08_leverage,
)
from .liquidity import compute_current_ratio, compute_nwc, evaluate_rf01_capital_imbalance
from .mb02_export import build_mb02_docx
from .narrative import generate_narrative
from .overview import evaluate_overview
from .policy_check import run_policy_check
from .profitability import compute_ebitda
from .repayment_capacity import (
    compute_dscr,
    compute_icr,
    evaluate_rf05_dscr_weak,
    evaluate_rf07_high_interest_burden,
    evaluate_rf09_icr_weak,
)
from .sanity_checks import run_sanity_checks
from .stress_scenarios import list_scenarios, save_scenario
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
    report_period: str | None = Form(default=None),
    sheets: str | None = Form(default=None),
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

        canonical_result = build_canonical(documents, include_all_sheets=(sheets == "all"))
        period_extractions = financial_inputs_by_period(canonical_result)
        available_periods = sorted(period_extractions.keys(), reverse=True)
        # Auto-selection (no explicit report_period requested) picks the
        # most POPULATED period, not just the newest year number — an
        # unrelated sheet bundled in the same upload (e.g. a bank
        # statement) can spuriously create a near-empty period bucket for
        # a later year that would otherwise silently outrank the real,
        # richly-populated BCTC period.
        selected_period = (
            report_period if report_period in period_extractions
            else select_richest_period(period_extractions)
        )
        if selected_period and selected_period in period_extractions:
            financial_inputs = period_extractions[selected_period].inputs
            field_evidence = period_extractions[selected_period].field_evidence
        else:
            financial_inputs, field_evidence = EbFinancialInputs(), {}

        ho_so_period: dict = {"selected": selected_period, "available": available_periods}
        if report_period and report_period not in period_extractions:
            ho_so_period["requested"] = report_period
            ho_so_period["fallback_notice"] = (
                f"Kỳ báo cáo '{report_period}' không có trong hồ sơ tải lên — "
                f"đã tự động chọn kỳ gần nhất có dữ liệu ({selected_period or 'không xác định'})."
            )

        # L2-bis: run sanity checks BEFORE any metric/flag/gate touches the
        # raw values, and compute everything downstream from a cleaned
        # copy with suspect fields nulled — a value the check itself
        # doesn't trust must never reach a KPI, a red flag, the export
        # gate, or the .docx as if it were real ("thà báo unknown còn hơn
        # hiển thị một con số sai"). The RAW financial_inputs (below, in
        # `computed`) still carries the suspect value so L2's "Xem dữ liệu
        # nguồn" trace and the suspect-reason banner can show it.
        sanity_result = run_sanity_checks(financial_inputs, selected_period)
        clean_inputs = replace(
            financial_inputs, **{f: None for f in sanity_result.suspect_fields}
        )

        nwc = compute_nwc(clean_inputs, field_evidence)
        current_ratio = compute_current_ratio(clean_inputs, field_evidence)
        short_term_debt_ratio = compute_short_term_debt_ratio(clean_inputs, field_evidence)
        dscr = compute_dscr(clean_inputs, field_evidence)
        icr = compute_icr(clean_inputs, field_evidence)
        output_contract_ratio = compute_output_contract_financing_ratio(
            proposed_limit_vnd, eligible_contract_value_vnd, qd_eb_039_method,
        )
        ebitda = compute_ebitda(clean_inputs, field_evidence)
        liquidity_balance = compute_liquidity_balance(clean_inputs, field_evidence)
        long_term_capital = compute_long_term_capital(clean_inputs, field_evidence)
        total_borrowings = compute_total_borrowings(clean_inputs, field_evidence)
        capital_balance_check = compute_capital_balance_check(clean_inputs, nwc, long_term_capital)
        receivables_financing_limit_80 = compute_receivables_financing_limit(clean_inputs.receivables_vnd, ltv=0.80)
        receivables_financing_limit_85 = compute_receivables_financing_limit(clean_inputs.receivables_vnd, ltv=0.85)

        risk_flags = [
            evaluate_rf01_capital_imbalance(clean_inputs, nwc, field_evidence),
            evaluate_rf02_negative_cfo(clean_inputs, field_evidence),
            evaluate_rf03_short_term_debt_ratio(short_term_debt_ratio, field_evidence),
            evaluate_rf04_dsp_mismatch(clean_inputs, field_evidence),
            evaluate_rf05_dscr_weak(dscr, field_evidence),
            evaluate_rf09_icr_weak(icr, field_evidence),
            evaluate_rf08_leverage(total_borrowings, clean_inputs, field_evidence),
            evaluate_rf06_receivables_inventory_concentration(clean_inputs, field_evidence),
            evaluate_rf07_high_interest_burden(clean_inputs, field_evidence),
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

        canonical_fields_for_period = canonical_result.fields_by_year.get(selected_period or "", {})
        overview_rows, overview_summary = evaluate_overview(documents, canonical_fields_for_period)
        metrics_by_name = {
            "nwc": nwc, "current_ratio": current_ratio,
            "short_term_debt_ratio": short_term_debt_ratio, "dscr": dscr, "icr": icr,
            "output_contract_financing_ratio": output_contract_ratio,
            "ebitda": ebitda, "liquidity_balance": liquidity_balance,
            "long_term_capital": long_term_capital, "total_borrowings": total_borrowings,
            "receivables_financing_limit_80": receivables_financing_limit_80,
            "receivables_financing_limit_85": receivables_financing_limit_85,
        }

        # S7.2(f): a same-year field read differently by two BCTC-included
        # sheets (canonical.consistency) or a balance sheet that itself
        # doesn't balance (sanity_result.balance_mismatch) are both document
        # defects, folded into one combined signal so neither can silently
        # slip past the other's hard block.
        combined_khop = canonical_result.consistency.khop and not sanity_result.balance_mismatch
        combined_lech = list(canonical_result.consistency.danh_sach_lech)
        if sanity_result.balance_mismatch:
            combined_lech.append({"chi_tieu": "Cân đối kế toán", "chi_tiet": sanity_result.balance_mismatch_detail})

        # Review Focus #5: an upload whose sheets were all scanned but NONE
        # classified as a BCTC source (e.g. a bank-statement-only "sao kê")
        # must hard-block exactly like an unreadable file — it is not the
        # same as "extracted successfully, all fields legitimately missing."
        no_bctc_sheet_included = bool(canonical_result.sheet_scan) and not any(
            s.included for s in canonical_result.sheet_scan
        )

        gate_result = evaluate_export_gate(
            risk_flags, equity_vnd=clean_inputs.equity_vnd, dscr=dscr, icr=icr,
            # Bước 0 hard-blocks (S7.2 a): unreadable upload, or the
            # balance sheet itself doesn't balance (Tổng tài sản ≠ Tổng
            # nguồn vốn) — both are document defects, never overridable.
            pre_check_blocked=(
                (bool(extraction_warnings) and not any(
                    v is not None for v in asdict(financial_inputs).values()
                ))
                or not combined_khop
                or no_bctc_sheet_included
            ),
            loai_chan="LECH_DU_LIEU" if not combined_khop else None,
            # TODO(personal-vs-legal-entity detection): this codebase has no
            # BCTC classifier for personal/household filings yet (out of
            # scope per the v2.3 rebuild spec's extraction-layer boundary);
            # hard-block (b) is unreachable until that classifier exists.
            is_legal_entity=True,
        )

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
            "export_available": True,
            "ho_so_period": ho_so_period,
            "capital_balance_check": capital_balance_check,
            "export_gate": asdict(gate_result),
            "sanity_check": {
                "suspect_fields": sanity_result.suspect_fields,
                "balance_mismatch": sanity_result.balance_mismatch,
                "balance_mismatch_detail": sanity_result.balance_mismatch_detail,
            },
            "sheet_scan": [asdict(s) for s in canonical_result.sheet_scan],
            "cot_nam": {
                "nguon_nam_bao_cao": "cot_nam_sheet_bctc" if selected_period else None,
                "cac_nam_co_trong_ho_so": available_periods,
                "nam_can_nguoi_dung_xac_nhan": len(available_periods) > 1 and not report_period,
            },
            "consistency": {"khop": combined_khop, "danh_sach_lech": combined_lech},
            "canonical": {
                ma: {
                    "nhan": cf.nhan, "gia_tri": cf.gia_tri, "don_vi": cf.don_vi, "nam": cf.nam,
                    "nguon": cf.nguon, "sheet": cf.sheet, "loai": cf.loai, "co_gia_tri": cf.co_gia_tri,
                }
                for ma, cf in canonical_fields_for_period.items()
            },
            # Raw extracted BCTC field values, independent of which metrics
            # happen to cite them in their own input_values — the frontend's
            # FinancialDataTable and StressTestDrawer read from this channel
            # directly instead of reverse-engineering it from per-metric
            # formula documentation (see 2026-09-22 EB redesign review).
            "financial_inputs": {k: v for k, v in asdict(financial_inputs).items() if v is not None},
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


def _ascii_safe_filename_part(text: str) -> str:
    """Content-Disposition headers are latin-1 encoded — a raw Vietnamese
    name (diacritics, either precomposed or combining) reaching the header
    raises UnicodeEncodeError -> 500. NFKD decomposition strips ordinary
    accents; Đ/đ have no NFKD decomposition to ASCII, so replace those
    explicitly first."""
    text = text.replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in normalized if not unicodedata.combining(c))
    return re.sub(r"[^\w\-]+", "_", ascii_only, flags=re.ASCII).strip("_")


def _rule_result_from_dict(data: dict) -> RuleResult:
    known = {k: v for k, v in data.items() if k in RuleResult.__dataclass_fields__}
    return RuleResult(**known)


def _metric_from_credit_engine(credit_engine: dict, name: str) -> Metric:
    m = credit_engine.get(name) or {}
    return Metric(
        metric=name, value=m.get("value"), formula=m.get("formula", ""),
        input_values=m.get("input_values", {}), input_sources=m.get("input_sources", {}),
        status=m.get("status", "NEED_MORE_DATA"),
    )


@router.post("/export")
async def export(payload: dict) -> Response:
    computed = payload.get("computed", payload)
    force = bool(payload.get("force", False))
    actor = payload.get("actor")

    risk_flags = [_rule_result_from_dict(f) for f in computed.get("risk_flags") or [] if isinstance(f, dict)]
    credit_engine = computed.get("credit_engine") or {}
    dscr = _metric_from_credit_engine(credit_engine, "dscr")
    icr = _metric_from_credit_engine(credit_engine, "icr")
    equity_vnd = (computed.get("financial_inputs") or {}).get("equity_vnd")
    sanity_check = computed.get("sanity_check") or {}
    consistency = computed.get("consistency") or {}
    sheet_scan = computed.get("sheet_scan") or []
    # S7.2(f): re-check the same combined consistency signal /assess
    # computed — a same-year cross-sheet conflict (canonical.consistency)
    # or a balance sheet that doesn't balance are both document defects,
    # never force-overridable.
    khop = consistency.get("khop", True) and not sanity_check.get("balance_mismatch")
    # Review Focus #5, re-checked here too: /assess's own HARD block for a
    # zero-BCTC-sheet upload must not be bypassable by re-posting the same
    # `computed` to /export with force=true.
    no_bctc_sheet_included = bool(sheet_scan) and not any(s.get("included") for s in sheet_scan)

    gate = evaluate_export_gate(
        risk_flags, equity_vnd=equity_vnd, dscr=dscr, icr=icr,
        # Same S7.2(a) hard-block as /assess: a balance sheet that
        # doesn't balance, or an upload with no BCTC-included sheet at
        # all, are both document defects, never overridable by force —
        # the re-posted `computed` carries /assess's own verdicts, so
        # both must be re-checked here too.
        pre_check_blocked=(not khop) or no_bctc_sheet_included,
        loai_chan="LECH_DU_LIEU" if not khop else None,
    )

    # HARD blocks (unreadable upload, balance mismatch) are never
    # force-overridable — only SOFT (risk-signal) blocks are.
    if gate.verdict == "KHONG_XUAT_TU_DONG" and (gate.block_type == "HARD" or not force):
        return JSONResponse(status_code=409, content={
            "export_blocked": True,
            "verdict": gate.verdict,
            "block_type": gate.block_type,
            "signal_count": gate.signal_count,
            "reasons": gate.reasons,
            "signals": [asdict(s) for s in gate.signals],
            "loai_chan": gate.loai_chan,
        })

    computed = {**computed, "export_gate": asdict(gate)}
    docx_bytes, fill_log = build_mb02_docx(computed, force=force, actor=actor)

    customer_name = (computed.get("customer_profile") or {}).get("customer_name") or "KH"
    period = (computed.get("ho_so_period") or {}).get("selected") or "khong-xac-dinh"
    date_str = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d")
    safe_name = _ascii_safe_filename_part(customer_name) or "KH"
    filename = f"TTTD_{safe_name}_{period}_{date_str}_BANNHAP.docx"

    # fill_log is diagnostic only — no frontend code reads it. It used to
    # ride along as a base64 X-Fill-Log header, but that routinely exceeds
    # 4KB and silently 502'd every real export at GreenNode's gateway
    # (which caps custom header size below that) — never surfaced as an
    # app-level error, since the gateway rejects the response before the
    # client sees anything but "invalid response from upstream".
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
        ebit_pct=deltas.get("ebit_pct", 0.0),
        interest_pct=deltas.get("interest_pct", 0.0),
        receivable_days_add=deltas.get("receivable_days_add", 0.0),
        inventory_pct=deltas.get("inventory_pct", 0.0),
        principal_due_pct=deltas.get("principal_due_pct", 0.0),
        comprehensive=payload.get("comprehensive_mode", False),
    )


@router.post("/stress-test/scenarios")
async def save_stress_scenario(payload: dict) -> dict:
    settings = get_settings()
    init_db(settings.db_path)
    scenario_id = save_scenario(
        settings.db_path,
        case_id=payload["case_id"], name=payload["name"], created_by=payload.get("created_by", "RM"),
        report_period=payload.get("report_period"), request=payload.get("request", {}), response=payload.get("response", {}),
    )
    return {"id": scenario_id}


@router.get("/stress-test/scenarios")
async def get_stress_scenarios(case_id: str) -> dict:
    settings = get_settings()
    init_db(settings.db_path)
    return {"scenarios": list_scenarios(settings.db_path, case_id)}


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
