export type ActionName =
  | "build_farm"
  | "build_factory"
  | "build_market"
  | "build_power_plant"
  | "build_housing"
  | "build_road"
  | "subsidize"
  | "do_nothing";
export type BuildingType = "farm" | "factory" | "housing" | "market" | "power_plant" | "road";
export type EventSeverity = "info" | "success" | "warning" | "danger";
export type MayorScoreStatus = "strong" | "stable" | "watch" | "off_track";
export type MayorScoreTrend = "improving" | "steady" | "declining";
export type MayorDecisionOutcome = "approved" | "rejected";
export type DecisionSource = "evolution_optimizer" | "rule_fallback";
export type OptimizerVerdict = "right" | "watch" | "wrong" | "unavailable";
export type TraceStatus = "positive" | "neutral" | "negative" | "warning";
export type RoadDirection = "n" | "e" | "s" | "w";
export type RoadType = "end" | "straight" | "corner" | "t" | "cross";
export type BuildingScale = "single" | "merged" | "maximum" | "landmark";
export type MapTileKind =
  | "water"
  | "road"
  | "residential"
  | "farm"
  | "factory"
  | "market"
  | "government"
  | "park"
  | "power_plant"
  | "empty";

export interface Params {
  base_price: number;
  alpha: number;
  min_price: number;
  max_price: number;
  farm_output: number;
  factory_output: number;
  build_cost_land: number;
  max_build_per_tick: number;
  profit_fixed_cost: number;
  subsidy_spending_scale: number;
  company_expand_probability: number;
  company_close_probability: number;
  history_limit: number;
  market_buy_food_limit: number;
  market_buy_goods_limit: number;
  export_food_limit: number;
  export_goods_limit: number;
  food_spoilage_rate: number;
  goods_decay_rate: number;
  tax_rate: number;
}

export interface WorldState {
  tick: number;
  population: number;
  food_supply: number;
  food_demand: number;
  price: number;
  land_total: number;
  land_used: number;
  farms: number;
  factories: number;
  housing: number;
  markets: number;
  parks: number;
  power_plants: number;
  roads: number;
  happiness: number;
  treasury: number;
  market_food_inventory: number;
  market_goods_inventory: number;
  tax_revenue_last_tick: number;
}

export interface GovernmentRecommendation {
  action: ActionName;
  reason: string;
  estimated_happiness_delta: number;
  estimated_food_supply_delta: number;
  estimated_price_delta: number;
}

export interface OptimizerInspection {
  verdict: OptimizerVerdict;
  reason: string;
  riskFlags: string[];
  suggestedAction?: ActionName | null;
  overrideApplied: boolean;
  originalAction?: ActionName | null;
  finalAction?: ActionName | null;
  fitnessDelta: number;
}

export interface DecisionInputSummary {
  tick: number;
  population: number;
  foodSupply: number;
  foodDemand: number;
  price: number;
  happiness: number;
  treasury: number;
  landUsed: number;
  landTotal: number;
  roads: number;
  powerPlants: number;
  recentActions: ActionName[];
}

export interface PolicyNodeTrace {
  key: string;
  label: string;
  previousValue?: number | null;
  currentValue: number;
  delta: number;
  status: TraceStatus;
  note: string;
}

export interface CandidateActionTrace {
  action: ActionName;
  rank: number;
  legal: boolean;
  selected: boolean;
  policyScore: number;
  optimizerScore: number;
  expectedHappinessDelta: number;
  expectedFoodSupplyDelta: number;
  expectedPriceDelta: number;
  rewardSignals: Record<string, number>;
  riskFlags: string[];
  note: string;
}

export interface DecisionOutputSummary {
  action: ActionName;
  confidence: number;
  valueEstimate: number;
  expectedHappinessDelta: number;
  expectedFoodSupplyDelta: number;
  expectedPriceDelta: number;
  reason: string;
}

