# Lightlag Traverse: a campaign of three sites, one site, and what Claude did on them

14 November 2026. Owner: Kristján / Claude Code (gap research chat). Code: [`lightlag_traverse/`](../lightlag_traverse/README.md). Tasks: [`harbor/lightlag-traverse-campaign/`](../harbor/lightlag-traverse-campaign/) (three sites, version 0.1.0) and [`harbor/lightlag-traverse/`](../harbor/lightlag-traverse/) (one site, version 0.1.2). Demos: [`viewer/traverse-campaign.html`](../viewer/traverse-campaign.html) and [`viewer/traverse-demo.html`](../viewer/traverse-demo.html). Nothing here changes `lightlag/`, `lightlag_dynamic/`, `lightlag_mcp/` or the canonical `harbor/lightlag`.

**Status.** Kristján froze this version on Saturday evening (`TEAM_STATUS.md`): the 0.1.0 rules, the pilot of commit `1545627` as the reference, the campaign as the submission candidate and the one-site task as the fallback. The team's choice of final project is still the team's. This page supersedes [`lightlag-traverse.md`](lightlag-traverse.md), the earlier write-up of the one-site task alone.

Kristján asked for an environment closer to real Mars driving than a 40 m square, harder for Claude, and a much stronger reference to go with it. This page is what was built, what real runs showed, and where it falls short.

## Bottom line

- **On the campaign, the reference scored higher than all seven Claude agent runs, the closest by 0.18.** Reference 0.476, back at the lander at all three sites. Opus 5.5: 0.267, 0.247, 0.244 and 0.120 (mean 0.220). Sonnet 5.5: 0.293 and 0.213. Haiku 5.5: 0.000. On one site the best two runs had come within 0.04 and 0.05.
- **Every Claude run lost ground to the same thing: energy over a whole day.** Three of the six Opus and Sonnet runs ran a battery flat at one site or two (one at tick 97, one 13 m from the lander). The other three brought the rover home every time but collected 28 to 53% fewer samples than the reference, waiting out a low battery, jittering or circling near the lander. Their programs played a site in 8 to 30 seconds of wall time, and three of the agents' own reports say the damage was done before they had looked.

- **On one site, the reference also scored higher than every Claude agent run.** Reference 0.565; seven Opus and Sonnet runs average 0.258 (Sonnet 0.528, 0.147, 0.059; Opus 0.515, 0.341, 0.216, 0.000), Haiku 0.000. But the two best came within 0.04 and 0.05.
- **Those two were lucky, which is why the campaign exists.** Replayed on 300 worlds they had never seen, the best Opus run's program runs its battery flat on 157 of them and the best Sonnet run's on 91. The reference loses no rover on those 300 worlds and scores higher than every saved Claude program on 288 to 300 of them. Grouped three worlds at a time, no saved program beats it on any group.
- **What goes wrong is energy and the end of the day, not driving.** Every Opus and Sonnet agent wrote, within minutes, a program that filters its position, finds ways around craters and searches for a route. Most plan that route on time alone and treat the battery as a guard, or check it once for the whole day. The reference keeps the battery above a reserve at every point of the route and is home with ticks to spare.
- **The tasks grade as intended.** Doing nothing scores 0.000 on both. Stopping early earns little: 0.073 on one site (the reference walking away after a quarter of the day), 0.149 on the campaign (the reference playing the first site perfectly well and stopping). The score is computed in a separate container from the rover's true state.

## The mission

One mission is 420 ticks on a height map of 600 m by 400 m: craters with steep walls and a breached side, a scarp with passes, sand in the flats, rock fields, bedrock. 38 targets are known at launch, 8 more appear on the way, most have deadlines, and nobody can reach them all. Slip grows with the slope being climbed and differs by terrain; ground steeper than `max_tilt` stops the rover and clears its queue; the battery is charged by a sun that climbs and sinks over the mission, through panels of hidden efficiency. The interface is the team's: the five tools `rules`, `map`, `telemetry_log`, `uplink`, `advance`, the same three commands, the same three-tick delay, the same scoring rule. Details: [`lightlag_traverse/README.md`](../lightlag_traverse/README.md).

