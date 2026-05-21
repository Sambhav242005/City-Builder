import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type WheelEvent as ReactWheelEvent
} from "react";
import {
  AlertTriangle,
  Building2,
  Check,
  CircleDollarSign,
  Cpu,
  DollarSign,
  Droplets,
  Eye,
  Factory,
  FastForward,
  Flame,
  Hammer,
  House,
  Landmark,
  Map,
  Package,
  Pause,
  Pickaxe,
  Play,
  RotateCcw,
  Smile,
  Store,
  TreePine,
  TrendingUp,
  Users,
  Wheat,
  X,
  Zap,
  ZoomIn,
  ZoomOut
} from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import {
  approveGovernmentAction,
  buildStructure,
  fetchState,
  liveUrl,
  rejectGovernmentAction,
  reset,
  tick
} from "./api";
import cityMapReference from "./assets/city-map-reference.png";

import type {
  ActionName,
  BuildingType,
  CandidateActionTrace,
  CityMapLayout,
  CityEvent,
  EventSeverity,
  MapBuilding,
  MapTile,
  MapTileKind,
  MayorDecisionScorecardEntry,
  Params,
  PolicyNodeTrace,
  MayorScore,
  StateResponse,
  WorldState
} from "./types";

const ACTION_LABELS: Record<ActionName, string> = {
  build_farm: "Build Farm",
  build_factory: "Build Factory",
  build_market: "Build Market",
  build_power_plant: "Build Power Plant",
  build_housing: "Build Housing",
  build_road: "Build Road",
  subsidize: "Subsidize Food",
  do_nothing: "Monitor City"
};

const RESOURCE_COLORS = {
  food: "#72df50",
  wood: "#b9884f",
  steel: "#b2bdc7",
  electronics: "#d45bca",
  fuel: "#ff8842"
};

const BUILDING_COSTS: Record<BuildingType, number> = {
  farm: 120_000,
  factory: 200_000,
  market: 80_000,
  power_plant: 250_000,
  housing: 60_000,
  road: 10_000
};

const BUILDING_LAND_COSTS: Record<BuildingType, number> = {
  farm: 2,
  factory: 3,
  market: 2,
  power_plant: 3,
  housing: 2,
  road: 1
};

const ACTION_BUILDING_TYPES: Partial<Record<ActionName, BuildingType>> = {
  build_farm: "farm",
  build_factory: "factory",
  build_market: "market",
  build_power_plant: "power_plant",
  build_housing: "housing",
  build_road: "road"
};

const MAP_MIN_SCALE = 0.78;
const MAP_MAX_SCALE = 2.2;
const MAP_ZOOM_STEP = 1.16;
// Matches the dimensions of city-map-reference.png.
const MAP_REFERENCE_ASPECT_RATIO = 882 / 766;
const MAP_REFERENCE_ASPECT_RATIO_CSS = MAP_REFERENCE_ASPECT_RATIO.toString();
const MAP_LAND_OVERLAY_OPACITY = 0.12;
const MAP_TEXTURE_OVERLAY_OPACITY = 0.06;
const MAP_STAGE_MAX_WIDTH = 1180;
const MAP_STAGE_PADDING = 32;

const TILE_ZONE_LABELS: Record<MapTileKind, string> = {
  water: "Waterfront",
  road: "Infrastructure",
  residential: "Residential",
  farm: "Farm",
  factory: "Factory",
  market: "Market",
  government: "Government",
  park: "Park",
  power_plant: "Infrastructure",
  empty: "Available Land"
};

const markerColors: Record<MapTileKind, string> = {
  water: "#28749a",
  road: "#39464d",
  residential: "#2f65b4",
  farm: "#439a37",
  factory: "#8652b6",
  market: "#d99a24",
  government: "#c8453c",
  park: "#5ca85a",
  power_plant: "#4d9bd8",
  empty: "#6f8b4a"
};

const EMPTY_TILE_COUNTS: Record<MapTileKind, number> = {
  water: 0,
  road: 0,
  residential: 0,
  farm: 0,
  factory: 0,
  market: 0,
  government: 0,
  park: 0,
  power_plant: 0,
  empty: 0
};

