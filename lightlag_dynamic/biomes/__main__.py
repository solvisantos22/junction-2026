"""Choose a biome and play one episode over JSON lines, or list the biomes.

  python3 -m lightlag_dynamic.biomes --list
  python3 -m lightlag_dynamic.biomes --biome troy_crust --profile rush_noisy --seed 7 --delay 3 < script.jsonl
  python3 -m lightlag_dynamic.biomes --biome troy_crust+relay_pass --seed 7 --result /tmp/r.json < script.jsonl

Same protocol as `python3 -m lightlag_dynamic` (one JSON request per line on stdin, one reply
per line on stdout, only the five public methods dispatchable), plus --biome. The default
biome, main_mars, is that runner's environment unchanged.
"""

import argparse
import json
from pathlib import Path
import sys

from lightlag.__main__ import dispatch, parse_finite_float, reject_nonfinite
from lightlag_dynamic.missions import PROFILES

from .catalog import BIOME_IDS, CATALOG, MAIN, parse_biome
from .environment import make_biome_env


def listing():
    lines = ["| Biome | Name | Kind | Modelled on | Published rule | Settings |", "|---|---|---|---|---|---|"]
    for name in BIOME_IDS:
        entry = CATALOG[name]
        lines.append(f"| `{name}` | {entry['name']} | {entry['kind']} | {entry['modelled_on']} | {entry['rule']} "
                     f"| `{json.dumps(entry['settings'])}` |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m lightlag_dynamic.biomes",
                                     description="Run one Lightlag episode in a chosen biome over JSON lines.")
    parser.add_argument("--list", action="store_true", help="list the biomes and exit")
    parser.add_argument("--biome", default=MAIN, help="one of: " + ", ".join(BIOME_IDS) + "; mix with +")
    parser.add_argument("--profile", default="rush", choices=list(PROFILES))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--delay", type=int, default=3)
    parser.add_argument("--ticks", type=int, default=None, help="horizon; default: the profile's own")
    parser.add_argument("--noise-level", type=float, default=1.0,
                        help="multiplies the sensing noise and drift of the noisy profiles")
    parser.add_argument("--result", type=Path, help="write the final score to a new JSON file")
    parser.add_argument("--replay", type=Path, help="write the evaluator replay to a new JSON file")
    args = parser.parse_args(argv)
    if args.list:
        print(listing())
        return 0
    try:
        parse_biome(args.biome)
    except ValueError as error:
        parser.error(str(error))
    for path in (args.result, args.replay):
        if path is not None and (path.exists() or not path.parent.is_dir()):
            parser.error("output files must be new and their parent directories must exist")
    env = make_biome_env(args.biome, args.seed, args.delay, args.profile, horizon=args.ticks,
                         noise_level=args.noise_level)
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
            print(f"lightlag_dynamic.biomes: {error}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
