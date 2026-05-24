import { existsSync } from "node:fs";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PACK_ROOT = ROOT;
const MANIFEST_PATH = path.join(PACK_ROOT, "metadata", "assets.json");
const MAP_STATE_PATH = path.join(PACK_ROOT, "examples", "example_map.generated.json");
const MAP_HTML_PATH = path.join(PACK_ROOT, "output", "generated_city_map.html");
const RAIL_OVERLAY_ID = "rail_straight_overlay";

const WIDTH = 20;
const HEIGHT = 16;
const DIRECTIONS = ["top", "right", "bottom", "left"];
const OPPOSITE = { top: "bottom", right: "left", bottom: "top", left: "right" };
const DELTAS = {
  top: [0, -1],
  right: [1, 0],
  bottom: [0, 1],
  left: [-1, 0],
};
const ROTATIONS = new Set([0, 90, 180, 270]);
const ACCESSIBLE_TILE_IDS = new Set([
  "road_straight",
  "road_vertical",
  "road_corner",
  "road_t_junction",
  "road_cross",
  "road_dead_end",
  "road_avenue",
  "road_bridge",
  "road_roundabout",
  "rail_crossing",
  "sidewalk_plaza",
]);

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function cell(assetId, x, y, extra = {}) {
  return { assetId, x, y, rotation: extra.rotation ?? 0, ...extra };
}

function keyOf(x, y) {
  return `${x},${y}`;
}

function layerMap(entries) {
  return new Map(entries.map((entry) => [keyOf(entry.x, entry.y), entry]));
}

function neighbor(entry, direction, map) {
  const [dx, dy] = DELTAS[direction];
  return map.get(keyOf(entry.x + dx, entry.y + dy));
}

function rotateSockets(sockets, rotation = 0) {
  if (!ROTATIONS.has(rotation)) {
    throw new Error(`Unsupported rotation ${rotation}. Use 0, 90, 180, or 270.`);
  }
  let rotated = { ...sockets };
  for (let step = 0; step < rotation / 90; step += 1) {
    rotated = {
      top: rotated.left,
      right: rotated.top,
      bottom: rotated.right,
      left: rotated.bottom,
    };
  }
  return rotated;
}

function isRoadAsset(asset) {
  return asset?.role === "road_tile";
}

function buildGround() {
  const ground = [];
  for (let y = 0; y < HEIGHT; y += 1) {
    for (let x = 0; x < WIDTH; x += 1) {
      let assetId = (x + y) % 4 === 0 ? "grass_tile_b" : "grass_tile_a";
      if (x === 0) assetId = "water_tile";
      if (x === 1) assetId = "sand_tile";
      if (x >= 2 && x <= 6 && y >= 11 && y <= 15) assetId = "farm_ground_tile";
      if (x >= 12 && x <= 15 && y >= 1 && y <= 4) assetId = "park_ground_tile";
      if (x >= 15 && x <= 19 && y >= 9 && y <= 14) assetId = (x + y) % 2 ? "dirt_tile" : "empty_lot_tile";
      ground.push(cell(assetId, x, y));
    }
  }

  const terrain = [
    cell("coast_edge_north", 1, 0),
    cell("coast_edge_corner", 1, 1),
    cell("coast_inlet_tile", 1, 2),
    cell("sand_tile", 1, 3),
    cell("water_tile", 6, 6),
    cell("water_tile", 6, 8),
    cell("pond_tile", 13, 2),
    cell("sidewalk_plaza", 12, 3),
    cell("wheat_farm", 2, 13),
    cell("vegetable_farm", 3, 13),
    cell("orchard_farm", 2, 14),
    cell("livestock_ranch", 3, 14),
  ];

  const roads = [
    cell("road_dead_end", 2, 7, { rotation: 180 }),
    cell("road_straight", 3, 7),
    cell("road_straight", 4, 7),
    cell("road_cross", 5, 7),
    cell("road_bridge", 6, 7),
    cell("road_avenue", 7, 7),
    cell("road_straight", 8, 7),
    cell("road_roundabout", 9, 7),
    cell("road_straight", 10, 7),
    cell("road_t_junction", 11, 7),
    cell("road_straight", 12, 7),
    cell("road_cross", 13, 7),
    cell("road_straight", 14, 7),
    cell("road_straight", 15, 7),
    cell("road_t_junction", 16, 7, { rotation: 180 }),
    cell("road_straight", 17, 7),
    cell("road_dead_end", 18, 7),

    cell("road_corner", 5, 3, { rotation: 90 }),
    cell("road_dead_end", 6, 3),
    cell("road_vertical", 5, 4),
    cell("rail_crossing", 5, 5, { rotation: 90 }),
    cell("road_vertical", 5, 6),
    cell("road_vertical", 5, 8),
    cell("road_vertical", 5, 9),
    cell("road_vertical", 5, 10),
    cell("road_vertical", 5, 11),
    cell("road_dead_end", 5, 12, { rotation: 90 }),

    cell("road_dead_end", 9, 4, { rotation: 270 }),
    cell("rail_crossing", 9, 5, { rotation: 90 }),
    cell("road_vertical", 9, 6),
    cell("road_vertical", 9, 8),
    cell("road_vertical", 9, 9),
    cell("road_vertical", 9, 10),
    cell("road_dead_end", 9, 11, { rotation: 90 }),

    cell("road_dead_end", 11, 4, { rotation: 270 }),
    cell("rail_crossing", 11, 5, { rotation: 90 }),
    cell("road_vertical", 11, 6),

    cell("road_dead_end", 13, 4, { rotation: 270 }),
    cell("rail_crossing", 13, 5, { rotation: 90 }),
    cell("road_vertical", 13, 6),
    cell("road_vertical", 13, 8),
    cell("road_vertical", 13, 9),
    cell("road_vertical", 13, 10),
    cell("road_vertical", 13, 11),
    cell("road_vertical", 13, 12),
    cell("road_dead_end", 13, 13, { rotation: 90 }),

    cell("road_vertical", 16, 8),
    cell("road_vertical", 16, 9),
    cell("road_vertical", 16, 10),
    cell("road_vertical", 16, 11),
    cell("road_vertical", 16, 12),
    cell("road_dead_end", 16, 13, { rotation: 90 }),
  ];

  const byCoord = layerMap(ground);
  for (const override of [...terrain, ...roads]) {
    byCoord.set(keyOf(override.x, override.y), override);
  }
  return [...byCoord.values()].sort((a, b) => a.y - b.y || a.x - b.x);
}

