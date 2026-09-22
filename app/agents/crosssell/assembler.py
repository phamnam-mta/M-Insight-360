"""Lắp ráp toàn bộ kết quả v3.1 thành đúng SCHEMA JSON §C.

Nối các mô-đun đã tính sẵn (Tầng 0, pre-check v2, 0B, phân loại dòng tiền, 6
Rule, danh sách đối tác, kịch bản, tự kiểm) thành một response — mô-đun này
không tự đọc file, không tự tính nghiệp vụ, chỉ gọi đúng thứ tự và định dạng
theo §C.
"""

import unicodedata
import uuid
from dataclasses import asdict

from .card_types import Opportunity, confidence_with_cap, format_deal_size_headline
from .dashboard import build_monthly_dashboard
from .deal_engine import evaluate_rule1, evaluate_rule2, evaluate_rule3, evaluate_rule4, evaluate_rule6
from .flow_classification import classify_flows, is_cash_transaction
from .partners_v2 import CIF_WARNING, build_partner_row, is_junk_partner_name, is_person_partner
from .precheck import run_precheck
from .precheck_v2 import build_daily_closing_balances, run_precheck_v2
from .quality_v2 import check_name_quality_v2
from .rule1_rule6 import is_loan_transaction
from .rule2_partners import RULE2_MIN_TRANSACTIONS, RULE2_MIN_VALUE_VND
from .rule5_v2 import evaluate_rule5a_receivables_financing, evaluate_rule5b_payables_scf, evaluate_rule5d_leak
from .scenario_templates import generate_scenarios
from .self_check import run_self_check
from .self_transfer import build_self_transfer_pattern, is_self_transfer
from .statement_parser import Transaction
from .tang0 import dedup_transactions

_CONFIDENCE_ORDER = {"H": 2, "M": 1, "L": 0}


def _combine_caps(*caps: str) -> str:
    return min(caps, key=lambda c: _CONFIDENCE_ORDER[c])


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()


def _parse_date(date_str: str) -> tuple[int, int, int] | None:
    parts = date_str.strip().split("/")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    day, month, year = parts
    return (int(year), int(month), int(day))


def _period_months(transactions: list[Transaction]) -> float:
    months = {m["month"] for m in build_monthly_dashboard(transactions) if m["month"] != "KHÔNG XÁC ĐỊNH"}
    return float(len(months)) if months else 1.0


def _statement_period_label(transactions: list[Transaction]) -> str:
    dates = sorted((d for d in (_parse_date(t.date) for t in transactions) if d is not None))
    if not dates:
        return "Không xác định"
    y0, m0, d0 = dates[0]
    y1, m1, d1 = dates[-1]
    return f"{d0:02d}/{m0:02d}/{y0} – {d1:02d}/{m1:02d}/{y1}"


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


def _build_partner_list(
    transactions: list[Transaction], customer_name: str, period_months: float
) -> list:
    self_pattern = build_self_transfer_pattern(customer_name)
    by_partner: dict[str, dict] = {}
    for t in transactions:
        name = t.partner.strip()
        if not name or is_junk_partner_name(name):
            continue
        if is_loan_transaction(t) or is_cash_transaction(t):
            continue
        if is_self_transfer(name, self_pattern) or is_self_transfer(t.description, self_pattern):
            continue
        entry = by_partner.setdefault(
            name, {"credit": 0.0, "debit": 0.0, "count": 0, "months": set()}
        )
        entry["credit"] += t.credit
        entry["debit"] += t.debit
        entry["count"] += 1
        parsed = _parse_date(t.date)
        if parsed:
            entry["months"].add((parsed[0], parsed[1]))

    qualifying = {
        name: e
        for name, e in by_partner.items()
        if e["count"] >= RULE2_MIN_TRANSACTIONS and (e["credit"] + e["debit"]) >= RULE2_MIN_VALUE_VND
    }
    if not qualifying:
        return []

    max_value = max(e["credit"] + e["debit"] for e in qualifying.values())
    total_period_months = max(1, round(period_months))

    rows = []
    for name, e in qualifying.items():
        total_value = e["credit"] + e["debit"]
        if e["credit"] > 0 and e["debit"] > 0:
            direction = "Ca hai"
        elif e["credit"] > 0:
            direction = "Dau ra (Nguoi mua)"
        else:
            direction = "Dau vao (NCC)"
        freq_per_month = e["count"] / total_period_months
        score = 40 * (total_value / max_value if max_value else 0)
        score += 30 * min(freq_per_month / 4, 1)
        score += 20 * (len(e["months"]) / total_period_months if total_period_months else 0)
        score = round(score, 1)
        rows.append(build_partner_row(name, direction, e["count"], total_value, score))

    rows.sort(key=lambda r: -r.diem)
    return rows[:10]


