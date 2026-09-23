from app.agents.eb.field_codes import FIELD_CODE_MAP, compute_total_assets_vnd
from app.agents.eb.financial_inputs import EbFinancialInputs


def test_field_code_map_covers_every_instruction_field():
    expected_codes = {
        "IS_REVENUE", "IS_COGS", "IS_PBT", "IS_PAT", "IS_INTEREST",
        "IS_DEPRECIATION", "BS_CURRENT_ASSETS", "BS_CURRENT_LIABILITIES",
        "BS_NON_CURRENT_ASSETS", "BS_TOTAL_ASSETS", "BS_EQUITY",
        "BS_CHARTER_CAPITAL", "BS_LT_BORROWINGS", "BS_ST_BORROWINGS",
        "BS_AR_CUSTOMER", "BS_INVENTORY", "BS_AP_SUPPLIER", "BS_CASH",
        "DEBT_PRINCIPAL_DUE",
    }
    assert expected_codes.issubset(FIELD_CODE_MAP.keys())


def test_field_code_map_values_are_real_dataclass_fields_or_none():
    real_fields = set(EbFinancialInputs.__dataclass_fields__)
    for code, attr in FIELD_CODE_MAP.items():
        assert attr is None or attr in real_fields, f"{code} -> {attr} is not a real field"


def test_compute_total_assets_sums_current_and_non_current():
    inputs = EbFinancialInputs(current_assets_vnd=100, non_current_assets_vnd=50)
    assert compute_total_assets_vnd(inputs) == 150


def test_compute_total_assets_missing_either_side_is_none():
    assert compute_total_assets_vnd(EbFinancialInputs(current_assets_vnd=100)) is None