function buildSprites() {
  return [
    cell("cottage_house", 4, 3, { district: "residential", accessSide: "right", rotation: 270 }),
    cell("suburban_house", 6, 2, { district: "residential", accessSide: "bottom" }),
    cell("townhouse", 4, 4, { district: "residential", accessSide: "right", rotation: 270 }),
    cell("apartment_block", 6, 4, { district: "residential", accessSide: "left", rotation: 90 }),

    cell("small_market", 10, 4, { district: "commercial", accessSide: "right", rotation: 270 }),
    cell("corner_shop", 10, 6, { district: "commercial", accessSide: "right", rotation: 270 }),
    cell("grocery_store", 12, 4, { district: "commercial", accessSide: "right", rotation: 270 }),
    cell("cafe", 12, 6, { district: "commercial", accessSide: "left", rotation: 90 }),
    cell("office_building", 14, 4, { district: "commercial", accessSide: "left", rotation: 90 }),

    cell("school", 8, 4, { district: "civic", accessSide: "right", rotation: 270 }),
    cell("clinic", 15, 6, { district: "civic", accessSide: "bottom", rotation: 180 }),
    cell("police_station", 14, 6, { district: "civic", accessSide: "left", rotation: 90 }),

    cell("factory", 15, 9, { district: "industrial", accessSide: "right", rotation: 270 }),
    cell("warehouse", 17, 9, { district: "industrial", accessSide: "left", rotation: 90 }),
    cell("power_plant", 15, 11, { district: "industrial", accessSide: "right", rotation: 270 }),
    cell("water_plant", 17, 11, { district: "industrial", accessSide: "left", rotation: 90 }),

    cell("farm_barn", 4, 12, { district: "farm", accessSide: "right", rotation: 270 }),
    cell("greenhouse", 6, 11, { district: "farm", accessSide: "left", rotation: 90 }),

    cell("tree", 12, 2, { district: "park" }),
    cell("tree", 14, 2, { district: "park", rotation: 90 }),
    cell("bush_cluster", 13, 3, { district: "park" }),
    cell("fountain", 12, 3, { district: "civic" }),
    cell("streetlight", 10, 6, { district: "commercial" }),
    cell("streetlight", 12, 8, { district: "road", rotation: 180 }),
    cell("rock_cluster", 2, 9, { district: "coast" }),
    cell("car", 12, 7, { district: "road", rotation: 90 }),
  ];
}

