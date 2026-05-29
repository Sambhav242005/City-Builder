from app.models import Params, WorldState
from app.rl_policy import (
    legal_actions,
    masked_legal_actions,
    policy_risk_flags,
    recommend_with_policy,
    reward_signals,
    reward_total,
)


def test_policy_exposes_action_mask_and_diagnostics():
    state = WorldState(land_used=99, land_total=100, price=22, food_supply=70, food_demand=120)
    recommendation, decision = recommend_with_policy(state, [], Params())

    assert recommendation.action in decision.legal_actions
    assert "build_farm" not in decision.legal_actions
    assert decision.confidence > 0
    assert decision.reward_signals
    assert decision.optimizer.verdict in {"right", "watch", "wrong"}
    assert decision.input_summary.food_supply == state.food_supply
    assert decision.nodes
    assert decision.candidates
    assert decision.output_summary.action == recommendation.action


def test_policy_flags_subsidy_spam_loophole():
    state = WorldState(price=24, food_supply=100, food_demand=100)
    history = []
    for _ in range(3):
        recommendation, _decision = recommend_with_policy(state, history, Params())
        recommendation = recommendation.model_copy(update={"action": "subsidize"})
        history.append(type("Snapshot", (), {"recommendation": recommendation})())

    assert "subsidy_spam_risk" in policy_risk_flags("subsidize", state, history, Params())


def test_reward_penalizes_oversupply_and_scarcity():
    balanced = reward_signals(WorldState(food_supply=100, food_demand=100), Params())
    oversupplied = reward_signals(WorldState(food_supply=250, food_demand=100), Params())
    scarce = reward_signals(WorldState(food_supply=40, food_demand=100), Params())

    assert balanced["foodBalance"] > oversupplied["foodBalance"]
    assert balanced["foodBalance"] > scarce["foodBalance"]
    assert oversupplied["oversupplyPenalty"] > 0
    assert scarce["scarcityPenalty"] > 0


def test_reward_applies_integral_happiness_floor_penalty():
    stable = reward_signals(WorldState(happiness=0.72), Params())
    collapsing = reward_signals(WorldState(happiness=0.64), Params())

    assert stable["happinessFloorPenalty"] == 0
    assert collapsing["happinessFloorPenalty"] > 0
    assert reward_total(collapsing) < reward_total(stable)


def test_context_mask_locks_market_action_and_alternates_categories():
    params = Params()
    state = WorldState(price=24, treasury=900_000)

    after_subsidy = masked_legal_actions(state, params, ["subsidize"])
    assert "subsidize" not in after_subsidy
    assert any(action.startswith("build_") for action in after_subsidy)
    assert "do_nothing" in after_subsidy

    after_build = masked_legal_actions(state, params, ["build_farm"])
    assert "subsidize" in after_build
    assert all(not action.startswith("build_") for action in after_build)


def test_do_nothing_clears_infrastructure_cooldown():
    params = Params()
    state = WorldState(price=12, treasury=900_000)

    after_wait = masked_legal_actions(state, params, ["build_farm", "do_nothing"])

    assert any(action.startswith("build_") for action in after_wait)


def test_optimizer_trace_replaces_external_inspection():
    _recommendation, decision = recommend_with_policy(WorldState(), [], Params())

    assert decision.optimizer.final_action == decision.output_summary.action
    assert decision.optimizer.original_action in decision.legal_actions
    assert "foodBalance" in decision.reward_signals
    assert "do_nothing" in legal_actions(WorldState(), Params())


def test_optimizer_can_override_weak_policy_choice():
    state = WorldState(
        price=24,
        food_supply=45,
        food_demand=140,
        happiness=0.58,
        land_used=70,
        land_total=100,
        farms=4,
        roads=7,
    )

    recommendation, decision = recommend_with_policy(state, [], Params())

    assert decision.optimizer.verdict in {"watch", "wrong", "right"}
    assert decision.optimizer.final_action == recommendation.action
    assert decision.candidates[0].action == recommendation.action
    assert decision.output_summary.value_estimate == decision.candidates[0].optimizer_score
