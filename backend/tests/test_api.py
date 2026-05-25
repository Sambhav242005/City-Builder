from collections import Counter

from fastapi.testclient import TestClient

from app.main import app, build_cors_origins, service


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
    assert len(payload["mayorScore"]["factors"]) == 4
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
    client.post("/reset")

    payload = client.post("/build", json={"buildingType": "road"}).json()

    assert payload["state"]["roads"] == 5
    assert payload["state"]["treasury"] == 990_000
    assert payload["events"][-1]["message"] == "Built a new Road for $10,000."


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
