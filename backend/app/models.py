from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ActionName = Literal[
    "build_farm",
    "build_factory",
    "build_market",
    "build_power_plant",
    "build_housing",
    "build_road",
    "subsidize",
    "do_nothing",
]
BuildingType = Literal["farm", "factory", "housing", "market", "power_plant", "road"]
EventSeverity = Literal["info", "success", "warning", "danger"]
MayorScoreStatus = Literal["strong", "stable", "watch", "off_track"]
MayorScoreTrend = Literal["improving", "steady", "declining"]
MayorDecisionOutcome = Literal["approved", "rejected"]
DecisionSource = Literal["evolution_optimizer", "rule_fallback"]
OptimizerVerdict = Literal["right", "watch", "wrong", "unavailable"]
TraceStatus = Literal["positive", "neutral", "negative", "warning"]
RoadDirection = Literal["n", "e", "s", "w"]
RoadType = Literal["end", "straight", "corner", "t", "cross"]
BuildingScale = Literal["single", "merged", "maximum", "landmark"]
MapTileKind = Literal[
    "water",
    "road",
    "residential",
    "farm",
    "factory",
    "market",
    "government",
    "park",
    "power_plant",
    "empty",
]


class Params(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_price: float = 10.0
    alpha: float = 0.1
    min_price: float = 2.0
    max_price: float = 50.0
    farm_output: float = 10.0
    factory_output: float = 12.0  # Enabled factory goods production
    build_cost_land: int = 2
    max_build_per_tick: int = 2
    profit_fixed_cost: float = 20.0
    subsidy_spending_scale: float = 100.0
    company_expand_probability: float = 0.6
    company_close_probability: float = 0.3
    history_limit: int = 240

    # New Economic Simulation parameters
    market_buy_food_limit: float = 30.0
    market_buy_goods_limit: float = 15.0
    export_food_limit: float = 16.0
    export_goods_limit: float = 8.0
    food_spoilage_rate: float = 0.15
    goods_decay_rate: float = 0.05
    tax_rate: float = 0.10
    reset_treasury_variance: float = 0.10
    external_market_shock_probability: float = 0.18
    external_market_shock_min: float = -0.08
    external_market_shock_max: float = 0.10
    market_action_cooldown_ticks: int = 3


class WorldState(BaseModel):
    tick: int = 0
    population: int = 100
    food_supply: float = 80.0
    food_demand: float = 100.0
    price: float = 10.0
    land_total: int = 100
    land_used: int = 60
    farms: int = 8
    factories: int = 4
    housing: int = 6
    markets: int = 2
    parks: int = 2
    power_plants: int = 1
    roads: int = 4
    happiness: float = 0.7
    treasury: float = 1_000_000.0

    # New Economic Simulation tracking states
    market_food_inventory: float = 20.0
    market_goods_inventory: float = 10.0
    tax_revenue_last_tick: float = 0.0


class GovernmentRecommendation(BaseModel):
    action: ActionName
    reason: str
    estimated_happiness_delta: float = 0.0
    estimated_food_supply_delta: float = 0.0
    estimated_price_delta: float = 0.0


class OptimizerInspection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    verdict: OptimizerVerdict = "unavailable"
    reason: str = "Optimizer has not reviewed this policy decision yet."
    risk_flags: list[str] = Field(default_factory=list, alias="riskFlags")
    suggested_action: ActionName | None = Field(default=None, alias="suggestedAction")
    override_applied: bool = Field(default=False, alias="overrideApplied")
    original_action: ActionName | None = Field(default=None, alias="originalAction")
    final_action: ActionName | None = Field(default=None, alias="finalAction")
    fitness_delta: float = Field(default=0.0, alias="fitnessDelta")


class DecisionInputSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tick: int = 0
    population: int = 0
    food_supply: float = Field(default=0.0, alias="foodSupply")
    food_demand: float = Field(default=0.0, alias="foodDemand")
    price: float = 0.0
    happiness: float = 0.0
    treasury: float = 0.0
    land_used: int = Field(default=0, alias="landUsed")
    land_total: int = Field(default=0, alias="landTotal")
    roads: int = 0
    power_plants: int = Field(default=0, alias="powerPlants")
    recent_actions: list[ActionName] = Field(default_factory=list, alias="recentActions")


class PolicyNodeTrace(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    label: str
    previous_value: float | None = Field(default=None, alias="previousValue")
    current_value: float = Field(alias="currentValue")
    delta: float = 0.0
    status: TraceStatus = "neutral"
    note: str = ""


class CandidateActionTrace(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action: ActionName
    rank: int
    legal: bool = True
    selected: bool = False
    policy_score: float = Field(default=0.0, alias="policyScore")
    optimizer_score: float = Field(default=0.0, alias="optimizerScore")
    expected_happiness_delta: float = Field(default=0.0, alias="expectedHappinessDelta")
    expected_food_supply_delta: float = Field(default=0.0, alias="expectedFoodSupplyDelta")
    expected_price_delta: float = Field(default=0.0, alias="expectedPriceDelta")
    reward_signals: dict[str, float] = Field(default_factory=dict, alias="rewardSignals")
    risk_flags: list[str] = Field(default_factory=list, alias="riskFlags")
    note: str = ""


class DecisionOutputSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action: ActionName = "do_nothing"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    value_estimate: float = Field(default=0.0, alias="valueEstimate")
    expected_happiness_delta: float = Field(default=0.0, alias="expectedHappinessDelta")
    expected_food_supply_delta: float = Field(default=0.0, alias="expectedFoodSupplyDelta")
    expected_price_delta: float = Field(default=0.0, alias="expectedPriceDelta")
    reason: str = ""


class DecisionSystemStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source: DecisionSource = "evolution_optimizer"
    policy_version: str = Field(default="city-evolution-optimizer-v1", alias="policyVersion")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    value_estimate: float = Field(default=0.0, alias="valueEstimate")
    legal_actions: list[ActionName] = Field(default_factory=list, alias="legalActions")
    risk_flags: list[str] = Field(default_factory=list, alias="riskFlags")
    reward_signals: dict[str, float] = Field(default_factory=dict, alias="rewardSignals")
    optimizer: OptimizerInspection = Field(default_factory=OptimizerInspection)
    input_summary: DecisionInputSummary = Field(default_factory=DecisionInputSummary, alias="inputSummary")
    nodes: list[PolicyNodeTrace] = Field(default_factory=list)
    candidates: list[CandidateActionTrace] = Field(default_factory=list)
    output_summary: DecisionOutputSummary = Field(default_factory=DecisionOutputSummary, alias="outputSummary")


class OptimizerCandidateScore(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action: ActionName
    q_score: float = Field(alias="qScore")
    risk_flags: list[str] = Field(default_factory=list, alias="riskFlags")
    rollout_score: float = Field(alias="rolloutScore")
    validation_score: float = Field(alias="validationScore")


class OptimizerTrainingScenario(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    baseline_action: ActionName = Field(alias="baselineAction")
    candidate_scores: list[OptimizerCandidateScore] = Field(alias="candidateScores")
    confidence: float = Field(ge=0.0, le=1.0)
    description: str
    expected_actions: list[ActionName] = Field(alias="expectedActions")
    name: str
    passed: bool
    q_margin_vs_baseline: float = Field(alias="qMarginVsBaseline")
    selected_action: ActionName = Field(alias="selectedAction")
    state_key: str = Field(alias="stateKey")
    validation_margin_vs_baseline: float = Field(alias="validationMarginVsBaseline")


class OptimizerTrainingSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    all_scenarios_passed: bool = Field(alias="allScenariosPassed")
    average_episode_reward: float = Field(alias="averageEpisodeReward")
    states_learned: int = Field(alias="statesLearned")
    validation_scenarios: int = Field(alias="validationScenarios")
    validation_scenarios_passed: int = Field(alias="validationScenariosPassed")


class OptimizerTrainingConfig(BaseModel):
    alpha: float
    environment: str
    episodes: int
    epsilon: float
    epsilon_decay: float = Field(alias="epsilonDecay")
    epsilon_min: float = Field(alias="epsilonMin")
    external_market_shock_probability: float = Field(
        alias="externalMarketShockProbability"
    )
    gamma: float
    happiness_floor: float = Field(alias="happinessFloor")
    market_action_cooldown_ticks: int = Field(alias="marketActionCooldownTicks")
    reset_treasury_variance: float = Field(alias="resetTreasuryVariance")
    rollout_horizon: int = Field(alias="rolloutHorizon")
    scenario_rollouts: int = Field(alias="scenarioRollouts")
    seed: int
    steps_per_episode: int = Field(alias="stepsPerEpisode")


class OptimizerTrainingReport(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    generated_at: str = Field(alias="generatedAt")
    policy_version: str = Field(alias="policyVersion")
    scenarios: list[OptimizerTrainingScenario]
    summary: OptimizerTrainingSummary
    training: OptimizerTrainingConfig


class CityEvent(BaseModel):
    tick: int
    message: str
    severity: EventSeverity = "info"


class MayorScoreFactor(BaseModel):
    name: str
    value: str
    score: int = Field(ge=0, le=100)
    note: str


class MayorScore(BaseModel):
    score: int = Field(ge=0, le=100)
    status: MayorScoreStatus
    label: str
    trend: MayorScoreTrend
    summary: str
    factors: list[MayorScoreFactor]


class DecisionMetricSnapshot(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    food_balance: float = Field(alias="foodBalance")
    price: float
    happiness: float
    mayor_score: int = Field(alias="mayorScore", ge=0, le=100)


class DecisionImpact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    food_balance_delta: float = Field(alias="foodBalanceDelta")
    price_delta: float = Field(alias="priceDelta")
    happiness_delta: float = Field(alias="happinessDelta")
    mayor_score_delta: int = Field(alias="mayorScoreDelta")


class MayorDecisionScorecardEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    tick: int
    action: ActionName
    decision: MayorDecisionOutcome
    reason: str
    before: DecisionMetricSnapshot
    after: DecisionMetricSnapshot | None = None
    impact: DecisionImpact | None = None
    next_tick: int | None = Field(default=None, alias="nextTick")


class MapBuilding(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    kind: MapTileKind
    label: str
    x: int
    y: int
    width: int
    height: int
    units: int
    max_units: int = Field(alias="maxUnits")
    level: int = 1
    scale: BuildingScale = "single"
    workers: int = 0
    output: float = 0.0
    income: float = 0.0
    pollution: float = 0.0
    status: str = "Operating"
    asset_key: str = Field(default="", alias="assetKey")


class MapTile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    x: int
    y: int
    kind: MapTileKind
    label: str
    active: bool = True
    zone: MapTileKind | None = None
    road_type: RoadType | None = Field(default=None, alias="roadType")
    road_connections: list[RoadDirection] = Field(default_factory=list, alias="roadConnections")
    building_id: str | None = Field(default=None, alias="buildingId")
    lot_id: str | None = Field(default=None, alias="lotId")
    is_anchor: bool = Field(default=False, alias="isAnchor")


class CityMapLayout(BaseModel):
    width: int
    height: int
    tiles: list[MapTile]
    buildings: list[MapBuilding] = Field(default_factory=list)


class BuildAvailability(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    can_build: bool = Field(alias="canBuild")
    reason: str
    open_cells: int = Field(default=0, alias="openCells")
    treasury_required: int = Field(default=0, alias="treasuryRequired")
    land_required: int = Field(default=0, alias="landRequired")


class TickSnapshot(BaseModel):
    state: WorldState
    recommendation: GovernmentRecommendation


class SimulationControls(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    running: bool = False
    terminal_reached: bool = Field(default=False, alias="terminalReached")
    pause_reason: str | None = Field(default=None, alias="pauseReason")
    max_days: int = Field(default=100, ge=1, alias="maxDays")
    live_tick_interval_seconds: float = Field(
        default=0.35,
        gt=0,
        alias="liveTickIntervalSeconds",
    )
    fast_forward_ticks: int = Field(default=5, ge=1, le=50, alias="fastForwardTicks")


class StateResponse(BaseModel):
    state: WorldState
    params: Params
    recommendation: GovernmentRecommendation
    decision_system: DecisionSystemStatus = Field(alias="decisionSystem")
    mayor_score: MayorScore = Field(alias="mayorScore")
    decision_scorecard: list[MayorDecisionScorecardEntry] = Field(
        default_factory=list, alias="decisionScorecard"
    )
    city_map: CityMapLayout = Field(alias="cityMap")
    build_availability: dict[BuildingType, BuildAvailability] = Field(
        default_factory=dict, alias="buildAvailability"
    )
    history: list[TickSnapshot] = Field(default_factory=list)
    events: list[CityEvent] = Field(default_factory=list)
    simulation: SimulationControls


class StepResult(BaseModel):
    state: WorldState
    events: list[CityEvent] = Field(default_factory=list)


class BuildRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    building_type: BuildingType = Field(alias="buildingType")


class AdvanceRequest(BaseModel):
    ticks: int = Field(default=5, ge=1, le=50)
