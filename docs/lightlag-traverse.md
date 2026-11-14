# Lightlag Traverse: a long mission on Mars-like ground, and what Claude did on it

14 November 2026. Owner: Kristján / Claude Code (gap research chat). Code: [`lightlag_traverse/`](../lightlag_traverse/README.md), task: [`harbor/lightlag-traverse/`](../harbor/lightlag-traverse/) (version 0.1.1), demo: [`viewer/traverse-demo.html`](../viewer/traverse-demo.html). **A proposal for the team, not a rules decision.** Nothing here changes `lightlag/`, `lightlag_dynamic/`, `lightlag_mcp/` or the canonical `harbor/lightlag`.

Kristján asked for an environment closer to real Mars driving than a 40 m square, harder for Claude, and a much stronger reference to go with it. This page is what was built, what real runs showed, and where it falls short.

## Bottom line

- **On the task, the reference scored higher than all eight Claude agent runs.** Reference 0.565. Seven Opus and Sonnet runs average 0.258: Sonnet 0.528, 0.147, 0.059 and Opus 0.515, 0.341, 0.216, 0.000. Haiku 0.000.
- **The two runs that came close were lucky.** Their programs were replayed on 300 worlds they had never seen: the best Opus run's program runs its battery flat on 157 of them, the best Sonnet run's on 91. The reference loses no rover on those 300 worlds and scores higher than every saved Claude program on 288 to 300 of them.
- **What goes wrong is energy and the end of the day, not driving.** Every Opus and Sonnet agent wrote, within minutes, a program that filters its position, finds ways around craters and searches for a route. Most of them plan that route on time alone and treat the battery as a guard, or check it once for the whole day. The reference keeps the battery above a reserve at every point of the route and is home with ticks to spare.
- **The task grades as intended.** Doing nothing scores 0.000. Walking away after a quarter of the day scores 0.073. The score is computed in a separate container from the rover's true state.
- **Where it falls short.** On the task's one world the margin over the two best runs is 0.04 to 0.05, so a lucky agent run could land above the reference there. The reference is far ahead on average and on fresh worlds, not on every single run.

## The mission

One mission of 420 ticks on a height map of 600 m by 400 m: craters with steep walls and a breached side, a scarp with passes, sand in the flats, rock fields, bedrock. 38 targets are known at launch, 8 more appear on the way, most have deadlines, and nobody can reach them all. Slip grows with the slope being climbed and differs by terrain; ground steeper than `max_tilt` stops the rover and clears its queue; the battery is charged by a sun that climbs and sinks over the mission, through panels of hidden efficiency. The interface is the team's: the five tools `rules`, `map`, `telemetry_log`, `uplink`, `advance`, the same three commands, the same three-tick delay, the same scoring rule. Details: [`lightlag_traverse/README.md`](../lightlag_traverse/README.md).

An agent gets the instruction, the five tools, a Python client, the published ground model as code and 30 minutes. The practical way to play is to write a program, so that is what the task measures: can the agent write a mission autopilot that works the first time, with no reset and no practice run.

## Results on the task's world

Seed 2026, fixed before anything had played it. Agent runs are OpenCode 1.19.5 in Harbor 0.25.0. Scores are from 0 to 1; nobody can reach every target, so a good score is well below 1.

