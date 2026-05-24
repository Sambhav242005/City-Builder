import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";

import type { BuildingType, CityMapLayout, MapBuilding, MapTile, MapTileKind, RoadDirection } from "./types";

const CITY_CANVAS_ASSET_ROOT = "./assets/citybuilder-svg-mvp-v2/citybuilder_svg_mvp_v2/assets_png_128";

const cityCanvasAssetModules = import.meta.glob("./assets/citybuilder-svg-mvp-v2/citybuilder_svg_mvp_v2/assets_png_128/**/*.png", {
  eager: true,
  query: "?url",
  import: "default"
}) as Record<string, string>;

function cityCanvasAsset(relativePath: string) {
  return cityCanvasAssetModules[`${CITY_CANVAS_ASSET_ROOT}/${relativePath}`] ?? "";
}

const CITY_CANVAS_ASSETS = {
  grass_tile_a: cityCanvasAsset("terrain/grass_tile_a.png"),
  grass_tile_b: cityCanvasAsset("terrain/grass_tile_b.png"),
  dirt_tile: cityCanvasAsset("terrain/dirt_tile.png"),
  sand_tile: cityCanvasAsset("terrain/sand_tile.png"),
  farm_ground_tile: cityCanvasAsset("terrain/farm_ground_tile.png"),
  park_ground_tile: cityCanvasAsset("terrain/park_ground_tile.png"),
  water_tile: cityCanvasAsset("terrain/water_tile.png"),
  pond_tile: cityCanvasAsset("terrain/pond_tile.png"),
  road_straight: cityCanvasAsset("roads/road_straight.png"),
  zone_residential: cityCanvasAsset("overlays/zone_residential.png"),
  zone_commercial: cityCanvasAsset("overlays/zone_commercial.png"),
  zone_industrial: cityCanvasAsset("overlays/zone_industrial.png"),
  sidewalk_plaza: cityCanvasAsset("civic/sidewalk_plaza.png"),
  cottage_house: cityCanvasAsset("buildings/cottage_house.png"),
  suburban_house: cityCanvasAsset("buildings/suburban_house.png"),
  townhouse: cityCanvasAsset("buildings/townhouse.png"),
  apartment_block: cityCanvasAsset("buildings/apartment_block.png"),
  corner_shop: cityCanvasAsset("buildings/corner_shop.png"),
  grocery_store: cityCanvasAsset("buildings/grocery_store.png"),
  cafe: cityCanvasAsset("buildings/cafe.png"),
  office_building: cityCanvasAsset("buildings/office_building.png"),
  small_market: cityCanvasAsset("buildings/small_market.png"),
  clinic: cityCanvasAsset("buildings/clinic.png"),
  school: cityCanvasAsset("buildings/school.png"),
  police_station: cityCanvasAsset("buildings/police_station.png"),
  factory: cityCanvasAsset("buildings/factory.png"),
  warehouse: cityCanvasAsset("buildings/warehouse.png"),
  power_plant: cityCanvasAsset("buildings/power_plant.png"),
  water_plant: cityCanvasAsset("buildings/water_plant.png"),
  farm_barn: cityCanvasAsset("farms/farm_barn.png"),
  greenhouse: cityCanvasAsset("farms/greenhouse.png"),
  wheat_farm: cityCanvasAsset("farms/wheat_farm.png"),
  vegetable_farm: cityCanvasAsset("farms/vegetable_farm.png"),
  orchard_farm: cityCanvasAsset("farms/orchard_farm.png"),
  livestock_ranch: cityCanvasAsset("farms/livestock_ranch.png"),
  tree: cityCanvasAsset("props/tree.png"),
  bush_cluster: cityCanvasAsset("props/bush_cluster.png"),
  fountain: cityCanvasAsset("props/fountain.png"),
  streetlight: cityCanvasAsset("props/streetlight.png"),
  rock_cluster: cityCanvasAsset("props/rock_cluster.png"),
  car: cityCanvasAsset("props/car.png")
} as const;

type CityCanvasAssetId = keyof typeof CITY_CANVAS_ASSETS;
type CanvasImageMap = Partial<Record<CityCanvasAssetId, HTMLImageElement>>;
type ZoneOverlayId = "zone_residential" | "zone_commercial" | "zone_industrial";

type DrawConfig = {
  offsetX: number;
  offsetY: number;
  scale: number;
  rotation: number;
};

