"""Deterministic template-filled conclusions/actions for Stress Test v2 —
no LLM call, same reasoning as the Cross-sell agent's scenario_templates.py:
filling a fixed template from already-computed numbers rules out both
hallucination and latency risk for a synchronous endpoint."""

DSCR_THRESHOLD = 1.0
DSCR_THIN_BUFFER_THRESHOLD = 1.2  # matches the spec's own 1.0–1.2x "vàng, biên mỏng" band
ICR_THRESHOLD = 1.5

_ACTIONS_IN_ORDER = [
    "Yêu cầu bảng tuổi nợ phải thu và xác minh chất lượng bên mua.",
    "Rà soát dòng tiền trả nợ và lịch trả nợ chi tiết.",
    "Xem xét điều chỉnh kỳ hạn, điều kiện giải ngân hoặc cơ chế kiểm soát dòng tiền.",
    "Với QĐ 039: chỉ đề xuất hạn mức trên phần phải thu đủ điều kiện sau thẩm định bên mua/hóa đơn.",
]


def _ok(metric) -> bool:
    return metric.status == "OK" and metric.value is not None


def generate_conclusions(before: dict, after: dict, comprehensive: bool) -> list[str]:
    conclusions: list[str] = []
    dscr_before, dscr_after = before.get("dscr"), after.get("dscr")
    icr_before, icr_after = before.get("icr"), after.get("icr")

    if dscr_before and dscr_after and _ok(dscr_before) and _ok(dscr_after) and dscr_after.value < DSCR_THRESHOLD <= dscr_before.value:
        conclusions.append(
            f"Trong kịch bản này, DSCR giảm từ {dscr_before.value:.2f}x xuống {dscr_after.value:.2f}x, "
            f"dưới ngưỡng {DSCR_THRESHOLD:.1f}x."
        )
    if icr_before and icr_after and _ok(icr_before) and _ok(icr_after) and icr_after.value < ICR_THRESHOLD:
        conclusions.append(
            f"Chi phí lãi vay tăng khiến ICR giảm xuống {icr_after.value:.2f}x, cần xem xét cơ cấu kỳ hạn nợ "
            "hoặc bổ sung nguồn trả nợ."
        )
    if (
        dscr_before and dscr_after and _ok(dscr_before) and _ok(dscr_after)
        and dscr_after.value < dscr_before.value
        and DSCR_THRESHOLD <= dscr_after.value < DSCR_THIN_BUFFER_THRESHOLD
    ):
        conclusions.append(
            f"DSCR giảm từ {dscr_before.value:.2f}x xuống {dscr_after.value:.2f}x nhưng vẫn trên ngưỡng "
            f"{DSCR_THRESHOLD:.1f}x — vùng đệm mỏng hơn."
        )
    return conclusions[:3]


def generate_recommended_actions(before: dict, after: dict) -> list[str]:
    dscr_after, icr_after = after.get("dscr"), after.get("icr")
    dscr_weak = dscr_after and _ok(dscr_after) and dscr_after.value < DSCR_THRESHOLD
    icr_weak = icr_after and _ok(icr_after) and icr_after.value < ICR_THRESHOLD
    if not (dscr_weak or icr_weak):
        return []
    return list(_ACTIONS_IN_ORDER)
