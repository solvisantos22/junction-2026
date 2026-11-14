"""Mars-operations tweaks for the scenario environment: small, realistic, switchable, reversible.

Each tweak is one factor in `factors`, published in rules() like the others, and off unless
named. Each comes from how Curiosity and Perseverance are actually driven:

  slip_check       {"limit": L}   Onboard fault protection. When the slip of a drive step exceeds
                                  L, the rover stops the drive and discards its queued commands, as
                                  the real rovers do when visual odometry measures too much slip
                                  (Curiosity turned back from Hidden Valley's sand in 2014 this way).
                                  Telemetry reports a safety_stop with reason "slip_limit".
  downlink_passes  {"period": P}  Telemetry is relayed by orbiters at passes, not continuously: a
                                  packet arrives at the first pass (a multiple of P ticks) at or after
                                  tick + delay_ticks. P = 1 is the unchanged environment.

The lab protocol is one tweak at a time, at its mildest setting first, measured on the
controllers and the baselines; a tweak that makes the best controller much worse, or shrinks
the gap between it and the baselines, is reverted or softened. Settings that passed (fresh
seeds 800-879, delay 3): slip_check 0.45 everywhere, 0.40-0.42 on the 50-tick rush profiles
only; downlink_passes period 2. None of this is a rules decision. Results and what was
reverted: docs/lightlag-dynamic-pilot.md, section "Mars-operations tweaks".

Co-designed controllers (proposals; registered as Manh controllers 30-33): `slip_aware(parent)` plans around the
check; `executive(parent)` adds explicit modes on top (nominal / recover after a slip stop).

    env = make_mars_env(seed, 3, "rush_noisy", factors={"slip_check": {"limit": 0.40}})
    policies()["executive_c24"](PublicTools(env)).run()   # controller 24 + layer + executive
"""

import math
import random

from lightlag import Config, Environment
from lightlag.model import NOISE, SEGMENT_METRES, TERRAIN_COSTS
from lightlag_dynamic.missions import PROFILES

from .scenarios import ScenarioEnvironment

MARS_FACTORS = ("slip_check", "downlink_passes")


class _SlipCheckDrive(Environment):
    """The team's drive loop (lightlag.Environment._drive) with an optional slip check.

    It sits below DynamicEnvironment in the class order, so heading drift and the scenario
    factors still apply first. Line for line with the parent where they overlap; a test checks
    that with the check off (or never tripping) the episode is identical to the parent's.
    """

    def _drive(self, command, events):
        limit = (getattr(self, "factors", None) or {}).get("slip_check", {}).get("limit")
        if limit is None:
            return super()._drive(command, events)
        self._heading = command["heading_deg"]
        radians = math.radians(self._heading)
        cardinal = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}
        dx, dy = cardinal.get(self._heading, (math.cos(radians), math.sin(radians)))
        noise = random.Random(f"{self._seed}:drive:{self._tick}").uniform(-NOISE, NOISE)
        remaining = command["metres"]
        wheel, visual = 0.0, 0.0
        while remaining > 1e-10 and self._battery > 0:
            terrain = self._world.terrain_at(self._x, self._y)
            cost = self._config.drive_cost * TERRAIN_COSTS[terrain]
            segment = min(SEGMENT_METRES, remaining, self._battery / cost)
            slip = min(0.9, max(0.0, self._slip[terrain] + noise))
            distance = segment * (1 - slip)
            next_x, next_y = self._x + dx * distance, self._y + dy * distance
            if not (0 <= next_x <= self._world.width and 0 <= next_y <= self._world.height):
                events.append({"type": "safety_stop", "reason": "map_boundary"})
                self._commands.clear()
                break
            if any(region.intersects_segment(self._x, self._y, next_x, next_y)
                   for region in self._world.hazards):
                events.append({"type": "safety_stop", "reason": "hazard"})
                self._commands.clear()
                break
            self._x, self._y = next_x, next_y
            self._spend(segment * cost)
            wheel += segment
            visual += distance
            remaining -= segment
            if slip > limit:  # the step that measured it still happened; the rest of the queue does not
                events.append({"type": "safety_stop", "reason": "slip_limit"})
                self._commands.clear()
                self._slip_trips += 1
                break
        return wheel, visual