const DEFAULT_DRAW_CONFIG: DrawConfig = { offsetX: 0, offsetY: 0, scale: 1, rotation: 0 };

const DRAW_CONFIG: Partial<Record<CityCanvasAssetId, DrawConfig>> = {
  car: { offsetX: 0, offsetY: 0, scale: 0.46, rotation: 0 },
  streetlight: { offsetX: 0, offsetY: 0, scale: 0.52, rotation: 0 },
  tree: { offsetX: 0, offsetY: 0, scale: 0.88, rotation: 0 },
  bush_cluster: { offsetX: 0, offsetY: 0, scale: 0.82, rotation: 0 },
  rock_cluster: { offsetX: 0, offsetY: 0, scale: 0.7, rotation: 0 },
  fountain: { offsetX: 0, offsetY: 0, scale: 0.78, rotation: 0 }
};

const RESIDENTIAL_ASSETS = ["cottage_house", "suburban_house", "townhouse", "apartment_block"] as const;
const MARKET_ASSETS = ["small_market", "grocery_store", "corner_shop", "cafe"] as const;
const FACTORY_ASSETS = ["factory", "warehouse"] as const;
const GOVERNMENT_ASSETS = ["office_building", "school", "clinic", "police_station"] as const;
const POWER_ASSETS = ["power_plant", "water_plant"] as const;
const FARM_ASSETS = ["wheat_farm", "vegetable_farm", "orchard_farm", "livestock_ranch", "farm_barn", "greenhouse"] as const;
const PARK_PROPS = ["tree", "bush_cluster", "fountain", "rock_cluster"] as const;

export const CITY_CANVAS_BUILD_MENU_ASSETS: Record<BuildingType, string> = {
  farm: CITY_CANVAS_ASSETS.wheat_farm,
  factory: CITY_CANVAS_ASSETS.factory,
  market: CITY_CANVAS_ASSETS.small_market,
  power_plant: CITY_CANVAS_ASSETS.power_plant,
  housing: CITY_CANVAS_ASSETS.suburban_house,
  road: CITY_CANVAS_ASSETS.road_straight
};

type CanvasProp = {
  id: CityCanvasAssetId;
  rotation?: number;
  offsetX?: number;
  offsetY?: number;
};

type CanvasMapCell = {
  x: number;
  y: number;
  terrain: CityCanvasAssetId;
  road: boolean;
  roadConnections: RoadDirection[];
  zone: ZoneOverlayId | null;
  building: CityCanvasAssetId | null;
  buildingRotation: number;
  farm: CityCanvasAssetId | null;
  farmRotation: number;
  civic: CityCanvasAssetId | null;
  civicRotation: number;
  props: CanvasProp[];
  sourceTile: MapTile;
  sourceBuilding: MapBuilding | null;
};

type CanvasMapState = {
  w: number;
  h: number;
  grid: CanvasMapCell[][];
};

export type CityCanvasMapPlan = {
  width: number;
  height: number;
  columns: number;
  rows: number;
  tileSize: number;
  tiles: MapTile[];
  buildingsById: Map<string, MapBuilding>;
  tilesByKey: Map<string, MapTile>;
};

export function buildCityCanvasMapPlan(layout: CityMapLayout, tileSize: number): CityCanvasMapPlan {
  const tiles = [...layout.tiles].sort((a, b) => a.y - b.y || a.x - b.x);
  const tilesByKey = new Map(tiles.map((tile) => [tileKey(tile.x, tile.y), tile]));

  return {
    width: layout.width * tileSize,
    height: layout.height * tileSize,
    columns: layout.width,
    rows: layout.height,
    tileSize,
    tiles,
    buildingsById: new Map(layout.buildings.map((building) => [building.id, building])),
    tilesByKey
  };
}

