from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import (
    ActionName,
    CandidateActionTrace,
    DecisionInputSummary,
    DecisionOutputSummary,
    DecisionSystemStatus,
    GovernmentRecommendation,
    OptimizerInspection,
    Params,
    PolicyNodeTrace,
    TickSnapshot,
    WorldState,
)
from .simulation import (
    BUILD_FUNCTIONS,
    BUILDING_COSTS,
    build_farm,
    build_factory,
    build_housing,
    build_market,
    build_power_plant,
    build_road,
    government_recommendation,
    subsidize,
    subsidy_cost,
    update_demand,
    update_happiness,
    update_price,
    update_supply,
)

from .q_agent import encode_state, QLearningAgent, reward_components

POLICY_VERSION_QL = "q-learning-city-v1"


POLICY_VERSION = "city-evolution-optimizer-v1"
OPTIMIZER_OVERRIDE_THRESHOLD = 0.055
ALL_ACTIONS: tuple[ActionName, ...] = (
    "build_farm",
    "build_factory",
    "build_market",
    "build_power_plant",
    "build_housing",
    "build_road",
    "subsidize",
    "do_nothing",
)

ACTION_TO_BUILDING: dict[ActionName, str] = {
    "build_farm": "farm",
    "build_factory": "factory",
    "build_market": "market",
    "build_power_plant": "power_plant",
    "build_housing": "housing",
    "build_road": "road",
}

ACTION_APPLIERS = {
    "build_farm": build_farm,
    "build_factory": build_factory,
    "build_market": build_market,
    "build_power_plant": build_power_plant,
    "build_housing": build_housing,
    "build_road": build_road,
    "subsidize": subsidize,
}


@dataclass(frozen=True)
class PolicyEvaluation:
    action: ActionName
    policy_score: float
    optimizer_score: float
    projected_state: WorldState
    reward_signals: dict[str, float]
    risk_flags: list[str]
    prior: float


class CityTrainingEnv:
    """Small offline environment for evolving/testing the decision policy."""

    def __init__(self, seed: int = 42, params: Params | None = None) -> None:
        self.seed = seed
        self.params = params or Params()
        self.rng = random.Random(seed)
        self.state = self.reset()

    def reset(self) -> WorldState:
        self.state = WorldState(
            population=self.rng.randint(80, 180),
            farms=self.rng.randint(4, 14),
            factories=self.rng.randint(1, 7),
            housing=self.rng.randint(4, 12),
            markets=self.rng.randint(1, 5),
            parks=self.rng.randint(0, 5),
            power_plants=self.rng.randint(1, 3),
            roads=self.rng.randint(3, 10),
            land_used=self.rng.randint(45, 88),
            price=self.rng.uniform(8, 24),
            happiness=self.rng.uniform(0.45, 0.9),
        )
        self.state = update_demand(update_supply(self.state, self.params))
        return self.state

    def step(self, action: ActionName) -> tuple[WorldState, float, bool]:
        before = reward_total(reward_signals(self.state, self.params))
        self.state = project_action(self.state, action, self.params)
        self.state = update_happiness(update_price(update_supply(update_demand(self.state), self.params), self.params))
        after_signals = reward_signals(self.state, self.params)
        reward = reward_total(after_signals) - before
        done = self.state.land_used >= self.state.land_total or self.state.happiness <= 0.05
        return self.state, reward, done


