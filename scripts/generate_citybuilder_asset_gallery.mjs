import { readFile, writeFile } from "node:fs/promises";
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
const MANIFEST_PATH = path.join(PACK_ROOT, "metadata", "asset_image_adjacency_128.json");
const VIEWER_PATH = path.join(PACK_ROOT, "all_assets_viewer.html");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function assetCard(asset) {
  const role = asset.connectivityRole;
  const category = asset.category;
  const sockets = asset.edgeSockets ?? {};
  const socketText = ["top", "right", "bottom", "left"]
    .map((side) => `${side}:${sockets[side] ?? "none"}`)
    .join(" ");
  const generated = asset.imagegenSource ? "imagegen" : "svg";
  const sourcePath = asset.sourceSvg?.packRelativePath ?? "";

  return `<article class="asset-card" data-id="${escapeHtml(asset.id)}" data-title="${escapeHtml(asset.title)}" data-category="${escapeHtml(category)}" data-role="${escapeHtml(role)}" data-source="${generated}">
  <a class="preview" href="${escapeHtml(asset.image.packRelativePath)}" target="_blank" aria-label="${escapeHtml(asset.title)} PNG">
    <img src="${escapeHtml(asset.image.packRelativePath)}" alt="${escapeHtml(asset.title)}" loading="lazy">
  </a>
  <div class="asset-info">
    <div class="asset-title">
      <strong>${escapeHtml(asset.title)}</strong>
      <span>${escapeHtml(generated)}</span>
    </div>
    <code>${escapeHtml(asset.id)}</code>
    <div class="meta">
      <span>${escapeHtml(category)}</span>
      <span>${escapeHtml(role)}</span>
    </div>
    <div class="edges" aria-label="edge sockets">${escapeHtml(socketText)}</div>
    <div class="links">
      <a href="${escapeHtml(asset.image.packRelativePath)}" target="_blank">PNG</a>
      ${sourcePath ? `<a href="${escapeHtml(sourcePath)}" target="_blank">SVG</a>` : ""}
    </div>
  </div>
</article>`;
}

function buttonGroup(values, group, allLabel) {
  const buttons = [`<button class="filter active" type="button" data-group="${group}" data-value="all">${allLabel}</button>`];
  for (const value of values) {
    buttons.push(`<button class="filter" type="button" data-group="${group}" data-value="${escapeHtml(value)}">${escapeHtml(value)}</button>`);
  }
  return buttons.join("");
}

