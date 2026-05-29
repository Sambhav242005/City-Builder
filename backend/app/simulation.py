from __future__ import annotations

import random

from .models import (
    BuildingType,
    CityEvent,
    GovernmentRecommendation,
    MayorScore,
    MayorScoreFactor,
    Params,
    StepResult,
    TickSnapshot,
    WorldState,
)


PARAMS = Params()


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def randomized_starting_state(
    rng: random.Random, params: Params = PARAMS, base_state: WorldState | None = None
) -> WorldState:
    state = base_state or WorldState()
    treasury_scale = rng.uniform(
        1 - params.reset_treasury_variance, 1 + params.reset_treasury_variance
    )
    price_scale = rng.uniform(
        1 + params.external_market_shock_min, 1 + params.external_market_shock_max
    )
    return state.model_copy(
        update={
            "treasury": round(state.treasury * treasury_scale, 2),
            "price": round(
                clamp(state.price * price_scale, params.min_price, params.max_price),
                2,
            ),
        }
    )


def update_demand(state: WorldState) -> WorldState:
    return state.model_copy(update={"food_demand": float(state.population)})


def update_supply(state: WorldState, params: Params = PARAMS) -> WorldState:
    supply = state.farms * params.farm_output
    return state.model_copy(update={"food_supply": supply})


def update_price(state: WorldState, params: Params = PARAMS) -> WorldState:
    demand = state.food_demand
    supply = max(state.food_supply, 1.0)
    current_price = state.price
    change = params.alpha * ((demand - supply) / supply) * current_price
    unclamped = current_price + change
    target_price = clamp(unclamped, params.min_price, params.max_price)
    smoothed_price = 0.8 * current_price + 0.2 * target_price
    return state.model_copy(update={"price": smoothed_price})


def update_happiness(state: WorldState) -> WorldState:
    delta = -0.02 if state.price > 15 else 0.01

    # Apply shortage penalty if food supply is severely below demand, or if markets are zero
    if state.markets == 0:
        delta -= 0.05
    elif state.food_supply < state.food_demand * 0.7:
        shortage = (state.food_demand - state.food_supply) / max(state.food_demand, 1.0)
        delta -= 0.04 * shortage

    happiness = clamp(state.happiness + delta, 0.0, 1.0)
    return state.model_copy(update={"happiness": happiness})


def apply_external_market_shock(
    state: WorldState, rng: random.Random, params: Params = PARAMS
) -> tuple[WorldState, list[CityEvent]]:
    if rng.random() >= params.external_market_shock_probability:
        return state, []

    price_scale = rng.uniform(
        1 + params.external_market_shock_min, 1 + params.external_market_shock_max
    )
    shocked_price = round(
        clamp(state.price * price_scale, params.min_price, params.max_price), 2
    )
    if shocked_price == round(state.price, 2):
        return state, []

    direction = "raised" if shocked_price > state.price else "softened"
    next_state = state.model_copy(update={"price": shocked_price})
    return next_state, [
        CityEvent(
            tick=state.tick,
            message=f"External food supply shock {direction} market prices.",
            severity="warning",
        )
    ]


def can_build_farm(state: WorldState, params: Params = PARAMS) -> bool:
    return state.land_used + params.build_cost_land <= state.land_total


def build_farm(state: WorldState, params: Params = PARAMS) -> WorldState:
    if not can_build_farm(state, params):
        return state

    return state.model_copy(
        update={
            "farms": state.farms + 1,
            "land_used": state.land_used + params.build_cost_land,
        }
    )


def close_farm(state: WorldState, params: Params = PARAMS) -> WorldState:
    if state.farms <= 1:
        return state

    return state.model_copy(
        update={
            "farms": state.farms - 1,
            "land_used": max(0, state.land_used - params.build_cost_land),
        }
    )


def subsidize(state: WorldState, params: Params = PARAMS) -> WorldState:
    price = clamp(state.price * 0.9, params.min_price, params.max_price)
    cost = subsidy_cost(state, params)
    if cost <= 0 or state.treasury < cost:
        return state

    return state.model_copy(
        update={
            "price": price,
            "treasury": state.treasury - cost,
        }
    )


