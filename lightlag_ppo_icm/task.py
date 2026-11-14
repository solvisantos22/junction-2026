"""The mission as a decision process for a learning agent, through the five public tools only.

    task = RoverTask(PublicTools(env))
    task.play(choose)            # choose(observation) -> action number, once per command slot

One decision fills one execution slot. A command sent at tick t runs at t + delay + 1 at the
earliest, one command per tick, and a slot that is not filled in time stays empty. So at every
tick the adapter asks for exactly the slots that can no longer wait: one per tick on an open
link, and all the slots up to the next relay pass on the last tick before the link closes. The
agent therefore decides every slot once, with the latest telemetry there can be for it.

Observation (TaskConfig.obs_dim numbers, all from rules(), map(), telemetry and the agent's own
acknowledged commands): the state the rover is expected to be in when the slot runs (belief.py
carried through the commands still on their way), then

    23  mission clock, battery, age and spread of the belief, the gain it has learned, ground
        under the rover, stops seen and expected, the link, the previous command, how many
        targets are open and the share of the known value already sampled
     7  the base: direction, distance, and the time and energy margins for getting home
    10  per open target, nearest first: direction, distance, in sampling range, value, what a
        sample is worth if driven to now, slack to the deadline
     3  per heading: how far to a stop (hazard, map edge, too steep), to soft ground and to
        ground the map marks as risky, out to two full drives

Actions: wait, sample, or drive at one of `headings` compass headings for a quarter, a half or
all of the longest drive the rules allow.

One safety rule sits between the agent and the uplink (TaskConfig.guard, on by default): a
command that the published numbers say would empty the battery before the horizon is not sent;
a wait goes in its place. Without it an untrained agent drives the battery flat in almost every
episode, a dead rover scores 0 whatever it sampled, and there is nothing to learn from. What to
spend the energy on, and whether to keep enough of it to come home, is still the agent's to learn.

A second rule is optional (TaskConfig.home_guard, off by default; flat 40 m family only): the home
guard. Before a command is sent it looks at where the command leaves the rover. If from there the
way home (home.py: around hazards, and around ground that can stop a drive when that is cheap)
would no longer fit, the guard sends its own command instead: the next drive of the way home, or
a wait at the base. "Fit" means energy and time. Energy: what the battery guard would charge for
every drive home (the dearest ground, the biggest wheels), the turns, the idle drain to the horizon
and one unit to spare. Time: the drives home plus two slots, and, for a drive that can be stopped
where the map does not expect it (soft or risky ground, close past a hazard), the slots a stop can
cost on top. Sand that trips the onboard slip check stops every step on it and moves the rover about
6 cm per round trip of the link, so where the published slip range of sand reaches over the check,
and elsewhere once telemetry reports a stop by it, the guard keeps the rover off sand: the way home
keeps clear of it where it can, a drive onto it is replaced, and a rover on it is driven off it.
With the guard on, the observation's two margins for getting home are the guard's own: how much
time and energy is left before it takes over. What to spend the rest on is the agent's.

Reward: the official score, cut into pieces so that the rewards of an episode add up to
raw_score / max_available_value exactly: half of each sample's credited value when it is taken,
and at the last decision the rest (plus the other half at base, minus it if the rover died).

Optional (rewards(..., home_pull=k)): the half that being home is worth is paid out along the
way instead of only at the end. With the potential

    phi = k * 1/2 * (value sampled so far / all value) * D / (D + distance to base),   D = 8 base radii

each decision also gets phi(next) - phi(now), and the last one gives phi back. The pieces still
add up to the official score (the potential starts and ends at 0), and no policy becomes better or
worse by it (Ng, Harada and Russell 1999); it only tells the agent sooner. k = 1 is exactly the
bonus for being home; a larger k pulls harder and takes more back at the end. Distance and value
are the adapter's own belief, not the evaluator's truth.
"""

from dataclasses import dataclass
import math

import numpy as np

