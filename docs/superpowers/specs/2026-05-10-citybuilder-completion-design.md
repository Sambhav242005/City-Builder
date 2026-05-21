# CityBuilder Completion Design

## Scope

Complete the existing FastAPI and React city simulation by fixing agent configuration loading, making manual simulation controls usable, and adding a mayor direction metric that tells whether the city is moving in a healthy direction.

## Mayor Direction Metric

The backend will compute a `MayorScore` object on every snapshot. The score is a 0-100 outcome score based on food balance, food affordability, happiness, land pressure, and recent trend from history. It includes a status label, short summary, and factor list so the UI can explain why the score changed.

The metric is outcome based rather than only checking whether the mayor followed the advisor. This makes it harder to game and better reflects whether citizens are actually better off.

## Backend Changes

Add Pydantic models for the score and expose it in `StateResponse`. Compute it in the service from current state and history. Load agent defaults from `backend/.env` using existing keys `APIURL`, `APIKEY`, and `MODEL`, then let `agent_config.json` override them when the user saves settings. Keep API keys out of response payloads.

## Frontend Changes

Add a mayor direction card to the dashboard with score, label, trend, and factor notes. Keep the layout dense and operational, matching the existing simulator style. Manual tick/run controls should work without agent configuration; only asking the external agent should require agent settings. Fix visible land costs in the build menu so they match backend land consumption.

## Testing And Inspection

Extend backend tests for score shape, score behavior, and `.env` loading. Run backend tests and frontend build. Start backend and frontend servers, then inspect the UI in a browser to verify the dashboard renders, the score appears, controls are usable, and there are no obvious runtime errors.
