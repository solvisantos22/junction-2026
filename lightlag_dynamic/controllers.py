"""Scripted controllers for the dynamic pilot.

They see only the five public tools (rules, map, telemetry_log, uplink, advance), the same
boundary as the team's planned PublicTools, and import nothing from the simulator.

  reference        predicts commands in transit, learns slip, plans around windows and discoveries
  leg_and_wait     same planner, but sends one leg and waits for all its telemetry before deciding
  stale_telemetry  same planner, but plans from the last received packet as if it were the present
  window_blind     the reference without the new rules: ignores deadlines, never re-reads the map
  open_loop        plans once from the briefing with mid-range slip, sends everything, never reads
                   telemetry (the "blind plan" a script could write; the team pilot's key baseline)
  do_nothing       sends nothing
  kf_mpc           Kalman filter + receding-horizon planning with chance constraints (kf_mpc.py)

This reference is a local stand-in for the team's reference controller, which is being
built separately. It is not optimal; it is an honest algorithm using public information.
"""

from collections import namedtuple
import heapq
import itertools
import math

RESERVE = 2.0            # energy kept in hand at the horizon
HAZARD_CLEARANCE = 0.35  # route clearance around hazards (metres)
CORNER_OFFSET = 0.6      # route waypoints sit this far outside hazard corners
AIM_MARGIN = 0.25        # aim this far inside the target and base radii
MAX_SEQUENCE = 4         # longest target sequence the planner enumerates
SAMPLE = {"action": "sample"}
MODES = ("reference", "leg_and_wait", "stale_telemetry", "window_blind", "open_loop")

Leg = namedtuple("Leg", "commands energy energy_safe uncertainty")


def _clip_interval(a, b, rect, margin=0.0):
    """Parameter interval of segment a->b inside rect (inflated by margin), or None."""
    x1, y1 = rect["x1"] - margin, rect["y1"] - margin
    x2, y2 = rect["x2"] + margin, rect["y2"] + margin
    t0, t1 = 0.0, 1.0
    for origin, delta, low, high in ((a[0], b[0] - a[0], x1, x2), (a[1], b[1] - a[1], y1, y2)):
        if abs(delta) < 1e-12:
            if not low <= origin <= high:
                return None
            continue
        near, far = sorted(((low - origin) / delta, (high - origin) / delta))
        t0, t1 = max(t0, near), min(t1, far)
        if t0 > t1:
            return None
    return (t0, t1)


