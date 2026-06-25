# CityBuilder MVP — Agent Instructions

## Project Overview

A stable micro-city simulation with one resource (`Food`), wrapped in a FastAPI backend and a React dashboard. The app simulates a city economy where the user acts as Mayor, approving or rejecting AI-generated policy recommendations to keep the city prosperous. Uses a fully local Q-learning optimizer.

## Tech Stack

- **Backend:** Python 3.13+, FastAPI, Pydantic, Uvicorn, WebSockets
- **Frontend:** React 19, TypeScript 5.9, Vite 7, Recharts, lucide-react
- **Map:** HTML5 Canvas tile engine (14×9 grid)
- **AI:** Q-learning agent with epsilon-greedy policy, local evolution optimizer
- **Infra:** Docker Compose, Nginx, GitHub Actions (Raspberry Pi deploy)

## Project Structure

```
backend/app/          # FastAPI app (main.py, models.py, simulation.py, service.py, city_map.py, q_agent.py, rl_policy.py, training_harness.py)
backend/tests/        # Pytest suite
backend/data/         # Persisted Q-table + training report
frontend/src/         # React app (App.tsx, CityCanvasMap.tsx, api.ts, types.ts, experiments.ts, styles.css)
deploy/               # Docker Compose, Nginx config, deploy docs
scripts/              # Asset preparation scripts
docs/superpowers/specs/  # Design documents
```

## Key Architecture

- **Simulation tick:** supply/demand → price → happiness → events
- **Policy engine:** Q-learning evaluates all actions → recommends best
- **Mayor:** User approves/rejects → decision recorded in scorecard
- **Map:** Persistent 14×9 tile grid with roads, zones, buildings, props
- **Dashboard:** Economy charts, interactive map, optimizer trace, action panel

## Commands

```powershell
# Backend
cd backend; ..\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
cd backend; ..\.venv\Scripts\python -m pytest
cd backend; ..\.venv\Scripts\python -m app.training_harness

# Frontend
cd frontend; npm install; npm run dev
cd frontend; npm run build
```

## Portfolio Cover Asset

Maintain a project-specific SVG at `docs/portfolio-cover.svg`.

Rules:
- The SVG must be hand-authored/static, not a raster screenshot, AI-generated image, base64 image, or external asset.
- Use `width="1200"`, `height="760"`, `viewBox="0 0 1200 760"`.
- It should visually summarize the real current project: architecture, workflow, UI, model pipeline, or system behavior.
- Update this SVG whenever major project functionality, architecture, or branding changes.
- Keep text minimal and readable at thumbnail size.
- No fake product names, unrelated placeholder visuals, or generic charts.
- The portfolio repo may copy this file into `public/project-assets` as the local backup/rendering copy.

## Conventions

- Follow existing patterns in the codebase (same libraries, same styles, same testing approach).
- No unnecessary comments in code.
- Verify changes with `pytest` (backend) and `npm run build` (frontend) before committing.