def assemble_response(
    *,
    customer_name: str,
    tax_id: str,
    raw_transactions: list[Transaction],
    opening_balance: float | None,
    closing_balance: float | None,
    receivables_131_current_vnd: float | None = None,
    payables_331_vnd: float | None = None,
    total_receivable_credit_131_vnd: float | None = None,
    documents_have_simulated_marker: bool = False,
    industry_guess: str = "thương mại và dịch vụ",
) -> dict:
    tang0 = dedup_transactions(raw_transactions)
    transactions = tang0.transactions
    period_months = _period_months(transactions)

    v1_precheck = run_precheck(transactions, opening_balance, closing_balance)
    precheck = run_precheck_v2(transactions, documents_have_simulated_marker, opening_balance, closing_balance)
    quality = check_name_quality_v2(transactions)
    confidence_cap = _combine_caps(precheck.confidence_cap, quality.confidence_cap)

    flows = classify_flows(transactions)
    total_credit = sum(t.credit for t in transactions)
    msb_credit = sum(t.credit for t in transactions if "msb" in _strip_accents_lower(t.source))
    msb_pct = round(msb_credit / total_credit * 100, 1) if total_credit else 0.0

    request_id = str(uuid.uuid4())
    ma_lo = f"CROSSSELL-{tax_id}"

    ho_so = {
        "ten_kh": customer_name,
        "mst": tax_id,
        "ky_sao_ke": _statement_period_label(transactions),
        "so_gd": tang0.deduped_count,
        "so_ngan_hang": len({t.source.strip() for t in transactions if t.source.strip()}) or 1,
        "nganh_suy_doan": "Chưa xác định — đề nghị RM bổ sung",
    }

    if precheck.verdict == "BLOCK":
        missing = v1_precheck.get("est_missing_debit") or v1_precheck.get("est_missing_credit") or 0
        badges = [{"loai": "err", "nhan": "Pre-check: BLOCK", "tro_toi": "evidence.precheck"}]
        kpi = [
            {
                "nhan": "Cần bổ sung chứng từ",
                "gia_tri": format_deal_size_headline(missing) if missing else "Chưa xác định",
                "phu": "Sao kê chưa đối chiếu được tính toàn vẹn — xem evidence.precheck",
                "nhan_manh": True,
            }
        ]
        co_hoi_dicts: list[dict] = []
        partner_rows: list = []
        warnings = [precheck.reason]
        status = "blocked"
    else:
        badges = []
        if precheck.verdict == "PASS (khong doi chieu doc lap duoc)":
            badges.append({"loai": "warn", "nhan": "Pre-check: PASS giả", "tro_toi": "evidence.precheck"})
        elif precheck.verdict == "WARN":
            badges.append({"loai": "warn", "nhan": "Pre-check: WARN", "tro_toi": "evidence.precheck"})
        else:
            badges.append({"loai": "ok", "nhan": "Pre-check: PASS", "tro_toi": "evidence.precheck"})

        if quality.verdict == "WARN":
            empty_metric = quality.metrics[0]
            badges.append(
                {"loai": "warn", "nhan": f"Bóc tên: {empty_metric.pct}% rỗng", "tro_toi": "evidence.quality"}
            )
        else:
            badges.append({"loai": "ok", "nhan": "Bóc tên: đạt chuẩn", "tro_toi": "evidence.quality"})

        badges.append({"loai": "info", "nhan": f"Confidence trần: {confidence_cap}", "tro_toi": "evidence.quality"})
        badges.append(
            {
                "loai": "ok" if tang0.duplicate_count == 0 else "warn",
                "nhan": f"{tang0.deduped_count}/{tang0.raw_count} khớp",
                "tro_toi": "evidence.tang0",
            }
        )

        daily_balances = build_daily_closing_balances(transactions)
        opportunities: list[Opportunity] = [
            evaluate_rule1(transactions, period_months, confidence_cap),
            evaluate_rule2(transactions, period_months, confidence_cap),
            evaluate_rule3(daily_balances, confidence_cap, documents_have_simulated_marker),
            evaluate_rule4(transactions, period_months, confidence_cap),
            evaluate_rule5a_receivables_financing(receivables_131_current_vnd, None, False, confidence_cap),
            evaluate_rule5b_payables_scf(payables_331_vnd, None, confidence_cap),
            evaluate_rule6(transactions, confidence_cap),
        ]

        for opp in opportunities:
            opp.kich_ban = generate_scenarios(opp, industry_guess)

        opportunities.sort(key=lambda o: (o.deal_size is None, -(o.deal_size or 0)))

        partner_rows = _build_partner_list(transactions, customer_name, period_months)

        total_deal_size = sum(o.deal_size for o in opportunities if o.deal_size is not None)
        n_quantified = sum(1 for o in opportunities if o.deal_size is not None)
        p1_opps = [o for o in opportunities if o.priority == "P1"]
        p1_total = sum(o.deal_size for o in p1_opps if o.deal_size is not None)
        n_ownership_flag = sum(
            1 for p in partner_rows if p.co_canh_bao and p.nhan_canh_bao != "Cá nhân → sản phẩm RB"
        )

        kpi = [
            {
                "nhan": "Tổng cơ hội",
                "gia_tri": format_deal_size_headline(total_deal_size) if n_quantified else "Chưa xác định",
                "phu": f"{n_quantified} cơ hội định lượng được",
                "nhan_manh": True,
            },
            {
                "nhan": "Ưu tiên P1",
                "gia_tri": str(len(p1_opps)),
                "phu": f"{format_deal_size_headline(p1_total)} · chào trước" if p1_opps else "Chưa có",
            },
            {
                "nhan": "Đối tác tiềm năng",
                "gia_tri": str(len(partner_rows)),
                "phu": f"{n_ownership_flag} cần xác minh sở hữu" if n_ownership_flag else "",
            },
            {
                "nhan": "Thị phần MSB",
                "gia_tri": f"{msb_pct:g}%".replace(".", ","),
                "phu": (
                    f"{format_deal_size_headline(total_credit - msb_credit)} đang ở ngoài MSB"
                    if msb_pct == 0
                    else f"{format_deal_size_headline(msb_credit)} qua MSB"
                ),
            },
        ]

        co_hoi_dicts = [asdict(o) for o in opportunities]
        warnings = []
        status = "ok"

    badges_valid = badges if status == "blocked" else badges

    self_check_partners_input = partner_rows
    self_check_opps = opportunities if status != "blocked" else []
    fails = run_self_check(self_check_opps, badges_valid, kpi, self_check_partners_input)
    warnings = [*warnings, *fails]

    n_ra_soat_opp = sum(1 for o in self_check_opps if o.deal_size is not None)
    n_ra_soat_na = len(self_check_opps) - n_ra_soat_opp
    all_canh_bao = [c for o in self_check_opps for c in o.canh_bao]

    evidence = {
        "tang0": {
            "tieu_de": "Tầng 0 — chuẩn hoá đầu vào",
            "tom_tat": _truncate(
                f"{tang0.deduped_count}/{tang0.raw_count} khớp · loại {tang0.duplicate_count} dòng trùng", 70
            ),
            "noi_dung": {
                "raw_count": tang0.raw_count,
                "deduped_count": tang0.deduped_count,
                "duplicate_count": tang0.duplicate_count,
                "unique_entry_no_count": tang0.unique_entry_no_count,
            },
        },
        "precheck": {
            "tieu_de": "Pre-check chứng từ",
            "tom_tat": _truncate(f"{precheck.verdict} · {precheck.reason}", 70),
            "noi_dung": {
                "verdict": precheck.verdict,
                "total_credit": precheck.total_credit,
                "total_debit": precheck.total_debit,
                "balance_source": precheck.balance_source,
                "reason": precheck.reason,
            },
        },
        "quality": {
            "tieu_de": "Chất lượng bóc tên (0B)",
            "tom_tat": _truncate(
                f"{quality.verdict} · {quality.metrics[0].pct}% tên rỗng".replace(".", ","), 70
            ),
            "noi_dung": {"metrics": [asdict(m) | {"result_text": m.result_text} for m in quality.metrics]},
        },
        "dongtien": {
            "tieu_de": "Dòng tiền & thị phần",
            "tom_tat": _truncate(
                f"operating_in {format_deal_size_headline(flows['operating_in'])} "
                f"({flows['operating_in_pct'] * 100:.1f}%) · MSB {msb_pct:g}%".replace(".0%", "%"),
                70,
            ),
            "noi_dung": {
                **flows, "msb_credit": msb_credit, "msb_pct": msb_pct,
                "leak_ratio_131": evaluate_rule5d_leak(
                    flows["operating_in"], total_receivable_credit_131_vnd, has_msb_statement=True
                ),
            },
        },
        "ra_soat": {
            "tieu_de": "Bảng rà soát 6 Rule",
            "tom_tat": _truncate(f"{n_ra_soat_opp} có cơ hội · {n_ra_soat_na} thiếu dữ liệu", 70),
            "noi_dung": {
                "rules": [
                    {"rule_id": o.rule_id, "priority": o.priority, "deal_size_headline": o.deal_size_headline}
                    for o in self_check_opps
                ]
            },
        },
        "nganh": {
            "tieu_de": "Ngành nghề & override",
            "tom_tat": _truncate(ho_so["nganh_suy_doan"], 70),
            "noi_dung": {},
        },
        "viec_rm": {
            "tieu_de": "Việc RM cần xác nhận",
            "tom_tat": _truncate(f"{len(all_canh_bao)} cảnh báo cần RM xác minh", 70),
            "noi_dung": {"canh_bao": all_canh_bao},
        },
    }

    doi_tac = {
        "canh_bao_cif": CIF_WARNING,
        "danh_sach": [asdict(p) for p in partner_rows],
        "ghi_chu_mo_rong": None,
    }

    ban_giao = {
        "noi_dung_mail": (
            f"Kính gửi RM,\n\nHồ sơ {customer_name} (MST {tax_id}) có "
            f"{len([o for o in self_check_opps if o.deal_size is not None])} cơ hội bán chéo định lượng được. "
            "Xem chi tiết trong bảng cơ hội đính kèm."
        )
        if status != "blocked"
        else "",
        "bang_tracking": [],
        "ghi_chu_plumbing": (
            "Gửi Outlook và ghi SharePoint cần connector trong tenant MSB — chưa cấu hình trong bản triển khai này."
        ),
    }

    return {
        "status": status,
        "request_id": request_id,
        "ma_lo": ma_lo,
        "ho_so": ho_so,
        "badges": badges,
        "kpi": kpi,
        "co_hoi": co_hoi_dicts,
        "doi_tac": doi_tac,
        "evidence": evidence,
        "ban_giao": ban_giao,
        "warnings": warnings,
        "error_code": None,
    }
