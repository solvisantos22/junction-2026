# Lightlag Traverse

One long rover mission across Mars-like ground, through the team's five tools. **In progress, a proposal, not a rules decision.** Owner: Kristján / Claude Code (gap research chat). It adds a new world behind the same interface and changes no file of `lightlag/`, `lightlag_dynamic/`, `lightlag_mcp/` or `harbor/lightlag`.

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

## Where it stands (Saturday 14 November, about 18:05 Helsinki)

All numbers are scores from 0 to 1 on one mission. Development worlds are seeds 1 to 24; the task's world is seed 2026.

| Controller | Development worlds | The task's world |
|---|---|---|
| Reference pilot (`pilot.py`) | 0.48 mean over 24, never lost or stranded | 0.45 to 0.48 depending on search budget |
| The pilot without route optimisation | 0.31 mean over 12, stranded on 6 | |
| A straight-line driver that ignores the ground | 0.15 mean over 12, stranded on 8 | |
| Claude Opus 5.5, one request, one program | 0.34 mean over 24; the pilot is higher on 23 | |
| Claude Sonnet 5.5, one request | 0.11 mean over 4 | |
| Claude Haiku 5.5, one request | 0.04 mean over 4 | |
| Claude Opus 5.5 as an agent (OpenCode in Harbor) | its first program replayed: 0.35 mean over 8 | 0.216 and 0.515 |
| Claude Sonnet 5.5 as an agent | | 0.528 |
| Claude Haiku 5.5 as an agent | | 0.000 |

**The reference does not yet beat the best agent runs on the task's world.** Two of four agent runs scored above it there. On the development worlds it is ahead of every Claude program so far, but one Opus agent wrote in four minutes a program that collects nearly as much as the pilot when it gets home. The pilot's route search and its handling of low battery are being improved; this table will change.

## Run

From the repository root. Python 3.9+, standard library only; Harbor and the sandbox need Docker.

```sh
python3 -m unittest discover -s tests/lightlag_traverse -v            # 44 tests
python3 -m lightlag_traverse.terrain 7                                # one world as a character map
python3 -m lightlag_traverse.play --seeds 1-8 --policies pilot,greedy,straight,nothing
harbor run -p harbor/lightlag-traverse -a oracle                      # the reference through Harbor, about a minute
harbor run -p harbor/lightlag-traverse -a opencode -m anthropic/claude-opus-5-5 --ak version=1.19.5 --env-file .env
python3 -m lightlag_traverse.make_task --check                        # are the task's copies fresh?
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
| `server.py` | The MCP server: `lightlag_mcp`'s episode service with this episode and this ground's tool descriptions |
| `make_task.py` | Writes `harbor/lightlag-traverse/` |
| `sandbox.py`, `sandbox_worker.py`, `oneshot.py` | Run model-written controllers in a locked-down container; build the one-request test |

The demo page for this ground is being built in `viewer/traverse/` (`viewer/traverse-demo.html`); what is committed now shows scripted stand-ins, not model runs.
