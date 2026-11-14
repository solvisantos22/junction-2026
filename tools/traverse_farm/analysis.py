"""Could the rover still have got home? A tick-by-tick check of a finished mission, on the evaluator's side.

From a mission's replay, hidden truth included (each terrain's true slip, the panel's true efficiency),
`home_margin` asks at every tick: from where the rover really was, with the battery it really had, could
a drive home over the cheapest ground have reached the lander by the last tick, waiting for the sun on
the way if the battery ran low? The last tick at which the answer is yes is the last moment the mission
could still have ended at the lander. The tick after it is the **point of no return**: from there the
best outcome left was "alive elsewhere", half the score, and only if the rover stopped in time.

The drive model is the reference planner's (`lightlag_traverse.planning.Ground`: the published physics,
fed the true slip), which matches the simulator to about a tenth of a tick per leg on the pilot's legs.
The check leans in the rover's favour: it ignores the 3-tick command delay and checks the battery only
at the end of the drive home, never on the way. So "past the point of no return" means getting home
was already out of reach even on those generous terms. It says what was physically possible, not
what the program could have known.

`summarise` turns rows holding this analysis into one line of medians per player.
Standard library only.
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional


def home_margin(replay: Dict[str, Any]) -> Dict[str, Any]:
    from lightlag_traverse.planning import INF, Ground, Sun
    from lightlag_traverse.surface import Surface

    world, config, hidden = replay["world"], replay["config"], replay["hidden"]
    surface = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])
    ground = Ground(surface, replay["physics"], hidden["slip_base"])
    bx, by = world["base"]
    field = ground.field(ground.node(bx, by))
    sun = Sun(config, hidden["solar_efficiency"])
    horizon, radius = config["max_ticks"], config["base_radius"]
    total, idle, capacity = sun.total, sun.idle, sun.capacity

    def arrival(t: int, battery: float, ticks: float, energy: float) -> Optional[int]:
        """The tick the rover is home if it leaves at tick t, waiting a tick at a time while the sun is short."""
        need = int(math.ceil(ticks - 1e-9))
        while t + need <= horizon:
            if battery + total[t + need] - total[t] - idle * need - energy > 0.0:
                return t + need
            gain = total[t + 1] - total[t] - idle
            if gain <= 0.0:
                return None
            battery, t = min(capacity, battery + gain), t + 1
        return None

    def way_home(x: float, y: float):
        """Ticks and energy from (x, y) to the lander over the cheapest ground, or None."""
        node = ground.node(x, y)
        if node is None or field.ticks[node] == INF:
            return None
        px, py = ground.point(node)
        hop = ground.straight(x, y, px, py, tilt=1.0) or (math.hypot(px - x, py - y) / ground.max_metres, 0.0)
        return hop[0] + field.ticks[node], hop[1] + field.energy[node]

    states = replay["states"]
    possible = []
    for state in states:
        x, y = state["position"]
        if not state["alive"]:
            possible.append(False)
        elif math.hypot(x - bx, y - by) <= radius:
            possible.append(True)
        else:
            leg = way_home(x, y)
            possible.append(leg is not None and arrival(state["tick"], state["battery"], *leg) is not None)

    final = states[-1]
    fx, fy = final["position"]
    end = "lost" if not final["alive"] else ("lander" if math.hypot(fx - bx, fy - by) <= radius else "away")
    died = next((s["tick"] for s in states if not s["alive"]), None)
    out: Dict[str, Any] = {"end": end, "died_tick": died, "point_of_no_return": None,
                           # waiting always charges the battery under these rules: no rover had to run flat
                           "waiting_always_charges": min(sun.rate[t] - idle for t in range(1, horizon + 1)) > 0}
    if end == "lander":
        return out
    last = max((i for i, ok in enumerate(possible) if ok), default=None)
    point = 0 if last is None else states[last]["tick"] + 1
    if point > horizon:
        return out
    at = states[point]
    px, py = at["position"]
    stop = died if died is not None else horizon
    executed = [c for c in replay["commands"] if point < c["execute_tick"] <= stop]
    out.update(
        point_of_no_return=point,
        ticks_left=horizon - point,
        battery=round(at["battery"], 2),
        metres_from_lander=round(math.hypot(px - bx, py - by), 1),
        metres_from_lander_at_end=round(math.hypot(fx - bx, fy - by), 1),
        drives_after=sum(c["command"]["action"] == "drive" for c in executed),
        samples_after=len(final["sampled_targets"]) - len(at["sampled_targets"]),
        ticks_to_death=None if died is None else died - point,
    )
    return out


def _median(values: List[Optional[float]]) -> Optional[float]:
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 1) if values else None


def summarise(rows: List[Dict[str, Any]], candidate: str) -> Dict[str, Any]:
    """Per player: how its rovers ended and, for lost and stranded rovers, where the way home closed.

    A lost rover either ran flat while the way home was still open (its point of no return is the tick
    it died), or it had already passed the point of no return and ran flat later. A stranded ("away")
    rover passed the point of no return and finished alive elsewhere."""
    mine = [row["home"] for row in rows if row.get("candidate") == candidate and row.get("home")]
    lost = [h for h in mine if h["end"] == "lost"]
    away = [h for h in mine if h["end"] == "away"]
    open_at_death = [h for h in lost if h["point_of_no_return"] == h["died_tick"]]
    closed_before = [h for h in lost if h["point_of_no_return"] is not None and h["point_of_no_return"] < h["died_tick"]]
    return {
        "worlds": len(mine),
        "lander": sum(h["end"] == "lander" for h in mine),
        "away": len(away),
        "lost": len(lost),
        "lost_home_still_open": len(open_at_death),
        "lost_home_open_metres": _median([h["metres_from_lander"] for h in open_at_death]),
        "lost_after_point": len(closed_before),
        "lost_after_point_ticks": _median([h["ticks_to_death"] for h in closed_before]),
        "lost_after_point_drives": _median([h["drives_after"] for h in closed_before]),
        "away_point_tick": _median([h["point_of_no_return"] for h in away]),
        "away_ticks_left": _median([h["ticks_left"] for h in away]),
        "away_samples_after": _median([h["samples_after"] for h in away]),
        "away_metres_at_end": _median([h["metres_from_lander_at_end"] for h in away]),
        "waiting_always_charges": all(h["waiting_always_charges"] for h in mine) if mine else None,
    }


def format_summary(table: Dict[str, Dict[str, Any]]) -> str:
    head = "{:36s} {:>6s} {:>6s} {:>4s} {:>11s} {:>13s} {:>11s} {:>13s}".format(
        "point of no return", "worlds", "lander", "lost", "  home open", " point passed", "away", "")
    sub = "{:36s} {:>6s} {:>6s} {:>4s} {:>11s} {:>13s} {:>11s} {:>13s}".format(
        "", "", "", "", "n / metres", "n/ticks/drives", "n / at tick", "left / samples")
    lines = [head, sub]
    dash = lambda v: "-" if v is None else ("{:g}".format(v))  # noqa: E731
    for name, s in table.items():
        lines.append("{:36s} {:>6d} {:>6d} {:>4d} {:>11s} {:>13s} {:>11s} {:>13s}".format(
            name[:36], s["worlds"], s["lander"], s["lost"],
            "{} / {}".format(s["lost_home_still_open"], dash(s["lost_home_open_metres"])),
            "{}/{}/{}".format(s["lost_after_point"], dash(s["lost_after_point_ticks"]), dash(s["lost_after_point_drives"])),
            "{} / {}".format(s["away"], dash(s["away_point_tick"])),
            "{} / {}".format(dash(s["away_ticks_left"]), dash(s["away_samples_after"]))))
    lines.append("home open: lost while the way home was still open (median metres out). point passed: lost after "
                 "the point of no return (median ticks from it to the end of the battery, drives sent after it). "
                 "away: stranded, median tick of the point, ticks then left, samples taken after it.")
    return "\n".join(lines)
