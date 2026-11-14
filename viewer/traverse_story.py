"""The moments a traverse replay's story mode stops at, computed from the evaluator's replays.

A moment is a tick at which one rover did something that decided its score: what it did, and where
the replay can show it, what would have saved it, or what the reference did instead. Every number
comes from the replays: the rover's true state, the hidden values the evaluator kept (each
terrain's true slip, the panels' true efficiency) and the published ground model. Nothing is
simulated beyond one question, asked as `tools/traverse_farm/analysis.py` asks it: from where the
rover really was, with the battery it really had, could a drive home over the cheapest ground,
waiting for the sun when short, have reached the lander by the last tick? The check is generous to
the rover (it ignores the command delay and checks the battery only at the end of the drive), so
"the way home was open" means physically possible, not what the rover's program could have known.

Kinds, for rovers other than the reference: `lost` (the battery ran out), `no_return` (the last
tick from which the lander was still in reach, when that was before the end), `away` (ended alive
outside the lander's ring), `close` (survived a battery under 3%), `steep` (three or more safety
stops), `misses` (three or more failed samples). For the reference: `ref_wait` (it stops to let
the sun recharge) and `ref_home` (it turns for home). Standard library only.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from lightlag_traverse.planning import INF, Ground, Sun
from lightlag_traverse.surface import Surface

CLOSE_SHARE = 0.03          # a battery under this share of capacity is a close call
MANY = 3                    # this many safety stops or failed samples make a moment


class Truth:
    """One replay with the questions a story asks of it."""

    def __init__(self, replay: Dict[str, Any]) -> None:
        self.replay = replay
        self.world, self.config, hidden = replay["world"], replay["config"], replay["hidden"]
        self.states = replay["states"]
        self.horizon = self.config["max_ticks"]
        self.capacity = self.config["battery_capacity"]
        self.base = tuple(self.world["base"])
        surface = Surface(self.world["cell_m"], self.world["elevation_cm"], self.world["terrain"])
        self.ground = Ground(surface, replay["physics"], hidden["slip_base"])
        self.goal = self.ground.node(*self.base)
        self.field = self.ground.field(self.goal)
        self.sun = Sun(self.config, hidden["solar_efficiency"])
        self.died = next((s["tick"] for s in self.states if not s["alive"]), None)
        samples = sorted((self.replay["result"].get("samples") or []), key=lambda s: s["tick"])
        self.samples = samples
        self.max_value = self.replay["result"]["max_available_value"]

    # ---- the way home -------------------------------------------------------------------
    def at_base(self, x: float, y: float) -> bool:
        return math.hypot(x - self.base[0], y - self.base[1]) <= self.config["base_radius"]

    def way_home(self, x: float, y: float) -> Optional[Tuple[float, float]]:
        """Ticks and energy from (x, y) to the lander over the cheapest ground, or None."""
        node = self.ground.node(x, y)
        if node is None or self.field.ticks[node] == INF:
            return None
        px, py = self.ground.point(node)
        hop = self.ground.straight(x, y, px, py, tilt=1.0) or (math.hypot(px - x, py - y) / self.ground.max_metres, 0.0)
        return hop[0] + self.field.ticks[node], hop[1] + self.field.energy[node]

    def arrival(self, t: int, battery: float, ticks: float, energy: float) -> Optional[Tuple[int, int]]:
        """(arrival tick, ticks waited first) leaving at tick t, waiting a tick at a time while the sun is short."""
        total, idle = self.sun.total, self.sun.idle
        need, waited = int(math.ceil(ticks - 1e-9)), 0
        while t + need <= self.horizon:
            if battery + total[t + need] - total[t] - idle * need - energy > 0.0:
                return t + need, waited
            gain = total[t + 1] - total[t] - idle
            if gain <= 0.0:
                return None
            battery, t, waited = min(self.capacity, battery + gain), t + 1, waited + 1
        return None

    def open_at(self, state: Dict[str, Any]) -> bool:
        x, y = state["position"]
        if not state["alive"]:
            return False
        if self.at_base(x, y):
            return True
        leg = self.way_home(x, y)
        return leg is not None and self.arrival(state["tick"], state["battery"], *leg) is not None

    def home_path(self, x: float, y: float, limit: int = 400) -> List[List[float]]:
        """The cheapest way to the lander from (x, y), as points every grid step."""
        node = self.ground.node(x, y)
        points = [[round(x, 1), round(y, 1)]]
        while node is not None and node != self.goal and len(points) < limit:
            px, py = self.ground.point(node)
            points.append([round(px, 1), round(py, 1)])
            following = self.field.step[node]
            if following is None or following < 0 or following == node:
                break
            node = following
        points.append([round(self.base[0], 1), round(self.base[1], 1)])
        return points

    def last_open(self) -> Optional[int]:
        """The last tick from which the lander was still in reach, or None if never."""
        last = None
        for state in self.states:
            if self.open_at(state):
                last = state["tick"]
        return last

    # ---- what it carried ----------------------------------------------------------------
    def carried(self, t: int) -> Tuple[int, float]:
        """Samples taken and value credited up to tick t."""
        taken = [s for s in self.samples if s["tick"] <= t]
        return len(taken), sum(s["credited_value"] for s in taken)

    def distance_home(self, state: Dict[str, Any]) -> float:
        x, y = state["position"]
        return math.hypot(x - self.base[0], y - self.base[1])

    def events(self, kind: str) -> List[int]:
        return [s["tick"] for s in self.states for e in s["events"] if e["type"] == kind]


def percent(battery: float, capacity: float) -> str:
    share = battery / capacity * 100
    return "{:.0f}%".format(share) if share >= 10 else "{:.1f}%".format(share)


def run_moments(run_id: str, label: str, truth: Truth, reference: Optional[Truth]) -> List[Dict[str, Any]]:
    """Moments for one rover other than the reference."""
    out: List[Dict[str, Any]] = []
    states, cap = truth.states, truth.capacity
    final = states[-1]
    ref_min = None if reference is None else min(s["battery"] for s in reference.states)

    def moment(t: int, kind: str, did: str, better: str, **more: Any) -> Dict[str, Any]:
        x, y = states[t]["position"]
        item = {"t": t, "run": run_id, "kind": kind, "focus": [round(x, 1), round(y, 1)], "did": did, "better": better}
        item.update(more)
        return item

    if truth.died is not None or not truth.at_base(*final["position"]):
        last = truth.last_open()
        if truth.died is not None:
            dead = truth.died
            before = states[dead - 1] if dead > 0 else states[0]
            n, value = truth.carried(dead)
            share = value / truth.max_value
            metres = truth.distance_home(states[dead])
            if last is not None and last >= dead - 1:
                x, y = before["position"]
                leg = truth.way_home(x, y)
                trip = truth.arrival(before["tick"], before["battery"], *leg) if leg else None
                if trip and trip[1] > 0:
                    better = ("The way home was still open: waiting {} ticks for the sun, then driving the {:.0f} m home, "
                              "would have reached the lander.".format(trip[1], metres))
                else:
                    better = "The way home was still open: driving the {:.0f} m home would have reached the lander.".format(metres)
                out.append(moment(dead, "lost",
                                  "Drove its battery to zero {:.0f} m from the lander, carrying {} samples worth {:.2f} of "
                                  "this site. A flat battery scores the whole site 0.".format(metres, n, share),
                                  better, path=truth.home_path(x, y), open=True, wait=trip[1] if trip else None))
            else:
                point = 0 if last is None else last + 1
                at = states[point]
                ticks_left = truth.horizon - point
                drives = sum(1 for c in truth.replay["commands"]
                             if point < c["execute_tick"] <= dead and c["command"]["action"] == "drive")
                x, y = at["position"]
                out.append(moment(point, "no_return",
                                  "From here the lander is out of reach for the rest of the day: {:.0f} m out, {} ticks left, "
                                  "battery {}. It drove on: {} more drives.".format(
                                      truth.distance_home(at), ticks_left, percent(at["battery"], cap), drives),
                                  "One tick earlier, turning for home, waiting for the sun when short, would still have "
                                  "reached the lander.", path=truth.home_path(x, y), open=False))
                out.append(moment(dead, "lost",
                                  "Battery flat {:.0f} m from the lander with {} samples worth {:.2f} of this site: the site "
                                  "scores 0.".format(metres, n, share),
                                  "The reference here never ran its battery below {}.".format(percent(ref_min, cap))
                                  if ref_min is not None else ""))
        else:
            n, value = truth.carried(truth.horizon)
            metres = truth.distance_home(final)
            point = 0 if last is None else last + 1
            if point <= truth.horizon:
                at = states[point]
                x, y = at["position"]
                stops = len([t for t in truth.events("safety_stop") if t <= point])
                out.append(moment(point, "no_return",
                                  "The last tick from which the lander is still in reach passes: {:.0f} m out, battery {}{}.".format(
                                      truth.distance_home(at), percent(at["battery"], cap),
                                      ", after {} stops on steep ground".format(stops) if stops >= MANY else ""),
                                  "Leaving for home earlier would have kept the whole value of its samples.",
                                  path=truth.home_path(x, y), open=False))
            out.append(moment(truth.horizon, "away",
                              "Ended {:.0f} m from the lander, outside its {:.0f} m ring: its {} samples count half, {:.2f} "
                              "instead of {:.2f}.".format(metres, truth.config["base_radius"], n,
                                                          value / truth.max_value / 2, value / truth.max_value),
                              "The reference was home with ticks to spare." if reference is not None else ""))
    else:
        low = min(states, key=lambda s: s["battery"])
        if low["battery"] < CLOSE_SHARE * cap:
            out.append(moment(low["tick"], "close",
                              "Battery down to {}: one more drive could have ended the site.".format(percent(low["battery"], cap)),
                              "The reference's lowest here: {}.".format(percent(ref_min, cap)) if ref_min is not None else ""))
    stops = truth.events("safety_stop")
    if len(stops) >= MANY:
        out.append(moment(stops[0], "steep",
                          "Drove onto ground steeper than the {:.0f}% tilt limit: {} safety stops at this site, each one "
                          "clearing every queued command.".format(truth.replay["physics"]["max_tilt"] * 100, len(stops)),
                          "The reference stopped {} times here: it plans around steep ground.".format(
                              len(reference.events("safety_stop"))) if reference is not None else ""))
    misses = truth.events("sample_failed")
    if len(misses) >= MANY:
        t = misses[0]
        x, y = states[t]["position"]
        done = {s["target_id"] for s in truth.samples if s["tick"] < t}
        near = min((math.hypot(target["x"] - x, target["y"] - y) for target in truth.world["targets"]
                    if target["id"] not in done and target["appear_tick"] <= t), default=None)
        where = " {} m from the nearest target; it must be within {:.1f} m".format(
            "{:.1f}".format(near) if near >= truth.config["target_radius"] + 0.1 else "{:.2f}".format(near),
            truth.config["target_radius"]) if near is not None else ""
        out.append(moment(t, "misses",
                          "Sampled{}. {} missed samples at this site, each costing {:.0f} battery and a tick.".format(
                              where, len(misses), truth.config["sample_cost"]),
                          "The reference missed {} here: it samples where it predicts the rover will be when the command "
                          "lands.".format(len(reference.events("sample_failed"))) if reference is not None else ""))
    return out


def reference_moments(run_id: str, truth: Truth) -> List[Dict[str, Any]]:
    """The reference's own choices: waiting for the sun, and turning for home."""
    out: List[Dict[str, Any]] = []
    states, cap, commands = truth.states, truth.capacity, truth.replay["commands"]
    # the waits it makes away from the lander with a low battery, in clusters no more than 15 ticks apart
    waits = sorted(c["execute_tick"] for c in commands if c["command"]["action"] == "wait"
                   and states[c["execute_tick"]]["battery"] < 0.15 * cap
                   and not truth.at_base(*states[c["execute_tick"]]["position"]))
    clusters: List[List[int]] = []
    for t in waits:
        if clusters and t - clusters[-1][-1] <= 15:
            clusters[-1].append(t)
        else:
            clusters.append([t])
    if clusters:
        cluster = clusters[0]
        state = states[cluster[0]]
        x, y = state["position"]
        out.append({"t": cluster[0], "run": run_id, "kind": "ref_wait", "focus": [round(x, 1), round(y, 1)],
                    "did": "Battery {}: it waits a tick whenever the next drive would take it under its reserve, {} times "
                           "in the next {} ticks, and drives on what the sun pays.".format(
                               percent(state["battery"], cap), len(cluster), cluster[-1] - cluster[0] + 1),
                    "better": "Its plan checks the battery leg by leg against the sun's curve, so it never runs low "
                              "on the way."})
    if truth.samples and truth.died is None and truth.at_base(*states[-1]["position"]):
        last = truth.samples[-1]["tick"]
        home = next((s["tick"] for s in states[last:] if truth.at_base(*s["position"])), truth.horizon)
        state = states[last]
        x, y = state["position"]
        n, value = truth.carried(last)
        out.append({"t": last, "run": run_id, "kind": "ref_home", "focus": [round(x, 1), round(y, 1)],
                    "did": "Its last sample, then home: {} samples worth {:.2f} of this site, battery {}.".format(
                        n, value / truth.max_value, percent(state["battery"], cap)),
                    "better": "It reaches the lander at tick {}, {} ticks before the end of the day.".format(
                        home, truth.horizon - home),
                    "path": truth.home_path(x, y), "open": True})
    return out


# what the second line of each kind of moment answers
BETTER = {"lost": "What would have saved it", "no_return": "What would have saved it", "away": "The reference",
          "close": "The reference", "steep": "The reference", "misses": "The reference",
          "ref_wait": "Why it works", "ref_home": "Why it works"}


def moments(loaded: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every moment of one page, in time order. `loaded` holds runs as build_traverse.load_run returns them."""
    truths = {run["source"]: Truth(run["replay"]) for run in loaded}
    reference = next((run for run in loaded if run["meta"].get("kind") == "reference"), None)
    ref_truth = truths[reference["source"]] if reference is not None else None
    out: List[Dict[str, Any]] = []
    for run in loaded:
        if run is reference:
            out.extend(reference_moments(run["source"], ref_truth))
        else:
            out.extend(run_moments(run["source"], run["meta"].get("label") or run["source"], truths[run["source"]], ref_truth))
    for item in out:
        heading = BETTER[item["kind"]]
        if item["kind"] == "lost" and not item.get("open"):
            heading = "The reference"
        item["better_title"] = heading if item["better"] else ""
    out.sort(key=lambda item: (item["t"], item["kind"] != "no_return", item["run"]))
    return out