| Run | Score | Samples | Ended | Lowest battery | Session | Cost |
|---|---|---|---|---|---|---|
| **Reference** (`pilot.py`, Harbor `-a oracle`) | **0.565** | 29 | at the lander | 7.4 | 50 s | none |
| Sonnet 5.5 · agent 1 | 0.528 | 26 | at the lander | 11.1 | 7.2 min | $0.37 |
| Opus 5.5 · agent 3 | 0.515 | 24 | at the lander | 0.7 | 3.6 min | $0.74 |
| Opus 5.5 · agent 4 | 0.341 | 15 | at the lander | 4.3 | 5.6 min | $0.60 |
| Opus 5.5 · agent 1 | 0.216 | 17 | 4.6 m from the lander, radius 4 m | 6.8 | 4.2 min | $0.58 |
| Sonnet 5.5 · agent 2 | 0.147 | 8 | at the lander | 77.7 | 4.2 min | $0.31 |
| Sonnet 5.5 · agent 3 | 0.059 | 9 | 69 m from the lander | 82.8 | 3.6 min | $0.37 |
| Opus 5.5 · agent 2 | 0.000 | 17 | battery flat at tick 372, 143 m out | 0.0 | 3.7 min | $0.66 |
| Haiku 5.5 · agent 1 | 0.000 | 0 | 4.5 m from the lander | 98.0 | 3.2 min | $0.02 |
| Do nothing (Harbor `-a nop`) | 0.000 | 0 | at the lander | | | |
| Walk away at tick 105 (the reference, stopped) | 0.073 | | away from the lander | | | |

One request for one program, played in the sandbox on the same world: Opus 0.237, Haiku 0.091, Sonnet 0.060 (generation $1.04, $0.02, $0.23).

Every folder is under [`docs/lightlag-runs/`](lightlag-runs/) as `traverse-*`, with the full OpenCode trajectory for agent runs and the evaluator's replay for all of them. The agent runs played task 0.1.0; version 0.1.1 differs only in the reference solution ([below](#task-versions)).

What the agent runs did, from their trajectories and replays:

- **Sonnet 1 (0.528).** Wrote a 305-line autopilot with a beam search over routes. It stopped the program mid-mission, patched it and restarted it with a resume switch. Its route search checks the energy balance once, at the end of a route, and credits the whole day's sun up front. Started from tick 0 on the same world, the final program drives out in the weak morning sun and runs the battery flat at tick 117. In the run itself the restart and nine ticks of waiting carried it past that point.
- **Opus 3 (0.515).** Position filter with heading bias, shortest ways over the grid with steep cells blocked, annealing over routes with deadlines, replanning every 30 ticks. The battery appears only as a guard: wait when it is under 6 and the sun is low. It came through with 0.7 units at its lowest.
- **Opus 4 (0.341).** A similar program with a battery forecast that assumed better panels than the worst case; the battery fell to 4.3. Two samples failed because the rover was not within reach when they executed.
- **Opus 1 (0.216).** 17 samples and back at the lander with ticks to spare. Then a command still in the queue drove it 5 m away on the last tick. The agent's last look at telemetry was from tick 417, and its report says the rover ended inside the radius. Half score.
- **Sonnet 2 (0.147).** Planned with margins so wide that around tick 280 nothing looked reachable, and the rover drove without a goal for about 30 ticks. Eight samples, home with a full battery.
- **Sonnet 3 (0.059).** The program kept correcting its position by small drives before each sample and took about 40 ticks per target. The agent reasoned about a fix while the program played on; the mission ended first, 69 m from the lander.
- **Opus 2 (0.000).** Planned on time only. Its battery guard applied while a target was the goal, not on the way home. Battery flat at tick 372 with 17 samples taken, 143 m from the lander.
- **Haiku 1 (0.000).** Read the rules and the map, sent one probe drive and ended its session.

None of the seven Opus and Sonnet runs used more than a quarter of its 30 minutes, so each had time to test its program against the published rules before starting the one mission it gets. Sonnet 1 did: it wrote its own simulator from the rules and played a whole day in it. That simulator has no rule for a flat battery, so it could not show the fault that kills the same program when it starts from tick 0. The others tried their planner at most, and none simulated the mission.

## The same programs on other worlds

A score on one world says little about a program. Kristján's other session built a farm on Modal and played the reference and seven saved Claude programs on the same 300 fresh worlds (seeds 600 to 899), paired. The full table, method and caveats are in [`traverse-farm.md`](traverse-farm.md); the summary:

