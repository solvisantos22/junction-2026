You are preparing the autopilot for a rover that is operated through a signal delay on Mars-like ground. Write one Python module that plays a whole mission on its own.

## The mission

- One long traverse: `max_ticks` ticks (420) over a map of 600 m by 400 m, with 38 science targets known at launch and more appearing on the way. There is not enough time to visit them all. Which ones to go for, in what order and by which way over the ground is the task.
- Sample science targets and have the rover back at the lander when the mission ends.
- The score is the value earned from the sampled targets, multiplied by 1.0 if the rover ends within `base_radius` of the lander, 0.5 if it ends alive anywhere else and 0 if its battery reached zero, and divided by the total value of every target of the mission, including those that only appear later. Nobody can reach every target, so a good score is well below 1.
- A target sampled at or before its `deadline_tick` earns its full `value`; after that it earns `late_value`. What counts is the tick at which the sample command executes.

## Why this has to be a program

The mission needs several hundred commands on a map you have not seen. Your program gets the rules and the map when it starts and has to work the first time: there is one mission, no reset and no practice run, and nobody can fix the program afterwards. It will be run on a world other than the example below.

## What makes it hard

- **Commands arrive late.** A command sent at tick `t` executes at tick `t + delay_ticks + 1` at the earliest. Commands execute one per tick, in the order sent.
- **Telemetry is old.** A packet describes the rover at `packet.tick` and reaches you `delay_ticks` later. Commands you have already sent may not show in it yet.
- **The ground is not flat.** `map()` gives a height grid and a terrain class for every cell. Slip grows with the slope the rover is climbing and depends on the terrain; on a cross slope the rover slides downhill; energy is spent per wheel metre and per metre climbed. The rules give the formulas under `physics`, `drive` and `ground`. Each terrain's base slip is hidden inside a published range.
- **Steep ground stops the rover.** Where the slope exceeds `max_tilt`, the rover stops at the last safe position and every command still queued is cleared. Crater walls and the scarp are that steep. They have breaches and passes.
- **Energy comes from the sun.** The battery is charged every tick by a sun that is low at the start, highest in the middle and low again at the end, through panels whose efficiency is hidden inside a published range. A battery that reaches zero ends the rover for good.
- **Sensing is noisy and the rover drifts.** Every reported position after the tick-0 briefing carries noise, reported visual odometry carries noise, and each drive goes off the commanded heading by a hidden, slowly changing bias. Sampling, the return to the lander and safety stops are decided by the rover's true position.
- **Targets have deadlines and new ones appear.** A `target_discovered` event travels in delayed telemetry; `map()` lists the target once that packet has arrived.

## This is the MAX map

The mission is played on the MAX map: the same kind of world, targets, deadlines, sun and drive limit as above, with harder operations. `rules()["max_option"]` names the changes, and each has its own entry in `rules()` with the exact rule. Where they differ from what is said above, they hold. In short:

- **The link is open only during relay passes** (`relay_passes`): 4 ticks of every 8, while `tick % 8 < 4`. An uplink sent while the link is closed goes up when the next pass opens; its acknowledgement gives `transmit_tick` and `execute_tick`. A packet that would arrive while the link is closed arrives when the next pass opens, so telemetry comes in bursts.
- **Packets are lost** (`telemetry_packet_loss`): each telemetry packet is lost with probability 0.1.
- **Position fixes are worse** (`sensing`, `position_fix_outliers`): 2.0 m of noise per axis, and 5% of fixes are off by a further 3.0 m per axis.
- **The rover stops itself when its wheels slip too much** (`onboard_slip_check`): a drive step that slips more than 0.45 is the last of its drive and every queued command is discarded; telemetry reports a `safety_stop` with reason `slip_limit`.
- **Some ground is softer than the map says** (`crust`): `map()` lists `crust_regions`. Inside them the ground is mapped as bedrock, but each cell there whose steepest slope is at most 0.1 is soft sand underneath with probability 0.1, not listed.
- **Dune slopes are hidden** (`sand_grade_gain`): how fast slip on sand grows with the slope is hidden in [2.5, 4.5]; `physics` publishes 3.5.
- **The wheels' size is hidden** (`wheel_scale_error`): a drive of M metres turns the wheels M x scale, with scale hidden within 1 +- 0.2, and wheel odometry still reads M for a drive that runs to the end.
- **Turning costs energy** (`turn_cost`): 0.01 x the degrees turned x the drive cost per metre of the terrain underneath, paid before the drive.
- **Visual odometry noise depends on the terrain** (`visual_odometry_by_terrain`): from 0.03 on bedrock to 0.2 on sand.

