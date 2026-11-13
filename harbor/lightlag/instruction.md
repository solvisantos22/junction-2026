# Lightlag: drive a rover through a signal delay

You are the remote operator of a rover. You reach it only through the `lightlag` MCP server, which offers five tools: `rules`, `map`, `telemetry_log`, `uplink` and `advance`.

## Goal

Sample science targets and bring the rover back to base before the episode ends.

Your score is the total value of the targets sampled, multiplied by:

- 1.0 if the rover ends within `base_radius` of base,
- 0.5 if it ends alive somewhere else,
- 0 if its battery reached zero.

The final score is that number divided by the total value on the map, so it lies between 0 and 1. It is computed from the rover's true state when the episode's fixed number of ticks has passed. Nothing you write or report changes it.

## What makes it hard

- **Commands arrive late.** A command sent at tick `t` executes at tick `t + delay_ticks + 1` at the earliest. Commands execute one per tick, in the order sent.
- **Telemetry is old.** A packet describes the rover at `packet.tick` and reaches you `delay_ticks` later. Commands you have already sent may not show in it yet.
- **Wheel slip is unknown.** Each terrain has a slip value that `rules` gives only as a range. A drive of `M` wheel metres moves the rover `M × (1 − slip)`. Telemetry reports both `wheel_odometry` and `visual_odometry`, so slip can be measured.
- **The battery is finite.** Every tick costs energy whether the rover moves or not, driving costs more on sand, and a sample costs energy even if it fails.

## How to act

- `rules` and `map` tell you everything that is fixed: the delay, the episode length, energy costs, slip ranges, the base, the targets with their values, hazards and sand.
- `uplink` queues 1 to 5 commands: `{"action": "drive", "heading_deg": H, "metres": M}` (0° is east, 90° is north, `M` in (0, 5]), `{"action": "sample"}` or `{"action": "wait"}`.
- `advance` lets 1 to 5 ticks pass and returns the telemetry that arrived. It is the only tool that moves the clock; all the others are free.
- A hazard or the map edge stops the rover where it is and cancels every command queued before that moment.

You may write and run code. The episode ends after `max_ticks` ticks whether or not you are finished; if you stop early, the remaining ticks still pass and the battery keeps draining.
