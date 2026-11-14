# Lightlag Traverse

One long rover mission across Mars-like ground, through the team's five tools, and a campaign of three such missions at three sites. **In progress, a proposal, not a rules decision.** Owner: Kristján / Claude Code (gap research chat). It adds a new world behind the same interface and changes no file of `lightlag/`, `lightlag_dynamic/`, `lightlag_mcp/` or `harbor/lightlag`.

Kristján asked for an environment that is closer to real Mars driving, harder for Claude, and a much stronger reference to go with it.

## What is different from a `rush` mission

| | `rush` | Traverse |
|---|---|---|
| Map | flat, 40 m by 40 m, sand and hazard rectangles | a height grid 600 m by 400 m: craters with steep walls and a breached side, a scarp with passes, sand in the flats, rock fields, bedrock |
| Slip | one hidden value per terrain | grows with the slope being climbed, differs by terrain; a cross slope makes the rover slide downhill |
| Hazards | rectangles | any ground steeper than `max_tilt` stops the rover and clears its queue |
| Energy | a battery that only drains | drive cost per wheel metre by terrain, plus every metre climbed; charged by a sun that rises and sinks over the mission, through panels of hidden efficiency |
| Mission | 50 ticks, 5 targets, 1 or 2 discoveries | 420 ticks, 38 targets at launch, 8 discoveries, deadlines |
| Tools, commands, delay, scoring | | unchanged: `rules`, `map`, `telemetry_log`, `uplink`, `advance`; value times 1 at the lander, 0.5 alive elsewhere, 0 if the battery ran out, over all the value there was |

Nobody can reach every target, so which ones, in what order and by which way over the ground is the task. Everything needed is published: `rules()` gives every formula and number, `map()` the grid, and the agent's container holds the ground model as code (`/app/lightlag_surface.py`).

## Where it stands (Saturday 14 November, about 20:30 Helsinki)

