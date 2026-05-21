# Map Regeneration And Agent Rate Limit Design

## Scope

Replace the current broken hybrid map with a coherent city map inspired by `frontend/ui-check.png`, and add a strict external agent request limit.

## Map Design

The map will be dynamic, not a single static generated image. The backend `cityMap.tiles` payload is the source of truth for what appears in the city. The frontend renders every tile as an interactive isometric cell. The visual layer uses a generated terrain background plus cleaned transparent 2.5D sprite assets for roads, water, farms, housing, markets, factories, parks, power plants, and government buildings.

The map should still match the reference feel: dense city blocks, clear road structure, visible farms and waterfront, and a civic center. The generated city image may remain as a visual reference, but it must not control the visible city state. When the simulation builds or changes structures, the rendered sprites update from the next API response.

The original asset PNGs remain untouched. A reproducible sprite-prep script creates project-local transparent sprite files in `frontend/src/assets/map-sprites/` so the UI does not render baked-in checkerboard backgrounds.

The map overlay has a visible toggle. When enabled, it shows district counts, land use, and selected-zone details; when disabled, the generated map and dynamic sprites remain visible without overlay panels.

## Agent Rate Limit

The backend will allow only one external `/agent/recommendation` request per 60 seconds. While a request is running, another request is rejected. When the limit blocks a request, the API returns HTTP 429 with a `retryAfterSeconds` value.

The API response will include an `agentRateLimit` object so the system can expose limit, remaining requests, reset time, and in-flight state. The Agent Settings panel is removed from the current dashboard UI; external agent defaults continue to load from backend configuration.

## Testing And Verification

Backend tests will cover the rate-limit status and HTTP 429 behavior. Frontend build must pass. Browser verification will confirm the new map renders, district controls work, the overlay toggle shows and hides map info, Agent Settings is absent, and the generated terrain background renders under the dynamic sprites.
