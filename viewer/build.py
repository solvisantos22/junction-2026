#!/usr/bin/env python3
"""Build a standalone replay page: the viewer with replays embedded.

    python3 viewer/build.py --out viewer/demo.html \
        "Reference=docs/lightlag-runs/reference-seed7-delay3/artifacts/evaluator/replay.json" \
        "Forgets commands in transit=policy:stale_telemetry"

Each argument is LABEL=SOURCE. SOURCE is a replay.json path, or `policy:NAME` to
record a scripted policy from lightlag_controllers on the simulator (use --seed
and --delay). The result opens by double-click and needs no network.

A replay contains the true rover states and the hidden slip values. It is
evaluator-side material: fine for a demo, never for an agent's container.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
MARKER = '<script id="embedded-replays" type="application/json">[]</script>'


def record(policy: str, seed: int, delay: int) -> Dict[str, Any]:
    """Play one scripted policy on the simulator and return its replay."""
    from lightlag import Config, Environment
    from lightlag_controllers import ALL_STRATEGIES, drive, make

    strategies = {strategy.name: strategy for strategy in ALL_STRATEGIES}
    if policy not in strategies:
        raise SystemExit("unknown policy {!r}; choose from {}".format(policy, ", ".join(sorted(strategies))))
    env = Environment(seed=seed, config=Config(delay_ticks=delay))
    controller = make(strategies[policy])
    drive(env, controller)
    # Where the controller believed the rover would be, per tick it planned for.
    # Kept beside the replay: the simulator knows nothing about a controller's beliefs.
    belief = {note["for_tick"]: list(note["believed"]) for note in controller.trace}
    return {"replay": env.replay(), "belief": [{"tick": t, "position": p} for t, p in sorted(belief.items())]}


def load(source: str, seed: int, delay: int) -> Dict[str, Any]:
    if source.startswith("policy:"):
        return record(source[len("policy:"):], seed, delay)
    with open(source, encoding="utf-8") as stream:
        replay = json.load(stream)
    if "states" not in replay or "world" not in replay:
        raise SystemExit("{} is not a Lightlag replay".format(source))
    return {"replay": replay, "belief": []}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("entries", nargs="+", metavar="LABEL=SOURCE")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=7, help="seed for policy: sources")
    parser.add_argument("--delay", type=int, default=3, help="delay for policy: sources")
    args = parser.parse_args(argv)
    embedded: List[Dict[str, Any]] = []
    for entry in args.entries:
        label, separator, source = entry.partition("=")
        if not separator or not label or not source:
            parser.error("expected LABEL=SOURCE, got {!r}".format(entry))
        embedded.append(dict(load(source, args.seed, args.delay), label=label))
    template = (REPO / "viewer" / "template.html").read_text(encoding="utf-8")
    if template.count(MARKER) != 1:
        raise SystemExit("template.html has lost its embedding marker")
    # "</" inside JSON would end the script element early in an HTML parser.
    payload = json.dumps(embedded, separators=(",", ":")).replace("</", "<\\/")
    page = template.replace(MARKER, '<script id="embedded-replays" type="application/json">{}</script>'.format(payload))
    args.out.write_text(page, encoding="utf-8")
    print("wrote {} with {} replay(s), {:.0f} kB".format(args.out, len(embedded), len(page) / 1000))
    return 0


if __name__ == "__main__":
    sys.exit(main())
