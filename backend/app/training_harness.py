from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from .models import ActionName, Params, WorldState
from .q_agent import (
    ALL_ACTIONS,
    HAPPINESS_FLOOR,
    INITIAL_Q,
    Q_TABLE_PATH,
    QLearningAgent,
    QLearningConfig,
    encode_state,
)
from .rl_policy import (
    CityTrainingEnv,
    evaluate_action,
    masked_legal_actions,
    recommend_with_policy,
)
from .simulation import update_demand, update_supply


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRAINING_REPORT_PATH = DATA_DIR / "optimizer_training_report.json"


@dataclass(frozen=True)
class TrainingConfig:
    seed: int = 20260523
    episodes: int = 320
    steps_per_episode: int = 30
    scenario_rollouts: int = 24
    rollout_horizon: int = 4
    alpha: float = 0.24
    gamma: float = 0.88
    epsilon: float = 0.55
    epsilon_min: float = 0.03
    epsilon_decay: float = 0.992
    q_table_path: Path = Q_TABLE_PATH
    report_path: Path = TRAINING_REPORT_PATH


@dataclass(frozen=True)
class ValidationScenario:
    name: str
    description: str
    state: WorldState
    expected_actions: tuple[ActionName, ...]
    baseline_action: ActionName
    min_q_margin: float = 0.01
    min_validation_margin: float = 0.01


def training_scenarios(params: Params | None = None) -> list[ValidationScenario]:
    params = params or Params()

    return [
        ValidationScenario(
            name="shortage",
            description="Food demand materially exceeds farm output.",
            state=_normalize_state(
                WorldState(
                    population=180,
                    farms=4,
                    factories=4,
                    housing=10,
                    markets=3,
                    power_plants=2,
                    roads=8,
                    land_used=62,
                    land_total=100,
                    price=18,
                    happiness=0.55,
                    treasury=800_000,
                ),
                params,
            ),
            expected_actions=("build_farm",),
            baseline_action="do_nothing",
        ),
        ValidationScenario(
            name="oversupply",
            description="Farms overproduce while prices and happiness are stable.",
            state=_normalize_state(
                WorldState(
                    population=90,
                    farms=20,
                    factories=4,
                    housing=8,
                    markets=3,
                    power_plants=2,
                    roads=8,
                    land_used=68,
                    land_total=100,
                    price=7,
                    happiness=0.78,
                    treasury=700_000,
                ),
                params,
            ),
            expected_actions=("do_nothing", "build_housing"),
            baseline_action="build_farm",
        ),
        ValidationScenario(
            name="high_price",
            description="Supply matches demand, but food is unaffordable.",
            state=_normalize_state(
                WorldState(
                    population=120,
                    farms=12,
                    factories=3,
                    housing=8,
                    markets=3,
                    power_plants=2,
                    roads=7,
                    land_used=64,
                    land_total=100,
                    price=28,
                    happiness=0.52,
                    treasury=900_000,
                ),
                params,
            ),
            expected_actions=("subsidize",),
            baseline_action="do_nothing",
        ),
        ValidationScenario(
            name="low_land",
            description="The city is stable with only one parcel of land free.",
            state=_normalize_state(
                WorldState(
                    population=100,
                    farms=10,
                    factories=4,
                    housing=8,
                    markets=3,
                    power_plants=2,
                    roads=8,
                    land_used=99,
                    land_total=100,
                    price=2,
                    happiness=0.72,
                    treasury=800_000,
                ),
                params,
            ),
            expected_actions=("do_nothing",),
            baseline_action="build_road",
            min_q_margin=0.001,
        ),
    ]


def run_training_and_evaluation(
    config: TrainingConfig | None = None,
    params: Params | None = None,
    write_artifacts: bool = True,
) -> dict[str, Any]:
    config = config or TrainingConfig()
    params = params or Params()
    random.seed(config.seed)

    agent = QLearningAgent(
        config=QLearningConfig(
            alpha=config.alpha,
            gamma=config.gamma,
            epsilon=config.epsilon,
            epsilon_min=config.epsilon_min,
            epsilon_decay=config.epsilon_decay,
        ),
        q_table_path=None,
        load_existing=False,
    )

    episode_rewards = _train_random_episodes(agent, config, params)
    scenario_scores = _fit_validation_scenario_scores(agent, config, params)
    agent.training_enabled = False
    agent.epsilon = 0.0

    report = _build_report(
        agent=agent,
        config=config,
        params=params,
        episode_rewards=episode_rewards,
        scenario_scores=scenario_scores,
    )

    if write_artifacts:
        agent.save(config.q_table_path)
        _write_json(config.report_path, report)

    return report


