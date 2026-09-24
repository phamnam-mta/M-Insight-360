"""Shared VN-locale number parser (app/engine/core/numbers.py).

Extracted from Cross-sell's statement parser so RB and EB parse the same
"500.000.000" the same way instead of each crashing or silently truncating.
"""

from app.engine.core.numbers import parse_vn_number


def test_vn_thousands_separator_dot():
    assert parse_vn_number("500.000.000") == 500_000_000


def test_vn_thousands_dot_with_decimal_comma():
    assert parse_vn_number("1.234.567,89") == 1_234_567.89


def test_us_thousands_comma_with_decimal_dot():
    assert parse_vn_number("1,234,567.89") == 1_234_567.89


def test_vn_decimal_comma():
    assert parse_vn_number("1234,56") == 1234.56


def test_us_thousands_only_commas():
    assert parse_vn_number("450,000,000") == 450_000_000


def test_plain_decimal_point_is_not_thousands():
    assert parse_vn_number("22.5") == 22.5


def test_negative_vn_number():
    assert parse_vn_number("-1.188.000.000") == -1_188_000_000


def test_empty_and_unparseable_return_zero():
    assert parse_vn_number("") == 0.0
    assert parse_vn_number("   ") == 0.0
    assert parse_vn_number("n/a") == 0.0


def test_parenthesized_negative_accounting_notation():
    # Standard Vietnamese/international accounting convention: a negative
    # figure is written in parentheses instead of with a minus sign — very
    # common on real BCTC exports (e.g. "Giá trị hao mòn luỹ kế (*)"
    # showing "(2.071.730.891)"). Previously silently parsed as 0.0.
    assert parse_vn_number("(20)") == -20.0
    assert parse_vn_number("(1.234.567)") == -1_234_567.0
    assert parse_vn_number("(1,234,567.89)") == -1_234_567.89


def test_parenthesized_with_surrounding_whitespace():
    assert parse_vn_number(" (500.000) ") == -500_000.0