An agent gets the instruction, the five tools, a Python client, the published ground model as code, and a session limit. The practical way to play is to write a program, so that is what the tasks measure: can the agent write a mission autopilot that works, with no reset and no practice run.

## The campaign: three sites in a row

On one world, a program with a flaw can still be lucky. The campaign plays three worlds in a row under exactly the rules of one mission and scores them together, so a program has to work everywhere, not once.

- Every mission is an unchanged `TraverseEnvironment`. When its last tick passes, it is scored and the next begins at once, at its tick 0, with the rover at that site's lander and a full battery, and new hidden slip, panel efficiency and heading bias. The clock moves only on `advance`, so an agent can look at a finished mission before playing the next.
- `map()`, every packet and every `advance` reply carry `mission`; `advance` says `campaign_complete` after the last.
- The score is the value credited in all three missions over all the value there was in them, so the team's grader reads it unchanged.
- The worlds are seeds 2027, 2028 and 2029. They were written into `TEAM_STATUS.md` and commit `3bff7b2` before any controller or model had played them. The session limit is 45 minutes.

| Who | Site 1 (2027) | Site 2 (2028) | Site 3 (2029) | Campaign |
|---|---|---|---|---|
| **Reference** (`fly_campaign`, Harbor `-a oracle`, 94 s) | 0.459 | 0.508 | 0.460 | **0.476** |
| Sonnet 5.5 · agent 2 | 0.351 | 0.260 | 0.269 | 0.293 |
| Opus 5.5 · agent 1 | 0.265 | 0.274 | 0.263 | 0.267 |
| Opus 5.5 · agent 3 | 0.259 | 0.368 | 0.111 | 0.247 |
| Opus 5.5 · agent 4 | 0.332 | 0.398 | lost | 0.244 |
| Sonnet 5.5 · agent 1 | lost | 0.486 | 0.139, away | 0.213 |
| Opus 5.5 · agent 2 | lost | 0.350 | lost | 0.120 |
| Haiku 5.5 · agent 1 | 0 | 0 | 0 | 0.000 |
| Do nothing (Harbor `-a nop`) | 0 | 0 | 0 | 0.000 |
| The reference, stopped after the first site | 0.459 | 0 | 0 | 0.149 |