## What you write

One Python module, standard library only, Python 3.12, that defines

```python
def play(tools):
    ...
```

`play` is called once, at tick 0, and should return when the mission is complete. `tools` offers exactly five calls:

- `tools.rules()`: the rules, the dictionary printed below. Free.
- `tools.map()`: the map as described below. Free.
- `tools.telemetry_log()`: every packet received so far, oldest first. Free.
- `tools.uplink(commands)`: queue 1 to 5 commands, each `{"action": "drive", "heading_deg": H, "metres": M}` (0 degrees is east, 90 is north, `M` in (0, 5]), `{"action": "sample"}` or `{"action": "wait"}`. Returns one acknowledgement per command with its `execute_tick`. A request with any invalid command raises `ValueError`, is rejected whole and changes nothing.
- `tools.advance(n)`: let `n` ticks pass, `n` from 1 to 5. The only call that moves the clock. Returns `current_tick`, `episode_complete` and the packets that arrived.

The clock does not run while your program thinks. It may take up to 20 minutes of real time in all, and no more than 2 minutes between two calls. The module may `import lightlag_surface`, the published ground model whose source is at the end of this message; it will be importable. Anything printed is ignored.

## The rules: the output of `rules()`

```json
{
 "version": "lightlag-traverse-v1",
 "delay_ticks": 3,
 "max_ticks": 420,
 "battery_capacity": 100.0,
 "initial_battery": 100.0,
 "idle_cost": 0.15,
 "sample_cost": 2.0,
 "target_radius": 2.5,
 "base_radius": 4.0,
 "solar_peak": 2.8,
 "solar_efficiency_range": [
  0.8,
  1.0
 ],
 "sun_margin_ticks": 56,
 "supported_actions": [
  "drive",
  "sample",
  "wait"
 ],
 "scripting_allowed": true,
 "first_execution_tick": "transmit_tick + delay_ticks + 1, transmit_tick being the send tick during a pass, else the tick the next pass opens; FIFO, one command per tick",
 "telemetry_arrival_tick": "state_tick + delay_ticks, or the tick the next relay pass opens if the link is closed then; tick 0 is the initial briefing",
 "max_commands_per_uplink": 5,
 "max_metres_per_drive": 5.0,
 "max_advance_ticks": 5,
 "heading": "0 degrees east (+x), 90 north (+y); each executed drive travels at the commanded heading plus a heading error: a hidden bias, uniform in +-heading_bias_deg at launch, which takes a Gaussian random-walk step of heading_bias_walk_deg before every executed drive, plus independent Gaussian noise of heading_noise_deg; telemetry heading_deg reports the commanded heading",
 "ground": "map() gives elevation_cm[j][i], the height in centimetres at x = i * cell_m, y = j * cell_m, and terrain[j][i], the class code of the grid cell whose south-west corner is that vertex. Height between vertices is bilinear inside the cell. The slope at a point is the gradient of that bilinear surface: d/dx = ((h10 - h00) * (1 - ty) + (h11 - h01) * ty) / cell_m and d/dy = ((h01 - h00) * (1 - tx) + (h11 - h10) * tx) / cell_m, with tx, ty the point's fractions inside its cell and h10 the vertex to the east",
 "physics": {
  "segment_m": 0.25,
  "max_tilt": 0.36,
  "slip_base_ranges": {
   "bedrock": [
    0.01,
    0.05
   ],
   "regolith": [
    0.05,
    0.12
   ],
   "sand": [
    0.15,
    0.35
   ],
   "rocks": [
    0.12,
    0.24
   ]
  },
  "slip_grade_gain": {
   "bedrock": 0.8,
   "regolith": 1.5,
   "sand": 3.5,
   "rocks": 1.2
  },
  "slip_noise": 0.02,
  "slip_max": 0.95,
  "side_slip_gain": {
   "bedrock": 0.1,
   "regolith": 0.3,
   "sand": 0.8,
   "rocks": 0.2
  },
  "drive_cost_per_wheel_m": {
   "bedrock": 0.3,
   "regolith": 0.36,
   "sand": 0.5,
   "rocks": 0.6
  },
  "climb_cost_per_m": 2.0
 },
 "drive": "a drive of M wheel metres is integrated in steps of segment_m, with the ground sampled where each step starts: grade = slope along the travelled heading, cross = slope to the left of it; slip = clip(slip_base[terrain] + slip_grade_gain[terrain] * max(0, grade) + noise, 0, slip_max), with slip_base[terrain] hidden inside slip_base_ranges and fixed for the mission, and noise one uniform draw in +-slip_noise per drive; the rover moves step * (1 - slip) along the heading and step * side_slip_gain[terrain] * cross to the right of it, which is downhill across the heading",
 "safety_stop": "a step that would leave the map, or end where the slope is steeper than max_tilt, is not taken: the rover stops at the last safe position and every queued command is cleared; their reserved ticks stay reserved",
 "energy": "each tick, in this order: the battery gains solar_peak * efficiency * sin(pi * (tick + sun_margin_ticks) / (max_ticks + 2 * sun_margin_ticks)), capped at battery_capacity, with efficiency hidden inside solar_efficiency_range and fixed for the mission; then idle_cost; then the command. A drive costs drive_cost_per_wheel_m[terrain] per wheel metre plus climb_cost_per_m per metre of height gained. A sample costs sample_cost, also when it fails. A battery that reaches 0 ends the rover for good",
 "sampling": "pay sample_cost; collect the nearest unsampled active target within target_radius; a discovered target is active from its appear tick",
 "sample_windows": {
  "late_fraction": 0.25,
  "deadline": "deadline_tick per target in map(); null means no deadline"
 },
 "discoveries": "new targets appear mid-mission; a target_discovered event in the telemetry packet for its appear tick announces it, so it arrives delay_ticks later, and map() lists it from then on",
 "reward": "sum over sampled targets of value if the sample executed at or before deadline_tick, otherwise value * late_fraction; times 1 within base_radius of the lander, 0.5 alive elsewhere, 0 if the battery ran out; divided by the value of every target of the mission, discovered or not; scored at max_ticks",
 "sensing": {
  "position_noise_m": 2.0,
  "visual_odometry_noise": 0.05,
  "heading_bias_deg": 5.0,
  "heading_bias_walk_deg": 0.2,
  "heading_noise_deg": 1.5,
  "visual_odometry_noise_by_terrain": {
   "bedrock": 0.03,
   "regolith": 0.05,
   "rocks": 0.05,
   "sand": 0.2
  }
 },
 "telemetry": "one packet per tick: position = true position + Gaussian noise of position_noise_m per axis, clipped to the map (the tick-0 briefing is exact); battery and charge (the solar energy gained that tick) are exact; terrain is the class under the rover and tilt the slope there; wheel_odometry is the wheel metres of the drive and visual_odometry the ground distance moved * (1 + Gaussian noise of visual_odometry_noise)",
 "scoring_position": "sampling, the return to the lander and safety stops use the true position",
 "map_generator": {
  "width_m": 600.0,
  "height_m": 400.0,
  "cell_m": 5.0,
  "relief_spacing_m": [
   200.0,
   100.0,
   50.0,
   25.0,
   12.5
  ],
  "relief_amplitude_m": [
   5.0,
   2.6,
   1.3,
   0.6,
   0.25
  ],
  "regional_tilt": 0.008,
  "craters": [
   3,
   5
  ],
  "crater_radius_m": [
   22.0,
   60.0
  ],
  "crater_depth_ratio": [
   0.19,
   0.24
  ],
  "crater_rim_ratio": [
   0.03,
   0.05
  ],
  "crater_breaches": [
   1,
   2
  ],
  "scarp_step_m": [
   5.0,
   8.0
  ],
  "scarp_length_m": [
   300.0,
   460.0
  ],
  "scarp_passes": 2,
  "terrain_share": {
   "sand": 0.18,
   "rocks": 0.12,
   "bedrock": 0.15
  },
  "sand_max_cell_slope": 0.1,
  "initial_targets": 38,
  "discoveries": 8,
  "target_clusters": 5,
  "cluster_targets": [
   4,
   6
  ],
  "cluster_radius_m": 55.0,
  "target_values": [
   1,
   5
  ],
  "target_min_spacing_m": 15.0,
  "target_min_base_distance_m": 35.0,
  "deadline_share": 0.7,
  "deadline_window": [
   0.22,
   0.95
  ],
  "discovery_appear": [
   30,
   0.68
  ],
  "discovery_window_ticks": [
   60,
   130
  ]
 },
 "map_option": "max",
 "relay_passes": {
  "period_ticks": 8,
  "open_ticks": 4,
  "rule": "the link is open only during relay passes: open_ticks ticks at the start of every period_ticks ticks (open when tick % period_ticks < open_ticks). An uplink sent between passes is transmitted when the next pass opens (its acknowledgement gives transmit_tick); a telemetry packet that would arrive between passes arrives when the next pass opens; map() lists a discovered target from the tick its packet arrives"
 },
 "onboard_slip_check": {
  "limit": 0.45,
  "rule": "onboard fault protection: if a drive step slips more than the limit, that step is the last of the drive and every queued command is discarded; telemetry reports safety_stop with reason slip_limit"
 },
 "sand_grade_gain": {
  "range": [
   2.5,
   4.5
  ],
  "rule": "dune slopes: the sand entry of slip_grade_gain is hidden inside range, fixed for the mission; physics.slip_grade_gain.sand is the published 3.5"
 },
 "crust": {
  "soft_rate": 0.1,
  "max_soft_slope": 0.1,
  "rule": "map() lists crust_regions. Inside one the ground is mapped as bedrock, but each grid cell whose steepest slope is at most max_soft_slope is soft sand underneath with probability soft_rate, fixed by the seed and not listed. A soft cell is sand for slip, slide and energy, and telemetry terrain reports sand while the rover stands on one"
 },
 "visual_odometry_by_terrain": "the relative noise of visual odometry is sensing.visual_odometry_noise_by_terrain for the terrain under the rover; a drive that starts and ends on different terrains gets the average",
 "wheel_scale_error": {
  "range": 0.2,
  "rule": "the wheels' true size is hidden: scale is uniform in 1 +- range, fixed for the mission. A drive of M metres turns the wheels M * scale wheel metres, which the drive physics integrate and the energy is paid for; wheel_odometry reports the wheel metres divided by scale (M for a drive that ran to the end)"
 },
 "turn_cost_per_degree": 0.01,
 "turn_cost": "before a drive, turning from the last commanded heading to the new one costs turn_cost_per_degree * the degrees turned * drive_cost_per_wheel_m of the terrain under the rover; the first drive turns from heading 0",
 "telemetry_packet_loss": {
  "probability": 0.1,
  "rule": "each telemetry packet is lost with this probability"
 },
 "position_fix_outliers": {
  "probability": 0.05,
  "sigma_m": 3.0,
  "rule": "with this probability a packet's position fix is off by a further Gaussian error of sigma_m per axis, clipped to the map"
 },
 "max_option": "the traverse with the max env's mechanics: position fixes 2.0 m off (sigma per axis), relay passes, onboard slip check, hidden sand slope gain, crust, visual odometry noise by terrain, hidden wheel size, turn cost, lost packets, wild position fixes. The world, targets, deadlines, sun and drive limit are the normal map's"
}
```

