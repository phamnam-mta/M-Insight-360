import io

import docx

DISCLAIMER = (
    "Đánh giá này được tạo nhằm hỗ trợ RM/Credit Officer xem xét hồ sơ. "
    "Không phải quyết định phê duyệt hoặc từ chối tín dụng tự động."
)

TEMPLATE_NOTE = (
    "Theo cấu trúc mẫu MB02a/QT.RR.037 To trinh TD cua HO (SME, MC) — mẫu MB02c gốc không có "
    "trong bộ dữ liệu cung cấp nên đây là thay thế đã ghi nhận (spec §6). Các mục ký duyệt nội bộ "
    "để trống cho RM/CBTĐ điền tay."
)


def _format_metric_value(metric) -> str:
    """Never fabricate a number: show the metric only when it has one."""
    if not isinstance(metric, dict):
        return str(metric) if metric is not None else "[chưa có]"
    status = metric.get("status", "OK")
    value = metric.get("value")
    if status != "OK" or value is None:
        return "NEED_MORE_DATA (chưa đủ dữ liệu để tính)"
    return str(value)


def build_mb02_docx(computed: dict, stress_scenario: dict | None = None) -> bytes:
    computed = computed or {}
    profile = computed.get("customer_profile") or {}
    document = docx.Document()

    document.add_heading("TỜ TRÌNH THẨM ĐỊNH TÍN DỤNG (Dự thảo AI hỗ trợ)", level=1)
    document.add_paragraph(TEMPLATE_NOTE)

    document.add_heading("A. Tổng quan khách hàng", level=2)
    document.add_paragraph(f"Tên khách hàng: {profile.get('customer_name', '[chưa có]')}")
    document.add_paragraph(f"Mã số thuế: {profile.get('tax_id', '[chưa có]')}")

    document.add_heading("B. Các chỉ số từ Credit Engine", level=2)
    credit_engine = computed.get("credit_engine") or {}
    if not credit_engine:
        document.add_paragraph("Chưa có chỉ số nào được tính (thiếu dữ liệu đầu vào).")
    for name, metric in credit_engine.items():
        document.add_paragraph(f"{name}: {_format_metric_value(metric)}", style="List Bullet")

    document.add_heading("C. Các điểm rủi ro", level=2)
    risk_flags = computed.get("risk_flags") or []
    if not risk_flags:
        document.add_paragraph("Không có cảnh báo rủi ro được kích hoạt.")
    for flag in risk_flags:
        if not isinstance(flag, dict):
            continue
        line = f"{flag.get('rule_id', '?')} — {flag.get('rule_name', '')} ({flag.get('severity') or 'N/A'}, {flag.get('status', '')})"
        document.add_paragraph(line, style="List Bullet")
        if flag.get("threshold"):
            document.add_paragraph(f"  Ngưỡng: {flag['threshold']}")
        if flag.get("observed_value") is not None:
            document.add_paragraph(f"  Giá trị quan sát: {flag['observed_value']}")
        for ev in flag.get("evidence") or []:
            document.add_paragraph(f"  Bằng chứng: {ev}")
        if flag.get("verification_question"):
            document.add_paragraph(f"  Câu hỏi xác minh: {flag['verification_question']}")
        if flag.get("recommended_action"):
            document.add_paragraph(f"  Đề xuất kiểm soát: {flag['recommended_action']}")

    document.add_heading("D. Hồ sơ còn thiếu", level=2)
    missing = computed.get("missing_data") or []
    if not missing:
        document.add_paragraph("Không có.")
    for item in missing:
        document.add_paragraph(str(item), style="List Bullet")

    document.add_heading("E. Khuyến nghị để Credit Officer xem xét", level=2)
    document.add_paragraph(computed.get("recommendation") or "[chưa có]")

    document.add_heading("F. Vì sao?", level=2)
    why = computed.get("why") or []
    if not why:
        document.add_paragraph("Chưa có nhận xét bổ sung.")
    for line in why:
        document.add_paragraph(str(line), style="List Bullet")

    document.add_heading("G. Tóm tắt dự thảo Credit Memo", level=2)
    document.add_paragraph(computed.get("credit_memo") or "[chưa có]")

    document.add_heading("H. Bảng điều kiện tổng quan (mục A)", level=2)
    overview = computed.get("overview") or []
    if not overview:
        document.add_paragraph("Chưa có dữ liệu điều kiện tổng quan.")
    for row in overview:
        if not isinstance(row, dict):
            continue
        observed = row.get("observed") or {}
        value = observed.get("value")
        value_text = "Chưa có dữ liệu" if value is None else str(value)
        line = f"{row.get('condition_name', '?')}: {value_text} — Kết quả: {row.get('result', '?')}"
        document.add_paragraph(line, style="List Bullet")
        if row.get("reason_if_incomplete"):
            document.add_paragraph(f"  Lý do: {row['reason_if_incomplete']}")

    if stress_scenario:
        document.add_heading("I. Kịch bản Stress Test đính kèm", level=2)
        document.add_paragraph(f"Tên kịch bản: {stress_scenario.get('name', '[chưa có]')}")
        response = stress_scenario.get("response", {})
        before_dscr = _format_metric_value(response.get("before", {}).get("dscr"))
        after_dscr = _format_metric_value(response.get("after", {}).get("dscr"))
        document.add_paragraph(f"DSCR trước stress: {before_dscr} → sau stress: {after_dscr}")
        document.add_paragraph(
            "Mô phỏng theo giả định — không thay thế thẩm định tín dụng và phê duyệt MSB."
        )

    document.add_paragraph("")
    document.add_paragraph(DISCLAIMER)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
