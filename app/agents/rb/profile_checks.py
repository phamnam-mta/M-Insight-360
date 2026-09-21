import re

from app.engine.core.types import RuleResult
from app.extraction.types import ExtractedDocument

# VN tax IDs are 10 digits, optionally with a 3-digit branch suffix
# ("0319998887" or "0319998887-001" / "0319998887001").
TAX_ID_PATTERN = re.compile(r"\b\d{10}(?:-?\d{3})?\b")
_VALID_TAX_ID_FORMAT = re.compile(r"^\d{10}(\d{3})?$")


def _normalize(raw: str) -> str:
    return raw.replace("-", "").replace(" ", "").strip()


def check_tax_id_consistency(
    declared_tax_id: str, documents: list[ExtractedDocument]
) -> RuleResult:
    declared_normalized = _normalize(declared_tax_id or "")
    declared_is_well_formed = bool(_VALID_TAX_ID_FORMAT.match(declared_normalized))

    found_ids: set[str] = set()
    for doc in documents:
        found_ids.update(_normalize(m) for m in TAX_ID_PATTERN.findall(doc.text))

    if not found_ids:
        return RuleResult(
            rule_id="TAX_ID_MISMATCH",
            rule_name="Đối chiếu mã số thuế",
            status="CHƯA ĐÁNH GIÁ",
            comment="Không tìm thấy mã số thuế nào trong hồ sơ để đối chiếu.",
        )

    if not declared_is_well_formed:
        # Declared tax ID doesn't fit VN's 10/13-digit format — this is a weak,
        # low-confidence comparison, not something to raise/crash on.
        return RuleResult(
            rule_id="TAX_ID_MISMATCH",
            rule_name="Đối chiếu mã số thuế",
            status="CHƯA ĐÁNH GIÁ",
            comment=(
                "Mã số thuế khai báo không đúng định dạng 10/13 số theo quy định VN — "
                "không thể đối chiếu tin cậy, cần nhập lại hoặc xác minh thủ công."
            ),
            evidence=[f"MST khai báo trên form: {declared_tax_id}"],
        )

    mismatches = found_ids - {declared_normalized}
    if mismatches:
        return RuleResult(
            rule_id="TAX_ID_MISMATCH",
            rule_name="Đối chiếu mã số thuế",
            status="KÍCH HOẠT",
            severity="HIGH",
            evidence=[
                f"MST khai báo trên form: {declared_tax_id}",
                f"MST tìm thấy trong hồ sơ: {', '.join(sorted(mismatches))}",
            ],
            comment=(
                "Mã số thuế trong hồ sơ không khớp với mã số thuế khai báo. "
                "Cần xác minh thủ công — không kết luận là chứng từ không hợp lệ."
            ),
            verification_question=(
                "Vui lòng xác nhận mã số thuế chính xác của khách hàng và giải thích "
                "sự khác biệt giữa mã số thuế khai báo và mã số thuế trong hồ sơ."
            ),
            recommended_action="Chuyển Credit Officer xác minh thủ công mã số thuế trước khi thẩm định tiếp.",
        )
    return RuleResult(
        rule_id="TAX_ID_MISMATCH",
        rule_name="Đối chiếu mã số thuế",
        status="KHÔNG KÍCH HOẠT",
    )