export function CityCanvasMap({
  plan,
  selectedKinds,
  selectedBuildingId,
  showOverlay,
  tileZoneLabels,
  onSelectBuilding,
  onSelectZone
}: {
  plan: CityCanvasMapPlan;
  selectedKinds: Set<MapTileKind>;
  selectedBuildingId: string | null;
  showOverlay: boolean;
  tileZoneLabels: Record<MapTileKind, string>;
  onSelectBuilding: (building: MapBuilding) => void;
  onSelectZone: (zone: string) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [images, setImages] = useState<CanvasImageMap | null>(null);
  const renderState = useMemo(() => buildCanvasMapState(plan), [plan]);

  useEffect(() => {
    let mounted = true;

    loadCanvasImages().then((loadedImages) => {
      if (mounted) {
        setImages(loadedImages);
      }
    });

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !images) {
      return;
    }

    renderCanvasMap(canvas, renderState, images, plan.tileSize, {
      selectedKinds,
      selectedBuildingId,
      showOverlay
    });
  }, [images, plan.tileSize, renderState, selectedBuildingId, selectedKinds, showOverlay]);

  const hitGridStyle = {
    gridTemplateColumns: `repeat(${plan.columns}, minmax(0, 1fr))`,
    gridTemplateRows: `repeat(${plan.rows}, minmax(0, 1fr))`
  } satisfies CSSProperties;

  function selectTile(tile: MapTile) {
    const building = tile.buildingId ? plan.buildingsById.get(tile.buildingId) ?? null : null;
    if (building) {
      onSelectBuilding(building);
      return;
    }

    onSelectZone(tileZoneLabels[tile.kind]);
  }

  return (
    <div className="canvas-map-surface">
      <canvas
        ref={canvasRef}
        className="city-map-canvas"
        width={plan.width}
        height={plan.height}
        role="img"
        aria-label="Top-down city tile map"
        data-renderer="procedural-roads"
      />
      <div className="canvas-map-hit-grid" style={hitGridStyle} aria-label="City map tiles">
        {plan.tiles.map((tile) => {
          const building = tile.buildingId ? plan.buildingsById.get(tile.buildingId) ?? null : null;
          const selected = selectedBuildingId ? building?.id === selectedBuildingId : selectedKinds.has(tile.kind);
          const title = building ? `${building.label} (${tile.label})` : tile.label;

          return (
            <button
              key={`${tile.x}-${tile.y}`}
              className={`canvas-map-hit-button ${selected ? "is-selected" : ""}`}
              type="button"
              aria-label={title}
              aria-pressed={showOverlay && selected}
              title={title}
              onClick={() => selectTile(tile)}
            />
          );
        })}
      </div>
    </div>
  );
}

let canvasImageCache: Promise<CanvasImageMap> | null = null;

function loadCanvasImages() {
  if (!canvasImageCache) {
    canvasImageCache = Promise.all(
      (Object.entries(CITY_CANVAS_ASSETS) as [CityCanvasAssetId, string][]).map(
        ([id, src]) =>
          new Promise<[CityCanvasAssetId, HTMLImageElement] | null>((resolve) => {
            if (!src) {
              resolve(null);
              return;
            }

            const image = new Image();
            image.onload = () => resolve([id, image]);
            image.onerror = () => resolve(null);
            image.src = src;
          })
      )
    ).then((entries) => {
      const images: CanvasImageMap = {};
      entries.forEach((entry) => {
        if (entry) {
          images[entry[0]] = entry[1];
        }
      });
      return images;
    });
  }

  return canvasImageCache;
}

function buildCanvasMapState(plan: CityCanvasMapPlan): CanvasMapState {
  const grid: CanvasMapCell[][] = [];

  for (let y = 0; y < plan.rows; y += 1) {
    const row: CanvasMapCell[] = [];
    for (let x = 0; x < plan.columns; x += 1) {
      const sourceTile = plan.tilesByKey.get(tileKey(x, y)) ?? fallbackTile(x, y);
      const sourceBuilding = sourceTile.buildingId ? plan.buildingsById.get(sourceTile.buildingId) ?? null : null;
      const terrain = terrainAssetForTile(sourceTile, sourceBuilding);
      const buildingAsset = sourceBuilding ? buildingAssetForTile(sourceTile, sourceBuilding) : null;
      const rotation = roadFacingRotation(plan, x, y);
      const isFarm = sourceBuilding?.kind === "farm";

      row.push({
        x,
        y,
        terrain,
        road: sourceTile.kind === "road",
        roadConnections: sourceTile.roadConnections,
        zone: zoneOverlayForTile(sourceTile),
        building: sourceBuilding && !isFarm && sourceBuilding.kind !== "park" ? buildingAsset : null,
        buildingRotation: rotation,
        farm: sourceBuilding && isFarm ? buildingAsset : null,
        farmRotation: rotation,
        civic: !sourceBuilding && sourceTile.kind === "government" ? "sidewalk_plaza" : null,
        civicRotation: rotation,
        props: propsForTile(sourceTile, terrain, sourceBuilding),
        sourceTile,
        sourceBuilding
      });
    }
    grid.push(row);
  }

  return { w: plan.columns, h: plan.rows, grid };
}

