"""Scenario environment for the Manh controllers: the dynamic environment plus test factors.

Adds, on top of lightlag_dynamic.environment.DynamicEnvironment (unchanged):
  * separate sensing dials (position noise, heading bias, bias walk, heading noise, odometry
    noise), published in rules()["sensing"] like the noisy profiles;
  * exact telemetry and a truth tap, for the privileged-information bounds only;
  * candidate rule factors ("Part B" of the brainstorm), one at a time or together:
      max_metres        drive time grows with distance (metres per tick); published
      vo_by_terrain     visual-odometry noise per terrain; published
      windows           uplink only in communication windows (store and forward); published
      hidden_patches    soft sand under ground the map calls bedrock; NOT published
      slip_change       slip coefficients jump once mid-mission; that it can happen is published
      turn_cost         energy per degree of heading change; published
      packet_loss       {"p": P}: each telemetry packet is lost with probability P and never
                        arrives (the tick-0 briefing never is); published
      fix_outliers      {"p": P, "sigma": S}: with probability P a delivered position fix carries
                        an extra Gaussian error of S metres per axis; published; never applied with
                        exact telemetry (the bounds keep perfect fixes)

None of this is a rules decision: it is a test bench for controllers.
"""

import copy
import math
import random

from lightlag import Config
from lightlag.model import MAX_BATCH, decode_command
from lightlag_dynamic.environment import DynamicEnvironment
from lightlag_dynamic.missions import PROFILES, SENSING

DEFAULT_SENSING = dict(SENSING)


class _HiddenTerrainWorld:
    """The real world with extra sand patches the published map does not show."""

    def __init__(self, world, patches):
        self._w, self.patches = world, patches

    def __getattr__(self, name):
        return getattr(self._w, name)

    def terrain_at(self, x, y):
        for x1, y1, x2, y2 in self.patches:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return "sand"
        return self._w.terrain_at(x, y)


