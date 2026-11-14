"""Start a Lightlag Live MCP server for one campaign.

    python -m lightlag_live --missions 9001:rush_noisy,9002:rush_noisy --noise-level 2 --transport stdio
    python -m lightlag_live --transport http --host 0.0.0.0 --port 8000 --artifact-dir /evaluator

The missions (seed:profile pairs) are chosen by whoever starts the server and are never
revealed by a tool. Settings may also come from the environment: LIGHTLAG_MISSIONS,
LIGHTLAG_DELAY, LIGHTLAG_TICKS, LIGHTLAG_SECONDS_PER_TICK, LIGHTLAG_NOISE_LEVEL,
LIGHTLAG_ARTIFACT_DIR, LIGHTLAG_TOKEN_FILE. The evaluator token is read only from
LIGHTLAG_EVALUATOR_TOKEN or generated into the token file, never from the command line.

When the server stops it finishes the campaign and writes the result, so a local run always
leaves a score in the artifact directory.
"""

from __future__ import annotations

import argparse
import os
import secrets
import signal
import sys
from typing import List, Optional, Sequence

from .campaign import CampaignService


def parse_missions(text: str) -> List[dict]:
    missions = []
    for part in text.split(","):
        seed, separator, profile = part.strip().partition(":")
        if not separator or not seed.lstrip("-").isdigit() or not profile:
            raise ValueError("missions look like 9001:rush_noisy,9002:rush; got {!r}".format(part))
        missions.append({"seed": int(seed), "profile": profile})
    return missions


def main(argv: Optional[Sequence[str]] = None) -> int:
    env = os.environ.get
    parser = argparse.ArgumentParser(prog="lightlag_live", description="Serve one Lightlag Live campaign over MCP.")
    parser.add_argument("--missions", default=env("LIGHTLAG_MISSIONS"),
                        help="comma-separated seed:profile pairs, played in this order")
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--delay", type=int, default=int(env("LIGHTLAG_DELAY") or 3), help="signal delay in ticks")
    parser.add_argument("--ticks", type=int, default=int(env("LIGHTLAG_TICKS") or 50), help="ticks per mission")
    parser.add_argument("--seconds-per-tick", type=float, default=float(env("LIGHTLAG_SECONDS_PER_TICK") or 1.0))
    parser.add_argument("--noise-level", type=float, default=float(env("LIGHTLAG_NOISE_LEVEL") or 1.0),
                        help="multiplies the published sensing noise and drift of the noisy profiles")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--artifact-dir", default=env("LIGHTLAG_ARTIFACT_DIR"),
                        help="evaluator-only directory for result.json and one replay per mission")
    parser.add_argument("--token-file", default=env("LIGHTLAG_TOKEN_FILE"),
                        help="HTTP only: write a freshly generated evaluator token here when "
                             "LIGHTLAG_EVALUATOR_TOKEN is not set, so no secret has to be configured")
    args = parser.parse_args(argv)
    if not args.missions:
        parser.error("missions are required (--missions or LIGHTLAG_MISSIONS)")
    try:
        missions = parse_missions(args.missions)
    except ValueError as failure:
        parser.error(str(failure))

    from .server import build_server  # late, so --help works without the mcp package

    service = CampaignService(missions, delay=args.delay, ticks=args.ticks,
                              seconds_per_tick=args.seconds_per_tick, noise_level=args.noise_level,
                              artifact_dir=args.artifact_dir)
    token = env("LIGHTLAG_EVALUATOR_TOKEN") or None
    if token is None and args.token_file and args.transport == "http":
        token = secrets.token_urlsafe(32)  # exists only inside this process's container
        os.makedirs(os.path.dirname(os.path.abspath(args.token_file)), exist_ok=True)
        descriptor = os.open(args.token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(token)
    server = build_server(service, evaluator_token=token, seconds_per_tick=args.seconds_per_tick)

    def finish() -> None:
        result = service.finish()
        # stdout belongs to the protocol in stdio mode, so report on stderr.
        print("lightlag live campaign finished: reward={:.6f} missions={} finished_by={} tool_calls={}".format(
            result["reward"], [round(m["reward"], 3) for m in result["missions"]], result["finished_by"],
            result["tool_calls"]), file=sys.stderr)

    def on_signal(signum: int, frame: object) -> None:
        # The HTTP server re-raises a stop signal after shutting down, which would end the
        # process before the `finally` below. Grade first, then exit.
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
