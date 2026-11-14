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

    env = make_mars_env(seed, 3, "rush_noisy", factors={"slip_check": {"limit": 0.40}})
    policies()["slip_aware_c1"](PublicTools(env)).run()   # controller 1 + the slip-check layer
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
# Controllers co-designed with the tweaks (experimental; not in the registry)
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
                and max(self._through.values(), default=0.0) > self.DROP_ABOVE
                and math.dist(goal, self.base) > self.base_radius):
            return None  # only reachable through terrain that keeps tripping the check
        return hop


def slip_aware(parent):
    """`parent` (a KalmanMPCController subclass) with the slip-check layer on top."""
    return type(f"SlipAware_{parent.__name__}", (_SlipCheckAware, parent), {})


def policies():
    """Controllers 1 and 24 with the layer; imported lazily (the zoo is large)."""
    from . import controllers as zoo
    return {"slip_aware_c1": slip_aware(zoo.EKF_MPC),
            "slip_aware_c24": slip_aware(zoo.EKF_sandodo_stayalive_aimdisc_turncost_window_MPC)}