Agent runs are OpenCode 1.19.5 in Harbor 0.25.0 on campaign task 0.1.0, run with `--agent-setup-timeout-multiplier 3` because installing OpenCode was slow on the venue network (the agent's own 45 minutes are unchanged). Sessions took 3.3 to 8.5 minutes; reported cost per run $0.02 (Haiku) and $0.51 to $0.88. "Lost": the battery ran out at that site. Folders: `docs/lightlag-runs/campaign-*`.

What the agent runs did, from their trajectories, replays and own reports:

- **Sonnet 2 (0.293), the best Claude run.** Home at every site, but with 18, 12 and 12 samples against the reference's 23, 26 and 19. From about tick 320 at each site the rover circled near the lander while one target flipped between reachable and not; five samples failed at site 2. The agent stopped and restarted its program once, losing about 8 ticks.
- **Opus 1 (0.267).** One program played all three sites, back at the lander every time, but with 15 to 17 samples where the reference took 19 to 26. Its energy estimate was too optimistic: the battery fell to 0.8 at site 1 and 1.1 at site 3, and a low-battery wait cost about 50 ticks. The program played the whole campaign in about 40 seconds of wall time, before the agent had looked at anything.
- **Opus 3 (0.247).** Its first program made the rover jitter, drives of 5 m then 1 to 2 m with the heading swinging, and several samples failed. The agent tried to stop it; the kill commands failed and site 1 ran to the end with the bug. A fixed program played sites 2 and 3, but at site 3 its energy model underestimated the ground and the rover sat at a battery of 3 to 5 for about 40 ticks. Home every time, with 11, 15 and 6 samples.
- **Opus 4 (0.244).** Sites 1 and 2 went well: 22 and 25 samples, home both times. At site 3 its energy forecast, a flat cost per metre plus climbing that also overestimated the morning sun, sent the rover toward sand and rocks; the battery stood at 74 by tick 20 and 33 by tick 60 and ran flat at tick 97, 152 m out with 5 samples. The program played the whole campaign in about 25 seconds.
- **Sonnet 1 (0.213).** Its first program ignored energy, and the battery ran flat at tick 392 of site 1 with 21 samples taken. Between missions the agent rewrote the planner to track the battery. That held: site 2 scored 0.486 against the reference's 0.508. At site 3 the rover met steep ground 30 times on the way home and stood 72 m from the lander for its last 100 ticks: half credit.
- **Opus 2 (0.120).** The route planner counted time only; the one battery guard was a wait below 8. The battery ran flat at site 1 at tick 409, 13 m from the lander with 21 samples taken, and at site 3 at tick 351, 157 m out. The agent started all three missions at once without checking the first; its own report says that testing on mission 1 first would have shown the energy problem.
- **Haiku 1 (0.000).** Read the rules, said it would analyse the map in code, and ended its session without sending a command.

Two agents learned between sites, which the campaign allows: Sonnet 1 rewrote its planner after losing site 1, and Opus 3 fixed its driving. The campaign charges for the first site's lesson, as a real operation would.

**The saved programs on the same three worlds.** Kristján's other session replayed every saved Claude program on 2027, 2028 and 2029 on Modal, as single missions under the same rules, and the pilot beside them. The pilot there repeats its Harbor scores exactly, mission for mission. Rows: [`traverse-farm/campaign-worlds/`](traverse-farm/campaign-worlds/).

| Saved program, replayed | 2027 | 2028 | 2029 | Campaign |
|---|---|---|---|---|
| One-request Opus | 0.375 | 0.417 | 0.292 | 0.362 |
| Opus agent 1's program | 0.280 | 0.216, away | 0.186, away | 0.227 |
| Opus agent 3's program | lost | 0.457 | lost | 0.157 |
| One-request Sonnet | 0.099 | 0.069, away | 0.151 | 0.106 |
| One-request Haiku | 0.030, away | 0.004, away | lost | 0.011 |
| Sonnet agent 1's final program | lost | lost | lost | 0.000 |

Opus agent 3's program, which came within 0.05 of the reference on the one-site task, is within 0.05 of it again on site 2. It loses its rover on the other two sites.

## Results on one site

Seed 2026, fixed before anything had played it. Agent runs are OpenCode 1.19.5 in Harbor 0.25.0 on task 0.1.0. Scores are from 0 to 1; nobody can reach every target, so a good score is well below 1.

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

Every folder is under [`docs/lightlag-runs/`](lightlag-runs/) as `traverse-*`, with the full OpenCode trajectory for agent runs and the evaluator's replay for all of them.

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

A score on one world says little about a program. Kristján's other session built a farm on Modal and played the reference and the saved Claude programs on the same 300 fresh worlds (seeds 600 to 899), paired. The full table, method and caveats are in [`traverse-farm.md`](traverse-farm.md); the summary:

| Policy | Mean | Rovers lost | Ended away | Higher / same / lower than the reference |
|---|---|---|---|---|
| **Reference pilot** | **0.502** | 0 | 0 | |
| One-request Opus | 0.321 | 1 | 0 | 2 / 0 / 298 |
| Opus agent 1's program | 0.309 | 0 | 93 | 0 / 0 / 300 |
| Sonnet agent 1's final program | 0.265 | 91 | 29 | 8 / 4 / 288 |
| Opus agent 3's program | 0.221 | 157 | 0 | 5 / 1 / 294 |
| One-request Sonnet | 0.094 | 0 | 160 | 0 / 0 / 300 |
| One-request Haiku | 0.039 | 44 | 208 | 0 / 0 / 300 |

Grouping those 300 worlds into 100 blocks of three, as the campaign does: each saved program's three-world mean is below the reference's on all 100 blocks (on single worlds the best of them is higher on 4%), and the closest block is 0.022 below it.

Read with care: an agent's program was written during its mission on world 2026 and is replayed here with no agent watching. That measures the program, not the agent, who in a mission could notice trouble and step in. The one-request programs never saw a world, so for them fresh worlds are a fair test.

The same in the sandbox on this laptop, at small scale: Opus agent 3's rebuilt program scores exactly its Harbor score on world 2026 (0.515) and 0.375 on development worlds 1 to 8, where it loses one rover and strands another; the reference is higher on all 8 (0.486). The reference itself: 0.505 on development worlds 1 to 24 and 0.515 on twelve worlds it was never tuned on (1000 to 1011), no rover lost or stranded on any.

## What the reference does

`pilot.py` plays through the five public tools and nothing else; a test wraps the tools and fails if it reaches for anything more. On the campaign, `fly_campaign` gives every site a fresh pilot.

- **Where the rover is.** A three-state filter (position and heading bias) fed by the commands it sent, visual odometry and the noisy fixes. Every decision is made for the state the rover will be in when the command lands, four ticks on.
- **What the ground costs.** Slip per terrain is learned from wheel against visual odometry; panel efficiency is read exactly off the first charge that did not fill the battery. When a slip estimate moves, the cost of the ground is rebuilt.
- **Which way.** A cost-to-go field per goal over the grid, with ground near the tilt limit closed, and any-angle steering along it.
- **Which targets, in what order.** Orienteering with deadlines, discoveries and a battery: the search simulates the battery leg by leg against the sun's curve, waits for the sun where a leg would dip under the reserve, and counts a route only if it ends at the lander in time. A beam search builds routes forward in time, local search improves them, and the plan is repaired, not thrown away, when it stops fitting.
- **The end of the day.** Home four ticks early. On the way home the reserve is there to be spent: the pilot drives down to a lower floor and creeps on what the battery can pay for, because stopping a metre short of the lander costs half the score.

How it got there is worth knowing. The first version's route search settled for days spent among cheap targets near the lander: 0.448 on the one-site task's world, and two agent runs (0.528 and 0.515) beat it. The beam search fixed that: 0.48 to 0.505 on the development worlds, 0.448 to 0.565 on the one-site world. So that world was fixed before anything played it, but the reference was improved after agents had beaten it there. The 300-world comparison, the twelve fresh worlds and the campaign's three worlds were played afterwards, and nothing was tuned on them.

## Reward integrity

- **Do nothing:** 0.000 through Harbor, on both tasks. **Stop early:** on one site, the reference stopped at tick 105 scores 0.073, an eighth of its full run, because the rover is left out in the field. On the campaign, the reference stopped after the first site scores 0.149, under a third of its full run: the sites not played earn nothing.
- **The score comes from the rover's true state**, computed in the simulator's container after the agent's container has stopped (`python -m lightlag_mcp.finish` as Harbor's collect hook), and read by a separate verifier image. Nothing the agent writes or reports enters it. On the campaign, the finish hook runs out every remaining tick of every remaining site first.
- **The agent's image holds no simulator and no seed.** It has the client, the launcher and the ground model, which is the simulator's own `surface.py` byte for byte, published on purpose. The seeds, the hidden slip values, the panel efficiency and the heading bias exist only in the simulator's container. Tests check all of this on both committed tasks; the campaign's agent image is byte for byte the one-site task's.
- **Five tools and nothing else.** `evaluate`, `replay`, `reset`, `finish`, `seed`, `run_out` and `mission_records` are refused; the finish endpoint needs a token that is generated inside the simulator's container. Commands are validated: non-finite numbers, drives over 5 m, unknown fields and batches that would run past the end of a mission are rejected and change nothing.
- **No reset.** One campaign or mission per container; a finished one takes no more commands.
- **Dying is never the best move.** A flat battery scores 0 for that site, ending away from the lander halves it, late samples earn a quarter.
- 75 tests cover the ground model, the environment, the planner, the pilot, the campaign and both tasks (`python3 -m unittest discover -s tests/lightlag_traverse`).

