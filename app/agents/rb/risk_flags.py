from app.engine.core.types import Metric, RuleResult

HIGH_DTI_THRESHOLD = 0.5


def compute_risk_flags(
    mandatory_check: dict,
    tax_id_result: RuleResult,
    dti_metric: Metric,
    classified_documents: list[tuple[str, str, float]] | None = None,
) -> list[RuleResult]:
    """Risk flags for an RB case.

    ``classified_documents`` is (filename, doc_type, confidence) per uploaded
    document, so a document the classifier could not place can flag the case
    for manual review instead of being silently dropped.
    """
    flags: list[RuleResult] = []

    if tax_id_result.status == "KÍCH HOẠT":
        flags.append(tax_id_result)

    if mandatory_check["missing"]:
        flags.append(
            RuleResult(
                rule_id="MISSING_MANDATORY_DOCUMENT",
                rule_name="Thiếu hồ sơ bắt buộc",
                status="KÍCH HOẠT",
                severity="HIGH",
                evidence=list(mandatory_check["missing"]),
                comment="Hồ sơ chưa đủ các loại chứng từ bắt buộc theo luồng sản phẩm.",
                recommended_action="Yêu cầu khách hàng bổ sung các chứng từ còn thiếu trước khi thẩm định.",
            )
        )

    unclassified = [
        (filename, confidence)
        for filename, doc_type, confidence in (classified_documents or [])
        if doc_type == "UNCLASSIFIED"
    ]
    if unclassified:
        # RB plan Global Constraint / spec §5: classification confidence below
        # threshold → UNCLASSIFIED + case flagged MANUAL_REVIEW_REQUIRED, never
        # silently dropped. HIGH severity is what determine_readiness reads to
        # return MANUAL_REVIEW_REQUIRED.
        flags.append(
            RuleResult(
                rule_id="UNCLASSIFIED_DOCUMENT",
                rule_name="Chứng từ chưa phân loại được",
                status="KÍCH HOẠT",
                severity="HIGH",
                evidence=[
                    f"{filename}: độ tin cậy phân loại {confidence:.2f} dưới ngưỡng"
                    for filename, confidence in unclassified
                ],
                comment=(
                    "Có chứng từ không phân loại được tự động — hồ sơ cần cán bộ "
                    "thẩm định xem xét thủ công, không được bỏ qua chứng từ này."
                ),
                recommended_action=(
                    "Chuyển Credit Officer phân loại thủ công các chứng từ chưa xác định "
                    "trước khi kết luận thẩm định."
                ),
            )
        )

    if dti_metric.status == "OK" and isinstance(dti_metric.value, (int, float)) and dti_metric.value > HIGH_DTI_THRESHOLD:
        flags.append(
            RuleResult(
                rule_id="HIGH_DTI",
                rule_name="Tỷ lệ nợ trên thu nhập cao",
                status="KÍCH HOẠT",
                severity="HIGH",
                evidence=[f"DTI = {dti_metric.value} (ngưỡng demo {HIGH_DTI_THRESHOLD})"],
                threshold=f"quy tắc demo: DTI > {HIGH_DTI_THRESHOLD}",
                comment="DTI vượt ngưỡng demo — cần Credit Officer xem xét kỹ khả năng trả nợ.",
                recommended_action="Chuyển Credit Officer đánh giá thêm khả năng trả nợ trước khi ra quyết định.",
            )
        )

    return flags
