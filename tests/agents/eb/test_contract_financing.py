from app.agents.eb.contract_financing import compute_output_contract_financing_ratio


def test_computes_ratio_as_percentage():
    m = compute_output_contract_financing_ratio(800_000_000, 1_000_000_000)
    assert m.value == 80.0
    assert m.status == "OK"


def test_missing_either_input_is_need_more_data():
    assert compute_output_contract_financing_ratio(None, 1_000_000_000).status == "NEED_MORE_DATA"
    assert compute_output_contract_financing_ratio(800_000_000, None).status == "NEED_MORE_DATA"
    assert compute_output_contract_financing_ratio(800_000_000, 0).status == "NEED_MORE_DATA"


def test_no_policy_label_without_a_recognised_method():
    m = compute_output_contract_financing_ratio(800_000_000, 1_000_000_000)
    assert m.policy_version is None


def test_qd_eb_039_label_attached_for_recognised_method():
    m = compute_output_contract_financing_ratio(800_000_000, 1_000_000_000, method="lc_or_bltt")
    assert "QĐ.EB.039" in m.policy_version


def test_unrecognised_method_does_not_attach_label():
    m = compute_output_contract_financing_ratio(800_000_000, 1_000_000_000, method="khong_hop_le")
    assert m.policy_version is None