function buildOverlays() {
  return [
    cell("zone_residential", 4, 3, { label: "residential zone" }),
    cell("zone_residential", 6, 2, { label: "residential zone" }),
    cell("zone_residential", 4, 4, { label: "residential zone" }),
    cell("zone_residential", 6, 4, { label: "residential zone" }),

    cell("zone_commercial", 10, 4, { label: "commercial zone" }),
    cell("zone_commercial", 10, 6, { label: "commercial zone" }),
    cell("zone_commercial", 12, 4, { label: "commercial zone" }),
    cell("zone_commercial", 12, 6, { label: "commercial zone" }),
    cell("zone_commercial", 14, 4, { label: "commercial zone" }),

    cell("zone_industrial", 15, 9, { label: "industrial zone" }),
    cell("zone_industrial", 17, 9, { label: "industrial zone" }),
    cell("zone_industrial", 15, 11, { label: "industrial zone" }),
    cell("zone_industrial", 17, 11, { label: "industrial zone" }),

    cell("selection_overlay", 6, 9, { label: "selected build lot" }),
    cell("build_preview_overlay", 7, 9, { label: "build preview" }),
    cell("invalid_overlay", 0, 5, { label: "invalid water placement" }),
    cell("road_preview_overlay", 6, 8, { label: "planned east-west road preview" }),
    cell("grid_overlay", 1, 14, { label: "grid overlay sample" }),
  ];
}

function buildFeatures() {
  const railTiles = Array.from({ length: WIDTH }, (_, x) => ({ x, y: 5, rotation: 0 }));
  return {
    rail: {
      label: "straight railway corridor",
      mode: "straight_overlay_tiles",
      assetId: RAIL_OVERLAY_ID,
      tiles: railTiles,
      crossings: [
        { x: 5, y: 5 },
        { x: 9, y: 5 },
        { x: 11, y: 5 },
        { x: 13, y: 5 },
      ],
    },
  };
}

function manifestLookup(manifest) {
  return Object.fromEntries(manifest.assets.map((asset) => [asset.id, {
    id: asset.id,
    title: asset.title,
    category: asset.category,
    role: asset.connectivityRole,
    image: asset.image.packRelativePath,
    edgeSockets: asset.edgeSockets,
  }]));
}

function validateAssetReferences(state, assetLookup) {
  for (const [assetId, asset] of Object.entries(assetLookup)) {
    if (!existsSync(path.join(PACK_ROOT, asset.image))) {
      throw new Error(`Missing PNG for ${assetId}: ${asset.image}`);
    }
  }
  for (const [layerName, entries] of Object.entries(state.layers)) {
    for (const entry of entries) {
      if (!assetLookup[entry.assetId]) {
        throw new Error(`Unknown asset in ${layerName}: ${entry.assetId}`);
      }
      if (!ROTATIONS.has(entry.rotation ?? 0)) {
        throw new Error(`Unsupported rotation for ${entry.assetId} at ${entry.x},${entry.y}`);
      }
    }
  }
}

function validateAllAssetsUsed(state, manifest) {
  const used = new Set();
  for (const layer of Object.values(state.layers)) {
    for (const entry of layer) used.add(entry.assetId);
  }
  used.add(state.features.rail.assetId);
  const missing = manifest.assets.map((asset) => asset.id).filter((id) => !used.has(id));
  if (missing.length) {
    throw new Error(`Map does not use every manifest asset: ${missing.join(", ")}`);
  }
  return used;
}

function roadSocketsFor(entry, assetLookup) {
  const asset = assetLookup[entry.assetId];
  if (!isRoadAsset(asset)) return null;
  return rotateSockets(asset.edgeSockets, entry.rotation ?? 0);
}

function validateRoadNetwork(state, assetLookup) {
  const ground = layerMap(state.layers.ground);
  const failures = [];
  for (const entry of state.layers.ground) {
    const sockets = roadSocketsFor(entry, assetLookup);
    if (!sockets) continue;
    for (const direction of DIRECTIONS) {
      if (sockets[direction] !== "road") continue;
      const adjacent = neighbor(entry, direction, ground);
      const neighborSockets = adjacent ? roadSocketsFor(adjacent, assetLookup) : null;
      if (!neighborSockets || neighborSockets[OPPOSITE[direction]] !== "road") {
        failures.push(`${entry.assetId}@${entry.x},${entry.y} ${direction}`);
      }
    }
  }
  if (failures.length) {
    throw new Error(`Road socket mismatches:\n${failures.join("\n")}`);
  }
}

