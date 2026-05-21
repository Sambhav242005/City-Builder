# Local Evolution Optimizer Design

## Scope

Remove the external LLM/API inspector path from CityBuilder and replace it with a fully local reinforcement/evolution optimizer that validates the policy recommendation, can override weak choices, and exposes its reasoning as a visual trace in the dashboard.

The user should no longer configure API URL, API key, or model name. The simulator should show what the local decision system is doing: what state went in, which reward nodes changed, which candidate actions were tested, what the optimizer judged right or wrong, and what final action came out.

## Architecture

The existing `rl_policy.py` remains the policy entry point, but its output is expanded with a trace. The policy still evaluates legal city actions against reward signals. A new optimizer layer then runs a short local validation pass over the policy result:

1. Read the current `WorldState`, recent `TickSnapshot` history, and `Params`.
2. Compute normalized feature nodes such as food balance, affordability, happiness, land buffer, infrastructure, oversupply, and scarcity.
3. Score every legal candidate action with projected state, reward signals, prior, and final score.
4. Let the optimizer compare the policy's top action against alternatives using fitness delta, safety flags, and recent-action penalties.
5. Return a final recommendation. If an alternative is meaningfully better, the optimizer marks the original policy choice as wrong/watch and overrides it.

This is local deterministic logic. It does not call chat completions, model APIs, local LLM servers, or any network service.

## Backend Components

`backend/app/agent.py` will be removed from the active flow. The service will stop importing `fetch_agent_inspection`, stop storing agent API config, and stop enforcing external-agent rate limits.

`backend/app/models.py` will replace external-agent models with local optimizer models:

- `OptimizerVerdict`: `right`, `watch`, `wrong`, or `unavailable`.
- `OptimizerInspection`: verdict, reason, risk flags, suggested action, override flag, and fitness delta.
- `PolicyNodeTrace`: node name, previous value when available, current value, delta, status, and short explanation.
- `CandidateActionTrace`: action, legal status, score, projected deltas, reward signals, risk flags, and whether it became the final output.
- `DecisionSystemStatus`: policy version, confidence, value estimate, legal actions, risk flags, reward signals, optimizer inspection, node trace, candidate trace, input summary, and output summary.

`backend/app/rl_policy.py` will own candidate evaluation and trace generation. It will keep the existing reward and risk logic, but return enough structured details for the UI to explain the decision without parsing prose.

`backend/app/service.py` and `backend/app/main.py` will remove `/agent/config`, `/agent/inspection`, and `/agent/recommendation` from the normal workflow. If compatibility endpoints are kept temporarily, they will return the local optimizer snapshot and never accept API credentials.

`backend/app/storage.py` will stop reading and writing API URL, API key, and model-name config. Old `agent_config.json` files may remain on disk, but the app will ignore them.

## UI Design

The dashboard will rename the AI/agent panels to local policy/optimizer language. The UI should not say that an LLM is connected or required.

The right column will show an optimizer trace with four compact sections:

- Input Snapshot: key values used by the policy, including food supply/demand, price, happiness, land use, infrastructure, and recent actions.
- Node Updates: reward/feature nodes with current value, delta, and status color. Nodes that pushed the decision most strongly should be visually prominent.
- Candidate Scores: a ranked list or compact table of legal actions with score, expected deltas, and risk flags.
- Optimizer Verdict and Output: right/watch/wrong result, whether the action was overridden, final action, confidence, fitness delta, and short reason.

The UI should feel like an operational dashboard, not a marketing explanation. It should use dense panels, readable tables, restrained color, Lucide icons, and stable dimensions so score changes do not shift the layout.

## Data Flow

Every `/state`, `/tick`, `/reset`, `/government/approve`, `/government/reject`, and `/build` response includes the local decision trace through `decisionSystem`.

Frontend types mirror the backend models. The frontend renders structured trace fields directly. It does not infer optimizer status from text strings.

The live websocket continues to stream snapshots. Each streamed snapshot includes the latest local optimizer trace.

## Error Handling

If no legal action exists, the app falls back to the existing rule recommendation and marks the optimizer verdict as `unavailable` with a clear reason.

If trace generation fails internally, the service should still return a usable simulation snapshot with the rule fallback. The UI should show an unavailable optimizer state rather than a broken panel.

Old saved API configuration should not break startup. The backend ignores it, and the frontend no longer exposes fields for API URL, API key, or model name.

## Testing

Backend tests will cover:

- No external agent configuration is required for state, tick, live websocket, and optimizer trace.
- Removed or compatibility agent endpoints do not require or expose API credentials.
- The optimizer can override a weak policy choice when a candidate has a stronger fitness score.
- The decision response includes input summary, node trace, candidate trace, optimizer verdict, and final output details.
- Existing city-map, simulation, and mayor-score flows still pass.

Frontend verification will cover:

- Build succeeds.
- The UI no longer shows external agent/API setup language.
- The optimizer trace renders input, node updates, candidate scores, verdict, and output.
- Buttons remain usable without any model configuration.
- Visual browser check confirms the dashboard fits at desktop and mobile widths without overlapping text.
