import json
from pathlib import Path

from app.q_agent import ALL_ACTIONS, Q_TABLE_PATH
from app.training_harness import (
    TRAINING_REPORT_PATH,
    TrainingConfig,
    run_training_and_evaluation,
)


def test_offline_training_harness_validates_target_scenarios(tmp_path: Path):
    report = run_training_and_evaluation(
        TrainingConfig(
            episodes=5,
            steps_per_episode=5,
            scenario_rollouts=4,
            q_table_path=tmp_path / "q_table.json",
            report_path=tmp_path / "optimizer_training_report.json",
        ),
        write_artifacts=True,
    )

    scenarios = {scenario["name"]: scenario for scenario in report["scenarios"]}

    assert report["summary"]["allScenariosPassed"] is True
    assert (tmp_path / "q_table.json").exists()
    assert (tmp_path / "optimizer_training_report.json").exists()
    assert scenarios["shortage"]["selectedAction"] == "build_farm"
    assert scenarios["high_price"]["selectedAction"] == "subsidize"
    assert scenarios["oversupply"]["selectedAction"] != "build_farm"
    assert scenarios["low_land"]["selectedAction"] == "do_nothing"

    for scenario in scenarios.values():
        assert scenario["qMarginVsBaseline"] > 0
        assert scenario["validationMarginVsBaseline"] > 0


def test_checked_in_optimizer_training_report_documents_validation():
    with open(TRAINING_REPORT_PATH) as f:
        report = json.load(f)

    scenarios = {scenario["name"]: scenario for scenario in report["scenarios"]}

    assert report["training"]["environment"] == "CityTrainingEnv"
    assert report["summary"]["allScenariosPassed"] is True
    assert set(scenarios) == {"shortage", "oversupply", "high_price", "low_land"}
    assert scenarios["shortage"]["selectedAction"] == "build_farm"
    assert scenarios["high_price"]["selectedAction"] == "subsidize"
    assert scenarios["oversupply"]["selectedAction"] in {"do_nothing", "build_housing"}
    assert scenarios["low_land"]["selectedAction"] == "do_nothing"


def test_checked_in_policy_table_contains_reported_scenario_scores():
    with open(TRAINING_REPORT_PATH) as f:
        report = json.load(f)
    with open(Q_TABLE_PATH) as f:
        q_table = json.load(f)

    for scenario in report["scenarios"]:
        state_scores = q_table[scenario["stateKey"]]
        selected_index = ALL_ACTIONS.index(scenario["selectedAction"])
        baseline_index = ALL_ACTIONS.index(scenario["baselineAction"])

        assert state_scores[selected_index] > state_scores[baseline_index]