## The map: the output of `map()`

The grid is the same size in every world. In the example world:

```
{
 "width": 600.0,
 "height": 400.0,
 "cell_m": 5.0,
 "elevation_cm": "[81 rows of 121 integers; row j is y = j * cell_m, column i is x = i * cell_m; first row begins [-146, -135, -106, -67, -35, -14, 11, 40] ...]",
 "terrain": "[80 strings of 120 codes; string j covers y from j * cell_m to (j + 1) * cell_m; first string begins 'rrrrrrrrrrrrrrrrrrrrrrrr' ...]",
 "terrain_codes": {
  "b": "bedrock",
  "r": "regolith",
  "s": "sand",
  "k": "rocks"
 },
 "base": [
  255.0,
  210.0
 ],
 "targets": [
  {
   "id": "t1",
   "x": 580.0,
   "y": 35.0,
   "value": 3.0,
   "deadline_tick": null,
   "late_value": 3.0,
   "appear_tick": 0
  },
  {
   "id": "t2",
   "x": 465.0,
   "y": 350.0,
   "value": 2.0,
   "deadline_tick": 360,
   "late_value": 0.5,
   "appear_tick": 0
  },
  {
   "id": "t3",
   "x": 155.0,
   "y": 115.0,
   "value": 1.0,
   "deadline_tick": 296,
   "late_value": 0.25,
   "appear_tick": 0
  },
  "... 38 targets in all at launch"
 ],
 "crust_regions": [
  {
   "x1": 120.0,
   "y1": 45.0,
   "x2": 195.0,
   "y2": 105.0
  },
  {
   "x1": 205.0,
   "y1": 285.0,
   "x2": 260.0,
   "y2": 325.0
  },
  {
   "x1": 275.0,
   "y1": 45.0,
   "x2": 340.0,
   "y2": 110.0
  }
 ]
}
```