function validateBuildingAccess(state, assetLookup) {
  const ground = layerMap(state.layers.ground);
  const failures = [];
  for (const entry of state.layers.sprites) {
    const asset = assetLookup[entry.assetId];
    const needsAccess = asset.category === "building" || ["farm_barn", "greenhouse"].includes(entry.assetId);
    if (!needsAccess) continue;
    if (!entry.accessSide) {
      failures.push(`${entry.assetId}@${entry.x},${entry.y} missing accessSide`);
      continue;
    }
    const accessTile = neighbor(entry, entry.accessSide, ground);
    if (!accessTile || !ACCESSIBLE_TILE_IDS.has(accessTile.assetId)) {
      failures.push(`${entry.assetId}@${entry.x},${entry.y} ${entry.accessSide}`);
    }
  }
  if (failures.length) {
    throw new Error(`Building access failures:\n${failures.join("\n")}`);
  }
}

function validateAccessoryPlacement(state) {
  const ground = layerMap(state.layers.ground);
  const failures = [];
  for (const entry of state.layers.sprites) {
    const groundTile = ground.get(keyOf(entry.x, entry.y));
    if (entry.assetId === "car" && !groundTile?.assetId.startsWith("road_") && groundTile?.assetId !== "rail_crossing") {
      failures.push(`car must be on a road tile: ${entry.x},${entry.y}`);
    }
    if (entry.assetId === "fountain" && groundTile?.assetId !== "sidewalk_plaza") {
      failures.push(`fountain must be on sidewalk_plaza: ${entry.x},${entry.y}`);
    }
    if (entry.assetId === "streetlight") {
      const hasAccessNeighbor = DIRECTIONS.some((direction) => {
        const adjacent = neighbor(entry, direction, ground);
        return adjacent && ACCESSIBLE_TILE_IDS.has(adjacent.assetId);
      });
      if (!hasAccessNeighbor) {
        failures.push(`streetlight must be beside road/plaza: ${entry.x},${entry.y}`);
      }
    }
  }
  if (failures.length) {
    throw new Error(`Accessory placement failures:\n${failures.join("\n")}`);
  }
}

function validateRail(state) {
  const ground = layerMap(state.layers.ground);
  const rail = state.features?.rail;
  const failures = [];
  if (!rail || rail.mode !== "straight_overlay_tiles") {
    failures.push("rail must use straight overlay tiles");
  }
  if (rail?.assetId !== RAIL_OVERLAY_ID) {
    failures.push(`rail must use ${RAIL_OVERLAY_ID}`);
  }
  if (!rail || rail.tiles.length < WIDTH) {
    failures.push("rail must cross the full map width");
  }
  const rows = new Set((rail?.tiles ?? []).map((tile) => tile.y));
  if (rows.size !== 1) {
    failures.push("rail overlay tiles must stay on one straight row");
  }
  const sortedTiles = [...(rail?.tiles ?? [])].sort((a, b) => a.x - b.x);
  for (let index = 0; index < sortedTiles.length; index += 1) {
    if (sortedTiles[index].x !== index) {
      failures.push("rail overlay tiles must be contiguous from the west edge to the east edge");
      break;
    }
  }
  if (!rail || rail.crossings.length < 3) {
    failures.push("rail path must pass through multiple road crossings");
  }
  for (const crossing of rail?.crossings ?? []) {
    const tile = ground.get(keyOf(crossing.x, crossing.y));
    if (tile?.assetId !== "rail_crossing") {
      failures.push(`rail crossing marker missing rail_crossing tile at ${crossing.x},${crossing.y}`);
    }
  }
  if (failures.length) {
    throw new Error(`Rail validation failures:\n${failures.join("\n")}`);
  }
}

function buildMapState(manifest) {
  const assetLookup = manifestLookup(manifest);
  const state = {
    mapId: "imagegen_showcase_city",
    title: "Imagegen Showcase City",
    width: WIDTH,
    height: HEIGHT,
    tileSize: [128, 128],
    renderTileSize: 72,
    purpose: "A standalone demo map using the full imagegen 128px CityBuilder asset pack with validated road access and rotations.",
    layers: {
      ground: buildGround(),
      overlays: buildOverlays(),
      sprites: buildSprites(),
    },
    features: buildFeatures(),
  };

  validateAssetReferences(state, assetLookup);
  const usedAssetIds = validateAllAssetsUsed(state, manifest);
  validateRoadNetwork(state, assetLookup);
  validateBuildingAccess(state, assetLookup);
  validateAccessoryPlacement(state);
  validateRail(state);

  return {
    ...state,
    assets: assetLookup,
    usedAssetIds: [...usedAssetIds].sort(),
    assetCount: manifest.assets.length,
  };
}

