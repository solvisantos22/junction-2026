You are preparing the autopilot for a rover that is operated through a signal delay. Write one Python module that plays a whole mission on its own.

## The mission

- The rover starts at base on a 40 m x 40 m map. Science targets are scattered around it. Sample as many as you can and have the rover back at base when the mission ends.
- A mission lasts exactly `max_ticks` ticks (50). It is scored from the rover's true state at the end:
  score = (value earned from sampled targets) x multiplier / (total value of every target generated for the mission, including targets that only appear later).
  The multiplier is 1.0 if the rover ends within `base_radius` of base, 0.5 if it ends alive anywhere else, and 0 if its battery reached zero.
- A target sampled at or before its `deadline_tick` earns its full `value`; after that it earns `late_value`. What counts is the tick at which the sample command executes.
- New targets appear during the mission. A `target_discovered` event travels in the telemetry packet of the tick it appears, so you learn of it `delay_ticks` later; from then on `map()` lists it. It cannot be sampled before its `appear_tick`.
- The battery drains `idle_cost` every tick until the mission ends, whether or not the rover moves and whether or not your program is still running. Driving costs `drive_cost` per wheel metre, times the terrain multiplier. A sample costs `sample_cost` even when it fails.

## Why this has to be a program

The mission runs in real time, one tick per second, with nobody at the controls: once it starts, your program is the only thing driving. It will be run on missions you have not seen (other maps, other hidden wheel slip, other heading bias), several in a row, and it has to work the first time. There is no practice run and no chance to fix it afterwards.

## What makes it hard

- Commands arrive late. A command sent at tick `t` executes at tick `t + delay_ticks + 1` at the earliest. Commands execute one per tick, in the order sent.
- Telemetry is old. A packet describes the rover at `packet["tick"]` and reaches you `delay_ticks` later. Commands you have already sent may not show in it yet.
- Wheel slip is unknown. A drive of `M` wheel metres moves the rover `M x (1 - slip)` over the ground. `rules()` gives only a range per terrain; each drive also has a little noise. Telemetry reports `wheel_odometry` and `visual_odometry` for each tick, so slip can be estimated.
- In some missions sensing is noisy and the rover drifts: `rules()["sensing"]` is then not null. Reported positions carry noise, reported visual odometry carries noise, and each drive goes a little off the commanded heading by a hidden, slowly changing bias. In other missions `rules()["sensing"]` is null and positions are exact. Your program must handle both.
- Sampling, returning to base and safety stops are all decided by the rover's true position, not the reported one.
- A drive that would enter a hazard rectangle or leave the map stops the rover at the last safe position and cancels every command queued at that moment (their execution ticks stay reserved, so new commands queue behind them).

## Interface

Your module must define `play(tools)`. `tools` has exactly these five methods. All values are plain JSON-style Python objects.

