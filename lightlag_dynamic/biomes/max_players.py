"""The max-env controller (maxenv.py): the fusing particle filter under controller 37's planning
layers, with what the max env adds to estimate and to plan for (needs numpy).

    max_navigator()(PublicTools(make_max_env(seed=7, delay=3))).run()

The fusing reference (`fused`, nogps_players.py) knows the many weak sensors. In the max env it
also meets lost packets, wild position fixes, crust over soft sand, an onboard slip check, dune
faces, relay passes and wheels of a hidden size. This player adds:

  estimation (MaxParticleFilter and _MaxNavigator)
    lost packets     before a packet is filtered, every acknowledged drive that executed in the
                     ticks of lost packets is predicted with its commanded metres (controller 35's
                     bridging, on particles)
    wild fixes       the published outlier probability and size make the fix likelihood a mixture,
                     so one wild fix cannot drag the estimate (a robust likelihood instead of 35's
                     chi-square gate, which a particle filter does not need)
    crust            inside a published crust region a "sand" terrain reading is expected about
                     soft_rate of the time, so map matching does not push the rover out of the crust
    battery scale    the battery reading has no noise, and a drive on mapped bedrock spends
                     drive_cost x wheel_scale x the reported wheel metres, plus the published turn
                     cost: the first clean bedrock drive gives the wheel scale exactly

  planning (controller 37's layers that do not need its Kalman filter, on the particle filter)
    the slip-check layer and executive (Hidden Valley), guarded moves when a probe is free and
    stay-alive, uplink windows, aim at the disc, turn cost, with these changes:
    dunes are traps  with dune faces, mapped sand trips the slip check on almost every face, so the
                     layer is told so and drops a target that only dune sand reaches (_SandTraps)
    true-slip trips  the trip chance comes from the filter's slip particles, not from the effective
                     slip the planner sees, which folds in the wheel scale (_SandTraps)
    no confirm wait  every leg ends with a sample attempt: waiting to see the landing costs a round
                     trip plus a closed relay pass, a missed attempt one tick and the sampling energy
    reserve 5        energy kept at the horizon: the plan prices every leg's first turn at 90
                     degrees and cannot see soft cells, and with the reserve of 1 greedy missions
                     died at base
    long back-outs   0.6 m back-out drives instead of 0.1 m steps (_QuickEscape)

Development runs (seeds 0-59 and 1100-1299, delay 3) and the fresh check are in
docs/lightlag-biomes.md. A sandbox player for a stress test, not a rules decision or a registered
Manh controller.
"""

import numpy as np

from lightlag_dynamic.manh_controllers import controllers as zoo
from lightlag_dynamic.manh_controllers.mars import executive

from .nogps_players import SENSORS, NavParticleFilter, _executed_drive, _Navigator


class MaxParticleFilter(NavParticleFilter):
    outlier_p = 0.0       # published chance that a fix is wild
    outlier_sigma = 0.0   # ... and its extra error, metres per axis
    crust = None          # published crust regions, rows x1 y1 x2 y2
    soft_rate = 0.0
    scale_known = False

    def update_position(self, z):
        if self.outlier_p <= 0:
            return super().update_position(z)
        d2 = (z[0] - self.x) ** 2 + (z[1] - self.y) ** 2
        v1 = self.sig_pos ** 2
        v2 = v1 + self.outlier_sigma ** 2
        likelihood = ((1.0 - self.outlier_p) / v1 * np.exp(-d2 / (2.0 * v1))
                      + self.outlier_p / v2 * np.exp(-d2 / (2.0 * v2)))
        self.logw += np.log(likelihood + 1e-300)
        self._normalise()

    def in_crust(self, x, y):
        if self.crust is None or not len(self.crust):
            return np.zeros(len(x), bool)
        c = self.crust
        return ((x[:, None] >= c[None, :, 0]) & (x[:, None] <= c[None, :, 2])
                & (y[:, None] >= c[None, :, 1]) & (y[:, None] <= c[None, :, 3])).any(axis=1)

    def update_terrain(self, reported, miss=0.05):
        if self.crust is None or not len(self.crust):
            return super().update_terrain(reported, miss)
        on_sand = self._terrain(self.x, self.y) == 1
        p_sand = np.where(on_sand, 1.0 - miss, np.where(self.in_crust(self.x, self.y), max(self.soft_rate, miss), miss))
        p = p_sand if reported == "sand" else 1.0 - p_sand
        self.logw += np.log(np.maximum(p, 1e-12))
        self._normalise()

    def set_scale(self, scale):
        """The wheel scale is known: every particle takes it."""
        if self.g is not None:
            self.g = np.full(self.n, float(scale) - 1.0)
            self.scale_known = True


