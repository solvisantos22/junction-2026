"""Players for the traverse, on the normal map and the MAX map, through the five public tools.

    from lightlag_traverse_max.players import POLICIES
    POLICIES["manh_max"](PublicTools(make_env(7, "max")))

  manh_max   Manh's controller for the MAX map (below)
  manh_max_home   manh_max with Kristján's way-home rule: on the way home the battery reserve is spent
             (the `home_rule` option). A separate player, so manh_max's published scores stay valid
  pilot      Kristján's reference pilot (lightlag_traverse/pilot.py), the traverse's reference
  greedy     the same pilot without route optimisation
  straight   ... and without reading the ground: straight at the next target
  nothing    the do-nothing baseline
  (*_fast    the same with the small search budget of Kristján's pilot_fast, for sweeps)

manh_max is Kristján's pilot (subclassed; lightlag_traverse/ is not changed) with the max-env layers
of Manh's max_navigator (lightlag_dynamic/biomes/max_players.py) carried over to this ground. That
controller itself cannot drive here: it plans on a flat 40 m square. What is added:

  lost packets     before a packet is filtered, the drives that ran in the ticks of lost packets are
                   applied on the drive model (bridging); the sampled list in every packet settles a
                   sample whose outcome was lost; a command that did not run when scheduled shows a
                   stop in a lost packet, and everything sent with it is dropped; map() is read again
                   after a gap, for discoveries
  wild fixes       the published outlier chance and size make each fix's weight the chance that it is
                   an ordinary one (a mixture likelihood, as in max_navigator)
  wheel size       the battery is exact and a drive costs drive_cost x wheel metres, so a clean drive
                   (downhill, one mapped terrain, outside the crust) gives the wheel scale; two that
                   agree to 0.2% fix it. Until then visual odometry against the slip range's middle
                   gives a rough one. Every model drive and command uses it
  slip check       a ground graph without the edges and straight lines whose predicted slip would trip
                   the check: an edge where its cells are steepest along it, a line every 1.25 m, a
                   drive also one predicted sigma to either side (slip estimate + margin + the
                   published noise; the sand slope gain taken high while it is hidden). A trip lowers
                   that terrain's trip grade. A queued drive the best estimate says will trip is
                   predicted to stop there and to discard what is queued behind it, and nothing is
                   sent until it has run: a command sent before the news of a trip arrives was planned
                   for a place the rover never reached and trips again, every relay pass, otherwise
  crust            uphill crust edges carry the expected cost of a hidden soft cell tripping the
                   check; a cell the rover reports as sand inside the crust becomes sand on its map
  relay passes     each command is computed for the tick it will really run: the next pass's opening
                   + delay + 1 when the link is closed
  ripples          visual odometry is weighed against the drive model by its published noise per
                   terrain (0.2 on sand), not taken as it comes
  turn cost        in the battery forecast and the energy floor
  getting stuck    an aim point is kept while it is ahead and safe (steering skips vertices nearer
                   than one drive, and the trip check can then send the rover back and forth); a
                   target 12 drives have not brought 1 m closer is given up; a stalled way home
                   follows the cost-to-go field vertex by vertex, and if the margins leave no way home,
                   or it stalls again, they are dropped; home slack 1.25 and margin 8 ticks

On the normal map none of this switches on and manh_max plays move for move like the pilot until
the way home (a test checks the first 100 ticks). Standard library only, Python 3.9+. Methods
copied from the pilot with changes say so; they follow lightlag_traverse/pilot.py as of commit
f90cb6b (Kristján's beam search). His later `home_floor` rule (task 0.1.1: on the way home the
reserve is spent) is not in manh_max, whose published scores were played without it, so the last
ticks of a day can differ; on his worlds 2026-2029 the scores are the same
(docs/second-machine-check.md). manh_max_home is manh_max with that rule (`home_rule`): at the same
spot and battery it decides as the pilot does (tested).
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional, Set, Tuple

from lightlag_traverse.pilot import Pilot
from lightlag_traverse.planning import INF, STEPS, Ground, Sun
from lightlag_traverse.play import POLICIES as TRAVERSE_POLICIES
from lightlag_traverse.surface import TERRAIN_CODES, drive

CODE_OF = {name: code for code, name in TERRAIN_CODES.items()}
SQRT2 = math.sqrt(2.0)

MAX_DEFAULTS: Dict[str, Any] = {
    "trip_ticks": 15.0,        # ticks a trip of the slip check costs: the queue is discarded, and a stale
                               # command sent before the news arrives usually trips once more
    "trip_margin": 0.03,       # slip margin over the estimate before a terrain has three clean drives ...
    "trip_margin_known": 0.015,  # ... and after
    "sand_gain": 4.0,          # the sand slope gain the trip model assumes while it is hidden in a range
    "line_share": 0.95,        # a straight line, sampled every 1.25 m, is refused above this share of the
                               # trip grade (an edge, where its cells are steepest along it, above all of it)
    "stall_drives": 12,        # drives towards one target without getting 1 m closer before it is given up
    "bridge_noise": 0.15,      # extra position sigma per metre of a bridged drive (no visual odometry)
    "scale_agree": 0.002,      # two battery readings of the wheel scale that agree this closely fix it
    "tube_share": 1.0,         # the trip check looks this many predicted sigmas to either side of a drive ...
    "tube_max": 3.0,           # ... and at most this many metres
    "model_noise": 0.04,       # relative error of a modelled drive, weighed against visual odometry's
    "rebuild_every": 8,        # ticks between rebuilds for what the trips and the crust taught; the drive
                               # checks use it at once, only the cost-to-go fields wait
    "max_home_slack": 1.25,    # on the MAX map, the pilot's home_slack and home_margin become these: relay
    "max_home_margin": 8.0,    # passes, detours around traps and trips make the way home slower than planned
    "home_rule": False,        # True (the player manh_max_home): on the way home, spend the reserve down to the
                               # pilot's home_floor and creep on what the battery can pay for. Off in manh_max,
                               # whose published scores were played without it
}


class TripModel:
    """Where the onboard slip check is expected to stop a drive: per terrain code, the uphill grade
    above which a step is predicted to slip more than the limit; and the crust cells that may hide
    sand. `limit` None: there is no check and nothing here changes the ground."""

    def __init__(self, limit: Optional[float], crust: Set[Tuple[int, int]], soft_rate: float,
                 trip_ticks: float) -> None:
        self.limit = limit
        self.grade: Dict[str, float] = {code: INF for code in TERRAIN_CODES}    # with margins: for planning
        self.likely: Dict[str, float] = {code: INF for code in TERRAIN_CODES}   # best estimate: for prediction
        self.crust = crust
        self.soft_rate = soft_rate
        self.trip_ticks = trip_ticks


class MaxGround(Ground):
    """Kristján's ground graph (planning.Ground) that also knows the onboard slip check."""

    def __init__(self, surface, physics, slip_base, max_metres, energy_weight, trips: TripModel,
                 line_share: float = 0.95) -> None:
        self.trips, self.line_share, self._steep = trips, line_share, None
        super().__init__(surface, physics, slip_base, max_metres, energy_weight)

    def _steepest(self) -> List[List[List[float]]]:
        """For every cell and each of the eight edge directions, the steepest uphill grade along that
        direction anywhere in the cell. Along a fixed direction the bilinear patch's grade is linear in
        each coordinate, so the steepest is at a corner. Computed once: the heights never change."""
        if getattr(self, "_steep", None) is None:
            h, cell = self.surface.h, self.cell
            units = [(di / math.hypot(di, dj), dj / math.hypot(di, dj)) for di, dj in STEPS]
            steep = []
            for j in range(self.ny - 1):
                row = []
                for i in range(self.nx - 1):
                    h00, h10, h01, h11 = h[j][i], h[j][i + 1], h[j + 1][i], h[j + 1][i + 1]
                    corners = [(((h10 - h00) * (1 - ty) + (h11 - h01) * ty) / cell,
                                ((h01 - h00) * (1 - tx) + (h11 - h10) * tx) / cell) for tx in (0, 1) for ty in (0, 1)]
                    row.append([max(gx * ux + gy * uy for gx, gy in corners) for ux, uy in units])
                steep.append(row)
            self._steep = steep
        return self._steep

    def rebuild(self, slip_base: Dict[str, float]) -> None:
        super().rebuild(slip_base)
        trips = self.trips
        if trips is None or trips.limit is None:
            return
        nx, ny, codes = self.nx, self.ny, self.surface.codes
        steep, top = self._steepest(), trips.grade
        direction = {step: k for k, step in enumerate(STEPS)}
        incoming = []
        for b, edges in enumerate(self.incoming):
            tj, ti = divmod(b, nx)
            kept = []
            for edge in edges:
                j, i = divmod(edge[0], nx)
                di, dj = ti - i, tj - j
                k = direction[(di, dj)]
                if di and dj:
                    cells = [(min(i, ti), min(j, tj))]
                elif di:
                    cells = [(min(i, ti), b2) for b2 in (j - 1, j) if 0 <= b2 < ny - 1]
                else:
                    cells = [(a2, min(j, tj)) for a2 in (i - 1, i) if 0 <= a2 < nx - 1]
                grades = [steep[cj][ci][k] for ci, cj in cells]
                if any(g > top[codes[cj][ci]] for g, (ci, cj) in zip(grades, cells)):
                    continue                                   # the check would stop the rover somewhere on it
                if trips.crust:
                    risky = sum((ci, cj) in trips.crust and g > top["s"] for g, (ci, cj) in zip(grades, cells))
                    if risky:
                        extra = trips.soft_rate * risky / len(cells) * trips.trip_ticks
                        edge = (edge[0], edge[1] + extra, edge[2] + extra, edge[3])
                kept.append(edge)
            incoming.append(kept)
        self.incoming = incoming

    def straight(self, x0: float, y0: float, x1: float, y1: float, tilt: Optional[float] = None):
        leg = super().straight(x0, y0, x1, y1, tilt)
        trips = self.trips
        if leg is None or trips is None or trips.limit is None:
            return leg
        distance = math.hypot(x1 - x0, y1 - y0)
        if distance < 1e-9:
            return leg
        pieces = max(1, int(distance / 1.25 + 0.999))     # the same pieces as Ground.straight
        piece = distance / pieces
        ux, uy = (x1 - x0) / distance, (y1 - y0) / distance
        cell, share = self.cell, self.line_share
        risk = 0.0
        for k in range(pieces):
            at = (k + 0.5) * piece
            px, py = x0 + ux * at, y0 + uy * at
            _, gx, gy, code = self.surface.sample(px, py)
            grade = gx * ux + gy * uy
            if grade > trips.grade[code] * share:
                return None
            if trips.crust and grade > trips.grade["s"] * share and \
                    (min(self.nx - 2, int(px / cell)), min(self.ny - 2, int(py / cell))) in trips.crust:
                risk += trips.soft_rate * piece / cell
        return leg[0] + risk * trips.trip_ticks, leg[1]