function renderCanvasMap(
  canvas: HTMLCanvasElement,
  state: CanvasMapState,
  images: CanvasImageMap,
  tileSize: number,
  options: {
    selectedKinds: Set<MapTileKind>;
    selectedBuildingId: string | null;
    showOverlay: boolean;
  }
) {
  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }

  const pixelRatio = window.devicePixelRatio || 1;
  const logicalWidth = state.w * tileSize;
  const logicalHeight = state.h * tileSize;
  canvas.width = logicalWidth * pixelRatio;
  canvas.height = logicalHeight * pixelRatio;
  canvas.style.width = "100%";
  canvas.style.height = "100%";

  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  context.clearRect(0, 0, logicalWidth, logicalHeight);
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";

  for (let y = 0; y < state.h; y += 1) {
    for (let x = 0; x < state.w; x += 1) {
      const cell = state.grid[y][x];
      drawImageTransformed(context, images, cell.terrain, x * tileSize, y * tileSize, tileSize);
    }
  }

  for (let y = 0; y < state.h; y += 1) {
    for (let x = 0; x < state.w; x += 1) {
      const cell = state.grid[y][x];
      if (cell.zone) {
        drawImageTransformed(context, images, cell.zone, x * tileSize, y * tileSize, tileSize, 0, 0.1);
      }
    }
  }

  drawRoadLayer(context, state, tileSize);

  for (let y = 0; y < state.h; y += 1) {
    for (let x = 0; x < state.w; x += 1) {
      const cell = state.grid[y][x];
      const px = x * tileSize;
      const py = y * tileSize;

      if (cell.civic) {
        drawImageTransformed(context, images, cell.civic, px, py, tileSize, cell.civicRotation, 1, 0, 0, 0.92);
      }
      if (cell.farm) {
        drawImageTransformed(context, images, cell.farm, px, py, tileSize, cell.farmRotation, 1, 0, 0, 0.9);
      }
      if (cell.building) {
        drawImageTransformed(context, images, cell.building, px, py, tileSize, cell.buildingRotation, 1, 0, 0, 0.9);
      }
    }
  }

  for (let y = 0; y < state.h; y += 1) {
    for (let x = 0; x < state.w; x += 1) {
      const cell = state.grid[y][x];
      cell.props.slice(0, 2).forEach((prop, index) => {
        const stackX = index ? tileSize * 0.05 : 0;
        const stackY = index ? tileSize * 0.04 : 0;
        const offsetX = stackX + (prop.offsetX ?? 0) * (tileSize / 128);
        const offsetY = stackY + (prop.offsetY ?? 0) * (tileSize / 128);
        const scale = prop.id === "car" ? 0.46 : prop.id === "streetlight" ? 0.52 : 0.82;

        drawImageTransformed(context, images, prop.id, x * tileSize, y * tileSize, tileSize, prop.rotation ?? 0, 1, offsetX, offsetY, scale);
      });
    }
  }

  if (options.showOverlay) {
    drawSelectionLayer(context, state, tileSize, options.selectedKinds, options.selectedBuildingId);
  }
}

function drawImageTransformed(
  context: CanvasRenderingContext2D,
  images: CanvasImageMap,
  id: CityCanvasAssetId,
  px: number,
  py: number,
  size: number,
  rotation = 0,
  alpha = 1,
  offsetX = 0,
  offsetY = 0,
  scaleOverride: number | null = null
) {
  const image = images[id];
  if (!image) {
    return;
  }

  const config = DRAW_CONFIG[id] ?? DEFAULT_DRAW_CONFIG;
  const scale = scaleOverride ?? config.scale;
  const drawSize = size * scale;

  context.save();
  context.globalAlpha = alpha;
  context.translate(px + size / 2 + offsetX + config.offsetX * (size / 128), py + size / 2 + offsetY + config.offsetY * (size / 128));
  context.rotate(((rotation || 0) + config.rotation) * Math.PI / 180);
  context.drawImage(image, -drawSize / 2, -drawSize / 2, drawSize, drawSize);
  context.restore();
}

