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

`env.replay()` is also evaluator-only and requires completion. There is no normalized score yet: a valid, nonzero reference score is required before introducing reference normalization.

## Verification and limits

```sh
python3 -m unittest discover -s tests/lightlag -v
```

The current 34 tests cover timing, independent seeded episodes, energy, invalid requests, copy isolation, safety, true-state scoring, CLI recovery and deterministic replay. Tests use only the standard library.

This pilot has one fixed flat map, two terrain types, constant per-terrain slip with per-drive noise, and exact visual odometry. Slopes, embedding, noisy odometry, map generation, baseline/reference controllers, HTTP/MCP, Harbor deployment and real agent evaluation remain follow-up work. The [design decisions](../docs/superpowers/specs/2026-11-13-lightlag-core-design.md) explain those choices. No project selection or benchmark difficulty claim follows from this implementation.

The in-process API and local runner do not isolate hidden state from an agent that can inspect Python, launch options or files. Benchmark deployment needs a separate simulator container, a serialized adapter and evaluator-only access to score/replay. See the team's [Harbor tool-access research](../afterquery-brainstorm.md#harbor-tool-access) and the [handoff](../docs/lightlag-handoff.md).