def recommend_with_policy(
    state: WorldState,
    history: list[TickSnapshot],
    params: Params,
    q_agent: QLearningAgent | None = None,
) -> tuple[GovernmentRecommendation, DecisionSystemStatus]:
    legal = legal_actions(state, params)
    if not legal:
        fallback = government_recommendation(state, params)
        return fallback, DecisionSystemStatus(
            source="rule_fallback",
            policyVersion=POLICY_VERSION,
            confidence=0,
            legalActions=[],
            riskFlags=["no_legal_actions"],
            optimizer=OptimizerInspection(
                verdict="unavailable",
                reason="No legal action was available, so the rule fallback was used.",
                riskFlags=["no_legal_actions"],
                finalAction=fallback.action,
            ),
            input_summary=decision_input_summary(state, history),
            nodes=policy_node_trace(state, history, params),
            output_summary=DecisionOutputSummary(
                action=fallback.action,
                confidence=0,
                reason=fallback.reason,
            ),
        )

    if q_agent is not None:
        return _recommend_with_q_agent(state, history, legal, params, q_agent)

    evaluations = [
        evaluate_action(state, action, history, params)
        for action in legal
    ]
    policy_ranked = sorted(evaluations, key=lambda item: item.policy_score, reverse=True)
    optimizer_ranked = sorted(evaluations, key=lambda item: item.optimizer_score, reverse=True)
    policy_choice = policy_ranked[0]
    optimizer_choice = optimizer_ranked[0]
    fitness_delta = optimizer_choice.optimizer_score - policy_choice.optimizer_score
    override_applied = (
        optimizer_choice.action != policy_choice.action
        and fitness_delta >= OPTIMIZER_OVERRIDE_THRESHOLD
    )
    best = optimizer_choice if override_applied else policy_choice

    second_score = next(
        (
            item.optimizer_score
            for item in optimizer_ranked
            if item.action != best.action
        ),
        best.optimizer_score - 1,
    )
    margin = best.optimizer_score - second_score
    confidence = clamp(0.55 + margin * 0.25 + max(fitness_delta, 0) * 0.20, 0.05, 0.97)
    risks = list(best.risk_flags)
    if override_applied:
        risks.append("optimizer_override")
    optimizer = optimizer_inspection(policy_choice, optimizer_choice, best, fitness_delta, override_applied)

    return (
        recommendation_for(
            best.action,
            state,
            best.projected_state,
            best.reward_signals,
            risks,
            optimizer,
        ),
        DecisionSystemStatus(
            source="evolution_optimizer",
            policyVersion=POLICY_VERSION,
            confidence=round(confidence, 3),
            valueEstimate=round(best.optimizer_score, 4),
            legalActions=legal,
            riskFlags=risks,
            rewardSignals={key: round(value, 4) for key, value in best.reward_signals.items()},
            optimizer=optimizer,
            input_summary=decision_input_summary(state, history),
            nodes=policy_node_trace(state, history, params),
            candidates=candidate_trace(optimizer_ranked, best.action, state),
            output_summary=DecisionOutputSummary(
                action=best.action,
                confidence=round(confidence, 3),
                valueEstimate=round(best.optimizer_score, 4),
                expectedHappinessDelta=round(best.projected_state.happiness - state.happiness, 4),
                expectedFoodSupplyDelta=round(best.projected_state.food_supply - state.food_supply, 2),
                expectedPriceDelta=round(best.projected_state.price - state.price, 2),
                reason=optimizer.reason,
            ),
        ),
    )


