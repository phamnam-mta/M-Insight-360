"""Canonical field-code map (instruction H4): every export cell, UI field
label, and sanity check speaks these codes, never a bare string. Extend
this map before adding a new export/UI use of an EbFinancialInputs field.

Two instruction codes intentionally have no counterpart today:
BS_LT_LIABILITIES (CĐKT mã 330, "Nợ dài hạn" as a whole) is not extracted
separately from BS_LT_BORROWINGS (mã 338, "Vay & nợ thuê TC dài hạn") —
`long_term_debt_vnd`'s regex matches "no dai han" (330's own label), but
`compute_total_borrowings` already uses it as the 338 figure. Fixing that
330/338 split is a BCTC-extraction change outside this plan's scope (the
spec's gap analysis marks capital_structure.py as already conforming);
BS_LT_BORROWINGS maps to `long_term_debt_vnd` to match the existing,
working formula, and BS_LT_LIABILITIES maps to None."""

from .financial_inputs import EbFinancialInputs

FIELD_CODE_MAP: dict[str, str | None] = {
    "IS_REVENUE": "net_revenue_vnd",
    "IS_COGS": "cogs_vnd",
    "IS_PBT": "pbt_vnd",
    "IS_PAT": "pat_vnd",
    "IS_INTEREST": "interest_expense_vnd",
    "IS_DEPRECIATION": "depreciation_vnd",
    "BS_CURRENT_ASSETS": "current_assets_vnd",
    "BS_CURRENT_LIABILITIES": "current_liabilities_vnd",
    "BS_NON_CURRENT_ASSETS": "non_current_assets_vnd",
    "BS_TOTAL_ASSETS": None,  # computed — see compute_total_assets_vnd
    "BS_EQUITY": "equity_vnd",
    "BS_CHARTER_CAPITAL": "charter_capital_vnd",
    "BS_LT_LIABILITIES": None,  # see module docstring
    "BS_LT_BORROWINGS": "long_term_debt_vnd",
    "BS_ST_BORROWINGS": "short_term_debt_vnd",
    "BS_AR_CUSTOMER": "receivables_vnd",
    "BS_INVENTORY": "inventory_vnd",
    "BS_AP_SUPPLIER": "payables_vnd",
    "BS_CASH": "cash_vnd",
    "DEBT_PRINCIPAL_DUE": "principal_due_vnd",
}


def compute_total_assets_vnd(inputs: EbFinancialInputs) -> float | None:
    """BS_TOTAL_ASSETS — instruction's own fallback formula
    (CĐKT mã 270 not extracted directly): current + non-current assets."""
    if inputs.current_assets_vnd is None or inputs.non_current_assets_vnd is None:
        return None
    return inputs.current_assets_vnd + inputs.non_current_assets_vnd
