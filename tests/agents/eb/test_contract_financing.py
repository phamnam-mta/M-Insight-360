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


def test_receivables_financing_limit_80_pct():
    from app.agents.eb.contract_financing import compute_receivables_financing_limit

    metric = compute_receivables_financing_limit(1_000_000_000, ltv=0.80)
    assert metric.value == 800_000_000
    assert metric.policy_version is None or "85" not in (metric.policy_version or "")


def test_receivables_financing_limit_85_pct_carries_priority_note():
    from app.agents.eb.contract_financing import compute_receivables_financing_limit

    metric = compute_receivables_financing_limit(1_000_000_000, ltv=0.85)
    assert metric.value == 850_000_000
    assert "VNR500/FDI" in metric.policy_version


def test_receivables_financing_limit_need_more_data_without_receivables():
    from app.agents.eb.contract_financing import compute_receivables_financing_limit

    metric = compute_receivables_financing_limit(None, ltv=0.80)
    assert metric.status == "NEED_MORE_DATA"


def test_receivables_financing_limit_rejects_invalid_ltv():
    import pytest

    from app.agents.eb.contract_financing import compute_receivables_financing_limit

    with pytest.raises(ValueError):
        compute_receivables_financing_limit(1_000_000_000, ltv=0.90)