def subsidy_cost(state: WorldState, params: Params = PARAMS) -> float:
    subsidized_price = clamp(state.price * 0.9, params.min_price, params.max_price)
    price_support = max(0.0, state.price - subsidized_price)
    return round(price_support * state.food_demand * params.subsidy_spending_scale, 2)


def build_factory(state: WorldState, params: Params = PARAMS) -> WorldState:
    cost = 3  # factories use more land
    if state.land_used + cost > state.land_total:
        return state
    return state.model_copy(
        update={
            "factories": state.factories + 1,
            "land_used": state.land_used + cost,
        }
    )


def build_housing(state: WorldState, params: Params = PARAMS) -> WorldState:
    cost = params.build_cost_land
    if state.land_used + cost > state.land_total:
        return state
    return state.model_copy(
        update={
            "housing": state.housing + 1,
            "land_used": state.land_used + cost,
            "population": state.population + 12,
        }
    )


def build_market(state: WorldState, params: Params = PARAMS) -> WorldState:
    cost = params.build_cost_land
    if state.land_used + cost > state.land_total:
        return state
    return state.model_copy(
        update={
            "markets": state.markets + 1,
            "land_used": state.land_used + cost,
        }
    )


def build_power_plant(state: WorldState, params: Params = PARAMS) -> WorldState:
    cost = 3
    if state.land_used + cost > state.land_total:
        return state
    return state.model_copy(
        update={
            "power_plants": state.power_plants + 1,
            "land_used": state.land_used + cost,
        }
    )


def build_road(state: WorldState, params: Params = PARAMS) -> WorldState:
    cost = 1
    if state.land_used + cost > state.land_total:
        return state
    return state.model_copy(
        update={
            "roads": state.roads + 1,
            "land_used": state.land_used + cost,
        }
    )


BUILD_FUNCTIONS: dict[BuildingType, object] = {
    "farm": build_farm,
    "factory": build_factory,
    "housing": build_housing,
    "market": build_market,
    "power_plant": build_power_plant,
    "road": build_road,
}

BUILDING_COSTS: dict[BuildingType, int] = {
    "farm": 120_000,
    "factory": 200_000,
    "housing": 60_000,
    "market": 80_000,
    "power_plant": 250_000,
    "road": 10_000,
}

TREASURY_RESERVE_MULTIPLIER = 1.5
TREASURY_EMERGENCY_FLOOR_MULTIPLIER = 2 / 3


def treasury_reserve(params: Params = PARAMS) -> float:
    return BUILDING_COSTS["farm"] * TREASURY_RESERVE_MULTIPLIER


def treasury_emergency_floor(params: Params = PARAMS) -> float:
    return BUILDING_COSTS["farm"] * TREASURY_EMERGENCY_FLOOR_MULTIPLIER


def can_spend_treasury(
    state: WorldState,
    cost: float,
    params: Params = PARAMS,
    protect_reserve: bool = True,
) -> bool:
    if cost <= 0:
        return True
    if state.treasury < cost:
        return False
    if not protect_reserve:
        return True
    return state.treasury - cost >= treasury_emergency_floor(params)


def municipal_revenue(state: WorldState, params: Params = PARAMS) -> float:
    civic_base = (
        state.population * 75
        + state.housing * 650
        + state.factories * 1_300
        + state.markets * 1_000
        + state.farms * 250
        + state.power_plants * 400
    )
    operating_cost = (
        state.roads * 150
        + state.farms * 120
        + state.factories * 300
        + state.markets * 180
        + state.power_plants * 500
    )
    return round(max(0.0, civic_base - operating_cost), 2)


def farm_market_capacity(state: WorldState, params: Params = PARAMS) -> float:
    return state.markets * params.market_buy_food_limit


def farm_production_capacity(state: WorldState, params: Params = PARAMS) -> float:
    return state.farms * params.farm_output


def needs_more_farm_capacity(state: WorldState, params: Params = PARAMS) -> bool:
    market_capacity = farm_market_capacity(state, params)
    if market_capacity <= 0:
        return False

    useful_food_capacity = min(
        market_capacity,
        state.food_demand + state.markets * params.export_food_limit,
    )
    return farm_production_capacity(state, params) < useful_food_capacity * 0.95

MAYOR_FACTOR_WEIGHTS = {
    "Food balance": 0.22,
    "Affordability": 0.18,
    "Happiness": 0.20,
    "Land buffer": 0.15,
    "Treasury": 0.15,
}


