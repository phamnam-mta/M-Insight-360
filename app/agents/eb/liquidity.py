from app.engine.core.types import Metric, RuleResult

from .financial_inputs import EbFinancialInputs

RF01_POLICY_VERSION = "policy_mode=DEMO_UAT (ngưỡng demo, chưa xác nhận chuẩn MSB chính thức)"


def compute_nwc(inputs: EbFinancialInputs) -> Metric:
    if inputs.current_assets_vnd is None or inputs.current_liabilities_vnd is None:
        return Metric.need_more_data("nwc", "tai_san_ngan_han - no_ngan_han")
    value = inputs.current_assets_vnd - inputs.current_liabilities_vnd
    return Metric(
        metric="nwc",
        value=value,
        formula="tai_san_ngan_han - no_ngan_han",
        input_values={"current_assets_vnd": inputs.current_assets_vnd, "current_liabilities_vnd": inputs.current_liabilities_vnd},
        input_sources={"current_assets_vnd": "bctc", "current_liabilities_vnd": "bctc"},
    )


def compute_current_ratio(inputs: EbFinancialInputs) -> Metric:
    if (
        inputs.current_assets_vnd is None
        or inputs.current_liabilities_vnd is None
        or inputs.current_liabilities_vnd <= 0
    ):
        return Metric.need_more_data("current_ratio", "tai_san_ngan_han / no_ngan_han")
    value = round(inputs.current_assets_vnd / inputs.current_liabilities_vnd, 4)
    return Metric(
        metric="current_ratio",
        value=value,
        formula="tai_san_ngan_han / no_ngan_han",
        input_values={"current_assets_vnd": inputs.current_assets_vnd, "current_liabilities_vnd": inputs.current_liabilities_vnd},
        input_sources={"current_assets_vnd": "bctc", "current_liabilities_vnd": "bctc"},
    )


def evaluate_rf01_capital_imbalance(inputs: EbFinancialInputs, nwc: Metric) -> RuleResult:
    if inputs.equity_vnd is None and nwc.status == "NEED_MORE_DATA":
        return RuleResult(
            rule_id="RF01", rule_name="Mất cân đối vốn", status="CHƯA ĐÁNH GIÁ",
            comment="Thiếu vốn chủ sở hữu và/hoặc dữ liệu vốn lưu động ròng để đánh giá.",
            verification_question="Hồ sơ có Bảng cân đối kế toán kỳ gần nhất để xác định VCSH và NWC không?",
            recommended_action="Bổ sung BCTC/Bảng cân đối kế toán trước khi kết luận về mất cân đối vốn.",
        )

    equity_negative = inputs.equity_vnd is not None and inputs.equity_vnd <= 0
    nwc_negative = nwc.status == "OK" and isinstance(nwc.value, (int, float)) and nwc.value < 0

    if equity_negative or nwc_negative:
        evidence = []
        if equity_negative:
            evidence.append(f"Vốn chủ sở hữu = {inputs.equity_vnd} (≤ 0)")
        if nwc_negative:
            evidence.append(f"NWC = {nwc.value} (< 0)")
        observed_value = nwc.value if nwc.status == "OK" else inputs.equity_vnd
        return RuleResult(
            rule_id="RF01", rule_name="Mất cân đối vốn", status="KÍCH HOẠT", severity="HIGH",
            evidence=evidence, threshold="quy tắc demo: VCSH ≤ 0 hoặc NWC < 0", formula=nwc.formula,
            comment="Có dấu hiệu dùng nguồn vốn ngắn hạn tài trợ tài sản dài hạn — cần rà soát áp lực thanh khoản.",
            observed_value=observed_value,
            policy_version=RF01_POLICY_VERSION,
            verification_question="Nguồn vốn ngắn hạn có đang tài trợ cho tài sản dài hạn không? Kế hoạch tái cơ cấu vốn của khách hàng là gì?",
            recommended_action="Yêu cầu khách hàng giải trình và bổ sung phương án tăng vốn/cơ cấu lại nguồn vốn trước khi cấp tín dụng.",
        )

    return RuleResult(
        rule_id="RF01", rule_name="Mất cân đối vốn", status="KHÔNG KÍCH HOẠT",
        observed_value=nwc.value if nwc.status == "OK" else inputs.equity_vnd,
        policy_version=RF01_POLICY_VERSION,
    )
