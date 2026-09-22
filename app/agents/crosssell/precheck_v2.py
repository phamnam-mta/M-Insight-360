"""Bước 0 — Pre-check chứng từ, mở rộng với phát hiện PASS giả.

Spec §Bước 0 "LUẬT MỚI — PASS GIẢ": a balance column that is itself derived by
cumulative sum from an assumed opening balance makes the audit equation
balance to zero on every reconciliation, so a plain PASS proves nothing. The
verdict for that case must read "PASS (khong doi chieu doc lap duoc)", not a
bare PASS, and Rule 3 (idle-balance CCTG/FD pitch) must never fire off a
simulated balance.
"""

from dataclasses import dataclass, field

from .statement_parser import Transaction, header_marks_simulated_balance
from .precheck import run_precheck as _run_precheck_v1

PASS_INDEPENDENT = "PASS"
PASS_NOT_INDEPENDENT = "PASS (khong doi chieu doc lap duoc)"
WARN = "WARN"
BLOCK = "BLOCK"

SIMULATED_BALANCE_NOTE = (
    "Số dư là số mô phỏng/suy ra, không phải số in trên sao kê. Pre-check PASS "
    "không phải bằng chứng sao kê toàn vẹn."
)


@dataclass
class PrecheckV2Result:
    verdict: str
    total_credit: float
    total_debit: float
    reason: str
    balance_source: str  # "doc_tu_sao_ke" | "suy_ra_mo_phong" | "khong_co"
    confidence_cap: str  # "H" | "M" | "L" — ceiling this precheck result imposes


def build_daily_closing_balances(transactions: list[Transaction]) -> dict[str, float]:
    """Last known balance per calendar date, in the order transactions were given.

    Statements are not guaranteed sorted; callers that need chronological
    order should sort transactions before calling this.
    """
    daily: dict[str, float] = {}
    for t in transactions:
        if t.balance is not None and t.date:
            daily[t.date] = t.balance
    return daily


def run_precheck_v2(
    transactions: list[Transaction],
    documents_have_simulated_marker: bool,
    opening_balance: float | None = None,
    closing_balance: float | None = None,
) -> PrecheckV2Result:
    v1 = _run_precheck_v1(transactions, opening_balance, closing_balance)
    has_balance_column = any(t.balance is not None for t in transactions)

    if v1["verdict"] == "BLOCK":
        return PrecheckV2Result(
            verdict=BLOCK,
            total_credit=v1["total_credit"],
            total_debit=v1["total_debit"],
            reason=v1["reason"],
            balance_source="khong_co" if not has_balance_column else (
                "suy_ra_mo_phong" if documents_have_simulated_marker else "doc_tu_sao_ke"
            ),
            confidence_cap="L",
        )

    if v1["verdict"] == "WARN":
        return PrecheckV2Result(
            verdict=WARN,
            total_credit=v1["total_credit"],
            total_debit=v1["total_debit"],
            reason=v1["reason"],
            balance_source="khong_co",
            confidence_cap="M",
        )

    # v1 verdict is PASS — check whether the balance column backing it (if any
    # exists at the transaction level) is simulated rather than read off the
    # real statement.
    if documents_have_simulated_marker and has_balance_column:
        return PrecheckV2Result(
            verdict=PASS_NOT_INDEPENDENT,
            total_credit=v1["total_credit"],
            total_debit=v1["total_debit"],
            reason=SIMULATED_BALANCE_NOTE,
            balance_source="suy_ra_mo_phong",
            confidence_cap="M",
        )

    return PrecheckV2Result(
        verdict=PASS_INDEPENDENT,
        total_credit=v1["total_credit"],
        total_debit=v1["total_debit"],
        reason=v1["reason"],
        balance_source="doc_tu_sao_ke" if has_balance_column else "khong_co",
        confidence_cap="H" if has_balance_column else "M",
    )