def company_behavior(
    state: WorldState, rng: random.Random, params: Params = PARAMS
) -> StepResult:
    profit_per_farm = state.price * params.farm_output - params.profit_fixed_cost
    events: list[CityEvent] = []
    next_state = state

    if (
        profit_per_farm > 0
        and needs_more_farm_capacity(state, params)
        and rng.random() < params.company_expand_probability
        and can_build_farm(state, params)
    ):
        next_state = build_farm(state, params)
        events.append(
            CityEvent(
                tick=state.tick,
                message="A private company opened a new farm.",
                severity="success",
            )
        )
    elif (
        profit_per_farm < 0
        and rng.random() < params.company_close_probability
        and state.farms > 1
    ):
        next_state = close_farm(state, params)
        events.append(
            CityEvent(
                tick=state.tick,
                message="A farm closed after running at a loss.",
                severity="warning",
            )
        )

    return StepResult(state=next_state, events=events)


def government_recommendation(
    state: WorldState, params: Params = PARAMS
) -> GovernmentRecommendation:
    shortage = state.food_demand - state.food_supply

    if shortage > 20 and can_build_farm(state, params):
        return GovernmentRecommendation(
            action="build_farm",
            reason="Food demand is materially higher than supply, so adding farm capacity is the safest correction.",
            estimated_happiness_delta=0.08,
            estimated_food_supply_delta=params.farm_output,
            estimated_price_delta=-1.5,
        )

    if state.price > 20:
        return GovernmentRecommendation(
            action="subsidize",
            reason="Food is too expensive for citizens, so a temporary subsidy should reduce price pressure.",
            estimated_happiness_delta=0.04,
            estimated_food_supply_delta=0.0,
            estimated_price_delta=-(state.price * 0.1),
        )

    return GovernmentRecommendation(
        action="do_nothing",
        reason="The food market is within stable bounds. Continue monitoring before intervening.",
    )


def mayor_direction_score(
    state: WorldState,
    history: list[TickSnapshot] | None = None,
    params: Params = PARAMS,
    land_buffer_free: int | None = None,
    land_buffer_capacity: int | None = None,
) -> MayorScore:
    factors = build_mayor_score_factors(
        state,
        params,
        land_buffer_free=land_buffer_free,
        land_buffer_capacity=land_buffer_capacity,
    )
    base_score = mayor_base_score(factors)

    trend = "steady"
    trend_score = 50
    if history:
        previous = history[max(0, len(history) - 6)].state
        previous_factors = build_mayor_score_factors(previous, params)
        previous_score = mayor_base_score(previous_factors)
        delta = base_score - previous_score
        trend_score = round(clamp(50 + delta * 5, 0, 100))
        if delta >= 3:
            trend = "improving"
        elif delta <= -3:
            trend = "declining"

    score = round(base_score + trend_score * 0.10)
    score = int(clamp(score, 0, 100))
    status, label = mayor_score_label(score)
    summary = mayor_score_summary(status, trend, factors)

    return MayorScore(
        score=score,
        status=status,
        label=label,
        trend=trend,
        summary=summary,
        factors=factors,
    )


def mayor_base_score(factors: list[MayorScoreFactor]) -> int:
    return round(
        sum(
            factor.score * MAYOR_FACTOR_WEIGHTS.get(factor.name, 0.0)
            for factor in factors
        )
    )


