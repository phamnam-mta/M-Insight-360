"""6 quy tắc bán chéo — công thức Deal size đầy đủ theo AGENT_CrossSell v3.1 §BỘ QUY TẮC.

Mỗi hàm evaluate_* nhận dữ liệu đã tính sẵn (giao dịch đã khử trùng, phân loại
dòng tiền, số liệu BCTC/công nợ tuỳ chọn) và trả về một Opportunity — không tự
đọc file, không tự gọi LLM. Khi thiếu dữ liệu gốc để tính, trả priority
"P-NA" kèm signal/canh_bao nêu rõ thiếu gì, không bao giờ bỏ trống hoàn toàn.
"""

import re
import unicodedata

from .card_types import (
    DetailBlock,
    Opportunity,
    confidence_with_cap,
    format_deal_size_exact,
    format_deal_size_headline,
    priority_from_deal_size,
)
from .rule1_rule6 import _PAYROLL_KEYWORDS, is_loan_transaction
from .rule2_partners import RULE2_MIN_TRANSACTIONS, RULE2_MIN_VALUE_VND, rank_top_partners
from .statement_parser import Transaction

CAP1_REVENUE_PCT = 0.10
CAP2_ABS_VND = 20_000_000_000
REVENUE_FLOOR_FOR_PROPOSED_PLAN = 100_000_000_000
IDLE_THRESHOLD_VND = 5_000_000_000
IDLE_MIN_DAYS = 10
OUTLIER_RATIO = 0.05


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()


def _na(rule_id: str, san_pham: str, segment: str, signal: str, canh_bao: list[str]) -> Opportunity:
    return Opportunity(
        rule_id=rule_id, san_pham=san_pham, segment=segment, deal_size=None,
        deal_size_headline="Chưa xác định", deal_size_exact=None, priority="P-NA",
        confidence=None, ly_do_confidence=None, signal_1dong=signal, canh_bao=canh_bao,
    )


def _card(
    rule_id: str, san_pham: str, segment: str, deal_size_float: float,
    signal: str, chi_tiet: list[DetailBlock], confidence_base: str, confidence_cap: str,
    ly_do_confidence: str, canh_bao: list[str] | None = None,
) -> Opportunity:
    deal_size = round(deal_size_float)
    confidence = confidence_with_cap(confidence_base, confidence_cap)
    return Opportunity(
        rule_id=rule_id, san_pham=san_pham, segment=segment, deal_size=deal_size,
        deal_size_headline=format_deal_size_headline(deal_size),
        deal_size_exact=format_deal_size_exact(deal_size),
        priority=priority_from_deal_size(deal_size), confidence=confidence,
        ly_do_confidence=ly_do_confidence, signal_1dong=signal,
        chi_tiet=chi_tiet, canh_bao=canh_bao or [],
    )


# ───────────────────────── Rule 1 — Payroll (RB) ─────────────────────────

def evaluate_rule1(
    transactions: list[Transaction], period_months: float, confidence_cap: str,
    lctt_payroll_vnd: float | None = None,
) -> Opportunity:
    matches = [
        t for t in transactions
        if t.debit > 0 and any(kw in _strip_accents_lower(t.description) for kw in _PAYROLL_KEYWORDS)
    ]
    if not matches:
        return _na(
            "RULE1_PAYROLL", "Payroll + Thẻ tín dụng CBNV", "RB",
            "Chưa có giao dịch ghi nợ nào khớp từ khoá lương trong kỳ.",
            ["Không kết luận khách hàng không có lương — có thể lương chạy hoàn toàn ở kênh khác."],
        )

    tong_chi_luong_ky = sum(t.debit for t in matches)
    statement_annualized = tong_chi_luong_ky / period_months * 12 if period_months else tong_chi_luong_ky

    if lctt_payroll_vnd is not None and lctt_payroll_vnd > statement_annualized * 1.05:
        deal_size = lctt_payroll_vnd
        pct = round(statement_annualized / lctt_payroll_vnd * 100) if lctt_payroll_vnd else 0
        chi_tiet = [
            DetailBlock("Công thức", f"LCTT · Tiền chi trả cho người lao động = {round(lctt_payroll_vnd):,} (lấy nguồn BCTC vì sao kê chỉ ghi nhận một phần)".replace(",", ".")),
            DetailBlock("Vì sao không dùng nguồn chính", f"Sao kê {len(matches)} GD annualized {round(statement_annualized):,} — chỉ bằng {pct}% số BCTC.".replace(",", ".")),
        ]
        signal = f"Sao kê chỉ ghi nhận ~{pct}% quỹ lương thực tế — còn {round((lctt_payroll_vnd - statement_annualized)/1_000_000_000, 2)} tỷ chạy ở kênh khác."
    else:
        deal_size = statement_annualized
        chi_tiet = [DetailBlock("Công thức", f"Annualized = {round(tong_chi_luong_ky):,} / {period_months:g} tháng × 12 = {round(deal_size):,}".replace(",", "."))]
        signal = f"{len(matches)} giao dịch trả lương, annualized {format_deal_size_headline(deal_size)}."

    return _card(
        "RULE1_PAYROLL", "Payroll + Thẻ tín dụng CBNV", "RB", deal_size, signal, chi_tiet,
        confidence_base="M", confidence_cap=confidence_cap,
        ly_do_confidence="Số liệu từ sao kê gốc, chưa đối chiếu chéo bảng lương thực tế.",
    )


