---
contentKind: case-study
title: "CityBuilder — A Self-Contained Micro-City Simulation with Local AI"
slug: "citybuilder-micro-city-simulation"
summary: "A full-stack micro-city MVP with a FastAPI simulation engine, React/TypeScript dashboard, interactive canvas map, and a local Q-learning policy agent — no external AI APIs required."
status: published
order: 1
featured: true
updatedAt: 2026-06-30
tags:
  - Python
  - FastAPI
  - React
  - TypeScript
  - Q-Learning
  - Game AI
  - Simulation
  - Canvas
---

## Problem

Most simulation projects fall apart at the boundary between backend state and frontend understanding. The simulation logic becomes a black box: state mutates in ways developers can't trace, the UI lags behind the model, and adding AI-driven decision-making typically means wiring up an external LLM API with latency, cost, and reproducibility problems.

I wanted to prove a different approach: a **self-contained micro-city simulation** where every layer — physics, AI, rendering, controls — is owned by the codebase, deployable on a Raspberry Pi, and traceable end-to-end.

## Approach

I built a stable micro-city MVP around a single resource loop (**Food**), then exposed it through a FastAPI backend and a React dashboard. The user plays as **Mayor**: each simulation tick, a local AI engine recommends a policy action. The Mayor approves or rejects it. Decisions are recorded in a **scorecard** with before/after impact tracking.

The AI engine is a **Q-learning agent** with an epsilon-greedy policy and a deterministic evolution optimizer that validates and overrides recommendations when fitness differs meaningfully. No external APIs, no cloud dependencies — the entire brain runs locally.

The simulation runs for up to 100 days. The city economy models supply and demand, food pricing, population happiness, company behaviour (farms open and close based on profitability), external market shocks, taxation, spoilage, and export limits.

## Technical Decisions

- **FastAPI** owns the simulation service boundary with clean Pydantic models for every state shape. WebSocket streaming for live ticks; REST for controls.
- **React 19 + TypeScript 5.9** on the frontend with Vite 7, Recharts for economy charts, and lucide-react for icons.
- **HTML5 Canvas tile engine** (14×9 grid) for the city map — procedural roads with automatic connection detection, 40+ procedurally rendered building and terrain sprites, deterministic prop placement, and full pan/zoom/click interaction.
- **Q-learning agent** with 8 discrete actions, 7-dimensional state encoding, and a reward function balancing food security, happiness, treasury, and land use. Q-table persisted to disk.
- **Evolution optimizer** that evaluates all legal actions each tick using a fitness function with action-specific bonuses and penalties, overriding the Q-learning recommendation when meaningfully better.
- **Action masking** prevents spam (no consecutive infrastructure builds; subsidize cooldown).
- **Full decision trace** — every tick publishes the input state, reward node deltas, candidate scores, and verdict. The frontend renders structured trace data, not free-text explanation.
- **Backend tests** (pytest) cover the simulation engine, Q-agent, policy engine, city map, API endpoints, and training harness.
- **Docker Compose + Nginx** for production deployment. Cloudflare Tunnel for public access. GitHub Actions CI/CD deploys to a Raspberry Pi self-hosted runner.
- **Offline training harness** runs 320 exploration episodes and fits Q-values across 4 validation scenarios (shortage, oversupply, high price, low land).

## Result

CityBuilder is a working, deployable MVP that demonstrates a complete full-stack systems pipeline:

- A **deterministic simulation engine** with market dynamics, company behaviour, and external shocks
- A **local AI policy agent** that learns from experience without any external API calls
- An **interactive canvas map** that makes the city state visible and clickable
- A **dashboard** with real-time charts, supply/demand visualisation, event logs, and a decision scorecard
- A **training harness** for offline Q-learning validation
- An **A/B experiment framework** for testing UI variants

The project runs entirely on a Raspberry Pi 4 with 4 GB RAM, including the AI agent. The codebase is tested, containerised, and ready for extension with additional resources, zoning mechanics, or multi-agent policy negotiation.

## Links

- [Source Repository](https://github.com/anomalyco/City-Builder)
- [Portfolio Cover Asset](../portfolio-cover.svg)
- [Design Docs](../superpowers/specs/)
