import random

from app.models import Params, WorldState
from app.simulation import (
    build_farm,
    can_spend_treasury,
    company_behavior,
    mayor_direction_score,
    municipal_revenue,
    run_ticks,
    step,
    subsidize,
    treasury_emergency_floor,
    update_happiness,
    update_price,
)


def test_price_smooths_upward_during_shortage_and_respects_cap():
    state = WorldState(food_demand=200, food_supply=20, price=49)

    updated = update_price(state)

    assert updated.price > state.price
    assert updated.price <= Params().max_price


def test_price_smooths_downward_during_surplus_and_respects_floor():
    state = WorldState(food_demand=10, food_supply=1_000, price=2.1)

    updated = update_price(state)

    assert updated.price < state.price
    assert updated.price >= Params().min_price


def test_happiness_stays_inside_bounds():
    low = WorldState(price=25, happiness=0.01)
    high = WorldState(price=10, happiness=0.99)

    for _ in range(10):
        low = update_happiness(low)
        high = update_happiness(high)

    assert low.happiness == 0
    assert high.happiness == 1


def test_build_farm_respects_land_limit():
    state = WorldState(land_total=100, land_used=100, farms=20)

    updated = build_farm(state)

    assert updated.farms == state.farms
    assert updated.land_used == state.land_used


def test_private_farms_do_not_expand_when_markets_are_saturated():
    params = Params(company_expand_probability=1.0)
    saturated = WorldState(
        farms=10,
        markets=1,
        food_demand=120,
        price=10,
        land_total=200,
        land_used=60,
    )
    hungry = saturated.model_copy(update={"farms": 1, "markets": 3})

    saturated_result = company_behavior(saturated, random.Random(1), params)
    hungry_result = company_behavior(hungry, random.Random(1), params)

    assert saturated_result.state.farms == saturated.farms
    assert saturated_result.events == []
    assert hungry_result.state.farms == hungry.farms + 1


def test_treasury_spending_protects_emergency_reserve():
    params = Params()
    floor = treasury_emergency_floor(params)
    state = WorldState(treasury=floor + 10_000)

    assert can_spend_treasury(state, 10_000, params)
    assert not can_spend_treasury(state, 10_001, params)


def test_municipal_revenue_lets_treasury_recover_after_reserve_pause():
    state = WorldState(
        population=70,
        farms=8,
        factories=4,
        housing=6,
        markets=2,
        power_plants=1,
        roads=4,
    )

    assert municipal_revenue(state) >= 10_000


def test_subsidize_reduces_price_without_breaking_floor():
    state = WorldState(price=20, food_demand=100, treasury=50_000)
    floor_state = WorldState(price=2)

    subsidized = subsidize(state)

    assert subsidized.price == 18
    assert subsidized.treasury == 30_000
    assert subsidize(floor_state).price == 2


def test_seeded_runs_are_reproducible():
    first = [state.model_dump() for state in run_ticks(40, seed=123)]
    second = [state.model_dump() for state in run_ticks(40, seed=123)]

    assert first == second


def test_step_stabilizes_without_exploding():
    rng = random.Random(42)
    state = WorldState()

    for _ in range(200):
        result = step(state, rng)
        state = result.state

    assert Params().min_price <= state.price <= Params().max_price
    assert 0 <= state.happiness <= 1
    assert state.land_used <= state.land_total
    assert state.farms >= 1


def test_mayor_direction_score_reflects_city_health():
    healthy = WorldState(
        food_supply=130,
        food_demand=100,
        price=9,
        happiness=0.9,
        land_total=100,
        land_used=60,
    )
    strained = WorldState(
        food_supply=35,
        food_demand=140,
        price=35,
        happiness=0.3,
        land_total=100,
        land_used=98,
    )

    healthy_score = mayor_direction_score(healthy)
    strained_score = mayor_direction_score(strained)

    assert healthy_score.score > strained_score.score
    assert healthy_score.status in {"strong", "stable"}
    assert strained_score.status in {"watch", "off_track"}
    assert [factor.name for factor in healthy_score.factors] == [
        "Food balance",
        "Affordability",
        "Happiness",
        "Land buffer",
        "Treasury",
    ]
