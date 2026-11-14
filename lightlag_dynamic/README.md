# Lightlag dynamic-rules pilot

Adds sample deadlines, targets discovered mid-mission, seeded maps, a time-pressured "rush" profile, noisy sensing with heading drift, and an experimental bumpy-ground option on top of the team's simulator in [`lightlag/`](../lightlag/README.md), without changing it. It also contains a Kalman filter + MPC reference, an MCP entry point for these profiles, and a comparison of the three team references. Owner: Manh / Claude Code (see `TEAM_STATUS.md`). Results and interpretation: [docs/lightlag-dynamic-pilot.md](../docs/lightlag-dynamic-pilot.md).

**No real agent has been run.** Every number this package produces compares scripted controllers.

## Run

From the repository root, Python 3.9+ (checked on 3.9.20, 3.10, 3.12 and 3.14, with identical results), no installation:

```sh
python3 -m unittest discover -s tests/lightlag_dynamic -v                 # 61 tests, under 20 seconds (12 need numpy)
python3 -m lightlag_dynamic.compare --delays 0 3 5 --seeds 400-419        # the three team references side by side; a few minutes
python3 -m lightlag_dynamic.compare --profiles rush_noisy --noise-level 1.5 --bumpiness 0.1
python3 -m lightlag_dynamic.pilot --profiles rush --delays 0 3 5 --seeds 100-139
python3 -m lightlag_dynamic.crosscheck --hard                             # adds lightlag_controllers and tougher physics; several minutes
python3 -m lightlag_dynamic --profile rush --seed 7 --delay 3 < script.jsonl   # one JSON-lines episode, same protocol as `python3 -m lightlag`
python3 -m lightlag_dynamic.serve --profile rush_noisy --seed 7 --delay 3 # one episode over MCP (needs the mcp package, Python 3.10+)
python3 -m lightlag_dynamic.realtime --seconds-per-tick 5 --profile rush_noisy --seed 7 --delay 3   # the same, on a real-time clock
python3 -m lightlag_dynamic.manh_controllers --list                      # Manh's controller collection and swarm runner (needs numpy)
```

`serve` takes the same options and environment variables as `python -m lightlag_mcp` (transport, port, artifact directory, evaluator token, token file), plus `--profile`, `--noise-level` and `--bumpiness`. Over HTTP it answers `/healthz` and is graded by `python -m lightlag_mcp.finish`, so the Harbor task in [`harbor/lightlag/`](../harbor/lightlag/) could serve a dynamic profile by starting `python -m lightlag_dynamic.serve --profile <name>` in its simulator container instead of `python -m lightlag_mcp` (with `lightlag_dynamic/` copied in). That switch is the Harbor task owner's call; nothing under `harbor/` is changed here.

