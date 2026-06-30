---
contentKind: article
slug: "building-a-local-q-learning-agent-for-simulation-ai"
title: "Building a Local Q-Learning Agent for Simulation AI"
type: technical-note
status: published
date: 2026-06-15
summary: "How I built a self-contained Q-learning policy engine for a city simulation — no cloud APIs, no GPUs, just numpy and a Q-table that fits on a Raspberry Pi."
tags:
  - Python
  - Q-Learning
  - Reinforcement Learning
  - Game AI
  - Simulation
---

## Why Local AI?

When I started CityBuilder, the obvious choice for AI-driven policy recommendations was to call an LLM API. But that introduced: latency on every tick, a cloud dependency for what should be a local game, cost for repeated calls, and non-deterministic outputs that make testing impossible.

I wanted the AI to be **deterministic, testable, and zero-cost** at runtime. Q-learning fit perfectly.

## State Encoding

The agent observes the city through 7 discretised dimensions:

| Dimension | Values | What it captures |
|---|---|---|
| Food balance | surplus, stable, shortage | Supply vs demand ratio |
| Price tier | low, normal, high | Food affordability |
| Happiness tier | happy, neutral, unhappy | Population morale |
| Land buffer | plenty, moderate, tight | Available build sites |
| Infrastructure ratio | low, medium, high | City development level |
| Population density | sparse, moderate, dense | Crowding pressure |
| Treasury tier | low, moderate, high | Budget headroom |

Each dimension is bucketed into 2–3 discrete bins, giving 972 possible states — small enough for a dense Q-table, but expressive enough to distinguish meaningful city regimes.

## Action Space

Eight actions spanning three categories:

- **Infrastructure**: `build_farm`, `build_factory`, `build_market`, `build_power_plant`, `build_housing`, `build_road`
- **Policy**: `subsidize` — temporarily boosts food supply at treasury cost
- **Null**: `do_nothing` — always available, lets the simulation run unguided

Actions are masked per tick to prevent repetition (no two infrastructure builds in a row, subsidize has a cooldown). This keeps the simulation dynamic and prevents the agent from spamming the same action.

## Reward Function

The reward is a weighted composite:

```
reward = +w₁ × food_balance + w₂ × affordability
       + w₃ × happiness + w₄ × land_buffer
       - w₅ × oversupply_penalty - w₆ × scarcity_penalty
       - w₇ × population_decline - w₈ × land_full_penalty
       - w₉ × bankruptcy_penalty - w₁₀ × happiness_floor
```

Weights are tuned so that survival (positive food balance, non-negative happiness) dominates short-term optimisation. The agent learns that driving food too high (waste) is almost as bad as driving it too low (starvation), which produces stable policies.

## Evolution Optimizer Override

Pure Q-learning can lock into locally optimal but globally brittle policies. I added a second opinion: an **evolution optimizer** that simulates each candidate action forward using a hand-tuned fitness function.

Every tick, after Q-learning selects the best action, the optimizer evaluates all legal actions independently. If the optimizer finds an action with a fitness score >0.055 higher than the Q-learning pick, it **overrides** the recommendation. This catches edge cases the agent hasn't learned yet.

The override threshold was calibrated by running offline validation across four scenarios: shortage, oversupply, high price, and low land.

## Training Harness

The offline harness runs 320 episodes of random exploration in a `CityTrainingEnv` gym-like wrapper. Each episode starts with a random initial state and runs until terminal or 100 ticks. The Q-table is updated with standard Q-learning:

```
Q(s, a) ← Q(s, a) + α × (r + γ × max Q(s', a') - Q(s, a))
```

After training, the harness validates against four scripted scenarios and produces a JSON report with pass/fail per scenario, Q-margins, and validation margins. This report is what told me the original reward weights over-prioritised food production — I adjusted, re-ran, and the agent stopped over-building farms.

## Key Takeaways

1. **You don't need a GPU or an API key for game AI.** A Q-table with 972 states and 8 actions fits in a few kilobytes and converges in under 500 episodes.
2. **Hybrid architectures work well.** The Q-learner provides fast, learned intuition; the deterministic optimizer provides safety bounds. Together they outperform either alone.
3. **Traceability matters.** Because the agent is simple, every decision can be decomposed into reward node contributions and presented as structured data — not free-text explanations that can't be verified.

## Code

The full implementation is in `backend/app/q_agent.py` and `backend/app/rl_policy.py`. The training harness is `backend/app/training_harness.py`.
