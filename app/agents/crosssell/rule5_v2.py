"""Rule 5 — Công nợ 131/331, tách thành 5A/5B/5C/5D theo AGENT_CrossSell v3.1.

Chỉ chạy khi có bảng công nợ 131/331 — không suy đoán khi thiếu.
"""

from .card_types import DetailBlock, Opportunity, confidence_with_cap, format_deal_size_headline

DSO_DPO_LOW_THRESHOLD_DAYS = 15


def _na_5(rule_id: str, san_pham: str, signal: str, canh_bao: list[str]) -> Opportunity:
    return Opportunity(
        rule_id=rule_id, san_pham=san_pham, segment="EB", deal_size=None,
        deal_size_headline="Chưa xác định", deal_size_exact=None, priority="P-NA",
        confidence=None, ly_do_confidence=None, signal_1dong=signal, canh_bao=canh_bao,
    )


def evaluate_rule5a_receivables_financing(
    receivables_131_current_vnd: float | None,
    receivables_131_opening_vnd: float | None,
    has_aging_column: bool,
    confidence_cap: str,
    payment_method: str = "domestic_receivable",
) -> Opportunity:
    if receivables_131_current_vnd is None:
        return _na_5(
            "RULE5A_AR", "Tài trợ khoản phải thu",
            "Chưa có bảng công nợ 131/331 — chưa đánh giá được khoản phải thu.",
            ["Chưa có bảng công nợ 131/331 — chưa đánh giá được khoản phải thu/phải trả."],
        )

    rates = {
        "perfect_bct_lc": 0.98, "lc_or_bltt": 0.90, "export_bct": 0.90,
        "contract_or_award_notice": 0.80, "domestic_receivable": 0.80,
    }
    rate = rates.get(payment_method, 0.80)
    deal_size = receivables_131_current_vnd * rate

    canh_bao = []
    if not has_aging_column:
        canh_bao.append(
            "Bảng 131 không có cột tuổi nợ. Con số này là TRẦN TRÊN, đề nghị RM xác minh tuổi nợ."
        )
    if (
        receivables_131_opening_vnd is not None
        and receivables_131_opening_vnd > 0
        and receivables_131_current_vnd < receivables_131_opening_vnd / 3
    ):
        canh_bao.append("Dư cuối kỳ thấp hơn đầu kỳ nhiều lần — có thể là điểm trũng. RM nên lấy số bình quân 12 tháng.")

    return Opportunity(
        rule_id="RULE5A_AR", san_pham="Tài trợ khoản phải thu", segment="EB",
        deal_size=round(deal_size), deal_size_headline=format_deal_size_headline(deal_size),
        deal_size_exact=f"{round(deal_size):,}".replace(",", "."),
        priority=_priority(deal_size), confidence=confidence_with_cap("M", confidence_cap),
        ly_do_confidence="Số từ bảng công nợ 131, chưa lọc được nợ quá hạn.",
        signal_1dong=f"{int(rate*100)}% × Dư Nợ 131 cuối kỳ {format_deal_size_headline(receivables_131_current_vnd)}.",
        chi_tiet=[DetailBlock("Công thức", f"{rate:g} × {round(receivables_131_current_vnd):,} = {round(deal_size):,}".replace(",", "."))],
        canh_bao=canh_bao,
    )