class Controller:
    def __init__(self, tools, mode="reference"):
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}")
        self.tools, self.mode = tools, mode
        rules = tools.rules()
        self.k = rules["delay_ticks"]
        self.horizon = rules["max_ticks"]
        self.idle = rules["idle_cost"]
        self.drive_cost = rules["drive_cost"]
        self.sample_cost = rules["sample_cost"]
        self.radius = rules["target_radius"]
        self.base_radius = rules["base_radius"]
        self.multiplier = rules["terrain_drive_multipliers"]
        self.slip_ranges = {name: tuple(bounds) for name, bounds in rules["slip_ranges"].items()}
        self.max_metres = rules["max_metres_per_drive"]
        self.max_batch = rules["max_commands_per_uplink"]
        self.late_fraction = (rules.get("sample_windows") or {}).get("late_fraction", 1.0)
        self.packets = tools.telemetry_log()
        self.tick = self.packets[-1]["tick"]
        self.acks, self.cancelled = [], set()
        self.slip_obs = {name: [] for name in self.slip_ranges}
        self.slip_version = 0
        self.confirm_tick = None
        self.quiet_signature = None
        self._segments = {}
        self._read_map()

    # ---- knowledge ------------------------------------------------------------------
    def _read_map(self):
        public = self.tools.map()
        self.size = (public["width"], public["height"])
        self.base = tuple(public["base"])
        self.sand, self.hazards = public["sand"], public["hazards"]
        self.targets = {t["id"]: t for t in public["targets"]}
        corners = []
        for rects, offset in ((self.hazards, CORNER_OFFSET), (self.sand, 0.05)):
            for r in rects:
                corners += [(x, y) for x in (r["x1"] - offset, r["x2"] + offset)
                            for y in (r["y1"] - offset, r["y2"] + offset)]
        w, h = self.size
        self.corners = [p for p in corners if 0.3 <= p[0] <= w - 0.3 and 0.3 <= p[1] <= h - 0.3
                        and not any(_clip_interval(p, p, r, HAZARD_CLEARANCE) for r in self.hazards)]

    def terrain_at(self, x, y):
        return "sand" if any(r["x1"] <= x <= r["x2"] and r["y1"] <= y <= r["y2"]
                             for r in self.sand) else "bedrock"

    def slip(self, terrain):
        obs = self.slip_obs[terrain]
        lo, hi = self.slip_ranges[terrain]
        return sum(obs) / len(obs) if obs else (lo + hi) / 2

    def slip_safe(self, terrain):
        hi = self.slip_ranges[terrain][1]
        return min(0.9, self.slip(terrain) + 0.03) if self.slip_obs[terrain] else hi

    def slip_spread(self, terrain):
        lo, hi = self.slip_ranges[terrain]
        return 0.03 if self.slip_obs[terrain] else (hi - lo) / 2

    def reserved_until(self):
        return max((a["execute_tick"] for a in self.acks), default=0)

    def next_slot(self):
        return max(self.tick + self.k + 1, self.reserved_until() + 1)

    # ---- telemetry --------------------------------------------------------------------
    def absorb(self, packet):
        previous = self.packets[-1]
        self.packets.append(packet)
        kinds = {event["type"] for event in packet["events"]}
        if kinds & {"safety_stop", "battery_depleted"}:
            # The stop cleared everything queued at that moment: commands sent before it.
            for ack in self.acks:
                if ack["sent_tick"] < packet["tick"] < ack["execute_tick"]:
                    self.cancelled.add(ack["command_id"])
            self.confirm_tick = None
        wheel = packet["wheel_odometry"]
        if wheel > 0.2 and "safety_stop" not in kinds and packet["alive"]:
            self._learn_slip(tuple(previous["position"]), tuple(packet["position"]), wheel)
        if "target_discovered" in kinds and self.mode != "window_blind":
            self._read_map()

    def _learn_slip(self, a, b, wheel):
        _, bed, sand = self._segment(a, b)
        if bed + sand < 1e-6:
            return
        if sand < 0.05:
            terrain, value = "bedrock", 1 - (bed + sand) / wheel
        elif bed < 0.05:
            terrain, value = "sand", 1 - (bed + sand) / wheel
        elif sand >= 0.5:  # mixed leg: attribute the rest of the wheel distance to sand
            rest = wheel - bed / (1 - self.slip("bedrock"))
            if rest <= sand:
                return
            terrain, value = "sand", 1 - sand / rest
        else:
            return
        self.slip_obs[terrain].append(min(0.9, max(0.0, value)))
        self.slip_version += 1

    # ---- prediction -------------------------------------------------------------------
    def predict(self, slot, use_pending=True):
        last = self.packets[-1]
        state = {"x": last["position"][0], "y": last["position"][1], "battery": last["battery"],
                 "sampled": set(last["sampled_targets"]), "alive": last["alive"]}
        queue = {}
        if use_pending:
            queue = {a["execute_tick"]: a["command"] for a in self.acks
                     if a["execute_tick"] > last["tick"] and a["command_id"] not in self.cancelled}
        for t in range(last["tick"] + 1, slot):
            state["battery"] -= self.idle
            if state["battery"] <= 0:
                state["battery"], state["alive"] = 0.0, False
                break
            command = queue.get(t)
            if command and command["action"] == "drive":
                self._simulate_drive(state, command)
            elif command and command["action"] == "sample":
                state["battery"] -= self.sample_cost
                near = [tid for tid, tg in self.targets.items() if tid not in state["sampled"]
                        and math.hypot(tg["x"] - state["x"], tg["y"] - state["y"]) <= self.radius]
                if near:
                    state["sampled"].add(min(near, key=lambda tid: math.hypot(
                        self.targets[tid]["x"] - state["x"], self.targets[tid]["y"] - state["y"])))
        state["tick"] = slot - 1
        return state

    def _simulate_drive(self, state, command):
        radians = math.radians(command["heading_deg"])
        dx, dy = math.cos(radians), math.sin(radians)
        remaining, (w, h) = command["metres"], self.size
        while remaining > 1e-9 and state["battery"] > 0:
            terrain = self.terrain_at(state["x"], state["y"])
            cost = self.drive_cost * self.multiplier[terrain]
            segment = min(0.1, remaining, state["battery"] / cost)
            distance = segment * (1 - self.slip(terrain))
            nx, ny = state["x"] + dx * distance, state["y"] + dy * distance
            if not (0 <= nx <= w and 0 <= ny <= h) or any(
                    _clip_interval((state["x"], state["y"]), (nx, ny), r) for r in self.hazards):
                break
            state["x"], state["y"] = nx, ny
            state["battery"] -= segment * cost
            remaining -= segment

    # ---- routing ------------------------------------------------------------------------
    def _segment(self, a, b):
        key = (round(a[0], 3), round(a[1], 3), round(b[0], 3), round(b[1], 3))
        hit = self._segments.get(key)
        if hit is None:
            length = math.dist(a, b)
            w, h = self.size
            clear = all(0 <= p[0] <= w and 0 <= p[1] <= h for p in (a, b)) and not any(
                _clip_interval(a, b, r, HAZARD_CLEARANCE) for r in self.hazards)
            sand_t, end = 0.0, 0.0
            for t0, t1 in sorted(iv for iv in (_clip_interval(a, b, r) for r in self.sand) if iv):
                t0 = max(t0, end)
                if t1 > t0:
                    sand_t += t1 - t0
                    end = t1
            hit = (clear, length * (1 - sand_t), length * sand_t)
            self._segments[key] = hit
        return hit

    def _energy(self, bed, sand, slip_of):
        return self.drive_cost * (self.multiplier["bedrock"] * bed / (1 - slip_of("bedrock"))
                                  + self.multiplier["sand"] * sand / (1 - slip_of("sand")))

    def route(self, a, b):
        nodes = [a] + self.corners + [b]
        goal = len(nodes) - 1
        best, previous, done = {0: 0.0}, {}, set()
        heap = [(0.0, 0)]
        while heap:
            cost, i = heapq.heappop(heap)
            if i in done:
                continue
            done.add(i)
            if i == goal:
                break
            for j in range(1, len(nodes)):
                if j in done:
                    continue
                clear, bed, sand = self._segment(nodes[i], nodes[j])
                if not clear:
                    continue
                new = cost + self._energy(bed, sand, self.slip) + 0.1 * (bed + sand)
                if new < best.get(j, math.inf) - 1e-12:
                    best[j], previous[j] = new, i
                    heapq.heappush(heap, (new, j))
        if goal not in done:
            # Last resort near a hazard edge: the straight line, if it does not touch the hazard.
            if not any(_clip_interval(a, b, r) for r in self.hazards):
                return [a, b]
            return None
        path = [goal]
        while path[-1] != 0:
            path.append(previous[path[-1]])
        return [nodes[i] for i in reversed(path)]

    def leg(self, start, goal):
        path = self.route(start, goal)
        if path is None:
            return None
        commands, energy, energy_safe, uncertainty = [], 0.0, 0.0, 0.0
        for a, b in zip(path, path[1:]):
            _, bed, sand = self._segment(a, b)
            if bed + sand < 0.02:
                continue
            wheel_bed = bed / (1 - self.slip("bedrock"))
            wheel_sand = sand / (1 - self.slip("sand"))
            wheel = wheel_bed + wheel_sand
            energy += self._energy(bed, sand, self.slip)
            energy_safe += self._energy(bed, sand, self.slip_safe)
            uncertainty += wheel_bed * self.slip_spread("bedrock") + wheel_sand * self.slip_spread("sand")
            heading = round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 360.0, 6)
            pieces = max(1, math.ceil(wheel / self.max_metres - 1e-9))
            commands += [{"action": "drive", "heading_deg": heading,
                          "metres": round(wheel / pieces, 6)} for _ in range(pieces)]
        return Leg(commands, energy, energy_safe, uncertainty)

    def needs_confirmation(self, leg):
        # leg_and_wait already waits after every leg, so it samples at once and retries on a miss.
        return (self.mode not in ("stale_telemetry", "leg_and_wait", "open_loop")
                and leg.uncertainty > self.radius - AIM_MARGIN)

    def home_slack(self):
        # Ticks kept free after the planned arrival home, for a last correction.
        return 0

    def confirmation_ticks(self, leg):
        # Stop, wait for the last drive's telemetry (k), then the next command needs k + 1.
        return 2 * self.k + 1

    def wait_per_leg(self):
        # leg_and_wait plans honestly for its own waiting: telemetry back (k), new command out (k).
        return 2 * self.k if self.mode == "leg_and_wait" else 0

    # ---- planning -----------------------------------------------------------------------
    def value_at(self, target, tick):
        if self.mode == "window_blind" or target.get("deadline_tick") is None:
            return target["value"]
        return target["value"] if tick <= target["deadline_tick"] else target.get(
            "late_value", target["value"] * self.late_fraction)

    def choose(self, state, slot):
        """Best target sequence ending at base; only its first target is acted on."""
        start = (state["x"], state["y"])
        open_targets = [t for tid, t in sorted(self.targets.items()) if tid not in state["sampled"]]
        budget = state["battery"] - self.idle * (self.horizon - state["tick"]) - RESERVE
        points = {t["id"]: (t["x"], t["y"]) for t in open_targets}
        points.update({"start": start, "base": self.base})
        legs = {}

        def leg(a, b):
            if (a, b) not in legs:
                legs[(a, b)] = self.leg(points[a], points[b])
            return legs[(a, b)]

        best = (0.0, math.inf, ())
        for size in range(1, min(len(open_targets), MAX_SEQUENCE) + 1):
            for sequence in itertools.permutations(open_targets, size):
                tick, value, expected, here = slot, 0.0, 0.0, "start"
                for target in sequence:
                    hop = leg(here, target["id"])
                    home = leg(target["id"], "base")
                    if hop is None or home is None:
                        break
                    if here != "start":
                        tick += self.wait_per_leg()
                    tick += len(hop.commands)
                    if self.needs_confirmation(hop):
                        tick += self.confirmation_ticks(hop)
                    value += self.value_at(target, tick)
                    tick += 1
                    expected += hop.energy + self.sample_cost
                    # After every stop a pessimistic way home must remain. This makes the
                    # planner visit uncertain terrain while energy is still plentiful.
                    if expected + home.energy_safe > budget:
                        break
                    here = target["id"]
                else:
                    home = leg(here, "base")
                    end = tick + self.wait_per_leg() + len(home.commands) - 1
                    if end > self.horizon - self.home_slack() or expected + home.energy > budget:
                        continue
                    if value > best[0] + 1e-9 or (abs(value - best[0]) <= 1e-9 and end < best[1]):
                        best = (value, end, sequence)
        self.plan_end, self.plan = best[1], best[2]  # subclasses read the time pressure from these
        return best[2]

    # ---- acting -------------------------------------------------------------------------
    def send(self, commands):
        room = self.horizon - self.next_slot() + 1
        commands = commands[:max(0, room)]
        for i in range(0, len(commands), self.max_batch):
            self.acks.extend(self.tools.uplink(commands[i:i + self.max_batch]))
        return bool(commands)

    def ready(self):
        last = self.packets[-1]
        if not last["alive"]:
            return False
        if self.mode == "leg_and_wait":
            return last["tick"] >= self.reserved_until()
        if self.reserved_until() >= self.tick + self.k + 1:
            return False  # the queue already covers the earliest slot a new command could use
        if self.confirm_tick is not None:
            if last["tick"] < self.confirm_tick:
                return False
            self.confirm_tick = None
        return True

    def decide(self):
        slot = self.next_slot()
        if slot > self.horizon:
            return
        state = self.predict(slot, use_pending=self.mode != "stale_telemetry")
        if not state["alive"]:
            return
        signature = (tuple(sorted(self.targets)), tuple(sorted(state["sampled"])),
                     round(state["x"], 2), round(state["y"], 2), self.slip_version)
        if signature == self.quiet_signature:
            return
        here = (state["x"], state["y"])
        sequence = self.choose(state, slot)
        if sequence:
            target = (sequence[0]["x"], sequence[0]["y"])
            if math.dist(here, target) <= self.radius - AIM_MARGIN:
                self.send([SAMPLE])
                return
            hop = self.leg(here, target)
            if hop is not None:
                if self.needs_confirmation(hop):
                    if self.send(hop.commands):
                        self.confirm_tick = self.reserved_until()
                else:
                    self.send(hop.commands + [SAMPLE])
                return
        if math.dist(here, self.base) > self.base_radius - AIM_MARGIN:
            hop = self.leg(here, self.base)
            if hop is not None and hop.commands:
                self.send(hop.commands)
                return
        self.quiet_signature = signature

    def run_open_loop(self):
        slot = self.next_slot()
        state = self.predict(slot)
        commands, here = [], (state["x"], state["y"])
        for target in self.choose(state, slot):
            point = (target["x"], target["y"])
            hop = self.leg(here, point)
            if hop is None:
                break
            commands += hop.commands + [SAMPLE]
            here = point
        hop = self.leg(here, self.base)
        if hop is not None:
            commands += hop.commands
        self.send(commands)
        while self.tick < self.horizon:  # never reads a packet
            self.tick = self.tools.advance(5)["current_tick"]

    def run(self):
        if self.mode == "open_loop":
            return self.run_open_loop()
        while self.tick < self.horizon:
            if self.ready():
                self.decide()
            result = self.tools.advance(1)
            self.tick = result["current_tick"]
            for packet in result["packets"]:
                self.absorb(packet)
            if result["episode_complete"]:
                break


def _policy(mode):
    def policy(tools):
        Controller(tools, mode=mode).run()
    policy.__name__ = mode
    return policy


def do_nothing(tools):
    return None


def kf_mpc(tools):
    """Kalman filter + receding-horizon controller (lightlag_dynamic/kf_mpc.py)."""
    from .kf_mpc import KalmanMPCController  # imported here: kf_mpc builds on this module
    KalmanMPCController(tools).run()


POLICIES = {"reference": _policy("reference"), "leg_and_wait": _policy("leg_and_wait"),
            "stale_telemetry": _policy("stale_telemetry"), "window_blind": _policy("window_blind"),
            "open_loop": _policy("open_loop"), "do_nothing": do_nothing, "kf_mpc": kf_mpc}
