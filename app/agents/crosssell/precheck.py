from .statement_parser import Transaction

BLOCK_TOLERANCE_VND = 1  # rounding-only tolerance

# The imbalance direction decides which rows the customer is actually asked for:
# a computed closing balance that is too high means outflow (ghi nợ) rows are
# missing, too low means inflow (ghi có) rows are. The message used to say
# "chi ra" either way, asking the customer for the wrong half of the statement.
BLOCK_MESSAGE_TEMPLATE = (
    "MSB đã kiểm toán tính toàn vẹn sao kê trước khi phân tích và phát hiện sao kê khách "
    "hàng cung cấp chưa đầy đủ: ước tính thiếu khoảng {amount:,.0f} VND các dòng {direction}. "
    "Anh/chị đề nghị khách hàng bổ sung phần còn thiếu trước khi làm hồ sơ, tránh trường hợp "
    "hoàn thiện tờ trình rồi mới bị trả về do thiếu chứng từ."
)
MISSING_DEBIT_DIRECTION = "chi ra (ghi nợ)"
MISSING_CREDIT_DIRECTION = "thu vào (ghi có)"


def run_precheck(
    transactions: list[Transaction],
    opening_balance: float | None = None,
    closing_balance: float | None = None,
) -> dict:
    total_credit = sum(t.credit for t in transactions)
    total_debit = sum(t.debit for t in transactions)

    if opening_balance is None or closing_balance is None:
        return {
            "verdict": "WARN",
            "total_credit": total_credit,
            "total_debit": total_debit,
            "reason": "Sao kê không có cột/thông tin số dư đầu kỳ và cuối kỳ — không đối chiếu được tính toàn vẹn số tiền.",
        }

    computed_closing = opening_balance + total_credit - total_debit
    diff = computed_closing - closing_balance

    if abs(diff) > BLOCK_TOLERANCE_VND:
        est_missing_debit = diff if diff > 0 else 0
        est_missing_credit = -diff if diff < 0 else 0
        direction = MISSING_DEBIT_DIRECTION if diff > 0 else MISSING_CREDIT_DIRECTION
        return {
            "verdict": "BLOCK",
            "total_credit": total_credit,
            "total_debit": total_debit,
            "est_missing_debit": est_missing_debit,
            "est_missing_credit": est_missing_credit,
            "reason": BLOCK_MESSAGE_TEMPLATE.format(amount=abs(diff), direction=direction),
        }

    return {
        "verdict": "PASS",
        "total_credit": total_credit,
        "total_debit": total_debit,
        "reason": "Đối chiếu số dư đầu kỳ + Thu − Chi = Số dư cuối kỳ khớp.",
    }


def check_name_quality(transactions: list[Transaction]) -> dict:
    total = len(transactions)
    if total == 0:
        return {"verdict": "PASS", "empty_pct": 0.0, "short_pct": 0.0, "no_space_pct": 0.0}

    empty = sum(1 for t in transactions if not t.partner.strip())
    short = sum(1 for t in transactions if t.partner and len(t.partner.strip()) < 8)
    no_space = sum(1 for t in transactions if t.partner and " " not in t.partner.strip())

    empty_pct = round(empty / total, 4)
    short_pct = round(short / total, 4)
    no_space_pct = round(no_space / total, 4)

    warn = empty_pct > 0.2 or short_pct > 0.1 or no_space_pct > 0.1
    return {
        "verdict": "WARN" if warn else "PASS",
        "empty_pct": empty_pct,
        "short_pct": short_pct,
        "no_space_pct": no_space_pct,
    }
