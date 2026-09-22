from app.storage.db import init_db
from app.agents.eb.stress_scenarios import list_scenarios, save_scenario


def test_save_and_list_scenario(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    scenario_id = save_scenario(
        db_path, case_id="EB-123", name="Thận trọng", created_by="RM Nam",
        report_period="2025", request={"preset": "than_trong"}, response={"after": {}},
    )
    assert scenario_id > 0
    scenarios = list_scenarios(db_path, "EB-123")
    assert len(scenarios) == 1
    assert scenarios[0]["name"] == "Thận trọng"
    assert scenarios[0]["created_by"] == "RM Nam"
    assert scenarios[0]["request"] == {"preset": "than_trong"}


def test_list_scenarios_newest_first(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    save_scenario(db_path, "EB-123", "A", "RM", "2025", {}, {})
    save_scenario(db_path, "EB-123", "B", "RM", "2025", {}, {})
    scenarios = list_scenarios(db_path, "EB-123")
    assert [s["name"] for s in scenarios] == ["B", "A"]


def test_list_scenarios_scoped_to_case_id(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    save_scenario(db_path, "EB-123", "A", "RM", "2025", {}, {})
    save_scenario(db_path, "EB-456", "B", "RM", "2025", {}, {})
    assert len(list_scenarios(db_path, "EB-123")) == 1