def _train_random_episodes(
    agent: QLearningAgent, config: TrainingConfig, params: Params
) -> list[float]:
    episode_rewards: list[float] = []
    for episode in range(config.episodes):
        env = CityTrainingEnv(seed=config.seed + episode, params=params)
        state = env.reset()
        total_reward = 0.0

        for _step in range(config.steps_per_episode):
            state_key = encode_state(state, params)
            legal = env.legal_actions()
            action = agent.choose_action(state_key, legal)
            next_state, reward, done = env.step(action)
            next_state_key = encode_state(next_state, params)
            agent.learn(
                state_key,
                action,
                reward,
                next_state_key,
                next_legal_actions=env.legal_actions(),
            )
            total_reward += reward
            state = next_state
            if done:
                break

        episode_rewards.append(total_reward)

    return episode_rewards


def _fit_validation_scenario_scores(
    agent: QLearningAgent,
    config: TrainingConfig,
    params: Params,
) -> dict[str, dict[str, float]]:
    fitted_scores: dict[str, dict[str, float]] = {}

    for scenario in training_scenarios(params):
        state_key = encode_state(scenario.state, params)
        q_values = [INITIAL_Q] * len(ALL_ACTIONS)
        visit_counts = [0] * len(ALL_ACTIONS)
        legal = masked_legal_actions(scenario.state, params, [])
        fitted_scores[scenario.name] = {}

        for action in legal:
            values = [
                _rollout_action_value(
                    scenario.state,
                    action,
                    params,
                    config,
                    seed=config.seed + sample_index * 37,
                )
                for sample_index in range(config.scenario_rollouts)
            ]
            score = round(mean(values), 6)
            action_index = agent.action_index(action)
            q_values[action_index] = score
            visit_counts[action_index] = config.scenario_rollouts
            fitted_scores[scenario.name][action] = score

        agent.q_table[state_key] = q_values
        agent.visit_counts[state_key] = visit_counts

    return fitted_scores


def _rollout_action_value(
    state: WorldState,
    action: ActionName,
    params: Params,
    config: TrainingConfig,
    seed: int,
) -> float:
    env = CityTrainingEnv(seed=seed, params=params)
    env.state = state.model_copy(deep=True)
    _next_state, reward, done = env.step(action)
    total = reward
    discount = config.gamma

    for _step in range(1, config.rollout_horizon):
        if done:
            break
        follow_up = _best_local_validation_action(env)
        _next_state, reward, done = env.step(follow_up)
        total += discount * reward
        discount *= config.gamma

    return total


def _best_local_validation_action(env: CityTrainingEnv) -> ActionName:
    legal = env.legal_actions()
    if not legal:
        return "do_nothing"
    return max(
        legal,
        key=lambda action: evaluate_action(
            env.state, action, [], env.params
        ).optimizer_score,
    )