class MaxPilot(Pilot):
    """Kristján's pilot with the max-env layers. Options: the pilot's DEFAULTS and MAX_DEFAULTS."""

    def __init__(self, tools: Any, options: Optional[Dict[str, Any]] = None) -> None:
        self._building = True                                  # the parent's cost fields wait for MaxGround
        super().__init__(tools, dict(MAX_DEFAULTS, **(options or {})))
        self._building = False
        rules, world = self.rules, tools.map()
        cell = world["cell_m"]
        crust: Set[Tuple[int, int]] = set()
        for region in world.get("crust_regions") or []:
            for j in range(int(round(region["y1"] / cell)), int(round(region["y2"] / cell))):
                for i in range(int(round(region["x1"] / cell)), int(round(region["x2"] / cell))):
                    crust.add((i, j))
        check = rules.get("onboard_slip_check") or {}
        self.relaxed = False
        self.trips = TripModel(check.get("limit"), crust, (rules.get("crust") or {}).get("soft_rate", 0.0),
                               self.opt["trip_ticks"])
        relay = rules.get("relay_passes")
        self.relay = (relay["period_ticks"], relay["open_ticks"]) if relay else None
        self.scale_error = (rules.get("wheel_scale_error") or {}).get("range", 0.0)
        self.scale, self.scale_exact = 1.0, not self.scale_error
        self.sand_gain_hidden = bool(rules.get("sand_grade_gain"))
        self.turn_rate = rules.get("turn_cost_per_degree", 0.0)
        wild = rules.get("position_fix_outliers") or {}
        self.wild_p, self.wild_sigma = wild.get("probability", 0.0), wild.get("sigma_m", 0.0)
        self.observations: Dict[str, List[Tuple[float, float]]] = {name: [] for name in self.slip}
        self.scale_votes: List[float] = []
        self.vo_votes: List[float] = []
        self.trip_caps: Dict[str, float] = {}
        self.soft_cells: Set[Tuple[int, int]] = set()
        self.vo_by_terrain = (rules.get("sensing") or {}).get("visual_odometry_noise_by_terrain")
        self.max_map = rules.get("map_option") == "max"
        if self.max_map:
            self.opt["home_slack"], self.opt["home_margin"] = self.opt["max_home_slack"], self.opt["max_home_margin"]
        self.walk_home = False
        self._aim: Optional[Tuple[str, float, float]] = None
        self.gave_up: Set[str] = set()
        self._progress: Dict[str, List[float]] = {}           # goal -> [closest distance, drives since]
        self.bridged = self.cleared = self.trips_seen = 0
        self.scale_from_battery: Optional[Tuple[int, float]] = None
        self._prev: Optional[Dict[str, Any]] = None
        self._gap = self._dirty = False
        self._built_at = 0
        self._trip_ahead: Optional[int] = None
        self._sigma = 0.0
        self.anchor_heading = self._pred_heading = 0.0        # the launch heading
        self._update_trips()
        self.ground = MaxGround(self.surface, self.physics, self.slip, self.max_metres, self.opt["energy_weight"],
                                self.trips, self.opt["line_share"])
        self.built_slip = dict(self.slip)
        self._field("base")
        for target_id in self.targets:
            self._field(target_id)

    # ---- the model ---------------------------------------------------------------------
    def _model(self, x: float, y: float, heading: float, metres: float) -> Dict[str, Any]:
        """The published drive with the slip estimates and the wheel scale."""
        return drive(self.surface, self.physics, x, y, heading, metres * self.scale, self.slip)

    def _field(self, name: str):
        if self._building:
            return None
        return super()._field(name)

    def _rebuild(self) -> None:
        self._update_trips()
        self.ground.max_metres = self.max_metres * self.scale
        self._dirty, self._built_at = False, self.now
        super()._rebuild()

    def _update_trips(self) -> None:
        limit = self.trips.limit
        if limit is None:
            return
        noise = self.physics["slip_noise"]
        for code, name in TERRAIN_CODES.items():
            gain = published = self.physics["slip_grade_gain"][name]
            if name == "sand" and self.sand_gain_hidden:
                gain = max(gain, self.opt["sand_gain"])
            known = len(self.observations[name]) >= 3
            base = self.slip[name] + self.opt["trip_margin_known" if known else "trip_margin"]
            cap = self.trip_caps.get(code, INF)
            self.trips.likely[code] = max(0.0, min((limit - self.slip[name]) / published, cap))
            self.trips.grade[code] = self.trips.likely[code] if self.relaxed else \
                max(0.0, min((limit - noise - base) / gain, cap))

    # ---- one decision (Pilot.act, at the tick the command will really run) ----------------
    def _open_at(self, tick: int) -> int:
        if self.relay is None or tick % self.relay[0] < self.relay[1]:
            return tick
        return (tick // self.relay[0] + 1) * self.relay[0]

    def act(self) -> None:
        if not self.alive:
            return
        tick = max(self._open_at(self.now) + self.delay + 1, self.reserved_until + 1)
        if tick > self.horizon:
            return
        x, y, sigma, battery = self.predict(tick)
        if self._trip_ahead is not None and self._trip_ahead > self.now:
            return              # a queued drive will trip the check and discard whatever is sent before it runs
        self._sigma = sigma
        command = self._decide(tick, x, y, sigma, battery)
        if command is None:
            return
        try:
            acks = self.tools.uplink([command])
        except ValueError:
            return
        for ack in acks:
            if ack["execute_tick"] != tick:               # not expected; keep the sample bookkeeping right
                for target_id, when in list(self.pending.items()):
                    if when == tick:
                        self.pending[target_id] = ack["execute_tick"]
            self.schedule[ack["execute_tick"]] = {"command": ack["command"], "sent": ack["sent_tick"]}
            self.by_id[ack["command_id"]] = ack["execute_tick"]
            self.reserved_until = max(self.reserved_until, ack["execute_tick"])

    # ---- telemetry (Pilot.observe and Pilot._packet, with the additions) -----------------
    def observe(self, packets: List[Dict[str, Any]], now: int) -> None:
        self.now = now
        for packet in packets:
            if packet["tick"] <= self.anchor_tick:
                continue
            self._packet(packet)
        if self._gap:
            self._gap = False
            self._poll_map()
        moved = max(abs(self.slip[name] - self.built_slip[name]) for name in self.slip)
        due = self._dirty and now - self._built_at >= self.opt["rebuild_every"]
        if (moved > self.opt["rebuild_shift"] or due) and self.opt["terrain"]:
            self._rebuild()

    def _packet(self, packet: Dict[str, Any]) -> None:
        tick = packet["tick"]
        if tick > self.anchor_tick + 1:
            self._bridge(tick)
            self._gap = True
        events = packet["events"]
        ran = self.schedule.get(tick)
        executed = any(e["type"] == "command_executed" for e in events)
        if ran is not None and not executed and packet["alive"]:
            self._cleared(tick, ran)                         # a stop in a lost packet emptied the queue
            ran = None
        stopped = [e.get("reason") for e in events if e["type"] == "safety_stop"]
        f = self.filter
        if executed and ran and ran["command"]["action"] == "drive":
            command = ran["command"]
            heading = command["heading_deg"] + f.bias
            model = self._model(f.x, f.y, heading, command["metres"])
            dx, dy = model["x"] - f.x, model["y"] - f.y
            expected = math.hypot(dx, dy)
            seen, wheel = packet["visual_odometry"], packet["wheel_odometry"]
            scale = seen / expected if expected > 0.2 else (1.0 if seen > 0 else 0.0)
            scale = min(2.0, max(0.0, scale))
            if self.vo_by_terrain and not stopped and expected > 0.2:
                # visual odometry noise is published by terrain (0.2 on sand): weigh it against the model
                ends = [packet["terrain"]] + ([self._prev["terrain"]] if self._prev else [])
                noise = sum(self.vo_by_terrain.get(name, 0.05) for name in ends) / len(ends)
                model_var = self.opt["model_noise"] ** 2
                scale = 1.0 + model_var / (model_var + noise * noise) * (scale - 1.0)
            if "slip_limit" not in stopped:
                if not stopped:
                    self._learn_scale(packet, command, f.x, f.y, heading, wheel)
                self._learn_slip(f.x, f.y, heading, wheel, seen)
            f.move(dx * scale, dy * scale, seen, math.radians(heading))
        self._fix(*packet["position"])
        # the panels: a charge that did not fill the battery shows their efficiency exactly
        rate = self.rules["solar_peak"] * math.sin(
            math.pi * (tick + self.rules["sun_margin_ticks"]) / (self.horizon + 2 * self.rules["sun_margin_ticks"]))
        if (not self.efficiency_known and packet["charge"] > 0 and rate > 0
                and self.anchor_battery + packet["charge"] < self.capacity - 1e-6
                and tick == self.anchor_tick + 1):
            self.efficiency, self.efficiency_known = packet["charge"] / rate, True
            self.sun = Sun(self.rules, self.efficiency)
            self.need_plan = self.full_plan = True      # the first plan was made on a cautious guess
        self.anchor_tick, self.anchor_battery = tick, packet["battery"]
        self.anchor_heading = packet["heading_deg"]
        if not packet["alive"]:
            self.alive = False
        for event in events:
            kind = event["type"]
            if kind == "sample_taken":
                self.sampled.add(event["target_id"])
                self.pending.pop(event["target_id"], None)
                self.need_plan = True
            elif kind == "sample_failed":
                for target_id, when in list(self.pending.items()):
                    if when == tick:
                        del self.pending[target_id]          # it is open again
                self.need_plan = True
            elif kind == "target_discovered":
                target = event["target"]
                self.targets[target["id"]] = target
                self._field(target["id"])
                self.need_plan = True
            elif kind == "safety_stop":
                # everything sent before this tick and not yet run was cleared
                for when in [w for w, item in self.schedule.items() if w > tick and item["sent"] < tick]:
                    cleared = self.schedule.pop(when)
                    if cleared["command"]["action"] == "sample":
                        for target_id, at in list(self.pending.items()):
                            if at == when:
                                del self.pending[target_id]
                if event.get("reason") == "tilt" and self.opt["terrain"]:
                    self._block(f.x, f.y)
                elif event.get("reason") == "slip_limit":
                    self._tripped(ran, packet)
                self.need_plan = True
        self._crust_reading(packet)
        self._sync(packet)
        self._prev = packet

    def _bridge(self, tick: int) -> None:
        """The ticks of lost packets: their scheduled drives, on the model, with extra uncertainty."""
        f = self.filter
        for t in range(self.anchor_tick + 1, tick):
            item = self.schedule.get(t)
            if item is None or item["command"]["action"] != "drive":
                continue
            command = item["command"]
            heading = command["heading_deg"] + f.bias
            model = self._model(f.x, f.y, heading, command["metres"])
            f.move(model["x"] - f.x, model["y"] - f.y, model["ground"], math.radians(heading))
            extra = (self.opt["bridge_noise"] * model["ground"]) ** 2
            f.P[0][0] += extra
            f.P[1][1] += extra
            self.bridged += 1
        self._prev = None                                    # the battery before this packet is unknown

    def _cleared(self, tick: int, ran: Dict[str, Any]) -> None:
        """The command scheduled for `tick` did not run: it, and everything sent with or before it, is gone."""
        for when in [w for w, item in self.schedule.items() if w >= tick and item["sent"] <= ran["sent"]]:
            item = self.schedule.pop(when)
            if item["command"]["action"] == "sample":
                for target_id, at in list(self.pending.items()):
                    if at == when:
                        del self.pending[target_id]
        self.cleared += 1
        self.need_plan = True

    def _sync(self, packet: Dict[str, Any]) -> None:
        """Every packet lists the sampled targets: it settles samples whose own packet was lost."""
        for target_id in packet["sampled_targets"]:
            if target_id not in self.sampled:
                self.sampled.add(target_id)
                self.pending.pop(target_id, None)
                self.need_plan = True
        for target_id, when in list(self.pending.items()):
            if when <= packet["tick"] and target_id not in self.sampled:
                del self.pending[target_id]                  # it failed, in a lost packet: open again
                self.need_plan = True

    def _poll_map(self) -> None:
        for target in self.tools.map()["targets"]:
            if target["id"] not in self.targets:
                self.targets[target["id"]] = target
                self._field(target["id"])
                self.need_plan = True

    def _fix(self, zx: float, zy: float) -> None:
        """Pilot's fix, weighted by the chance that it is an ordinary fix and not a wild one."""
        f = self.filter
        if self.wild_p <= 0:
            f.fix(zx, zy)
            return
        P, r = f.P, f.fix_var
        s00, s01, s11 = P[0][0] + r, P[0][1], P[1][1] + r
        w2 = self.wild_sigma ** 2
        det, det_wild = s00 * s11 - s01 * s01, (s00 + w2) * (s11 + w2) - s01 * s01
        if det <= 1e-12:
            return
        vx, vy = zx - f.x, zy - f.y
        d2 = (s11 * vx * vx - 2 * s01 * vx * vy + s00 * vy * vy) / det
        d2_wild = ((s11 + w2) * vx * vx - 2 * s01 * vx * vy + (s00 + w2) * vy * vy) / det_wild
        ordinary = (1.0 - self.wild_p) * math.exp(-0.5 * d2) / math.sqrt(det)
        wild = self.wild_p * math.exp(-0.5 * d2_wild) / math.sqrt(det_wild)
        weight = ordinary / (ordinary + wild) if ordinary + wild > 0 else 0.0
        f.fix_var = r / max(weight, 0.02)
        try:
            f.fix(zx, zy)
        finally:
            f.fix_var = r

    # ---- learning ---------------------------------------------------------------------------
    def _path_codes(self, x: float, y: float, heading_deg: float, reach: float, points: int = 8):
        radians = math.radians(heading_deg)
        ux, uy = math.cos(radians), math.sin(radians)
        out = []
        for k in range(points):
            at = reach * (k + 0.5) / points
            px, py = x + ux * at, y + uy * at
            _, gx, gy, code = self.surface.sample(px, py)
            cell = (min(self.surface.nx - 2, int(px / self.surface.cell)),
                    min(self.surface.ny - 2, int(py / self.surface.cell)))
            out.append((code, gx * ux + gy * uy, cell in self.trips.crust))
        return out

    def _learn_slip(self, x: float, y: float, heading_deg: float, wheel: float, seen: float) -> None:
        """Pilot._learn_slip with the wheel scale, and not inside the crust (a soft cell may be under it)."""
        if wheel < 1.5:
            return
        path = self._path_codes(x, y, heading_deg, max(seen, 0.5))
        codes = {code for code, _, _ in path}
        if len(codes) != 1 or any(crust for _, _, crust in path):
            return
        name = TERRAIN_CODES[codes.pop()]
        grade = sum(max(0.0, g) for _, g, _ in path) / len(path)
        ratio = seen / wheel
        self.observations[name].append((ratio, grade))
        if not self.scale_exact and name in ("bedrock", "regolith"):
            low, high = self.physics["slip_base_ranges"][name]
            self.vo_votes.append(ratio / (1.0 - 0.5 * (low + high) - self.physics["slip_grade_gain"][name] * grade))
            if len(self.vo_votes) >= 3:
                rough = statistics.median(self.vo_votes)
                rough = min(1.0 + self.scale_error, max(1.0 - self.scale_error, rough))
                if abs(rough - self.scale) > 0.01:
                    self._set_scale(rough, exact=False)
                    return
        self._refit(name)

    def _refit(self, name: str) -> None:
        low, high = self.physics["slip_base_ranges"][name]
        gain = self.physics["slip_grade_gain"][name]
        mean = low + self.opt["slip_prior"] * (high - low)
        weight = 1.0
        for ratio, grade in self.observations[name]:
            weight += 1.0
            mean += (1.0 - ratio / self.scale - gain * grade - mean) / weight
        self.slip_seen[name] = [weight, mean]
        slack = 0.0 if self.scale_exact else 0.03         # room for a wheel scale not yet exact
        self.slip[name] = min(high + slack, max(low - slack, mean))

    def _set_scale(self, scale: float, exact: bool) -> None:
        self.scale, self.scale_exact = scale, exact
        for name in self.slip:
            self._refit(name)
        self._dirty = True

    def _learn_scale(self, packet: Dict[str, Any], command: Dict[str, Any], x: float, y: float,
                     heading: float, wheel: float) -> None:
        """The wheel scale off the exact battery: a drive on one terrain, all downhill (no climbing
        energy), outside the crust, spends drive_cost x scale x wheel odometry plus the turn."""
        prev = self._prev
        if self.scale_exact or prev is None or prev["tick"] != packet["tick"] - 1 or wheel < 1.0:
            return
        name = packet["terrain"]
        if prev["terrain"] != name or not prev["alive"]:
            return
        model = self._model(x, y, heading, command["metres"])
        path = self._path_codes(x, y, heading, max(model["ground"], 0.5), 16)
        if any(code != CODE_OF[name] or grade > -0.005 or crust for code, grade, crust in path):
            return
        cost = self.physics["drive_cost_per_wheel_m"][name]
        energy = prev["battery"] + packet["charge"] - self.rules["idle_cost"] - packet["battery"]
        if self.turn_rate:
            turn = abs((command["heading_deg"] - prev["heading_deg"] + 180.0) % 360.0 - 180.0)
            energy -= self.turn_rate * turn * cost
        scale = energy / (cost * wheel)
        if abs(scale - 1.0) > self.scale_error + 0.01:
            return
        for other in self.scale_votes:
            if abs(other - scale) <= self.opt["scale_agree"] * scale:
                self.scale_from_battery = (packet["tick"], 0.5 * (other + scale))
                self._set_scale(0.5 * (other + scale), exact=True)
                return
        self.scale_votes.append(scale)

    def _tripped(self, ran: Optional[Dict[str, Any]], packet: Dict[str, Any]) -> None:
        """The slip check stopped a drive: that terrain trips at least at the grade there."""
        self.trips_seen += 1
        if ran is None or self.trips.limit is None:
            return
        f = self.filter
        radians = math.radians(ran["command"]["heading_deg"] + f.bias)
        ux, uy = math.cos(radians), math.sin(radians)
        # the step that tripped ended about here: blame the most slip-prone ground within half a metre
        spots = [(f.x + ux * d, f.y + uy * d) for d in (-0.5, 0.0, 0.5)]
        samples = [self.surface.sample(px, py) for px, py in spots]
        codes = {s[3] for s in samples} | {CODE_OF[packet["terrain"]]}
        code = min(codes, key=lambda c: self.trips.likely[c])
        grade = max(gx * ux + gy * uy for _, gx, gy, _ in samples)
        floor = 0.5 * self.trips.likely[code]
        if grade > 0.01:
            self.trip_caps[code] = min(self.trip_caps.get(code, INF), max(grade, floor))
        self._dirty = True

    def _crust_reading(self, packet: Dict[str, Any]) -> None:
        """Sand reported inside the crust: that cell is soft, on this pilot's map from now on."""
        if not self.trips.crust or packet["terrain"] != "sand":
            return
        s, f = self.surface, self.filter
        cell = (min(s.nx - 2, max(0, int(f.x / s.cell))), min(s.ny - 2, max(0, int(f.y / s.cell))))
        if cell in self.trips.crust and cell not in self.soft_cells and s.codes[cell[1]][cell[0]] != "s":
            row = s.codes[cell[1]]
            s.codes[cell[1]] = row[:cell[0]] + "s" + row[cell[0] + 1:]
            self.soft_cells.add(cell)
            self._dirty = True

    # ---- prediction and driving (Pilot.predict, Pilot._drive, Pilot._sidestep with the model above) ----
    def predict(self, tick: int) -> Tuple[float, float, float, float]:
        """Pilot.predict with the model above, and the slip check: a queued drive the trip model says
        will trip stops where it trips, and the commands queued behind it are discarded with it.
        `_trip_ahead` is the tick of the first such trip, or None."""
        f = self.filter
        x, y, battery, sigma = f.x, f.y, self.anchor_battery, f.sigma
        self._trip_ahead = None
        last = self.anchor_heading
        for t in range(self.anchor_tick + 1, tick):
            battery = min(self.capacity, battery + self.sun.rate[min(t, self.horizon + 1)]) - self.sun.idle
            item = self.schedule.get(t)
            if item is None or (self._trip_ahead is not None and item["sent"] < self._trip_ahead):
                continue
            command = item["command"]
            if command["action"] == "drive":
                battery -= self._turn_energy(x, y, last, command["heading_deg"])
                last = command["heading_deg"]
                heading = command["heading_deg"] + f.bias
                model = self._model(x, y, heading, command["metres"])
                trip = self._trips_on(x, y, heading, model["ground"], likely=True)
                if trip is not None:
                    self._trip_ahead = t
                    x, y = x + trip[0], y + trip[1]
                    battery -= model["energy"] * trip[2]
                else:
                    x, y = model["x"], model["y"]
                    battery -= model["energy"]
                sigma = math.hypot(sigma, 0.06 * command["metres"] + 0.1)
            elif command["action"] == "sample":
                battery -= self.rules["sample_cost"]
        self._pred_heading = last
        return x, y, sigma, battery

    def _turn_energy(self, x: float, y: float, last: float, heading: float) -> float:
        """The published turn cost of turning from the last commanded heading to this one at (x, y)."""
        if not self.turn_rate:
            return 0.0
        name = TERRAIN_CODES[self.surface.sample(x, y)[3]]
        turn = abs((heading - last + 180.0) % 360.0 - 180.0)
        return self.turn_rate * turn * self.physics["drive_cost_per_wheel_m"][name]

    def _trips_on(self, x: float, y: float, heading_deg: float, ground: float, sigma: float = 0.0,
                  likely: bool = False):
        """Would a step of this drive, as modelled, trip the slip check, from (x, y) or from a point
        `sigma` to either side of it? With the planning margins, or `likely`: the best estimate.
        None, or the move to the first tripping step and the share of the drive done by then."""
        if self.trips.limit is None:
            return None
        radians = math.radians(heading_deg)
        ux, uy = math.cos(radians), math.sin(radians)
        if likely:
            top = self.trips.likely
        else:
            top = {code: grade * self.opt["line_share"] for code, grade in self.trips.grade.items()}
        steps = max(1, int(ground / self.physics["segment_m"] + 0.999))
        offsets = (0.0, -sigma, sigma) if sigma > 0 else (0.0,)
        for k in range(steps):
            at = ground * k / steps
            for side in offsets:
                _, gx, gy, code = self.surface.sample(x + ux * at - uy * side, y + uy * at + ux * side)
                if gx * ux + gy * uy > top[code]:
                    step = at + self.physics["segment_m"] * 0.5
                    return ux * step, uy * step, (k + 1) / steps
        return None

    def _open(self, tick: int) -> List[str]:
        return [t for t in super()._open(tick) if t not in self.gave_up]

    def _stalled(self, goal: str, distance: float) -> bool:
        """On the MAX map: a target the rover has driven at stall_drives times without getting 1 m
        closer is given up (a trap the model cannot see, or two aims that send it back and forth).
        The way home is not given up: it follows the cost-to-go field vertex by vertex instead."""
        if not self.max_map:
            return False
        track = self._progress.setdefault(goal, [distance, 0])
        if distance < track[0] - 1.0:
            track[0], track[1] = distance, 0
            return False
        track[1] += 1
        if track[1] < self.opt["stall_drives"]:
            return False
        if goal == "base":
            if self.walk_home:
                self._relax()                                  # stalled twice: take the trip risk
            self.walk_home = True
            track[0], track[1] = distance, 0
            return False
        self.gave_up.add(goal)
        self.route = [t for t in self.route if t != goal]
        self.need_plan = True
        return True

    def _aim_at(self, goal: str, x: float, y: float, gx: float, gy: float):
        """Kristján's steering, and on the MAX map two additions. An aim point kept while it is still
        ahead and safe to drive at: steering skips vertices nearer than one drive, and near an aim the
        trip check can refuse every line onwards, so the next aim may lie behind and the one after
        that ahead again. And the way home vertex by vertex along the field once it has stalled."""
        field = self._field(goal)
        if field is None:
            return None
        if self.max_map and goal == "base" and not self.relaxed:
            node = self.ground.node(x, y)
            if node is None or field.cost[node] == INF:
                self._relax()                                  # no way home with the margins: drop them
                field = self._field(goal)
                if field is None:
                    return None
        if self.max_map and goal == "base" and self.walk_home:
            node = self.ground.node(x, y)
            if node is not None and field.step[node] >= 0:
                nxt = field.step[node]
                px, py = self.ground.point(nxt)
                if math.hypot(px - x, py - y) < 1.5 and field.step[nxt] >= 0:
                    px, py = self.ground.point(field.step[nxt])
                return px, py, 0.0, 0.0
        aim = self.ground.steer(x, y, field, (gx, gy))
        if not self.max_map:
            return aim
        kept = self._aim
        if kept is not None and kept[0] == goal and math.hypot(kept[1] - x, kept[2] - y) >= 1.0 and (
                aim is None or self._turn(x, y, kept[1], kept[2], aim[0], aim[1]) > 90.0) and \
                self.ground.straight(x, y, kept[1], kept[2]) is not None:
            aim = (kept[1], kept[2], 0.0, 0.0)
        self._aim = (goal, aim[0], aim[1]) if aim is not None else None
        return aim

    def _relax(self) -> None:
        """Ending away from the lander halves the score: from now on plan with the best estimate of
        where the check trips, without the margins, and take the risk of a trip."""
        if not self.relaxed:
            self.relaxed = True
            self._rebuild()

    @staticmethod
    def _turn(x: float, y: float, ax: float, ay: float, bx: float, by: float) -> float:
        a = math.degrees(math.atan2(ay - y, ax - x))
        b = math.degrees(math.atan2(by - y, bx - x))
        return abs((a - b + 180.0) % 360.0 - 180.0)

    def _drive(self, goal: str, x: float, y: float, gx: float, gy: float, distance: float,
               battery: float) -> Optional[Dict[str, Any]]:
        command = self._drive_command(goal, x, y, gx, gy, distance, battery)
        if command and command["action"] == "drive" and self._stalled(goal, distance):
            return {"action": "wait"}                          # replanned without it next tick
        return command

    def _drive_command(self, goal: str, x: float, y: float, gx: float, gy: float, distance: float,
                       battery: float) -> Optional[Dict[str, Any]]:
        """Pilot._drive with the wheel scale, the trip check, the turn cost and the aim above."""
        aim = None
        if self.opt["terrain"]:
            aim = self._aim_at(goal, x, y, gx, gy)
        if aim is None:
            aim = (gx, gy, 0.0, 0.0)
        ax, ay = aim[0], aim[1]
        reach = math.hypot(ax - x, ay - y)
        if reach < 1e-6:
            return {"action": "wait"}
        want = math.atan2(ay - y, ax - x)
        ux, uy = math.cos(want), math.sin(want)
        _, sx, sy, code = self.surface.sample(x, y)
        name = TERRAIN_CODES[code]
        grade, cross = sx * ux + sy * uy, -sx * uy + sy * ux
        slip = min(0.9, self.slip[name] + self.physics["slip_grade_gain"][name] * max(0.0, grade))
        lean = math.degrees(self.physics["side_slip_gain"][name] * cross / (1.0 - slip))   # steer up the cross slope
        heading = math.degrees(want) + lean
        metres = self.max_metres
        final = (ax, ay) == (gx, gy)
        per_metre = (1.0 - slip) * self.scale                 # ground metres per commanded metre
        if final or reach < self.max_metres * per_metre:
            metres = min(self.max_metres, max(0.05, reach / per_metre))
        # try the drive on the model first; shorten it rather than run onto steep ground or trip the check
        for _ in range(5):
            model = self._model(x, y, heading, metres)
            if (model["stop"] is None and self.surface.slope(model["x"], model["y"]) <= self.ground.tilt_safe * 1.08
                    and self._trips_on(x, y, heading, model["ground"], self._tube()) is None):
                break
            metres *= 0.5
            if metres < 0.2:
                return {"action": "wait"} if not self.opt["terrain"] else self._sidestep(x, y, want)
        commanded = (heading - self.filter.bias) % 360.0
        turn = self._turn_energy(x, y, self._pred_heading, commanded)
        if not self.opt["home_rule"]:
            if battery - model["energy"] - turn - self.sun.idle < self.opt["floor"]:
                return {"action": "wait"}                      # let the sun catch up
            return {"action": "drive", "heading_deg": commanded, "metres": round(metres, 3)}
        # Kristján's way-home rule (lightlag_traverse/pilot.py, task 0.1.1), with the turn cost paid first: a
        # reserve is worth nothing once the mission is over, and stopping short of the lander costs half the
        # score, so on the way home it is spent down to home_floor, creeping on what the battery can pay for
        reserve = self.opt["floor"]
        if goal == "base":
            reserve = min(reserve, self.opt["home_floor"])
        spare = battery - self.sun.idle - reserve - turn
        if model["energy"] > spare:
            if goal != "base" or spare <= 0.0:
                return {"action": "wait"}                      # let the sun catch up
            for _ in range(4):                                 # the first part of the same drive
                metres *= min(0.9, spare / model["energy"])
                if metres < 0.5:
                    return {"action": "wait"}
                model = self._model(x, y, heading, metres)
                if model["stop"] is None and model["energy"] <= spare:
                    break
            else:
                return {"action": "wait"}
        return {"action": "drive", "heading_deg": commanded, "metres": round(metres, 3)}

    def _sidestep(self, x: float, y: float, want: float) -> Dict[str, Any]:
        """Boxed in by the model: take the safest short step that does not go backwards."""
        for turn in (30, -30, 60, -60, 90, -90, 120, -120, 180):
            heading = math.degrees(want) + turn
            metres = round(2.0 / self.scale, 3)
            model = self._model(x, y, heading, metres)
            if (model["stop"] is None and self.surface.slope(model["x"], model["y"]) <= self.ground.tilt_safe
                    and self._trips_on(x, y, heading, model["ground"], self._tube()) is None):
                return {"action": "drive", "heading_deg": (heading - self.filter.bias) % 360.0,
                        "metres": min(self.max_metres, metres)}
        return {"action": "wait"}

    def _tube(self) -> float:
        """How far to either side of a drive the trip check looks: the predicted position's sigma."""
        return min(self.opt["tube_max"], self.opt["tube_share"] * self._sigma)


def fly_max(tools: Any, options: Optional[Dict[str, Any]] = None) -> MaxPilot:
    """Play the whole mission with manh_max. Returns the pilot, to look at what it believed."""
    pilot = MaxPilot(tools, options)
    while True:
        pilot.act()
        out = tools.advance(1)
        pilot.observe(out["packets"], out["current_tick"])
        if out["episode_complete"]:
            return pilot


FAST = {"plan_steps": 40000, "replan_steps": 5000, "beam": 150, "rebeam": 40}     # Kristján's pilot_fast budget
HOME = {"home_rule": True}                 # manh_max with Kristján's way-home rule

POLICIES = {
    "manh_max": lambda tools: fly_max(tools),
    "manh_max_fast": lambda tools: fly_max(tools, FAST),
    "manh_max_home": lambda tools: fly_max(tools, HOME),
    "manh_max_home_fast": lambda tools: fly_max(tools, dict(FAST, **HOME)),
    "pilot": TRAVERSE_POLICIES["pilot"],
    "pilot_fast": TRAVERSE_POLICIES["pilot_fast"],
    "greedy": TRAVERSE_POLICIES["greedy"],
    "straight": TRAVERSE_POLICIES["straight"],
    "nothing": TRAVERSE_POLICIES["nothing"],
}
