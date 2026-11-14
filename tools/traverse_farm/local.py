#!/usr/bin/env python3
"""The farm's commands on a local process pool: small runs and checks, no Modal account needed.

    python3 tools/traverse_farm/local.py evaluate --policies pilot,greedy,straight --seeds 600-603
    python3 tools/traverse_farm/local.py search --generations 2 --population 4 --block 3 \\
        --search-seeds 100-105 --select 400-401 --confirm 600-602 --out /tmp/farm-check

Program policies are refused here: they run model-written code, which belongs in Modal's
isolated containers. Standard library only.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The Traverse code that plays: the repository's, or another checkout given in TRAVERSE_SOURCE.
SOURCE = Path(os.environ.get("TRAVERSE_SOURCE") or HERE.parent.parent).resolve()
# Order: the Traverse source, then tools/ (traverse_farm), then the repository (lightlag and the rest).
for path in (str(HERE.parent.parent), str(HERE.parent), str(SOURCE)):
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

from traverse_farm import jobs, search  # noqa: E402
from traverse_farm.common import format_table, format_versus, parse_policies, parse_seeds  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    ev = commands.add_parser("evaluate", help="several policies on the same worlds")
    ev.add_argument("--policies", default="pilot,greedy,straight")
    ev.add_argument("--seeds", default="600-603")
    ev.add_argument("--workers", type=int, default=4)
    ev.add_argument("--out", type=Path)
    ev.add_argument("--baseline", default="pilot", help="compare every other policy with this one, world by world")
    se = commands.add_parser("search", help="search the pilot's options, then confirm on unseen worlds")
    se.add_argument("--generations", type=int, default=2)
    se.add_argument("--population", type=int, default=4)
    se.add_argument("--block", type=int, default=3)
    se.add_argument("--elites", type=int, default=2)
    se.add_argument("--search-seeds", default="100-105")
    se.add_argument("--select", default="400-401")
    se.add_argument("--confirm", default="600-602")
    se.add_argument("--workers", type=int, default=4)
    se.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    run_many = lambda batch: jobs.local_map(batch, workers=args.workers)  # noqa: E731
    if args.command == "evaluate":
        policies = parse_policies(args.policies)
        if any(spec["policy"] == "program" for spec in policies.values()):
            parser.error("program policies run only on Modal (tools/traverse_farm/modal_app.py)")
        result = search.evaluate(run_many, policies, parse_seeds(args.seeds), out=args.out, baseline=args.baseline)
        print(format_table(result["table"]))
        if result["versus"]:
            print(format_versus(args.baseline, result["versus"]))
    else:
        search.search(run_many, jobs.pilot_defaults(), search_seeds=parse_seeds(args.search_seeds),
                      select_seeds=parse_seeds(args.select), confirm_seeds=parse_seeds(args.confirm),
                      generations=args.generations, population=args.population, block=args.block,
                      elites=args.elites, out=args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
