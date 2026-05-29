from __future__ import annotations

import random
from typing import cast

from .city_map import PersistentCityMap
from .models import (
    ActionName,
    BuildAvailability,
    BuildingType,
    CityEvent,
    DecisionImpact,
    DecisionMetricSnapshot,
    GovernmentRecommendation,
    MayorDecisionOutcome,
    MayorDecisionScorecardEntry,
    MayorScore,
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
    can_spend_treasury,
    mayor_direction_score,
    randomized_starting_state,
    step,
    subsidize,
    subsidy_cost,
    treasury_emergency_floor,
    treasury_reserve,
    update_supply,
)
from .rl_policy import ACTION_TO_BUILDING, legal_actions_for_history, recommend_with_policy


class CitySimulationService:
    LIVE_TICK_INTERVAL_SECONDS = 0.35
    FAST_FORWARD_TICKS = 5
    MAX_SIMULATION_DAYS = 100
    TERMINAL_PAUSE_REASON = "Terminal state reached. Reset to start a new episode."
    DAY_LIMIT_PAUSE_REASON = "100-day limit reached. Reset to start a new episode."

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
        self.state = self._new_episode_state()
        self.city_map = PersistentCityMap.from_state(self.state)
        self._sync_land_budget_to_map()
        self.live_running = False
        self.terminal_reached = False
        self.pause_reason: str | None = None
        self.q_agent = QLearningAgent()
        self.q_agent.training_enabled = persist_online_learning
        self.events: list[CityEvent] = [
            CityEvent(tick=0, message="Simulation initialized.", severity="info")
        ]
        self.history: list[TickSnapshot] = []
        self.decision_scorecard: list[MayorDecisionScorecardEntry] = []
        self._decision_sequence = 0
        self._last_state_key = encode_state(self.state, self.params)
        self._refresh_policy_recommendation()
        self._record_snapshot()

    def snapshot(self) -> StateResponse:
        return StateResponse(
            state=self.state,
            params=self.params,
            recommendation=self.recommendation,
            decisionSystem=self.decision_system,
            mayorScore=self._mayor_score(),
            decisionScorecard=list(self.decision_scorecard),
            cityMap=self.city_map.to_layout(self.state),
            buildAvailability=self._build_availability(),
            history=list(self.history),
            events=list(self.events[-80:]),
            simulation=self._simulation_controls(),
        )

    def reset(self) -> StateResponse:
        self.state = self._new_episode_state()
        self.city_map = PersistentCityMap.from_state(self.state)
        self._sync_land_budget_to_map()
        self.live_running = False
        self.terminal_reached = False
        self.pause_reason = None
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
        if self.state.tick >= self.MAX_SIMULATION_DAYS and not self.terminal_reached:
            self._mark_day_limit_reached()

        if self.terminal_reached:
            self.live_running = False
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=(
                        f"Simulation is paused: {self._terminal_pause_reason()}"
                    ),
                    severity="warning",
                )
            )
            return self.snapshot()

        state_before = self.state
        state_key_before = self._last_state_key
        action_taken = self.recommendation.action

        step_params = (
            self.params
            if self.city_map.can_place_building_type("farm")
            else self.params.model_copy(update={"company_expand_probability": 0.0})
        )
        result = step(self.state, self.rng, step_params)
        self.state = result.state
        self.city_map.sync_to_state(state_before, self.state)
        self._sync_land_budget_to_map()
        self.events.extend(result.events)

        self._apply_action(action_taken)
        self._sync_land_budget_to_map()

        new_state_key = encode_state(self.state, self.params)
        reward_result = compute_reward(state_before, self.state, self.params)
        next_legal_actions = legal_actions_for_history(
            self.state, self.params, self.history
        )
        next_legal_actions = self._map_aware_legal_actions_from(next_legal_actions)
        self.q_agent.learn(
            state_key_before,
            action_taken,
            reward_result["total"],
            new_state_key,
            next_legal_actions=next_legal_actions,
        )
        self._last_state_key = new_state_key

        if self.state.tick >= self.MAX_SIMULATION_DAYS:
            self._mark_day_limit_reached()
            self._resolve_pending_decision_impacts()
            self._refresh_policy_recommendation()
            self._record_snapshot()
            self._persist_q_agent()
            return self.snapshot()

        terminal = (
            self.state.population < 50
            or self.state.land_used >= self.state.land_total * 0.9
            or (self.state.treasury < 30_000 and self.state.population < 80)
        )
        if terminal and self.state.tick > 20 and self.persist_online_learning:
            self.live_running = False
            self.terminal_reached = True
            self.pause_reason = self.TERMINAL_PAUSE_REASON
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"{self.TERMINAL_PAUSE_REASON} "
                    f"City layout preserved; Q-table has {len(self.q_agent.q_table)} states, "
                    f"epsilon={self.q_agent.epsilon:.3f}.",
                    severity="danger",
                )
            )
            self._resolve_pending_decision_impacts()
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
            if self.terminal_reached:
                break
        return response or self.snapshot()

    def play_live(self) -> StateResponse:
        if self.state.tick >= self.MAX_SIMULATION_DAYS and not self.terminal_reached:
            self._mark_day_limit_reached()

        if self.terminal_reached:
            self.live_running = False
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Cannot resume: {self._terminal_pause_reason()}",
                    severity="warning",
                )
            )
            return self.snapshot()
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
            state_before_subsidy = self.state
            if not can_spend_treasury(self.state, cost, self.params):
                self.events.append(
                    CityEvent(
                        tick=self.state.tick,
                    message=(
                        "Government could not fund the food price subsidy without "
                        f"breaching the ${treasury_emergency_floor(self.params):,.0f} emergency floor."
                    ),
                    severity="warning",
                )
                )
            else:
                self.state = subsidize(self.state, self.params)
                if self.state == state_before_subsidy:
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
        self._sync_land_budget_to_map()
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

        building_key = cast(BuildingType, building_type)
        cost = BUILDING_COSTS.get(building_type, 0)  # type: ignore[arg-type]
        if not self.city_map.can_place_building_type(building_key):
            label = building_type.replace("_", " ").title()
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Cannot build {label}: no open map cell is available.",
                    severity="warning",
                )
            )
            return self.snapshot()

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

        if not can_spend_treasury(self.state, cost, self.params):
            label = building_type.replace("_", " ").title()
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=(
                        f"Cannot build {label}: emergency treasury floor of "
                        f"${treasury_emergency_floor(self.params):,.0f} would be breached."
                    ),
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
            self.city_map.place_building_type(building_key)
            self.state = self.state.model_copy(
                update={"treasury": self.state.treasury - cost}
            )
            self.state = update_supply(self.state, self.params)
            self._sync_land_budget_to_map()
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
        mayor_score = self._mayor_score().score if state == self.state else mayor_direction_score(state, self.history, self.params).score
        return DecisionMetricSnapshot(
            food_balance=round(state.food_supply - state.food_demand, 2),
            price=round(state.price, 2),
            happiness=round(state.happiness, 4),
            mayor_score=mayor_score,
        )

    def _refresh_policy_recommendation(self) -> None:
        self._sync_land_budget_to_map()
        self.recommendation, self.decision_system = recommend_with_policy(
            self.state,
            self.history,
            self.params,
            q_agent=self.q_agent,
            legal_override=self._map_aware_legal_actions(),
        )

    def _simulation_controls(self) -> SimulationControls:
        terminal_reached = (
            self.terminal_reached or self.state.tick >= self.MAX_SIMULATION_DAYS
        )
        return SimulationControls(
            running=self.live_running and not terminal_reached,
            terminalReached=terminal_reached,
            pauseReason=self._terminal_pause_reason() if terminal_reached else None,
            maxDays=self.MAX_SIMULATION_DAYS,
            liveTickIntervalSeconds=self.LIVE_TICK_INTERVAL_SECONDS,
            fastForwardTicks=self.FAST_FORWARD_TICKS,
        )

    def _mark_day_limit_reached(self) -> None:
        self.live_running = False
        self.terminal_reached = True
        self.pause_reason = self.DAY_LIMIT_PAUSE_REASON
        if not any(
            event.message == self.DAY_LIMIT_PAUSE_REASON for event in self.events[-5:]
        ):
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=self.DAY_LIMIT_PAUSE_REASON,
                    severity="warning",
                )
            )

    def _terminal_pause_reason(self) -> str:
        if self.pause_reason:
            return self.pause_reason
        if self.state.tick >= self.MAX_SIMULATION_DAYS:
            return self.DAY_LIMIT_PAUSE_REASON
        return self.TERMINAL_PAUSE_REASON

    def _mayor_score(self) -> MayorScore:
        open_cells = len(self.city_map.available_building_cells())
        map_capacity = max(len(self.city_map.occupied_cells()) + open_cells, 1)
        return mayor_direction_score(
            self.state,
            self.history,
            self.params,
            land_buffer_free=open_cells,
            land_buffer_capacity=map_capacity,
        )

    def _build_availability(self) -> dict[BuildingType, BuildAvailability]:
        availability: dict[BuildingType, BuildAvailability] = {}
        for building_type in BUILDING_COSTS:
            typed_building = cast(BuildingType, building_type)
            cost = BUILDING_COSTS[typed_building]
            land_required = self._land_required(typed_building)
            open_cells = self.city_map.available_cells_for_building_type(typed_building)

            if open_cells <= 0:
                can_build = False
                reason = "No open map cell is available."
            elif self.state.treasury < cost:
                can_build = False
                reason = "Not enough treasury."
            elif not can_spend_treasury(self.state, cost, self.params):
                can_build = False
                reason = f"Emergency floor ${treasury_emergency_floor(self.params):,.0f} protected."
            elif self.state.treasury - cost < treasury_reserve(self.params):
                can_build = True
                reason = "Below reserve target, but funded."
            else:
                can_build = True
                reason = "Ready."

            availability[typed_building] = BuildAvailability(
                canBuild=can_build,
                reason=reason,
                openCells=open_cells,
                treasuryRequired=cost,
                landRequired=land_required,
            )
        return availability

    def _land_required(self, building_type: BuildingType) -> int:
        if building_type == "road":
            return 1
        if building_type in {"factory", "power_plant"}:
            return 3
        return self.params.build_cost_land

    def _new_episode_state(self) -> WorldState:
        return randomized_starting_state(self.rng, self.params)

    def _sync_land_budget_to_map(self) -> None:
        open_building_cells = len(self.city_map.available_building_cells())
        open_road_cells = len(self.city_map.available_road_cells())
        land_budget_remaining = open_building_cells * 3 + open_road_cells
        land_total = self.state.land_used + land_budget_remaining
        if self.state.land_total != land_total:
            self.state = self.state.model_copy(update={"land_total": land_total})

    def _apply_action(self, action: ActionName) -> None:
        if action == "do_nothing":
            return
        if action in ACTION_TO_BUILDING:
            building_type = ACTION_TO_BUILDING[action]
            build_fn = BUILD_FUNCTIONS.get(building_type)
            cost = BUILDING_COSTS.get(building_type, 0)
            if build_fn is None:
                return
            if self.state.treasury < cost:
                return
            if not can_spend_treasury(self.state, cost, self.params):
                self.events.append(
                    CityEvent(
                        tick=self.state.tick,
                        message=(
                            f"Skipped {building_type.replace('_', ' ')}: emergency treasury floor of "
                            f"${treasury_emergency_floor(self.params):,.0f} would be breached."
                        ),
                        severity="warning",
                    )
                )
                return
            if not self.city_map.can_place_building_type(building_type):
                self.events.append(
                    CityEvent(
                        tick=self.state.tick,
                        message=f"Skipped {building_type.replace('_', ' ')}: no open map cell is available.",
                        severity="warning",
                    )
                )
                return
            before = self.state
            self.state = build_fn(self.state, self.params)
            if self.state != before:
                self.city_map.place_building_type(building_type)
                self.state = self.state.model_copy(
                    update={"treasury": self.state.treasury - cost}
                )
                self.state = update_supply(self.state, self.params)
                self._sync_land_budget_to_map()
        elif action == "subsidize":
            cost = subsidy_cost(self.state, self.params)
            if can_spend_treasury(self.state, cost, self.params):
                self.state = subsidize(self.state, self.params)

    def _persist_q_agent(self) -> None:
        if self.persist_online_learning:
            self.q_agent.save()

    def _approve_build_action(self, action: str) -> None:
        building_type = ACTION_TO_BUILDING[action]  # type: ignore[index]
        build_fn = BUILD_FUNCTIONS[building_type]  # type: ignore[index]
        cost = BUILDING_COSTS[building_type]  # type: ignore[index]
        label = building_type.replace("_", " ").title()
        if not self.city_map.can_place_building_type(building_type):
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Government could not build {label} because no open map cell is available.",
                    severity="warning",
                )
            )
            return

        if self.state.treasury < cost:
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=f"Government could not build {label} because treasury is too low.",
                    severity="warning",
                )
            )
            return

        if not can_spend_treasury(self.state, cost, self.params):
            self.events.append(
                CityEvent(
                    tick=self.state.tick,
                    message=(
                        f"Government could not build {label} because the "
                        f"${treasury_emergency_floor(self.params):,.0f} emergency floor would be breached."
                    ),
                    severity="warning",
                )
            )
            return

        before = self.state
        self.state = build_fn(self.state, self.params)  # type: ignore[operator]
        self.state = update_supply(self.state, self.params)
        if self.state != before:
            self.city_map.place_building_type(building_type)
            self.state = self.state.model_copy(
                update={"treasury": self.state.treasury - cost}
            )
            self._sync_land_budget_to_map()
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

    def _map_aware_legal_actions(self) -> list[ActionName]:
        legal = legal_actions_for_history(self.state, self.params, self.history)
        return self._map_aware_legal_actions_from(legal)

    def _map_aware_legal_actions_from(
        self, actions: list[ActionName]
    ) -> list[ActionName]:
        legal: list[ActionName] = []
        for action in actions:
            if action in ACTION_TO_BUILDING:
                building_type = ACTION_TO_BUILDING[action]
                if self.city_map.can_place_building_type(building_type):
                    legal.append(action)
                continue
            legal.append(action)
        return legal
