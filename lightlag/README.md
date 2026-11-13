# Lightlag prototype

Provisional simulator for the team's saved Lightlag draft. No agent/reference gap has been measured. Requires Python 3.9+; no installation or dependencies.

The simulator supplies the tick clock, command scheduling, seeded terrain slip, movement, battery drain, hazard/map-edge safety, sampling, delayed telemetry and evaluator replay. The [handoff](../docs/lightlag-handoff.md) records the current scope and next work.

## Run a complete episode

Run from the repository root. The example drives west, samples one target and returns to base; it is a smoke-test script, not a reference controller.

```sh
lightlag_run_dir="$(mktemp -d)"
python3 -m lightlag --seed 7 --delay 3 --ticks 20 \
  --result "$lightlag_run_dir/result.json" \
  --replay "$lightlag_run_dir/replay.json" \
  < lightlag/examples/return_to_base.jsonl \
  > "$lightlag_run_dir/telemetry.jsonl"
cat "$lightlag_run_dir/result.json"
```

Expected: `raw_score: 1.0`, `sampled_targets: ["west"]`, alive and at base at tick 20. Changing `--delay 3` to `--delay 0` also completes this script. This checks execution; it does not measure a delay-related performance gap.

The replay contains initial and per-tick true states, received telemetry, accepted commands, configuration, world and hidden slip coefficients. `received_tick` on a truth frame is its scheduled delivery tick; frames beyond the horizon are absent from `received_telemetry`. Use those two tracks to show the real rover and the delayed view. Keep replay files outside any future agent container.

Output files must be new and their parent directories must exist. If EOF arrives before the horizon while `--result` or `--replay` is requested, the runner exits with status 2 and writes no final artifacts. Without artifact flags, a short interactive session is allowed. The runner never advances time merely because stdin closes.

## Public protocol

Send one JSON object per line; each nonblank line gets one JSON response. This is a local protocol, not an MCP server.

```json
{"id":"move","method":"uplink","params":{"commands":[{"action":"drive","heading_deg":180,"metres":2}]}}
{"id":"step","method":"advance","params":{"ticks":5}}
```

Success responses contain `id`, `ok: true` and `result`. Invalid requests contain `id`, `ok: false` and `error`; the session remains usable and no action is applied. IDs may be strings, integers or null. Only these methods are dispatchable:

| Method | Parameters | Result |
|---|---|---|
| `rules` | none | Published physics, timing, costs and limits |
| `map` | none | Base, targets, visible terrain and hazards |
| `telemetry_log` | none | All packets received so far |
| `uplink` | `commands`, a list of 1–5 commands | IDs and reserved execution ticks |
| `advance` | optional `ticks`, integer 1–5 (default 1) | Current controller tick, fixed-horizon completion flag and newly arrived packets |

Commands are `{"action":"drive","heading_deg":0,"metres":2}`, `{"action":"sample"}` or `{"action":"wait"}`. Zero degrees points east and 90 points north. Each drive requests at most 5 wheel metres. Extra fields and nonfinite numbers are rejected. An uplink is all-or-nothing and cannot reserve work past the horizon. Scripts may call the same public tools as a model.

Read calls and uplinks cost no time. Only `advance` ticks the clock. A command sent at `t` first executes at `t + delay + 1`; later commands use consecutive slots. A state packet from `s` arrives at `s + delay`. Tick 0 is a known initial briefing. At delay 3, send at 0 → execute at 4 → see the result at 7. Hazard stops clear queued work but keep its reservations, preventing acknowledgements from revealing unseen stops.

## Python integration

Trusted local controllers and test fixtures can use the same API directly:

```python
from lightlag import Config, Environment

env = Environment(seed=7, config=Config(delay_ticks=3))
print(env.rules())
print(env.map())
print(env.telemetry_log())  # Known initial state at tick 0.
print(env.uplink([{"action": "drive", "heading_deg": 0, "metres": 2}]))
print(env.advance(3))       # No new telemetry yet.
print(env.advance(3))       # Receives states 1–3; the command ran at 4.
print(env.advance(1))       # Receives the drive's result, state 4 at tick 7.
```

