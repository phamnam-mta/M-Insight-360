from dataclasses import dataclass, field
from typing import Literal

from app.engine.core.types import EvidenceRef

from .canonical import CanonicalResult, FIELD_CODE_MAP


@dataclass
class EbFinancialInputs:
    equity_vnd: float | None = None
    current_assets_vnd: float | None = None
    current_liabilities_vnd: float | None = None
    cfo_vnd: float | None = None
    short_term_debt_vnd: float | None = None
    total_liabilities_vnd: float | None = None
    revenue_bctc_vnd: float | None = None
    revenue_dsp_vnd: float | None = None
    principal_due_vnd: float | None = None
    interest_due_vnd: float | None = None
    ebit_vnd: float | None = None
    interest_expense_vnd: float | None = None
    net_revenue_vnd: float | None = None
    pbt_vnd: float | None = None
    pat_vnd: float | None = None
    depreciation_vnd: float | None = None
    non_current_assets_vnd: float | None = None
    long_term_debt_vnd: float | None = None
    finance_lease_debt_vnd: float | None = None
    receivables_vnd: float | None = None
    inventory_vnd: float | None = None
    payables_vnd: float | None = None
    cash_vnd: float | None = None
    total_principal_due_vnd: float | None = None
    cogs_vnd: float | None = None
    charter_capital_vnd: float | None = None
    gross_profit_vnd: float | None = None


@dataclass
class FieldEvidence:
    status: Literal["COMPUTED", "PENDING_REVIEW", "MISSING_DATA"]
    evidence: list[EvidenceRef] = field(default_factory=list)


@dataclass
class PeriodExtraction:
    year: str
    inputs: EbFinancialInputs
    field_evidence: dict[str, FieldEvidence]


def financial_inputs_by_period(canonical: CanonicalResult) -> dict[str, PeriodExtraction]:
    result: dict[str, PeriodExtraction] = {}
    for year, fields in canonical.fields_by_year.items():
        values: dict[str, float] = {}
        evidence: dict[str, FieldEvidence] = {}
        for ma, attr in FIELD_CODE_MAP.items():
            if attr is None:
                continue
            cf = fields.get(ma)
            if cf is None or not cf.co_gia_tri:
                status = "PENDING_REVIEW" if (cf is not None and cf.evidence) else "MISSING_DATA"
                evidence[attr] = FieldEvidence(status=status, evidence=cf.evidence if cf else [])
                continue
            values[attr] = cf.gia_tri
            evidence[attr] = FieldEvidence(status="COMPUTED", evidence=cf.evidence)
        result[year] = PeriodExtraction(year=year, inputs=EbFinancialInputs(**values), field_evidence=evidence)
    return result


def select_richest_period(period_extractions: dict[str, "PeriodExtraction"]) -> str | None:
    """Picks the period with the most populated fields, tie-broken by the
    newest year — never just the newest year outright. A single upload can
    bundle an unrelated sheet (e.g. a bank statement) alongside the real
    BCTC; if any of its rows coincidentally satisfy a field pattern, that
    creates a near-empty period bucket for a later year that would
    otherwise silently outrank the real, richly-populated BCTC period
    (auto-selection sorted by year number alone always prefers the newer,
    emptier bucket over the correct one)."""
    if not period_extractions:
        return None

    def _populated_count(year: str) -> int:
        inputs = period_extractions[year].inputs
        return sum(1 for v in vars(inputs).values() if v is not None)

    return max(period_extractions, key=lambda year: (_populated_count(year), year))
