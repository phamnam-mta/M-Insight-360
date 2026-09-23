from dataclasses import asdict

from app.agents.rb_portal.models import (
    RbCollateral, RbCustomer, RbIncome, RbLegal, RbLoan, RbOther,
)


def test_rb_customer_all_fields_default_to_none():
    c = RbCustomer()
    d = asdict(c)
    assert d["full_name"] is None
    assert d["gender"] is None
    assert d["marital_status"] is None


def test_rb_customer_round_trips_through_asdict():
    c = RbCustomer(full_name="NGUYEN VAN A", gender="male", tax_id="0100000001")
    assert asdict(c)["full_name"] == "NGUYEN VAN A"


def test_rb_income_source_type_field():
    i = RbIncome(source_type="business", business_name="Quan Com A")
    assert asdict(i)["source_type"] == "business"


def test_rb_collateral_items_default_to_empty_list():
    col = RbCollateral()
    assert asdict(col)["items"] == []


def test_rb_legal_and_loan_and_other_construct_empty():
    assert asdict(RbLegal())["id_type"] is None
    assert asdict(RbLoan())["product"] is None
    assert asdict(RbOther())["notes"] is None