def _recommend_with_q_agent(
    state: WorldState,
    history: list[TickSnapshot],
    legal: list[ActionName],
    params: Params,
    agent: QLearningAgent,
) -> tuple[GovernmentRecommendation, DecisionSystemStatus]:
    state_key = encode_state(state, params)
    chosen_action = agent.choose_action(state_key, legal)
    q_values = agent.get_q_values(state_key)

    ranked = sorted(
        [(a, q_values[agent.action_index(a)]) for a in legal],
        key=lambda x: x[1],
        reverse=True,
    )

    best_action, best_q = ranked[0]
    second_best_q = ranked[1][1] if len(ranked) > 1 else best_q - 1
    margin = best_q - second_best_q
    confidence = clamp(0.55 + margin * 0.25 + max(margin, 0) * 0.20, 0.05, 0.97)

    projected = project_action(state, best_action, params)
    projected = update_happiness(update_price(update_supply(update_demand(projected), params), params))
    signals = reward_components(projected, params)

    risks = []
    reason = (
        f"Q-learning agent selected {best_action.replace('_', ' ')} "
        f"(Q={best_q:.3f}, margin={margin:.3f}, "
        f"exploration={agent.epsilon:.2f})."
    )
    if agent.epsilon > 0.3:
        risks.append("exploring")
    if projected.population < 30:
        risks.append("population_collapse_risk")
    infra = (state.roads + state.power_plants * 2) / max(state.factories + state.housing + state.markets, 1)
    if state.treasury > 500_000 and infra < 1.0:
        risks.append("idle_treasury")

    optimizer = OptimizerInspection(
        verdict="right" if confidence >= 0.7 else "watch",
        reason=reason,
        riskFlags=risks,
        suggestedAction=best_action,
        overrideApplied=False,
        originalAction=best_action,
        finalAction=best_action,
        fitnessDelta=round(margin, 4),
    )

    candidates: list[CandidateActionTrace] = []
    for i, (action, q_val) in enumerate(ranked):
        proj = project_action(state, action, params)
        proj = update_happiness(update_price(update_supply(update_demand(proj), params), params))
        candidates.append(
            CandidateActionTrace(
                action=action,
                rank=i + 1,
                selected=action == best_action,
                policyScore=round(q_val, 4),
                optimizerScore=round(q_val, 4),
                expectedHappinessDelta=round(proj.happiness - state.happiness, 4),
                expectedFoodSupplyDelta=round(proj.food_supply - state.food_supply, 2),
                expectedPriceDelta=round(proj.price - state.price, 2),
                rewardSignals={k: round(v, 4) for k, v in reward_components(proj, params).items()},
                riskFlags=risks if action == best_action else [],
            )
        )

    rec = recommendation_for(best_action, state, projected, signals, risks, optimizer)

    return rec, DecisionSystemStatus(
        source="evolution_optimizer",
        policyVersion=POLICY_VERSION_QL,
        confidence=round(confidence, 3),
        valueEstimate=round(best_q, 4),
        legalActions=legal,
        riskFlags=risks,
        rewardSignals={k: round(v, 4) for k, v in signals.items()},
        optimizer=optimizer,
        input_summary=decision_input_summary(state, history),
        nodes=policy_node_trace(state, history, params),
        candidates=candidates,
        output_summary=DecisionOutputSummary(
            action=best_action,
            confidence=round(confidence, 3),
            valueEstimate=round(best_q, 4),
            expectedHappinessDelta=round(projected.happiness - state.happiness, 4),
            expectedFoodSupplyDelta=round(projected.food_supply - state.food_supply, 2),
            expectedPriceDelta=round(projected.price - state.price, 2),
            reason=optimizer.reason,
        ),
    )


def legal_actions(state: WorldState, params: Params) -> list[ActionName]:
    legal: list[ActionName] = []
    for action in ALL_ACTIONS:
        if action in ACTION_TO_BUILDING:
            building_type = ACTION_TO_BUILDING[action]
            build_fn = BUILD_FUNCTIONS[building_type]  # type: ignore[index]
            cost = BUILDING_COSTS[building_type]  # type: ignore[index]
            if state.treasury >= cost and build_fn(state, params) != state:  # type: ignore[operator]
                legal.append(action)
        elif action == "subsidize":
            if state.price > params.min_price and state.treasury >= subsidy_cost(state, params):
                legal.append(action)
        else:
            legal.append(action)
    return legal


def evaluate_action(
    state: WorldState,
    action: ActionName,
    history: list[TickSnapshot],
    params: Params,
) -> PolicyEvaluation:
    projected = project_action(state, action, params)
    projected = update_demand(update_supply(projected, params))
    projected = update_price(projected, params)
    projected = update_happiness(projected)
    signals = reward_signals(projected, params)
    prior = action_prior(action, state, history, params)
    risks = policy_risk_flags(action, state, history, params)
    policy_score = reward_total(signals) + prior
    optimizer_score = optimizer_fitness(action, state, history, params, signals, risks)
    return PolicyEvaluation(
        action=action,
        policy_score=policy_score,
        optimizer_score=optimizer_score,
        projected_state=projected,
        reward_signals=signals,
        risk_flags=risks,
        prior=prior,
    )