def build_mayor_score_factors(
    state: WorldState,
    params: Params = PARAMS,
    land_buffer_free: int | None = None,
    land_buffer_capacity: int | None = None,
) -> list[MayorScoreFactor]:
    demand = max(state.food_demand, 1.0)
    food_ratio = state.food_supply / demand
    food_score = int(round(clamp(food_ratio, 0, 1) * 100))

    price_span = max(params.max_price - params.base_price, 1.0)
    affordability_pressure = clamp((state.price - params.base_price) / price_span, 0, 1)
    affordability_score = int(round((1 - affordability_pressure) * 100))

    happiness_score = int(round(clamp(state.happiness, 0, 1) * 100))

    reserve = treasury_reserve(params)
    treasury_target = max(reserve * 2, 1)
    treasury_score = int(round(clamp(state.treasury / treasury_target, 0, 1) * 100))

    land_remaining = (
        max(land_buffer_free, 0)
        if land_buffer_free is not None
        else max(state.land_total - state.land_used, 0)
    )
    land_total = (
        max(land_buffer_capacity or 0, 1)
        if land_buffer_free is not None
        else max(state.land_total, 1)
    )
    land_buffer_ratio = land_remaining / land_total
    land_score = int(round(clamp(land_buffer_ratio / 0.20, 0, 1) * 100))
    land_value = (
        f"{land_remaining} cells"
        if land_buffer_free is not None
        else f"{land_remaining} free"
    )
    land_note = (
        "Open map cells remain for placement."
        if land_score >= 70 and land_buffer_free is not None
        else "Enough land remains for policy moves."
        if land_score >= 70
        else "No open map placement cells remain."
        if land_buffer_free is not None and land_remaining == 0
        else "Limited land makes future fixes harder."
    )

    return [
        MayorScoreFactor(
            name="Food balance",
            value=f"{state.food_supply:.0f} / {state.food_demand:.0f}",
            score=food_score,
            note=(
                "Supply covers demand."
                if food_score >= 95
                else "Food demand is above current supply."
            ),
        ),
        MayorScoreFactor(
            name="Affordability",
            value=f"${state.price:.2f}",
            score=affordability_score,
            note=(
                "Food prices are controlled."
                if affordability_score >= 75
                else "Food prices are pressuring residents."
            ),
        ),
        MayorScoreFactor(
            name="Happiness",
            value=f"{state.happiness * 100:.0f}%",
            score=happiness_score,
            note=(
                "Citizens are broadly satisfied."
                if happiness_score >= 70
                else "Citizen mood needs attention."
            ),
        ),
        MayorScoreFactor(
            name="Land buffer",
            value=land_value,
            score=land_score,
            note=land_note,
        ),
        MayorScoreFactor(
            name="Treasury",
            value=f"${state.treasury:,.0f}",
            score=treasury_score,
            note=(
                "Treasury can fund major construction."
                if treasury_score >= 70
                else "Treasury reserve is protected; major builds are paused."
            ),
        ),
    ]


def mayor_score_label(score: int) -> tuple[str, str]:
    if score >= 80:
        return "strong", "Right Direction"
    if score >= 65:
        return "stable", "Stable"
    if score >= 45:
        return "watch", "Needs Attention"
    return "off_track", "Off Track"


def mayor_score_summary(
    status: str, trend: str, factors: list[MayorScoreFactor]
) -> str:
    weakest = min(factors, key=lambda factor: factor.score)
    if status == "strong":
        return f"Policy direction is strong and {trend}; keep protecting {weakest.name.lower()}."
    if status == "stable":
        return f"The city is stable and {trend}; {weakest.name.lower()} is the next watch point."
    if status == "watch":
        return f"The city needs attention and is {trend}; focus on {weakest.name.lower()}."
    return f"The city is off track and {trend}; urgent action is needed on {weakest.name.lower()}."


