"""Compare the reference and the scripted baselines on the Lightlag simulator.

    python3 -m lightlag_controllers.pilot                      # default map, delays 0 and 3
    python3 -m lightlag_controllers.pilot --maps seeded --delays 0 1 3 6
    python3 -m lightlag_controllers.pilot --maps seeded --target-radius 0.4 --noise 0.08 --sand-slip 0.15 0.6

Every controller uses only the five public methods. Slip seeds are shared across
controllers, so rows within one delay are directly comparable.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import random
import statistics
import sys
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

import lightlag.environment as sim_environment
import lightlag.model as sim_model
from lightlag import Config, Environment, Rect, Target, World

from .controllers import ALL_STRATEGIES, Strategy, Tuning, make
from .runner import run_episode

EnvFactory = Callable[[int, int], Any]  # (seed, delay) -> environment


def seeded_world(seed: int) -> World:
    """A varied 40 x 40 m map: three hazards, two sand patches, three targets near base.

    The simulator's own default map is fixed. These maps check that results do not
    depend on that one layout.
    """
    rng = random.Random("lightlag-pilot-map:{}".format(seed))
    base = (20.0, 20.0)

    def rect(cx: float, cy: float, w: float, h: float) -> Rect:
        return Rect(
            round(max(0.0, cx - w / 2), 2), round(max(0.0, cy - h / 2), 2),
            round(min(40.0, cx + w / 2), 2), round(min(40.0, cy + h / 2), 2),
        )

    def near(r: Rect, x: float, y: float, margin: float) -> bool:
        return r.x1 - margin <= x <= r.x2 + margin and r.y1 - margin <= y <= r.y2 + margin

    hazards: List[Rect] = []
    while len(hazards) < 3:
        cx, cy = rng.uniform(6, 34), rng.uniform(6, 34)
        long_side, short_side = rng.uniform(2, 5), rng.uniform(0.6, 1.2)
        candidate = rect(cx, cy, long_side, short_side) if rng.random() < 0.5 else rect(cx, cy, short_side, long_side)
        if not near(candidate, base[0], base[1], 2.0):
            hazards.append(candidate)
    sand = [rect(rng.uniform(6, 34), rng.uniform(6, 34), rng.uniform(5, 11), rng.uniform(5, 11)) for _ in range(2)]
    targets: List[Target] = []
    values = (3.0, 2.0, 1.0)
    while len(targets) < 3:
        angle, radius = rng.uniform(0, 2 * math.pi), rng.uniform(6, 12)
        x = round(base[0] + radius * math.cos(angle), 2)
        y = round(base[1] + radius * math.sin(angle), 2)
        if any(near(h, x, y, 1.0) for h in hazards):
            continue
        if any(math.hypot(x - t.x, y - t.y) < 4.0 for t in targets):
            continue
        targets.append(Target("t{}".format(len(targets) + 1), x, y, values[len(targets)]))
    return World(40.0, 40.0, base, tuple(sand), tuple(hazards), tuple(targets))


@contextlib.contextmanager
def physics_overrides(
    noise: Optional[float] = None, sand_slip: Optional[Tuple[float, float]] = None
) -> Iterator[None]:
    """Experiment-only: temporarily change the simulator's slip noise and sand range.

    These are module constants in `lightlag`, not `Config` fields, so the only way to
    try other values without editing the simulator is to patch them for the run.
    The simulator's `rules()` reports the patched values, so controllers stay honest.
    """
    saved = (sim_model.NOISE, sim_environment.NOISE, dict(sim_model.SLIP_RANGES))
    try:
        if noise is not None:
            sim_model.NOISE = sim_environment.NOISE = noise
        if sand_slip is not None:
            sim_model.SLIP_RANGES["sand"] = (float(sand_slip[0]), float(sand_slip[1]))
        yield
    finally:
        sim_model.NOISE, sim_environment.NOISE = saved[0], saved[1]
        sim_model.SLIP_RANGES.clear()
        sim_model.SLIP_RANGES.update(saved[2])


def environment_factory(maps: str = "fixed", **config: Any) -> EnvFactory:
    def build(seed: int, delay: int) -> Environment:
        world = World() if maps == "fixed" else seeded_world(seed)
        return Environment(seed=seed, config=Config(delay_ticks=delay, **config), world=world)

    return build


def run_grid(
    factory: EnvFactory,
    seeds: Sequence[int],
    delays: Sequence[int],
    strategies: Sequence[Strategy] = ALL_STRATEGIES,
    tuning: Optional[Tuning] = None,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for delay in delays:
        for strategy in strategies:
            for seed in seeds:
                outcome = run_episode(factory(seed, delay), make(strategy, tuning))
                rows.append({
                    "delay": delay, "controller": strategy.name, "seed": seed,
                    "raw_score": outcome["raw_score"], "max_value": outcome["max_value"],
                    "sampled": len(outcome["sampled"]), "alive": outcome["alive"],
                    "at_base": outcome["at_base"], "commands": outcome["commands_sent"],
                    "rejected": outcome["rejected_uplinks"],
                })
    return rows


def summarise(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    names = list(dict.fromkeys(r["controller"] for r in rows))
    for delay in sorted({r["delay"] for r in rows}):
        reference = [r["raw_score"] for r in rows if r["delay"] == delay and r["controller"] == "reference"]
        reference_mean = statistics.fmean(reference) if reference else 0.0
        for name in names:
            group = [r for r in rows if r["delay"] == delay and r["controller"] == name]
            if not group:
                continue
            scores = [r["raw_score"] for r in group]
            summary.append({
                "delay": delay,
                "controller": name,
                "mean": statistics.fmean(scores),
                "min": min(scores),
                "max": max(scores),
                "share_of_reference": statistics.fmean(scores) / reference_mean if reference_mean else None,
                "alive": sum(r["alive"] for r in group) / len(group),
                "at_base": sum(r["at_base"] for r in group) / len(group),
                "commands": statistics.fmean(r["commands"] for r in group),
                "episodes": len(group),
            })
    return summary


def format_table(summary: Sequence[Dict[str, Any]]) -> str:
    lines = ["delay  controller          mean   min   max  vs ref  alive  at base  commands"]
    last_delay = None
    for row in summary:
        if last_delay is not None and row["delay"] != last_delay:
            lines.append("")
        last_delay = row["delay"]
        share = "   n/a" if row["share_of_reference"] is None else "{:5.0f}%".format(100 * row["share_of_reference"])
        lines.append("{:>5}  {:<18} {:5.2f} {:5.2f} {:5.2f}  {}  {:4.0f}%  {:6.0f}%  {:8.1f}".format(
            row["delay"], row["controller"], row["mean"], row["min"], row["max"], share,
            100 * row["alive"], 100 * row["at_base"], row["commands"],
        ))
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Lightlag reference and baselines on shared seeds.")
    parser.add_argument("--seeds", type=int, default=10, help="number of seeds, starting at 0")
    parser.add_argument("--delays", type=int, nargs="+", default=[0, 3])
    parser.add_argument("--maps", choices=("fixed", "seeded"), default="fixed")
    parser.add_argument("--ticks", type=int, default=None, help="episode length (simulator default 80)")
    parser.add_argument("--battery", type=float, default=None, help="initial battery (default 100)")
    parser.add_argument("--target-radius", type=float, default=None, help="sampling radius in metres (default 0.75)")
    parser.add_argument("--noise", type=float, default=None, help="experiment: per-drive slip noise (default 0.02)")
    parser.add_argument("--sand-slip", type=float, nargs=2, default=None, metavar=("LOW", "HIGH"),
                        help="experiment: sand slip range (default 0.20 0.45)")
    parser.add_argument("--json", default=None, help="write per-episode rows and the summary here")
    args = parser.parse_args(argv)

    config: Dict[str, Any] = {}
    if args.ticks is not None:
        config["max_ticks"] = args.ticks
    if args.battery is not None:
        config["initial_battery"] = args.battery
    if args.target_radius is not None:
        config["target_radius"] = args.target_radius
    with physics_overrides(args.noise, tuple(args.sand_slip) if args.sand_slip else None):
        rows = run_grid(environment_factory(args.maps, **config), range(args.seeds), args.delays)
    summary = summarise(rows)
    settings = {"maps": args.maps, "seeds": args.seeds, "config": config, "noise": args.noise, "sand_slip": args.sand_slip}
    print("Lightlag pilot: {}".format(json.dumps(settings)))
    print(format_table(summary))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as stream:
            json.dump({"settings": settings, "rows": rows, "summary": summary}, stream, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