There are two Harbor tasks. `harbor/lightlag-traverse/` is one mission on one world. `harbor/lightlag-traverse-campaign/` is three missions on three worlds, played one after another under exactly the same rules and scored together ([below](#the-campaign-three-sites-in-a-row)). The campaign exists because one world lets a lucky program through.

All numbers are scores from 0 to 1. Development worlds are seeds 1 to 24; the one-mission task's world is seed 2026, fixed before anything had played it. Agent runs on it played task 0.1.0; the task is now 0.1.2, with the same instruction, agent image and simulator behaviour ([versions](../docs/lightlag-traverse-campaign.md#task-versions)).

**On the task's world, through Harbor:**

| Who | Score | How it ended |
|---|---|---|
| **Reference pilot** (`pilot.py`) | **0.565** | 29 samples, at the lander |
| Sonnet 5.5 agent, run 1 | 0.528 | 26 samples, at the lander. It stopped and restarted its program mid-mission; the final program started from tick 0 runs the battery flat at tick 117 |
| Opus 5.5 agent, run 3 | 0.515 | 24 samples, at the lander, with 0.7 battery units to spare at its lowest |
| Opus 5.5 agent, run 4 | 0.341 | 15 samples, at the lander |
| Opus 5.5 agent, run 1 | 0.216 | 17 samples; parked at the lander, then drove off on the last tick and ended 0.6 m outside its radius: half score |
| Sonnet 5.5 agent, run 2 | 0.147 | 8 samples, at the lander with a full battery |
| Sonnet 5.5 agent, run 3 | 0.059 | 9 samples, 69 m from the lander when time ran out |
| Opus 5.5 agent, run 2 | 0.000 | 17 samples, then the battery ran flat at tick 372, 143 m from the lander |
| Haiku 5.5 agent, run 1 | 0.000 | no samples |
| Do nothing (Harbor `nop`) | 0.000 | |
| Walk away after a quarter of the day | 0.073 | the reference, stopped at tick 105 |

The seven Opus and Sonnet agent runs average **0.258**; the reference is above every one of them. One request for one program, replayed in the sandbox on the same world: Opus 0.237, Haiku 0.091, Sonnet 0.060.

**On other worlds:**

| Controller | Result |
|---|---|
| Reference pilot | 0.505 mean on development worlds 1 to 24, 0.515 on twelve worlds it was never tuned on (1000 to 1011); never lost or stranded on any of them |
| The pilot without route optimisation | 0.31 mean over 12, stranded on 6 |
| A straight-line driver that ignores the ground | 0.15 mean over 12, stranded on 8 |
| Opus agent 3's program (the best Opus run), replayed | 0.375 mean on development worlds 1 to 8: lost on one, stranded on one; the pilot is higher on all 8 |
| Opus's one-request program, replayed | 0.34 mean over 24; the pilot is higher on all 24 |

Kristján's other session measured the same question at scale on Modal: on 300 fresh worlds the pilot is higher than each saved Claude program on 298 to 300 of them (`docs/traverse-farm.md` on `main`). A replay measures the program an agent left behind, not the agent.

**What to take from it.** A good Opus or Sonnet run writes, in a few minutes, a program that plans almost as well as the pilot: the two best runs are within 0.04 to 0.05 of it. What separates the reference is that it does this every time: it keeps the battery above a floor along the whole route, not on average over the day, and it is home with ticks to spare. Three of the seven agent runs lost all or half of their score to one such mistake (a flat battery, a rover parked just outside the lander's radius, a rover still far out when time ran out), and none of the seven used more than a quarter of its 30 minutes.

What it took to get the pilot there: its first route search settled for days spent among cheap targets near the lander, and two agent runs beat it. A beam search that builds routes forward in time, and so finds the far clusters worth a long drive, moved it from 0.48 to 0.505 on the development worlds and from 0.45 to 0.565 on the task's.

## The campaign: three sites in a row

On one world the two best agent runs came within 0.04 and 0.05 of the reference, and then their programs ran the battery flat on 91 and 157 of 300 fresh worlds. Grouping the farm's 300 paired worlds into 100 blocks of three, each saved Claude program beats the reference on none of the blocks, against up to 4% of single worlds. So the campaign plays three worlds in a row and scores them together: a program has to work everywhere, not once.

`campaign.py` changes nothing about a mission. Each one is an unchanged `TraverseEnvironment`. When its last tick passes, it is scored and the next begins at once, at its tick 0, with the rover at that world's lander and a full battery; the clock still moves only on `advance`, so an agent can look at a finished mission before playing the next. `map()`, packets and `advance` replies carry `mission`, and `advance` says `campaign_complete`. The score is all value credited over all value there was, so the team's grader reads it unchanged. The worlds, seeds 2027, 2028 and 2029, were fixed in `TEAM_STATUS.md` and in commit `3bff7b2` before any controller or model had played them. An agent gets 45 minutes.

| Who, on the campaign's worlds | Site 1 (2027) | Site 2 (2028) | Site 3 (2029) | Campaign |
|---|---|---|---|---|
| **Reference pilot**, through Harbor | 0.459 | 0.508 | 0.460 | **0.476** |
| Do nothing, through Harbor | 0 | 0 | 0 | 0.000 |
| The reference, stopped after the first mission, through Harbor | 0.459 | 0 | 0 | 0.149 |
| Opus's one-request program, replayed | 0.375 | 0.417 | 0.292 | 0.362 |
| Opus agent 1's program, replayed | 0.280 | 0.216, away | 0.186, away | 0.227 |
| Opus agent 3's program, replayed | lost | 0.457 | lost | 0.157 |
| Sonnet's one-request program, replayed | 0.099 | 0.069, away | 0.151 | 0.106 |
| Haiku's one-request program, replayed | 0.030, away | 0.004, away | lost | 0.011 |
| Sonnet agent 1's final program, replayed | lost | lost | lost | 0.000 |

The replays are Kristján's other session's, on Modal (`docs/traverse-farm/campaign-worlds/` on `main`); on the same worlds the pilot there repeats its Harbor scores exactly. They measure programs written for one mission on world 2026, played without their agents. Claude agents playing the campaign itself: see [`docs/lightlag-traverse.md`](../docs/lightlag-traverse-campaign.md).

## Run

From the repository root. Python 3.9+, standard library only; Harbor and the sandbox need Docker.

```sh
python3 -m unittest discover -s tests/lightlag_traverse -v            # 75 tests
python3 -m lightlag_traverse.terrain 7                                # one world as a character map
python3 -m lightlag_traverse.play --seeds 1-8 --policies pilot,greedy,straight,nothing
harbor run -p harbor/lightlag-traverse -a oracle                      # the reference through Harbor, about a minute: 0.564655
harbor run -p harbor/lightlag-traverse-campaign -a oracle             # the reference on the campaign, two minutes: 0.476257
harbor run -p harbor/lightlag-traverse-campaign -a opencode -m anthropic/claude-opus-5-5 --ak version=1.19.5 --env-file .env
python3 -m lightlag_traverse.make_task --all --check                  # are both tasks' copies fresh?
```

## Files

| File | Contents |
|---|---|
| `surface.py` | The published ground model: height, slope and terrain class from the grid, and `drive()`, one drive command. The simulator and any controller run the same function |
| `terrain.py` | The seeded world: relief, craters, scarp, terrain classes, and the targets placed where a rover can reach and stand |
| `environment.py` | `TraverseEnvironment`: the five tools, solar charging, sensing noise, discoveries, grading, replay |
| `planning.py` | From public information only: the grid as a graph with cost-to-go fields, and the route search |
| `pilot.py` | The reference: position filter, slip and panel estimates, steering over the cost-to-go field, route planning, all computed for the state the rover will be in when a command lands |
| `play.py` | Play missions in process and compare controllers on the same worlds |
| `server.py` | The MCP server: `lightlag_mcp`'s episode service with this episode and this ground's tool descriptions; with `LIGHTLAG_SEEDS`, a campaign |
| `campaign.py` | Several missions in a row behind the same five tools, graded together, and the episode service around them |
| `make_task.py` | Writes `harbor/lightlag-traverse/` and `harbor/lightlag-traverse-campaign/` |
| `sandbox.py`, `sandbox_worker.py`, `oneshot.py` | Run model-written controllers in a locked-down container; build the one-request test |

The demo page for this ground is `viewer/traverse-demo.html`, one file, built by `viewer/build_traverse.py` from the saved runs under `docs/lightlag-runs/traverse-*`: the reference in gold, every Claude run on the same world beside it. `viewer/traverse-campaign.html` (`--campaign`, from `docs/lightlag-runs/campaign-*`) does the same for the campaign, one site at a time: `?site=2` or the key 2 opens the second.
