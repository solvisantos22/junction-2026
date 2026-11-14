"""JSON-lines runner for one dynamic episode, using the team runner's own dispatch.

Same protocol as `python3 -m lightlag` (see lightlag/README.md), plus --profile:

  python3 -m lightlag_dynamic --profile rush --seed 7 --delay 3 --result /tmp/r.json < script.jsonl

This is the hook a real agent harness can drive: one JSON request per line on stdin,
one JSON reply per line on stdout, only the five public methods dispatchable.
"""

import argparse
import json
from pathlib import Path
import sys

from lightlag import Config
from lightlag.__main__ import dispatch, parse_finite_float, reject_nonfinite

from .environment import DynamicEnvironment
from .missions import PROFILES


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run one dynamic Lightlag episode over JSON lines.")
    parser.add_argument("--profile", default="rush", choices=list(PROFILES))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--delay", type=int, default=3)
    parser.add_argument("--ticks", type=int, default=None, help="horizon; default: the profile's own")
    parser.add_argument("--noise-level", type=float, default=1.0,
                        help="multiplies the sensing noise and drift of the noisy profiles")
    parser.add_argument("--bumpiness", type=float, default=0.0,
                        help="experimental: share of rough cells that can spin the wheels (0 = off)")
    parser.add_argument("--result", type=Path, help="write the final score to a new JSON file")
    parser.add_argument("--replay", type=Path, help="write the evaluator replay to a new JSON file")
    args = parser.parse_args(argv)
    for path in (args.result, args.replay):
        if path is not None and (path.exists() or not path.parent.is_dir()):
            parser.error("output files must be new and their parent directories must exist")
    ticks = PROFILES[args.profile][4] if args.ticks is None else args.ticks
    env = DynamicEnvironment(seed=args.seed, config=Config(delay_ticks=args.delay, max_ticks=ticks),
                             profile=args.profile, noise_level=args.noise_level,
                             bumpiness=args.bumpiness)
    for line in sys.stdin:
        if not line.strip():
            continue
        request_id = None
        try:
            request = json.loads(line, parse_constant=reject_nonfinite, parse_float=parse_finite_float)
            if isinstance(request, dict) and type(request.get("id")) in (str, int):
                request_id = request["id"]
            reply = {"id": request_id, "ok": True, "result": dispatch(env, request)}
        except ValueError as error:
            reply = {"id": request_id, "ok": False, "error": str(error)}
        except RecursionError:
            reply = {"id": request_id, "ok": False, "error": "JSON nesting is too deep"}
        print(json.dumps(reply, allow_nan=False), flush=True)
    if args.result or args.replay:
        try:
            for path, artifact in ((args.result, env.evaluate()),
                                   (args.replay, env.replay() if args.replay else None)):
                if path is not None:
                    with path.open("x", encoding="utf-8") as output:
                        json.dump(artifact, output, indent=2, sort_keys=True, allow_nan=False)
        except (ValueError, OSError) as error:
            print(f"lightlag_dynamic: {error}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