Use `{"action": "sample"}` to collect the nearest unsampled target within 0.75 m of the true rover position. At the fixed horizon, trusted evaluator code can call `env.evaluate()` for raw score: sampled value × 1 at base, × 0.5 alive elsewhere, or × 0 if the battery is depleted. Doing nothing scores zero. The evaluator method is not an agent tool, and it rejects early scoring.

`env.replay()` is also evaluator-only and requires completion. `evaluate()` reports raw score; a comparison must use a matching positive reference score before computing a reference-normalized ratio.

### Run a policy through public tools

Evaluator code can run a callable without handing it the simulator or hidden seed:

```python
from lightlag.controllers.baselines import do_nothing
from lightlag.evaluation import run_episode

run = run_episode(do_nothing, seed=7, policy_name="do_nothing")
print(run["result"])      # Scored at tick 80, even though this policy returns immediately.
print(run["tool_calls"])  # Policy and evaluator calls are counted separately.
```

A policy receives only `rules`, `map`, `telemetry_log`, `uplink` and `advance` callbacks. Each run starts fresh and returns the final result, existing replay format and a copied public-call transcript. When a policy returns early, the evaluator advances the remaining horizon: queued commands still execute and idle energy still drains. Policy exceptions and invalid actions propagate as execution errors, not benchmark scores. This interface is for auditable trusted controllers; it is not a Python security sandbox.

Trusted evaluator code can construct a different compatible episode with `environment_factory`. The factory receives `seed`, deep-copied `config` and deep-copied `world` keywords; it must return a fresh environment. For example, Manh's dynamic pilot can use the same runner without replacing a module global:

```python
from lightlag import Config
from lightlag.evaluation import run_episode
from lightlag_dynamic.controllers import POLICIES as DYNAMIC_POLICIES
from lightlag_dynamic.environment import DynamicEnvironment

def rush_episode(*, seed, config, world):
    return DynamicEnvironment(seed=seed, config=config, profile="rush")

run = run_episode(DYNAMIC_POLICIES["reference"], seed=3,
                  config=Config(delay_ticks=3, max_ticks=50),
                  environment_factory=rush_episode)
print(run["result"])
```

The factory stays on the evaluator side, and the policy still receives only the five callbacks. Horizon completion follows the constructed episode's public rules; factory errors propagate before policy execution. Omitting the factory preserves the existing default environment. This hook does not change `run_comparison` or the CLI's fixed-map experiment contract, and it does not choose a dynamic profile for the team.

### Conservative reference and diagnostic policies

```python
from lightlag import Config
from lightlag.controllers import POLICIES
from lightlag.evaluation import run_episode

run = run_episode(POLICIES["reference"], seed=7,
                  config=Config(delay_ticks=3), policy_name="reference")
print(run["result"])
```

| Registry name | Behavior |
|---|---|
| `reference` | Learn slip from received homogeneous-terrain drives, predict queued commands, route around hazards and reserve return energy through the full horizon |
| `move_and_wait` | Use similar navigation but wait for each command's telemetry before making the next decision |
| `nominal_open_loop` | Use published midpoint slip and the initial briefing; ignore later packet contents |
| `stale_telemetry` | Treat the last received position as current while retaining energy accounting and valid command scheduling |
| `do_nothing` | Send no commands; the evaluator still completes the horizon |
| `stop_early` | Make the reference's decisions for the first quarter of the horizon, then return control; already queued work still executes |

The reference uses public terrain/hazard geometry, a weighted slip estimate and conservative travel budgeting. It waits for actual sample confirmation before abandoning a target, and can back out of a safety margin after a stop. The planner is greedy and geometrically routes around hazards; it is not an energy-optimal tour solver. On the default development map it chooses the north and west targets and conservatively skips east, so its partial score does not demonstrate a need to learn sand. These policies are diagnostic algorithms; frontier-agent comparison still requires harness integration.

Kristján's independently developed family is in `lightlag_controllers/`. Its `as_policy(strategy)` adapter runs through the same public interface. Further work on the conservative planner above is frozen so the team can concentrate reference improvements in one package. The [pilot](../docs/lightlag-pilot.md) describes the adaptive planner and its separate varied-map experiments.

