---
contentKind: case-study
---

## Problem

Simulation projects need clear state updates, predictable rules, and a frontend that makes the system understandable.

## Approach

I built a stable micro-city MVP around a single resource loop, then exposed it through a FastAPI backend and a React dashboard.

## Technical Decisions

- FastAPI owns the simulation service boundary.
- React and TypeScript render the dashboard and controls.
- Backend tests verify simulation behavior.
- Export and deployment folders keep artifacts organized for iteration.

## Result

CityBuilder adds full-stack systems proof: backend state modeling, dashboard UI, testing, and deployment-oriented project structure.