function drawRoadLayer(context: CanvasRenderingContext2D, state: CanvasMapState, tileSize: number) {
  const curb = tileSize * 0.48;
  const asphalt = tileSize * 0.36;
  const inner = tileSize * 0.28;
  const stripe = Math.max(2, tileSize * 0.026);

  drawRoadHalfSegments(context, state, tileSize, { width: curb + tileSize * 0.06, color: "rgba(0, 0, 0, 0.2)" });
  drawRoadHalfSegments(context, state, tileSize, { width: curb, color: "#c9c9ba" });
  drawRoadHalfSegments(context, state, tileSize, { width: curb - tileSize * 0.05, color: "#96988d" });
  drawRoadHalfSegments(context, state, tileSize, { width: asphalt, color: "#3f4446" });
  drawRoadHalfSegments(context, state, tileSize, { width: inner, color: "#4b5052" });

  context.save();
  context.strokeStyle = "#f0f0e8";
  context.lineWidth = stripe;
  context.lineCap = "butt";
  const dash = tileSize * 0.13;
  const gap = tileSize * 0.11;

  for (let y = 0; y < state.h; y += 1) {
    for (let x = 0; x < state.w; x += 1) {
      const cell = state.grid[y][x];
      if (!cell.road) {
        continue;
      }

      const connections = roadConnections(state, x, y);
      const cx = x * tileSize + tileSize / 2;
      const cy = y * tileSize + tileSize / 2;

      if (connections.W && connections.E && !(connections.N || connections.S)) {
        drawDashedLine(context, x * tileSize, cy, (x + 1) * tileSize, cy, tileSize, dash, gap);
      } else {
        if (connections.W) drawDashedLine(context, x * tileSize, cy, cx - tileSize * 0.1, cy, tileSize, dash, gap);
        if (connections.E) drawDashedLine(context, cx + tileSize * 0.1, cy, (x + 1) * tileSize, cy, tileSize, dash, gap);
      }

      if (connections.N && connections.S && !(connections.E || connections.W)) {
        drawDashedLine(context, cx, y * tileSize, cx, (y + 1) * tileSize, tileSize, dash, gap);
      } else {
        if (connections.N) drawDashedLine(context, cx, y * tileSize, cx, cy - tileSize * 0.1, tileSize, dash, gap);
        if (connections.S) drawDashedLine(context, cx, cy + tileSize * 0.1, cx, (y + 1) * tileSize, tileSize, dash, gap);
      }
    }
  }
  context.restore();
}

function drawRoadHalfSegments(
  context: CanvasRenderingContext2D,
  state: CanvasMapState,
  tileSize: number,
  style: { width: number; color: string }
) {
  context.save();
  context.lineCap = "butt";
  context.lineJoin = "round";
  context.strokeStyle = style.color;
  context.lineWidth = style.width;

  for (let y = 0; y < state.h; y += 1) {
    for (let x = 0; x < state.w; x += 1) {
      const cell = state.grid[y][x];
      if (!cell.road) {
        continue;
      }

      const connections = roadConnections(state, x, y);
      const cx = x * tileSize + tileSize / 2;
      const cy = y * tileSize + tileSize / 2;

      context.beginPath();
      if (connections.W) {
        context.moveTo(x * tileSize, cy);
        context.lineTo(cx, cy);
      }
      if (connections.E) {
        context.moveTo(cx, cy);
        context.lineTo((x + 1) * tileSize, cy);
      }
      if (connections.N) {
        context.moveTo(cx, y * tileSize);
        context.lineTo(cx, cy);
      }
      if (connections.S) {
        context.moveTo(cx, cy);
        context.lineTo(cx, (y + 1) * tileSize);
      }
      if (!connections.N && !connections.E && !connections.S && !connections.W) {
        context.moveTo(cx - tileSize * 0.25, cy);
        context.lineTo(cx + tileSize * 0.25, cy);
      }
      context.stroke();
    }
  }

  context.restore();
}

