# Selective information before commitment: stage one

User approved the one-rover / uncertain-terrain / costly-probe / delayed-commitment direction, with expansion only after testing. This implements a **route-decision abstraction**, not the continuous rover, a final task choice, or evidence that Claude fails. Existing failure traces motivate the question, but do not establish an information-acquisition deficit. All existing simulator, biome, controller, Harbor, viewer and frozen-result files stay intact.

## Contract

New isolated `lightlag_information` package, Python standard library. Each episode has one fixed hidden terrain state (firm or soft), a known prior, and one binary inspection signal with published accuracy 0.9. The physical inspection uses one consumable and battery; repeatedly reading delivered logs is free. Scripting is allowed. No wall-clock pressure or blanket public-call limit.

One rover chooses one immutable route: shortcut to a target worth 10 points, or detour to a smaller target worth 6. This is a route/target choice, not two routes that inexplicably change the same target's value. A completed trip includes return home. Shortcut costs 4 energy and takes 2 ticks on firm ground, but costs 12 on soft; detour always costs 8 and takes 6 ticks. Initial energy 10; no idle drain. Insufficient energy on departure drains battery to zero, ends the trip unsuccessfully, and scores zero. Surviving completion earns `max(0, target_value - 0.25 * completion_tick) / 10`. No completed route by horizon 30 scores zero. Scores are realized outcomes, never expected values.

Five public methods: `rules()`, `map()`, `telemetry_log()`, `uplink(commands)`, `advance(ticks=1)`. Rules/map publish all parameters, the prior and both possible route costs, never the seed, hidden state or future signal. Public results are copies. Evaluator alone has `evaluate()` and `replay()`, available at horizon. This local callback boundary is not a security sandbox or Harbor integration.

Commands are `{"action":"probe"}`, `{"action":"commit","route":"shortcut"}` (or `detour`), and `{"action":"wait"}`. An uplink has 1–5 commands, validated atomically. First execution is `sent_tick + delay + 1`, one command per tick, FIFO including previous reservations. Delay is 1 tick for this first experiment. Accepted route commitment is immutable immediately, even before execution or later feedback. At most one probe and one commitment may be accepted. A probe must precede commitment in accepted order; a single batch can probe then commit blindly. Invalid calls have no state/resource effects. `advance` accepts integer 1–5, never bool, and clips at horizon.

Probe executes on its reserved tick, spends its context's energy cost, and produces the fixed episode signal. All telemetry, including signal, arrives `state_tick + delay`; tick 0 is a known briefing. A commitment reserves the route but its hidden terrain-dependent expenditure is revealed only when execution telemetry arrives. Completion occurs execution tick + route duration. Both routes use the same completion convention. For the optimal timing: direct commitment starts at tick 2; probing at tick 2 delivers at 3, allowing adaptive commitment at 5. Counterfactual tests keep terrain/signal fixed without exposing those controls through public tools.

## Frozen development contexts

| Context id | P(firm) | Probe energy |
|---|---:|---:|
| uncertain | 0.50 | 1 |
| likely_firm | 0.95 | 1 |
| likely_soft | 0.05 | 1 |
| costly_probe | 0.50 | 3 |

These four hand-designed contexts are mechanism checks, not population benchmarks or hidden holdouts. Terrain and signal use independent deterministic random streams. Evaluation enumerates all four terrain/signal branches per context and weights each by `P(terrain) * P(signal | terrain)`. Equal weighting would be incorrect. Separately retain a fixed seeded smoke matrix (seeds 0–39 in this new independent environment, all four contexts). Never construct the separately reserved continuous-rover seeds 60000–60019.

## Policies and exact reference

`never_probe` chooses the route with highest expected realized reward using the public prior. `always_probe` obtains one signal then selects the best route using the Bayesian posterior and remaining battery. `selective` chooses whichever of these two strategies has greater expected reward (tie: no probe). All consume only public callbacks and share the same clock/resources. The reference enumerates public outcomes, never receives hidden terrain or unrevealed signal. An information-blind `blind_probe` spends the probe but ignores its signal, allowing us to separate benefit of evidence from delay/cost.

This reference is exact for the declared finite action space: only one probe and one trip are possible; delay can only reduce reward, and blind early commitments gain nothing from probing compared with an earlier no-probe commitment. This is not an optimal controller for continuous Lightlag.

## Acceptance and expansion gate

Test arrival timing, immutable commitments, atomic rejection, copies, hidden-state nonleakage, deterministic replay, budgets and realized grading. Cross-check analytical policy values against every realized terrain/signal branch. Selective must strictly beat both always- and never-probe in aggregate across these declared contexts, with at least one context choosing each behavior. Reading a log repeatedly must never mint extra independent evidence.

Retain negative results. If the mechanism gate fails, stop and report it. If it passes, the **next** experiment is a separately frozen, protected Harbor model pilot using clear instructions and scripting. No model difficulty or deployment claim follows from scripted success. No provider calls are part of this first mechanism-validation increment. Continuous-rover integration and wider mechanics follow evidence, not automatic expansion.
