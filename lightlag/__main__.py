"""Local JSON-lines runner. This transport is not an agent security boundary."""

import argparse
import json
from pathlib import Path
import sys

from . import Config, Environment
from .model import finite_number


def dispatch(env, request):
    if not isinstance(request, dict) or set(request) - {"id", "method", "params"}:
        raise ValueError("request must be an object with method, optional params and optional id")
    request_id = request.get("id")
    if request_id is not None and type(request_id) not in (str, int):
        raise ValueError("id must be a string, integer or null")
    methods = {
        "rules": (env.rules, set(), set()),
        "map": (env.map, set(), set()),
        "telemetry_log": (env.telemetry_log, set(), set()),
        "uplink": (env.uplink, {"commands"}, {"commands"}),
        "advance": (env.advance, {"ticks"}, set()),
    }
    method = request.get("method")
    if not isinstance(method, str) or method not in methods:
        raise ValueError("unknown public method; use rules, map, telemetry_log, uplink or advance")
    handler, allowed, required = methods[method]
    params = request.get("params", {})
    if not isinstance(params, dict) or set(params) - allowed or required - set(params):
        raise ValueError(f"invalid parameters for {method}; allowed: {', '.join(sorted(allowed)) or 'none'}")
    return handler(**params)


def reject_nonfinite(value):
    raise ValueError("JSON numbers must be finite")


def parse_finite_float(value):
    return finite_number(float(value), "JSON number")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run one local Lightlag episode over JSON lines.")
    parser.add_argument("--seed", type=int, default=0, help="evaluator-owned episode seed")
    parser.add_argument("--delay", type=int, default=3, help="one-way delay in complete ticks")
    parser.add_argument("--ticks", type=int, default=80, help="fixed episode horizon")
    parser.add_argument("--result", type=Path, help="write final evaluator score to a new JSON file")
    parser.add_argument("--replay", type=Path, help="write hidden evaluator replay to a new JSON file")
    args = parser.parse_args(argv)
    outputs = [path.expanduser().resolve() for path in (args.result, args.replay) if path is not None]
    if len(set(outputs)) != len(outputs):
        parser.error("result and replay must use different output paths")
    for path in outputs:
        if path.exists() or not path.parent.is_dir():
            parser.error("output files must be new and their parent directories must exist")
    try:
        env = Environment(seed=args.seed, config=Config(delay_ticks=args.delay, max_ticks=args.ticks))
    except ValueError as error:
        parser.error(str(error))

    for line in sys.stdin:
        if not line.strip():
            continue
        request_id = None
        try:
            request = json.loads(line, parse_constant=reject_nonfinite, parse_float=parse_finite_float)
            if isinstance(request, dict) and type(request.get("id")) in (str, int):
                request_id = request["id"]
            result = dispatch(env, request)
            reply = {"id": request_id, "ok": True, "result": result}
        except ValueError as error:
            reply = {"id": request_id, "ok": False, "error": str(error)}
        except RecursionError:
            reply = {"id": request_id, "ok": False, "error": "JSON nesting is too deep"}
        print(json.dumps(reply, allow_nan=False), flush=True)

    if outputs:
        try:
            # Validate completion before creating either output file.
            result = env.evaluate()
            artifacts = ((args.result, result), (args.replay, env.replay() if args.replay else None))
            for path, artifact in artifacts:
                if path is not None:
                    with path.expanduser().open("x", encoding="utf-8") as output:
                        json.dump(artifact, output, indent=2, sort_keys=True, allow_nan=False)
                        output.write("\n")
        except (ValueError, OSError) as error:
            print(f"lightlag: {error}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
