import { spawn } from "node:child_process";
import { once } from "node:events";
import { existsSync } from "node:fs";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PACK_ROOT = path.join(
  ROOT,
  "frontend",
  "src",
  "assets",
  "citybuilder-svg-mvp-v2",
  "citybuilder_svg_mvp_v2",
);
const CATALOG_PATH = path.join(PACK_ROOT, "metadata", "asset_catalog.json");
const MANIFEST_PATH = path.join(PACK_ROOT, "metadata", "asset_image_adjacency_128.json");
const PNG_ROOT = path.join(PACK_ROOT, "assets_png_128");
const PREVIEW_HTML_PATH = path.join(PACK_ROOT, "preview_png_128.html");

const TILE_SIZE = 128;
const SOURCE_TILE_VIEWBOX = [24, 24, 112, 112];
const DIRECTIONS = ["top", "right", "bottom", "left"];
const OPPOSITE = { top: "bottom", right: "left", bottom: "top", left: "right" };
const TRANSPARENT_EDGES = { top: "transparent", right: "transparent", bottom: "transparent", left: "transparent" };

const SPRITE_IDS = new Set([
  "farm_barn",
  "greenhouse",
]);

const ROAD_EDGES = {
  road_straight: { top: "grass", right: "road", bottom: "grass", left: "road" },
  road_vertical: { top: "road", right: "grass", bottom: "road", left: "grass" },
  road_corner: { top: "road", right: "road", bottom: "grass", left: "grass" },
  road_t_junction: { top: "road", right: "road", bottom: "grass", left: "road" },
  road_cross: { top: "road", right: "road", bottom: "road", left: "road" },
  road_dead_end: { top: "grass", right: "grass", bottom: "grass", left: "road" },
  road_avenue: { top: "grass", right: "road", bottom: "grass", left: "road" },
  road_bridge: { top: "water", right: "road", bottom: "water", left: "road" },
  road_roundabout: { top: "road", right: "road", bottom: "road", left: "road" },
  rail_crossing: { top: "grass", right: "road", bottom: "grass", left: "road" },
};

const TERRAIN_EDGES = {
  grass_tile_a: edge("grass"),
  grass_tile_b: edge("grass"),
  dirt_tile: edge("dirt"),
  empty_lot_tile: edge("grass"),
  sand_tile: edge("sand"),
  farm_ground_tile: edge("farm"),
  park_ground_tile: edge("park"),
  water_tile: edge("water"),
  pond_tile: edge("park"),
  coast_edge_north: { top: "water", right: "sand", bottom: "sand", left: "sand" },
  coast_edge_corner: { top: "water", right: "water", bottom: "sand", left: "sand" },
  coast_inlet_tile: { top: "water", right: "coast", bottom: "sand", left: "coast" },
};

const FARM_TILE_EDGES = {
  wheat_farm: edge("farm"),
  vegetable_farm: edge("farm"),
  orchard_farm: edge("farm"),
  livestock_ranch: edge("farm"),
};

const CIVIC_EDGES = {
  sidewalk_plaza: edge("paved"),
};

function edge(socket) {
  return { top: socket, right: socket, bottom: socket, left: socket };
}

function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ].filter(Boolean);

  const found = candidates.find((candidate) => existsSync(candidate));
  if (!found) {
    throw new Error("Chrome or Edge was not found. Set CHROME_PATH to export PNG assets.");
  }
  return found;
}

function assertInside(child, parent) {
  const relative = path.relative(parent, child);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`Refusing to write outside expected root: ${child}`);
  }
}

function svgInner(svgText) {
  return svgText
    .replace(/^\s*<svg\b[^>]*>/i, "")
    .replace(/<\/svg>\s*$/i, "");
}