from .belief import Belief
from .ground import make_ground
from .home import HomeField

GLOBAL, BASE, PER_TARGET, PER_HEADING = 23, 7, 10, 3
WAIT, SAMPLE, FIRST_DRIVE = 0, 1, 2
GATE = 9.21   # 99% of a chi-square with two degrees of freedom: a fix further out is held back


@dataclass(frozen=True)
class TaskConfig:
    headings: int = 16
    metres: tuple = (0.25, 0.5, 1.0)   # shares of the longest drive the rules allow
    targets: int = 6                   # open targets in the observation, nearest first
    ray_reach: float = 2.0             # the view reaches this many full drives
    guard: bool = True                 # replace a command that would empty the battery by a wait
    home_guard: bool = False           # keep the energy and time to get home; drive home when they run out

    @property
    def n_actions(self):
        return FIRST_DRIVE + self.headings * len(self.metres)

    @property
    def obs_dim(self):
        return GLOBAL + BASE + self.targets * PER_TARGET + PER_HEADING * self.headings

    @property
    def curiosity_inputs(self):
        """The observation entries the curiosity module sees: the clock, the battery, the ground
        under the rover, whether it is alive, how many targets are open, the value sampled so far,
        then the base, the targets and the view. Left out: the previous command and the last
        heading (echoes of the agent's own action), and the adapter's bookkeeping about the link,
        stops and the belief, which jumps for reasons that are not worth being curious about."""
        return (0, 1, 6, 7, 12, 21, 22) + tuple(range(GLOBAL, self.obs_dim))

    def to_dict(self):
        return {"headings": self.headings, "metres": list(self.metres), "targets": self.targets,
                "ray_reach": self.ray_reach, "guard": self.guard, "home_guard": self.home_guard}

    @classmethod
    def from_dict(cls, data):
        return cls(headings=int(data["headings"]), metres=tuple(float(m) for m in data["metres"]),
                   targets=int(data["targets"]), ray_reach=float(data["ray_reach"]),
                   guard=bool(data.get("guard", True)), home_guard=bool(data.get("home_guard", False)))


def _wrap(degrees):
    return (degrees + 180.0) % 360.0 - 180.0


