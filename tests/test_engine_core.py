from app.engine.core.types import Metric, RuleResult


def test_metric_holds_computed_value_with_provenance():
    m = Metric(
        metric="DTI",
        value=0.2262,
        formula="(tong nghia vu tra no + nghia vu de xuat) / thu nhap ghi nhan",
        input_values={"debt": 52812500, "income": 233520000},
        input_sources={"debt": "credit_engine", "income": "income_assessment"},
    )
    assert m.status == "OK"
    assert m.value == 0.2262


def test_metric_need_more_data_has_null_value_and_status():
    m = Metric.need_more_data("DSCR", formula="CFADS / (goc + lai den han)")
    assert m.value is None
    assert m.status == "NEED_MORE_DATA"
    assert m.formula == "CFADS / (goc + lai den han)"


def test_rule_result_defaults():
    r = RuleResult(rule_id="RF01", rule_name="Mat can doi von", status="KHONG_KICH_HOAT")
    assert r.evidence == []
    assert r.severity is None
    assert r.comment == ""
