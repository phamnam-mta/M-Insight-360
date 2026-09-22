from dataclasses import dataclass, field
from typing import Any, Literal

FieldStatus = Literal["VERIFIED", "COMPUTED", "PENDING_REVIEW", "MISSING_DATA", "NOT_APPLICABLE"]
ConditionResult = Literal["PASS", "FAIL", "INSUFFICIENT_DATA", "PENDING_INTERNAL_CHECK", "NOT_APPLICABLE"]


@dataclass
class EvidenceRef:
    file_id: str
    filename: str
    location: str
    original_text: str
    period: str | None = None


@dataclass
class EvidencedField:
    field_id: str
    label: str
    value: float | str | None
    unit: str | None
    period: str | None
    status: FieldStatus
    evidence: list["EvidenceRef"] = field(default_factory=list)
    formula: str | None = None
    input_fields: list[str] = field(default_factory=list)
    policy_version: str | None = None
    last_verified_at: str | None = None

    def __post_init__(self) -> None:
        if self.status == "MISSING_DATA" and self.value is not None:
            raise ValueError(f"{self.field_id}: MISSING_DATA field must not carry a value")


@dataclass
class ConditionRow:
    condition_id: str
    condition_name: str
    observed: EvidencedField
    compare_rule: str
    result: ConditionResult
    reason_if_incomplete: str | None = None

    def __post_init__(self) -> None:
        if self.result in ("PASS", "FAIL") and self.observed.value is None:
            raise ValueError(f"{self.condition_id}: {self.result} requires observed.value")


@dataclass
class Metric:
    metric: str
    value: float | str | None
    formula: str
    input_values: dict[str, Any]
    input_sources: dict[str, str]
    status: str = "OK"  # "OK" | "NEED_MORE_DATA"
    evidence: dict[str, list["EvidenceRef"]] = field(default_factory=dict)
    policy_version: str | None = None

    @staticmethod
    def need_more_data(
        metric: str, formula: str, input_values: dict[str, Any] | None = None
    ) -> "Metric":
        return Metric(
            metric=metric,
            value=None,
            formula=formula,
            input_values=input_values or {},
            input_sources={},
            status="NEED_MORE_DATA",
        )


@dataclass
class RuleResult:
    rule_id: str
    rule_name: str
    status: str
    severity: str | None = None
    evidence: list[str] = field(default_factory=list)
    evidence_refs: dict[str, list["EvidenceRef"]] = field(default_factory=dict)
    threshold: str | None = None
    formula: str | None = None
    comment: str = ""
    observed_value: float | str | None = None
    policy_version: str | None = None
    verification_question: str | None = None
    recommended_action: str | None = None