## A harsher day, tested and not adopted

In both tasks the sun is already up when a mission starts (`sun_margin_ticks` 56: a third of its peak at tick 0 and at tick 420). A variant makes the day run from sunrise to sunset (`sun_margin_ticks` 0), so the morning is driven on the battery and the rover must be home before dark. It was tried on world 2026 with a scratch copy of the task (two substitutions: that number and one sentence of the instruction).

| Under the harsher day, world 2026 | Score | What happened |
|---|---|---|
| Reference (in process) | 0.491 | home; never lost or stranded on development worlds 1 to 24 either (0.440 mean) |
| Opus 5.5, run 1 | 0.407 | home, 20 samples, lowest battery 9.6 |
| Opus 5.5, run 2 | 0.425 | home |
| Sonnet 5.5, run 1 | 0.000 | battery flat by the end of the day with 2 samples; its own report: "energy ran out much faster than I planned for" |

The best Opus run is still within 0.07 of the reference, so a darker day does not separate them much; Kristján's other session also found that no option of the pilot gains under it. The campaign does what the harsher day was meant to do. Runs: `docs/lightlag-runs/dawn-agent-*`. On the farm's 300 worlds under that day the first version of the pilot ended away from the lander on two; both were the same end-game flaw (it stopped a metre short of the lander to protect a reserve), fixed in task 0.1.1, after which those two worlds score 0.428 and 0.450 at the lander.