function renderLayerItems(entries, assetLookup, layerName) {
  return entries.map((entry) => {
    const asset = assetLookup[entry.assetId];
    if (!asset) throw new Error(`Unknown asset ${entry.assetId}`);
    const title = `${asset.title} (${entry.x}, ${entry.y})`;
    return `<img class="tile ${layerName}" src="${escapeHtml(htmlAssetSrc(asset.image))}" alt="${escapeHtml(title)}" title="${escapeHtml(title)}" data-asset="${escapeHtml(entry.assetId)}" style="--x:${entry.x};--y:${entry.y};--r:${entry.rotation ?? 0}deg;">`;
  }).join("\n");
}

function htmlAssetSrc(packRelativePath) {
  return path.relative(path.dirname(MAP_HTML_PATH), path.join(PACK_ROOT, packRelativePath)).replaceAll("\\", "/");
}

function renderRailFeature(state) {
  const rail = state.features.rail;
  const railAsset = state.assets[rail.assetId];
  return rail.tiles.map((tile) => (
    `<img class="tile rail-segment" src="${escapeHtml(htmlAssetSrc(railAsset.image))}" alt="${escapeHtml(rail.label)} (${tile.x}, ${tile.y})" title="${escapeHtml(rail.label)} (${tile.x}, ${tile.y})" data-asset="${escapeHtml(rail.assetId)}" style="--x:${tile.x};--y:${tile.y};--r:${tile.rotation ?? 0}deg;">`
  )).join("\n");
}

function renderLegend(state, manifest) {
  const byCategory = new Map();
  for (const asset of manifest.assets) {
    const count = state.usedAssetIds.includes(asset.id) ? 1 : 0;
    byCategory.set(asset.category, (byCategory.get(asset.category) ?? 0) + count);
  }
  return [...byCategory.entries()].sort().map(([category, count]) => (
    `<span><strong>${escapeHtml(count)}</strong> ${escapeHtml(category)}</span>`
  )).join("");
}

function renderHtml(state, manifest) {
  const assets = state.assets;
  const mapWidth = state.width * state.renderTileSize;
  const mapHeight = state.height * state.renderTileSize;
  const ground = renderLayerItems(state.layers.ground, assets, "ground");
  const overlays = renderLayerItems(state.layers.overlays, assets, "overlay");
  const sprites = renderLayerItems(state.layers.sprites, assets, "sprite");
  const rail = renderRailFeature(state);
  const legend = renderLegend(state, manifest);

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(state.title)}</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #07111b;
    --panel: #0d1d2b;
    --line: #1d3c54;
    --text: #f5f7fb;
    --muted: #9cc1df;
    --accent: #5fc8ff;
    --tile: ${state.renderTileSize}px;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    min-height: 100vh;
    background: #07111b;
    color: var(--text);
    font-family: Inter, "Segoe UI", Arial, sans-serif;
  }
  header {
    position: sticky;
    top: 0;
    z-index: 5;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    padding: 14px 16px;
    border-bottom: 1px solid var(--line);
    background: #050d14;
  }
  h1 {
    margin: 0;
    font-size: 21px;
    letter-spacing: 0;
  }
  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }
  button, select {
    height: 34px;
    border: 1px solid var(--line);
    border-radius: 7px;
    background: var(--panel);
    color: var(--text);
    padding: 0 10px;
    font: inherit;
  }
  button { cursor: pointer; }
  button[aria-pressed="false"] { color: var(--muted); }
  main {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 290px;
    gap: 16px;
    padding: 16px;
  }
  .map-shell {
    overflow: auto;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #03090f;
    max-height: calc(100vh - 96px);
  }
  .map {
    position: relative;
    width: calc(${state.width} * var(--tile));
    height: calc(${state.height} * var(--tile));
    background: #102331;
    isolation: isolate;
  }
  .tile {
    position: absolute;
    left: calc(var(--x) * var(--tile));
    top: calc(var(--y) * var(--tile));
    width: var(--tile);
    height: var(--tile);
    image-rendering: auto;
    transform: rotate(var(--r));
    transform-origin: center;
    user-select: none;
  }
  .ground { z-index: 1; }
  .rail-segment { z-index: 2; pointer-events: none; }
  .overlay { z-index: 3; pointer-events: auto; }
  .sprite { z-index: 4; pointer-events: auto; }
  body.hide-sprites .sprite { display: none; }
  body.hide-overlays .overlay { display: none; }
  body.hide-rail .rail-segment { display: none; }
  .map::after {
    content: "";
    position: absolute;
    inset: 0;
    z-index: 5;
    pointer-events: none;
    background-image:
      linear-gradient(to right, rgba(255,255,255,.14) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(255,255,255,.14) 1px, transparent 1px);
    background-size: var(--tile) var(--tile);
    display: none;
  }
  body.show-grid .map::after { display: block; }
  aside {
    display: grid;
    align-content: start;
    gap: 12px;
  }
  .panel {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel);
    padding: 12px;
  }
  h2 {
    margin: 0 0 10px;
    font-size: 14px;
    letter-spacing: 0;
  }
  .stats {
    display: grid;
    gap: 7px;
    color: var(--muted);
    font-size: 13px;
  }
  .stats strong { color: var(--text); }
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
  }
  .legend span {
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 5px 8px;
    color: var(--muted);
    font-size: 12px;
  }
  .legend strong { color: var(--accent); }
  code {
    color: var(--muted);
    font-size: 12px;
    word-break: break-word;
  }
  @media (max-width: 960px) {
    main { grid-template-columns: 1fr; }
    .map-shell { max-height: none; }
  }