class MarsEnvironment(ScenarioEnvironment, _SlipCheckDrive):
    def __init__(self, *args, **kwargs):
        self._slip_trips = 0
        super().__init__(*args, **kwargs)
        unknown = set(self.factors) - set(MARS_FACTORS) - _SCENARIO_FACTORS
        if unknown:
            raise ValueError(f"unknown factors: {sorted(unknown)}")

    def rules(self):
        rules = super().rules()
        f = self.factors
        if "slip_check" in f:
            rules["onboard_slip_check"] = {
                "limit": f["slip_check"]["limit"],
                "rule": "if a drive step slips more than the limit, the rover stops that drive and "
                        "discards every queued command; telemetry reports safety_stop / slip_limit"}
        if "downlink_passes" in f:
            rules["downlink_passes"] = {
                "period_ticks": f["downlink_passes"]["period"],
                "rule": "telemetry is relayed at orbiter passes: a packet describing tick t arrives at "
                        "the first pass (a multiple of period_ticks) at or after t + delay_ticks"}
        return rules

    def _snapshot(self, wheel, visual, events):
        packet = super()._snapshot(wheel, visual, events)
        factors = getattr(self, "factors", None) or {}  # the parent builds the launch packet first
        period = factors.get("downlink_passes", {}).get("period", 1)
        if period > 1:
            packet["received_tick"] = int(math.ceil(packet["received_tick"] / period) * period)
        return packet

    def scenario_replay(self):
        replay = super().scenario_replay()
        replay["scenario"]["slip_trips"] = self._slip_trips
        return replay


_SCENARIO_FACTORS = {"max_metres", "vo_by_terrain", "windows", "hidden_patches", "slip_change", "turn_cost"}


def make_mars_env(seed, delay, profile="rush_noisy", horizon=None, **kw):
    horizon = PROFILES[profile][4] if horizon is None else horizon
    return MarsEnvironment(seed=seed, config=Config(delay_ticks=delay, max_ticks=horizon),
                           profile=profile, **kw)


# =============================================================================================
# Controllers co-designed with the tweaks (registered in controllers.py as 30-33)
# =============================================================================================

class _SlipCheckAware:
    """Plans around the onboard slip check, as the Curiosity team did after Hidden Valley.

    Inactive when the rules publish no slip check: then every decision is the parent's.
    With a check of limit L, each terrain has a trip chance: the chance that the next drive on
    it slips more than L. The slip s is the filter's estimate (mean and spread, truncated to the
    published range); a drive slips s + u, u uniform in the published +-noise, so it trips with
    q(s) = P(u > L - s). Every stop seen on the terrain multiplies the belief over s by q(s)
    (Bayes), and the trip chance is the mean of q under that belief. Then
      * ROUTE_ABOVE: routes pay AVOID energy per metre of a terrain whose chance exceeds this,
        so the planner goes around it, or leaves it by the shortest way;
      * DROP_ABOVE: a target that can only be reached through a terrain whose chance exceeds
        this is not planned for: each stop flushes the queue and costs a round trip, and inside
        such terrain the rover is stopped every 0.1 m.
    Tuned on development seeds 0-39 (rush_noisy and noisy, delay 3); results and what did not
    work (charging legs their expected delay instead of dropping) in the lab note.
    """
    AVOID = 25.0
    ROUTE_ABOVE = 0.10
    DROP_ABOVE = 0.30
    GRID = 60

    def __init__(self, tools):
        rules = tools.rules()
        self.slip_limit = (rules.get("onboard_slip_check") or {}).get("limit")
        self.slip_noise = max(abs(v) for v in rules["slip_noise"])
        self.segment = rules["drive_integration_metres"]
        self.stops = {}
        self._avoid_now, self._through = set(), {}
        super().__init__(tools)

    # ---- knowledge ----
    def absorb(self, packet):
        super().absorb(packet)
        if self.slip_limit is not None and any(e["type"] == "safety_stop" and e.get("reason") == "slip_limit"
                                               for e in packet["events"]):
            # The stopping step may have just left the terrain that tripped: blame one that can.
            for terrain in (self.terrain_at(*packet["position"]), self.terrain_at(*self.packets[-2]["position"])):
                if self.slip_ranges[terrain][1] + self.slip_noise > self.slip_limit:
                    self.stops[terrain] = self.stops.get(terrain, 0) + 1
                    break

    def trip_chance(self, terrain):
        f = getattr(self, "filter", None)
        mean, sigma = (f.slip(terrain), f.slip_sigma(terrain)) if f is not None else \
            (self.slip(terrain), self.slip_spread(terrain))
        lo, hi = self.slip_ranges[terrain]
        n, limit, stops = self.slip_noise, self.slip_limit, self.stops.get(terrain, 0)
        num = den = 0.0
        for i in range(self.GRID):
            slip = lo + (hi - lo) * (i + 0.5) / self.GRID
            q = min(1.0, max(0.0, (slip - (limit - n)) / (2 * n)))
            w = math.exp(-0.5 * ((slip - mean) / max(sigma, 1e-3)) ** 2) * q ** stops
            num, den = num + w * q, den + w
        return num / den if den > 1e-300 else 1.0  # a stop the belief ruled out: assume the worst

    # ---- planning ----
    def _energy(self, bed, sand, slip_of):
        energy = super()._energy(bed, sand, slip_of)
        avoid = self._avoid_now
        if avoid:  # only while routing
            energy += self.AVOID * (sand * ("sand" in avoid) + bed * ("bedrock" in avoid))
        return energy

    def route(self, a, b):
        if self.slip_limit is None:
            return super().route(a, b)
        chances = {t: self.trip_chance(t) for t in self.slip_ranges}
        self._avoid_now = {t for t, c in chances.items() if c > self.ROUTE_ABOVE}
        try:
            path = super().route(a, b)
        finally:
            self._avoid_now = set()
        for p, q in zip(path or [], (path or [])[1:]):
            _, bed, sand = self._segment(p, q)
            for t, metres in (("sand", sand), ("bedrock", bed)):
                if metres > 0.05:
                    self._through[t] = max(self._through.get(t, 0.0), chances[t])
        return path

    def leg(self, start, goal):
        self._through = {}
        hop = super().leg(start, goal)
        if (hop is not None and self.slip_limit is not None
                and any(self._drops(t, c) for t, c in self._through.items())
                and math.dist(goal, self.base) > self.base_radius):
            return None  # only reachable through terrain that keeps tripping the check
        return hop

    def _drops(self, terrain, chance):
        return chance > self.DROP_ABOVE

    def can_trip(self, terrain):
        return self.slip_ranges[terrain][1] + self.slip_noise > self.slip_limit


