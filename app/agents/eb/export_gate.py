"""S7 — Export Gate (instruction §S7). Decides whether the "Soạn tờ trình
MB02a" action auto-generates a file, warns-and-generates, or declines
(always overridable by a human via force — see S7.4). This module never
refuses credit; it only decides whether a draft auto-exports."""

from dataclasses import dataclass, field
from typing import Literal

from app.engine.core.types import Metric, RuleResult

Verdict = Literal["XUAT", "XUAT_KEM_CANH_BAO", "KHONG_XUAT_TU_DONG"]
BlockType = Literal["HARD", "SOFT"] | None

# The instruction's Nhóm A list has 7 bullets but two are the same
# condition worded twice (NWC âm ⟺ nợ ngắn hạn > tài sản ngắn hạn) — RF01
# already covers both. This is the closed set of rule IDs that count
# toward S7's signal math; RF02/RF03 remain real, displayed credit
# observations but are deliberately excluded here (spec decision D3).
NHOM_A_CANONICAL_RULE_IDS = frozenset({"RF01", "RF05", "RF09", "RF08", "RF07", "RF06"})

_MAX_SIGNALS_BEFORE_BLOCK = 3
_DSCR_HARD_THRESHOLD = 1.0
_ICR_HARD_THRESHOLD = 1.5


def _format_vnd_vn(value: float) -> str:
    """S1.2 locale rule: reasons strings are shown verbatim in the S7.3
    screen and the force banner — a raw Python float must never leak past
    this boundary."""
    formatted = f"{value:,.0f}"
    return formatted.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


@dataclass
class ExportGateResult:
    verdict: Verdict
    block_type: BlockType
    signal_count: int
    signals: list[RuleResult] = field(default_factory=list)
    data_warnings: list[RuleResult] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    loai_chan: str | None = None


def evaluate_export_gate(
    risk_flags: list[RuleResult],
    *,
    equity_vnd: float | None,
    dscr: Metric,
    icr: Metric,
    pre_check_blocked: bool = False,
    is_legal_entity: bool = True,
    loai_chan: str | None = None,
) -> ExportGateResult:
    if pre_check_blocked:
        reason = (
            "Hệ thống đọc ra hai kết quả khác nhau cho cùng một chỉ tiêu nên tạm dừng xuất tờ trình "
            "để anh/chị kiểm tra lại, tránh tờ trình mang số liệu không thống nhất."
            if loai_chan == "LECH_DU_LIEU"
            else "Hồ sơ khách hàng cung cấp chưa đầy đủ — không đọc được nội dung BCTC tải lên."
        )
        return ExportGateResult(
            verdict="KHONG_XUAT_TU_DONG", block_type="HARD", signal_count=0,
            reasons=[reason], loai_chan=loai_chan,
        )
    if not is_legal_entity:
        return ExportGateResult(
            verdict="KHONG_XUAT_TU_DONG", block_type="HARD", signal_count=0,
            reasons=["Hồ sơ không phải BCTC pháp nhân."],
        )

    signals = [f for f in risk_flags if f.rule_id in NHOM_A_CANONICAL_RULE_IDS and f.status == "KÍCH HOẠT"]
    data_warnings = [f for f in risk_flags if f.status == "CHƯA ĐÁNH GIÁ"]
    signal_count = len(signals)

    equity_non_positive = equity_vnd is not None and equity_vnd <= 0
    too_many_signals = signal_count >= _MAX_SIGNALS_BEFORE_BLOCK
    both_weak = (
        dscr.status == "OK" and dscr.value < _DSCR_HARD_THRESHOLD
        and icr.status == "OK" and icr.value < _ICR_HARD_THRESHOLD
    )

    if equity_non_positive or too_many_signals or both_weak:
        reasons = []
        if equity_non_positive:
            reasons.append(f"Vốn chủ sở hữu = {_format_vnd_vn(equity_vnd)} (≤ 0).")
        if too_many_signals:
            reasons.append(f"Có {signal_count} tín hiệu tín dụng cần thẩm định thêm (≥ 3).")
        if both_weak:
            reasons.append(f"DSCR {dscr.value:.2f}x < 1,0x đồng thời ICR {icr.value:.2f}x < 1,5x.")
        return ExportGateResult(
            verdict="KHONG_XUAT_TU_DONG", block_type="SOFT", signal_count=signal_count,
            signals=signals, data_warnings=data_warnings, reasons=reasons,
        )

    if signal_count > 0 or data_warnings:
        return ExportGateResult(
            verdict="XUAT_KEM_CANH_BAO", block_type=None, signal_count=signal_count,
            signals=signals, data_warnings=data_warnings,
        )

    return ExportGateResult(verdict="XUAT", block_type=None, signal_count=0)
