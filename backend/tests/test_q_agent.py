from pathlib import Path

from app.q_agent import ALL_ACTIONS, INITIAL_Q, QLearningAgent


def test_q_agent_warns_when_persisted_table_is_corrupt(
    tmp_path: Path, caplog
):
    q_table_path = tmp_path / "q_table.json"
    q_table_path.write_text("{ not valid json", encoding="utf-8")

    with caplog.at_level("WARNING"):
        agent = QLearningAgent(q_table_path=q_table_path, load_existing=True)

    assert "Could not load Q-table" in caplog.text
    assert agent.get_q_values("new_state") == [INITIAL_Q] * len(ALL_ACTIONS)
