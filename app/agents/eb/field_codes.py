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

from .canonical import FIELD_CODE_MAP  # noqa: F401 — re-exported; owned by canonical.py (Bước 0C)
from .financial_inputs import EbFinancialInputs


def compute_total_assets_vnd(inputs: EbFinancialInputs) -> float | None:
    """BS_TOTAL_ASSETS — instruction's own fallback formula
    (CĐKT mã 270 not extracted directly): current + non-current assets."""
    if inputs.current_assets_vnd is None or inputs.non_current_assets_vnd is None:
        return None
    return inputs.current_assets_vnd + inputs.non_current_assets_vnd