### Reproducible comparisons and replay exports

The [recorded 480-episode comparison](../docs/lightlag-reference-results.md) includes raw CSVs, the frozen configuration, measured outcomes and limitations for both controller families.

Run a small comparison through the shared evaluator:

```sh
lightlag_batch_parent="$(mktemp -d)"
python3 -m lightlag.evaluation --seeds 0 1 --delays 0 3 \
  --policies team_reference team_open_loop_nominal team_move_and_wait \
  --reference-policy team_reference \
  --output-dir "$lightlag_batch_parent/comparison"
```

The CLI defaults to seeds 0–9, delays 0 and 3, horizon 80 and the six local registry names above. It also accepts `team_reference`, `team_move_and_wait`, `team_stale_telemetry`, `team_open_loop_nominal`, `team_stop_early` and `team_no_op`, which wrap the teammate's strategies. Select the denominator explicitly with `--reference-policy`; its default is the local `reference`. The two stop-early policies differ: local stops after one quarter of the horizon, team after tick 5.

Each comparison starts fresh episodes in policy/delay/seed order. It prints a JSON summary and optionally writes `summary.json`, `scores.csv` and evaluator replays into a **new** output directory whose parent exists. Existing paths are rejected before running policies. Invalid inputs, invalid tool calls and policy exceptions fail visibly. A failed policy batch produces no completed experiment exports.

Summary rows retain raw score, sampled value, survival, base status and tool-call counts. Return rate means **alive and at base**. Ratios divide each run's score by the selected reference on the same seed and delay; a zero or absent denominator yields null with a reason. Aggregate ratios are means of defined per-seed ratios, with defined/undefined counts, and may exceed 1. They differ from the ratio of aggregate mean scores used in the older pilot.

The summary records public rules, world, seed/delay selections, horizon, policies and denominator. Replays retain `lightlag-replay-v1`; keep them outside any agent container. No timestamps or timing measurements enter the scientific output. Matching seeds preserve terrain coefficients and the temporal noise field, but different action timing encounters different noise samples.

Programmatic callers can select any named trusted public-tool policies:

```python
from lightlag.controllers import POLICIES
from lightlag.evaluation import run_comparison

batch = run_comparison({"reference": POLICIES["reference"],
                        "nominal": POLICIES["nominal_open_loop"]},
                       seeds=(0, 1), delays=(0, 3), reference_policy="reference")
print(batch["summary"]["aggregates"])
# batch["episodes"] contains full run_episode results, including replays/transcripts.
```

## Verification and limits

```sh
python3 -m unittest discover -s tests/lightlag -v
python3 -m unittest discover -s tests/lightlag_controllers -v
```

The tests cover timing, independent seeded episodes, energy, invalid requests, copy isolation, safety, true-state scoring, CLI recovery, deterministic replay and public-tool episode execution. Tests use only the standard library.

This core has one fixed flat map, two terrain types, constant per-terrain slip with per-drive noise, and exact visual odometry. Teammates have also published a separate [dynamic-rules pilot](../docs/lightlag-dynamic-pilot.md) and an optional [MCP service](../docs/lightlag-mcp.md), which has its own runtime requirements. Those additions do not change the batch CLI's fixed-map defaults. Slopes, embedding, noisy odometry, further reference optimization, Harbor deployment and real agent evaluation remain follow-up work. The [simulator design](../docs/superpowers/specs/2026-11-13-lightlag-core-design.md) and [reference design](../docs/superpowers/specs/2026-11-14-lightlag-reference-design.md) explain those choices. No project selection or benchmark difficulty claim follows from this implementation.

The in-process API and local runner do not isolate hidden state from an agent that can inspect Python, launch options or files. Benchmark deployment needs a separate simulator container, a serialized adapter and evaluator-only access to score/replay. See the team's [Harbor tool-access research](../afterquery-brainstorm.md#harbor-tool-access) and the [handoff](../docs/lightlag-handoff.md).