class _MaxNavigator(_Navigator):
    PF_CLASS = MaxParticleFilter
    BRIDGE = True
    BATTERY_SCALE = True
    COMMIT_BELOW = 0.0    # a leg waits to be confirmed only below this chance (None: the base rule)

    def needs_confirmation(self, leg):
        if self.COMMIT_BELOW is None:
            return super().needs_confirmation(leg)
        return self._end_inside(leg, self.radius) < self.COMMIT_BELOW

    def _made_pf(self, rules):
        pf = self.pf
        wild = rules.get("position_fix_outliers") or {}
        pf.outlier_p, pf.outlier_sigma = float(wild.get("probability", 0.0)), float(wild.get("sigma_m", 0.0))
        regions = self.tools.map().get("crust_regions") or []
        pf.crust = np.array([[r["x1"], r["y1"], r["x2"], r["y2"]] for r in regions], float).reshape(-1, 4)
        pf.soft_rate = float((rules.get("crust") or {}).get("soft_rate", 0.0))
        self._turn_cost_rule = float(rules.get("turn_cost_per_degree") or 0.0)
        self._seen_tick = 0
        self.bridged = 0

    def _filter(self, packet):
        if hasattr(self, "pf") and self.BRIDGE:
            self._bridge(packet)
        super()._filter(packet)
        if hasattr(self, "pf"):
            self._seen_tick = packet["tick"]
            if self.BATTERY_SCALE:
                self._battery_scale(packet)

    def _bridge(self, packet):
        """Predict the drives that executed in the ticks of lost packets, with their commanded metres."""
        by_tick = {a["execute_tick"]: a for a in self.acks}
        for t in range(self._seen_tick + 1, packet["tick"]):
            a = by_tick.get(t)
            if a and a["command"]["action"] == "drive" and a["command_id"] not in self.cancelled:
                self.pf.predict(a["command"]["heading_deg"], a["command"]["metres"])
                self.bridged += 1

    def _battery_scale(self, packet):
        pf = self.pf
        if pf.g is None or pf.scale_known or len(self.packets) < 2:
            return
        prev = self.packets[-2]
        drive = _executed_drive(self, packet)
        if drive is None or not drive[2] or packet["tick"] != prev["tick"] + 1 or not packet["alive"]:
            return
        heading, wheel, _ = drive
        if wheel < 0.5 or prev.get("terrain") != "bedrock" or packet.get("terrain") != "bedrock":
            return
        if pf.last_by is None or float(pf.weights() @ pf.last_by[:, 1]) > 0.01:
            return  # some of the drive may have been on mapped sand
        if float(pf.weights() @ pf.in_crust(pf.x, pf.y)) > 0.01:
            return  # a crust region may hide soft sand along it
        energy = prev["battery"] - packet["battery"] - self.idle
        if self._turn_cost_rule and prev.get("heading_deg") is not None:
            turn = abs((heading - prev["heading_deg"] + 180.0) % 360.0 - 180.0)
            energy -= self._turn_cost_rule * turn * self.drive_cost * self.multiplier["bedrock"]
        scale = energy / (self.drive_cost * self.multiplier["bedrock"] * wheel)
        if abs(scale - 1.0) <= pf.scale_error + 1e-6:
            pf.set_scale(scale)
            self.wheel_scale = (scale, 0.0)
            self.scale_from_battery = (packet["tick"], scale)