function drawDashedLine(
  context: CanvasRenderingContext2D,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  tileSize: number,
  dash: number,
  gap: number
) {
  const length = Math.hypot(x2 - x1, y2 - y1);
  if (!Number.isFinite(length) || length <= 0) {
    return;
  }

  const dx = (x2 - x1) / length;
  const dy = (y2 - y1) / length;
  let position = tileSize * 0.08;

  while (position < length - tileSize * 0.08) {
    const start = position;
    const end = Math.min(position + dash, length - tileSize * 0.08);

    context.beginPath();
    context.moveTo(x1 + dx * start, y1 + dy * start);
    context.lineTo(x1 + dx * end, y1 + dy * end);
    context.stroke();
    position += dash + gap;
  }
}

function drawSelectionLayer(
  context: CanvasRenderingContext2D,
  state: CanvasMapState,
  tileSize: number,
  selectedKinds: Set<MapTileKind>,
  selectedBuildingId: string | null
) {
  context.save();
  context.lineWidth = Math.max(4, tileSize * 0.035);
  context.strokeStyle = "rgba(248, 184, 71, 0.96)";
  context.fillStyle = "rgba(255, 221, 89, 0.1)";

  for (let y = 0; y < state.h; y += 1) {
    for (let x = 0; x < state.w; x += 1) {
      const cell = state.grid[y][x];
      const selected = selectedBuildingId
        ? cell.sourceBuilding?.id === selectedBuildingId
        : selectedKinds.has(cell.sourceTile.kind);

      if (!selected) {
        continue;
      }

      const inset = tileSize * 0.06;
      context.fillRect(x * tileSize + inset, y * tileSize + inset, tileSize - inset * 2, tileSize - inset * 2);
      context.strokeRect(x * tileSize + inset, y * tileSize + inset, tileSize - inset * 2, tileSize - inset * 2);
    }
  }

  context.restore();
}

function roadConnections(state: CanvasMapState, x: number, y: number) {
  const cell = mapCell(state, x, y);
  const listed = new Set(cell?.roadConnections ?? []);
  const hasExplicitConnections = listed.size > 0;

  return {
    N: hasExplicitConnections ? listed.has("n") && hasRoad(state, x, y - 1) : hasRoad(state, x, y - 1),
    E: hasExplicitConnections ? listed.has("e") && hasRoad(state, x + 1, y) : hasRoad(state, x + 1, y),
    S: hasExplicitConnections ? listed.has("s") && hasRoad(state, x, y + 1) : hasRoad(state, x, y + 1),
    W: hasExplicitConnections ? listed.has("w") && hasRoad(state, x - 1, y) : hasRoad(state, x - 1, y)
  };
}

function mapCell(state: CanvasMapState, x: number, y: number) {
  if (x < 0 || y < 0 || x >= state.w || y >= state.h) {
    return null;
  }

  return state.grid[y][x];
}

function hasRoad(state: CanvasMapState, x: number, y: number) {
  return !!mapCell(state, x, y)?.road;
}

function terrainAssetForTile(tile: MapTile, building: MapBuilding | null): CityCanvasAssetId {
  if (tile.kind === "water") {
    return tileVariantIndex(tile, 5) === 0 ? "pond_tile" : "water_tile";
  }

  if (tile.kind === "farm" || building?.kind === "farm") {
    return "farm_ground_tile";
  }

  if (tile.kind === "park" || building?.kind === "park") {
    return "park_ground_tile";
  }

  if (tile.kind === "factory" || tile.kind === "power_plant") {
    return "dirt_tile";
  }

  if (tile.kind === "market" || tile.kind === "government") {
    return tileVariantIndex(tile, 3) === 0 ? "sand_tile" : "grass_tile_b";
  }

  return tileVariantIndex(tile, 2) === 0 ? "grass_tile_a" : "grass_tile_b";
}

function zoneOverlayForTile(tile: MapTile): ZoneOverlayId | null {
  switch (tile.kind) {
    case "residential":
      return "zone_residential";
    case "market":
      return "zone_commercial";
    case "factory":
    case "power_plant":
      return "zone_industrial";
    default:
      return null;
  }
}