def project_action(state: WorldState, action: ActionName, params: Params) -> WorldState:
    if action == "do_nothing":
        return state
    apply_action = ACTION_APPLIERS[action]
    projected = apply_action(state, params)
    if action in ACTION_TO_BUILDING and projected != state:
        building_type = ACTION_TO_BUILDING[action]
        cost = BUILDING_COSTS[building_type]  # type: ignore[index]
        projected = projected.model_copy(
            update={"treasury": max(0.0, projected.treasury - cost)}
        )
    return update_supply(projected, params)


def reward_signals(state: WorldState, params: Params) -> dict[str, float]:
    demand = max(state.food_demand, 1)
    food_balance = clamp(1 - abs(1 - state.food_supply / demand), 0, 1)
    affordability = clamp(1 - ((state.price - params.base_price) / max(params.max_price - params.base_price, 1)), 0, 1)
    happiness = clamp(state.happiness, 0, 1)
    land_buffer = clamp((state.land_total - state.land_used) / max(state.land_total * 0.20, 1), 0, 1)
    infrastructure = clamp((state.roads + state.power_plants * 2) / max(state.factories + state.housing + state.markets, 1), 0, 1)
    oversupply_penalty = clamp((state.food_supply - state.food_demand * 1.35) / demand, 0, 1)
    scarcity_penalty = clamp((state.food_demand - state.food_supply) / demand, 0, 1)

    return {
        "foodBalance": food_balance,
        "affordability": affordability,
        "happiness": happiness,
        "landBuffer": land_buffer,
        "infrastructure": infrastructure,
        "oversupplyPenalty": oversupply_penalty,
        "scarcityPenalty": scarcity_penalty,
    }


def reward_total(signals: dict[str, float]) -> float:
    return (
        signals["foodBalance"] * 0.30
        + signals["affordability"] * 0.22
        + signals["happiness"] * 0.22
        + signals["landBuffer"] * 0.12
        + signals["infrastructure"] * 0.08
        - signals["oversupplyPenalty"] * 0.14
        - signals["scarcityPenalty"] * 0.18
    )


def optimizer_fitness(
    action: ActionName,
    state: WorldState,
    history: list[TickSnapshot],
    params: Params,
    signals: dict[str, float],
    risks: list[str],
) -> float:
    shortage = max(0.0, state.food_demand - state.food_supply)
    land_free = state.land_total - state.land_used
    recent_actions = [snapshot.recommendation.action for snapshot in history[-6:]]
    score = reward_total(signals)

    if action == "build_farm":
        score += clamp(shortage / max(params.farm_output * 6, 1), 0, 0.24)
    elif action == "subsidize":
        score += 0.10 if state.price > 18 else 0.0
        if shortage > params.farm_output * 2:
            score -= 0.14
        score -= 0.05 * recent_actions.count("subsidize")
    elif action == "build_road":
        score += 0.08 if state.roads < max(5, state.factories + state.markets) else 0.0
    elif action == "build_power_plant":
        score += 0.07 if state.factories > state.power_plants * 4 else 0.0
    elif action == "build_housing":
        score += 0.06 if state.housing * 18 < state.population else 0.0
    elif action == "build_market":
        score += 0.06 if state.markets * 70 < state.population else 0.0
    elif action == "build_factory":
        score += 0.04 if state.food_supply >= state.food_demand and state.happiness >= 0.65 else -0.04
    elif action == "do_nothing":
        score += 0.08 if shortage <= 0 and state.price <= 15 and state.happiness >= 0.65 else -0.18

    if action in ACTION_TO_BUILDING and land_free <= 12:
        score -= 0.12
    score -= 0.055 * len(risks)
    return score


