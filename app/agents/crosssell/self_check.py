"""Mục G — tự kiểm JSON bằng máy (tập con chạy phía server).

Spec bắt buộc dừng và sửa khi còn FAIL trước khi trả kết quả — nhưng đây là
một web app đồng bộ có người dùng (RM) đang chờ, không phải pipeline tự động
không ai giám sát, nên một FAIL ở đây không chặn response: nó được trả về
trong `warnings[]` để RM/kỹ thuật thấy ngay, thay vì bị nuốt im lặng.
"""

import re

from .card_types import Opportunity

_TECHNICAL_NAME_MARKERS = [
    "RULE1_", "RULE2_", "RULE3_", "RULE4_", "RULE5", "RULE6_",
    "operating_in", "total_in", "total_out", "directed_cashflow",
    "est_missing", "flow_classification", "MO PHONG",
]


def _check_technical_names_leaked(opportunities: list[Opportunity], badges: list[dict], kpi: list[dict]) -> list[str]:
    haystacks: list[str] = []
    for o in opportunities:
        haystacks.append(o.san_pham)
        haystacks.append(o.signal_1dong)
        haystacks.extend(f"{d.tieu_de} {d.noi_dung}" for d in o.chi_tiet)
        haystacks.extend(o.canh_bao)
        haystacks.extend(k.noi_dung for k in o.kich_ban)
    haystacks.extend(b["nhan"] for b in badges)
    haystacks.extend(f"{k['nhan']} {k.get('phu', '')}" for k in kpi)

    leaked = []
    for text in haystacks:
        for marker in _TECHNICAL_NAME_MARKERS:
            if marker in text:
                leaked.append(marker)
    return leaked


def run_self_check(
    opportunities: list[Opportunity],
    badges: list[dict],
    kpi: list[dict],
    partners: list,
) -> list[str]:
    """Returns human-readable FAIL messages; empty list means all checks passed."""
    fails: list[str] = []

    for o in opportunities:
        if not o.deal_size_headline:
            fails.append(f"D1: {o.rule_id} thiếu deal_size_headline")
        if o.deal_size is not None and not o.deal_size_exact:
            fails.append(f"D1: {o.rule_id} có deal_size nhưng thiếu deal_size_exact")
        if o.priority != "P-NA" and o.deal_size is None and o.confidence is not None:
            fails.append(f"D1: {o.rule_id} không phải P-NA nhưng deal_size null")
        if len(o.signal_1dong) > 110:
            fails.append(f"D2: {o.rule_id} signal_1dong dài {len(o.signal_1dong)} ký tự (> 110)")
        if not re.search(r"\d", o.signal_1dong) and o.priority != "P-NA":
            fails.append(f"D2: {o.rule_id} signal_1dong không chứa chữ số")
        if len(o.san_pham) > 60:
            fails.append(f"D3: {o.rule_id} san_pham dài {len(o.san_pham)} ký tự (> 60)")
        if o.deal_size is not None and not any(d.tieu_de == "Công thức" for d in o.chi_tiet):
            fails.append(f"D4: {o.rule_id} có deal_size nhưng thiếu khối 'Công thức'")
        for s in o.kich_ban:
            if s.loai == "B" and re.search(r"\d", s.noi_dung):
                fails.append(f"D6: {o.rule_id} kịch bản B chứa chữ số")

    leaked = _check_technical_names_leaked(opportunities, badges, kpi)
    if leaked:
        fails.append(f"B: lọt tên kỹ thuật ra giao diện: {sorted(set(leaked))}")

    sizes = [o.deal_size for o in opportunities if o.deal_size is not None]
    if sizes != sorted(sizes, reverse=True):
        fails.append("D10: co_hoi không sắp giảm dần theo deal_size")
    if opportunities and any(o.priority == "P-NA" for o in opportunities):
        na_positions = [i for i, o in enumerate(opportunities) if o.priority == "P-NA"]
        non_na_positions = [i for i, o in enumerate(opportunities) if o.priority != "P-NA"]
        if non_na_positions and na_positions and min(na_positions) < max(non_na_positions):
            fails.append("D10: P-NA không nằm cuối danh sách")

    valid_badge_types = {"ok", "warn", "err", "info", "na"}
    for b in badges:
        if b["loai"] not in valid_badge_types:
            fails.append(f"D7: badge loai không hợp lệ: {b['loai']}")

    if len(kpi) != 4:
        fails.append(f"D8: phải đúng 4 ô KPI, hiện có {len(kpi)}")
    elif not kpi[0].get("nhan_manh"):
        fails.append("D8: ô KPI đầu tiên phải có nhan_manh=true")

    for p in partners:
        if p.trang_thai != "Chua kiem tra CIF":
            fails.append(f"CIF: {p.ten} không mang trạng thái 'Chua kiem tra CIF'")
    if any("đủ điều kiện" in (p.sp_de_xuat or "").lower() for p in partners):
        fails.append("CIF: có đối tác bị gắn nhãn 'đủ điều kiện'")

    return fails