# ───────────────────────── Rule 2 — SCF / Chuỗi (EB) ─────────────────────────

def evaluate_rule2(
    transactions: list[Transaction], period_months: float, confidence_cap: str,
    revenue_vnd: float | None = None,
) -> Opportunity:
    ranked = rank_top_partners(transactions)
    qualifying = [p for p in ranked if p["qualifies"]]
    if not qualifying:
        return _na(
            "RULE2_SCF", "Tài trợ chuỗi — SCF / Bảo lãnh thanh toán", "EB",
            f"Không có đối tác nào đạt ngưỡng {RULE2_MIN_TRANSACTIONS} GD và {RULE2_MIN_VALUE_VND:,.0f} VND.".replace(",", "."),
            [],
        )

    top = qualifying[0]
    annualized = top["total_value"] / period_months * 12 if period_months else top["total_value"]
    deal_tho = annualized * 0.80

    cap1 = None
    caps_note = [f"deal thô = annualized {round(annualized):,} × 80% = {round(deal_tho):,}".replace(",", ".")]
    candidates = [deal_tho]
    if revenue_vnd is not None and revenue_vnd < 500_000_000_000:
        cap1 = revenue_vnd * CAP1_REVENUE_PCT
        candidates.append(cap1)
        caps_note.append(f"cap 10% doanh thu = {round(cap1):,}".replace(",", "."))
    candidates.append(CAP2_ABS_VND)
    caps_note.append(f"cap 20 tỷ = {CAP2_ABS_VND:,}".replace(",", "."))

    deal_size = min(candidates)
    caps_note.append(f"→ Deal size = MIN = {round(deal_size):,}".replace(",", "."))

    canh_bao = []
    if revenue_vnd is not None and revenue_vnd < REVENUE_FLOOR_FOR_PROPOSED_PLAN:
        canh_bao.append(
            f"Doanh thu {format_deal_size_headline(revenue_vnd)} dưới 100 tỷ → không đủ điều kiện phương án đầu ra dự kiến."
        )

    n_qual = len(qualifying)
    signal = f"{n_qual} đối tác đạt ngưỡng, giá trị annualized cao nhất {format_deal_size_headline(annualized)}."

    return _card(
        "RULE2_SCF", "Tài trợ chuỗi — SCF / Bảo lãnh thanh toán", "EB", deal_size, signal,
        [DetailBlock("Công thức", " | ".join(caps_note))],
        confidence_base="M", confidence_cap=confidence_cap,
        ly_do_confidence="Số liệu từ sao kê gốc, chưa đối chiếu chéo BCTC.",
        canh_bao=canh_bao,
    )


# ───────────────────────── Rule 3 — Vốn nhàn rỗi (EB) ─────────────────────────