def action_prior(
    action: ActionName,
    state: WorldState,
    history: list[TickSnapshot],
    params: Params,
) -> float:
    shortage = state.food_demand - state.food_supply
    land_free = state.land_total - state.land_used
    recent_actions = [snapshot.recommendation.action for snapshot in history[-6:]]

    prior = 0.0
    if action == "build_farm":
        prior += clamp(shortage / max(params.farm_output * 4, 1), -0.15, 0.35)
    elif action == "subsidize":
        prior += 0.24 if state.price > 18 else -0.08
        prior -= 0.08 * recent_actions.count("subsidize")
    elif action == "build_housing":
        prior += 0.06 if state.housing * 18 < state.population else -0.05
    elif action == "build_road":
        prior += 0.08 if state.roads < max(5, state.factories + state.markets) else -0.03
    elif action == "build_power_plant":
        prior += 0.08 if state.factories > state.power_plants * 4 else -0.04
    elif action == "build_market":
        prior += 0.07 if state.markets * 70 < state.population else -0.03
    elif action == "build_factory":
        prior += 0.04 if state.food_supply >= state.food_demand and state.happiness >= 0.65 else -0.08
    elif action == "do_nothing":
        prior += 0.11 if abs(shortage) <= params.farm_output and state.price <= 15 and state.happiness >= 0.65 else -0.12

    if action in ACTION_TO_BUILDING:
        building_type = ACTION_TO_BUILDING[action]
        land_cost = 1 if building_type == "road" else 3 if building_type in {"factory", "power_plant"} else params.build_cost_land
        prior -= land_cost * 0.018
        if land_free <= 12:
            prior -= 0.10

    return prior


def policy_risk_flags(
    action: ActionName,
    state: WorldState,
    history: list[TickSnapshot],
    params: Params,
) -> list[str]:
    risks: list[str] = []
    recent_actions = [snapshot.recommendation.action for snapshot in history[-6:]]
    if action == "subsidize" and recent_actions.count("subsidize") >= 2:
        risks.append("subsidy_spam_risk")
    if action in ACTION_TO_BUILDING and state.land_total - state.land_used <= 12:
        risks.append("land_pressure")
    if action == "build_farm" and state.food_supply > state.food_demand * 1.25:
        risks.append("oversupply_risk")
    if action == "do_nothing" and (
        state.food_supply < state.food_demand or state.price > 16 or state.happiness < 0.6
    ):
        risks.append("stagnation_risk")
    if action in {"build_factory", "build_market", "build_housing"} and state.roads < 4:
        risks.append("connectivity_risk")
    if "do_nothing" not in legal_actions(state, params):
        risks.append("invalid_action_masking_failed")
    return risks


def recommendation_for(
    action: ActionName,
    state: WorldState,
    projected: WorldState,
    signals: dict[str, float],
    risks: list[str],
    optimizer: OptimizerInspection,
) -> GovernmentRecommendation:
    if action == "do_nothing":
        reason = "The local optimizer expects the city to remain stable without a new intervention this tick."
    elif action == "subsidize":
        reason = "The local optimizer is reducing short-term price pressure while watching for subsidy spam."
    else:
        label = ACTION_TO_BUILDING[action].replace("_", " ")
        reason = f"The local optimizer selected {label} because it improves the projected city reward."

    if optimizer.override_applied and optimizer.original_action:
        original = optimizer.original_action.replace("_", " ")
        reason += f" It overrode {original} after validation found a stronger fitness path."

    if risks:
        reason += f" Watch flags: {', '.join(risks)}."

    return GovernmentRecommendation(
        action=action,
        reason=reason,
        estimated_happiness_delta=round(projected.happiness - state.happiness, 4),
        estimated_food_supply_delta=round(projected.food_supply - state.food_supply, 2),
        estimated_price_delta=round(projected.price - state.price, 2),
    )


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def optimizer_inspection(
    policy_choice: PolicyEvaluation,
    optimizer_choice: PolicyEvaluation,
    selected: PolicyEvaluation,
    fitness_delta: float,
    override_applied: bool,
) -> OptimizerInspection:
    if override_applied:
        verdict = "wrong" if fitness_delta >= 0.12 else "watch"
        reason = (
            f"Policy chose {policy_choice.action.replace('_', ' ')}, but validation found "
            f"{optimizer_choice.action.replace('_', ' ')} improves fitness by {fitness_delta:.3f}."
        )
    elif selected.risk_flags:
        verdict = "watch"
        reason = (
            f"Policy action {selected.action.replace('_', ' ')} is usable, but the optimizer "
            f"is watching {', '.join(selected.risk_flags)}."
        )
    else:
        verdict = "right"
        reason = (
            f"Policy action {selected.action.replace('_', ' ')} passed local validation "
            "against the candidate action set."
        )

    return OptimizerInspection(
        verdict=verdict,
        reason=reason,
        riskFlags=selected.risk_flags,
        suggestedAction=selected.action,
        overrideApplied=override_applied,
        originalAction=policy_choice.action,
        finalAction=selected.action,
        fitnessDelta=round(fitness_delta, 4),
    )