class ScenarioEnvironment(DynamicEnvironment):
    def __init__(self, seed=0, config=None, profile="noisy", sensing=None, exact_telemetry=False,
                 factors=None, noise_level=1.0, bumpiness=0.0):
        super().__init__(seed=seed, config=config, profile=profile, noise_level=noise_level,
                         bumpiness=bumpiness)
        self.factors = dict(factors or {})
        if sensing is not None:
            self._sensing = dict(sensing)
            limit = self._sensing["heading_bias_deg"]
            self._heading_bias = random.Random(f"lightlag-dynamic-heading:{seed}").uniform(-limit, limit)
            self._initial_heading_bias = self._heading_bias
        self._exact = exact_telemetry
        self._last_drive_terrains = None
        self._turn_spent = 0.0
        self._slip_changed_at = None
        self.fault_events = []
        if self.factors.get("hidden_patches"):
            self._world = _HiddenTerrainWorld(self._world, self._patches(seed, self.factors["hidden_patches"]))
        self.true_slip_initial = dict(self._slip)

    # ---- published rules ---------------------------------------------------------------
    def rules(self):
        rules = super().rules()
        if self._sensing is not None:
            rules["sensing"] = dict(self._sensing)
        f = self.factors
        if "max_metres" in f:
            rules["max_metres_per_drive"] = f["max_metres"]
        if "vo_by_terrain" in f and rules.get("sensing"):
            rules["sensing"]["visual_odometry_noise_by_terrain"] = dict(f["vo_by_terrain"])
        if "windows" in f:
            period, open_ = f["windows"]
            rules["uplink_windows"] = {"period_ticks": period, "open_ticks": open_,
                                       "rule": "an uplink sent outside a window is transmitted at the "
                                               "next window opening (store and forward)"}
        if "slip_change" in f:
            rules["slip_may_change"] = "slip coefficients may change once during the mission"
        if "turn_cost" in f:
            rules["turn_cost_per_degree"] = f["turn_cost"]
        if "packet_loss" in f:
            rules["telemetry_packet_loss"] = {"probability": f["packet_loss"]["p"],
                                              "rule": "a lost packet never arrives; later packets still do"}
        if "fix_outliers" in f:
            rules["position_fix_outliers"] = {"probability": f["fix_outliers"]["p"],
                                              "sigma_m": f["fix_outliers"]["sigma"],
                                              "rule": "an outlier fix carries an extra Gaussian error of "
                                                      "sigma_m per axis on top of the usual noise"}
        return rules

    # ---- privileged access (bounds only; never given to a real controller) ------------------
    def oracle_truth(self):
        return {"slip": dict(self._slip), "bias_rad": math.radians(self._heading_bias)}

    def true_terrain(self, x, y):
        return self._world.terrain_at(x, y)

    # ---- factors ---------------------------------------------------------------------------
    def _patches(self, seed, count):
        """Hidden sand squares (2.5 m) on the straight route from base to `count` targets."""
        rng = random.Random(f"lab-hidden:{seed}")
        bx, by = self._world.base
        targets = list(self._world.targets)
        rng.shuffle(targets)
        patches = []
        for t in targets[:count]:
            frac = rng.uniform(0.35, 0.65)
            cx, cy = bx + (t.x - bx) * frac, by + (t.y - by) * frac
            patches.append((cx - 1.25, cy - 1.25, cx + 1.25, cy + 1.25))
        return patches

    def uplink(self, commands):
        f = self.factors
        if "max_metres" not in f and "windows" not in f:
            return super().uplink(commands)
        if not isinstance(commands, list) or not 1 <= len(commands) <= MAX_BATCH:
            raise ValueError(f"commands must be a list of 1..{MAX_BATCH} commands")
        if self._tick >= self._config.max_ticks:
            raise ValueError("episode complete")
        decoded = [decode_command(c) for c in commands]
        limit = f.get("max_metres")
        if limit is not None and any(c["action"] == "drive" and c["metres"] > limit + 1e-9 for c in decoded):
            raise ValueError(f"a drive may cover at most {limit} metres per tick")
        send = self._tick
        if "windows" in f:
            period, open_ = f["windows"]
            if send % period >= open_:
                send = (send // period + 1) * period
        first = max(send + self._config.delay_ticks + 1, self._reserved_until + 1)
        if first + len(decoded) - 1 > self._config.max_ticks:
            raise ValueError("commands would execute beyond the episode horizon")
        acks = [{"command_id": len(self._sent) + i + 1, "sent_tick": self._tick,
                 "transmit_tick": send, "execute_tick": first + i, "command": c}
                for i, c in enumerate(decoded)]
        self._commands.extend(copy.deepcopy(acks))
        self._sent.extend(copy.deepcopy(acks))
        self._reserved_until = acks[-1]["execute_tick"]
        return acks

    def _step(self):
        sc = self.factors.get("slip_change")
        if sc and self._tick + 1 == sc["tick"]:
            for terrain, delta in sc["delta"].items():
                self._slip[terrain] = min(0.9, max(0.0, self._slip[terrain] + delta))
            self._slip_changed_at = self._tick + 1
        super()._step()
        self._faults(self._tick)

    def _faults(self, t):
        """Outlier fixes, then lost packets, for the packet of tick t. Seeded by (seed, tick)."""
        f = self.factors
        if not (f.get("fix_outliers") or f.get("packet_loss")) or not self._pending_packets:
            return
        packet = self._pending_packets[-1]
        out = f.get("fix_outliers")
        if out and not self._exact and random.Random(f"scenario-outlier:{self._seed}:{t}").random() < out["p"]:
            rng = random.Random(f"scenario-outlier-xy:{self._seed}:{t}")
            x, y = packet["position"]
            x = min(self._world.width, max(0.0, x + rng.gauss(0.0, out["sigma"])))
            y = min(self._world.height, max(0.0, y + rng.gauss(0.0, out["sigma"])))
            self._pending_packets[-1] = {**packet, "position": [round(x, 10), round(y, 10)]}
            self.fault_events.append({"tick": t, "fault": "fix_outlier"})
        loss = f.get("packet_loss")
        if loss and random.Random(f"scenario-loss:{self._seed}:{t}").random() < loss["p"]:
            self._pending_packets.pop()
            self.fault_events.append({"tick": t, "fault": "packet_lost"})

    def _drive(self, command, events):
        start = self._world.terrain_at(self._x, self._y)
        cost = self.factors.get("turn_cost")
        if cost:
            turn = abs((command["heading_deg"] - self._heading + 180.0) % 360.0 - 180.0)
            spend = cost * turn * self._config.drive_cost * (2.0 if start == "sand" else 1.0)
            self._spend(spend)
            self._turn_spent += spend
        result = super()._drive(command, events)
        self._last_drive_terrains = (self._tick, start, self._world.terrain_at(self._x, self._y))
        return result

    def _measured(self, packet):
        if self._exact:
            return packet
        by_terrain = self.factors.get("vo_by_terrain")
        if by_terrain and self._last_drive_terrains and self._last_drive_terrains[0] == packet["tick"]:
            _, a, b = self._last_drive_terrains
            saved = self._sensing["visual_odometry_noise"]
            self._sensing["visual_odometry_noise"] = (by_terrain[a] + by_terrain[b]) / 2
            try:
                return super()._measured(packet)
            finally:
                self._sensing["visual_odometry_noise"] = saved
        return super()._measured(packet)

    def scenario_replay(self):
        replay = self.replay()
        replay["scenario"] = {"factors": self.factors, "true_slip_initial": self.true_slip_initial,
                              "true_slip_final": dict(self._slip), "slip_changed_at": self._slip_changed_at,
                              "turn_energy": self._turn_spent, "fault_events": list(self.fault_events),
                              "hidden_patches": getattr(self._world, "patches", None)}
        return replay


def make_env(seed, delay, profile="noisy", horizon=None, **kw):
    horizon = PROFILES[profile][4] if horizon is None else horizon
    return ScenarioEnvironment(seed=seed, config=Config(delay_ticks=delay, max_ticks=horizon),
                               profile=profile, **kw)