## Telemetry

`tools.telemetry_log()` at tick 0 holds one packet, the exact launch state:

```json
{"tick": 0, "received_tick": 0, "position": [255.0, 210.0], "heading_deg": 0.0, "battery": 100.0, "charge": 0.0, "terrain": "regolith", "tilt": 0.0484, "wheel_odometry": 0.0, "visual_odometry": 0.0, "sampled_targets": [], "alive": true, "events": []}
```

After `tools.uplink([{"action": "drive", "heading_deg": 90, "metres": 5}])`, which returned

```json
[{"command_id": 1, "sent_tick": 0, "transmit_tick": 0, "execute_tick": 4, "command": {"action": "drive", "heading_deg": 90, "metres": 5}}]
```

the fifth `tools.advance(1)` returned

```json
{"current_tick": 5, "episode_complete": false, "packets": []}
```

On the MAX map the link was closed at tick 5, so nothing arrived. The eighth `tools.advance(1)`, when the next relay pass opened, returned the packets of ticks 1 to 5 together (the packet of tick 3 was lost):

```json
{"current_tick": 8, "episode_complete": false, "packets": [{"tick": 1, "received_tick": 8, "position": [255.765312, 208.515783], "heading_deg": 0.0, "battery": 99.85, "charge": 0.0, "terrain": "regolith", "tilt": 0.0484, "wheel_odometry": 0.0, "visual_odometry": 0.0, "sampled_targets": [], "alive": true, "events": []}, {"tick": 2, "received_tick": 8, "position": [255.881459, 211.074017], "heading_deg": 0.0, "battery": 99.85, "charge": 0.15, "terrain": "regolith", "tilt": 0.0484, "wheel_odometry": 0.0, "visual_odometry": 0.0, "sampled_targets": [], "alive": true, "events": []}, {"tick": 4, "received_tick": 8, "position": [253.045029, 216.556812], "heading_deg": 90, "battery": 97.425378, "charge": 0.15, "terrain": "regolith", "tilt": 0.0632, "wheel_odometry": 5.0, "visual_odometry": 5.466279, "sampled_targets": [], "alive": true, "events": [{"type": "command_executed", "command_id": 1}]}, {"tick": 5, "received_tick": 8, "position": [255.315078, 214.57138], "heading_deg": 90, "battery": 98.200837, "charge": 0.925459, "terrain": "regolith", "tilt": 0.0632, "wheel_odometry": 0.0, "visual_odometry": 0.0, "sampled_targets": [], "alive": true, "events": []}]}
```

