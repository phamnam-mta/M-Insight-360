from dataclasses import dataclass, field


@dataclass
class RbCustomer:
    full_name: str | None = None
    gender: str | None = None  # "male" | "female"
    date_of_birth: str | None = None  # ISO "YYYY-MM-DD"
    nationality: str | None = None
    id_number: str | None = None
    tax_id: str | None = None
    permanent_address: str | None = None
    temporary_address: str | None = None
    contact_address: str | None = None
    phone_mobile: str | None = None
    phone_home: str | None = None
    email: str | None = None
    marital_status: str | None = None  # "single"|"married"|"divorced"|"widowed"
    education_level: str | None = None


@dataclass
class RbLegal:
    id_type: str | None = None  # "CCCD" | "CMND" | "PASSPORT"
    id_issue_date: str | None = None
    id_issue_place: str | None = None
    business_registration_number: str | None = None
    business_registration_issue_date: str | None = None
    business_registration_issue_place: str | None = None


@dataclass
class RbIncome:
    source_type: str | None = None  # salary|business|self_employed|household_business
    # Nguồn thu từ kinh doanh
    business_name: str | None = None
    business_sector: str | None = None
    business_years: float | None = None
    business_address: str | None = None
    # Nguồn thu từ lương
    employer_name: str | None = None
    employer_address: str | None = None
    position: str | None = None
    employment_years: float | None = None
    # Tài chính (khớp mục "1. Thu nhập / 2. Chi phí" của form MB01A)
    income_salary_vnd: float | None = None
    income_rental_vnd: float | None = None
    income_business_vnd: float | None = None
    income_guarantor_vnd: float | None = None
    expense_living_vnd: float | None = None
    expense_other_debt_vnd: float | None = None
    expense_other_vnd: float | None = None
    dependents_count: int | None = None
    tax_declaration_present: bool = False


@dataclass
class RbLoan:
    product: str | None = None  # "vay_von" — luồng vay vốn (khoản vay), phạm vi bản này
    purpose: str | None = None
    amount_vnd: float | None = None
    tenor_months: int | None = None
    annual_rate: float | None = None
    existing_monthly_obligation_vnd: float | None = None
    repayment_method: str | None = None


@dataclass
class RbCollateral:
    items: list[dict] = field(default_factory=list)
    # mỗi item: {"asset_type": str, "ownership_status": str, "estimated_value_vnd": float}


@dataclass
class RbOther:
    notes: str | None = None
    existing_credit_relationships: list[dict] = field(default_factory=list)
    # mỗi item: {"institution": str, "credit_type": str, "outstanding_vnd": float,
    #            "monthly_payment_vnd": float}
