from __future__ import annotations

import random

from .city_map import build_city_map
from .models import (
    ActionName,
    CityEvent,
    DecisionImpact,
    DecisionMetricSnapshot,
    GovernmentRecommendation,
    MayorDecisionOutcome,
    MayorDecisionScorecardEntry,
    Params,
    SimulationControls,
    StateResponse,
    TickSnapshot,
    WorldState,
)
from .q_agent import QLearningAgent, compute_reward, encode_state
from .simulation import (
    BUILD_FUNCTIONS,
    BUILDING_COSTS,
    mayor_direction_score,
    step,
    subsidize,
    subsidy_cost,
    update_supply,
)
from .rl_policy import ACTION_TO_BUILDING, recommend_with_policy


class CitySimulationService:
    LIVE_TICK_INTERVAL_SECONDS = 0.35
    FAST_FORWARD_TICKS = 5

    def __init__(
        self,
        seed: int = 42,
        params: Params | None = None,
        persist_online_learning: bool = False,
    ) -> None:
        self.seed = seed
        self.params = params or Params()
        self.persist_online_learning = persist_online_learning
        self.rng = random.Random(seed)
        self.state = WorldState()
        self.live_running = False
        self.q_agent = QLearningAgent()
        self.recommendation, self.decision_system = recommend_with_policy(
            self.state, [], self.params, q_agent=self.q_agent
        )
        self.events: list[CityEvent] = [
            CityEvent(tick=0, message="Simulation initialized.", severity="info")
        ]
        self.history: list[TickSnapshot] = []
        self.decision_scorecard: list[MayorDecisionScorecardEntry] = []
        self._decision_sequence = 0
        self._last_state_key = encode_state(self.state, self.params)
        self._record_snapshot()

    def snapshot(self) -> StateResponse:
        return StateResponse(
            state=self.state,
            params=self.params,
            recommendation=self.recommendation,
            decisionSystem=self.decision_system,
            mayorScore=mayor_direction_score(self.state, self.history, self.params),
            decisionScorecard=list(self.decision_scorecard),
            cityMap=build_city_map(self.state),
            history=list(self.history),
            events=list(self.events[-80:]),
            simulation=self._simulation_controls(),
        )

    def reset(self) -> StateResponse:
        self.rng = random.Random(self.seed)
        self.state = WorldState()
        self.live_running = False
        self.events = [
            CityEvent(tick=0, message="Simulation reset.", severity="info")
        ]
        self.history = []
        self.decision_scorecard = []
        self._decision_sequence = 0
        self._last_state_key = encode_state(self.state, self.params)
        self._refresh_policy_recommendation()
        self._record_snapshot()
        return self.snapshot()

    def tick(self) -> StateResponse:
        state_before = self.state
        state_key_before = self._last_state_key
        action_taken = self.recommendation.action

        result = step(self.state, self.rng, self.params)
        self.state = result.state
        self.events.extend(result.events)

        self._apply_action(action_taken)

        new_state_key = encode_state(self.state, self.params)
        reward_result = compute_reward(state_before, self.state, self.params)
        self.q_agent.learn(state_key_before, action_taken, reward_result["total"], new_state_key)
        self._last_state_key = new_state_key

        terminal = (
            self.state.population < 50
            or self.state.land_used >= self.state.land_total * 0.9
            or (self.state.treasury < 30_000 and self.state.population < 80)
        )
        if terminal and self.state.tick > 20:
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Terminal state reached. Resetting simulation for next training episode. "
                    f"Q-table has {len(self.q_agent.q_table)} states, epsilon={self.q_agent.epsilon:.3f}.",
                    severity="danger",
                )
            )
            self.state = WorldState()
            self._last_state_key = encode_state(self.state, self.params)
            self._refresh_policy_recommendation()
            self._record_snapshot()
            self._persist_q_agent()
            return self.snapshot()

        if self.q_agent.training_enabled:
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Q-Learning: reward={reward_result['total']:.3f}, "
                    f"exploration={self.q_agent.epsilon:.2%}, "
                    f"states_visited={len(self.q_agent.q_table)}.",
                    severity="info",
                )
            )

        self._resolve_pending_decision_impacts()
        self._refresh_policy_recommendation()

        if self.recommendation.action != "do_nothing":
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Local optimizer recommends {self.recommendation.action.replace('_', ' ')}.",
                    severity="info",
                )
            )

        self._record_snapshot()
        self._persist_q_agent()
        return self.snapshot()

    def advance(self, ticks: int | None = None) -> StateResponse:
        ticks_to_run = ticks if ticks is not None else self.FAST_FORWARD_TICKS
        response: StateResponse | None = None
        for _ in range(ticks_to_run):
            response = self.tick()
        return response or self.snapshot()

    def play_live(self) -> StateResponse:
        self.live_running = True
        return self.snapshot()

    def pause_live(self) -> StateResponse:
        self.live_running = False
        return self.snapshot()

    def approve_government_action(self) -> StateResponse:
        action = self.recommendation.action
        recommendation = self.recommendation.model_copy(deep=True)
        before = self._decision_metric_snapshot(self.state)

        if action in ACTION_TO_BUILDING:
            self._approve_build_action(action)
        elif action == "subsidize":
            cost = subsidy_cost(self.state, self.params)
            before = self.state
            self.state = subsidize(self.state, self.params)
            if self.state == before:
                self.events.append(
                    CityEvent(
                        tick=self.state.tick,
                        message="Government could not fund the food price subsidy.",
                        severity="warning",
                    )
                )
            else:
                self.events.append(
                    CityEvent(
                        tick=self.state.tick,
                        message=f"Government approved a food price subsidy for ${cost:,.0f}.",
                        severity="success",
                    )
                )
        else:
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message="Government approved no intervention.",
                    severity="info",
                )
            )

        self._record_decision(recommendation, "approved", before)
        self._refresh_policy_recommendation()
        self._record_snapshot()
        return self.snapshot()

    def reject_government_action(self) -> StateResponse:
        recommendation = self.recommendation.model_copy(deep=True)
        before = self._decision_metric_snapshot(self.state)
        self.events.append(
            CityEvent(
                tick=self.state.tick,
                message=f"Government rejected {self.recommendation.action.replace('_', ' ')}.",
                severity="warning",
            )
        )
        self._record_decision(recommendation, "rejected", before)
        self._refresh_policy_recommendation()
        self._record_snapshot()
        return self.snapshot()

    def build_structure(self, building_type: str) -> StateResponse:
        build_fn = BUILD_FUNCTIONS.get(building_type)  # type: ignore[arg-type]
        if build_fn is None:
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Unknown building type: {building_type}.",
                    severity="danger",
                )
            )
            return self.snapshot()

        cost = BUILDING_COSTS.get(building_type, 0)  # type: ignore[arg-type]
        if self.state.treasury < cost:
            label = building_type.replace("_", " ").title()
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Cannot build {label}: not enough treasury.",
                    severity="warning",
                )
            )
            return self.snapshot()

        before = self.state
        self.state = build_fn(self.state, self.params)  # type: ignore[operator]
        if self.state == before:
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Cannot build {building_type.replace('_', ' ')}: not enough land.",
                    severity="warning",
                )
            )
        else:
            self.state = self.state.model_copy(
                update={"treasury": self.state.treasury - cost}
            )
            self.state = update_supply(self.state, self.params)
            label = building_type.replace("_", " ").title()
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Built a new {label} for ${cost:,}.",
                    severity="success",
                )
            )

        self._refresh_policy_recommendation()
        self._record_snapshot()
        return self.snapshot()

    def _record_snapshot(self) -> None:
        self.history.append(
            TickSnapshot(state=self.state, recommendation=self.recommendation)
        )
        if len(self.history) > self.params.history_limit:
            self.history = self.history[-self.params.history_limit :]

    def _record_decision(
        self,
        recommendation: GovernmentRecommendation,
        decision: MayorDecisionOutcome,
        before: DecisionMetricSnapshot,
    ) -> None:
        self._decision_sequence += 1
        self.decision_scorecard.append(
            MayorDecisionScorecardEntry(
                id=f"{self.state.tick}-{self._decision_sequence}-{recommendation.action}",
                tick=self.state.tick,
                action=recommendation.action,
                decision=decision,
                reason=recommendation.reason,
                before=before,
            )
        )
        if len(self.decision_scorecard) > self.params.history_limit:
            self.decision_scorecard = self.decision_scorecard[-self.params.history_limit :]

    def _resolve_pending_decision_impacts(self) -> None:
        if not any(entry.impact is None for entry in self.decision_scorecard):
            return

        after = self._decision_metric_snapshot(self.state)
        resolved_entries: list[MayorDecisionScorecardEntry] = []
        for entry in self.decision_scorecard:
            if entry.impact is None and self.state.tick > entry.tick:
                impact = DecisionImpact(
                    food_balance_delta=round(after.food_balance - entry.before.food_balance, 2),
                    price_delta=round(after.price - entry.before.price, 2),
                    happiness_delta=round(after.happiness - entry.before.happiness, 4),
                    mayor_score_delta=after.mayor_score - entry.before.mayor_score,
                )
                entry = entry.model_copy(
                    update={
                        "after": after,
                        "impact": impact,
                        "next_tick": self.state.tick,
                    }
                )
            resolved_entries.append(entry)
        self.decision_scorecard = resolved_entries

    def _decision_metric_snapshot(self, state: WorldState) -> DecisionMetricSnapshot:
        mayor_score = mayor_direction_score(state, self.history, self.params).score
        return DecisionMetricSnapshot(
            food_balance=round(state.food_supply - state.food_demand, 2),
            price=round(state.price, 2),
            happiness=round(state.happiness, 4),
            mayor_score=mayor_score,
        )

    def _refresh_policy_recommendation(self) -> None:
        self.recommendation, self.decision_system = recommend_with_policy(
            self.state, self.history, self.params, q_agent=self.q_agent
        )

    def _simulation_controls(self) -> SimulationControls:
        return SimulationControls(
            running=self.live_running,
            liveTickIntervalSeconds=self.LIVE_TICK_INTERVAL_SECONDS,
            fastForwardTicks=self.FAST_FORWARD_TICKS,
        )

    def _apply_action(self, action: ActionName) -> None:
        if action == "do_nothing":
            return
        if action in ACTION_TO_BUILDING:
            building_type = ACTION_TO_BUILDING[action]
            build_fn = BUILD_FUNCTIONS.get(building_type)
            cost = BUILDING_COSTS.get(building_type, 0)
            if build_fn is None or self.state.treasury < cost:
                return
            before = self.state
            self.state = build_fn(self.state, self.params)
            if self.state != before:
                self.state = self.state.model_copy(
                    update={"treasury": self.state.treasury - cost}
                )
                self.state = update_supply(self.state, self.params)
        elif action == "subsidize":
            cost = subsidy_cost(self.state, self.params)
            if self.state.treasury >= cost:
                self.state = subsidize(self.state, self.params)

    def _persist_q_agent(self) -> None:
        if self.persist_online_learning:
            self.q_agent.save()

    def _approve_build_action(self, action: str) -> None:
        building_type = ACTION_TO_BUILDING[action]  # type: ignore[index]
        build_fn = BUILD_FUNCTIONS[building_type]  # type: ignore[index]
        cost = BUILDING_COSTS[building_type]  # type: ignore[index]
        label = building_type.replace("_", " ").title()
        if self.state.treasury < cost:
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Government could not build {label} because treasury is too low.",
                    severity="warning",
                )
            )
            return

        before = self.state
        self.state = build_fn(self.state, self.params)  # type: ignore[operator]
        self.state = update_supply(self.state, self.params)
        if self.state != before:
            self.state = self.state.model_copy(
                update={"treasury": self.state.treasury - cost}
            )
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Government approved construction of a new {label} for ${cost:,}.",
                    severity="success",
                )
            )
        else:
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Government could not build {label} because no land is available.",
                    severity="warning",
                )
            )
