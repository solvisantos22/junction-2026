# Lightlag pilot: reference controller, baselines and first findings

14 November 2026, 00:35 Helsinki. Owner: Kristján / Claude Code. Code: [`lightlag_controllers/`](../lightlag_controllers/), tests: `tests/lightlag_controllers/`. Runs on Sölvi's simulator in [`lightlag/`](../lightlag/README.md) and changes nothing in it.

**No real agent has been run yet.** Everything below compares scripted controllers. It tells us how the environment behaves, not whether a frontier agent struggles in it.

## The finding that matters most

**Under the current rules the rover does not need telemetry.** A controller that plans once from the map with mid-range slip, sends its commands and never looks at a single packet scores 97–101% of the reference on varied maps, at every delay. The delay cannot hurt a controller that ignores feedback, so an agent with a shell could script the same plan and the gap would close.

Three rule changes together make feedback necessary (the blind plan drops to 68–78% while the reference still gets home every time). They are in [Rule variants](#rule-variants). This needs a decision from whoever owns the simulator rules.

## Overlap with the `lightlag/controllers/` claim

This work was claimed locally at 23:54 on Friday, but the claim could not be pushed until this increment was done. Meanwhile Sölvi's session claimed the same scope at about 00:17 (reference, baselines and an evaluation runner under `lightlag/controllers/` and `lightlag/evaluation.py`). To avoid two references:

- **These controllers already run in that runner.** `lightlag_controllers.as_policy(strategy)` returns a `policy(tools)` callable for `lightlag.evaluation.run_episode`. A test checks all six give the same score there as in this pilot, with no rejected request.
- **Suggested split:** keep `lightlag/evaluation.py` and `PublicTools` as the evaluator boundary, and use the controllers here as the reference and baselines instead of writing a second set. The team should confirm this before either side builds further.

```python
from lightlag import Config
from lightlag.evaluation import run_episode
from lightlag_controllers import REFERENCE, as_policy

report = run_episode(as_policy(REFERENCE), seed=3, config=Config(delay_ticks=3))
```

## Run it

From the repository root, Python 3.9+, no installation:

```sh
python3 -m lightlag_controllers.pilot                          # default map, delays 0 and 3, 10 seeds
python3 -m lightlag_controllers.pilot --maps seeded --seeds 20 --delays 0 3 6
python3 -m unittest discover -s tests/lightlag_controllers -v  # 25 tests, about 15 seconds
```

`--maps seeded` uses 40 × 40 m maps generated per seed in `pilot.py` (three hazards, two sand patches, three targets worth 3, 2 and 1). They are my test maps, not part of the benchmark.

## The controllers

All of them share one planner and use only the five public methods. They differ in one switch each, so a score difference is attributable to one behaviour.

| Controller | What it does |
|---|---|
| `reference` | Predicts the present by replaying commands still in transit on its slip estimate. Learns slip from wheel versus visual odometry. Sends one command per tick. Waits for telemetry only before a sample it is unsure of. |
| `stale_telemetry` | Same, but treats the last packet as the present and forgets commands in transit. |
| `move_and_wait` | Same, but waits to see each command land before sending the next. |
| `open_loop_nominal` | Plans from the briefing with mid-range slip and never reads telemetry. |
| `stop_early` | The reference, but it stops acting after tick 5. |
| `no_op` | Sends nothing. |

The reference also does three things the baselines get for free through the shared planner: it counts value already collected when deciding whether to return, it keeps planned paths half a metre clear of sand edges, and it visits a target on unobserved sand first when that reading decides whether a bigger route fits the battery.

## Results on the current rules

Mean raw score over seeds; "vs ref" is the share of the reference's mean at the same delay.

**Simulator's default map, 10 seeds (maximum 4):**

| Delay | reference | move_and_wait | stale_telemetry | open_loop_nominal | stop_early | no_op |
|---|---|---|---|---|---|---|
| 0 | 3.80 | 3.80 (100%) | 3.80 (100%) | 3.00 (79%) | 0.50 (13%) | 0 |
| 3 | 3.90 | 3.00 (77%) | 0.00 (0%) | 3.00 (77%) | 0.00 (0%) | 0 |
| 6 | 4.00 | 2.00 (50%) | 0.00 (0%) | 3.00 (75%) | 0.00 (0%) | 0 |

**Seeded maps, 20 seeds (maximum 6):**

| Delay | reference | move_and_wait | stale_telemetry | open_loop_nominal | stop_early | no_op |
|---|---|---|---|---|---|---|
| 0 | 5.20 | 5.20 (100%) | 5.20 (100%) | 5.25 (101%) | 1.18 (23%) | 0 |
| 3 | 5.20 | 3.65 (70%) | 0.00 (0%) | 5.08 (98%) | 0.55 (11%) | 0 |
| 6 | 5.15 | 1.93 (37%) | 0.00 (0%) | 5.00 (97%) | 0.53 (10%) | 0 |

The reference ended alive and at base in every one of these episodes.

## What the numbers say

1. **The reference is not hurt by delay.** Its score is flat from delay 0 to 6. Its believed position is 0.07–0.32 m from the truth on average (worst case 0.66 m, below the 0.75 m sampling radius).
2. **Forgetting commands in transit is fatal.** `stale_telemetry` equals the reference at delay 0 and scores zero at any delay above it: it re-sends moves that are already on their way, overshoots by 9–14 m on average and drains the battery. This is the failure the environment was designed around, and it is real and easy to explain from a trace.
3. **Waiting costs clock, not battery.** Idle drain runs to the fixed horizon whatever the rover does, so it is a flat tax of 40 out of 100. `move_and_wait` loses only because 80 ticks hold few round trips: 70% at delay 3, 37% at delay 6. A mission takes about 13 commands, so at delay 3 it nearly fits.
4. **Ignoring telemetry costs almost nothing on varied maps.** See the top of this page. The 0.75 m sampling radius absorbs the position error from guessing slip, and per-drive noise is small.
5. **On the default map there is a real decision.** All three targets fit the battery only on low-slip seeds. Driving to the sand target first reveals the slip and lets the rover drop a target in time. The reference does this and scores 3.8–4.0; controllers that do not settle for 3.0.
6. **Doing nothing scores zero and stopping early scores 0–23%.** Stopping early keeps half the value of whatever was really sampled, by design.

## Rule variants

Seeded maps, 20 seeds. "Blind plan" is `open_loop_nominal` as a share of the reference; lower means feedback matters more.

| Rules | Reference at delay 0 / 3 / 6 | Blind plan at delay 0 / 3 / 6 | move_and_wait at delay 3 / 6 |
|---|---|---|---|
| Current | 5.20 / 5.20 / 5.15 | 101% / 98% / 97% | 70% / 37% |
| Sampling radius 0.4 m | 5.25 / 5.20 / 5.15 | 93% / 92% / 96% | 69% / 34% |
| Slip noise ±0.08 | 5.15 / 5.05 / 5.10 | 89% / 90% / 88% | 69% / 36% |
| Sand slip 0.15–0.60 | 5.10 / 5.10 / 5.10 | 97% / 94% / 96% | 70% / 36% |
| **All three** | 5.00 / 5.00 / 5.05 | **74% / 78% / 68%** | 70% / 34% |
| All three, 40 ticks, battery 80 | 5.00 / 5.00 / 3.00 | 74% / 78% / 114% | 36% / 0% |

- **Recommendation:** adopt the "all three" row, or something stronger in the same direction. It is the only variant here where a blind plan loses clearly while the reference still returns to base in every episode.
- **Do not shorten the horizon to 40 yet.** At delay 6 the reference itself runs out of clock and the blind plan beats it. A shorter horizon is the right lever against `move_and_wait`, but it needs a faster reference first.
- **How the variants were run:** slip noise and slip ranges are module constants in `lightlag/model.py`, not `Config` fields, so `pilot.py` patches them for the duration of a run (`physics_overrides`). `rules()` reports the patched values, so controllers stay honest. Making them `Config` fields would remove the patch.

## Limits

- **No agent runs.** The gap that matters is frontier agent versus reference, and it is unmeasured.
- **The reference is a heuristic, not an optimum.** Its "learn the sand first" rule looks one step ahead. A controller that plans over slip scenarios could score higher, which would only widen any gap.
- **Small samples.** 10 and 20 seeds; differences of a few percent between rows are noise.
- **The blind-plan result depends on the map.** On maps where targets sit deeper in sand it should do worse; that has not been mapped out.
- **Exact visual odometry.** Slip is learned from one or two drives because the simulator reports the distance moved exactly. Noisy odometry would make learning harder for everyone.

## Suggested next steps

1. Decide the rule changes above, then re-run this pilot.
2. Wrap the simulator as an MCP server and run a real agent three times at delays 0 and 3. Compare it with the blind plan as well as the reference: if the agent matches the blind plan, it is not using feedback.
3. Add the believed-versus-true position error to the replay viewer. It is the one-number explanation of every failure here.