| Policy | Mean | Rovers lost | Ended away | Higher / same / lower than the reference |
|---|---|---|---|---|
| **Reference pilot** | **0.502** | 0 | 0 | |
| One-request Opus | 0.321 | 1 | 0 | 2 / 0 / 298 |
| Opus agent 1's program | 0.309 | 0 | 93 | 0 / 0 / 300 |
| Sonnet agent 1's final program | 0.265 | 91 | 29 | 8 / 4 / 288 |
| Opus agent 3's program | 0.221 | 157 | 0 | 5 / 1 / 294 |
| One-request Sonnet | 0.094 | 0 | 160 | 0 / 0 / 300 |
| One-request Haiku | 0.039 | 44 | 208 | 0 / 0 / 300 |

Read with care: an agent's program was written during its mission on world 2026 and is replayed here with no agent watching. That measures the program, not the agent, who in a mission could notice trouble and step in. The one-request programs never saw a world, so for them fresh worlds are a fair test.

The same in the sandbox on this laptop, at small scale: Opus agent 3's rebuilt program scores exactly its Harbor score on world 2026 (0.515) and 0.375 on development worlds 1 to 8, where it loses one rover and strands another; the reference is higher on all 8 (0.486). The reference itself: 0.505 on development worlds 1 to 24 and 0.515 on twelve worlds it was never tuned on (1000 to 1011), no rover lost or stranded on any.

## What the reference does

`pilot.py` plays through the five public tools and nothing else; a test wraps the tools and fails if it reaches for anything more.

- **Where the rover is.** A three-state filter (position and heading bias) fed by the commands it sent, visual odometry and the noisy fixes. Every decision is made for the state the rover will be in when the command lands, four ticks on.
- **What the ground costs.** Slip per terrain is learned from wheel against visual odometry; panel efficiency is read exactly off the first charge that did not fill the battery. When a slip estimate moves, the cost of the ground is rebuilt.
- **Which way.** A cost-to-go field per goal over the grid, with ground near the tilt limit closed, and any-angle steering along it.
- **Which targets, in what order.** Orienteering with deadlines, discoveries and a battery: the search simulates the battery leg by leg against the sun's curve, waits for the sun where a leg would dip under the reserve, and counts a route only if it ends at the lander in time. A beam search builds routes forward in time, local search improves them, and the plan is repaired, not thrown away, when it stops fitting.
- **The end of the day.** Home four ticks early. On the way home the reserve is there to be spent: the pilot drives down to a lower floor and creeps on what the battery can pay for, because stopping a metre short of the lander costs half the score.

How it got there is worth knowing. The first version's route search settled for days spent among cheap targets near the lander: 0.448 on the task's world, and two agent runs (0.528 and 0.515) beat it. The beam search fixed that: 0.48 to 0.505 on the development worlds, 0.448 to 0.565 on the task's. So the task's world was fixed before anything played it, but the reference was improved after agents had beaten it there. The 300-world comparison and the twelve fresh worlds were played afterwards and nothing was tuned on them.

## Reward integrity

- **Do nothing:** 0.000 through Harbor. **Stop early:** the reference stopped at tick 105 scores 0.073, an eighth of the full run, because the rover is left out in the field.
- **The score comes from the rover's true state**, computed in the simulator's container after the agent's container has stopped (`python -m lightlag_mcp.finish` as Harbor's collect hook), and read by a separate verifier image. Nothing the agent writes or reports enters it.
- **The agent's image holds no simulator and no seed.** It has the client, the launcher and the ground model, which is the simulator's own `surface.py` byte for byte, published on purpose. The seed, the hidden slip values, the panel efficiency and the heading bias exist only in the simulator's container. A test checks all of this on the committed task.
- **Five tools and nothing else.** `evaluate`, `replay`, `reset`, `finish` and `seed` are refused; the finish endpoint needs a token that is generated inside the simulator's container. Commands are validated: non-finite numbers, drives over 5 m, unknown fields and batches that would run past the last tick are rejected and change nothing.
- **No reset.** One mission per container; a finished mission takes no more calls.
- **Dying is never the best move.** A flat battery scores 0, ending away from the lander halves the score, late samples earn a quarter.
- 62 tests cover the ground model, the environment, the planner, the pilot and the task (`python3 -m unittest discover -s tests/lightlag_traverse`).

