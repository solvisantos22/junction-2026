# Lightlag: first simulator slice

Status: provisional prototype. The user authorized starting development on the saved Lightlag draft; this does not settle the team's project choice. Basis: [Lightlag deep dive](../../../afterquery-brainstorm.md#lightlag-deep-dive) and its bare-simulator pilot. No frontier-agent gap has been measured.

## Scope and decisions

Build the headless simulation first. A controller-first approach would need to invent the simulator contract while implementing it; a UI-first approach would postpone testing the delay hypothesis. A small deterministic core makes both follow-up tasks possible independently.

Use Python 3.9+ and its standard library, consistent with the existing local tooling. This slice needs no model credentials, dependencies, network or wall-clock scheduling. `lightlag/` owns the simulator and a JSON-lines local runner; `tests/lightlag/` owns its tests.

The first map is a fixed 40 × 40 metre arena, with base at its centre, three science targets, visible rectangular hazards and two flat terrain types. Seeded hidden slip varies between bedrock and sand. World and cost parameters can be supplied by evaluator code for small test fixtures. Map generation, slopes, embedding and noisy visual odometry are later experiments; this first slice must not pretend to implement those parts of the brainstorm.

Use constant delay, optional calibration chosen by the controller, and a safety stop. These are reversible prototype choices from the brainstorm. A collision stops at the last safe position and clears all previously queued commands, including ones still in transit. Cleared commands retain their reserved execution slots so that a subsequent uplink acknowledgement cannot reveal an unseen safety stop.

## Tick contract

The controller begins at tick 0 with an initial briefing packet. Read calls and uplinks consume no time. Only `advance(ticks)` moves the clock, in chunks of 1–5 ticks.

A command sent at tick `t` waits `k` complete transitions and can first execute on the transition ending at `t + k + 1`. At most one command executes per tick; later commands reserve consecutive slots. With delay 0 a command sent at 0 executes at 1; with delay 3 it executes at 4. A packet describing state at tick `s` arrives at controller tick `s + k`. This explicit convention avoids an off-by-one ambiguity in “arrives k ticks later.”

Each uplink accepts 1–5 commands atomically: `drive(heading_deg, metres)`, `sample`, or `wait`. Headings are finite degrees; distance is finite and in `(0, 5]`. Unknown fields, booleans masquerading as numbers, invalid commands, and commands scheduled beyond the episode horizon are rejected without changing state. Acknowledgements contain command IDs and scheduled ticks, never rover state.

Every episode lasts the configured horizon (default 80 ticks). Early battery depletion freezes motion and clears commands but does not reveal termination before telemetry arrives. The public `episode_complete` flag changes only at the fixed horizon. At the horizon, packets still in transit remain undelivered; a replay can show them to the evaluator. Calling `advance` beyond the remaining time clips at the horizon.

## Physics, observations and reward

Each seed draws a slip coefficient for bedrock in `[0, 0.05]` and sand in `[0.20, 0.45]`. Per-drive noise in `[-0.02, 0.02]` is keyed by seed and execution tick; clip effective slip to `[0, 0.9]`. Commands are integrated in wheel-distance segments no longer than 0.1 m, using the terrain at each segment's start. Movement is actual distance `wheel distance × (1 - slip)`. Check the full proposed segment against hazards and world bounds, including thin obstacles.

Idle drain is 0.5 per tick, sampling costs 3, and driving costs 1 per wheel metre on bedrock or 2 on sand. Deduct idle energy before a command. A drive stops when its energy runs out; battery never becomes negative. Sampling requires enough energy and a true position within 0.75 m of the nearest unsampled target; each target counts once. Heading zero points east and 90 points north.

Packets contain their state and arrival ticks, position, heading, battery, terrain, wheel/visual odometry for that tick, sampled targets, alive status and events. Exact visual odometry is an intentional first-pilot simplification. `rules()`, `map()` and `telemetry_log()` return independent JSON-compatible copies. Hidden seed, slip, pending telemetry and current truth do not appear in public tool results.

At the fixed horizon, evaluator-owned scoring sums sampled target values and multiplies by 1 at base (within 0.75 m), 0.5 alive elsewhere, or 0 when dead. No-op scores zero. There is no reward for calibration or leftover battery. Publish raw score and maximum available value; reference normalization waits for a verified reference and a nonzero reference score.

## Boundaries and runnable artifact

`model.py` defines immutable world/configuration types and validates commands. `environment.py` implements the five public methods and trusted evaluator methods. `__main__.py` reads one JSON request per line and writes one response per line. Only the five public methods are dispatchable. Evaluator-only score/replay output is written only to explicit CLI output paths after the horizon; replay contains truth and must stay outside an agent's filesystem.

This is a local prototype, not a security boundary. An agent with access to the Python process or its files can inspect hidden state. A separate simulator process/container and a restricted HTTP/MCP adapter are required before adversarial benchmark claims.

## Acceptance and handoff

Tests must establish the exact zero/three-delay timeline, side-effect-free reads and invalid requests, deterministic seeds, idle drain, terminal behavior, true-position sampling, no duplicate rewards, safety-stop queue cancellation, and safe public dispatch. A recorded script must reproduce the same replay and score. The CLI must run from a clean checkout without installation.

Ship three independently checked increments: delay/physics core, mission/safety/scoring, then runner/replay and handoff. Publish each before the next independent increment. Leave the five-method contract for an adapter owner, and the seed/observation contract for an honest reference-controller owner. Their later pilot compares zero versus three delay on shared seeds and includes real coding-agent runs before any difficulty claim.