def evaluate_rule3(
    daily_closing_balances: dict[str, float], confidence_cap: str,
    balance_is_simulated: bool,
) -> Opportunity:
    if not daily_closing_balances:
        return _na(
            "RULE3_IDLE", "Chứng chỉ tiền gửi (CCTG) / Tiền gửi có kỳ hạn", "EB",
            "Không có cột số dư thực trong sao kê.",
            ["Cần sao kê bản gốc có cột số dư — không suy diễn từ Thu − Chi bắt đầu từ 0."],
        )

    values = list(daily_closing_balances.values())
    days_above = [v for v in values if v > IDLE_THRESHOLD_VND]
    if len(days_above) < IDLE_MIN_DAYS:
        return _na(
            "RULE3_IDLE", "Chứng chỉ tiền gửi (CCTG) / Tiền gửi có kỳ hạn", "EB",
            f"Chỉ {len(days_above)} ngày số dư > {format_deal_size_headline(IDLE_THRESHOLD_VND)}, dưới ngưỡng {IDLE_MIN_DAYS} ngày.",
            [],
        )

    raw_min = min(values)
    avg = sum(values) / len(values)
    canh_bao = []
    if avg and raw_min < avg * OUTLIER_RATIO:
        sorted_vals = sorted(values)
        # Nearest-rank 5th percentile: skip at least the bottom outlier(s) so
        # the technical trough itself is never picked back up as "the 5th
        # percentile" (with few samples, round(n*0.05) can land on index 0,
        # i.e. the trough itself — always skip at least one value here).
        idx = min(len(sorted_vals) - 1, max(1, round(len(sorted_vals) * 0.05)))
        deal_size = sorted_vals[idx]
        canh_bao.append(
            f"Số dư thấp nhất {format_deal_size_headline(raw_min)} là điểm trũng kỹ thuật một ngày. "
            f"Deal size lấy phân vị 5% = {format_deal_size_headline(deal_size)}."
        )
    else:
        deal_size = raw_min

    if balance_is_simulated:
        canh_bao.append(
            "Số dư trong file là số mô phỏng, không phải số in trên sao kê. Rule 3 chỉ mang tính minh "
            "hoạ, đề nghị RM lấy sao kê bản gốc có cột số dư trước khi chào CCTG/FD."
        )
        return _na(
            "RULE3_IDLE", "Chứng chỉ tiền gửi (CCTG) / Tiền gửi có kỳ hạn", "EB",
            f"Số dư nhàn rỗi ~{format_deal_size_headline(deal_size)} nhưng số dư là mô phỏng — không dùng để chào bán.",
            canh_bao,
        )

    signal = f"Số dư > {format_deal_size_headline(IDLE_THRESHOLD_VND)} xuất hiện {len(days_above)} ngày, thấp nhất kỳ {format_deal_size_headline(deal_size)}."
    return _card(
        "RULE3_IDLE", "Chứng chỉ tiền gửi (CCTG) / Tiền gửi có kỳ hạn", "EB", deal_size, signal,
        [DetailBlock("Công thức", f"Deal size = số dư thấp nhất kỳ = {round(deal_size):,}".replace(",", "."))],
        confidence_base="M", confidence_cap=confidence_cap,
        ly_do_confidence="Số dư đọc trực tiếp từ cột số dư trên sao kê gốc.",
        canh_bao=canh_bao,
    )


# ───────────────────────── Rule 4 — FX (EB) ─────────────────────────

def evaluate_rule4(transactions: list[Transaction], period_months: float, confidence_cap: str) -> Opportunity:
    fx = [t for t in transactions if t.currency and t.currency.upper() not in ("VND", "VN")]
    total = len(transactions)
    if not fx:
        return _na(
            "RULE4_FX", "Hạn mức ngoại hối / Tài trợ XNK", "EB",
            f"Kỳ này {total}/{total} giao dịch là VND." if total else "Không có giao dịch trong kỳ.",
            ["Không kết luận khách hàng không có nhu cầu ngoại hối. Đề nghị RM hỏi trực tiếp về hoạt động XNK."],
        )

    fx_total = sum(t.credit + t.debit for t in fx)
    annualized = fx_total / period_months * 12 if period_months else fx_total
    return _card(
        "RULE4_FX", "Hạn mức ngoại hối / Tài trợ XNK", "EB", annualized,
        f"{len(fx)}/{total} giao dịch ngoại tệ, annualized {format_deal_size_headline(annualized)}.",
        [DetailBlock("Công thức", f"Tổng ngoại tệ quy đổi trong kỳ {round(fx_total):,} annualized = {round(annualized):,}".replace(",", "."))],
        confidence_base="M", confidence_cap=confidence_cap,
        ly_do_confidence="Bắt theo từ khoá/cột Loại tiền — cần RM xác minh cột Loại tiền thực tế.",
        canh_bao=["Script chỉ bắt cột Loại tiền — cần xác minh không phải false positive từ chữ 'chuyển tiền' trong diễn giải VND."],
    )