def decision_input_summary(state: WorldState, history: list[TickSnapshot]) -> DecisionInputSummary:
    return DecisionInputSummary(
        tick=state.tick,
        population=state.population,
        foodSupply=round(state.food_supply, 2),
        foodDemand=round(state.food_demand, 2),
        price=round(state.price, 2),
        happiness=round(state.happiness, 4),
        treasury=round(state.treasury, 2),
        landUsed=state.land_used,
        landTotal=state.land_total,
        roads=state.roads,
        powerPlants=state.power_plants,
        recentActions=[snapshot.recommendation.action for snapshot in history[-6:]],
    )


def policy_node_trace(
    state: WorldState,
    history: list[TickSnapshot],
    params: Params,
) -> list[PolicyNodeTrace]:
    current = reward_signals(state, params)
    previous_state = getattr(history[-1], "state", None) if history else None
    previous = reward_signals(previous_state, params) if previous_state else {}
    labels = {
        "foodBalance": "Food Balance",
        "affordability": "Affordability",
        "happiness": "Happiness",
        "landBuffer": "Land Buffer",
        "infrastructure": "Infrastructure",
        "oversupplyPenalty": "Oversupply",
        "scarcityPenalty": "Scarcity",
    }
    notes = {
        "foodBalance": "Supply and demand alignment.",
        "affordability": "Price pressure against the base price.",
        "happiness": "Citizen satisfaction signal.",
        "landBuffer": "Available land for future moves.",
        "infrastructure": "Road and power support for the city.",
        "oversupplyPenalty": "Penalty when farms overproduce too much food.",
        "scarcityPenalty": "Penalty when demand is above food supply.",
    }

    nodes: list[PolicyNodeTrace] = []
    for key, value in current.items():
        previous_value = previous.get(key)
        delta = 0.0 if previous_value is None else value - previous_value
        nodes.append(
            PolicyNodeTrace(
                key=key,
                label=labels[key],
                previousValue=None if previous_value is None else round(previous_value, 4),
                currentValue=round(value, 4),
                delta=round(delta, 4),
                status=node_status(key, value, delta),
                note=notes[key],
            )
        )
    return nodes


def node_status(key: str, value: float, delta: float) -> str:
    is_penalty = key.endswith("Penalty")
    if is_penalty:
        if value >= 0.18 or delta > 0.05:
            return "negative"
        if value >= 0.08:
            return "warning"
        return "positive"

    if value >= 0.72 or delta > 0.05:
        return "positive"
    if value <= 0.38 or delta < -0.05:
        return "negative"
    if value <= 0.55:
        return "warning"
    return "neutral"


def candidate_trace(
    ranked: list[PolicyEvaluation],
    selected_action: ActionName,
    state: WorldState,
) -> list[CandidateActionTrace]:
    traces: list[CandidateActionTrace] = []
    for index, evaluation in enumerate(ranked, start=1):
        traces.append(
            CandidateActionTrace(
                action=evaluation.action,
                rank=index,
                selected=evaluation.action == selected_action,
                policyScore=round(evaluation.policy_score, 4),
                optimizerScore=round(evaluation.optimizer_score, 4),
                expectedHappinessDelta=round(evaluation.projected_state.happiness - state.happiness, 4),
                expectedFoodSupplyDelta=round(evaluation.projected_state.food_supply - state.food_supply, 2),
                expectedPriceDelta=round(evaluation.projected_state.price - state.price, 2),
                rewardSignals={
                    key: round(value, 4)
                    for key, value in evaluation.reward_signals.items()
                },
                riskFlags=evaluation.risk_flags,
                note="Final output" if evaluation.action == selected_action else "Validated candidate",
            )
        )
    return traces


def confidence_label(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.6:
        return "medium"
    return "low"


def sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-value))
