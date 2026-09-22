"""0B — Kiểm tra chất lượng bóc tên, với đủ 4 chỉ số kèm tử số/mẫu số.

Spec §0B: pre-check chỉ đối chiếu SỐ TIỀN, tên bóc sai vẫn PASS — đây là hàng
rào thứ hai, bắt cả trường hợp ngân hàng đổi mẫu sao kê (toạ độ cột viết
cứng, đổi mẫu thì tên vỡ nhưng số tiền vẫn khớp).
"""

import re
import unicodedata
from dataclasses import dataclass

from .statement_parser import Transaction

# Spec §0B examples of a name cut off at the front by a hard-coded column
# offset: "PANY" (from "...company" truncated), "ONG TY" (missing the leading
# "C" of "CONG TY"), "NHH" (missing the leading "T" of "TNHH"). A normal name
# that legitimately starts with "CONG TY" or "TNHH" must never match here.
_TRUNCATED_FRAGMENTS = ("PANY", "ONG TY", "NHH")


def _strip_accents_upper(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).upper()


def _starts_with_truncated_fragment(name: str) -> bool:
    upper = _strip_accents_upper(name.strip())
    return any(upper.startswith(frag) for frag in _TRUNCATED_FRAGMENTS)


@dataclass
class QualityMetric:
    label: str
    numerator: int
    denominator: int
    threshold_pct: float
    passed: bool

    @property
    def pct(self) -> float:
        return round(self.numerator / self.denominator * 100, 1) if self.denominator else 0.0

    @property
    def result_text(self) -> str:
        return f"{self.numerator}/{self.denominator} = {self.pct}%".replace(".", ",")


@dataclass
class QualityResult:
    verdict: str  # "PASS" | "WARN"
    metrics: list[QualityMetric]
    confidence_cap: str


def check_name_quality_v2(transactions: list[Transaction]) -> QualityResult:
    total = len(transactions)
    with_name = [t for t in transactions if t.partner.strip()]
    named_total = len(with_name)

    empty = sum(1 for t in transactions if not t.partner.strip())
    empty_metric = QualityMetric("Tên đối tác rỗng", empty, total, 20.0, (empty / total * 100 if total else 0) <= 20.0)

    short = sum(1 for t in with_name if len(t.partner.strip()) < 8)
    short_metric = QualityMetric("Tên < 8 ký tự", short, named_total, 10.0, (short / named_total * 100 if named_total else 0) <= 10.0)

    no_space = sum(1 for t in with_name if " " not in t.partner.strip())
    no_space_metric = QualityMetric("Tên không có khoảng trắng", no_space, named_total, 10.0, (no_space / named_total * 100 if named_total else 0) <= 10.0)

    truncated = sum(1 for t in with_name if _starts_with_truncated_fragment(t.partner))
    truncated_metric = QualityMetric("Tên cụt đầu", truncated, named_total, 0.0, truncated == 0)

    metrics = [empty_metric, short_metric, no_space_metric, truncated_metric]
    warn = any(not m.passed for m in metrics)
    return QualityResult(
        verdict="WARN" if warn else "PASS",
        metrics=metrics,
        confidence_cap="M" if warn else "H",
    )
