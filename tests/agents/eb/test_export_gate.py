from app.agents.eb.export_gate import evaluate_export_gate
from app.engine.core.types import Metric, RuleResult


def _flag(rule_id: str, status: str, **kw) -> RuleResult:
    return RuleResult(rule_id=rule_id, rule_name=rule_id, status=status, **kw)


def _metric(value, status="OK") -> Metric:
    return Metric(metric="m", value=value, formula="x", input_values={}, input_sources={}, status=status)


def test_xuat_when_no_signals_and_no_warnings():
    flags = [_flag("RF01", "KHÔNG KÍCH HOẠT"), _flag("RF02", "KHÔNG KÍCH HOẠT")]
    result = evaluate_export_gate(flags, equity_vnd=1000, dscr=_metric(1.5), icr=_metric(2.0))
    assert result.verdict == "XUAT"
    assert result.signal_count == 0


def test_xuat_kem_canh_bao_with_one_or_two_signals():
    flags = [_flag("RF06", "KÍCH HOẠT", observed_value=0.75)]
    result = evaluate_export_gate(flags, equity_vnd=1000, dscr=_metric(1.5), icr=_metric(2.0))
    assert result.verdict == "XUAT_KEM_CANH_BAO"
    assert result.signal_count == 1


def test_xuat_kem_canh_bao_when_only_data_warning_present_never_blocks():
    flags = [_flag("RF04", "CHƯA ĐÁNH GIÁ")]
    result = evaluate_export_gate(flags, equity_vnd=1000, dscr=Metric.need_more_data("dscr", "x"), icr=_metric(2.0))
    assert result.verdict == "XUAT_KEM_CANH_BAO"
    assert result.block_type is None


def test_khong_xuat_when_three_or_more_canonical_signals():
    flags = [
        _flag("RF05", "KÍCH HOẠT", observed_value=0.62),
        _flag("RF09", "KÍCH HOẠT", observed_value=0.75),
        _flag("RF01", "KÍCH HOẠT"),
        _flag("RF08", "KÍCH HOẠT", observed_value=3.0),
        _flag("RF06", "KÍCH HOẠT", observed_value=0.85),
    ]
    result = evaluate_export_gate(flags, equity_vnd=1000, dscr=_metric(0.62), icr=_metric(0.75))
    assert result.verdict == "KHONG_XUAT_TU_DONG"
    assert result.block_type == "SOFT"
    assert result.signal_count == 5


def test_khong_xuat_when_equity_non_positive():
    result = evaluate_export_gate([], equity_vnd=0, dscr=_metric(1.5), icr=_metric(2.0))
    assert result.verdict == "KHONG_XUAT_TU_DONG"
    assert result.block_type == "SOFT"


def test_equity_reason_uses_vietnamese_thousand_separators():
    # S1.2 locale rule: reasons strings are shown verbatim in the S7.3
    # screen and the force banner — a raw Python float like -1000000.0
    # must never leak past this boundary.
    result = evaluate_export_gate([], equity_vnd=-1_000_000.0, dscr=_metric(1.5), icr=_metric(2.0))
    assert any("1.000.000" in r for r in result.reasons)
    assert not any("1000000" in r for r in result.reasons)


def test_khong_xuat_when_dscr_and_icr_both_weak():
    flags = [_flag("RF05", "KÍCH HOẠT", observed_value=0.9), _flag("RF09", "KÍCH HOẠT", observed_value=1.2)]
    result = evaluate_export_gate(flags, equity_vnd=1000, dscr=_metric(0.9), icr=_metric(1.2))
    assert result.verdict == "KHONG_XUAT_TU_DONG"


def test_khong_xuat_hard_block_when_pre_check_blocked():
    result = evaluate_export_gate([], equity_vnd=1000, dscr=_metric(1.5), icr=_metric(2.0), pre_check_blocked=True)
    assert result.verdict == "KHONG_XUAT_TU_DONG"
    assert result.block_type == "HARD"


def test_non_canonical_flags_never_count_toward_signal_total():
    # RF02 (CFO âm) and RF03 (short-term debt ratio) are real credit
    # observations but not in the instruction's canonical Nhóm A list —
    # per spec D3, they must never inflate the S7 signal count.
    flags = [_flag("RF02", "KÍCH HOẠT"), _flag("RF03", "KÍCH HOẠT")]
    result = evaluate_export_gate(flags, equity_vnd=1000, dscr=_metric(1.5), icr=_metric(2.0))
    assert result.signal_count == 0
    assert result.verdict == "XUAT"


def test_insufficient_data_flags_never_count_as_signals():
    flags = [_flag("RF06", "CHƯA ĐÁNH GIÁ")]
    result = evaluate_export_gate(flags, equity_vnd=1000, dscr=_metric(1.5), icr=_metric(2.0))
    assert result.signal_count == 0
    assert result.verdict == "XUAT_KEM_CANH_BAO"  # the CHƯA ĐÁNH GIÁ flag is still a data warning
