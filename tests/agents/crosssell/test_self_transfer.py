from app.agents.crosssell.self_transfer import build_self_transfer_pattern, is_self_transfer


def test_builds_pattern_dynamically_not_hardcoded():
    pattern = build_self_transfer_pattern("CONG TY TNHH PHUC ANH")
    assert pattern is not None
    assert is_self_transfer("Chuyen tien tu TK PHUC ANH sang TK khac", pattern)


def test_different_customer_gets_different_pattern():
    # The bug being fixed: a hardcoded "PHUC ANH" regex would wrongly match
    # this completely unrelated customer's self-transfer text too.
    pattern = build_self_transfer_pattern("CONG TY CO PHAN XYZ HOLDING")
    assert pattern is not None
    assert not is_self_transfer("Chuyen tien noi bo PHUC ANH", pattern)


def test_lien_danh_partner_is_never_flagged_as_self():
    # Real case: "LIÊN DANH NHÀ THẦU PHÚC ANH – PHƯƠNG ĐÔNG" is a genuine
    # ~6.4B VND partner, not the customer transferring money to themself.
    pattern = build_self_transfer_pattern("CONG TY TNHH PHUC ANH")
    assert not is_self_transfer("LIEN DANH NHA THAU PHUC ANH - PHUONG DONG", pattern)


def test_self_account_number_takes_priority_over_regex():
    pattern = build_self_transfer_pattern("CONG TY ABC")
    assert is_self_transfer("Chuyen khoan toi TK 0011002233", pattern, self_accounts=["0011002233"])


def test_no_usable_core_words_returns_none_pattern():
    pattern = build_self_transfer_pattern("CONG TY TNHH")  # only stopwords
    assert pattern is None
    assert not is_self_transfer("bat ky noi dung nao", pattern)