function renderHtml(manifest) {
  const assets = manifest.assets;
  const categories = [...new Set(assets.map((asset) => asset.category))].sort();
  const roles = [...new Set(assets.map((asset) => asset.connectivityRole))].sort();
  const cards = assets.map(assetCard).join("\n");
  const counts = {
    total: assets.length,
    png128: assets.filter((asset) => asset.size?.[0] === 128 && asset.size?.[1] === 128).length,
    imagegen: assets.filter((asset) => asset.imagegenSource).length,
  };

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CityBuilder Asset Gallery</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #07111b;
    --panel: #0d1d2b;
    --panel-2: #102435;
    --line: #23465f;
    --line-soft: #18344a;
    --text: #f5f7fb;
    --muted: #9cc1df;
    --accent: #5fc8ff;
    --good: #8edb6a;
    --warn: #ffd15f;
    --tile-size: 128px;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: Inter, "Segoe UI", Arial, sans-serif;
  }
  header {
    position: sticky;
    top: 0;
    z-index: 2;
    border-bottom: 1px solid var(--line);
    background: color-mix(in srgb, var(--bg) 92%, black);
  }
  .bar {
    display: grid;
    gap: 12px;
    padding: 16px 18px;
  }
  .title-row {
    display: flex;
    align-items: end;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
  }
  h1 {
    margin: 0;
    font-size: 22px;
    letter-spacing: 0;
  }
  .counts {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    color: var(--muted);
    font-size: 12px;
  }
  .pill {
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 5px 9px;
    background: var(--panel);
  }
  .controls {
    display: grid;
    grid-template-columns: minmax(220px, 1fr) auto auto;
    gap: 10px;
    align-items: center;
  }
  input, select {
    height: 38px;
    border: 1px solid var(--line);
    border-radius: 7px;
    background: var(--panel);
    color: var(--text);
    padding: 0 11px;
    font: inherit;
  }
  .filters {
    display: flex;
    gap: 7px;
    flex-wrap: wrap;
  }
  button {
    height: 34px;
    border: 1px solid var(--line);
    border-radius: 7px;
    background: var(--panel);
    color: var(--muted);
    padding: 0 10px;
    font: inherit;
    cursor: pointer;
  }
  button.active {
    border-color: var(--accent);
    background: #12344b;
    color: var(--text);
  }
  main {
    padding: 18px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(238px, 1fr));
    gap: 14px;
  }
  .asset-card {
    border: 1px solid var(--line-soft);
    border-radius: 8px;
    background: var(--panel);
    overflow: hidden;
  }
  .preview {
    display: grid;
    place-items: center;
    min-height: calc(var(--tile-size) + 38px);
    padding: 18px;
    border-bottom: 1px solid var(--line-soft);
    background: var(--preview-bg);
  }
  body[data-bg="checker"] .preview {
    --preview-bg:
      linear-gradient(45deg, #0b1720 25%, transparent 25% 75%, #0b1720 75%),
      linear-gradient(45deg, #102331 25%, transparent 25% 75%, #102331 75%);
    background-position: 0 0, 8px 8px;
    background-size: 16px 16px;
    background-color: #0d1d2b;
  }
  body[data-bg="grass"] .preview { --preview-bg: #6f9d34; }
  body[data-bg="sand"] .preview { --preview-bg: #d9c081; }
  body[data-bg="water"] .preview { --preview-bg: #287faf; }
  body[data-bg="road"] .preview { --preview-bg: #4b535c; }
  body[data-bg="dark"] .preview { --preview-bg: #07111b; }
  img {
    width: var(--tile-size);
    height: var(--tile-size);
    image-rendering: auto;
  }
  .asset-info {
    display: grid;
    gap: 8px;
    padding: 12px;
  }
  .asset-title {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    align-items: baseline;
  }
  strong {
    font-size: 14px;
    line-height: 1.2;
  }
  .asset-title span {
    color: var(--good);
    font-size: 11px;
    text-transform: uppercase;
  }
  code {
    color: var(--muted);
    font-size: 12px;
    word-break: break-word;
  }
  .meta, .links {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .meta span, .links a {
    border: 1px solid var(--line-soft);
    border-radius: 999px;
    padding: 4px 7px;
    color: var(--muted);
    font-size: 11px;
    text-decoration: none;
  }
  .links a {
    color: var(--accent);
  }
  .edges {
    color: #b9c9d6;
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 10px;
    line-height: 1.35;
  }
  .empty {
    display: none;
    margin: 30px 0;
    color: var(--muted);
  }
  .empty.visible {
    display: block;
  }
  @media (max-width: 760px) {
    .controls {
      grid-template-columns: 1fr;
    }
    .grid {
      grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
    }
  }
</style>
</head>
<body data-bg="checker">
<header>
  <div class="bar">
    <div class="title-row">
      <h1>CityBuilder Asset Gallery</h1>
      <div class="counts">
        <span class="pill"><strong id="visibleCount">${counts.total}</strong> shown</span>
        <span class="pill">${counts.total} total</span>
        <span class="pill">${counts.png128} at 128x128</span>
        <span class="pill">${counts.imagegen} imagegen sprites</span>
      </div>
    </div>
    <div class="controls">
      <input id="search" type="search" placeholder="Search assets" autocomplete="off">
      <select id="background">
        <option value="checker">Checker</option>
        <option value="grass">Grass</option>
        <option value="sand">Sand</option>
        <option value="water">Water</option>
        <option value="road">Road</option>
        <option value="dark">Dark</option>
      </select>
      <select id="zoom">
        <option value="96">96 px</option>
        <option value="128" selected>128 px</option>
        <option value="160">160 px</option>
        <option value="192">192 px</option>
      </select>
    </div>
    <div class="filters" id="categoryFilters">${buttonGroup(categories, "category", "all categories")}</div>
    <div class="filters" id="roleFilters">${buttonGroup(roles, "role", "all roles")}</div>
  </div>
</header>
<main>
  <section class="grid" id="grid">
${cards}
  </section>
  <p class="empty" id="empty">No assets match the current filters.</p>
</main>
<script>
  const state = { category: "all", role: "all", search: "" };
  const cards = Array.from(document.querySelectorAll(".asset-card"));
  const visibleCount = document.getElementById("visibleCount");
  const empty = document.getElementById("empty");
  const search = document.getElementById("search");
  const background = document.getElementById("background");
  const zoom = document.getElementById("zoom");

  function applyFilters() {
    const query = state.search.trim().toLowerCase();
    let count = 0;
    for (const card of cards) {
      const matchesCategory = state.category === "all" || card.dataset.category === state.category;
      const matchesRole = state.role === "all" || card.dataset.role === state.role;
      const haystack = [card.dataset.id, card.dataset.title, card.dataset.category, card.dataset.role, card.dataset.source].join(" ").toLowerCase();
      const matchesSearch = !query || haystack.includes(query);
      const visible = matchesCategory && matchesRole && matchesSearch;
      card.hidden = !visible;
      if (visible) count += 1;
    }
    visibleCount.textContent = String(count);
    empty.classList.toggle("visible", count === 0);
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("button.filter");
    if (!button) return;
    const group = button.dataset.group;
    state[group] = button.dataset.value;
    document.querySelectorAll(\`button.filter[data-group="\${group}"]\`).forEach((item) => {
      item.classList.toggle("active", item === button);
    });
    applyFilters();
  });

  search.addEventListener("input", () => {
    state.search = search.value;
    applyFilters();
  });

  background.addEventListener("change", () => {
    document.body.dataset.bg = background.value;
  });

  zoom.addEventListener("change", () => {
    document.documentElement.style.setProperty("--tile-size", \`\${zoom.value}px\`);
  });
</script>
</body>
</html>`;
}

async function main() {
  const manifest = JSON.parse(await readFile(MANIFEST_PATH, "utf8"));
  await writeFile(VIEWER_PATH, renderHtml(manifest), "utf8");
  console.log(path.relative(ROOT, VIEWER_PATH).replaceAll("\\", "/"));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