class RoverTask:
    def __init__(self, tools, config=None):
        self.tools = tools
        self.config = config = config or TaskConfig()
        rules = self.rules = tools.rules()
        public = tools.map()
        self.ground = make_ground(rules, public)
        self.delay, self.horizon = int(rules["delay_ticks"]), int(rules["max_ticks"])
        self.max_metres = float(rules["max_metres_per_drive"])
        self.battery0 = float(rules["initial_battery"])
        self.sample_cost = float(rules["sample_cost"])
        self.target_radius, self.base_radius = float(rules["target_radius"]), float(rules["base_radius"])
        passes = rules.get("uplink_windows") or rules.get("relay_passes")
        self.passes = (int(passes["period_ticks"]), int(passes["open_ticks"])) if passes else None
        if self.passes and self.passes[1] >= self.passes[0]:
            self.passes = None

        sensing = rules.get("sensing") or {}
        navigation = rules.get("navigation") or {}
        scale_error = (navigation.get("wheel_scale_error") or (rules.get("wheels") or {}).get("wheel_scale_error")
                       or rules.get("wheel_scale_error") or 0.0)
        if isinstance(scale_error, dict):      # the traverse's MAX map publishes {"range": ...}
            scale_error = scale_error.get("range") or 0.0
        self.scale_error = float(scale_error)
        bias = math.radians(sensing.get("heading_bias_deg") or 0.0)
        self.heading_noise = math.radians(sensing.get("heading_noise_deg") or 0.0)
        self.q_rot = math.radians(sensing.get("heading_bias_walk_deg") or 0.0) ** 2 + 1e-6
        noise = sensing.get("position_noise_m") if sensing else 0.02   # no sensing model: exact fixes
        self.fix_var = None if noise is None else max(float(noise), 0.02) ** 2
        self.gate = GATE if rules.get("position_fix_outliers") else None
        self.vo_noise = float(sensing.get("visual_odometry_noise") or 0.0)
        self.vo_by_terrain = sensing.get("visual_odometry_noise_by_terrain") or {}
        compass = navigation.get("sun_compass_noise_deg")
        self.compass_var = None if compass is None else math.radians(compass) ** 2 + self.heading_noise ** 2

        briefing = tools.telemetry_log()[0]
        self.base = (float(public["base"][0]), float(public["base"][1]))
        x, y = briefing["position"] if briefing.get("position") is not None else self.base
        self.kf = Belief(x, y, scale_error ** 2 / 3.0 + 0.05 ** 2, bias ** 2 / 3.0 + 1e-4)
        self.filter_tick = int(briefing["tick"])
        self.tick = self.filter_tick
        self.heading = float(briefing.get("heading_deg") or 0.0)
        self.battery = float(briefing["battery"])
        self.alive = bool(briefing.get("alive", True))
        self.last_soft = briefing.get("terrain") in self.ground.soft_names
        self.targets, self.sampled, self.claims = {}, set(briefing.get("sampled_targets", [])), {}
        self.credited = {}    # target -> the value its sample is taken to have earned
        self._read_targets(public)
        self.acks, self.cancelled, self.reserved = {}, set(), 0
        self.stops, self.last_stop, self.rejects = 0, None, 0
        self.decisions = []   # (execute tick, action) of every decision, in order
        self.guarded = 0      # commands the safety rule replaced by a wait
        self.homed = 0        # commands the home guard replaced by its own
        self.field = HomeField(self.ground, self.base, self.base_radius) if config.home_guard else None
        # A stop clears the queue: what it can cost, at most, in slots (the closed part of a relay
        # period, the news of the stop coming down, the new commands going up).
        self.stop_slots = (self.passes[0] - self.passes[1] if self.passes else 0) + 2 * self.delay + 1
        self.trace = []       # (value taken to be sampled, believed distance to base) at every decision
        self._expected = None  # (slot, the state expected there), from the latest observation

        angles = np.radians(np.arange(config.headings) * 360.0 / config.headings)
        self.ray_cos, self.ray_sin = np.cos(angles), np.sin(angles)
        # drain_from[t]: energy the ticks from t to the horizon are expected to cost, for the way home.
        # need_from[t]: the most the battery is expected to be down, at any moment from t on, if the
        # rover only waits (with a sun that charges it this is less than the sum).
        self.drain_from, self.need_from = np.zeros(self.horizon + 2), np.zeros(self.horizon + 2)
        for t in range(self.horizon, 0, -1):
            self.drain_from[t] = self.drain_from[t + 1] + self.ground.tick_energy(t)
            self.need_from[t] = max(0.0, self.ground.tick_energy(t) + self.need_from[t + 1])

    # ---- the link ---------------------------------------------------------------------------
    def _open(self, tick):
        return self.passes is None or tick % self.passes[0] < self.passes[1]

    def _next_open(self, tick):
        if self._open(tick):
            return tick
        period = self.passes[0]
        return (tick // period + 1) * period

    # ---- playing ----------------------------------------------------------------------------
    def play(self, choose):
        """Run the mission, asking `choose(observation)` for the command of every slot."""
        while self.tick < self.horizon:
            if self._open(self.tick):
                slot = max(self.tick + self.delay + 1, self.reserved + 1)
                last = min(self.horizon, self._next_open(self.tick + 1) + self.delay)
                index = 0
                while slot <= last:
                    action = int(choose(self.observe(slot, index)))
                    slot = self._send(action, slot) + 1
                    index += 1
            out = self.tools.advance(1)
            self.tick = out["current_tick"]
            self.absorb(out["packets"])
            if out["episode_complete"]:
                break

    def command(self, action):
        if action == WAIT:
            return {"action": "wait"}
        if action == SAMPLE:
            return {"action": "sample"}
        if not FIRST_DRIVE <= action < self.config.n_actions:
            raise ValueError(f"action {action} is outside 0..{self.config.n_actions - 1}")
        heading, size = divmod(action - FIRST_DRIVE, len(self.config.metres))
        return {"action": "drive", "heading_deg": heading * 360.0 / self.config.headings,
                "metres": self.max_metres * self.config.metres[size]}

    def _affordable(self, command, slot):
        """Can the battery pay for this command at `slot` and still last to the horizon, even if
        every drive telemetry has not confirmed yet costs the most the published numbers allow
        (the dearest ground under every metre, the biggest wheels)?"""
        if command["action"] == "wait":
            return True
        kf, heading, battery, _, _, alive, risk = self._state(slot)
        if not alive:
            return True      # nothing left to protect
        cost = self.sample_cost
        if command["action"] == "drive":
            cost = self._worst(command["heading_deg"], command["metres"], kf.m[0], kf.m[1], heading)
        return battery - risk - cost - self.need_from[min(slot, self.horizon + 1)] > 1.0

    def _worst(self, heading_deg, metres, x, y, heading):
        return self.ground.worst_energy(x, y, heading_deg, metres * (1.0 + self.scale_error),
                                        abs(_wrap(heading_deg - heading)))

    # ---- the home guard ---------------------------------------------------------------------------
    def _home_need(self, slot, x, y, heading, gr, gi):
        """(energy the home guard keeps back, drives the way home takes) from (x, y), for a rover
        whose last commanded heading is `heading`, with the idle drain from `slot` to the horizon."""
        g = max(0.5, math.hypot(gr, gi))
        reach = self.max_metres * (1.0 - self.ground.slip_at(x, y)) * g
        ground_m, wheel_m, first, sand_m = self.field.left(x, y, reach)
        energy = self.need_from[min(slot, self.horizon + 1)] + 1.0
        if ground_m <= 0.0:
            return energy, 0
        # The first leg's commanded heading is its ground heading less the rotation the belief has learned;
        # the turns after it are allowed 45 degrees in all.
        heading_out = first - math.degrees(math.atan2(gi, gr))
        turn = abs(_wrap(heading_out - heading)) + 45.0
        energy += self.ground.worst_energy(x, y, heading_out, wheel_m / g * (1.0 + self.scale_error), turn)
        per_drive = self.max_metres * (1.0 - self.ground.firm_slip) * min(1.0, g)
        if self.field.sand_stops and sand_m > 0.0:
            # Sand that stops every step: each step of the way costs a round trip of the link.
            return energy, self.horizon + 1
        return energy, math.ceil(ground_m / per_drive) + 1

    def _home_slots(self, drives, unsure=False):
        """Slots the way home needs: its drives and two to spare, and what a stop can cost when the
        command before it can be stopped unexpectedly."""
        return (drives + 2 if drives else 0) + (self.stop_slots if unsure else 0)

    def _home_ok(self, command, slot):
        """After `command` at `slot`, is there still the energy and the time to get home?"""
        kf, heading, battery, _, _, alive, risk = self._state(slot)
        if not alive:
            return True      # nothing left to bring home
        x, y, gr, gi = (float(v) for v in kf.m)
        spend, unsure = 0.0, False
        if command["action"] == "sample":
            spend = self.sample_cost
        elif command["action"] == "drive":
            spend = self._worst(command["heading_deg"], command["metres"], x, y, heading)
            dx, dy, _, _, stopped = self.ground.advance(x, y, command["heading_deg"], command["metres"], gr, gi, True)
            nx, ny = x + gr * dx - gi * dy, y + gr * dy + gi * dx
            if self.field.into_sand(x, y, nx, ny):
                return False     # no drive onto sand that stops every step, but the guard's own
            unsure = stopped or self.field.may_stop(x, y, nx, ny)
            x, y, heading = nx, ny, command["heading_deg"]
        energy, drives = self._home_need(slot, x, y, heading, gr, gi)
        return battery - risk - spend >= energy and self.horizon - slot >= self._home_slots(drives, unsure)

    def _home_command(self, slot):
        """The home guard's own command: the next drive of the way home, or a wait at the base."""
        kf, _, _, _, _, alive, _ = self._state(slot)
        x, y, gr, gi = (float(v) for v in kf.m)
        if not alive or self.field.home(x, y):
            return {"action": "wait"}
        gain = complex(gr, gi)
        slip = self.ground.slip_at(x, y)
        wx, wy = self.field.waypoint(x, y, self.max_metres * (1.0 - slip) * abs(gain))
        wheel = complex(wx - x, wy - y) / gain        # the drive that the belief expects to end there
        metres = min(self.max_metres, abs(wheel) / (1.0 - slip))
        if metres < 0.05:
            return {"action": "wait"}
        return {"action": "drive", "heading_deg": math.degrees(math.atan2(wheel.imag, wheel.real)) % 360.0,
                "metres": round(metres, 3)}

    def _state(self, slot):
        if self._expected is None or self._expected[0] != slot:
            self._expected = (slot, self._predict(slot))
        return self._expected[1]

    def _send(self, action, slot=None):
        command = self.command(action)
        if slot is None:
            slot = max(self.tick + self.delay + 1, self.reserved + 1)
        if self.field is not None and not self._home_ok(command, slot):
            command = self._home_command(slot)
            self.homed += 1
        if self.config.guard and not self._affordable(command, slot):
            command = {"action": "wait"}
            self.guarded += 1
        x, y = self._state(slot)[0].m[:2]
        self.trace.append((sum(self.credited.values()), math.hypot(self.base[0] - x, self.base[1] - y)))
        ack = self.tools.uplink([command])[0]
        slot = int(ack["execute_tick"])
        self.acks[slot] = {"id": ack["command_id"], "sent": int(ack["sent_tick"]), "action": command["action"],
                           "heading": command.get("heading_deg"), "metres": command.get("metres")}
        self.reserved = slot
        self.decisions.append((slot, action))
        self._expected = None
        if command["action"] == "sample":
            x, y = self._predict(slot)[0].m[:2]
            near = min(((math.hypot(t[0] - x, t[1] - y), tid) for tid, t in self.targets.items()
                        if tid not in self.sampled and tid not in self.claims), default=None)
            if near is not None and near[0] <= self.target_radius:
                self.claims[near[1]] = slot   # counted as taken until telemetry says otherwise
                self.credited[near[1]] = self._worth(near[1], slot)
        return slot

    def rewards(self, result, home_pull=0.0):
        """The extrinsic reward of every decision; they add up to raw_score / max_available_value.
        With `home_pull`, what being home is worth is paid along the way (see the module text)."""
        out = np.zeros(len(self.decisions))
        total = result["max_available_value"]
        if not len(out) or total <= 0:
            return out
        index = {slot: i for i, (slot, _) in enumerate(self.decisions)}
        value = 0.0
        for sample in result.get("samples", []):
            out[index.get(sample["tick"], len(out) - 1)] += 0.5 * sample["credited_value"] / total
            value += sample["credited_value"]
        out[-1] += (result["survival_factor"] - 0.5) * value / total
        if home_pull:
            scale = 8.0 * self.base_radius
            phi = np.array([float(home_pull) * 0.5 * min(1.0, taken / total) * scale / (scale + distance)
                            for taken, distance in self.trace] + [0.0])
            out += phi[1:] - phi[:-1]
        return out

    # ---- telemetry ----------------------------------------------------------------------------
    def absorb(self, packets):
        self._expected = None
        for packet in packets:
            tick = int(packet["tick"])
            if tick <= self.filter_tick:
                continue
            ack = self.acks.get(tick)
            if (ack is not None and tick not in self.cancelled and packet.get("alive", True) and not any(
                    e["type"] == "command_executed" and e.get("command_id") == ack["id"] for e in packet["events"])):
                # The command of this tick did not run: a stop in a packet that never arrived
                # emptied the queue. Blame the latest lost tick that had a drive.
                lost = [t for t in range(self.filter_tick + 1, tick)
                        if t not in self.cancelled and (self.acks.get(t) or {}).get("action") == "drive"]
                self._flush(lost[-1] if lost else tick, tick)
            for t in range(self.filter_tick + 1, tick):
                self._run_tick(t, None)    # a lost packet: its command is taken to have run as expected
            self._run_tick(tick, packet)
            self.filter_tick = tick
            self._read_packet(packet)
        if packets:
            self._read_targets(self.tools.map())   # a discovery whose packet was lost is listed here

    def _flush(self, stop_tick, first):
        """A stop at `stop_tick` discarded what was queued then: sent before it, due at `first` or later."""
        for slot, ack in self.acks.items():
            if slot >= first and ack["sent"] < stop_tick:
                self.cancelled.add(slot)

    def _noise(self, kf, dx, dy, soft):
        distance = math.hypot(dx, dy)
        spread = 0.15 if soft else 0.05
        return (spread * distance) ** 2 + (self.heading_noise * distance) ** 2 + 1e-6

    def _run_tick(self, tick, packet):
        """Fold the command that ran at `tick` into the belief; `packet` is its telemetry, if it came."""
        ack = self.acks.get(tick)
        if ack is None or tick in self.cancelled or ack["action"] != "drive" or not self.alive:
            return
        kf = self.kf
        x, y, gr, gi = kf.m
        soft = self.ground.soft_at(x, y)
        if packet is None:
            dx, dy, _, _, _ = self.ground.advance(x, y, ack["heading"], ack["metres"], gr, gi, True)
        else:
            dx, dy, _, _, _ = self.ground.advance(x, y, ack["heading"], float(packet["wheel_odometry"]), gr, gi, False)
        kf.move(dx, dy, self._noise(kf, dx, dy, soft), 1e-4, self.q_rot)
        self.heading = ack["heading"]
        if packet is None:
            return
        expected = math.hypot(dx, dy)
        visual = packet.get("visual_odometry")
        if visual and expected > 0.3 and not soft and packet.get("terrain") not in self.ground.soft_names:
            ratio = visual / expected            # ground covered / ground expected: the scale
            sigma = self.vo_by_terrain.get(packet.get("terrain"), self.vo_noise)
            kf.reading(2, math.sqrt(max(ratio * ratio - kf.m[3] ** 2, 0.01)), (sigma * ratio) ** 2 + 0.02 ** 2)
        sun = packet.get("sun_heading_deg")
        if sun is not None and self.compass_var is not None and float(packet["wheel_odometry"]) > 0:
            kf.reading(3, math.radians(_wrap(sun - ack["heading"])) * kf.m[2], self.compass_var)

    def _read_packet(self, packet):
        tick = int(packet["tick"])
        self.battery = float(packet["battery"])
        self.alive = bool(packet.get("alive", True))
        self.last_soft = packet.get("terrain") in self.ground.soft_names
        position = packet.get("position")
        if position is not None and self.fix_var is not None:
            taken = self.kf.fix(position[0], position[1], self.fix_var, self.gate if self.rejects < 3 else None)
            self.rejects = 0 if taken else self.rejects + 1
        confirmed = set(packet.get("sampled_targets", []))
        for target_id in confirmed - self.sampled:   # taken, perhaps in a packet that never came
            self.credited.setdefault(target_id, self._worth(target_id, self.claims.get(target_id, tick)))
        self.sampled |= confirmed
        for target_id, slot in list(self.claims.items()):
            if slot <= tick and target_id not in confirmed:
                del self.claims[target_id]         # that sample missed: the target is open again
                self.credited.pop(target_id, None)
        for event in packet["events"]:
            if event["type"] == "safety_stop":
                self.stops += 1
                self.last_stop = tick
                self._flush(tick, tick + 1)
                if self.field is not None and event.get("reason") == "slip_limit":
                    self.field.learn_trip()
            elif event["type"] == "target_discovered":
                self._read_targets({"targets": [event["target"]]})
            elif event["type"] == "sample_taken" and event["target_id"] in self.targets:
                target = self.targets[event["target_id"]]
                self.credited[event["target_id"]] = target[2] if event.get("on_time", True) else target[4]

    def _worth(self, target_id, tick):
        """What a sample of this target at `tick` earns: its value, or the late value past the deadline."""
        if target_id not in self.targets:
            return 0.0
        _, _, value, deadline, late_value = self.targets[target_id]
        return value if deadline is None or tick <= deadline else late_value

    def _read_targets(self, public):
        for t in public["targets"]:
            self.targets[t["id"]] = (float(t["x"]), float(t["y"]), float(t["value"]), t.get("deadline_tick"),
                                     float(t.get("late_value", t["value"])))

    # ---- the expected state at a slot -------------------------------------------------------------
    def _predict(self, slot):
        """The belief carried through the commands due before `slot`: (belief, heading, battery,
        a stop is expected on the way, the command of the slot before, the rover is expected alive,
        how much more than expected those commands can cost at worst). A rover whose battery is
        empty, or is expected to be by then, does not move again."""
        kf, heading, battery = self.kf.copy(), self.heading, self.battery
        flushed_before, stop, previous, alive = -1, False, None, self.alive and self.battery > 0
        risk = 0.0
        for tick in range(self.filter_tick + 1, slot):
            ack = self.acks.get(tick)
            previous = None
            if alive:
                battery -= self.ground.tick_energy(tick)
                if battery <= 0:
                    battery, alive = 0.0, False
            if not alive or ack is None or tick in self.cancelled:
                continue
            if ack["sent"] < flushed_before:
                # Expected to be discarded by the stop above. If that stop does not happen it runs,
                # so the battery guard still has to be able to pay for it.
                if ack["action"] == "drive":
                    risk += self._worst(ack["heading"], ack["metres"], kf.m[0], kf.m[1], heading)
                elif ack["action"] == "sample":
                    risk += self.sample_cost
                continue
            previous = ack
            if ack["action"] == "sample":
                battery -= self.sample_cost
            elif ack["action"] == "drive":
                x, y, gr, gi = kf.m
                turn = self.ground.turn_energy(abs(_wrap(ack["heading"] - heading)), x, y)
                dx, dy, _, energy, stopped = self.ground.advance(x, y, ack["heading"], ack["metres"], gr, gi, True)
                kf.move(dx, dy, self._noise(kf, dx, dy, self.ground.soft_at(x, y)), 1e-4, self.q_rot)
                battery -= turn + energy
                risk += max(0.0, self._worst(ack["heading"], ack["metres"], x, y, heading) - turn - energy)
                heading = ack["heading"]
                if stopped:
                    stop, flushed_before = True, tick
            if battery <= 0:
                battery, alive = 0.0, False
        return kf, heading, battery, stop, previous, alive, risk

    def observe(self, slot, batch_index=0):
        """The observation for the command that will run at `slot`."""
        c = self.config
        kf, heading, battery, stop, previous, alive, risk = self._state(slot)
        x, y, gr, gi = (float(v) for v in kf.m)
        reach = self.max_metres
        per_drive = reach * (1.0 - self.ground.firm_slip)
        obs = np.zeros(c.obs_dim)
        sigma = kf.sigma
        open_targets = sorted((math.hypot(t[0] - x, t[1] - y), tid) for tid, t in self.targets.items()
                              if tid not in self.sampled and tid not in self.claims)
        obs[0] = slot / self.horizon
        obs[1] = min(1.0, max(0.0, battery / self.battery0))
        obs[2] = min(1.0, (slot - 1 - self.filter_tick) / 16.0)
        obs[3] = sigma / (sigma + self.target_radius)
        obs[4] = min(1.0, max(-1.0, 2.0 * (gr - 1.0)))
        obs[5] = min(1.0, max(-1.0, 2.0 * gi))
        obs[6] = float(self.ground.soft_at(x, y))
        obs[7] = float(self.ground.risky_at(x, y))
        obs[8] = float(self.last_soft)
        obs[9] = min(self.stops, 3) / 3.0
        obs[10] = float(self.last_stop is not None and self.filter_tick - self.last_stop <= 8)
        obs[11] = float(stop)
        obs[12] = float(alive)
        obs[13] = min(batch_index, 4) / 4.0
        obs[14] = float(not self._open(self.tick + 1))
        if previous is not None:
            obs[15 + ("wait", "sample", "drive").index(previous["action"])] = 1.0
            if previous["action"] == "drive":
                obs[20] = previous["metres"] / reach
        obs[18], obs[19] = math.cos(math.radians(heading)), math.sin(math.radians(heading))
        obs[21] = min(len(open_targets), 8) / 8.0
        known = sum(t[2] for t in self.targets.values())
        obs[22] = min(1.0, sum(self.credited.values()) / known) if known > 0 else 0.0

        i = GLOBAL
        distance = math.hypot(self.base[0] - x, self.base[1] - y)
        slots_left = self.horizon - slot + 1
        home_energy = distance * self.ground.metre_energy(x, y) + self.drain_from[min(slot, self.horizon + 1)]
        if distance > 1e-9:
            obs[i], obs[i + 1] = (self.base[0] - x) / distance, (self.base[1] - y) / distance
        obs[i + 2] = distance / (distance + 3.0 * reach)
        obs[i + 3] = min(1.0, distance / (2.0 * reach))
        obs[i + 4] = float(distance <= self.base_radius)
        obs[i + 5] = min(1.0, max(-1.0, (slots_left - math.ceil(distance / per_drive)) / 10.0))
        obs[i + 6] = min(1.0, max(-1.0, (battery - home_energy) / self.battery0))
        if self.field is not None and alive:
            # The home guard's own margins, as they stand if this slot is a wait.
            energy, drives = self._home_need(slot, x, y, heading, gr, gi)
            obs[i + 5] = min(1.0, max(-1.0, (self.horizon - slot - self._home_slots(drives)) / 10.0))
            obs[i + 6] = min(1.0, max(-1.0, (battery - risk - energy) / self.battery0))

        i += BASE
        for distance, target_id in open_targets[:c.targets]:
            tx, ty, value, deadline, late_value = self.targets[target_id]
            arrive = slot + math.ceil(max(0.0, distance - 0.5 * self.target_radius) / per_drive)
            late = deadline is not None and arrive > deadline
            obs[i] = 1.0
            if distance > 1e-9:
                obs[i + 1], obs[i + 2] = (tx - x) / distance, (ty - y) / distance
            obs[i + 3] = distance / (distance + 3.0 * reach)
            obs[i + 4] = min(1.0, distance / (2.0 * reach))
            obs[i + 5] = float(distance <= self.target_radius)
            obs[i + 6] = value / (value + 2.0)
            credited = late_value if late else value
            obs[i + 7] = credited / (credited + 2.0)
            obs[i + 8] = 1.0 if deadline is None else min(1.0, max(-1.0, (deadline - arrive) / 10.0))
            obs[i + 9] = float(late)
            i += PER_TARGET

        i = GLOBAL + BASE + c.targets * PER_TARGET
        free, firm, safe = self.ground.rays(x, y, self.ray_cos, self.ray_sin, c.ray_reach * reach)
        n = c.headings
        obs[i:i + n], obs[i + n:i + 2 * n], obs[i + 2 * n:i + 3 * n] = free, firm, safe
        return obs