## A harsher day, tested and not adopted

In the task the sun is already up when the mission starts (`sun_margin_ticks` 56: a third of its peak at tick 0 and at tick 420). A variant makes the day run from sunrise to sunset (`sun_margin_ticks` 0), so the morning is driven on the battery and the rover must be home before dark.

- **The reference handles it.** 0.440 on development worlds 1 to 24 and 0.491 on world 2026, no rover lost or stranded. On the farm's 300 worlds the first version scored 0.435, lost no rover and ended away from the lander on two; both were the same end-game flaw (it stopped a metre short of the lander to protect a reserve), fixed in 0.1.1, after which those two worlds score 0.428 and 0.450 at the lander.
- **Agents under it:** see the table below. The saved programs cannot be used here: they hardcode the task's sun.

| Agent run under the harsher day | Score | What happened |
|---|---|---|
| Sonnet 5.5, run 1 | 0.000 | battery flat by the end of the day with 2 samples; its own report: "energy ran out much faster than I planned for" |

Two Opus runs and one more Sonnet run were still playing when this was written; six earlier attempts ended in setup when the venue network dropped, with no model call. These runs used a scratch copy of the task (two substitutions: `sun_margin_ticks` 0 and one sentence of the instruction) and are not yet saved under `docs/lightlag-runs/`.

It is not the task's rule because the task as it stands already separates the reference from the agents, all the evidence above was gathered under it, and a rule change this late would need every run repeated.

## Limits

- **One world.** The task plays one mission on one world. On that world the two best agent runs are within 0.04 to 0.05 of the reference, and scores swing by about that much from world to world. The claim that holds is the average and the fresh-world record, not a win in every single run.
- **Seven runs.** Four Opus and three Sonnet runs, 0.000 to 0.528. That is enough to see the spread, not to state a rate.
- **Replays measure programs.** See the caveat above.
- **Harbor reports an exception on every OpenCode run of this task** (`NonZeroAgentExitCodeError`): OpenCode prints `EPIPE: broken pipe` during the session and exits with status 1 at the end. The reward is computed and recorded as usual. The same happens on `harbor/lightlag-live` and not on `harbor/lightlag`; the cause is not established.
- **Option tuning is flat.** No single option of the pilot moved its mean by more than about 0.01, under either day. Its strength is in what it models, not in its numbers.

## Task versions

- **0.1.0**: the version every agent run above played.
- **0.1.1**: the reference solution spends its battery reserve on the way home. Only `solution/lightlag_traverse/pilot.py` and the version number differ; the instruction, the agent's image and the simulator are byte for byte the same. Under the task's rules the change does nothing: identical scores on worlds 1 to 24, 1000 to 1011 and 2026, where Harbor's replay of the reference is byte for byte the one from 0.1.0.

## Spend

Claude API, as reported by Harbor and by the one-request script: eight agent runs $3.65, three one-request programs $1.30, the harsher-day runs not yet tallied (one finished, three in progress). Trials that failed in setup made no model call. Modal compute for the farm is on Kristján's Modal credit and is accounted for in [`traverse-farm.md`](traverse-farm.md).

## Reproduce

From the repository root; Harbor and the sandbox need Docker.

```sh
python3 -m unittest discover -s tests/lightlag_traverse -v             # 62 tests
python3 -m lightlag_traverse.play --seeds 1-24 --policies pilot        # the reference on the development worlds
harbor run -p harbor/lightlag-traverse -a oracle                       # the reference through Harbor: 0.564655
harbor run -p harbor/lightlag-traverse -a nop                          # do nothing: 0.0
harbor run -p harbor/lightlag-traverse -a opencode -m anthropic/claude-opus-5-5 --ak version=1.19.5 --env-file .env
python3 viewer/build_traverse.py                                       # the demo page from the saved runs
```
