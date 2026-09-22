import pytest

from app.agents.crosssell.card_types import (
    confidence_with_cap,
    format_deal_size_exact,
    format_deal_size_headline,
    priority_from_deal_size,
)


@pytest.mark.parametrize(
    "amount,expected",
    [
        (169_910_860_881, "169,9 tỷ"),
        (78_810_636_239, "78,8 tỷ"),
        (9_010_589_375, "9,01 tỷ"),
        (8_548_116_444, "8,55 tỷ"),
        (3_950_214_073, "3,95 tỷ"),
        (824_418_933, "824 triệu"),
        (1_200_000_000_000, "1,2 nghìn tỷ"),
        (None, "Chưa xác định"),
    ],
)
def test_format_deal_size_headline_matches_spec_examples(amount, expected):
    assert format_deal_size_headline(amount) == expected


def test_format_deal_size_exact_uses_dot_thousands_separator():
    assert format_deal_size_exact(169_910_860_881) == "169.910.860.881"
    assert format_deal_size_exact(None) is None


def test_priority_thresholds():
    assert priority_from_deal_size(20_000_000_000) == "P1"
    assert priority_from_deal_size(19_999_999_999) == "P2"
    assert priority_from_deal_size(5_000_000_000) == "P2"
    assert priority_from_deal_size(4_999_999_999) == "P3"
    assert priority_from_deal_size(0) == "P3"
    assert priority_from_deal_size(None) == "P-NA"


def test_confidence_cap_never_raises_only_lowers():
    assert confidence_with_cap("H", "M") == "M"
    assert confidence_with_cap("M", "H") == "M"  # cap can't raise a lower base
    assert confidence_with_cap("H", "H") == "H"
    assert confidence_with_cap("L", "H") == "L"