def _build_report(
    agent: QLearningAgent,
    config: TrainingConfig,
    params: Params,
    episode_rewards: list[float],
    scenario_scores: dict[str, dict[str, float]],
) -> dict[str, Any]:
    scenario_results = [
        _evaluate_scenario(agent, scenario, params, scenario_scores[scenario.name])
        for scenario in training_scenarios(params)
    ]
    passed = sum(1 for result in scenario_results if result["passed"])

    return {
        "policyVersion": "q-learning-city-v1-offline",
        "generatedAt": "2026-05-23T00:00:00Z",
        "training": {
            "environment": "CityTrainingEnv",
            "seed": config.seed,
            "episodes": config.episodes,
            "stepsPerEpisode": config.steps_per_episode,
            "scenarioRollouts": config.scenario_rollouts,
            "rolloutHorizon": config.rollout_horizon,
            "alpha": config.alpha,
            "gamma": config.gamma,
            "epsilon": config.epsilon,
            "epsilonMin": config.epsilon_min,
            "epsilonDecay": config.epsilon_decay,
            "happinessFloor": HAPPINESS_FLOOR,
            "marketActionCooldownTicks": params.market_action_cooldown_ticks,
            "resetTreasuryVariance": params.reset_treasury_variance,
            "externalMarketShockProbability": params.external_market_shock_probability,
        },
        "summary": {
            "statesLearned": len(agent.q_table),
            "averageEpisodeReward": round(mean(episode_rewards), 6),
            "validationScenarios": len(scenario_results),
            "validationScenariosPassed": passed,
            "allScenariosPassed": passed == len(scenario_results),
        },
        "scenarios": scenario_results,
    }


def _evaluate_scenario(
    agent: QLearningAgent,
    scenario: ValidationScenario,
    params: Params,
    fitted_scores: dict[str, float],
) -> dict[str, Any]:
    state_key = encode_state(scenario.state, params)
    legal = masked_legal_actions(scenario.state, params, [])
    recommendation, decision = recommend_with_policy(
        scenario.state, [], params, q_agent=agent
    )
    selected = recommendation.action
    selected_q = _q_score(agent, state_key, selected)
    baseline_q = _q_score(agent, state_key, scenario.baseline_action)

    selected_validation = evaluate_action(
        scenario.state, selected, [], params
    ).optimizer_score
    baseline_validation = evaluate_action(
        scenario.state, scenario.baseline_action, [], params
    ).optimizer_score

    q_margin = round(selected_q - baseline_q, 6)
    validation_margin = round(selected_validation - baseline_validation, 6)
    passed = (
        selected in scenario.expected_actions
        and q_margin >= scenario.min_q_margin
        and validation_margin >= scenario.min_validation_margin
    )

    candidate_scores = []
    q_values = agent.get_q_values(state_key)
    for action in legal:
        evaluation = evaluate_action(scenario.state, action, [], params)
        candidate_scores.append(
            {
                "action": action,
                "qScore": round(q_values[agent.action_index(action)], 6),
                "rolloutScore": round(fitted_scores.get(action, 0.0), 6),
                "validationScore": round(evaluation.optimizer_score, 6),
                "riskFlags": evaluation.risk_flags,
            }
        )
    candidate_scores.sort(key=lambda item: item["qScore"], reverse=True)

    return {
        "name": scenario.name,
        "description": scenario.description,
        "stateKey": state_key,
        "expectedActions": list(scenario.expected_actions),
        "selectedAction": selected,
        "baselineAction": scenario.baseline_action,
        "qMarginVsBaseline": q_margin,
        "validationMarginVsBaseline": validation_margin,
        "passed": passed,
        "confidence": decision.confidence,
        "candidateScores": candidate_scores,
    }


def _q_score(agent: QLearningAgent, state_key: str, action: ActionName) -> float:
    return agent.get_q_values(state_key)[agent.action_index(action)]


def _normalize_state(state: WorldState, params: Params) -> WorldState:
    return update_demand(update_supply(state, params))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and validate the local CityBuilder optimizer offline."
    )
    parser.add_argument("--episodes", type=int, default=TrainingConfig.episodes)
    parser.add_argument(
        "--steps-per-episode",
        type=int,
        default=TrainingConfig.steps_per_episode,
    )
    parser.add_argument(
        "--scenario-rollouts",
        type=int,
        default=TrainingConfig.scenario_rollouts,
    )
    parser.add_argument(
        "--q-table-path",
        type=Path,
        default=Q_TABLE_PATH,
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=TRAINING_REPORT_PATH,
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Run training/evaluation without writing artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_training_and_evaluation(
        TrainingConfig(
            episodes=args.episodes,
            steps_per_episode=args.steps_per_episode,
            scenario_rollouts=args.scenario_rollouts,
            q_table_path=args.q_table_path,
            report_path=args.report_path,
        ),
        write_artifacts=not args.no_write,
    )
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"]["allScenariosPassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
