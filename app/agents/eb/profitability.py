from app.engine.core.types import Metric

from .financial_inputs import EbFinancialInputs


def _evidence_for(field_evidence: dict | None, *keys: str) -> dict:
    if not field_evidence:
        return {}
    return {k: field_evidence[k].evidence for k in keys if k in field_evidence}


def resolve_ebit_vnd(inputs: EbFinancialInputs) -> float | None:
    """Prefer a directly extracted EBIT line (rare in VN BCTC); else compute
    PBT + interest expense from real extracted figures — this is the spec's
    own CALC_EBIT formula, not a suy diễn, since VN BCTC almost never has a
    literal "EBIT" line item."""
    if inputs.ebit_vnd is not None:
        return inputs.ebit_vnd
    if inputs.pbt_vnd is not None and inputs.interest_expense_vnd is not None:
        return inputs.pbt_vnd + inputs.interest_expense_vnd
    return None


def compute_ebitda(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> Metric:
    ebit = resolve_ebit_vnd(inputs)
    if ebit is None or inputs.depreciation_vnd is None:
        return Metric.need_more_data("ebitda", "EBIT + khau_hao")
    value = ebit + inputs.depreciation_vnd
    return Metric(
        metric="ebitda", value=value, formula="EBIT + khau_hao",
        input_values={"ebit_vnd": ebit, "depreciation_vnd": inputs.depreciation_vnd},
        input_sources={"ebit_vnd": "bctc", "depreciation_vnd": "bctc"},
        evidence=_evidence_for(field_evidence, "pbt_vnd", "interest_expense_vnd", "depreciation_vnd"),
    )
