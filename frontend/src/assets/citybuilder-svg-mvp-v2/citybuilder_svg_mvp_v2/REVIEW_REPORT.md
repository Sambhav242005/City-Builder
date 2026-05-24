# CityBuilder SVG MVP Pack v2 - Review Report

## Fix Summary

**Status: converted to a top-down simulation asset vocabulary.**

The asset pack now uses a flat map perspective instead of the earlier isometric/2.5D look. It is organized around gameplay roles instead of decorative icons, so the dummy map/model flow can reason about what each tile does.

Changes made:

- Rebuilt all SVGs as top-down assets.
- Removed 2.5D side faces and isometric diamond bases.
- Removed terrain/foundation backgrounds from standalone building sprites.
- Kept shadows using per-asset filter IDs, so inline SVGs do not collide.
- Clipped road geometry to the visible tile footprint, so roads cannot spill outside the tile.
- Converted buildings into top-down roof/footprint sprites instead of front-facing facades.
- Fixed `coast_inlet_tile.svg` so it reads as a coast inlet instead of a pond icon.
- Converted `sidewalk_plaza` from a road into a civic/amenity tile.
- Converted `road_preview_overlay.svg` into a real transparent overlay, not a full road tile.
- Added farm variants with economy metadata for price/supply effects: wheat, vegetable, orchard, and livestock.
- Reclassified `farm_barn` and `greenhouse` as farm assets.
- Added placement/economy metadata for props such as streetlights and decorative rock clusters.
- Regenerated preview and alignment HTML files from the fixed SVG sources.

## Alignment Rules

Every asset still uses `viewBox="0 0 160 160"`.

Terrain, farm, civic, and road assets use the same top-down tile footprint:

- Main footprint: `x=24 y=24 width=112 height=112 rx=10`
- Roads are clipped to the footprint, including connectors, roundabouts, bridges, and rail crossings.
- Buildings are transparent sprites intended to sit on top of terrain/zone tiles.
- Overlays are transparent and do not contain terrain or road bases.
- Props live on the prop layer and should not block building placement unless metadata explicitly says so.

## Asset Count

| Category | Count |
|---|---:|
| building | 16 |
| civic | 1 |
| farm | 6 |
| overlay | 8 |
| prop | 6 |
| road | 10 |
| terrain | 12 |

Total: **59 SVG assets**

## Preview

Use `preview_relative.html` inside the pack folder to check the real SVG files.

Use `preview_standalone.html` for a single self-contained inline preview.

Use `alignment_check.html` to verify mixed tile alignment in a top-down grid.
