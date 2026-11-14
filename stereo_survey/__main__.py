"""Generate, solve or replay a stereo mission without third-party packages."""

import argparse
import json
from pathlib import Path

from .mission import PROFILES, generate
from .search import Problem, exact
from .verify import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generator = commands.add_parser("generate")
    generator.add_argument("--seed", type=int, required=True)
    generator.add_argument("--profile", choices=PROFILES, default="compact")
    generator.add_argument("--output", type=Path, required=True)
    solver = commands.add_parser("solve")
    solver.add_argument("mission", type=Path)
    solver.add_argument("--output", type=Path, required=True)
    solver.add_argument("--max-local", type=int, default=10_000)
    solver.add_argument("--max-joint", type=int, default=2_000_000)
    validator = commands.add_parser("verify")
    validator.add_argument("mission", type=Path)
    validator.add_argument("plan", type=Path)
    args = parser.parse_args()
    if args.command == "generate":
        result = generate(args.seed, args.profile)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    elif args.command == "solve":
        if min(args.max_local, args.max_joint) < 1:
            parser.error("search limits must be positive")
        result = exact(Problem(json.loads(args.mission.read_text())), max_local=args.max_local, max_joint=args.max_joint)
        args.output.write_text(json.dumps(result["plan"], indent=2) + "\n")
        print(json.dumps({key: value for key, value in result.items() if key not in ("plan", "mask")}, indent=2))
        raise SystemExit(0 if result["proven_optimal"] else 2)
    else:
        result = verify(json.loads(args.mission.read_text()), json.loads(args.plan.read_text()))
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