def evaluate_rule5b_payables_scf(
    payables_331_current_vnd: float | None,
    payables_331_opening_vnd: float | None,
    confidence_cap: str,
) -> Opportunity:
    if payables_331_current_vnd is None:
        return _na_5(
            "RULE5B_AP", "SCF / Bảo lãnh thanh toán / L/C nhập",
            "Chưa có bảng công nợ 331 — chưa đánh giá được hạn mức SCF.",
            ["Chưa có bảng công nợ 131/331 — chưa đánh giá được khoản phải thu/phải trả."],
        )

    canh_bao = []
    deal_size = payables_331_current_vnd
    chi_tiet_text = f"Dư Có 331 cuối kỳ = {round(deal_size):,}".replace(",", ".")

    if (
        payables_331_opening_vnd is not None
        and payables_331_opening_vnd > 0
        and payables_331_current_vnd < payables_331_opening_vnd / 3
    ):
        deal_size = (payables_331_current_vnd + payables_331_opening_vnd) / 2
        canh_bao.append("RM nên lấy số dư 331 bình quân 12 tháng thay vì số cuối kỳ.")
        chi_tiet_text = (
            f"cuối kỳ {round(payables_331_current_vnd):,} · đầu kỳ {round(payables_331_opening_vnd):,} "
            f"→ bình quân = {round(deal_size):,}"
        ).replace(",", ".")

    return Opportunity(
        rule_id="RULE5B_AP", san_pham="SCF / Bảo lãnh thanh toán / L/C nhập", segment="EB",
        deal_size=round(deal_size), deal_size_headline=format_deal_size_headline(deal_size),
        deal_size_exact=f"{round(deal_size):,}".replace(",", "."),
        priority=_priority(deal_size), confidence=confidence_with_cap("M", confidence_cap),
        ly_do_confidence="Số từ bảng công nợ 331.",
        signal_1dong=f"Hạn mức SCF dựa trên Dư Có 331 {format_deal_size_headline(deal_size)}.",
        chi_tiet=[DetailBlock("Công thức", chi_tiet_text)],
        canh_bao=canh_bao,
    )


def compute_dso_dpo(
    receivables_131_vnd: float | None, revenue_period_vnd: float | None,
    payables_331_vnd: float | None, cogs_period_vnd: float | None, period_days: int = 365,
) -> dict:
    dso = (receivables_131_vnd / revenue_period_vnd) * period_days if receivables_131_vnd is not None and revenue_period_vnd else None
    dpo = (payables_331_vnd / cogs_period_vnd) * period_days if payables_331_vnd is not None and cogs_period_vnd else None
    return {"dso_days": dso, "dpo_days": dpo}


def rule5c_conclusion(dso_days: float | None, dpo_days: float | None) -> str | None:
    if dso_days is None or dpo_days is None:
        return None
    if dso_days < DSO_DPO_LOW_THRESHOLD_DAYS and dpo_days < DSO_DPO_LOW_THRESHOLD_DAYS:
        return (
            "Cả hai dưới 15 ngày → khách hàng KHÔNG bị chiếm dụng vốn thương mại. Nhu cầu tài trợ "
            "không nằm ở khoản phải thu — chuyển trọng tâm sang dư nợ vay ngân hàng khác và tín hiệu trả lương."
        )
    if dso_days >= DSO_DPO_LOW_THRESHOLD_DAYS:
        return "DSO cao → khách hàng bị chiếm dụng vốn → nhu cầu tài trợ khoản phải thu rõ rệt."
    return None


def evaluate_rule5d_leak(
    operating_in_msb_vnd: float | None,
    total_receivable_credit_131_vnd: float | None,
    has_msb_statement: bool,
) -> dict:
    """Not a sellable card on its own — a diagnostic ratio folded into evidence.ra_soat."""
    if total_receivable_credit_131_vnd is None:
        return {"status": "khong_tinh_duoc", "ratio": None, "note": "Không có bảng công nợ 131 để đối chiếu."}
    if not has_msb_statement:
        return {
            "status": "khong_tinh_duoc", "ratio": None,
            "note": "KHÔNG TÍNH ĐƯỢC — bộ hồ sơ không có sao kê MSB. Toàn bộ dòng tiền đang chạy ngoài "
                    "MSB. Đây chính là cơ hội, không phải thiếu dữ liệu.",
        }
    ratio = (operating_in_msb_vnd or 0) / total_receivable_credit_131_vnd
    return {
        "status": "tinh_duoc", "ratio": round(ratio, 4),
        "note": (
            "Đây là chỉ số nghi vấn ở mức tổng thể, chưa phải kết luận. Chênh lệch có thể đến từ dư công "
            "nợ đầu kỳ, bù trừ công nợ, hàng đổi hàng, thu tiền mặt, hoặc KH có tài khoản khác tại MSB. "
            "Đề nghị RM xác minh với khách hàng trước khi sử dụng con số này."
        ),
    }


def _priority(deal_size: float) -> str:
    if deal_size >= 20_000_000_000:
        return "P1"
    if deal_size >= 5_000_000_000:
        return "P2"
    return "P3"