## `lightlag_surface.py`

```python
"""The ground and the drive physics of the traverse, as published.

Everything here is public: `rules()` gives the numbers and `map()` the grid. The simulator
runs a drive through `drive()` with the hidden values; a controller can run the same function
with its own estimates, so nobody has to guess how the published formulas are applied.
Standard library only, Python 3.9+.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

TERRAIN_CODES = {"b": "bedrock", "r": "regolith", "s": "sand", "k": "rocks"}

# Published physics. `rules()` returns this table unchanged.
PHYSICS: Dict[str, Any] = {
    "segment_m": 0.25,                  # a drive is integrated in steps of this many wheel metres
    "max_tilt": 0.36,                   # rise over run (about 20 degrees); steeper ground stops the rover
    "slip_base_ranges": {"bedrock": [0.01, 0.05], "regolith": [0.05, 0.12],
                         "sand": [0.15, 0.35], "rocks": [0.12, 0.24]},
    "slip_grade_gain": {"bedrock": 0.8, "regolith": 1.5, "sand": 3.5, "rocks": 1.2},
    "slip_noise": 0.02,                 # one uniform draw in +-this per executed drive
    "slip_max": 0.95,
    "side_slip_gain": {"bedrock": 0.1, "regolith": 0.3, "sand": 0.8, "rocks": 0.2},
    "drive_cost_per_wheel_m": {"bedrock": 0.30, "regolith": 0.36, "sand": 0.50, "rocks": 0.60},
    "climb_cost_per_m": 2.0,            # energy per metre of height gained; descending returns nothing
}


class Surface:
    """A height grid with bilinear interpolation, and one terrain class per grid cell.

    `elevation_cm[j][i]` is the height in centimetres at x = i * cell, y = j * cell.
    `terrain[j][i]` is the class code of the cell with that vertex as its south-west corner.
    """

    def __init__(self, cell: float, elevation_cm: Sequence[Sequence[int]], terrain: Sequence[str]) -> None:
        self.cell = float(cell)
        self.h: List[List[float]] = [[value / 100.0 for value in row] for row in elevation_cm]
        self.ny, self.nx = len(self.h), len(self.h[0])
        if self.ny < 2 or self.nx < 2 or any(len(row) != self.nx for row in self.h):
            raise ValueError("the elevation grid must be rectangular, at least 2 by 2")
        if len(terrain) != self.ny - 1 or any(len(row) != self.nx - 1 for row in terrain):
            raise ValueError("terrain needs one code per grid cell")
        self.codes: List[str] = [str(row) for row in terrain]
        self.width = (self.nx - 1) * self.cell
        self.height = (self.ny - 1) * self.cell

    def inside(self, x: float, y: float) -> bool:
        return 0.0 <= x <= self.width and 0.0 <= y <= self.height

    def locate(self, x: float, y: float) -> Tuple[int, int, float, float]:
        """The cell (i, j) holding the point and the point's fractions inside it."""
        fx, fy = x / self.cell, y / self.cell
        i = min(self.nx - 2, max(0, int(fx)))
        j = min(self.ny - 2, max(0, int(fy)))
        return i, j, fx - i, fy - j

    def sample(self, x: float, y: float) -> Tuple[float, float, float, str]:
        """Height, d(height)/dx, d(height)/dy and terrain code at a point."""
        cell = self.cell
        fx, fy = x / cell, y / cell
        i = min(self.nx - 2, max(0, int(fx)))
        j = min(self.ny - 2, max(0, int(fy)))
        tx, ty = fx - i, fy - j
        low, high = self.h[j], self.h[j + 1]
        h00, h10, h01, h11 = low[i], low[i + 1], high[i], high[i + 1]
        height = (h00 * (1 - tx) + h10 * tx) * (1 - ty) + (h01 * (1 - tx) + h11 * tx) * ty
        gx = ((h10 - h00) * (1 - ty) + (h11 - h01) * ty) / cell
        gy = ((h01 - h00) * (1 - tx) + (h11 - h10) * tx) / cell
        return height, gx, gy, self.codes[j][i]

    def elevation(self, x: float, y: float) -> float:
        return self.sample(x, y)[0]

    def slope(self, x: float, y: float) -> float:
        _, gx, gy, _ = self.sample(x, y)
        return math.hypot(gx, gy)

    def terrain(self, x: float, y: float) -> str:
        return TERRAIN_CODES[self.sample(x, y)[3]]

    def cell_max_slope(self, i: int, j: int) -> float:
        """The steepest slope anywhere in cell (i, j). On a bilinear patch that is at a corner."""
        low, high, cell = self.h[j], self.h[j + 1], self.cell
        h00, h10, h01, h11 = low[i], low[i + 1], high[i], high[i + 1]
        south, north = (h10 - h00) / cell, (h11 - h01) / cell
        west, east = (h01 - h00) / cell, (h11 - h10) / cell
        return max(math.hypot(south, west), math.hypot(south, east),
                   math.hypot(north, west), math.hypot(north, east))


def drive(surface: Surface, physics: Dict[str, Any], x: float, y: float, heading_deg: float, metres: float,
          slip_base: Dict[str, float], noise: float = 0.0, battery: Optional[float] = None) -> Dict[str, Any]:
    """One drive command: `metres` of wheel travel at `heading_deg` from (x, y).

    Per step of `segment_m` wheel metres, with the ground sampled where the step starts:
      grade  = slope along the heading (rise over run), cross = slope to the left of it
      slip   = clip(slip_base[terrain] + slip_grade_gain[terrain] * max(0, grade) + noise, 0, slip_max)
      the rover moves segment * (1 - slip) along the heading and
      segment * side_slip_gain[terrain] * cross to the right (downhill across the heading)
      energy = segment * drive_cost_per_wheel_m[terrain] + climb_cost_per_m * max(0, height gained)
    The step is refused, and the drive ends, if it would leave the map (`stop` = "map_boundary")
    or end on ground steeper than `max_tilt` (`stop` = "tilt"). With a `battery`, the drive also
    ends when the battery is spent (`stop` = "battery").

    Returns the end position, wheel and ground metres, the energy used and `stop` (None if the
    whole command ran).
    """
    radians = math.radians(heading_deg)
    ux, uy = math.cos(radians), math.sin(radians)
    segment_full = physics["segment_m"]
    gain, side, cost = physics["slip_grade_gain"], physics["side_slip_gain"], physics["drive_cost_per_wheel_m"]
    climb, slip_max, max_tilt = physics["climb_cost_per_m"], physics["slip_max"], physics["max_tilt"]
    width, height = surface.width, surface.height
    remaining = float(metres)
    wheel = ground = energy = 0.0
    stop = None
    here, gx, gy, code = surface.sample(x, y)
    while remaining > 1e-9:
        segment = min(segment_full, remaining)
        name = TERRAIN_CODES[code]
        grade = gx * ux + gy * uy
        cross = -gx * uy + gy * ux
        slip = slip_base[name] + gain[name] * (grade if grade > 0 else 0.0) + noise
        slip = 0.0 if slip < 0 else (slip_max if slip > slip_max else slip)
        forward = segment * (1.0 - slip)
        sideways = segment * side[name] * cross
        next_x = x + ux * forward + uy * sideways
        next_y = y + uy * forward - ux * sideways
        if not (0.0 <= next_x <= width and 0.0 <= next_y <= height):
            stop = "map_boundary"
            break
        there, next_gx, next_gy, next_code = surface.sample(next_x, next_y)
        if math.hypot(next_gx, next_gy) > max_tilt:
            stop = "tilt"
            break
        spent = segment * cost[name] + climb * (there - here if there > here else 0.0)
        if battery is not None and spent >= battery - energy:
            energy = battery
            wheel += segment
            ground += math.hypot(next_x - x, next_y - y)
            x, y = next_x, next_y
            stop = "battery"
            break
        energy += spent
        wheel += segment
        ground += math.hypot(next_x - x, next_y - y)
        remaining -= segment
        x, y, here, gx, gy, code = next_x, next_y, there, next_gx, next_gy, next_code
    return {"x": x, "y": y, "wheel": wheel, "ground": ground, "energy": energy, "stop": stop}
```

## Your reply

Reply with the complete module in one fenced `python` block. It is run as it is.
