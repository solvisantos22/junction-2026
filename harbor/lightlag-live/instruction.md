# Lightlag Live: build an autopilot for a rover you cannot joystick

You are the remote operator of a rover. You reach it only through the `lightlag` MCP server, which offers five tools: `rules`, `map`, `telemetry_log`, `uplink` and `advance`.

The clock is real. Once you start, one tick passes every second, the rover is given 6 missions in a row, and nothing waits for you. A mission of 50 ticks is over in 50 seconds, so calling the tools by hand cannot keep up. Your job is to write a program that drives the rover, start it, and let it run.

## Goal

In each mission, sample science targets and have the rover back at base when the mission ends.

A mission's score is the value earned from the targets it sampled, multiplied by:

- 1.0 if the rover ends within `base_radius` of base,
- 0.5 if it ends alive somewhere else,
- 0 if its battery reached zero,

and divided by the total value generated for that mission, including targets that only appear later. A target sampled at or before its `deadline_tick` earns its full `value`; after that it earns `late_value`. What counts is the tick at which the sample command executes.

Your score is the mean over all 6 missions, so it lies between 0 and 1. It is computed from the rover's true state. Nothing you write or report changes it. A mission you do not play scores 0.

## The clock

- Nothing moves until your first `uplink` or `advance`. Until then `rules`, `map` and `telemetry_log` are free: read the first mission and prepare for as long as you like.
- From then on one tick passes every second of real time, whether or not you call a tool.
- Each mission lasts `max_ticks` ticks. The next one starts the moment it ends, on a new map, with a recharged rover at base. `rules`, `map` and `telemetry_log` then describe the new mission. You cannot see a map before its mission starts.
- `advance(n)` waits until `n` more ticks have passed, never past the end of the mission. It returns `current_tick`, `episode_complete` (this mission has ended), `campaign_complete`, `mission` and every telemetry packet that arrived since your previous `advance`.
- The whole campaign takes 5 minutes once started. Your session is limited to 30 minutes in total, preparation included, so start the campaign while at least 5 minutes remain.

## What makes it hard

- **Commands arrive late.** A command sent at tick `t` executes at tick `t + delay_ticks + 1` at the earliest. Commands execute one per tick, in the order sent.
- **Telemetry is old.** A packet describes the rover at `packet.tick` and reaches you `delay_ticks` later. Commands you have already sent may not show in it yet.
- **Wheel slip is unknown.** Each terrain has a slip value that `rules` gives only as a range. A drive of `M` wheel metres moves the rover `M x (1 - slip)`. Telemetry reports `wheel_odometry` and `visual_odometry`.
- **Sensing is noisy and the rover drifts.** `rules()["sensing"]` gives the numbers. Every reported position after the tick-0 briefing carries noise, reported visual odometry carries noise, and each drive goes off the commanded heading by a hidden, slowly changing bias. Sampling, returning to base and safety stops are decided by the rover's true position.
- **Targets have deadlines and new ones appear.** A `target_discovered` event travels in delayed telemetry; `map` lists the target once that packet has arrived.
- **The battery is finite.** Every tick costs energy until the mission ends, whether the rover moves or not; driving costs more on sand; a sample costs energy even if it fails.
- **A hazard or the map edge stops the rover** where it is and cancels every command queued at that moment.

## How to act

- `rules` and `map` tell you everything that is fixed for the mission in progress. `uplink` queues 1 to 5 commands: `{"action": "drive", "heading_deg": H, "metres": M}` (0 degrees is east, 90 is north, `M` in (0, 5]), `{"action": "sample"}` or `{"action": "wait"}`.
- A Python helper is waiting in `/app/lightlag_client.py`. It gives a program the same five tools as plain function calls:

  ```python
  from lightlag_client import connect

  with connect("http://lightlag:8000/mcp") as tools:
      rules = tools.rules()            # free
      world = tools.map()              # free
      packets = tools.telemetry_log()  # free
      # The next two start the clock the first time either of them is called:
      # acks = tools.uplink([{"action": "drive", "heading_deg": 90, "metres": 2.5}])
      # out = tools.advance(1)
  ```

  A rejected request raises `ValueError` with the reason and changes nothing.
- Start your program in the background and watch its output, for example `nohup python3 autopilot.py > autopilot.log 2>&1 &`. A command left in the foreground may be cut off by your shell tool's time limit while the campaign is still running.
- You may also call the tools yourself at any time, and you may change or restart your program while the campaign runs. The clock does not wait for either.

You may write and run any code. If you stop early, the mission in progress still runs to its end with the battery draining, and the missions after it score 0.
