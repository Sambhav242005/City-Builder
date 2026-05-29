from collections import Counter

from fastapi.testclient import TestClient

from app.city_map import PersistentCityMap
from app.main import app, build_cors_origins, service
from app.models import GovernmentRecommendation, Params, WorldState
from app.service import CitySimulationService
from app.simulation import treasury_emergency_floor


RECOMMENDATION_ACTIONS = {
    "build_farm",
    "build_factory",
    "build_market",
    "build_power_plant",
    "build_housing",
    "build_road",
    "subsidize",
    "do_nothing",
}


def test_state_tick_reset_flow():
    client = TestClient(app)

    reset = client.post("/reset")
    assert reset.status_code == 200
    assert reset.json()["state"]["tick"] == 0
    assert reset.json()["simulation"]["running"] is False
    assert reset.json()["simulation"]["fastForwardTicks"] == 5

    tick = client.post("/tick")
    assert tick.status_code == 200
    payload = tick.json()
    assert payload["state"]["tick"] == 1
    assert payload["simulation"]["running"] is False
    assert payload["state"]["treasury"] >= 0
    assert len(payload["history"]) >= 2
    assert payload["cityMap"]["width"] == 14
    assert payload["cityMap"]["height"] == 9
    assert len(payload["cityMap"]["tiles"]) == 126
    assert payload["mayorScore"]["score"] >= 0
    assert payload["mayorScore"]["label"]
    assert [factor["name"] for factor in payload["mayorScore"]["factors"]] == [
        "Food balance",
        "Affordability",
        "Happiness",
        "Land buffer",
        "Treasury",
    ]
    assert "agent" not in payload
    assert "agentRateLimit" not in payload
    assert payload["recommendation"]["action"] in RECOMMENDATION_ACTIONS
    assert payload["decisionSystem"]["source"] in {"evolution_optimizer", "rule_fallback"}
    assert payload["decisionSystem"]["optimizer"]["verdict"] in {
        "right",
        "watch",
        "wrong",
        "unavailable",
    }
    assert payload["decisionScorecard"] == []
    assert payload["decisionSystem"]["inputSummary"]["foodSupply"] >= 0
    assert payload["decisionSystem"]["nodes"]
    assert payload["decisionSystem"]["candidates"]
    assert payload["decisionSystem"]["outputSummary"]["action"] in RECOMMENDATION_ACTIONS