- `tools.rules()` -> dict. The published rules. Costs no time.
- `tools.map()` -> dict. Map size, base, sand rectangles, hazard rectangles and the targets known so far. Costs no time.
- `tools.telemetry_log()` -> list of every packet received so far, oldest first. Costs no time.
- `tools.uplink(commands)` -> list of acknowledgements. `commands` is a list of 1 to 5 commands:
  `{"action": "drive", "heading_deg": H, "metres": M}` (0 degrees is east, 90 is north; `M` is wheel metres, 0 < M <= 5),
  `{"action": "sample"}` (collects the nearest unsampled target within `target_radius` of the rover's true position), or `{"action": "wait"}`.
  The first command executes at `current_tick + delay_ticks + 1`, or one tick after the last command already queued, whichever is later; the rest follow one per tick. A request with any invalid command, or one whose commands would execute after the last tick of the mission, raises `ValueError` and changes nothing. Costs no time.
- `tools.advance(ticks=1)` -> dict. Lets 1 to 5 ticks pass and returns `current_tick`, `episode_complete` and the telemetry packets that arrived in those ticks. It is the only call that moves time forward.

`play` should return once `episode_complete` is true (or earlier if there is nothing left to do; the remaining ticks then pass by themselves). If `play` raises, your control ends there: commands already accepted still execute and the rest of the mission passes with the rover as it is.

### Real outputs from one example mission

`tools.map()` at the start:

```json
{"width": 40.0, "height": 40.0, "base": [20.0, 20.0], "default_terrain": "bedrock", "sand": [{"x1": 26.16, "y1": 32.57, "x2": 34.44, "y2": 38.86}, {"x1": 16.55, "y1": 25.43, "x2": 27.87, "y2": 35.96}], "hazards": [{"x1": 27.11, "y1": 15.41, "x2": 28.68, "y2": 18.82}, {"x1": 24.39, "y1": 22.7, "x2": 27.83, "y2": 24.71}], "targets": [{"id": "t1", "x": 22.84, "y": 21.38, "value": 2, "deadline_tick": 19, "late_value": 0.5, "appear_tick": 0}, {"id": "t2", "x": 15.47, "y": 18.17, "value": 2, "deadline_tick": 23, "late_value": 0.5, "appear_tick": 0}, {"id": "t3", "x": 28.59, "y": 21.11, "value": 2, "deadline_tick": 27, "late_value": 0.5, "appear_tick": 0}, {"id": "t4", "x": 15.09, "y": 15.16, "value": 1, "deadline_tick": 29, "late_value": 0.25, "appear_tick": 0}, {"id": "t5", "x": 21.73, "y": 27.41, "value": 1, "deadline_tick": 17, "late_value": 0.25, "appear_tick": 0}]}
```

`tools.telemetry_log()` at the start (the tick-0 briefing is always exact):

```json
[{"tick": 0, "received_tick": 0, "position": [20.0, 20.0], "heading_deg": 0.0, "battery": 100.0, "terrain": "bedrock", "wheel_odometry": 0, "visual_odometry": 0, "sampled_targets": [], "alive": true, "events": []}]
```

`tools.uplink([{"action": "drive", "heading_deg": 30, "metres": 2}, {"action": "sample"}])` at tick 0:

```json
[{"command_id": 1, "sent_tick": 0, "execute_tick": 4, "command": {"action": "drive", "heading_deg": 30, "metres": 2}}, {"command_id": 2, "sent_tick": 0, "execute_tick": 5, "command": {"action": "sample"}}]
```

`tools.advance(5)` right after that, then `tools.advance(3)`:

```json
{"current_tick": 5, "episode_complete": false, "packets": [{"tick": 1, "received_tick": 4, "position": [19.8730882643, 19.373973042], "heading_deg": 0.0, "battery": 99.5, "terrain": "bedrock", "wheel_odometry": 0.0, "visual_odometry": 0.0, "sampled_targets": [], "alive": true, "events": []}, {"tick": 2, "received_tick": 5, "position": [19.9459649287, 20.0559804652], "heading_deg": 0.0, "battery": 99.0, "terrain": "bedrock", "wheel_odometry": 0.0, "visual_odometry": 0.0, "sampled_targets": [], "alive": true, "events": []}]}
```

```json
{"current_tick": 8, "episode_complete": false, "packets": [{"tick": 3, "received_tick": 6, "position": [19.8726464666, 19.985352128], "heading_deg": 0.0, "battery": 98.5, "terrain": "bedrock", "wheel_odometry": 0.0, "visual_odometry": 0.0, "sampled_targets": [], "alive": true, "events": []}, {"tick": 4, "received_tick": 7, "position": [21.5743211742, 20.6504068396], "heading_deg": 30, "battery": 96.0, "terrain": "bedrock", "wheel_odometry": 2.0, "visual_odometry": 2.1244969514, "sampled_targets": [], "alive": true, "events": [{"type": "command_executed", "command_id": 1}]}, {"tick": 5, "received_tick": 8, "position": [22.0220397235, 20.4831444468], "heading_deg": 30, "battery": 92.5, "terrain": "bedrock", "wheel_odometry": 0.0, "visual_odometry": 0.0, "sampled_targets": [], "alive": true, "events": [{"type": "command_executed", "command_id": 2}, {"type": "sample_failed", "reason": "no_unsampled_target_in_range"}]}]}
```

## The published rules

`tools.rules()` for a mission with noisy sensing:

```json
{
 "version": "lightlag-dynamic-v1",
 "delay_ticks": 3,
 "max_ticks": 50,
 "initial_battery": 100.0,
 "idle_cost": 0.5,
 "drive_cost": 1.0,
 "sample_cost": 3.0,
 "target_radius": 0.75,
 "base_radius": 0.75,
 "supported_actions": [
  "drive",
  "sample",
  "wait"
 ],
 "scripting_allowed": true,
 "first_execution_tick": "sent_tick + delay_ticks + 1; FIFO, one command per tick",
 "telemetry_arrival_tick": "state_tick + delay_ticks; tick 0 is the initial briefing",
 "max_commands_per_uplink": 5,
 "max_metres_per_drive": 5.0,
 "max_advance_ticks": 5,
 "slip_ranges": {
  "bedrock": [
   0.0,
   0.05
  ],
  "sand": [
   0.2,
   0.45
  ]
 },
 "slip_noise": [
  -0.02,
  0.02
 ],
 "terrain_drive_multipliers": {
  "bedrock": 1.0,
  "sand": 2.0
 },
 "energy_order": "idle drain, then command; drive costs per wheel metre",
 "safety_stop": "at a hazard or map edge, stop at last safe position and clear queued commands; reservations remain",
 "sampling": "pay sampling cost; collect the nearest unsampled active target within target_radius; a discovered target is active from its appear tick",
 "reward": "sum over sampled targets of value if the sample executed at or before deadline_tick, otherwise value * late_fraction; times 1 at base, 0.5 alive elsewhere, 0 if dead; scored at the horizon",
 "drive_integration_metres": 0.1,
 "slip_model": "clip(terrain coefficient + per-drive noise, 0, 0.9); noise is fixed by seed and execution tick",
 "heading": "0 degrees east, 90 north; each executed drive travels at the commanded heading plus a heading error: a hidden bias, uniform in +-heading_bias_deg at launch, which takes a Gaussian random-walk step of heading_bias_walk_deg before every executed drive, plus independent Gaussian noise of heading_noise_deg; telemetry heading_deg reports the commanded heading",
 "visual_odometry": "reported distance = true distance * (1 + Gaussian noise with std dev visual_odometry_noise)",
 "mission_profile": "rush_noisy",
 "random_map": true,
 "sample_windows_enabled": true,
 "discoveries_enabled": true,
 "map_generator": {
  "base": [
   20.0,
   20.0
  ],
  "sand_patches": 2,
  "sand_size_m": [
   6,
   12
  ],
  "hazards": 2,
  "hazard_size_m": [
   [
    2,
    4
   ],
   [
    1,
    2.5
   ]
  ],
  "hazard_distance_m": [
   4,
   10
  ],
  "initial_targets": 5,
  "initial_distance_m": [
   3,
   9
  ],
  "initial_values": [
   1,
   2
  ],
  "initial_deadline_tick": [
   10,
   32
  ],
  "discoveries": [
   1,
   2
  ],
  "discovery_appear_tick": [
   6,
   24
  ],
  "discovery_distance_m": [
   3,
   8
  ],
  "discovery_values": [
   2,
   3
  ],
  "discovery_window_ticks": [
   6,
   12
  ],
  "min_spacing_m": 3.0,
  "hazard_clearance_m": 1.2
 },
 "profile_default_horizon": 50,
 "sensing": {
  "position_noise_m": 0.3,
  "visual_odometry_noise": 0.05,
  "heading_bias_deg": 5.0,
  "heading_bias_walk_deg": 0.5,
  "heading_noise_deg": 1.5
 },
 "noise_level": 1.0,
 "roughness": null,
 "sample_windows": {
  "late_fraction": 0.25,
  "deadline": "deadline_tick per target in map(); null means no deadline"
 },
 "discoveries": "new targets can appear mid-mission; a target_discovered event in the telemetry packet for its appear tick announces it, so it arrives delay_ticks later, and map() lists it from then on",
 "position_fix": "every delivered position after the tick-0 briefing = true position + independent Gaussian noise with std dev position_noise_m per axis, clipped to the map; the tick-0 briefing position is exact; the terrain field reports the terrain under the rover",
 "scoring_position": "sampling, base return and safety stops use the true position"
}
```

For a mission with exact sensing the same call differs only in these keys, shown as [exact, noisy]:

```json
{
 "heading": [
  "0 degrees east, 90 north",
  "0 degrees east, 90 north; each executed drive travels at the commanded heading plus a heading error: a hidden bias, uniform in +-heading_bias_deg at launch, which takes a Gaussian random-walk step of heading_bias_walk_deg before every executed drive, plus independent Gaussian noise of heading_noise_deg; telemetry heading_deg reports the commanded heading"
 ],
 "mission_profile": [
  "rush",
  "rush_noisy"
 ],
 "noise_level": [
  null,
  1.0
 ],
 "position_fix": [
  null,
  "every delivered position after the tick-0 briefing = true position + independent Gaussian noise with std dev position_noise_m per axis, clipped to the map; the tick-0 briefing position is exact; the terrain field reports the terrain under the rover"
 ],
 "scoring_position": [
  null,
  "sampling, base return and safety stops use the true position"
 ],
 "sensing": [
  null,
  {
   "position_noise_m": 0.3,
   "visual_odometry_noise": 0.05,
   "heading_bias_deg": 5.0,
   "heading_bias_walk_deg": 0.5,
   "heading_noise_deg": 1.5
  }
 ],
 "visual_odometry": [
  "exact in this prototype",
  "reported distance = true distance * (1 + Gaussian noise with std dev visual_odometry_noise)"
 ]
}
```

## Requirements

- Python 3.12, standard library only, one module, no input or output other than `tools`, no sleeping, no randomness.
- Keep your own computation between calls short: well under a second.
- Read everything you need from `rules()` and `map()` at run time; do not hard-code the example mission.

Reply with the complete module in a single ```python fenced block.