class _Executive(_SlipCheckAware):
    """A small executive on top of the slip-check-aware MPC: explicit modes, switched by
    telemetry events, like the rovers' fault protection or a behaviour tree's fallback node.

        nominal --slip_limit stop, and backing out is expected to be quicker--> recover
        recover --telemetry puts the rover on terrain that cannot trip, or the planned
                  back-out steps are all sent--> nominal

    recover backs out with one-segment drives, each uplinked only once the previous one has
    executed, so a stop cannot discard it: n steps cost n (delay + 1) ticks. Driving on instead
    costs one round trip (2 delay + 1 ticks) per stop, p / (1 - p) stops on average with trip
    chance p. Recover when n (delay + 1) is the smaller cost. Which way and how far:
      * the stopped drive started outside: the slip noise is drawn once per drive, so it
        stopped at its first step inside, at most two steps deep; back out along its own
        tracks (the reverse of its heading), two steps;
      * it started inside (it may have gone metres in, often along the edge): out through the
        nearest edge of the patch on the map, as deep as the position estimate is inside it
        plus one standard deviation, corrected for the estimated heading bias.
    In nominal the MPC plans as before, except EVIDENCE_TO_DROP: a target is dropped only once
    there is evidence about the terrain (a stop seen on it, or a slip estimate whose spread is
    below EVIDENCE_SIGMA). Before that, going for it is the cheapest probe.
    Inactive without a published slip check. Switches are logged in mode_log.
    """
    EVIDENCE_SIGMA = 0.03
    EVIDENCE_TO_DROP = True

    def __init__(self, tools):
        self.mode, self.mode_log = "nominal", []
        self.backout_heading, self.backouts, self.backout_steps = None, 0, 0
        super().__init__(tools)

    def _switch(self, mode, reason):
        self.mode_log.append((self.tick, mode, reason))
        self.mode = mode

    # ---- events ----
    def absorb(self, packet):
        super().absorb(packet)
        if self.slip_limit is None:
            return
        stopped = any(e["type"] == "safety_stop" and e.get("reason") == "slip_limit" for e in packet["events"])
        heading = self._stopped_heading(packet) if stopped and self.mode != "recover" else None
        if heading is not None and self.can_trip(packet["terrain"]):
            back, steps = self._way_out(packet, heading)
            chance = self.trip_chance(packet["terrain"])
            drive_on = (2 * self.k + 1) * chance / max(1e-9, 1.0 - chance)
            if steps * (self.k + 1) < drive_on:
                self.backout_heading, self.backouts, self.backout_steps = back, 0, steps
                self._switch("recover", f"slip stop at tick {packet['tick']}: {steps} steps back "
                                        f"({steps * (self.k + 1)} ticks) vs driving on ({drive_on:.0f})")
        elif self.mode == "recover" and not self.can_trip(packet["terrain"]):
            self._switch("nominal", f"on {packet['terrain']} at tick {packet['tick']}")

    def _way_out(self, packet, heading):
        """(commanded heading, steps) to leave the terrain the rover was stopped on."""
        step = self.segment * (1.0 - self.slip(packet["terrain"]))  # ground covered by one step inside
        if not self.can_trip(self.packets[-2]["terrain"]):
            return (heading + 180.0) % 360.0, 2  # started outside: back along its own tracks
        # Started inside: leave by the nearest edge. If the estimate is outside every patch while
        # telemetry says inside, the rover is just inside the nearest one: leave toward the estimate.
        f = getattr(self, "filter", None)
        x, y = (f.mean[0], f.mean[1]) if f is not None else packet["position"]
        sigma = math.sqrt(max(f.cov[0][0], f.cov[1][1])) if f is not None else 0.0
        bias = math.degrees(f.mean[2]) if f is not None else 0.0
        inside, near = [], []
        for r in self.sand:
            if r["x1"] <= x <= r["x2"] and r["y1"] <= y <= r["y2"]:
                inside += [(x - r["x1"], 180.0), (r["x2"] - x, 0.0), (y - r["y1"], 270.0), (r["y2"] - y, 90.0)]
            else:
                cx, cy = min(max(x, r["x1"]), r["x2"]), min(max(y, r["y1"]), r["y2"])
                near.append((math.hypot(x - cx, y - cy), math.degrees(math.atan2(y - cy, x - cx))))
        if inside:
            depth, direction = min(inside)
        elif near:
            depth, direction = 0.0, min(near)[1]
        else:
            return (heading + 180.0) % 360.0, 2
        return (direction - bias) % 360.0, int(math.ceil((depth + sigma) / max(step, 1e-3)))

    def _stopped_heading(self, packet):
        acks = {a["command_id"]: a for a in self.acks}
        for event in packet["events"]:
            ack = acks.get(event.get("command_id")) if event["type"] == "command_executed" else None
            if ack is not None and ack["command"]["action"] == "drive":
                return ack["command"]["heading_deg"]
        return None

    # ---- acting ----
    def ready(self):
        if self.mode == "recover":
            return self.packets[-1]["alive"]
        return super().ready()

    def decide(self):
        if self.mode != "recover":
            return super().decide()
        if self.backouts >= self.backout_steps + 1:
            self._switch("nominal", "back-out steps sent")
            return super().decide()
        live = max((a["execute_tick"] for a in self.acks if a["command_id"] not in self.cancelled), default=0)
        if self.tick < live:
            return  # a stop of the queued drive would discard anything sent now
        if self.send([{"action": "drive", "heading_deg": round(self.backout_heading, 6), "metres": self.segment}]):
            self.backouts += 1

    def _drops(self, terrain, chance):
        if not self.EVIDENCE_TO_DROP:
            return super()._drops(terrain, chance)
        f = getattr(self, "filter", None)
        known = self.stops.get(terrain) or (f is not None and f.slip_sigma(terrain) < self.EVIDENCE_SIGMA)
        return bool(known) and super()._drops(terrain, chance)


def slip_aware(parent):
    """`parent` (a KalmanMPCController subclass) with the slip-check layer on top."""
    return type(f"SlipAware_{parent.__name__}", (_SlipCheckAware, parent), {})


def executive(parent, **knobs):
    """`parent` with the slip-check layer and the executive on top."""
    return type(f"Executive_{parent.__name__}", (_Executive, parent), dict(knobs))


def policies():
    """Controllers 1 and 24 with the layer, and with the executive; imported lazily (the zoo is large)."""
    from . import controllers as zoo
    c1, c24 = zoo.EKF_MPC, zoo.EKF_sandodo_stayalive_aimdisc_turncost_window_MPC
    return {"slip_aware_c1": slip_aware(c1), "slip_aware_c24": slip_aware(c24),
            "executive_c1": executive(c1), "executive_c24": executive(c24)}