class _SandTraps:
    """Trip chances for the slip-check layer of the executive.

    With dune faces in the rules, mapped sand is a trap. A face slips the hidden sand coefficient
    plus slip_per_degree x its slope, above the limit on almost every face, and from a step that
    trips every later drive trips at its first 0.1 m step and empties the queue: the rover moves
    about 5 cm per uplink for the rest of the mission. So sand trips with at least DUNE_TRIP, and
    the layer routes around it and drops a target that only sand reaches, instead of learning it
    from a stop it cannot leave.

    The trip chance itself comes from the particle filter's own slip particles. The planner is
    handed the effective slip, which folds in the wheel scale and is below zero for big wheels; the
    slip check sees the true slip. Read as a true slip, an effective one the filter is sure of lies
    far outside the published range, and the base rule then takes bedrock as certain to trip and
    drops targets on it (late in some missions with big wheels)."""
    SAND_TRAP = True
    DUNE_TRIP = 0.9
    RAW_TRIP = True

    def trip_chance(self, terrain):
        pf = getattr(self, "pf", None)
        if self.RAW_TRIP and pf is not None and pf.g is not None:
            chance = self._particle_trip_chance(terrain)
        else:
            chance = super().trip_chance(terrain)
        if self.SAND_TRAP and terrain == "sand" and self._dune_faces():
            return max(chance, self.DUNE_TRIP)
        return chance

    def _particle_trip_chance(self, terrain):
        """The base rule's Bayes update on the particles: each stop seen on the terrain weighs a
        particle by its chance q(s) to trip; the trip chance is the mean of q under that belief."""
        pf, n, limit = self.pf, self.slip_noise, self.slip_limit
        s = pf.s[:, pf.terrains.index(terrain)]
        q = np.clip((s - (limit - n)) / (2 * n), 0.0, 1.0)
        w = pf.weights() * q ** self.stops.get(terrain, 0)
        total = float(w.sum())
        return float(w @ q) / total if total > 1e-300 else 1.0  # a stop the belief ruled out: assume the worst

    def _dune_faces(self):
        if "_faces" not in self.__dict__:
            self._faces = self.tools.map().get("dune_faces") or []
        return self._faces


class _QuickEscape:
    """Leaves a slip trap with longer back-out drives than the executive's one 0.1 m step. The slip
    noise is drawn once per drive, so on the trap a drive either trips at its first step, moving as
    far as the one-step drive would, or does not trip at all and leaves along its own tracks at once.
    Under relay passes each back-out drive costs a whole pass (8 ticks)."""
    ESCAPE_METRES = 0.6

    def decide(self):
        if (getattr(self, "mode", None) != "recover" or self.ESCAPE_METRES <= self.segment
                or self.backouts >= self.backout_steps + 1):
            return super().decide()
        live = max((a["execute_tick"] for a in self.acks if a["command_id"] not in self.cancelled), default=0)
        if self.tick < live:
            return  # a stop of the queued drive would discard anything sent now
        if self.send([{"action": "drive", "heading_deg": round(self.backout_heading, 6),
                       "metres": self.ESCAPE_METRES}]):
            self.backouts += 1


class PF_c37_planner(zoo._ArmedGuard, zoo._WindowAware, zoo._AimDisc, zoo._TurnCost, zoo._Unverified, zoo.PF_MPC):
    """Controller 37's planning stack on the zoo's particle filter (its Kalman-only estimator
    layers, the gate, fading and the sand-aware propagation, are left out)."""


def _planner():
    # EVIDENCE_TO_DROP off: a target that only trap terrain reaches is dropped on the trip chance,
    # before a stop has shown it (with dune faces, sand is known to trip).
    return type("PF_c37_planner_exec", (zoo._RulesOnce, zoo._ReserveByEvidence, executive(PF_c37_planner)),
                {"RESERVE_CLEAN": 5.0, "EVIDENCE_TO_DROP": False})


def max_navigator(use=SENSORS, layers=True, **knobs):
    """The max-env controller class. `layers=False`: the fusing reference's planner instead of 37's
    (no slip-check layer, the stock reserve), for comparison."""
    base = _planner() if layers else zoo.PF_aimdisc_turncost_window_MPC
    name = "MaxNavigator" + ("" if layers else "_plain")
    return type(name, (_QuickEscape, _SandTraps, _MaxNavigator, base), {"USE": frozenset(use), **knobs})