`realtime` is `serve` on a wall clock: one tick every `--seconds-per-tick` seconds (or `LIGHTLAG_SECONDS_PER_TICK`) from the agent's first tool call, whether or not it calls tools, so thinking costs ticks. `advance(n)` waits for n ticks instead of moving the clock and returns every packet received since the previous `advance`; `rules()` reports the clock; the tool descriptions say so. Clock steps appear in `transcript.jsonl` as `"tool": "clock"` records. It is a separate module so `serve.py`, which Sölvi's experiments copy and hash, stays unchanged. [Design and calibration](../docs/lightlag-dynamic-pilot.md#real-time-clock-thinking-costs-ticks).

## Profiles

| Profile | Map | Deadlines | Discoveries | Horizon |
|---|---|---|---|---|
| `static` | simulator's fixed map | no | no | 80 |
| `windows` | simulator's fixed map | north 10, west 16, east 26 | no | 80 |
| `random` | seeded (standard ranges) | no | no | 80 |
| `dynamic` | seeded (standard ranges) | 18–55 | 1–2, windows 10–18 ticks | 80 |
| `rush` | seeded: 5 targets 3–9 m out, smaller sand | 10–32 | 1–2, windows 6–12 ticks | 50 |
| `noisy` | `static` plus noisy sensing and heading drift | no | no | 80 |
| `rush_noisy` | `rush` plus noisy sensing and heading drift | 10–32 | 1–2, windows 6–12 ticks | 50 |

Rules added on top of the simulator, all published in `rules()` and `map()`:
- **Windows:** a target is worth its full value if the sample command executes at or before its `deadline_tick`, and `late_fraction` (0.25) of it afterwards.
- **Discoveries:** a new target appears at its appear tick. The `target_discovered` event travels in that tick's telemetry packet, so a controller learns about it `delay` ticks later, and `map()` lists it from then on. It cannot be sampled before it appears.
- **Seeded maps:** the generator's ranges are published in `rules()["map_generator"]`; the seed picks the instance. For a given seed, `random` and `dynamic` share the same geometry.
- **Noisy sensing and heading drift** (`noisy`, `rush_noisy`), published in `rules()["sensing"]`:
  - every drive travels at the commanded heading plus a hidden bias (uniform ±5° at launch, then a 0.5° random-walk step per drive) plus 1.5° of independent noise; telemetry still reports the commanded heading;
  - every delivered position fix after the tick-0 briefing carries 0.3 m of Gaussian noise per axis, and visual odometry a 5% relative error;
  - sampling, the base return and safety stops use the true position; the replay keeps both the truth and what was reported.
- **Noise level dial:** `noise_level` (default 1) multiplies every sensing value, so difficulty can rise as controllers improve. It is published as `rules()["noise_level"]`.
- **Bumpy ground (experimental, off by default):** `bumpiness` is the share of 1 m cells that are rough; `map()` lists them. Entering a rough cell jolts the rover sideways (0.1 m) and, 40% of the time, spins the wheels in place for 0.3–1.2 wheel metres: energy and wheel odometry count it, the rover does not move. Not part of any profile.

Physics, timing, energy, safety stops, the five public methods and the 1 / 0.5 / 0 return rule are inherited unchanged.

## Files

| File | Contents |
|---|---|
| `missions.py` | Profiles, published generator ranges, `make_mission(profile, seed)` |
| `environment.py` | `DynamicEnvironment(seed, config, profile)`, a subclass of `lightlag.Environment` |
| `tools.py` | `PublicTools` (five methods) and an evaluator-owned `run_episode` |
| `controllers.py` | Scripted controllers using only the public tools: `reference`, `leg_and_wait`, `open_loop`, `stale_telemetry`, `window_blind`, `do_nothing`, and the `kf_mpc` entry |
| `kf_mpc.py` | Kalman filter + receding-horizon controller with chance constraints (details below) |
| `kf_mpc_rt.py` | Optional extra, not adopted: `kf_mpc` for the real-time clock. It measures its own lag and decides that much earlier; identical to `kf_mpc` without lag. [What it is, results, how to adopt or decline](../docs/lightlag-dynamic-pilot.md#real-time-aware-reference-optional-extra-awaiting-team-decision) |
| `compare.py` | Sölvi's, Kristján's and the KF + MPC reference, plus baselines, on the same seeds and profiles |
| `serve.py` | `DynamicEpisodeService` and an MCP entry point: Kristján's `lightlag_mcp` server playing a dynamic profile |
| `realtime.py` | `RealTimeEpisodeService` and its MCP entry point: the same episode on a wall clock, with the tool texts describing it |
| `pilot.py` | Policy × profile × delay × seed matrix and summary table |
| `crosscheck.py` | Runs `lightlag_controllers` beside these controllers, checks `lightlag.evaluation.run_episode` gives identical scores, and optionally applies the team pilot's tougher physics |
| `manh_controllers/` | Every Manh controller combination, named `<METHODS>_manh_controller_<N>` with what, why and when; bounds, rule factors, failure logger and swarm runner. [What each one is and where things stand](manh_controllers/README.md) |
| `__main__.py` | JSON-lines runner reusing `lightlag.__main__.dispatch` |

The original `reference` here treats every position fix as exact; under noise it is the "naive" controller. `kf_mpc` is the reference for the noisy profiles.

## The Kalman filter + MPC reference (`kf_mpc.py`)

- **Estimation:** an extended Kalman filter over position, heading bias and the slip of each terrain. A drive is the prediction step; the position fix and visual odometry are the updates. Visual-odometry readings more than 3 standard deviations off are rejected, so a wheel spin is not learned as slip. A failed sample is also a measurement ("outside the radius"): the estimate truncated to outside the target disc is moment-matched and applied as a pseudo-measurement, so the rover does not keep sampling from a spot it wrongly believes is inside.
- **Delay:** the filter sits at the newest packet; commands already sent are pushed through the model, mean and covariance, to the tick the next command will run.
- **Control:** every decision re-plans which targets to visit, in which order, and the way home, from that predicted state; only the next leg is sent (a receding horizon). Fixed margins are replaced by chance constraints on the predicted covariance: when to sample, when to stop for fixes first, whether to wait and see a sample land (below 97% certainty, when there is time), and how much energy to keep (slip at mean plus a margin of standard deviations). Headings are corrected by the estimated bias.
- **Consistency:** the position estimate's normalized error (NEES) averages 1.8–2.1 at the default noise level, with and without bumps, against 2 for a consistent 2-D filter; about 2.5 at noise level 2 (mildly overconfident).
- **Bumpy ground:** the published rough cells are used to expect the average spin, feed it forward into the commanded distance, and widen the covariance.
- It uses only the five public tools and the published rules, and runs on every profile.
## How it connects

- **Simulator:** `DynamicEnvironment` overrides `_sample` and `_snapshot` and reads a few private fields of `lightlag.Environment`. A test fails loudly if those hooks change.
- **Team evaluator:** `lightlag.evaluation.run_episode(..., environment_factory=crosscheck.dynamic_factory(profile))` runs any profile through the shared runner.
- **Team controllers:** `lightlag_controllers.as_policy(strategy)` and `lightlag.controllers.POLICIES` run unchanged. They read the map once and ignore deadlines, so they never see discoveries, and they treat position fixes as exact.
- **MCP server:** `serve.DynamicEpisodeService` subclasses `lightlag_mcp.service.EpisodeService` and swaps in a `DynamicEnvironment`; `python3 -m lightlag_dynamic.serve` is `python -m lightlag_mcp` with `--profile`. It relies on three private attributes of the service; a constructor hook in `lightlag_mcp` would remove that. The JSON-lines runner speaks the simulator runner's protocol.