</style>
</head>
<body class="show-grid">
<header>
  <h1>${escapeHtml(state.title)}</h1>
  <div class="controls">
    <select id="zoom" aria-label="Zoom">
      <option value="56">56 px</option>
      <option value="72" selected>72 px</option>
      <option value="88">88 px</option>
      <option value="104">104 px</option>
      <option value="128">128 px</option>
    </select>
    <button type="button" data-toggle="hide-sprites" aria-pressed="true">Sprites</button>
    <button type="button" data-toggle="hide-overlays" aria-pressed="true">Overlays</button>
    <button type="button" data-toggle="hide-rail" aria-pressed="true">Rail</button>
    <button type="button" data-toggle="show-grid" aria-pressed="true">Grid</button>
  </div>
</header>
<main>
  <section class="map-shell" aria-label="Generated city map">
    <div class="map" style="width:${mapWidth}px;height:${mapHeight}px">
${ground}
${rail}
${overlays}
${sprites}
    </div>
  </section>
  <aside>
    <section class="panel">
      <h2>Map Stats</h2>
      <div class="stats">
        <span><strong>${state.width} x ${state.height}</strong> tiles</span>
        <span><strong>${state.usedAssetIds.length} / ${state.assetCount}</strong> assets used</span>
        <span><strong>${state.layers.ground.length}</strong> ground tiles</span>
        <span><strong>${state.layers.sprites.length}</strong> sprites</span>
        <span><strong>${state.layers.overlays.length}</strong> overlays</span>
        <span><strong>${state.features.rail.tiles.length}</strong> straight rail tiles</span>
        <span><strong>${state.features.rail.crossings.length}</strong> rail crossings</span>
      </div>
    </section>
    <section class="panel">
      <h2>Used Categories</h2>
      <div class="legend">${legend}</div>
    </section>
    <section class="panel">
      <h2>Files</h2>
      <div class="stats">
        <code>metadata/generated_city_map_state.json</code>
        <code>metadata/asset_image_adjacency_128.json</code>
      </div>
    </section>
  </aside>
</main>
<script>
  const zoom = document.getElementById("zoom");
  zoom.addEventListener("change", () => {
    document.documentElement.style.setProperty("--tile", zoom.value + "px");
  });
  document.querySelectorAll("[data-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const className = button.dataset.toggle;
      document.body.classList.toggle(className);
      const active = className === "show-grid"
        ? document.body.classList.contains(className)
        : !document.body.classList.contains(className);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  });
</script>
</body>
</html>`;
}

async function main() {
  const manifest = JSON.parse(await readFile(MANIFEST_PATH, "utf8"));
  const state = buildMapState(manifest);
  await writeFile(MAP_STATE_PATH, `${JSON.stringify(state, null, 2)}\n`, "utf8");
  await writeFile(MAP_HTML_PATH, renderHtml(state, manifest), "utf8");
  console.log(path.relative(ROOT, MAP_HTML_PATH).replaceAll("\\", "/"));
  console.log(path.relative(ROOT, MAP_STATE_PATH).replaceAll("\\", "/"));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
