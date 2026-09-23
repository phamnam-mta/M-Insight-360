"""L2-bis — 4 sanity checks run before a value reaches the screen or the
export (instruction §L2-bis). A field this module flags renders as
`unknown` with the given reason, never as the real (possibly wrong)
number: "thà báo unknown còn hơn hiển thị một con số sai"."""

from dataclasses import dataclass, field

from .field_codes import compute_total_assets_vnd
from .financial_inputs import EbFinancialInputs

_BIG_SCALE_FIELDS = ("net_revenue_vnd", "pbt_vnd", "pat_vnd")
_BIG_SCALE_THRESHOLD_VND = 1_000_000_000  # a company this big triggers check #2
_UNDERSIZED_THRESHOLD_VND = 1_000_000  # < 7 digits
_INCOME_STATEMENT_GROUP = (
    "net_revenue_vnd", "cogs_vnd", "pbt_vnd", "pat_vnd",
    "interest_expense_vnd", "depreciation_vnd",
)
_BALANCE_TOLERANCE_VND = 1_000


@dataclass
class SanityCheckResult:
    suspect_fields: dict[str, str] = field(default_factory=dict)
    balance_mismatch: bool = False
    balance_mismatch_detail: str | None = None


def _check_year_collision(inputs: EbFinancialInputs, year: str | None, out: dict[str, str]) -> None:
    if year is None:
        return
    try:
        year_int = int(year)
    except ValueError:
        return
    candidates = {float(year_int - 1), float(year_int), float(year_int + 1)}
    for attr, value in vars(inputs).items():
        if isinstance(value, (int, float)) and float(value) in candidates:
            out[attr] = (
                f"Giá trị đọc được nghi ngờ sai dòng ({value:g} trùng số năm báo cáo "
                f"{year}), đề nghị kiểm tra lại hồ sơ nguồn."
            )


def _check_undersized_at_scale(inputs: EbFinancialInputs, out: dict[str, str]) -> None:
    total_assets = compute_total_assets_vnd(inputs)
    if total_assets is None or total_assets < _BIG_SCALE_THRESHOLD_VND:
        return
    for attr in _BIG_SCALE_FIELDS:
        value = getattr(inputs, attr)
        if value is not None and 0 < abs(value) < _UNDERSIZED_THRESHOLD_VND:
            out.setdefault(attr, (
                "Giá trị đọc được nghi ngờ sai dòng (số quá nhỏ so với quy mô doanh nghiệp "
                "tỷ đồng), đề nghị kiểm tra lại hồ sơ nguồn."
            ))


def _check_single_field_in_group(inputs: EbFinancialInputs, out: dict[str, str]) -> None:
    present = [attr for attr in _INCOME_STATEMENT_GROUP if getattr(inputs, attr) is not None]
    if len(present) == 1:
        out.setdefault(present[0], (
            "Giá trị đọc được nghi ngờ sai dòng (chỉ 1 trường duy nhất trích được trong "
            "nhóm Kết quả kinh doanh — có thể bảng bị lệch cột), đề nghị kiểm tra lại hồ sơ nguồn."
        ))


def _check_balance(inputs: EbFinancialInputs, result: SanityCheckResult) -> None:
    total_assets = compute_total_assets_vnd(inputs)
    if total_assets is None or inputs.equity_vnd is None or inputs.total_liabilities_vnd is None:
        return
    total_capital = inputs.equity_vnd + inputs.total_liabilities_vnd
    if abs(total_assets - total_capital) > _BALANCE_TOLERANCE_VND:
        result.balance_mismatch = True
        result.balance_mismatch_detail = (
            f"Tổng tài sản ({total_assets:,.0f}) khác Tổng nguồn vốn ({total_capital:,.0f}) — "
            "hồ sơ BCTC tải lên chưa cân đối, đề nghị khách hàng bổ sung bản chuẩn."
        )


def run_sanity_checks(inputs: EbFinancialInputs, year: str | None) -> SanityCheckResult:
    result = SanityCheckResult()
    _check_year_collision(inputs, year, result.suspect_fields)
    _check_undersized_at_scale(inputs, result.suspect_fields)
    _check_single_field_in_group(inputs, result.suspect_fields)
    _check_balance(inputs, result)
    return result
