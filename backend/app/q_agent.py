from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .models import ActionName, Params, WorldState


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

Q_TABLE_PATH = Path(__file__).resolve().parent.parent / "data" / "q_table.json"


@dataclass
class QLearningConfig:
    alpha: float = 0.1
    gamma: float = 0.95
    epsilon: float = 0.6
    epsilon_min: float = 0.05
    epsilon_decay: float = 0.992


def encode_state(state: WorldState, params: Params) -> str:
    demand = max(state.food_demand, 1)
    ratio = state.food_supply / demand
    fb = 0 if ratio < 0.7 else 1 if ratio < 1.3 else 2

    p = 0 if state.price <= 8 else 1 if state.price <= 18 else 2

    h = 0 if state.happiness < 0.4 else 1 if state.happiness < 0.7 else 2

    land_free = (state.land_total - state.land_used) / max(state.land_total, 1)
    lb = 0 if land_free < 0.1 else 1 if land_free < 0.3 else 2

    infra = (state.roads + state.power_plants * 2) / max(
        state.factories + state.housing + state.markets, 1
    )
    inf = 0 if infra < 0.5 else 1 if infra < 1.0 else 2

    pop_ratio = state.population / max(state.housing * 18, 1)
    pop = 0 if pop_ratio < 0.5 else 1

    treasury_idle = 1 if state.treasury > 500_000 and infra < 1.0 else 0

    return f"fb{fb}_p{p}_h{h}_lb{lb}_inf{inf}_pop{pop}_t{treasury_idle}"


def reward_components(state: WorldState, params: Params) -> dict[str, float]:
    demand = max(state.food_demand, 1)
    return {
        "foodBalance": max(0, 1 - abs(1 - state.food_supply / demand)),
        "affordability": max(
            0,
            1
            - (
                (state.price - params.base_price)
                / max(params.max_price - params.base_price, 1)
            ),
        ),
        "happiness": max(0, state.happiness),
        "landBuffer": max(
            0,
            (state.land_total - state.land_used) / max(state.land_total * 0.20, 1),
        ),
        "infrastructure": max(
            0,
            (state.roads + state.power_plants * 2)
            / max(state.factories + state.housing + state.markets, 1),
        ),
        "oversupplyPenalty": max(
            0, (state.food_supply - state.food_demand * 1.35) / demand
        ),
        "scarcityPenalty": max(
            0, (state.food_demand - state.food_supply) / demand
        ),
    }


def compute_reward(
    state: WorldState, next_state: WorldState, params: Params
) -> dict[str, float]:
    current = reward_components(state, params)
    next_comp = reward_components(next_state, params)

    pop_change = next_state.population - state.population
    pop_reward = pop_change / max(state.population, 1) * 0.5

    infra_ratio = (next_state.roads + next_state.power_plants * 2) / max(
        next_state.factories + next_state.housing + next_state.markets, 1
    )
    treasury_penalty = (
        -0.15 if next_state.treasury > 500_000 and infra_ratio < 1.0 else 0.0
    )

    pop_level = next_state.population / max(next_state.food_demand, 1)
    if pop_level < 0.5:
        collapse_penalty = -0.5 - (0.5 - pop_level) * 2.0
    elif pop_level < 0.3:
        collapse_penalty = -1.0
    else:
        collapse_penalty = 0.0

    land_full_penalty = (
        -0.3 if next_state.land_used >= next_state.land_total else 0.0
    )
    bankrupt_penalty = -0.3 if next_state.treasury < 10_000 else 0.0

    total = (
        next_comp["foodBalance"] * 0.20
        + next_comp["affordability"] * 0.12
        + next_comp["happiness"] * 0.18
        + next_comp["landBuffer"] * 0.12
        - next_comp["oversupplyPenalty"] * 0.08
        - next_comp["scarcityPenalty"] * 0.12
        + pop_reward
        + treasury_penalty
        + collapse_penalty
        + land_full_penalty
        + bankrupt_penalty
    )

    return {
        "total": total,
        "popReward": round(pop_reward, 4),
        "treasuryPenalty": treasury_penalty,
        "collapsePenalty": round(collapse_penalty, 4),
        "landFullPenalty": land_full_penalty,
        "bankruptPenalty": bankrupt_penalty,
    }


class QLearningAgent:
    def __init__(self, config: QLearningConfig | None = None):
        self.config = config or QLearningConfig()
        self.q_table: dict[str, list[float]] = defaultdict(
            lambda: [0.0] * len(ALL_ACTIONS)
        )
        self.epsilon = self.config.epsilon
        self.training_enabled = True
        self._load()

    def action_index(self, action: ActionName) -> int:
        return ALL_ACTIONS.index(action)

    def action_name(self, index: int) -> ActionName:
        return ALL_ACTIONS[index]

    def choose_action(
        self, state_key: str, legal_actions: list[ActionName]
    ) -> ActionName:
        if not legal_actions:
            return "do_nothing"
        if self.training_enabled and random.random() < self.epsilon:
            return random.choice(legal_actions)
        q_values = self.q_table[state_key]
        legal_set = set(legal_actions)
        candidates = [
            (a, q_values[self.action_index(a)])
            for a in ALL_ACTIONS
            if a in legal_set
        ]
        if not candidates:
            return "do_nothing"
        return max(candidates, key=lambda x: x[1])[0]

    def learn(
        self,
        state_key: str,
        action: ActionName,
        reward: float,
        next_state_key: str,
    ) -> None:
        if not self.training_enabled:
            return
        idx = self.action_index(action)
        current_q = self.q_table[state_key][idx]
        max_next = max(self.q_table[next_state_key])
        td_target = reward + self.config.gamma * max_next
        self.q_table[state_key][idx] = current_q + self.config.alpha * (
            td_target - current_q
        )
        self.epsilon = max(
            self.config.epsilon_min, self.epsilon * self.config.epsilon_decay
        )

    def _load(self) -> None:
        try:
            if Q_TABLE_PATH.exists():
                with open(Q_TABLE_PATH) as f:
                    data = json.load(f)
                for k, v in data.items():
                    self.q_table[k] = v
        except Exception:
            pass

    def save(self) -> None:
        Q_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(Q_TABLE_PATH, "w") as f:
            json.dump(dict(self.q_table), f, indent=2)

    def get_q_values(self, state_key: str) -> list[float]:
        return self.q_table[state_key]

    def get_max_q(self, state_key: str) -> float:
        return max(self.q_table[state_key])
