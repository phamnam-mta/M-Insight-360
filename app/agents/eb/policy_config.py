from dataclasses import dataclass
from typing import Any


@dataclass
class PolicyThreshold:
    value: Any
    doc_code: str | None = None
    version: str | None = None
    effective_date: str | None = None
    open_question: str | None = None
    is_demo: bool = True

    @property
    def policy_version_label(self) -> str:
        if self.is_demo:
            return "Ngưỡng demo – chờ nghiệp vụ xác nhận"
        return f"{self.doc_code} v{self.version} (hiệu lực {self.effective_date})"


POLICY_CONFIG: dict[str, PolicyThreshold] = {
    "REVENUE_12M_MIN_VND": PolicyThreshold(20_000_000_000),
    "REVENUE_12M_MAX_VND": PolicyThreshold(1_000_000_000_000),
    "MIN_OPERATING_MONTHS": PolicyThreshold(24),
    "TOP_PARTNERS_COUNT": PolicyThreshold(
        5,
        open_question=(
            "Áp dụng riêng đầu ra/đầu vào hay gộp — chờ chủ chính sách xác nhận."
        ),
    ),
    "PROHIBITED_INDUSTRIES": PolicyThreshold([]),
}
