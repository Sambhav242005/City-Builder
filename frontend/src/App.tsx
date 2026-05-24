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
  advanceTicks,
  approveGovernmentAction,
  buildStructure,
  fetchOptimizerTrainingReport,
  fetchState,
  liveUrl,
  pauseLive,
  playLive,
  rejectGovernmentAction,
  reset,
  tick
} from "./api";
import { CityCanvasMap, CITY_CANVAS_BUILD_MENU_ASSETS, buildCityCanvasMapPlan } from "./CityCanvasMap";
import { attachExperimentDebugTools, resolveExperimentAssignment, trackExperimentEvent } from "./experiments";

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
  OptimizerTrainingReport,
  OptimizerTrainingScenario,
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

type StatTone = "neutral" | "good" | "watch" | "danger";

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
const MAP_STAGE_MAX_WIDTH = 1180;
const MAP_STAGE_PADDING = 32;
const CITY_TILE_SIZE = 160;

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

const BUILD_MENU_ASSETS: Record<BuildingType, string> = {
  ...CITY_CANVAS_BUILD_MENU_ASSETS
};

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
  const experiment = useMemo(() => resolveExperimentAssignment(), []);
  const [data, setData] = useState<StateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [trainingReport, setTrainingReport] = useState<OptimizerTrainingReport | null>(null);
  const [trainingReportError, setTrainingReportError] = useState<string | null>(null);
  const [selectedZone, setSelectedZone] = useState("Available Land");
  const [selectedBuildingId, setSelectedBuildingId] = useState<string | null>(null);
  const [showMapOverlay, setShowMapOverlay] = useState(true);
  const running = data?.simulation.running ?? false;

  useEffect(() => {
    attachExperimentDebugTools(experiment);
    trackExperimentEvent(experiment, "page_view", {
      path: window.location.pathname,
      search: window.location.search || null
    });
  }, [experiment]);

  useEffect(() => {
    fetchState()
      .then((payload) => {
        commitState(payload);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    fetchOptimizerTrainingReport()
      .then((payload) => {
        setTrainingReport(payload);
        setTrainingReportError(null);
      })
      .catch((err: Error) => setTrainingReportError(err.message));
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
      <main className={`app-shell loading-screen experiment-${experiment.variant}`} data-experiment-key={experiment.key} data-experiment-variant={experiment.variant}>
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
  const happinessTone: StatTone = state.happiness >= 0.75 ? "good" : state.happiness >= 0.55 ? "watch" : "danger";
  const mayorTone: StatTone = data.mayorScore.status === "off_track" ? "danger" : data.mayorScore.status === "watch" ? "watch" : "good";
  const treasuryTone: StatTone = treasury < 50_000 ? "watch" : "neutral";
  const selectedBuilding = selectedBuildingId
    ? data.cityMap.buildings.find((building) => building.id === selectedBuildingId) ?? null
    : null;
  const selectedMapLabel = selectedBuilding?.label ?? selectedZone;
  const selectedZoneData = selectedBuilding ? getBuildingData(selectedBuilding) : getZoneData(selectedZone, state);
  const mapTileCounts = countMapTiles(data.cityMap.tiles);

  async function handleUpdate(action: () => Promise<StateResponse>) {
    try {
      const payload = await action();
      commitState(payload);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    }
  }

  function handlePlayPause() {
    trackExperimentEvent(experiment, "simulation_control", {
      action: running ? "pause" : "play",
      tick: state?.tick ?? null
    });
    return handleUpdate(running ? pauseLive : playLive);
  }

  function handleAdvanceOneTick() {
    trackExperimentEvent(experiment, "simulation_control", {
      action: "advance_one",
      tick: state?.tick ?? null
    });
    return handleUpdate(tick);
  }

  function handleAdvanceFaster() {
    trackExperimentEvent(experiment, "simulation_control", {
      action: "advance_fast",
      tick: state?.tick ?? null,
      ticks: data?.simulation.fastForwardTicks ?? 5
    });
    return handleUpdate(() => advanceTicks(data?.simulation.fastForwardTicks ?? 5));
  }

  function handleResetSimulation() {
    trackExperimentEvent(experiment, "simulation_control", {
      action: "reset",
      tick: state?.tick ?? null
    });
    return handleUpdate(reset);
  }

  function handleBuild(buildingType: BuildingType) {
    trackExperimentEvent(experiment, "build_attempt", {
      buildingType,
      tick: state?.tick ?? null,
      treasury: state?.treasury ?? null,
      landRemaining: state ? state.land_total - state.land_used : null
    });
    return handleUpdate(() => buildStructure(buildingType));
  }

  function handleDecision(decision: "approve" | "reject") {
    trackExperimentEvent(experiment, "mayor_decision", {
      decision,
      recommendedAction: recommendation?.action ?? null,
      tick: state?.tick ?? null
    });
    return handleUpdate(decision === "approve" ? approveGovernmentAction : rejectGovernmentAction);
  }

  function commitState(payload: StateResponse) {
    setData(payload);
  }


  return (
    <main
      className={`app-shell experiment-${experiment.variant}`}
      data-experiment-key={experiment.key}
      data-experiment-variant={experiment.variant}
    >
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
          tone={happinessTone}
        />
        <StatCard label="Mayor Direction" value={`${data.mayorScore.score}/100`} trend={data.mayorScore.label} icon={<TrendingUp />} tone={mayorTone} />
        <StatCard label="GDP" value={formatMoney(gdp)} trend={gdpTrend} icon={<TrendingUp />} />
        <StatCard label="Treasury" value={formatMoney(treasury)} trend={treasuryTrend} icon={<CircleDollarSign />} tone={treasuryTone} />

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
              onClick={handlePlayPause}
            >
              {running ? <Pause size={18} /> : <Play size={18} />}
            </IconButton>
            <IconButton label="Advance one tick" onClick={handleAdvanceOneTick}>
              <Play size={18} />
            </IconButton>
            <IconButton label="Advance faster" onClick={handleAdvanceFaster}>
              <FastForward size={18} />
            </IconButton>
            <IconButton label="Reset simulation" onClick={handleResetSimulation}>
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

        <section className="center-column">
          <section className="map-column">
            <Panel title="City Map" flush>
              <div className="city-map">
                <CityMapBoard
                  layout={data.cityMap}
                  selectedZone={selectedZone}
                  selectedBuildingId={selectedBuildingId}
                  onSelectZone={(zone) => {
                    trackExperimentEvent(experiment, "map_select", {
                      target: "zone",
                      zone,
                      tick: state.tick
                    });
                    setSelectedZone(zone);
                    setSelectedBuildingId(null);
                  }}
                  onSelectBuilding={(building) => {
                    trackExperimentEvent(experiment, "map_select", {
                      target: "building",
                      buildingKind: building.kind,
                      units: building.units,
                      tick: state.tick
                    });
                    setSelectedBuildingId(building.id);
                    setSelectedZone(TILE_ZONE_LABELS[building.kind]);
                  }}
                  showOverlay={showMapOverlay}
                  setShowOverlay={setShowMapOverlay}
                />
                {showMapOverlay ? (
                  <>
                    <aside className="legend-card" aria-label="City map legend">
                      {CITY_MAP_LEGEND.map((item) => (
                        <LegendItem
                          key={item.label}
                          icon={item.icon}
                          color={item.color}
                          label={item.label}
                          count={item.kinds.reduce((total, kind) => total + mapTileCounts[kind], 0)}
                        />
                      ))}
                    </aside>
                    <aside className="map-status-card" aria-label="Land status">
                      <span>Open Land</span>
                      <strong>{landRemaining}</strong>
                      <em>{state.land_total} total tiles</em>
                    </aside>
                    <MapInspector label={selectedMapLabel} zoneData={selectedZoneData} building={selectedBuilding} />
                  </>
                ) : null}
              </div>
            </Panel>
          </section>

          <section className="build-panel">
            <Panel title="Build Menu">
              <div className="build-menu">
                <BuildCard icon={<Wheat />} assetSrc={BUILD_MENU_ASSETS.farm} name="Farm" cost={formatCost(BUILDING_COSTS.farm)} land={`${BUILDING_LAND_COSTS.farm}`} tone="green" disabled={!canBuildType("farm", state)} onBuild={() => handleBuild("farm")} />
                <BuildCard icon={<Factory />} assetSrc={BUILD_MENU_ASSETS.factory} name="Factory" cost={formatCost(BUILDING_COSTS.factory)} land={`${BUILDING_LAND_COSTS.factory}`} tone="purple" disabled={!canBuildType("factory", state)} onBuild={() => handleBuild("factory")} />
                <BuildCard icon={<Store />} assetSrc={BUILD_MENU_ASSETS.market} name="Market" cost={formatCost(BUILDING_COSTS.market)} land={`${BUILDING_LAND_COSTS.market}`} tone="gold" disabled={!canBuildType("market", state)} onBuild={() => handleBuild("market")} />
                <BuildCard icon={<Zap />} assetSrc={BUILD_MENU_ASSETS.power_plant} name="Power Plant" cost={formatCost(BUILDING_COSTS.power_plant)} land={`${BUILDING_LAND_COSTS.power_plant}`} tone="steel" disabled={!canBuildType("power_plant", state)} onBuild={() => handleBuild("power_plant")} />
                <BuildCard icon={<House />} assetSrc={BUILD_MENU_ASSETS.housing} name="Housing" cost={formatCost(BUILDING_COSTS.housing)} land={`${BUILDING_LAND_COSTS.housing}`} tone="blue" disabled={!canBuildType("housing", state)} onBuild={() => handleBuild("housing")} />
                <BuildCard icon={<Hammer />} assetSrc={BUILD_MENU_ASSETS.road} name="Road" cost={formatCost(BUILDING_COSTS.road)} land={`${BUILDING_LAND_COSTS.road}`} tone="road" disabled={!canBuildType("road", state)} onBuild={() => handleBuild("road")} />
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

          <Panel title="Offline Validation">
            <OfflineValidationPanel report={trainingReport} error={trainingReportError} />
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
                onClick={() => handleDecision("approve")}
              >
                <Check size={16} />
                Approve
              </button>
              <button
                className="reject-button"
                type="button"
                disabled={!actionIsAvailable}
                onClick={() => handleDecision("reject")}
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
  icon,
  tone = "neutral"
}: {
  label: string;
  value: string;
  trend: string;
  icon: ReactNode;
  tone?: StatTone;
}) {
  return (
    <section className={`stat-card stat-${tone}`}>
      <div className="stat-hidden-icon">{icon}</div>
      <div className="stat-label-row">
        <span>{label}</span>
      </div>
      <div className="stat-value-row">
        <strong>{value}</strong>
        <em>{trend}</em>
      </div>
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
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [chartReady, setChartReady] = useState(false);

  useEffect(() => {
    const node = chartRef.current;
    if (!node) {
      return;
    }

    const updateSize = () => {
      const rect = node.getBoundingClientRect();
      const hasSize = rect.width > 0 && rect.height > 0;
      setChartReady((current) => (current === hasSize ? current : hasSize));
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="chart-box" ref={chartRef} style={{ height, minHeight: height, minWidth: 0, width: "100%" }}>
      {chartReady ? (
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      ) : null}
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
  const visibleNodes = nodes.slice(0, 5);
  return (
    <div className="trace-block">
      <div className="trace-block-title">
        <span>Node Updates</span>
        <em>{nodes.length > visibleNodes.length ? `${visibleNodes.length} of ${nodes.length}` : `${visibleNodes.length} active`}</em>
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

function OfflineValidationPanel({
  report,
  error
}: {
  report: OptimizerTrainingReport | null;
  error: string | null;
}) {
  if (error) {
    return (
      <div className="scorecard-empty">
        <AlertTriangle size={18} />
        <span>{error}</span>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="scorecard-empty">
        <Cpu size={18} />
        <span>Loading offline validation report...</span>
      </div>
    );
  }

  const summary = report.summary;
  const allPassed = summary.allScenariosPassed;

  return (
    <div className="offline-validation" aria-label="Offline optimizer validation report">
      <div className={`validation-summary ${allPassed ? "validation-pass" : "validation-fail"}`}>
        <div>
          <span>{formatReportDate(report.generatedAt)}</span>
          <strong>{report.policyVersion}</strong>
          <em>
            {summary.validationScenariosPassed}/{summary.validationScenarios} scenarios
          </em>
        </div>
        <b>
          {allPassed ? <Check size={14} /> : <X size={14} />}
          {allPassed ? "All passed" : "Review"}
        </b>
      </div>

      <div className="validation-kpis">
        <TraceMetric label="States" value={formatNumber(summary.statesLearned)} />
        <TraceMetric label="Reward" value={summary.averageEpisodeReward.toFixed(3)} />
      </div>

      <div className="validation-scenarios">
        {report.scenarios.map((scenario) => (
          <ValidationScenarioCard key={scenario.name} scenario={scenario} />
        ))}
      </div>
    </div>
  );
}

function ValidationScenarioCard({ scenario }: { scenario: OptimizerTrainingScenario }) {
  const selectedIsExpected = scenario.expectedActions.includes(scenario.selectedAction);

  return (
    <article className={`validation-scenario ${scenario.passed ? "validation-pass" : "validation-fail"}`}>
      <div className="validation-scenario-head">
        <span className={`validation-chip ${scenario.passed ? "validation-chip-pass" : "validation-chip-fail"}`}>
          {scenario.passed ? <Check size={12} /> : <X size={12} />}
          {scenario.passed ? "Pass" : "Fail"}
        </span>
        <strong>{formatScenarioName(scenario.name)}</strong>
        <em>{formatPercent(scenario.confidence)}</em>
      </div>

      <p>{scenario.description}</p>

      <div className="validation-actions">
        <div>
          <span>Selected</span>
          <strong>{ACTION_LABELS[scenario.selectedAction]}</strong>
          <em>{selectedIsExpected ? "expected" : "unexpected"}</em>
        </div>
        <div>
          <span>Baseline</span>
          <strong>{ACTION_LABELS[scenario.baselineAction]}</strong>
          <em>{scenario.stateKey}</em>
        </div>
      </div>

      <div className="validation-margins">
        <span>Q {formatMargin(scenario.qMarginVsBaseline)}</span>
        <span>Validation {formatMargin(scenario.validationMarginVsBaseline)}</span>
      </div>
    </article>
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
          <span className="supply-chain-icon" aria-hidden="true">
            <Wheat size={16} />
          </span>
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
          <span className="supply-chain-icon" aria-hidden="true">
            <Package size={16} />
          </span>
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
          <span className="supply-chain-icon" aria-hidden="true">
            <CircleDollarSign size={16} />
          </span>
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
  selectedZone,
  selectedBuildingId,
  onSelectZone,
  onSelectBuilding,
  showOverlay,
  setShowOverlay
}: {
  layout: CityMapLayout;
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
  const selectedKinds = useMemo(() => selectedKindsForZone(selectedZone), [selectedZone]);
  const plan = useMemo(() => buildCityCanvasMapPlan(layout, CITY_TILE_SIZE), [layout]);
  const stageAspectRatio = plan.width / plan.height;
  const stageWidth = useMemo(() => {
    if (!viewportSize.width || !viewportSize.height) {
      return undefined;
    }

    const widthBound = Math.max(680, viewportSize.width * 1.45);
    const heightBound = Math.max(220, (viewportSize.height - MAP_STAGE_PADDING * 2) * stageAspectRatio);
    return Math.min(MAP_STAGE_MAX_WIDTH, widthBound, heightBound);
  }, [stageAspectRatio, viewportSize]);

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

  function selectZone(zone: string) {
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }

    onSelectZone(zone);
  }

  const stageStyle = {
    width: stageWidth ? `${stageWidth}px` : "min(1180px, calc(100% - 32px))",
    transform: `translate(-50%, -50%) translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
    "--map-aspect-ratio": stageAspectRatio.toString()
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
        className="canvas-map-stage"
        style={stageStyle}
      >
        <CityCanvasMap
          plan={plan}
          selectedKinds={selectedKinds}
          selectedBuildingId={selectedBuildingId}
          showOverlay={showOverlay}
          tileZoneLabels={TILE_ZONE_LABELS}
          onSelectBuilding={selectBuilding}
          onSelectZone={selectZone}
        />
      </div>
    </div>
  );
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
  assetSrc,
  name,
  cost,
  land,
  tone,
  onBuild,
  disabled = false
}: {
  icon: ReactNode;
  assetSrc?: string;
  name: string;
  cost: string;
  land: string;
  tone: string;
  onBuild?: () => void;
  disabled?: boolean;
}) {
  return (
    <button className={`build-card build-${tone}`} type="button" disabled={disabled} onClick={onBuild}>
      <div className="build-card-head">
        <span className="build-card-icon">
          {assetSrc ? <img src={assetSrc} alt="" aria-hidden="true" /> : icon}
        </span>
        <strong>{name}</strong>
      </div>
      <div className="build-card-meta">
        <span>
          <em>Cost</em>
          <b>{cost}</b>
        </span>
        <span>
          <em>Land</em>
          <b>{land}</b>
        </span>
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

function formatReportDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(date);
}

function formatScenarioName(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatMargin(value: number): string {
  if (Math.abs(value) < 0.0005) {
    return "0.000";
  }

  return `${value > 0 ? "+" : ""}${value.toFixed(3)}`;
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