def update_market_economy(
    state: WorldState, params: Params = PARAMS
) -> tuple[WorldState, list[CityEvent]]:
    events: list[CityEvent] = []

    # 1. Supply collection from producers
    food_produced = state.farms * params.farm_output
    goods_produced = state.factories * params.factory_output

    food_to_buy = min(state.markets * params.market_buy_food_limit, food_produced)
    goods_to_buy = min(state.markets * params.market_buy_goods_limit, goods_produced)

    # Add to inventory
    new_food_inv = state.market_food_inventory + food_to_buy
    new_goods_inv = state.market_goods_inventory + goods_to_buy

    # 2. Local consumption / buying by citizens
    local_food_demand = float(state.population)
    local_goods_demand = float(state.population) * 0.5

    food_sold_locally = min(local_food_demand, new_food_inv) if state.markets > 0 else 0.0
    goods_sold_locally = min(local_goods_demand, new_goods_inv) if state.markets > 0 else 0.0

    new_food_inv = max(0.0, new_food_inv - food_sold_locally)
    new_goods_inv = max(0.0, new_goods_inv - goods_sold_locally)

    # 3. Export limits (how much other cities can buy)
    export_food_limit = state.markets * params.export_food_limit
    export_goods_limit = state.markets * params.export_goods_limit

    food_exported = min(export_food_limit, new_food_inv) if state.markets > 0 else 0.0
    goods_exported = min(export_goods_limit, new_goods_inv) if state.markets > 0 else 0.0

    new_food_inv = max(0.0, new_food_inv - food_exported)
    new_goods_inv = max(0.0, new_goods_inv - goods_exported)

    # 4. Spoilage and value loss (decay of remaining inventory)
    food_spoiled = new_food_inv * params.food_spoilage_rate
    goods_decayed = new_goods_inv * params.goods_decay_rate

    final_food_inv = max(0.0, new_food_inv - food_spoiled)
    final_goods_inv = max(0.0, new_goods_inv - goods_decayed)

    # 5. Treasury tax collection: market sales plus recurring municipal revenue.
    goods_price = 20.0
    sales_value = (food_sold_locally + food_exported) * state.price + (goods_sold_locally + goods_exported) * goods_price
    tax_collected = sales_value * params.tax_rate + municipal_revenue(state, params)
    new_treasury = state.treasury + tax_collected

    # 6. Citizen satisfaction and shortage warnings
    population = state.population
    if state.markets == 0:
        events.append(
            CityEvent(
                tick=state.tick,
                message="No operational markets! Citizens cannot buy food.",
                severity="danger",
            )
        )
    elif food_sold_locally < local_food_demand:
        starvation_pct = (local_food_demand - food_sold_locally) / local_food_demand
        population_loss = max(1, int(population * starvation_pct * 0.15))
        population = max(0, population - population_loss)
        events.append(
            CityEvent(
                tick=state.tick,
                message=f"Food shortage! Sold only {food_sold_locally:.0f}/{local_food_demand:.0f} food. {population_loss} citizens starved!",
                severity="danger",
            )
        )

    if state.markets > 0:
        if food_produced < food_to_buy:
            events.append(
                CityEvent(
                    tick=state.tick,
                    message="Markets are undersupplied on food. Build more farms!",
                    severity="warning",
                )
            )
        if goods_produced < goods_to_buy:
            events.append(
                CityEvent(
                    tick=state.tick,
                    message="Markets are undersupplied on goods. Build more factories!",
                    severity="warning",
                )
            )

    # Calculate actual food supply for the pricing model (what is actually supplied on the market!)
    actual_supplied_food = food_sold_locally + food_exported

    updated_state = state.model_copy(
        update={
            "market_food_inventory": round(final_food_inv, 2),
            "market_goods_inventory": round(final_goods_inv, 2),
            "tax_revenue_last_tick": round(tax_collected, 2),
            "treasury": round(new_treasury, 2),
            "food_supply": round(actual_supplied_food, 2),
            "food_demand": round(local_food_demand, 2),
            "population": population,
        }
    )

    # 7. Update happiness based on food supply and price
    updated_state = update_happiness(updated_state)

    return updated_state, events


def step(
    state: WorldState, rng: random.Random, params: Params = PARAMS
) -> StepResult:
    # 1. Increment tick and update basic demand
    next_state = state.model_copy(update={"tick": state.tick + 1})
    next_state = update_demand(next_state)

    # 2. Run company behavior (private company actions)
    company_result = company_behavior(next_state, rng, params)
    next_state = company_result.state
    events = list(company_result.events)

    # 3. Run market economy simulation (supply chain, local sales, exports, decay, taxes, happiness)
    next_state, market_events = update_market_economy(next_state, params)
    events.extend(market_events)

    # 4. Update food prices based on the actual supplied food vs demand
    next_state = update_price(next_state, params)
    next_state, shock_events = apply_external_market_shock(next_state, rng, params)
    events.extend(shock_events)

    # 5. Price alerts
    if next_state.price > 15:
        events.append(
            CityEvent(
                tick=next_state.tick,
                message="Food price is too high.",
                severity="danger",
            )
        )

    if next_state.food_demand > next_state.food_supply:
        events.append(
            CityEvent(
                tick=next_state.tick,
                message="Food demand is above current supply.",
                severity="warning",
            )
        )

    return StepResult(state=next_state, events=events)


def run_ticks(
    ticks: int, seed: int = 42, params: Params = PARAMS, state: WorldState | None = None
) -> list[WorldState]:
    rng = random.Random(seed)
    current = state or WorldState()
    states: list[WorldState] = []

    for _ in range(ticks):
        result = step(current, rng, params)
        current = result.state
        states.append(current)

    return states
