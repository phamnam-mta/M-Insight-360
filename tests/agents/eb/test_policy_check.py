from app.agents.eb.policy_check import run_policy_check


def test_policy_check_reports_need_more_data_not_pass():
    results = run_policy_check()
    assert len(results) == 1
    assert results[0].status == "NEED_MORE_DATA"
    assert "chính sách" in results[0].comment.lower()
