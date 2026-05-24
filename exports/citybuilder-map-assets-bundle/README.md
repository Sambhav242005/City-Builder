# CityBuilder Map Assets Bundle

This zip contains the CityBuilder map assets and a runnable example showing how they are assembled into a map.

## Contents

- `assets/` - source SVG map assets.
- `assets_png_128/` - 128px PNG assets used by the example renderer.
- `metadata/assets.json` - asset manifest with IDs, categories, PNG paths, SVG paths, edge sockets, and neighbor compatibility rules.
- `metadata/asset_catalog.json` - original source catalog for the SVG pack.
- `metadata/action_schema.json` - action/schema reference for map actions.
- `examples/example_map.json` - example 20 x 16 map state using all 60 manifest assets.
- `code/generate-showcase-map-from-manifest.mjs` - builds the example map JSON from `metadata/assets.json` and validates roads, rail, rotations, and building access.
- `code/render-map-html.mjs` - renders a map JSON file into layered HTML using the PNG asset paths.
- `code/export-map-png.ps1` - exports the rendered HTML to PNG using Chrome or Edge headless on Windows.
- `output/example_map.html` - generated HTML map preview.
- `output/example_map.png` - generated image output for the example map.

## Regenerate The Example

From the extracted bundle folder:

```powershell
node .\code\render-map-html.mjs
powershell -ExecutionPolicy Bypass -File .\code\export-map-png.ps1
```

To rebuild the example JSON from the asset manifest:

```powershell
node .\code\generate-showcase-map-from-manifest.mjs
```

The map is composed by placing entries from `examples/example_map.json` onto a tile grid. Each entry has an `assetId`, `x`, `y`, and optional `rotation`. The renderer resolves `assetId` through `metadata/assets.json`, then layers ground tiles first, rail and overlays next, and sprites last.