function buildingAssetForTile(tile: MapTile, building: MapBuilding): CityCanvasAssetId | null {
  const salt = building.level + building.units;

  switch (building.kind) {
    case "residential":
      if (building.level >= 3) return "apartment_block";
      return RESIDENTIAL_ASSETS[tileVariantIndex(tile, 3, salt)];
    case "factory":
      return FACTORY_ASSETS[tileVariantIndex(tile, FACTORY_ASSETS.length, salt)];
    case "market":
      return MARKET_ASSETS[tileVariantIndex(tile, MARKET_ASSETS.length, salt)];
    case "government":
      return GOVERNMENT_ASSETS[tileVariantIndex(tile, GOVERNMENT_ASSETS.length, salt)];
    case "power_plant":
      return POWER_ASSETS[tileVariantIndex(tile, POWER_ASSETS.length, salt)];
    case "farm":
      return FARM_ASSETS[tileVariantIndex(tile, FARM_ASSETS.length, salt)];
    case "park":
      return null;
    default:
      return null;
  }
}

function propsForTile(tile: MapTile, terrain: CityCanvasAssetId, building: MapBuilding | null): CanvasProp[] {
  const props: CanvasProp[] = [];

  if (tile.kind === "road") {
    const connections = new Set(tile.roadConnections);
    const isVertical = (connections.has("n") || connections.has("s")) && !(connections.has("e") || connections.has("w"));
    const isHorizontal = (connections.has("e") || connections.has("w")) && !(connections.has("n") || connections.has("s"));

    if (isVertical || isHorizontal) {
      if (tileChance(tile, 41, 0.12)) {
        props.push({ id: "car", rotation: isVertical ? 90 : 0, offsetX: 0, offsetY: 0 });
      }
      if (tileChance(tile, 67, 0.16)) {
        props.push({
          id: "streetlight",
          rotation: 0,
          offsetX: isVertical ? -28 : 28,
          offsetY: isVertical ? 28 : -28
        });
      }
    }

    return props;
  }

  if (building && building.kind !== "park") {
    return props;
  }

  if (tile.kind === "park" || building?.kind === "park") {
    props.push({ id: PARK_PROPS[tileVariantIndex(tile, PARK_PROPS.length, 5)], rotation: 0, offsetX: 0, offsetY: 0 });
    if (tileChance(tile, 91, 0.28)) {
      props.push({ id: "bush_cluster", rotation: 0, offsetX: 24, offsetY: -18 });
    }
    return props;
  }

  if ((terrain === "grass_tile_a" || terrain === "grass_tile_b") && tileChance(tile, 17, 0.12)) {
    props.push({
      id: tileChance(tile, 23, 0.7) ? "tree" : "bush_cluster",
      rotation: 0,
      offsetX: tileChance(tile, 29, 0.5) ? -18 : 20,
      offsetY: tileChance(tile, 31, 0.5) ? -16 : 18
    });
  }

  if ((terrain === "dirt_tile" || terrain === "sand_tile") && tileChance(tile, 37, 0.06)) {
    props.push({ id: "rock_cluster", rotation: 0, offsetX: 0, offsetY: 0 });
  }

  return props;
}

function roadFacingRotation(plan: CityCanvasMapPlan, x: number, y: number) {
  const south = plan.tilesByKey.get(tileKey(x, y + 1))?.kind === "road";
  const west = plan.tilesByKey.get(tileKey(x - 1, y))?.kind === "road";
  const east = plan.tilesByKey.get(tileKey(x + 1, y))?.kind === "road";
  const north = plan.tilesByKey.get(tileKey(x, y - 1))?.kind === "road";

  if (south) return 0;
  if (west) return 90;
  if (north) return 180;
  if (east) return 270;
  return 0;
}

function tileVariantIndex(tile: MapTile, modulo: number, salt = 0) {
  if (modulo <= 1) {
    return 0;
  }

  return Math.abs(tile.x * 31 + tile.y * 17 + salt * 13) % modulo;
}

function tileChance(tile: MapTile, salt: number, threshold: number) {
  return normalizedTileHash(tile, salt) < threshold;
}

function normalizedTileHash(tile: MapTile, salt: number) {
  const value = Math.imul(tile.x + 1, 73856093) ^ Math.imul(tile.y + 1, 19349663) ^ Math.imul(salt + 1, 83492791);
  return Math.abs(value % 1000) / 1000;
}

function tileKey(x: number, y: number) {
  return `${x}:${y}`;
}

function fallbackTile(x: number, y: number): MapTile {
  return {
    x,
    y,
    kind: "empty",
    label: "Open land",
    active: false,
    zone: null,
    roadType: null,
    roadConnections: [],
    buildingId: null,
    lotId: null,
    isAnchor: false
  };
}
