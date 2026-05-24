import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BUNDLE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DEFAULT_MAP_PATH = path.join(BUNDLE_ROOT, "examples", "example_map.json");
const DEFAULT_ASSETS_PATH = path.join(BUNDLE_ROOT, "metadata", "assets.json");
const DEFAULT_OUTPUT_PATH = path.join(BUNDLE_ROOT, "output", "example_map.html");
const LAYER_ORDER = ["terrain", "ground", "roads", "rail", "overlays", "sprites"];

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function normalizePath(value) {
  return value.replaceAll(path.sep, "/");
}

function parseArgs() {
  const args = process.argv.slice(2);
  return {
    mapPath: args[0] ? path.resolve(args[0]) : DEFAULT_MAP_PATH,
    assetsPath: args[1] ? path.resolve(args[1]) : DEFAULT_ASSETS_PATH,
    outputPath: args[2] ? path.resolve(args[2]) : DEFAULT_OUTPUT_PATH,
  };
}

function assetLookup(manifest) {
  return Object.fromEntries(manifest.assets.map((asset) => [asset.id, asset]));
}

function imageSrc(asset, outputPath) {
  const imagePath = asset.image?.packRelativePath ?? asset.file;
  if (!imagePath) {
    throw new Error(`Asset ${asset.id} does not declare an image path.`);
  }
  return normalizePath(path.relative(path.dirname(outputPath), path.join(BUNDLE_ROOT, imagePath)));
}

function orderedLayers(layers) {
  const known = LAYER_ORDER.filter((name) => Array.isArray(layers[name]));
  const extra = Object.keys(layers).filter((name) => !known.includes(name)).sort();
  return [...known, ...extra];
}

function tileImage(entry, asset, outputPath, cssClass) {
  const rotation = entry.rotation ?? 0;
  const title = `${asset.title ?? asset.id} at ${entry.x},${entry.y}`;
  return `<img class="tile ${cssClass}" src="${escapeHtml(imageSrc(asset, outputPath))}" alt="${escapeHtml(title)}" title="${escapeHtml(title)}" style="--x:${entry.x};--y:${entry.y};--r:${rotation}deg">`;
}

function renderLayer(name, entries, assets, outputPath) {
  return entries.map((entry) => {
    const asset = assets[entry.assetId];
    if (!asset) {
      throw new Error(`Unknown asset id "${entry.assetId}" in layer "${name}".`);
    }
    return tileImage(entry, asset, outputPath, name);
  }).join("\n");
}

function renderRailFeature(mapState, assets, outputPath) {
  const rail = mapState.features?.rail;
  if (!rail?.tiles?.length) return "";
  const asset = assets[rail.assetId];
  if (!asset) {
    throw new Error(`Unknown rail asset id "${rail.assetId}".`);
  }
  return rail.tiles.map((tile) => tileImage({
    assetId: rail.assetId,
    x: tile.x,
    y: tile.y,
    rotation: tile.rotation ?? 0,
  }, asset, outputPath, "rail")).join("\n");
}

function renderHtml(mapState, manifest, outputPath) {
  const assets = assetLookup(manifest);
  const tileSize = mapState.renderTileSize ?? 72;
  const layers = orderedLayers(mapState.layers ?? {});
  const layerMarkup = layers.map((name) => renderLayer(name, mapState.layers[name], assets, outputPath)).join("\n");
  const railMarkup = renderRailFeature(mapState, assets, outputPath);
  const width = mapState.width * tileSize;
  const height = mapState.height * tileSize;

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(mapState.title ?? mapState.mapId ?? "CityBuilder Map")}</title>
<style>
  :root { --tile: ${tileSize}px; color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    min-height: 100vh;
    display: grid;
    place-items: start center;
    background: #07111b;
    color: #f5f7fb;
    font-family: Inter, "Segoe UI", Arial, sans-serif;
  }
  .wrap { padding: 18px; }
  h1 { margin: 0 0 12px; font-size: 20px; letter-spacing: 0; }
  .map {
    position: relative;
    width: ${width}px;
    height: ${height}px;
    background: #102331;
    overflow: hidden;
    isolation: isolate;
  }
  .map::after {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background-image:
      linear-gradient(to right, rgba(255,255,255,.14) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(255,255,255,.14) 1px, transparent 1px);
    background-size: var(--tile) var(--tile);
    z-index: 10;
  }
  .tile {
    position: absolute;
    left: calc(var(--x) * var(--tile));
    top: calc(var(--y) * var(--tile));
    width: var(--tile);
    height: var(--tile);
    transform: rotate(var(--r));
    transform-origin: center;
    user-select: none;
  }
  .terrain, .ground, .roads { z-index: 1; }
  .rail { z-index: 2; }
  .overlays { z-index: 3; }
  .sprites { z-index: 4; }
</style>
</head>
<body>
  <main class="wrap">
    <h1>${escapeHtml(mapState.title ?? "CityBuilder Map")}</h1>
    <section class="map" aria-label="CityBuilder rendered map">
${railMarkup}
${layerMarkup}
    </section>
  </main>
</body>
</html>`;
}

async function main() {
  const { mapPath, assetsPath, outputPath } = parseArgs();
  const mapState = JSON.parse(await readFile(mapPath, "utf8"));
  const manifest = JSON.parse(await readFile(assetsPath, "utf8"));
  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, renderHtml(mapState, manifest, outputPath), "utf8");
  console.log(normalizePath(path.relative(BUNDLE_ROOT, outputPath)));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