## Limits

- **Seven campaign runs on three worlds.** Four Opus, two Sonnet and one Haiku run, 0.000 to 0.293. The spread is clear; seven runs do not give a rate. The three worlds were fixed once, before anything played them, not searched for.
- **When the reference was built.** It was developed on development worlds 1 to 24 and checked on world 2026, after agents had beaten its first version there. Nothing was tuned on the campaign's worlds.
- **One site alone is a weaker test.** On world 2026 the two best agent runs came within 0.04 and 0.05 of the reference, and scores swing by about that much from world to world. That is why the campaign is the candidate.
- **Replays measure programs.** See the caveat above.
- **Harbor reports an exception on every OpenCode run of these tasks** (`NonZeroAgentExitCodeError`): OpenCode prints `EPIPE: broken pipe` during the session and exits with status 1 at the end. The reward is computed and recorded as usual. The same happens on `harbor/lightlag-live` and not on `harbor/lightlag`; the cause is not established.
- **The venue network.** Installing OpenCode in a trial's container timed out several times on Saturday evening; those trials made no model call and are not counted. Later trials were run with `--agent-setup-timeout-multiplier 3`, which lengthens only the install, not the agent's session.
- **Option tuning is flat.** No single option of the pilot moved its mean by more than about 0.01, under either day. Its strength is in what it models, not in its numbers.

## Task versions

- **One site, 0.1.0**: the version every one-site agent run played.
- **0.1.1**: the reference solution spends its battery reserve on the way home. Only `solution/lightlag_traverse/pilot.py` and the version number differ. Under the task's rules the change does nothing: identical scores on worlds 1 to 24, 1000 to 1011 and 2026, where Harbor's replay of the reference is byte for byte the one from 0.1.0.
- **0.1.2**: the server can also serve a campaign, and the pilot module has `fly_campaign`. One mission is served exactly as before; the instruction, the agent's image and the simulator's behaviour are unchanged since 0.1.0.
- **Campaign, 0.1.0**: the version every campaign run played.

## Spend

Claude API, as reported by Harbor and by the one-request script, not checked against a balance: eight one-site agent runs $3.65, three one-request programs $1.30, three harsher-day agent runs $1.90, seven campaign agent runs $4.15; **$11.00 in all** for Lightlag Traverse. Trials that failed in setup made no model call. Modal compute for the farm is on Kristján's Modal credit and is accounted for in [`traverse-farm.md`](traverse-farm.md).

## Reproduce

From the repository root; Harbor and the sandbox need Docker.

```sh
python3 -m unittest discover -s tests/lightlag_traverse -v              # 75 tests
python3 -m lightlag_traverse.play --seeds 1-24 --policies pilot         # the reference on the development worlds
harbor run -p harbor/lightlag-traverse-campaign -a oracle               # the reference on the campaign: 0.476257
harbor run -p harbor/lightlag-traverse-campaign -a nop                  # do nothing: 0.0
harbor run -p harbor/lightlag-traverse-campaign -a opencode -m anthropic/claude-opus-5-5 --ak version=1.19.5 --env-file .env
harbor run -p harbor/lightlag-traverse -a oracle                        # the reference on one site: 0.564655
python3 viewer/build_traverse.py --campaign                             # the campaign's demo page from the saved runs
python3 viewer/build_traverse.py                                        # the one-site demo page
```
