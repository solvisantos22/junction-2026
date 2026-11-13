# Lightlag prototype

Provisional simulator for the team's saved Lightlag draft. No agent/reference gap has been measured. Requires Python 3.9+; no installation or dependencies.

The first increment supplies the tick clock, command scheduling, seeded terrain slip, movement, battery drain, map-edge safety and delayed telemetry. Mission scoring and the local runner are the next increments in the [implementation plan](../docs/superpowers/plans/2026-11-13-lightlag-core.md).

From the repository root:

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

```sh
python3 -m unittest discover -s tests/lightlag -v
```

The [design decisions](../docs/superpowers/specs/2026-11-13-lightlag-core-design.md) define the exact timing and the remaining mission contract. This in-process API does not isolate hidden state from an agent that can inspect Python or its files; benchmark deployment needs a separate simulator container and a restricted adapter.