# ───────────────────────── Rule 6 — Vay NH khác (EB) ─────────────────────────

def evaluate_rule6(
    transactions: list[Transaction], confidence_cap: str,
    cdkt_short_term_debt_vnd: float | None = None,
    cdkt_short_term_debt_opening_vnd: float | None = None,
    lctt_loan_disbursement_vnd: float | None = None,
    lctt_loan_repayment_vnd: float | None = None,
) -> Opportunity:
    matches = [t for t in transactions if is_loan_transaction(t)]
    if not matches:
        return _na(
            "RULE6_LOAN", "Tái tài trợ / Chia sẻ hạn mức vay", "EB",
            "Không có giao dịch khớp từ khoá khế ước/giải ngân/trả nợ vay trong kỳ.", [],
        )

    stmt_disbursed = sum(t.credit for t in matches)
    stmt_repaid = sum(t.debit for t in matches)

    if cdkt_short_term_debt_vnd is not None:
        deal_size = cdkt_short_term_debt_vnd
        chi_tiet = [DetailBlock(
            "Công thức",
            f"CĐKT · Vay và nợ thuê tài chính ngắn hạn cuối kỳ = {round(deal_size):,}".replace(",", ".")
            + (f" (đầu kỳ {round(cdkt_short_term_debt_opening_vnd):,})".replace(",", ".") if cdkt_short_term_debt_opening_vnd is not None else "")
            + (f". LCTT: thu từ đi vay {round(lctt_loan_disbursement_vnd):,}, trả gốc {round(lctt_loan_repayment_vnd):,}.".replace(",", ".")
               if lctt_loan_disbursement_vnd is not None and lctt_loan_repayment_vnd is not None else ""),
        )]
    else:
        deal_size = None

    canh_bao = ["Không suy ra dư nợ hiện tại từ số trả nợ trong kỳ. Cần RM lấy CIC."]
    if stmt_disbursed == 0 and stmt_repaid > 0:
        canh_bao.append(
            "Toàn bộ tiền giải ngân không về tài khoản này — khách hàng có quan hệ tín dụng sâu với "
            "ngân hàng khác. Cơ hội tái tài trợ/chia sẻ hạn mức."
        )

    signal = f"{len(matches)} giao dịch trả nợ — {'0 đồng giải ngân về tài khoản này' if stmt_disbursed == 0 else f'giải ngân {format_deal_size_headline(stmt_disbursed)}'}."

    if deal_size is None:
        return Opportunity(
            rule_id="RULE6_LOAN", san_pham="Tái tài trợ / Chia sẻ hạn mức vay", segment="EB",
            deal_size=None, deal_size_headline="CHƯA XÁC ĐỊNH — cần CIC", deal_size_exact=None,
            priority="P1" if stmt_repaid >= 5_000_000_000 else "P-NA",
            confidence="L" if stmt_repaid >= 5_000_000_000 else None,
            ly_do_confidence="Chưa có BCTC — quy mô ước theo tổng trả nợ trong kỳ, cần CIC xác nhận dư nợ thật." if stmt_repaid >= 5_000_000_000 else None,
            signal_1dong=signal,
            chi_tiet=[DetailBlock("Công thức", f"Chưa có BCTC. Bằng chứng quy mô: tổng giải ngân {round(stmt_disbursed):,}, tổng trả nợ {round(stmt_repaid):,} trong kỳ.".replace(",", "."))],
            canh_bao=canh_bao,
        )

    return _card(
        "RULE6_LOAN", "Tái tài trợ / Chia sẻ hạn mức vay", "EB", deal_size, signal, chi_tiet,
        confidence_base="M", confidence_cap=confidence_cap,
        ly_do_confidence="Số từ CĐKT, đối chiếu chéo với giao dịch trả nợ trên sao kê.",
        canh_bao=canh_bao,
    )
