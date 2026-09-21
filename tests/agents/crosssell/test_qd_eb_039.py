import pytest

from app.agents.crosssell.qd_eb_039 import compute_qd_eb_039_deal_size


@pytest.mark.parametrize(
    "method,expected_rate",
    [
        ("perfect_bct_lc", 0.98),
        ("lc_or_bltt", 0.90),
        ("export_bct", 0.90),
        ("contract_or_award_notice", 0.80),
        ("domestic_receivable", 0.80),
    ],
)
def test_rate_table(method, expected_rate):
    assert compute_qd_eb_039_deal_size(method, 1_000_000_000) == round(1_000_000_000 * expected_rate)


def test_unknown_method_raises():
    with pytest.raises(ValueError):
        compute_qd_eb_039_deal_size("khong_ton_tai", 1_000_000_000)
