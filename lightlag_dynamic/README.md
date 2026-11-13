# Lightlag dynamic-rules pilot

Adds sample deadlines, targets discovered mid-mission, seeded maps and a time-pressured "rush" profile on top of the team's simulator in [`lightlag/`](../lightlag/README.md), without changing it. Owner: Manh / Claude Code (see `TEAM_STATUS.md`). Results and interpretation: [docs/lightlag-dynamic-pilot.md](../docs/lightlag-dynamic-pilot.md).

**No real agent has been run.** Every number this package produces compares scripted controllers.

## Run

From the repository root, Python 3.9+, no installation:

```sh
python3 -m unittest discover -s tests/lightlag_dynamic -v                 # 12 tests, about 1 second
python3 -m lightlag_dynamic.pilot                                         # all profiles, delays 0 3, seeds 0-19
python3 -m lightlag_dynamic.pilot --profiles rush --delays 0 3 5 --seeds 100-139
python3 -m lightlag_dynamic.crosscheck --hard                             # adds lightlag_controllers and tougher physics; several minutes
python3 -m lightlag_dynamic --profile rush --seed 7 --delay 3 < script.jsonl   # one JSON-lines episode, same protocol as `python3 -m lightlag`
```

## Profiles

| Profile | Map | Deadlines | Discoveries | Horizon |
|---|---|---|---|---|
| `static` | simulator's fixed map | no | no | 80 |
| `windows` | simulator's fixed map | north 10, west 16, east 26 | no | 80 |
| `random` | seeded (standard ranges) | no | no | 80 |
| `dynamic` | seeded (standard ranges) | 18–55 | 1–2, windows 10–18 ticks | 80 |
| `rush` | seeded: 5 targets 3–9 m out, smaller sand | 10–32 | 1–2, windows 6–12 ticks | 50 |

Rules added on top of the simulator, all published in `rules()` and `map()`:
- **Windows:** a target is worth its full value if the sample command executes at or before its `deadline_tick`, and `late_fraction` (0.25) of it afterwards.
- **Discoveries:** a new target appears at its appear tick. The `target_discovered` event travels in that tick's telemetry packet, so a controller learns about it `delay` ticks later, and `map()` lists it from then on. It cannot be sampled before it appears.
- **Seeded maps:** the generator's ranges are published in `rules()["map_generator"]`; the seed picks the instance. For a given seed, `random` and `dynamic` share the same geometry.

Physics, timing, energy, safety stops, the five public methods and the 1 / 0.5 / 0 return rule are inherited unchanged.

## Files

| File | Contents |
|---|---|
| `missions.py` | Profiles, published generator ranges, `make_mission(profile, seed)` |
| `environment.py` | `DynamicEnvironment(seed, config, profile)`, a subclass of `lightlag.Environment` |
| `tools.py` | `PublicTools` (five methods) and an evaluator-owned `run_episode` |
| `controllers.py` | Scripted controllers using only the public tools: `reference`, `leg_and_wait`, `open_loop`, `stale_telemetry`, `window_blind`, `do_nothing` |
| `pilot.py` | Policy × profile × delay × seed matrix and summary table |
| `crosscheck.py` | Runs `lightlag_controllers` beside these controllers, checks `lightlag.evaluation.run_episode` gives identical scores, and optionally applies the team pilot's tougher physics |
| `__main__.py` | JSON-lines runner reusing `lightlag.__main__.dispatch` |

The `reference` here is a stand-in for testing the new rules, not a third team reference. The intent is to port its deadline and discovery handling into the team reference.

## How it connects

- **Simulator:** `DynamicEnvironment` overrides `_sample` and `_snapshot` and reads a few private fields of `lightlag.Environment`. A test fails loudly if those hooks change.
- **Team evaluator:** `lightlag.evaluation.run_episode` constructs `Environment` itself. `crosscheck.team_evaluator_with(profile)` swaps in `DynamicEnvironment` for one block; an environment-factory argument would make this permanent.
- **Team controllers:** `lightlag_controllers.as_policy(strategy)` runs unchanged. Those controllers read the map once and ignore deadlines, so they never see discoveries.
- **MCP server or agent harness:** `DynamicEnvironment` has the same five public methods as `Environment`, so a server can build it in place of `Environment`. The JSON-lines runner speaks the simulator runner's protocol.
