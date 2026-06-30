---
contentKind: article
slug: "canvas-city-map-rendering-with-procedural-roads-and-assets"
title: "Canvas City Map Rendering with Procedural Roads and Assets"
type: technical-note
status: published
date: 2026-06-20
summary: "Building an interactive 14x9 tile map renderer in plain HTML5 Canvas — procedural road connections, 40+ sprite variants, deterministic props, and full pan/zoom/click interaction."
tags:
  - TypeScript
  - Canvas
  - Game Development
  - Procedural Generation
  - Frontend
---

## Why Canvas, Not SVG or a Game Engine

CityBuilder needed a city map that was interactive (pan, zoom, click to inspect), data-driven (render state from the backend), and lightweight enough to run on a Raspberry Pi's browser. A game engine like Phaser was overkill. SVG would struggle with 126 tiles by multiple layers. Canvas gave me a single raster surface I could redraw 60 times a second with full control over every pixel.

## Tile Grid Architecture

The map is a 14x9 grid of 64x64 px tiles. Each tile has a **zone** (residential, commercial, industrial, park) and optionally a **building** or **road**. The backend (`city_map.py`) manages the grid as a persistent data structure; the frontend (`CityCanvasMap.tsx`) renders it.

Layers are drawn bottom-to-top:

1. **Terrain** — grass, dirt, or water base tiles
2. **Zones** — coloured overlays indicating land use
3. **Roads** — procedural connection-aware road segments
4. **Buildings** — type and level-variant sprites
5. **Props** — trees, cars, streetlights, bushes, rocks (placed deterministically)

## Procedural Road System

Roads are the most technically interesting piece. Each road tile checks its four neighbours (N, S, E, W) for connecting roads, then selects the correct visual variant from a lookup table:

| Neighbour pattern | Render style |
|---|---|
| Single connection (e.g., only N) | Dead end — rounded cap |
| Two opposite (N-S or E-W) | Straight segment |
| Two adjacent (N-E, etc.) | Corner |
| Three (e.g., N-S-E) | T-junction |
| Four | Cross intersection |

Each road tile is drawn procedurally in three passes:

1. **Curb** — dark grey border with rounded outer corners
2. **Asphalt** — filled mid-grey interior
3. **Centre dashes** — white dashes or yellow double-line depending on road type

No sprite sheets needed — every road is pure Canvas path calls, which means infinite visual variety at zero asset cost.

## Building Sprite System

Buildings are rendered as procedural vectors with type-specific silhouettes and colour palettes. Each building type (farm, residential, factory, market, power plant) has 2-4 level variants:

- **Farms**: wheat field (level 1), vegetable rows (2), orchard rows (3), livestock pen (4)
- **Residential**: cottage (1), suburban house (2), townhouse (3), apartment (4)
- **Factories**: workshop (1), industrial unit (2), factory complex (3), processing plant (4)

Each variant is drawn with a combination of rectangles, triangles (roofs), and detail marks (windows, doors, silos). The result is 40+ visually distinct building looks from about 200 lines of drawing code.

## Deterministic Prop Placement

Props (trees, cars, streetlights, bushes, rocks) are placed using a seeded pseudo-random function based on the tile coordinates:

```typescript
const seed = x * 31 + y * 17;
```

This means every tile has the same decorations every time it renders, without storing prop positions in the backend. The density and variety are controlled by per-tile random checks against configurable thresholds.

## Interaction System

The map supports:

- **Pan** — click and drag with pointer events (touch-compatible)
- **Zoom** — mouse wheel or pinch gesture
- **Click-to-select** — click a tile to open the inspector panel
- **Keyboard navigation** — arrow keys pan the viewport

The camera transform is managed as a `{x, y, zoom}` object applied via `ctx.setTransform()` on every frame. Zoom clamps between 0.5x and 3x; the viewport follows the mouse position during zoom to keep the cursor point stable.

## Performance

Rendering 126 tiles with up to 5 layers each is around 630 draw calls per frame. At 60 fps that is well within budget for Canvas on a Raspberry Pi 4. The critical optimisation is **dirty region tracking**: the map only redraws when state changes, not on every animation frame. A transform change (pan/zoom) triggers a full redraw; a tile update redraws only the affected 64x64 region.

The interaction layer uses a separate off-screen canvas hit-test: when the user clicks, the click coordinates are inverse-transformed through the camera matrix to identify the tile, and a simple AABB check on the tile grid resolves the selection without iterating all elements.

## Code

The full implementation is in `frontend/src/CityCanvasMap.tsx`.