export interface DecisionSystemStatus {
  source: DecisionSource;
  policyVersion: string;
  confidence: number;
  valueEstimate: number;
  legalActions: ActionName[];
  riskFlags: string[];
  rewardSignals: Record<string, number>;
  optimizer: OptimizerInspection;
  inputSummary: DecisionInputSummary;
  nodes: PolicyNodeTrace[];
  candidates: CandidateActionTrace[];
  outputSummary: DecisionOutputSummary;
}

export interface OptimizerCandidateScore {
  action: ActionName;
  qScore: number;
  riskFlags: string[];
  rolloutScore: number;
  validationScore: number;
}

export interface OptimizerTrainingScenario {
  baselineAction: ActionName;
  candidateScores: OptimizerCandidateScore[];
  confidence: number;
  description: string;
  expectedActions: ActionName[];
  name: string;
  passed: boolean;
  qMarginVsBaseline: number;
  selectedAction: ActionName;
  stateKey: string;
  validationMarginVsBaseline: number;
}

export interface OptimizerTrainingSummary {
  allScenariosPassed: boolean;
  averageEpisodeReward: number;
  statesLearned: number;
  validationScenarios: number;
  validationScenariosPassed: number;
}

export interface OptimizerTrainingConfig {
  alpha: number;
  environment: string;
  episodes: number;
  epsilon: number;
  epsilonDecay: number;
  epsilonMin: number;
  gamma: number;
  rolloutHorizon: number;
  scenarioRollouts: number;
  seed: number;
  stepsPerEpisode: number;
}

export interface OptimizerTrainingReport {
  generatedAt: string;
  policyVersion: string;
  scenarios: OptimizerTrainingScenario[];
  summary: OptimizerTrainingSummary;
  training: OptimizerTrainingConfig;
}

export interface CityEvent {
  tick: number;
  message: string;
  severity: EventSeverity;
}

export interface MayorScoreFactor {
  name: string;
  value: string;
  score: number;
  note: string;
}

export interface MayorScore {
  score: number;
  status: MayorScoreStatus;
  label: string;
  trend: MayorScoreTrend;
  summary: string;
  factors: MayorScoreFactor[];
}

export interface DecisionMetricSnapshot {
  foodBalance: number;
  price: number;
  happiness: number;
  mayorScore: number;
}

export interface DecisionImpact {
  foodBalanceDelta: number;
  priceDelta: number;
  happinessDelta: number;
  mayorScoreDelta: number;
}

export interface MayorDecisionScorecardEntry {
  id: string;
  tick: number;
  action: ActionName;
  decision: MayorDecisionOutcome;
  reason: string;
  before: DecisionMetricSnapshot;
  after?: DecisionMetricSnapshot | null;
  impact?: DecisionImpact | null;
  nextTick?: number | null;
}

export interface MapBuilding {
  id: string;
  kind: MapTileKind;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  units: number;
  maxUnits: number;
  level: number;
  scale: BuildingScale;
  workers: number;
  output: number;
  income: number;
  pollution: number;
  status: string;
  assetKey: string;
}

export interface MapTile {
  x: number;
  y: number;
  kind: MapTileKind;
  label: string;
  active: boolean;
  zone?: MapTileKind | null;
  roadType?: RoadType | null;
  roadConnections: RoadDirection[];
  buildingId?: string | null;
  lotId?: string | null;
  isAnchor: boolean;
}

export interface CityMapLayout {
  width: number;
  height: number;
  tiles: MapTile[];
  buildings: MapBuilding[];
}

export interface TickSnapshot {
  state: WorldState;
  recommendation: GovernmentRecommendation;
}

export interface SimulationControls {
  running: boolean;
  liveTickIntervalSeconds: number;
  fastForwardTicks: number;
}

export interface StateResponse {
  state: WorldState;
  params: Params;
  recommendation: GovernmentRecommendation;
  decisionSystem: DecisionSystemStatus;
  mayorScore: MayorScore;
  decisionScorecard: MayorDecisionScorecardEntry[];
  cityMap: CityMapLayout;
  history: TickSnapshot[];
  events: CityEvent[];
  simulation: SimulationControls;
}