function renderHtml(svgText) {
  const [x, y, width, height] = SOURCE_TILE_VIEWBOX;
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
html, body { margin: 0; width: ${TILE_SIZE}px; height: ${TILE_SIZE}px; overflow: hidden; background: transparent; }
svg { display: block; width: ${TILE_SIZE}px; height: ${TILE_SIZE}px; }
</style>
</head>
<body>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="${x} ${y} ${width} ${height}" width="${TILE_SIZE}" height="${TILE_SIZE}">
${svgInner(svgText)}
</svg>
</body>
</html>`;
}

class CdpClient {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.nextId = 1;
    this.pending = new Map();
    this.eventWaiters = new Map();
  }

  async connect() {
    this.ws = new WebSocket(this.url);
    await new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
    this.ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const { resolve, reject } = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) reject(new Error(message.error.message));
        else resolve(message.result ?? {});
        return;
      }
      if (message.method && this.eventWaiters.has(message.method)) {
        const waiters = this.eventWaiters.get(message.method);
        this.eventWaiters.delete(message.method);
        waiters.forEach((resolve) => resolve(message.params ?? {}));
      }
    });
  }

  send(method, params = {}) {
    const id = this.nextId;
    this.nextId += 1;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });
  }

  waitFor(method) {
    return new Promise((resolve) => {
      const waiters = this.eventWaiters.get(method) ?? [];
      waiters.push(resolve);
      this.eventWaiters.set(method, waiters);
    });
  }

  close() {
    this.ws?.close();
  }
}

async function waitForDevToolsPort(profileDir) {
  const portFile = path.join(profileDir, "DevToolsActivePort");
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    if (existsSync(portFile)) {
      const [port] = (await readFile(portFile, "utf8")).trim().split(/\r?\n/);
      return port;
    }
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  throw new Error("Timed out waiting for Chrome DevTools port.");
}

async function createPage(port) {
  const response = await fetch(`http://127.0.0.1:${port}/json/new`, { method: "PUT" });
  if (!response.ok) {
    throw new Error(`Could not create Chrome page: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function navigateAndCapture(client, html) {
  const dataUrl = `data:text/html;charset=utf-8,${encodeURIComponent(html)}`;
  const loaded = client.waitFor("Page.loadEventFired");
  await client.send("Page.navigate", { url: dataUrl });
  await loaded;
  const result = await client.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    omitBackground: true,
    captureBeyondViewport: false,
  });
  return Buffer.from(result.data, "base64");
}

function assetPngPath(asset) {
  const svgRelative = String(asset.file);
  const pngRelative = svgRelative.replace(/^assets\//, "assets_png_128/").replace(/\.svg$/i, ".png");
  return {
    packRelative: pngRelative.replaceAll("\\", "/"),
    absolute: path.join(PACK_ROOT, pngRelative),
  };
}

function connectivityRole(asset) {
  const category = String(asset.category);
  const id = String(asset.id);
  if (category === "building" || category === "prop" || category === "overlay" || SPRITE_IDS.has(id)) {
    return category === "overlay" ? "overlay" : "sprite";
  }
  if (category === "road") return "road_tile";
  return "base_tile";
}

function edgesFor(asset) {
  const id = String(asset.id);
  const category = String(asset.category);
  if (ROAD_EDGES[id]) return ROAD_EDGES[id];
  if (TERRAIN_EDGES[id]) return TERRAIN_EDGES[id];
  if (FARM_TILE_EDGES[id]) return FARM_TILE_EDGES[id];
  if (CIVIC_EDGES[id]) return CIVIC_EDGES[id];
  if (category === "building" || category === "prop" || category === "overlay" || SPRITE_IDS.has(id)) {
    return TRANSPARENT_EDGES;
  }
  return edge("grass");
}

function usesAdjacency(asset) {
  const role = connectivityRole(asset);
  return role === "base_tile" || role === "road_tile";
}

function socketsMatch(a, b) {
  if (a === b) return true;
  if (a === "transparent" || b === "transparent") return true;
  if (a === "road" || b === "road") return a === "road" && b === "road";
  if (a === "water" || b === "water") return a === "water" && b === "water" || a === "coast" || b === "coast";
  if (a === "coast" || b === "coast") return ["water", "sand", "coast"].includes(a) && ["water", "sand", "coast"].includes(b);
  return ["grass", "dirt", "sand", "farm", "park", "paved"].includes(a)
    && ["grass", "dirt", "sand", "farm", "park", "paved"].includes(b);
}

function roadConnections(edges) {
  return Object.fromEntries(DIRECTIONS.map((direction) => [direction, edges[direction] === "road"]));
}

function compatibleNeighbors(assetRecord, candidates) {
  if (!assetRecord.usesAdjacency) {
    return { top: [], right: [], bottom: [], left: [] };
  }

  return Object.fromEntries(DIRECTIONS.map((direction) => {
    const opposite = OPPOSITE[direction];
    const matches = candidates
      .filter((candidate) => candidate.usesAdjacency)
      .filter((candidate) => socketsMatch(assetRecord.edgeSockets[direction], candidate.edgeSockets[opposite]))
      .map((candidate) => candidate.id);
    return [direction, matches];
  }));
}

function renderPreviewHtml(records) {
  const cards = records.map((record) => `
    <article class="card" data-category="${record.category}">
      <img src="${record.image.packRelativePath}" alt="${record.title}">
      <strong>${record.title}</strong>
      <span>${record.id} · ${record.connectivityRole}</span>
    </article>`).join("\n");

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CityBuilder 128 PNG Assets</title>
<style>
  :root { color-scheme: dark; --bg:#07111b; --panel:#0d1d2b; --line:#1e3d54; --text:#f5f7fb; --muted:#9cc1df; }
  * { box-sizing: border-box; }
  body { margin:0; background:#07111b; color:var(--text); font-family:Inter, Segoe UI, Arial, sans-serif; }
  header { padding:18px 22px; border-bottom:1px solid var(--line); background:#050d14; }
  h1 { margin:0 0 5px; font-size:24px; letter-spacing:0; }
  p { margin:0; color:var(--muted); font-size:14px; }
  main { padding:24px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(170px, 1fr)); gap:16px; }
  .card { min-height:214px; border:1px solid var(--line); border-radius:8px; padding:16px; background:var(--panel); display:grid; justify-items:center; align-content:center; gap:10px; }
  img { width:128px; height:128px; image-rendering:auto; background:linear-gradient(45deg, #0b1720 25%, #102331 25% 50%, #0b1720 50% 75%, #102331 75%); background-size:16px 16px; }
  strong { font-size:14px; text-align:center; }
  span { color:var(--muted); font-size:12px; text-align:center; }
</style>
</head>
<body>
<header>
  <h1>CityBuilder 128 PNG Assets</h1>
  <p>Generated from the top-down SVG pack. Edge sockets and image paths are stored in metadata/asset_image_adjacency_128.json.</p>
</header>
<main>
  <section class="grid">
${cards}
  </section>
</main>
</body>
</html>`;
}

async function main() {
  assertInside(PNG_ROOT, PACK_ROOT);
  await rm(PNG_ROOT, { recursive: true, force: true });
  await mkdir(PNG_ROOT, { recursive: true });

  const catalog = JSON.parse(await readFile(CATALOG_PATH, "utf8"));
  const assets = catalog.assets;
  const chromePath = findChrome();
  const profileDir = path.join(os.tmpdir(), `citybuilder-png-export-${Date.now()}`);
  await mkdir(profileDir, { recursive: true });

  const chrome = spawn(chromePath, [
    "--headless=new",
    "--disable-gpu",
    "--allow-file-access-from-files",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-debugging-port=0",
    `--user-data-dir=${profileDir}`,
    "about:blank",
  ], { stdio: "ignore" });

  let client;
  try {
    const port = await waitForDevToolsPort(profileDir);
    const page = await createPage(port);
    client = new CdpClient(page.webSocketDebuggerUrl);
    await client.connect();
    await client.send("Page.enable");
    await client.send("Emulation.setDeviceMetricsOverride", {
      width: TILE_SIZE,
      height: TILE_SIZE,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await client.send("Emulation.setDefaultBackgroundColorOverride", {
      color: { r: 0, g: 0, b: 0, a: 0 },
    });

    const records = [];
    for (const asset of assets) {
      const id = String(asset.id);
      const sourceSvg = String(asset.file);
      const sourcePath = path.join(PACK_ROOT, sourceSvg);
      const output = assetPngPath(asset);
      assertInside(output.absolute, PACK_ROOT);
      await mkdir(path.dirname(output.absolute), { recursive: true });

      const svgText = await readFile(sourcePath, "utf8");
      const png = await navigateAndCapture(client, renderHtml(svgText));
      await writeFile(output.absolute, png);

      const edgeSockets = edgesFor(asset);
      const role = connectivityRole(asset);
      records.push({
        id,
        title: String(asset.title),
        category: String(asset.category),
        connectivityRole: role,
        usesAdjacency: usesAdjacency(asset),
        size: [TILE_SIZE, TILE_SIZE],
        sourceViewBox: SOURCE_TILE_VIEWBOX,
        image: {
          packRelativePath: output.packRelative,
          projectRelativePath: path.relative(ROOT, output.absolute).replaceAll("\\", "/"),
        },
        sourceSvg: {
          packRelativePath: sourceSvg,
          projectRelativePath: path.relative(ROOT, sourcePath).replaceAll("\\", "/"),
        },
        edgeSockets,
        roadConnections: roadConnections(edgeSockets),
      });
    }

    const finalized = records.map((record) => ({
      ...record,
      compatibleNeighbors: compatibleNeighbors(record, records),
    }));

    const manifest = {
      version: "1.0",
      generatedFrom: {
        catalog: path.relative(ROOT, CATALOG_PATH).replaceAll("\\", "/"),
        sourcePackVersion: catalog.version,
      },
      tileSize: [TILE_SIZE, TILE_SIZE],
      sourceTileViewBox: SOURCE_TILE_VIEWBOX,
      directions: {
        top: "north",
        right: "east",
        bottom: "south",
        left: "west",
      },
      rules: {
        matching: "Compare an asset edge socket with the opposite edge socket of the neighbor.",
        road: "A road edge only attaches to another road edge.",
        coast: "A coast edge can attach to water, sand, or coast.",
        land: "Grass, dirt, sand, farm, park, and paved edges can sit next to each other.",
        transparent: "Sprite and overlay assets do not drive tile adjacency; place them on top of base tiles.",
      },
      assets: finalized,
    };

    await writeFile(MANIFEST_PATH, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
    await writeFile(PREVIEW_HTML_PATH, renderPreviewHtml(finalized), "utf8");
    console.log(`Exported ${finalized.length} PNG assets to ${path.relative(ROOT, PNG_ROOT)}`);
    console.log(`Wrote ${path.relative(ROOT, MANIFEST_PATH)}`);
  } finally {
    client?.close();
    if (!chrome.killed) {
      chrome.kill();
    }
    try {
      await once(chrome, "exit");
    } catch {
      // Chrome may already be gone.
    }
    await rm(profileDir, { recursive: true, force: true }).catch(() => undefined);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