const CITY_MAP_LEGEND: { label: string; color: string; icon: ReactNode; kinds: MapTileKind[] }[] = [
  { label: "Residential", color: "#2f65b4", icon: <House />, kinds: ["residential"] },
  { label: "Factory", color: "#8652b6", icon: <Factory />, kinds: ["factory"] },
  { label: "Market", color: "#d99a24", icon: <Store />, kinds: ["market"] },
  { label: "Farm", color: "#439a37", icon: <Wheat />, kinds: ["farm"] },
  { label: "Power", color: "#4d9bd8", icon: <Zap />, kinds: ["power_plant"] },
  { label: "Road", color: "#39464d", icon: <Hammer />, kinds: ["road"] },
  { label: "Government", color: "#c8453c", icon: <Landmark />, kinds: ["government"] },
  { label: "Park", color: "#5ca85a", icon: <TreePine />, kinds: ["park"] },
  { label: "Waterfront", color: "#28749a", icon: <Droplets />, kinds: ["water"] },
  { label: "Open Land", color: "#6f8b4a", icon: <Map />, kinds: ["empty"] }
];

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function computeTrend(current: number, history: { state: WorldState }[]): string {
  if (history.length < 2) return "--";
  const prev = history[Math.max(0, history.length - 6)];
  const prevVal = prev.state.population * prev.state.price * prev.state.happiness * 1200;
  if (prevVal === 0) return "+0%";
  const pct = ((current - prevVal) / Math.abs(prevVal)) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

function getZoneData(zone: string, state: WorldState) {
  switch (zone) {
    case "Farm":
      return { production: state.food_supply, workers: Math.round(state.farms * 4), land: state.farms * 2, status: "Operating" };
    case "Factory":
    case "Industrial":
      return { production: state.factories * 15, workers: Math.round(state.factories * 8), land: state.factories * 3, status: "Operating" };
    case "Residential":
      return { production: 0, workers: state.population, land: state.housing * 2, status: "Occupied" };
    case "Market":
    case "Commercial":
      return { production: state.markets * 20, workers: Math.round(state.markets * 5), land: state.markets * 2, status: "Trading" };
    case "Government":
      return { production: 0, workers: Math.round(state.population * 0.05), land: 4, status: "Active" };
    case "Infrastructure":
      return {
        production: Math.max(58, 96 - state.factories * 4),
        workers: Math.round(state.power_plants * 3),
        land: state.power_plants * 3 + state.roads,
        status: "Supplying"
      };
    case "Park":
      return { production: 0, workers: Math.round(state.population * 0.02), land: state.parks * 2, status: "Maintained" };
    case "Waterfront":
      return { production: 0, workers: 0, land: 0, status: "Protected" };
    case "Available Land":
      return { production: 0, workers: 0, land: state.land_total - state.land_used, status: "Ready" };
    default:
      return { production: state.food_supply, workers: Math.round(state.population / 3), land: state.land_used, status: "Operating" };
  }
}

function getBuildingData(building: MapBuilding) {
  return {
    production: building.output,
    workers: building.workers,
    land: building.units,
    status: building.status
  };
}

function formatBuildingScale(building: MapBuilding) {
  if (building.scale === "landmark") return "Landmark";
  if (building.scale === "maximum") return `Max Compound ${building.units}/${building.maxUnits}`;
  if (building.scale === "merged") return `Merged ${building.units}/${building.maxUnits}`;
  return `Single ${building.units}/${building.maxUnits}`;
}

function App() {
  const [data, setData] = useState<StateResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cityMapImageUrl = import.meta.env.VITE_CITY_MAP_IMAGE_URL ?? cityMapReference;

  useEffect(() => {
    fetchState()
      .then((payload) => {
        commitState(payload);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!running) {
      return;
    }

    const socket = new WebSocket(liveUrl());
    socket.onmessage = (event) => {
      commitState(JSON.parse(event.data) as StateResponse);
      setError(null);
    };
    socket.onerror = () => {
      setError("Live connection failed. Check that the backend is running.");
    };

    return () => socket.close();
  }, [running]);


  const state = data?.state;
  const recommendation = data?.recommendation;
  const decisionSystem = data?.decisionSystem;

  const chartData = useMemo(
    () =>
      data?.history.map((snapshot) => {
        const current = snapshot.state;
        return {
          tick: current.tick,
          gdp: Math.round(current.population * current.price * current.happiness * 1200),
          happiness: Number((current.happiness * 100).toFixed(1)),
          inflation: Number(Math.max(0, current.price - 8).toFixed(2)),
          price: Number(current.price.toFixed(2)),
          supply: current.food_supply,
          demand: current.food_demand,
          farms: current.farms
        };
      }) ?? [],
    [data]
  );

  if (!state || !data || !recommendation || !decisionSystem) {
    return (
      <main className="app-shell loading-screen">
        <section className="loading-panel">
          <Landmark size={38} />
          <h1>Evolution Government Simulator</h1>
          <p>Connecting to the city simulation...</p>
          {error ? <p className="error-text">{error}</p> : null}
        </section>
      </main>
    );
  }

  const shortage = Math.max(0, state.food_demand - state.food_supply);
  const landRemaining = state.land_total - state.land_used;
  const treasury = state.treasury;
  const gdp = state.population * state.price * state.happiness * 1200;
  const actionIsAvailable =
    recommendation.action !== "do_nothing" &&
    canAffordAction(recommendation.action, state, data.params);
  const optimizer = decisionSystem.optimizer;
  const inputSummary = decisionSystem.inputSummary;
  const topCandidates = decisionSystem.candidates.slice(0, 5);
  const optimizerReasonText = optimizer.overrideApplied && optimizer.originalAction
    ? `Overrode ${ACTION_LABELS[optimizer.originalAction]} after local validation.`
    : "Validated selected action against local candidates.";
  const recentEvents = [...data.events].reverse().slice(0, 6);
  const popTrend = data.history.length >= 2
    ? (() => { const prev = data.history[Math.max(0, data.history.length - 6)].state.population; return prev === 0 ? "--" : `${((state.population - prev) / prev * 100) >= 0 ? "+" : ""}${((state.population - prev) / prev * 100).toFixed(1)}%`; })()
    : "--";
  const gdpTrend = computeTrend(gdp, data.history);
  const treasuryTrend = data.history.length >= 2
    ? (() => { const prev = data.history[Math.max(0, data.history.length - 6)].state.treasury; return prev === 0 ? "--" : `${((treasury - prev) / Math.abs(prev) * 100) >= 0 ? "+" : ""}${((treasury - prev) / Math.abs(prev) * 100).toFixed(1)}%`; })()
    : "--";

  async function handleUpdate(action: () => Promise<StateResponse>) {
    try {
      const payload = await action();
      commitState(payload);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    }
  }

  function commitState(payload: StateResponse) {
    setData(payload);
  }


  return (
    <main className="app-shell">
      <header className="topbar">
        <section className="brand-card">
          <Landmark size={42} />
          <div>
            <h1>Evolution Government Simulator</h1>
            <p>Build - Manage - Prosper</p>
          </div>
        </section>

        <StatCard label="Population" value={formatNumber(state.population)} trend={popTrend} icon={<Users />} />
        <StatCard
          label="Happiness"
          value={`${Math.round(state.happiness * 100)}%`}
          trend={state.happiness > 0.8 ? "Thriving" : state.happiness > 0.6 ? "Happy" : state.happiness > 0.4 ? "Concerned" : "Critical"}
          icon={<Smile />}
        />
        <StatCard label="Mayor Direction" value={`${data.mayorScore.score}/100`} trend={data.mayorScore.label} icon={<TrendingUp />} />
        <StatCard label="GDP" value={formatMoney(gdp)} trend={gdpTrend} icon={<TrendingUp />} />
        <StatCard label="Treasury" value={formatMoney(treasury)} trend={treasuryTrend} icon={<CircleDollarSign />} />

        <section className="time-card">
          <div>
            <span>Day / Time</span>
            <strong>Day {state.tick}</strong>
          </div>
          <b>{formatTime(state.tick)}</b>
          <div className="control-row">
            <IconButton
              label={
                running
                  ? "Pause simulation"
                  : "Resume simulation"
              }
              onClick={() => setRunning((value) => !value)}
            >
              {running ? <Pause size={18} /> : <Play size={18} />}
            </IconButton>
            <IconButton label="Advance one tick" onClick={() => handleUpdate(tick)}>
              <Play size={18} />
            </IconButton>
            <IconButton label="Advance faster" onClick={() => handleUpdate(tick)}>
              <FastForward size={18} />
            </IconButton>
            <IconButton label="Reset simulation" onClick={() => handleUpdate(reset)}>
              <RotateCcw size={18} />
            </IconButton>
          </div>
        </section>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="sim-grid">
        <aside className="left-column">
          <Panel title="Economy Overview">
            <ChartBox height={178}>
              <LineChart data={chartData}>
                <CartesianGrid stroke="#263841" strokeDasharray="4 4" />
                <XAxis dataKey="tick" stroke="#8fa2ad" tick={{ fontSize: 11 }} />
                <YAxis stroke="#8fa2ad" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend />
                <Line type="monotone" dataKey="gdp" name="GDP" stroke="#77db4f" dot={false} strokeWidth={2} />
                <Line
                  type="monotone"
                  dataKey="happiness"
                  name="Happiness"
                  stroke="#4ba6ff"
                  dot={false}
                  strokeWidth={2}
                />
                <Line
                  type="monotone"
                  dataKey="inflation"
                  name="Inflation"
                  stroke="#ff943c"
                  dot={false}
                  strokeWidth={2}
                />
              </LineChart>
            </ChartBox>
          </Panel>

          <Panel title="Market Prices">
            <MarketTable state={state} />
          </Panel>

          <Panel title="Resources">
            <div className="resource-list">
              <ResourceRow icon={<DollarSign />} label="Money" value={formatMoney(treasury)} />
              <ResourceRow icon={<Map />} label="Land" value={`${state.land_used} / ${state.land_total}`} />
              <ResourceRow icon={<Users />} label="Labor" value={formatNumber(state.population * 50)} />
              <ResourceRow icon={<Zap />} label="Power" value={`${Math.max(58, 96 - state.factories * 4)}%`} />
              <ResourceRow icon={<Droplets />} label="Water" value={`${Math.max(55, 82 - state.farms)}%`} />
            </div>
          </Panel>

          <Panel title="Supply Chain">
            <SupplyChainPanel state={state} params={data.params} />
          </Panel>

          <Panel title="Event Log">
            <div className="event-list">
              {recentEvents.map((event, index) => (
                <EventRow key={`${event.tick}-${event.message}-${index}`} event={event} />
              ))}
            </div>
          </Panel>
        </aside>

        <section className="map-column">
          <Panel title="City Map" flush>
            <div className="city-map-static">
              <img
                className="city-map-static-image"
                src={cityMapImageUrl}
                alt="City map overview"
                loading="lazy"
              />
            </div>
          </Panel>
        </section>

        <aside className="right-column">
          <Panel title="Mayor Direction">
            <MayorDirectionCard score={data.mayorScore} />
          </Panel>

          <Panel title="Optimizer Trace">
            <div className={`optimizer-verdict optimizer-${optimizer.verdict}`}>
              <span>Local Validator</span>
              <strong>{optimizer.verdict}</strong>
              <em>
                {optimizer.overrideApplied && optimizer.originalAction
                  ? `Overrode ${ACTION_LABELS[optimizer.originalAction]}`
                  : "Validated policy output"}
              </em>
            </div>
            <div className="optimizer-reason">
              <Cpu size={22} />
              <p>{optimizerReasonText}</p>
            </div>
            <div className="trace-input-grid" aria-label="Optimizer input snapshot">
              <TraceMetric label="Food" value={`${formatNumber(inputSummary.foodSupply)} / ${formatNumber(inputSummary.foodDemand)}`} />
              <TraceMetric label="Price" value={formatMoney(inputSummary.price)} />
              <TraceMetric label="Happy" value={`${Math.round(inputSummary.happiness * 100)}%`} />
              <TraceMetric label="Land" value={`${inputSummary.landUsed}/${inputSummary.landTotal}`} />
            </div>
            <TraceNodeList nodes={decisionSystem.nodes} />
            <CandidateScoreList candidates={topCandidates} />
          </Panel>

          <Panel title="Optimizer Output">
            <div className="decision-action">
              <div className="decision-icon">
                {decisionIcon(recommendation.action)}
              </div>
              <div>
                <span>Recommended Action</span>
                <strong>{ACTION_LABELS[recommendation.action]}</strong>
              </div>
            </div>
            <div className="policy-diagnostics">
              <span>{decisionSystem.source.replace("_", " ")}</span>
              <strong>{Math.round(decisionSystem.confidence * 100)}%</strong>
              <em>Fitness {decisionSystem.valueEstimate.toFixed(2)}</em>
            </div>
            <div className="impact-grid">
              <Impact icon={<Smile />} label="Happiness" value={`${signed(recommendation.estimated_happiness_delta * 100)}%`} />
              <Impact icon={<Wheat />} label="Food Supply" value={signed(recommendation.estimated_food_supply_delta)} />
              <Impact
                icon={<DollarSign />}
                label="Cost"
                value={actionCost(recommendation.action, state, data.params)}
                danger
              />
            </div>
            <p className="decision-note">{recommendation.reason}</p>
            <div className="decision-buttons">
              <button
                className="approve-button"
                type="button"
                disabled={!actionIsAvailable}
                onClick={() => handleUpdate(approveGovernmentAction)}
              >
                <Check size={16} />
                Approve
              </button>
              <button
                className="reject-button"
                type="button"
                disabled={!actionIsAvailable}
                onClick={() => handleUpdate(rejectGovernmentAction)}
              >
                <X size={16} />
                Reject
              </button>
            </div>
          </Panel>

          <Panel title="Mayor Decision Scorecard">
            <DecisionScorecard entries={data.decisionScorecard} />
          </Panel>

          <Panel title="City Alerts">
            <div className="alert-list">
              {state.price > 15 ? <AlertRow level="danger" text="Food price is too high" /> : null}
              {shortage > 0 ? <AlertRow level="warning" text="Food supply below demand" /> : null}
              {landRemaining < 10 ? <AlertRow level="warning" text="Low land available" /> : null}
              {state.happiness < 0.55 ? <AlertRow level="danger" text="Happiness is falling" /> : null}
              {state.markets === 0 && state.population > 0 ? <AlertRow level="danger" text="No markets! Citizens can't buy food" /> : null}
              {state.market_food_inventory < 5 && state.markets > 0 ? <AlertRow level="warning" text="Market food inventory critically low" /> : null}
              {state.market_goods_inventory < 3 && state.markets > 0 ? <AlertRow level="warning" text="Market goods inventory running low" /> : null}
              {state.tax_revenue_last_tick > 0 ? <AlertRow level="success" text={`Tax collected: ${formatMoney(state.tax_revenue_last_tick)}`} /> : null}
              {state.price <= 15 && shortage === 0 && state.happiness >= 0.55 && state.markets > 0 ? (
                <AlertRow level="success" text="City systems stable" />
              ) : null}
            </div>
          </Panel>
        </aside>

        <section className="build-panel">
          <Panel title="Build Menu">
            <div className="build-menu">
              <BuildCard icon={<Wheat />} name="Farm" cost={formatCost(BUILDING_COSTS.farm)} land={`${BUILDING_LAND_COSTS.farm}`} tone="green" disabled={!canBuildType("farm", state)} onBuild={() => handleUpdate(() => buildStructure("farm"))} />
              <BuildCard icon={<Factory />} name="Factory" cost={formatCost(BUILDING_COSTS.factory)} land={`${BUILDING_LAND_COSTS.factory}`} tone="purple" disabled={!canBuildType("factory", state)} onBuild={() => handleUpdate(() => buildStructure("factory"))} />
              <BuildCard icon={<Store />} name="Market" cost={formatCost(BUILDING_COSTS.market)} land={`${BUILDING_LAND_COSTS.market}`} tone="gold" disabled={!canBuildType("market", state)} onBuild={() => handleUpdate(() => buildStructure("market"))} />
              <BuildCard icon={<Zap />} name="Power Plant" cost={formatCost(BUILDING_COSTS.power_plant)} land={`${BUILDING_LAND_COSTS.power_plant}`} tone="steel" disabled={!canBuildType("power_plant", state)} onBuild={() => handleUpdate(() => buildStructure("power_plant"))} />
              <BuildCard icon={<House />} name="Housing" cost={formatCost(BUILDING_COSTS.housing)} land={`${BUILDING_LAND_COSTS.housing}`} tone="blue" disabled={!canBuildType("housing", state)} onBuild={() => handleUpdate(() => buildStructure("housing"))} />
              <BuildCard icon={<Hammer />} name="Road" cost={formatCost(BUILDING_COSTS.road)} land={`${BUILDING_LAND_COSTS.road}`} tone="road" disabled={!canBuildType("road", state)} onBuild={() => handleUpdate(() => buildStructure("road"))} />
            </div>
          </Panel>
        </section>

        <section className="demand-panel">
          <Panel title="Supply vs Demand (Food)">
            <ChartBox height={118}>
              <LineChart data={chartData}>
                <CartesianGrid stroke="#263841" strokeDasharray="4 4" />
                <XAxis dataKey="tick" stroke="#8fa2ad" tick={{ fontSize: 11 }} />
                <YAxis stroke="#8fa2ad" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend />
                <Line type="monotone" dataKey="supply" name="Supply" stroke="#72df50" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="demand" name="Demand" stroke="#ff6161" dot={false} strokeWidth={2} />
              </LineChart>
            </ChartBox>
          </Panel>
        </section>
      </section>
    </main>
  );
}

const tooltipStyle = {
  background: "#101b21",
  border: "1px solid #31505d",
  borderRadius: 6,
  color: "#f6fbff"
};

function StatCard({
  label,
  value,
  trend,
  icon
}: {
  label: string;
  value: string;
  trend: string;
  icon: ReactNode;
}) {
  return (
    <section className="stat-card">
      <div className="stat-hidden-icon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{trend}</em>
    </section>
  );
}

function Panel({ title, children, flush = false }: { title: string; children: ReactNode; flush?: boolean }) {
  return (
    <section className={`panel ${flush ? "panel-flush" : ""}`}>
      <div className="panel-title">
        <h2>{title}</h2>
        <span>::</span>
      </div>
      {children}
    </section>
  );
}

function IconButton({
  label,
  onClick,
  children,
  disabled = false
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <button className="icon-button" type="button" title={label} aria-label={label} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}

function ChartBox({ height, children }: { height: number; children: ReactNode }) {
  return (
    <div className="chart-box" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}

function TraceMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="trace-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TraceNodeList({ nodes }: { nodes: PolicyNodeTrace[] }) {
  const visibleNodes = nodes.slice(0, 7);
  return (
    <div className="trace-block">
      <div className="trace-block-title">
        <span>Node Updates</span>
        <em>{visibleNodes.length} active</em>
      </div>
      <div className="node-trace-list">
        {visibleNodes.map((node) => (
          <div className={`node-trace node-${node.status}`} key={node.key} title={node.note}>
            <div>
              <strong>{node.label}</strong>
              <span>{node.note}</span>
            </div>
            <em>{formatTraceDelta(node.delta)}</em>
            <b>{formatNodeValue(node.currentValue)}</b>
          </div>
        ))}
      </div>
    </div>
  );
}

function CandidateScoreList({ candidates }: { candidates: CandidateActionTrace[] }) {
  return (
    <div className="trace-block">
      <div className="trace-block-title">
        <span>Candidate Scores</span>
        <em>optimizer rank</em>
      </div>
      <div className="candidate-list">
        {candidates.map((candidate) => (
          <div className={`candidate-row ${candidate.selected ? "candidate-selected" : ""}`} key={candidate.action}>
            <span>#{candidate.rank}</span>
            <strong>{ACTION_LABELS[candidate.action]}</strong>
            <em>{candidate.optimizerScore.toFixed(3)}</em>
            <b>{candidate.selected ? "output" : candidate.riskFlags[0] ?? "valid"}</b>
          </div>
        ))}
      </div>
    </div>
  );
}

function MayorDirectionCard({ score }: { score: MayorScore }) {
  return (
    <div className={`mayor-direction mayor-${score.status}`}>
      <div className="mayor-score-row">
        <div className="mayor-score-ring" aria-label={`Mayor direction score ${score.score} out of 100`}>
          <strong>{score.score}</strong>
          <span>/100</span>
        </div>
        <div>
          <span className="mayor-status">{score.label}</span>
          <strong>{score.trend}</strong>
          <p>{score.summary.replace("; keep protecting happiness.", ".")}</p>
        </div>
      </div>

      <div className="mayor-factor-list">
        {score.factors.map((factor) => (
          <div className="mayor-factor" key={factor.name}>
            <div>
              <span>{factor.name}</span>
              <strong>{factor.value}</strong>
            </div>
            <div className="factor-bar" aria-label={`${factor.name} score ${factor.score}`}>
              <i style={{ width: `${factor.score}%` }} />
            </div>
            <em>{factor.note}</em>
          </div>
        ))}
      </div>
    </div>
  );
}

function DecisionScorecard({ entries }: { entries: MayorDecisionScorecardEntry[] }) {
  const visibleEntries = [...entries].reverse().slice(0, 8);

  if (visibleEntries.length === 0) {
    return (
      <div className="scorecard-empty">
        <TrendingUp size={18} />
        <span>No approved or rejected recommendations yet.</span>
      </div>
    );
  }

  return (
    <div className="decision-scorecard" aria-label="Mayor decision scorecard">
      {visibleEntries.map((entry) => {
        const impact = entry.impact;
        return (
          <article className={`scorecard-entry scorecard-${entry.decision}`} key={entry.id}>
            <div className="scorecard-entry-head">
              <span className={`decision-chip decision-${entry.decision}`}>
                {entry.decision === "approved" ? <Check size={12} /> : <X size={12} />}
                {entry.decision}
              </span>
              <div>
                <strong>{ACTION_LABELS[entry.action]}</strong>
                <em>
                  Day {entry.tick}
                  {entry.nextTick ? ` -> ${entry.nextTick}` : " -> next tick pending"}
                </em>
              </div>
            </div>

            <div className="scorecard-impact-grid">
              <ScorecardMetric
                label="Food"
                value={impact ? signed(impact.foodBalanceDelta) : "pending"}
                tone={impactTone("food", impact?.foodBalanceDelta)}
                title={metricTitle("Food balance", entry.before.foodBalance, entry.after?.foodBalance)}
              />
              <ScorecardMetric
                label="Price"
                value={impact ? formatSignedPrice(impact.priceDelta) : "pending"}
                tone={impactTone("price", impact?.priceDelta)}
                title={metricTitle("Price", entry.before.price, entry.after?.price)}
              />
              <ScorecardMetric
                label="Happy"
                value={impact ? `${signed(impact.happinessDelta * 100)}%` : "pending"}
                tone={impactTone("happiness", impact?.happinessDelta)}
                title={metricTitle("Happiness", entry.before.happiness, entry.after?.happiness)}
              />
              <ScorecardMetric
                label="Score"
                value={impact ? formatScoreDelta(impact.mayorScoreDelta) : "pending"}
                tone={impactTone("mayor", impact?.mayorScoreDelta)}
                title={metricTitle("Mayor score", entry.before.mayorScore, entry.after?.mayorScore)}
              />
            </div>
            <p>{entry.reason}</p>
          </article>
        );
      })}
    </div>
  );
}

function ScorecardMetric({
  label,
  value,
  tone,
  title
}: {
  label: string;
  value: string;
  tone: string;
  title: string;
}) {
  return (
    <span className={`scorecard-metric metric-${tone}`} title={title}>
      <em>{label}</em>
      <strong>{value}</strong>
    </span>
  );
}

function MarketTable({ state }: { state: WorldState }) {
  const woodPrice = 6 + state.population * 0.02 + Math.sin(state.tick * 0.3) * 1.2;
  const steelPrice = 14 + state.factories * 1.5 + Math.cos(state.tick * 0.2) * 2;
  const elecPrice = 20 + state.factories * 2 + Math.sin(state.tick * 0.15) * 3;
  const fuelPrice = 12 + state.factories * 0.8 + Math.cos(state.tick * 0.25) * 1.5;
  const rows = [
    {
      icon: <Wheat size={16} />,
      name: "Food",
      color: RESOURCE_COLORS.food,
      price: state.price,
      demand: state.food_demand,
      supply: state.food_supply
    },
    {
      icon: <TreePine size={16} />,
      name: "Wood",
      color: RESOURCE_COLORS.wood,
      price: woodPrice,
      demand: Math.round(state.population * 0.6),
      supply: Math.round(state.farms * 5 + 30)
    },
    {
      icon: <Pickaxe size={16} />,
      name: "Steel",
      color: RESOURCE_COLORS.steel,
      price: steelPrice,
      demand: Math.round(state.population * 0.8 + state.factories * 5),
      supply: Math.round(state.factories * 15)
    },
    {
      icon: <Cpu size={16} />,
      name: "Electronics",
      color: RESOURCE_COLORS.electronics,
      price: elecPrice,
      demand: Math.round(state.population * 0.35),
      supply: Math.round(state.factories * 8)
    },
    {
      icon: <Flame size={16} />,
      name: "Fuel",
      color: RESOURCE_COLORS.fuel,
      price: fuelPrice,
      demand: Math.round(state.population * 0.65),
      supply: Math.round(state.factories * 12 + 20)
    }
  ];

  return (
    <table className="market-table">
      <thead>
        <tr>
          <th>Goods</th>
          <th>Price</th>
          <th>Demand</th>
          <th>Supply</th>
          <th>Trend</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const isShort = row.demand > row.supply;
          return (
            <tr key={row.name}>
              <td style={{ color: row.color }}>
                {row.icon}
                <span>{row.name}</span>
              </td>
              <td>{formatPrice(row.price)}</td>
              <td>{formatNumber(row.demand)}</td>
              <td>{formatNumber(row.supply)}</td>
              <td className={isShort ? "trend-up" : "trend-down"}>{isShort ? "up" : "down"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function ResourceRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="resource-row">
      <span>
        {icon}
        {label}
      </span>
      <strong>{value}</strong>
    </div>
  );
}

function SupplyChainPanel({ state, params }: { state: WorldState; params: Params }) {
  const maxFoodCap = Math.max(1, state.markets * params.market_buy_food_limit * 2);
  const maxGoodsCap = Math.max(1, state.markets * params.market_buy_goods_limit * 2);
  const foodPct = Math.min(100, (state.market_food_inventory / maxFoodCap) * 100);
  const goodsPct = Math.min(100, (state.market_goods_inventory / maxGoodsCap) * 100);
  const foodColor = foodPct > 50 ? "#72df50" : foodPct > 20 ? "#ffc84d" : "#ff6060";
  const goodsColor = goodsPct > 50 ? "#4ba6ff" : goodsPct > 20 ? "#ffc84d" : "#ff6060";

  return (
    <div className="supply-chain-panel">
      <div className="supply-chain-row">
        <div className="supply-chain-header">
          <span className="supply-chain-icon">🍎</span>
          <span className="supply-chain-label">Food Inventory</span>
          <strong className="supply-chain-value" style={{ color: foodColor }}>
            {state.market_food_inventory.toFixed(1)}
          </strong>
        </div>
        <div className="supply-chain-bar-bg">
          <div
            className="supply-chain-bar-fill"
            style={{
              width: `${foodPct}%`,
              background: `linear-gradient(90deg, ${foodColor}cc, ${foodColor})`,
            }}
          />
        </div>
        <div className="supply-chain-meta">
          <em>Spoilage: {(params.food_spoilage_rate * 100).toFixed(0)}%/tick</em>
          <em>Cap: {(state.markets * params.market_buy_food_limit).toFixed(0)}/tick</em>
        </div>
      </div>

      <div className="supply-chain-row">
        <div className="supply-chain-header">
          <span className="supply-chain-icon">📦</span>
          <span className="supply-chain-label">Goods Inventory</span>
          <strong className="supply-chain-value" style={{ color: goodsColor }}>
            {state.market_goods_inventory.toFixed(1)}
          </strong>
        </div>
        <div className="supply-chain-bar-bg">
          <div
            className="supply-chain-bar-fill"
            style={{
              width: `${goodsPct}%`,
              background: `linear-gradient(90deg, ${goodsColor}cc, ${goodsColor})`,
            }}
          />
        </div>
        <div className="supply-chain-meta">
          <em>Decay: {(params.goods_decay_rate * 100).toFixed(0)}%/tick</em>
          <em>Cap: {(state.markets * params.market_buy_goods_limit).toFixed(0)}/tick</em>
        </div>
      </div>

      <div className="supply-chain-divider" />

      <div className="supply-chain-row">
        <div className="supply-chain-header">
          <span className="supply-chain-icon">💰</span>
          <span className="supply-chain-label">Tax Revenue (last tick)</span>
          <strong className="supply-chain-value" style={{ color: state.tax_revenue_last_tick > 0 ? "#72df50" : "#9eb2bd" }}>
            {state.tax_revenue_last_tick > 0 ? `+${formatMoney(state.tax_revenue_last_tick)}` : "$0"}
          </strong>
        </div>
        <div className="supply-chain-meta">
          <em>Rate: {(params.tax_rate * 100).toFixed(0)}% sales tax</em>
          <em>Export cap: {(state.markets * params.export_food_limit).toFixed(0)}F / {(state.markets * params.export_goods_limit).toFixed(0)}G</em>
        </div>
      </div>
    </div>
  );
}

function EventRow({ event }: { event: CityEvent }) {
  return (
    <div className={`event-row event-${event.severity}`}>
      <i />
      <p>
        Day {event.tick}: <span>{event.message}</span>
      </p>
    </div>
  );
}

function LegendItem({
  icon,
  color,
  label,
  count
}: {
  icon: ReactNode;
  color: string;
  label: string;
  count?: number;
}) {
  return (
    <span className="legend-item">
      <b style={{ backgroundColor: color }}>{icon}</b>
      <span>{label}</span>
      {typeof count === "number" ? <em>{count}</em> : null}
    </span>
  );
}

function MapInspector({
  label,
  zoneData,
  building
}: {
  label: string;
  zoneData: ReturnType<typeof getZoneData>;
  building: MapBuilding | null;
}) {
  return (
    <aside className="map-inspector" aria-label={`${label} details`}>
      <div className="map-inspector-head">
        <span>{building ? TILE_ZONE_LABELS[building.kind] : "District"}</span>
        <strong>{label}</strong>
      </div>
      <div className="map-inspector-grid">
        {building ? <MapMetric label="Scale" value={formatBuildingScale(building)} /> : null}
        <MapMetric label="Production" value={formatNumber(zoneData.production)} />
        <MapMetric label="Workers" value={formatNumber(zoneData.workers)} />
        <MapMetric label="Land" value={`${zoneData.land}`} />
        {building ? <MapMetric label="Footprint" value={`${building.width} x ${building.height}`} /> : null}
        <MapMetric label="Status" value={zoneData.status} tone="good" />
      </div>
    </aside>
  );
}

function MapMetric({
  label,
  value,
  tone = "neutral"
}: {
  label: string;
  value: string;
  tone?: "good" | "neutral";
}) {
  return (
    <span className={`map-metric map-metric-${tone}`}>
      <em>{label}</em>
      <strong>{value}</strong>
    </span>
  );
}

function CityMapBoard({
  layout,
  state,
  selectedZone,
  selectedBuildingId,
  onSelectZone,
  onSelectBuilding,
  showOverlay,
  setShowOverlay
}: {
  layout: CityMapLayout;
  state: WorldState;
  selectedZone: string;
  selectedBuildingId: string | null;
  onSelectZone: (zone: string) => void;
  onSelectBuilding: (building: MapBuilding) => void;
  showOverlay: boolean;
  setShowOverlay: (value: boolean) => void;
}) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
    dragged: boolean;
  } | null>(null);
  const suppressClickRef = useRef(false);
  const [view, setView] = useState({ scale: 1, x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [viewportSize, setViewportSize] = useState({ width: 0, height: 0 });
  const selectedKinds = selectedKindsForZone(selectedZone);
  const plan = useMemo(() => buildTopDownMapPlan(layout, state), [layout, state]);
  const stageWidth = useMemo(() => {
    if (!viewportSize.width || !viewportSize.height) {
      return undefined;
    }

    const widthBound = Math.max(220, viewportSize.width - MAP_STAGE_PADDING * 2);
    const heightBound = Math.max(220, (viewportSize.height - MAP_STAGE_PADDING * 2) * MAP_REFERENCE_ASPECT_RATIO);
    return Math.min(MAP_STAGE_MAX_WIDTH, widthBound, heightBound);
  }, [viewportSize]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) {
      return;
    }

    const updateSize = () => {
      const rect = viewport.getBoundingClientRect();
      setViewportSize({ width: rect.width, height: rect.height });
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(viewport);

    return () => observer.disconnect();
  }, []);

  function updateView(nextView: { scale: number; x: number; y: number }) {
    const panX = Math.max(320, plan.width * 0.38) * nextView.scale;
    const panY = Math.max(220, plan.height * 0.32) * nextView.scale;
    return {
      scale: clamp(nextView.scale, MAP_MIN_SCALE, MAP_MAX_SCALE),
      x: clamp(nextView.x, -panX, panX),
      y: clamp(nextView.y, -panY, panY)
    };
  }

  function zoomBy(factor: number, clientX?: number, clientY?: number) {
    setView((current) => {
      const nextScale = clamp(current.scale * factor, MAP_MIN_SCALE, MAP_MAX_SCALE);
      const viewport = viewportRef.current;
      if (!viewport || typeof clientX !== "number" || typeof clientY !== "number") {
        return updateView({ ...current, scale: nextScale });
      }

      const rect = viewport.getBoundingClientRect();
      const localX = clientX - rect.left - rect.width / 2;
      const localY = clientY - rect.top - rect.height / 2;
      const scaleRatio = nextScale / current.scale;

      return updateView({
        scale: nextScale,
        x: localX - (localX - current.x) * scaleRatio,
        y: localY - (localY - current.y) * scaleRatio
      });
    });
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0 || (event.target as HTMLElement).closest(".map-control-button")) {
      return;
    }

    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: view.x,
      originY: view.y,
      dragged: false
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(true);
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) {
      return;
    }

    const deltaX = event.clientX - drag.startX;
    const deltaY = event.clientY - drag.startY;
    if (Math.abs(deltaX) > 4 || Math.abs(deltaY) > 4) {
      drag.dragged = true;
    }

    setView((current) =>
      updateView({
        scale: current.scale,
        x: drag.originX + deltaX,
        y: drag.originY + deltaY
      })
    );
  }

  function finishDrag(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) {
      return;
    }

    suppressClickRef.current = drag.dragged;
    if (drag.dragged) {
      window.setTimeout(() => {
        suppressClickRef.current = false;
      }, 120);
    }
    dragRef.current = null;
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function handleWheel(event: ReactWheelEvent<HTMLDivElement>) {
    event.preventDefault();
    zoomBy(event.deltaY < 0 ? MAP_ZOOM_STEP : 1 / MAP_ZOOM_STEP, event.clientX, event.clientY);
  }

  function selectBuilding(building: MapBuilding) {
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }

    onSelectBuilding(building);
  }

  const stageStyle = {
    width: stageWidth ? `${stageWidth}px` : "min(1180px, calc(100% - 32px))",
    transform: `translate(-50%, -50%) translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
    "--map-aspect-ratio": MAP_REFERENCE_ASPECT_RATIO_CSS
  } satisfies CSSProperties & { "--map-aspect-ratio": string };

  return (
    <div
      ref={viewportRef}
      className={`city-map-viewport ${dragging ? "is-dragging" : ""}`}
      aria-label={`${Math.round(plan.width)} by ${Math.round(plan.height)} top-down city map`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={finishDrag}
      onPointerCancel={finishDrag}
      onWheel={handleWheel}
    >
      <div className="map-controls" aria-label="Map controls">
        <button
          className="map-control-button"
          type="button"
          aria-label="Toggle overlay"
          title="Toggle overlay"
          style={showOverlay ? { color: "#78e859", borderColor: "#78e859" } : {}}
          onClick={() => setShowOverlay(!showOverlay)}
        >
          <Eye size={16} />
        </button>
        <button
          className="map-control-button"
          type="button"
          aria-label="Recenter map"
          title="Recenter map"
          onClick={() => setView({ scale: 1, x: 0, y: 0 })}
        >
          <RotateCcw size={16} />
        </button>
        <button className="map-control-button" type="button" aria-label="Zoom in" title="Zoom in" onClick={() => zoomBy(MAP_ZOOM_STEP)}>
          <ZoomIn size={16} />
        </button>
        <button className="map-control-button" type="button" aria-label="Zoom out" title="Zoom out" onClick={() => zoomBy(1 / MAP_ZOOM_STEP)}>
          <ZoomOut size={16} />
        </button>
      </div>

      <div
        className="top-map-stage"
        style={stageStyle}
      >
        <TopDownSvgMap
          plan={plan}
          selectedKinds={selectedKinds}
          selectedBuildingId={selectedBuildingId}
          onSelectBuilding={selectBuilding}
          onSelectZone={onSelectZone}
        />
      </div>
    </div>
  );
}

type TopDownPlan = {
  width: number;
  height: number;
  roads: MapPath[];
  paths: MapPath[];
  parking: MapRect[];
  fields: MapRect[];
  trees: MapPoint[];
  buildings: TopDownBuilding[];
};

type MapPath = { id: string; d: string; width: number };
type MapRect = { id: string; x: number; y: number; width: number; height: number; rotation?: number; kind?: MapTileKind };
type MapPoint = { id: string; x: number; y: number; size: number };
type TopDownBuilding = MapRect & { source: MapBuilding; marker: number };

function TopDownSvgMap({
  plan,
  selectedKinds,
  selectedBuildingId,
  onSelectBuilding,
  onSelectZone
}: {
  plan: TopDownPlan;
  selectedKinds: Set<MapTileKind>;
  selectedBuildingId: string | null;
  onSelectBuilding: (building: MapBuilding) => void;
  onSelectZone: (zone: string) => void;
}) {
  return (
    <svg className="top-map-svg" viewBox={`0 0 ${plan.width} ${plan.height}`} role="img" aria-label="Top-down city plan">
      <defs>
        <filter id="topMapShadow" x="-25%" y="-25%" width="150%" height="150%">
          <feDropShadow dx="0" dy="7" stdDeviation="5" floodColor="#6b785e" floodOpacity="0.28" />
        </filter>
        <pattern id="topMapGrass" width="34" height="34" patternUnits="userSpaceOnUse">
          <path d="M0 34 L34 0" stroke="rgba(99,122,75,0.12)" strokeWidth="1" />
        </pattern>
        <pattern id="fieldRows" width="12" height="12" patternUnits="userSpaceOnUse">
          <path d="M0 6 H12" stroke="rgba(89,126,43,0.3)" strokeWidth="2" />
        </pattern>
      </defs>

      <image
        className="top-map-image"
        href={cityMapReference}
        x="0"
        y="0"
        width={plan.width}
        height={plan.height}
        aria-hidden="true"
        style={{ pointerEvents: "none" }}
      />
      <rect
        className="top-map-land"
        x="0"
        y="0"
        width={plan.width}
        height={plan.height}
        rx="18"
        style={{ cursor: "pointer", opacity: MAP_LAND_OVERLAY_OPACITY }}
        onClick={() => onSelectZone("Available Land")}
      />
      <rect
        className="top-map-texture"
        x="0"
        y="0"
        width={plan.width}
        height={plan.height}
        fill="url(#topMapGrass)"
        rx="18"
        style={{ cursor: "pointer", opacity: MAP_TEXTURE_OVERLAY_OPACITY }}
        onClick={() => onSelectZone("Available Land")}
      />

      {plan.paths.map((path) => (
        <path className="top-footpath" key={path.id} d={path.d} strokeWidth={path.width} />
      ))}

      {plan.roads.map((road) => (
        <g key={road.id}>
          <path className="top-road-edge" d={road.d} strokeWidth={road.width + 12} />
          <path className="top-road" d={road.d} strokeWidth={road.width} />
          <path className="top-road-line" d={road.d} strokeWidth="2" />
        </g>
      ))}

      {plan.parking.map((lot) => (
        <g className="top-parking" key={lot.id} transform={rectTransform(lot)}>
          <rect x={lot.x} y={lot.y} width={lot.width} height={lot.height} rx="4" />
          {Array.from({ length: Math.max(2, Math.floor(lot.width / 18)) }).map((_, index) => (
            <line key={index} x1={lot.x + 12 + index * 18} y1={lot.y + 6} x2={lot.x + 12 + index * 18} y2={lot.y + lot.height - 6} />
          ))}
        </g>
      ))}

      {plan.fields.map((field) => (
        <g className="top-field" key={field.id} transform={rectTransform(field)}>
          <rect x={field.x} y={field.y} width={field.width} height={field.height} rx="7" />
          <rect x={field.x + 5} y={field.y + 5} width={field.width - 10} height={field.height - 10} rx="5" fill="url(#fieldRows)" />
        </g>
      ))}

      {plan.trees.map((tree) => (
        <g className="top-tree" key={tree.id}>
          <circle cx={tree.x} cy={tree.y} r={tree.size} />
          <circle cx={tree.x - tree.size * 0.42} cy={tree.y + tree.size * 0.24} r={tree.size * 0.56} />
          <circle cx={tree.x + tree.size * 0.5} cy={tree.y + tree.size * 0.18} r={tree.size * 0.48} />
        </g>
      ))}

      {plan.buildings.map((building) => {
        const selected = selectedBuildingId
          ? building.source.id === selectedBuildingId
          : selectedKinds.has(building.source.kind);
        return (
          <TopDownBuildingShape
            key={building.id}
            building={building}
            selected={selected}
            onSelectBuilding={onSelectBuilding}
          />
        );
      })}
    </svg>
  );
}

function TopDownBuildingShape({
  building,
  selected,
  onSelectBuilding
}: {
  building: TopDownBuilding;
  selected: boolean;
  onSelectBuilding: (building: MapBuilding) => void;
}) {
  const centerX = building.x + building.width / 2;
  const centerY = building.y + building.height / 2;

  function select() {
    onSelectBuilding(building.source);
  }

  return (
    <g
      className={`top-building top-building-${building.source.kind} ${selected ? "top-building-selected" : ""}`}
      transform={rectTransform(building)}
      tabIndex={0}
      role="button"
      aria-label={`Select ${building.source.label}`}
      onClick={select}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          select();
        }
      }}
    >
      <title>{`${building.source.label} (Unit ${building.marker}/${building.source.units})`}</title>
      <rect className="top-building-shadow" x={building.x + 4} y={building.y + 5} width={building.width} height={building.height} rx="5" />
      <rect className="top-building-base" x={building.x} y={building.y} width={building.width} height={building.height} rx="5" />
      <path
        className="top-building-roof"
        d={`M ${building.x + building.width * 0.08} ${building.y + building.height * 0.12} H ${building.x + building.width * 0.92} V ${building.y + building.height * 0.38} H ${building.x + building.width * 0.08} Z`}
      />
      {building.source.kind === "government" ? (
        <g opacity="0.9">
          {/* Neoclassical Pediment (Triangular Roof) */}
          <polygon
            points={`${building.x + building.width * 0.05},${building.y + building.height * 0.32} ${building.x + building.width * 0.95},${building.y + building.height * 0.32} ${centerX},${building.y + building.height * 0.08}`}
            fill="#78909c"
            stroke="#37474f"
            strokeWidth="1.5"
          />
          {/* Neoclassical Columns */}
          <rect x={building.x + building.width * 0.18} y={building.y + building.height * 0.32} width={building.width * 0.08} height={building.height * 0.48} fill="#b0bec5" stroke="#37474f" strokeWidth="1" />
          <rect x={centerX - building.width * 0.04} y={building.y + building.height * 0.32} width={building.width * 0.08} height={building.height * 0.48} fill="#b0bec5" stroke="#37474f" strokeWidth="1" />
          <rect x={building.x + building.width * 0.74} y={building.y + building.height * 0.32} width={building.width * 0.08} height={building.height * 0.48} fill="#b0bec5" stroke="#37474f" strokeWidth="1" />
          {/* Neoclassical Staircase Entrance */}
          <rect x={building.x + building.width * 0.1} y={building.y + building.height * 0.8} width={building.width * 0.8} height={building.height * 0.08} fill="#cfd8dc" stroke="#37474f" strokeWidth="1" />
          <rect x={building.x + building.width * 0.15} y={building.y + building.height * 0.88} width={building.width * 0.7} height={building.height * 0.07} fill="#eceff1" stroke="#37474f" strokeWidth="1" />
        </g>
      ) : null}
      {building.source.kind === "residential" ? (
        <g opacity="0.9">
          {/* Residential pitched roof */}
          <polygon
            points={`${building.x + building.width * 0.05},${building.y + building.height * 0.35} ${centerX},${building.y + building.height * 0.08} ${building.x + building.width * 0.95},${building.y + building.height * 0.35}`}
            fill="#cfd8dc"
            stroke="#5a6b73"
            strokeWidth="1.5"
          />
          {/* Double entry door */}
          <rect x={centerX - building.width * 0.08} y={building.y + building.height * 0.65} width={building.width * 0.16} height={building.height * 0.3} rx="1" fill="#8d6e63" stroke="#4e342e" strokeWidth="1" />
          {/* Left & Right Windows */}
          <rect x={building.x + building.width * 0.15} y={building.y + building.height * 0.45} width={building.width * 0.15} height={building.height * 0.18} rx="1" fill="#e0f7fa" stroke="#006064" strokeWidth="1" />
          <rect x={building.x + building.width * 0.7} y={building.y + building.height * 0.45} width={building.width * 0.15} height={building.height * 0.18} rx="1" fill="#e0f7fa" stroke="#006064" strokeWidth="1" />
        </g>
      ) : null}
      {building.source.kind === "farm" ? (
        <g>
          {/* Gambrel Barn Roof */}
          <polygon
            points={`${building.x + building.width * 0.15},${building.y + building.height * 0.42} ${building.x + building.width * 0.28},${building.y + building.height * 0.14} ${building.x + building.width * 0.72},${building.y + building.height * 0.14} ${building.x + building.width * 0.85},${building.y + building.height * 0.42}`}
            fill="#d32f2f"
            stroke="#5c2e16"
            strokeWidth="1.5"
          />
          {/* Hayloft window */}
          <circle cx={centerX} cy={building.y + building.height * 0.28} r={Math.min(building.width, building.height) * 0.08} fill="#ffffff" stroke="#5c2e16" strokeWidth="1" />
          {/* Barn Double-Doors with White "X" Planks */}
          <rect x={centerX - building.width * 0.16} y={building.y + building.height * 0.55} width={building.width * 0.32} height={building.height * 0.4} fill="#a0522d" stroke="#5c2e16" strokeWidth="1.5" rx="1.5" />
          <line x1={centerX - building.width * 0.16} y1={building.y + building.height * 0.55} x2={centerX + building.width * 0.16} y2={building.y + building.height * 0.95} stroke="#f0d3b7" strokeWidth="1.5" />
          <line x1={centerX + building.width * 0.16} y1={building.y + building.height * 0.55} x2={centerX - building.width * 0.16} y2={building.y + building.height * 0.95} stroke="#f0d3b7" strokeWidth="1.5" />
        </g>
      ) : null}
      {building.source.kind === "market" ? (
        <g>
          {/* Awning stretched across the building width */}
          <rect x={building.x + building.width * 0.06} y={building.y + building.height * 0.18} width={building.width - building.width * 0.12} height={building.height * 0.25} fill="#d94135" rx="1.5" />
          {Array.from({ length: 5 }).map((_, i) => (
            <rect
              key={i}
              x={building.x + building.width * 0.12 + i * building.width * 0.15}
              y={building.y + building.height * 0.18}
              width={building.width * 0.08}
              height={building.height * 0.25}
              fill="#ffffff"
            />
          ))}
          {/* Storefront Display Window */}
          <rect x={building.x + building.width * 0.1} y={building.y + building.height * 0.55} width={building.width * 0.38} height={building.height * 0.38} rx="1" fill="#e0f7fa" stroke="#00838f" strokeWidth="1" />
          <line x1={building.x + building.width * 0.29} y1={building.y + building.height * 0.55} x2={building.x + building.width * 0.29} y2={building.y + building.height * 0.93} stroke="#00838f" strokeWidth="1" />
          {/* Entrance Door */}
          <rect x={building.x + building.width * 0.58} y={building.y + building.height * 0.52} width={building.width * 0.24} height={building.height * 0.42} rx="1.5" fill="#8d6e63" stroke="#4e342e" strokeWidth="1.5" />
        </g>
      ) : null}
      {building.source.kind === "factory" ? (
        <g>
          {/* Sawtooth Roofline */}
          <path
            d={`M ${building.x + building.width * 0.08} ${building.y + building.height * 0.4} L ${building.x + building.width * 0.32} ${building.y + building.height * 0.15} L ${building.x + building.width * 0.32} ${building.y + building.height * 0.4} L ${building.x + building.width * 0.56} ${building.y + building.height * 0.15} L ${building.x + building.width * 0.56} ${building.y + building.height * 0.4} L ${building.x + building.width * 0.8} ${building.y + building.height * 0.15} L ${building.x + building.width * 0.8} ${building.y + building.height * 0.4} Z`}
            fill="#cfd8dc"
            stroke="#37474f"
            strokeWidth="1.5"
          />
          {/* Smokestack emitting clouds */}
          <rect x={building.x + building.width * 0.74} y={building.y - building.height * 0.22} width={building.width * 0.1} height={building.height * 0.36} fill="#4f5b66" stroke="#2c3539" strokeWidth="1" rx="0.5" />
          <rect x={building.x + building.width * 0.72} y={building.y - building.height * 0.25} width={building.width * 0.14} height={building.height * 0.06} fill="#ff7f24" rx="0.5" />
          <circle cx={building.x + building.width * 0.78} cy={building.y - building.height * 0.34} r={Math.min(building.width, building.height) * 0.1} fill="#eceff1" opacity="0.6" />
          <circle cx={building.x + building.width * 0.86} cy={building.y - building.height * 0.46} r={Math.min(building.width, building.height) * 0.14} fill="#eceff1" opacity="0.4" />
          {/* Garage shutter metal door */}
          <rect x={centerX - building.width * 0.2} y={building.y + building.height * 0.55} width={building.width * 0.4} height={building.height * 0.4} fill="#90a4ae" stroke="#37474f" strokeWidth="1.5" rx="1" />
          <line x1={centerX - building.width * 0.2} y1={building.y + building.height * 0.65} x2={centerX + building.width * 0.2} y2={building.y + building.height * 0.65} stroke="#37474f" strokeWidth="1" />
          <line x1={centerX - building.width * 0.2} y1={building.y + building.height * 0.75} x2={centerX + building.width * 0.2} y2={building.y + building.height * 0.75} stroke="#37474f" strokeWidth="1" />
          <line x1={centerX - building.width * 0.2} y1={building.y + building.height * 0.85} x2={centerX + building.width * 0.2} y2={building.y + building.height * 0.85} stroke="#37474f" strokeWidth="1" />
        </g>
      ) : null}
      {building.source.kind === "power_plant" ? (
        <g>
          {/* Cooling Tower Neoclassical Blueprint */}
          <path
            d={`M ${building.x + building.width * 0.15} ${building.y + building.height * 0.9} L ${building.x + building.width * 0.26} ${building.y + building.height * 0.15} H ${building.x + building.width * 0.74} L ${building.x + building.width * 0.85} ${building.y + building.height * 0.9} Z`}
            fill="#5b6e7a"
            stroke="#2f3a40"
            strokeWidth="1.5"
          />
          {/* Rim safety hazard stripes */}
          <rect x={building.x + building.width * 0.26} y={building.y + building.height * 0.15} width={building.width * 0.48} height={building.height * 0.08} fill="#ffca28" />
          <line x1={building.x + building.width * 0.34} y1={building.y + building.height * 0.15} x2={building.x + building.width * 0.4} y2={building.y + building.height * 0.23} stroke="#000000" strokeWidth="2" />
          <line x1={building.x + building.width * 0.48} y1={building.y + building.height * 0.15} x2={building.x + building.width * 0.54} y2={building.y + building.height * 0.23} stroke="#000000" strokeWidth="2" />
          <line x1={building.x + building.width * 0.62} y1={building.y + building.height * 0.15} x2={building.x + building.width * 0.68} y2={building.y + building.height * 0.23} stroke="#000000" strokeWidth="2" />
          {/* Yellow lightning bolt emblem */}
          <polygon
            points={`${centerX - building.width * 0.04},${centerY - building.height * 0.12} ${centerX + building.width * 0.05},${centerY - building.height * 0.12} ${centerX - building.width * 0.01},${centerY + building.height * 0.02} ${centerX + building.width * 0.04},${centerY + building.height * 0.02} ${centerX - building.width * 0.05},${centerY + building.height * 0.18} ${centerX - building.width * 0.01},${centerY + building.height * 0.05} ${centerX - building.width * 0.05},${centerY + building.height * 0.05}`}
            fill="#ffca28"
            stroke="#b78a00"
            strokeWidth="0.8"
          />
        </g>
      ) : null}
      {building.source.kind === "park" ? (
        <g>
          {/* Multi-toned nested tree circles */}
          <circle cx={centerX} cy={centerY - building.height * 0.08} r={Math.min(building.width, building.height) * 0.32} fill="#2e7d32" opacity="0.85" />
          <circle cx={centerX - building.width * 0.18} cy={centerY + building.height * 0.08} r={Math.min(building.width, building.height) * 0.24} fill="#388e3c" opacity="0.9" />
          <circle cx={centerX + building.width * 0.18} cy={centerY + building.height * 0.08} r={Math.min(building.width, building.height) * 0.22} fill="#4caf50" opacity="0.85" />
          {/* Dynamic park pond */}
          <ellipse cx={centerX} cy={building.y + building.height * 0.74} rx={building.width * 0.28} ry={building.height * 0.16} fill="#0288d1" stroke="#01579b" strokeWidth="1" />
        </g>
      ) : null}
      <circle
        className="top-marker"
        cx={centerX}
        cy={building.y - 4}
        r="12"
        style={{ fill: selected ? "#f3a62d" : markerColors[building.source.kind] }}
      />
      <text className="top-marker-text" x={centerX} y={building.y} textAnchor="middle">{building.marker}</text>
    </g>
  );
}

function buildTopDownMapPlan(layout: CityMapLayout, state: WorldState): TopDownPlan {
  const expansion = Math.max(0, Math.min(4, Math.floor((state.land_used - 58) / 10)));
  const width = 980 + expansion * 210;
  const height = Math.round(width / MAP_REFERENCE_ASPECT_RATIO);
  const margin = 76;
  const roads = topRoads(width, height, expansion);
  const paths = topPaths(width, height);
  const districtBuildings = layout.buildings.flatMap((building, districtIndex) =>
    placeDistrictBuildings(building, districtZone(building.kind, width, height, expansion), districtIndex)
  );
  const buildings = districtBuildings.map((building, index) => ({
    ...building,
    marker: 1 + index
  }));
  const fields = buildings
    .filter((building) => building.source.kind === "farm")
    .map((building, index) => {
      const fW = building.width * 0.9;
      const fH = building.height * 0.35;
      return {
        id: `field-${index}`,
        x: building.x + (building.width - fW) / 2,
        y: building.y + building.height + Math.max(1, building.height * 0.05),
        width: fW,
        height: fH,
        rotation: building.rotation,
        kind: "farm" as MapTileKind
      };
    });
  const parking = [
    { id: "parking-market", x: width * 0.58, y: height * 0.54, width: 112, height: 58, rotation: 0 },
    { id: "parking-power", x: width * 0.72, y: height * 0.74, width: 138, height: 62, rotation: -2 },
    ...(expansion >= 2 ? [{ id: "parking-north", x: width * 0.72, y: height * 0.16, width: 120, height: 58, rotation: 1 }] : [])
  ];
  const trees = topTrees(width, height, margin, buildings);

  return { width, height, roads, paths, parking, fields, trees, buildings };
}

function topRoads(width: number, height: number, expansion: number): MapPath[] {
  const x1 = width * 0.25;
  const x2 = width * 0.51;
  const x3 = width * 0.76;
  const y1 = height * 0.18;
  const y2 = height * 0.43;
  const y3 = height * 0.68;
  return [
    { id: "north", d: `M 0 ${y1} H ${width}`, width: 34 },
    { id: "middle", d: `M 0 ${y2} H ${width}`, width: 42 },
    { id: "south", d: `M 0 ${y3} C ${width * 0.24} ${y3 - 28}, ${width * 0.42} ${y3 + 40}, ${width} ${y3 + 12}`, width: 42 },
    { id: "west", d: `M ${x1} 0 V ${height}`, width: 34 },
    { id: "center", d: `M ${x2} 0 V ${height}`, width: 38 },
    { id: "east", d: `M ${x3} 0 V ${height}`, width: 34 },
    ...(expansion >= 1 ? [{ id: "expansion-east", d: `M ${width * 0.89} ${height * 0.04} V ${height * 0.92}`, width: 30 }] : []),
    ...(expansion >= 2 ? [{ id: "expansion-south", d: `M ${width * 0.08} ${height * 0.84} H ${width * 0.94}`, width: 32 }] : [])
  ];
}

function topPaths(width: number, height: number): MapPath[] {
  return [
    { id: "quad-loop", d: `M ${width * 0.34} ${height * 0.28} C ${width * 0.44} ${height * 0.18}, ${width * 0.58} ${height * 0.22}, ${width * 0.64} ${height * 0.34} C ${width * 0.54} ${height * 0.48}, ${width * 0.41} ${height * 0.49}, ${width * 0.34} ${height * 0.28}`, width: 7 },
    { id: "park-cross-1", d: `M ${width * 0.34} ${height * 0.28} L ${width * 0.64} ${height * 0.34}`, width: 5 },
    { id: "park-cross-2", d: `M ${width * 0.49} ${height * 0.21} L ${width * 0.48} ${height * 0.51}`, width: 5 },
    { id: "farm-path", d: `M ${width * 0.18} ${height * 0.62} C ${width * 0.28} ${height * 0.58}, ${width * 0.36} ${height * 0.75}, ${width * 0.49} ${height * 0.66}`, width: 5 }
  ];
}

function districtZone(kind: MapTileKind, width: number, height: number, expansion: number): MapRect {
  const zones: Partial<Record<MapTileKind, MapRect>> = {
    residential: { id: "zone-residential", x: width * 0.08, y: height * 0.08, width: width * 0.34, height: height * 0.27 },
    market: { id: "zone-market", x: width * 0.54, y: height * 0.22, width: width * 0.22, height: height * 0.22 },
    factory: { id: "zone-factory", x: width * 0.73, y: height * 0.1, width: width * 0.2, height: height * 0.28 },
    government: { id: "zone-government", x: width * 0.41, y: height * 0.42, width: width * 0.18, height: height * 0.18 },
    park: { id: "zone-park", x: width * 0.28, y: height * 0.22, width: width * 0.22, height: height * 0.2 },
    farm: { id: "zone-farm", x: width * 0.08, y: height * 0.55, width: width * (0.34 + expansion * 0.02), height: height * 0.26 },
    power_plant: { id: "zone-power", x: width * 0.62, y: height * 0.62, width: width * 0.28, height: height * 0.12 }
  };
  return zones[kind] ?? { id: `zone-${kind}`, x: width * 0.12, y: height * 0.12, width: width * 0.2, height: height * 0.2 };
}

function placeDistrictBuildings(building: MapBuilding, zone: MapRect, districtIndex: number): TopDownBuilding[] {
  if (building.kind === "government") {
    return [{
      id: `${building.id}-main`,
      source: building,
      marker: 0,
      x: zone.x + zone.width * 0.12,
      y: zone.y + zone.height * 0.04,
      width: zone.width * 0.72,
      height: zone.height * 0.72,
      rotation: 0,
      kind: building.kind
    }];
  }

  const visibleUnits = Math.max(1, building.units);
  const cols = Math.ceil(Math.sqrt(visibleUnits * (zone.width / Math.max(zone.height, 1))));
  const rows = Math.ceil(visibleUnits / cols);
  const cellW = zone.width / Math.max(cols, 1);
  const cellH = zone.height / Math.max(rows, 1);
  return Array.from({ length: visibleUnits }).map((_, index) => {
    const col = index % cols;
    const row = Math.floor(index / cols);
    const size = buildingSize(building.kind, cellW, cellH);
    const spaceX = cellW - size.width;
    const spaceY = cellH - size.height;
    const jitterX = spaceX > 0 ? (pseudoJitter(index + districtIndex * 7, 0.28) - 0.5) * spaceX * 0.65 : 0;
    const jitterY = spaceY > 0 ? (pseudoJitter(index + districtIndex * 11, 0.36) - 0.5) * spaceY * 0.65 : 0;
    return {
      id: `${building.id}-${index}`,
      source: building,
      marker: 0,
      x: zone.x + col * cellW + Math.max(0, (cellW - size.width) / 2) + jitterX,
      y: zone.y + row * cellH + Math.max(0, (cellH - size.height) / 2) + jitterY,
      width: size.width,
      height: size.height,
      rotation: building.kind === "farm" ? -3 + (index % 3) * 2 : index % 2 === 0 ? 0 : 1.5,
      kind: building.kind
    };
  });
}

function buildingSize(kind: MapTileKind, cellW?: number, cellH?: number) {
  let base = { width: 74, height: 48 };
  if (kind === "residential") base = { width: 66, height: 42 };
  else if (kind === "farm") base = { width: 76, height: 38 };
  else if (kind === "factory") base = { width: 86, height: 58 };
  else if (kind === "market") base = { width: 72, height: 52 };
  else if (kind === "power_plant") base = { width: 118, height: 70 };
  else if (kind === "park") base = { width: 64, height: 42 };

  if (typeof cellW === "number" && typeof cellH === "number") {
    // Proportional scaling algorithm:
    // Scale down if base size is larger than cell size (with some padding, e.g. 12% of cell size)
    const paddingW = Math.max(8, cellW * 0.12);
    const paddingH = Math.max(6, cellH * 0.12);
    const maxW = Math.max(20, cellW - paddingW);
    let maxH = Math.max(20, cellH - paddingH);
    if (kind === "farm") {
      maxH = Math.max(12, (cellH - paddingH) / 1.6);
    }
    
    const scaleW = maxW / base.width;
    const scaleH = maxH / base.height;
    const scale = Math.min(1.0, scaleW, scaleH);
    
    return {
      width: Math.max(16, Math.round(base.width * scale)),
      height: Math.max(12, Math.round(base.height * scale))
    };
  }
  return base;
}

function topTrees(width: number, height: number, margin: number, buildings: TopDownBuilding[]): MapPoint[] {
  const trees: MapPoint[] = [];
  for (let i = 0; i < 130; i += 1) {
    const edge = i % 4;
    const x = edge === 0 ? margin * pseudoJitter(i, 0.7) : edge === 1 ? width - margin * pseudoJitter(i, 0.8) : margin + pseudoJitter(i, 0.33) * (width - margin * 2);
    const y = edge === 2 ? margin * pseudoJitter(i, 0.6) : edge === 3 ? height - margin * pseudoJitter(i, 0.55) : margin + pseudoJitter(i, 0.44) * (height - margin * 2);
    if (buildings.some((building) => x > building.x - 34 && x < building.x + building.width + 34 && y > building.y - 34 && y < building.y + building.height + 34)) {
      continue;
    }
    trees.push({ id: `tree-${i}`, x, y, size: 7 + pseudoJitter(i, 0.22) * 7 });
  }
  return trees;
}

function pseudoJitter(index: number, salt: number) {
  const value = Math.sin(index * 12.9898 + salt * 78.233) * 43758.5453;
  return value - Math.floor(value);
}

function rectTransform(rect: { x: number; y: number; width: number; height: number; rotation?: number }) {
  const rotation = rect.rotation ?? 0;
  if (!rotation) {
    return undefined;
  }
  return `rotate(${rotation} ${rect.x + rect.width / 2} ${rect.y + rect.height / 2})`;
}

function selectedKindsForZone(zone: string) {
  const kinds = new Set<MapTileKind>();
  Object.entries(TILE_ZONE_LABELS).forEach(([kind, label]) => {
    if (label === zone) {
      kinds.add(kind as MapTileKind);
    }
  });
  return kinds;
}

function countMapTiles(tiles: MapTile[]) {
  const counts = { ...EMPTY_TILE_COUNTS };
  tiles.forEach((tile) => {
    counts[tile.kind] += 1;
  });
  return counts;
}

function Impact({
  icon,
  label,
  value,
  danger = false
}: {
  icon: ReactNode;
  label: string;
  value: string;
  danger?: boolean;
}) {
  return (
    <div className={`impact ${danger ? "danger-impact" : ""}`}>
      <span>{icon}</span>
      <strong>{value}</strong>
      <em>{label}</em>
    </div>
  );
}

function AlertRow({ level, text }: { level: EventSeverity; text: string }) {
  return (
    <div className={`alert-row alert-${level}`}>
      <AlertTriangle size={17} />
      <span>{text}</span>
    </div>
  );
}

function BuildCard({
  icon,
  name,
  cost,
  land,
  tone,
  onBuild,
  disabled = false
}: {
  icon: ReactNode;
  name: string;
  cost: string;
  land: string;
  tone: string;
  onBuild?: () => void;
  disabled?: boolean;
}) {
  return (
    <button className={`build-card build-${tone}`} type="button" disabled={disabled} onClick={onBuild}>
      <strong>{name}</strong>
      <div>
        <span>{icon}</span>
        <p>
          Cost: {cost}
          <br />
          Land: {land}
        </p>
      </div>
    </button>
  );
}

function decisionIcon(action: ActionName) {
  if (action === "subsidize") return <DollarSign />;
  if (action === "build_factory") return <Factory />;
  if (action === "build_market") return <Store />;
  if (action === "build_power_plant") return <Zap />;
  if (action === "build_housing") return <House />;
  if (action === "build_road") return <Hammer />;
  return <Wheat />;
}

function actionCost(action: ActionName, state: WorldState, params: Params) {
  const buildingType = ACTION_BUILDING_TYPES[action];
  if (buildingType) {
    return formatCost(BUILDING_COSTS[buildingType]);
  }
  if (action === "subsidize") {
    return formatCost(subsidyCost(state, params));
  }
  return "$0";
}

function canAffordAction(action: ActionName, state: WorldState, params: Params) {
  const buildingType = ACTION_BUILDING_TYPES[action];
  if (buildingType) {
    return canBuildType(buildingType, state);
  }
  if (action === "subsidize") {
    return state.price > params.min_price && state.treasury >= subsidyCost(state, params);
  }
  return true;
}

function canBuildType(type: BuildingType, state: WorldState) {
  const landRemaining = state.land_total - state.land_used;
  return state.treasury >= BUILDING_COSTS[type] && landRemaining >= BUILDING_LAND_COSTS[type];
}

function subsidyCost(state: WorldState, params: Params) {
  const subsidizedPrice = Math.max(params.min_price, Math.min(params.max_price, state.price * 0.9));
  const support = Math.max(0, state.price - subsidizedPrice);
  return support * state.food_demand * params.subsidy_spending_scale;
}

function formatCost(value: number) {
  if (value <= 0) {
    return "$0";
  }
  return `-${formatMoney(value).replace("$ ", "$")}`;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

function formatMoney(value: number): string {
  if (value >= 1_000_000) {
    return `$ ${(value / 1_000_000).toFixed(2)}M`;
  }

  if (value >= 1_000) {
    return `$ ${(value / 1_000).toFixed(0)}K`;
  }

  return `$ ${value.toFixed(0)}`;
}

function formatPrice(value: number): string {
  return `$ ${value.toFixed(1)}`;
}

function formatSignedPrice(value: number): string {
  if (value === 0) {
    return "$0";
  }

  return `${value > 0 ? "+" : "-"}$${Math.abs(value).toFixed(2)}`;
}

function signed(value: number): string {
  if (value === 0) {
    return "0";
  }

  return `${value > 0 ? "+" : ""}${value.toFixed(value % 1 === 0 ? 0 : 1)}`;
}

function formatScoreDelta(value: number): string {
  if (value === 0) {
    return "0";
  }

  return `${value > 0 ? "+" : ""}${value}`;
}

function impactTone(
  metric: "food" | "price" | "happiness" | "mayor",
  value?: number
): "good" | "bad" | "neutral" | "pending" {
  if (typeof value !== "number") {
    return "pending";
  }

  if (Math.abs(value) < 0.0001) {
    return "neutral";
  }

  const helped = metric === "price" ? value < 0 : value > 0;
  return helped ? "good" : "bad";
}

function metricTitle(label: string, before: number, after?: number | null): string {
  if (typeof after !== "number") {
    return `${label}: waiting for next tick`;
  }

  return `${label}: ${before.toFixed(2)} to ${after.toFixed(2)}`;
}

function formatTraceDelta(value: number): string {
  if (Math.abs(value) < 0.0001) {
    return "steady";
  }

  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

function formatNodeValue(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatTime(tickValue: number): string {
  const hours = (8 + Math.floor(tickValue / 2)) % 24;
  const minutes = tickValue % 2 === 0 ? "00" : "30";
  const suffix = hours >= 12 ? "PM" : "AM";
  const hour12 = hours % 12 === 0 ? 12 : hours % 12;
  return `${hour12}:${minutes} ${suffix}`;
}

export default App;
