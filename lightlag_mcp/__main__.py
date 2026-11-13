"""Start a Lightlag MCP server for one episode.

    python -m lightlag_mcp --transport stdio --seed 7 --delay 3
    python -m lightlag_mcp --transport http --port 8000 --seed 7 --delay 3 --artifact-dir /evaluator/run1

The seed is chosen by whoever starts the server and is never revealed by a tool.
Settings may also come from the environment (LIGHTLAG_SEED, LIGHTLAG_DELAY,
LIGHTLAG_TICKS, LIGHTLAG_ARTIFACT_DIR). The evaluator token is read only from
LIGHTLAG_EVALUATOR_TOKEN, never from the command line, so it does not show up in
process listings.

When the server stops, it finishes the episode and writes the result, so a local
stdio run always leaves a score in the artifact directory.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
from typing import Optional, Sequence

from lightlag import Config

from .service import EpisodeService


def _env_int(name: str, default: Optional[int]) -> Optional[int]:
    value = os.environ.get(name)
    return default if value in (None, "") else int(value)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="lightlag_mcp", description="Serve one Lightlag episode over MCP.")
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--seed", type=int, default=_env_int("LIGHTLAG_SEED", None))
    parser.add_argument("--delay", type=int, default=_env_int("LIGHTLAG_DELAY", 3), help="signal delay in ticks")
    parser.add_argument("--ticks", type=int, default=_env_int("LIGHTLAG_TICKS", None), help="episode length")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--artifact-dir", default=os.environ.get("LIGHTLAG_ARTIFACT_DIR"),
                        help="evaluator-only directory for result.json, replay.json and transcript.jsonl")
    args = parser.parse_args(argv)
    if args.seed is None:
        parser.error("a seed is required (--seed or LIGHTLAG_SEED)")

    from .server import build_server  # imported late so --help works without the mcp package

    settings = {"delay_ticks": args.delay}
    if args.ticks is not None:
        settings["max_ticks"] = args.ticks
    service = EpisodeService(seed=args.seed, config=Config(**settings), artifact_dir=args.artifact_dir)
    server = build_server(service, evaluator_token=os.environ.get("LIGHTLAG_EVALUATOR_TOKEN") or None)

    def finish() -> None:
        result = service.finish()
        # stdout belongs to the protocol in stdio mode, so report on stderr.
        print("lightlag episode finished: raw_score={raw_score} sampled={sampled_targets} "
              "alive={alive} at_base={at_base} tool_calls={tool_calls}".format(**result), file=sys.stderr)

    def on_signal(signum: int, frame: object) -> None:
        # The HTTP server re-raises a stop signal after shutting down, which would
        # end the process before the `finally` below. Grade first, then exit.
        finish()
        sys.exit(0)

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    try:
        if args.transport == "stdio":
            server.run("stdio")
        else:
            server.run("streamable-http", host=args.host, port=args.port)
    finally:
        finish()
    return 0


if __name__ == "__main__":
    sys.exit(main())