def test_optimizer_training_report_endpoint_exposes_checked_in_validation():
    client = TestClient(app)

    response = client.get("/optimizer/training-report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["policyVersion"] == "q-learning-city-v1-offline"
    assert payload["summary"]["allScenariosPassed"] is True
    assert payload["summary"]["validationScenariosPassed"] == payload["summary"]["validationScenarios"]
    assert len(payload["scenarios"]) == payload["summary"]["validationScenarios"]

    first_scenario = payload["scenarios"][0]
    assert first_scenario["name"]
    assert first_scenario["passed"] is True
    assert first_scenario["selectedAction"] in RECOMMENDATION_ACTIONS
    assert first_scenario["baselineAction"] in RECOMMENDATION_ACTIONS
    assert 0 <= first_scenario["confidence"] <= 1
    assert first_scenario["candidateScores"]


def test_cors_origins_include_extra_deploy_origins_once():
    origins = build_cors_origins(
        "http://192.168.1.5:5173, http://localhost:5173, http://example.test"
    )

    assert "http://127.0.0.1:5173" in origins
    assert origins.count("http://localhost:5173") == 1
    assert "http://192.168.1.5:5173" in origins
    assert "http://example.test" in origins


def test_city_map_reflects_simulation_counts():
    client = TestClient(app)
    client.post("/reset")

    payload = client.get("/state").json()
    units_by_kind = Counter()
    footprint_by_kind = Counter()

    for building in payload["cityMap"]["buildings"]:
        units_by_kind[building["kind"]] += building["units"]
        footprint_by_kind[building["kind"]] += building["width"] * building["height"]

    assert units_by_kind["farm"] == payload["state"]["farms"]
    assert units_by_kind["factory"] == payload["state"]["factories"]
    assert footprint_by_kind["farm"] > 0
    assert footprint_by_kind["factory"] > 0


def test_manual_build_spends_treasury():
    client = TestClient(app)
    reset_payload = client.post("/reset").json()
    starting_treasury = reset_payload["state"]["treasury"]

    payload = client.post("/build", json={"buildingType": "road"}).json()

    assert payload["state"]["roads"] == 5
    assert payload["state"]["treasury"] == round(starting_treasury - 10_000, 2)
    assert payload["events"][-1]["message"] == "Built a new Road for $10,000."


def test_manual_build_adds_stable_map_placement_without_moving_existing_buildings():
    client = TestClient(app)
    reset_payload = client.post("/reset").json()
    before_positions = {
        building["id"]: (building["x"], building["y"])
        for building in reset_payload["cityMap"]["buildings"]
    }

    payload = client.post("/build", json={"buildingType": "farm"}).json()
    after_positions = {
        building["id"]: (building["x"], building["y"])
        for building in payload["cityMap"]["buildings"]
    }

    assert payload["state"]["farms"] == reset_payload["state"]["farms"] + 1
    assert len(after_positions) == len(before_positions) + 1
    for building_id, position in before_positions.items():
        assert after_positions[building_id] == position
    assert len(set(after_positions.values())) == len(after_positions)


def test_manual_build_reports_no_open_cell_without_changing_state():
    simulation = CitySimulationService(seed=7)
    simulation.state = WorldState(
        farms=0,
        factories=0,
        housing=0,
        markets=0,
        parks=0,
        power_plants=0,
        roads=4,
        land_used=0,
        land_total=200,
        treasury=5_000_000,
    )
    simulation.city_map = PersistentCityMap.from_state(simulation.state)
    while simulation.city_map.place_building_type("farm"):
        pass

    snapshot = simulation.snapshot()
    assert snapshot.build_availability["farm"].can_build is False
    assert snapshot.build_availability["farm"].reason == "No open map cell is available."

    payload = simulation.build_structure("farm")

    assert payload.state.farms == 0
    assert payload.events[-1].message == "Cannot build Farm: no open map cell is available."


def test_land_buffer_and_manual_build_use_open_map_cells_when_budget_is_full():
    simulation = CitySimulationService(seed=13)
    simulation.state = WorldState(
        land_used=100,
        land_total=100,
        treasury=5_000_000,
    )
    simulation.city_map = PersistentCityMap.from_state(simulation.state)
    before_farms = simulation.state.farms

    snapshot = simulation.snapshot()
    land_factor = next(
        factor for factor in snapshot.mayor_score.factors if factor.name == "Land buffer"
    )

    assert snapshot.build_availability["farm"].open_cells > 0
    assert snapshot.build_availability["farm"].can_build is True
    assert land_factor.value != "0 free"
    assert land_factor.value.endswith("cells")
    assert land_factor.score > 0

    payload = simulation.build_structure("farm")

    assert payload.state.farms == before_farms + 1
    assert payload.events[-1].message == "Built a new Farm for $120,000."


def test_dashboard_optimizer_keeps_funded_actions_after_long_run():
    simulation = CitySimulationService(seed=2)

    assert simulation.q_agent.training_enabled is False

    for _ in range(72):
        simulation.tick()

    assert simulation.state.treasury >= treasury_emergency_floor(simulation.params)
    assert simulation.state.farms < 30
    assert any(
        action != "do_nothing"
        for action in simulation.snapshot().decision_system.legal_actions
    )
    assert simulation.snapshot().recommendation.action != "do_nothing"


def test_build_availability_blocks_emergency_floor_breaching_spend():
    simulation = CitySimulationService(seed=5)
    floor = treasury_emergency_floor(simulation.params)
    simulation.state = WorldState(
        treasury=floor + 5_000,
        land_used=60,
        land_total=200,
    )
    simulation.city_map = PersistentCityMap.from_state(simulation.state)

    payload = simulation.snapshot()

    assert payload.build_availability["road"].can_build is False
    assert "emergency floor" in payload.build_availability["road"].reason.lower()


def test_terminal_state_does_not_pause_the_dashboard_simulation():
    simulation = CitySimulationService(
        seed=11,
        params=Params(
            company_expand_probability=0.0,
            external_market_shock_probability=0.0,
        ),
    )
    simulation.q_agent.training_enabled = False
    simulation.recommendation = GovernmentRecommendation(
        action="do_nothing",
        reason="Test keeps optimizer from adding a building during terminal check.",
    )
    simulation.state = WorldState(
        tick=21,
        population=120,
        food_supply=150.0,
        food_demand=120.0,
        land_total=100,
        land_used=90,
        treasury=0,
    )
    simulation.city_map = PersistentCityMap.from_state(simulation.state)
    simulation.live_running = True

    before_positions = {
        building.id: (building.kind, building.x, building.y, building.units)
        for building in simulation.snapshot().city_map.buildings
    }

    payload = simulation.tick()

    after_positions = {
        building.id: (building.kind, building.x, building.y, building.units)
        for building in payload.city_map.buildings
    }
    assert payload.state.tick == 22
    assert payload.simulation.running is True
    assert payload.simulation.terminal_reached is False
    assert payload.simulation.pause_reason is None
    assert before_positions == after_positions
    assert not any("Terminal state reached" in event.message for event in payload.events)


def test_reset_randomizes_starting_treasury_within_configured_bounds():
    client = TestClient(app)

    first = client.post("/reset").json()["state"]["treasury"]
    second = client.post("/reset").json()["state"]["treasury"]

    assert 900_000 <= first <= 1_100_000
    assert 900_000 <= second <= 1_100_000
    assert first != second


def test_government_approve_and_reject_flow():
    client = TestClient(app)
    client.post("/reset")

    approved = client.post("/government/approve")
    assert approved.status_code == 200
    approved_payload = approved.json()
    assert "events" in approved_payload
    assert approved_payload["decisionScorecard"][-1]["decision"] == "approved"
    assert approved_payload["decisionScorecard"][-1]["impact"] is None

    resolved = client.post("/tick").json()
    approved_entry = resolved["decisionScorecard"][-1]
    assert approved_entry["nextTick"] == resolved["state"]["tick"]
    assert approved_entry["after"] is not None
    assert set(approved_entry["impact"]) == {
        "foodBalanceDelta",
        "priceDelta",
        "happinessDelta",
        "mayorScoreDelta",
    }

    rejected = client.post("/government/reject")
    assert rejected.status_code == 200
    rejected_payload = rejected.json()
    assert rejected_payload["events"][-1]["message"].startswith("Government rejected")
    assert rejected_payload["decisionScorecard"][-1]["decision"] == "rejected"
    assert rejected_payload["decisionScorecard"][-1]["impact"] is None


def test_external_agent_endpoints_are_removed():
    client = TestClient(app)

    assert client.get("/agent/config").status_code == 404
    assert client.post("/agent/config", json={}).status_code == 404
    assert client.post("/agent/inspection").status_code == 404
    assert client.post("/agent/recommendation").status_code == 404


def test_tick_advances_exactly_one_step_and_preserves_live_state():
    client = TestClient(app)
    client.post("/reset")
    client.post("/live/play")

    before = client.get("/state").json()
    payload = client.post("/tick").json()

    assert payload["state"]["tick"] == before["state"]["tick"] + 1
    assert payload["simulation"]["running"] is True


def test_advance_runs_multiple_ticks_without_enabling_live_mode():
    client = TestClient(app)
    client.post("/reset")

    before = client.get("/state").json()
    payload = client.post("/advance", json={"ticks": 4}).json()

    assert payload["state"]["tick"] == before["state"]["tick"] + 4
    assert payload["simulation"]["running"] is False


def test_live_play_pause_is_backend_driven_and_optimizer_independent():
    client = TestClient(app)
    client.post("/reset")

    original_training_enabled = service.q_agent.training_enabled
    service.q_agent.training_enabled = False

    try:
        play_payload = client.post("/live/play").json()
        assert play_payload["simulation"]["running"] is True
        assert (
            play_payload["simulation"]["liveTickIntervalSeconds"]
            == service.LIVE_TICK_INTERVAL_SECONDS
        )

        with client.websocket_connect("/live") as websocket:
            payload = websocket.receive_json()

        assert payload["state"]["tick"] == 1
        assert payload["simulation"]["running"] is True
        assert "history" in payload
        assert "cityMap" in payload
        assert "mayorScore" in payload
        assert "decisionScorecard" in payload
        assert "decisionSystem" in payload
        assert "agent" not in payload
        assert "agentRateLimit" not in payload
        assert payload["decisionSystem"]["optimizer"]["verdict"] in {
            "right",
            "watch",
            "wrong",
            "unavailable",
        }
        assert payload["recommendation"]["action"] in RECOMMENDATION_ACTIONS

        paused = client.post("/live/pause").json()
        assert paused["simulation"]["running"] is False

        with client.websocket_connect("/live") as websocket:
            paused_payload = websocket.receive_json()

        assert paused_payload["state"]["tick"] == paused["state"]["tick"]
        assert paused_payload["simulation"]["running"] is False
    finally:
        service.q_agent.training_enabled = original_training_enabled
        client.post("/live/pause")
