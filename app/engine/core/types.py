from dataclasses import dataclass, field
from typing import Any


@dataclass
class Metric:
    metric: str
    value: float | str | None
    formula: str
    input_values: dict[str, Any]
    input_sources: dict[str, str]
    status: str = "OK"  # "OK" | "NEED_MORE_DATA"

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
    threshold: str | None = None
    formula: str | None = None
    comment: str = ""
    observed_value: float | str | None = None
    policy_version: str | None = None
    verification_question: str | None = None
    recommended_action: str | None = None
