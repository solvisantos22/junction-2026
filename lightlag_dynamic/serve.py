"""Serve one dynamic-pilot episode over MCP, through Kristján's lightlag_mcp server.

    python3 -m lightlag_dynamic.serve --profile rush --seed 7 --delay 3
    python3 -m lightlag_dynamic.serve --profile rush_noisy --transport http --port 8000 --seed 7 \\
        --delay 3 --artifact-dir /evaluator/run1

Same five tools, same evaluator-only finish, same artifacts and the same settings as
`python -m lightlag_mcp` (LIGHTLAG_SEED, LIGHTLAG_DELAY, LIGHTLAG_TICKS,
LIGHTLAG_ARTIFACT_DIR, LIGHTLAG_EVALUATOR_TOKEN, LIGHTLAG_TOKEN_FILE), plus --profile / LIGHTLAG_PROFILE,
--noise-level / LIGHTLAG_NOISE_LEVEL and --bumpiness / LIGHTLAG_BUMPINESS. The only difference
is the episode behind the tools: a DynamicEnvironment for the chosen profile.

Harbor: the task in harbor/lightlag/ starts `python -m lightlag_mcp` in its simulator
container. Starting `python -m lightlag_dynamic.serve --profile <name>` there instead (with
lightlag_dynamic/ copied in) serves a dynamic profile with the same tools, token and finish.

This is a thin wrapper. It imports lightlag_mcp and changes none of its files. It relies on
EpisodeService keeping its episode in `_env`, `_max_ticks` and `_max_advance`
(checked by tests/lightlag_dynamic/test_dynamic.py); a constructor hook in lightlag_mcp
would make that unnecessary. Serving over MCP needs the `mcp` package (2.x, Python 3.10+);
DynamicEpisodeService itself is standard library only.
"""

import argparse
import os
import secrets
import signal
import sys

from lightlag import Config
from lightlag_mcp.service import EpisodeService

from .environment import DynamicEnvironment
from .missions import PROFILES


class DynamicEpisodeService(EpisodeService):
    """lightlag_mcp's EpisodeService, playing a dynamic-pilot profile."""

    def __init__(self, seed, profile="rush", config=None, artifact_dir=None, noise_level=1.0,
                 bumpiness=0.0):
        if profile not in PROFILES:
            raise ValueError(f"unknown profile {profile!r}; use one of {', '.join(PROFILES)}")
        if config is None:
            config = Config(max_ticks=PROFILES[profile][4])
        super().__init__(seed=seed, config=config, artifact_dir=artifact_dir)
        # Swap the episode before any tool call; the lock, transcript and grading are unchanged.
        self._env = DynamicEnvironment(seed=seed, config=config, profile=profile,
                                       noise_level=noise_level, bumpiness=bumpiness)
        rules = self._env.rules()
        self._max_ticks = rules["max_ticks"]
        self._max_advance = rules["max_advance_ticks"]
        self.profile = profile


def _env_int(name, default):
    value = os.environ.get(name)
    return default if value in (None, "") else int(value)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lightlag_dynamic.serve",
                                     description="Serve one dynamic Lightlag episode over MCP.")
    parser.add_argument("--profile", choices=list(PROFILES),
                        default=os.environ.get("LIGHTLAG_PROFILE") or "rush")
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--seed", type=int, default=_env_int("LIGHTLAG_SEED", None))
    parser.add_argument("--delay", type=int, default=_env_int("LIGHTLAG_DELAY", 3))
    parser.add_argument("--ticks", type=int, default=_env_int("LIGHTLAG_TICKS", None),
                        help="episode length; defaults to the profile's horizon")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--artifact-dir", default=os.environ.get("LIGHTLAG_ARTIFACT_DIR"))
    parser.add_argument("--token-file", default=os.environ.get("LIGHTLAG_TOKEN_FILE"),
                        help="HTTP only: write a fresh evaluator token here when "
                             "LIGHTLAG_EVALUATOR_TOKEN is not set (as lightlag_mcp does)")
    parser.add_argument("--noise-level", type=float,
                        default=float(os.environ.get("LIGHTLAG_NOISE_LEVEL") or 1.0),
                        help="multiplies the sensing noise and drift of the noisy profiles")
    parser.add_argument("--bumpiness", type=float,
                        default=float(os.environ.get("LIGHTLAG_BUMPINESS") or 0.0),
                        help="experimental: share of rough cells that can spin the wheels")
    args = parser.parse_args(argv)
    if args.seed is None:
        parser.error("a seed is required (--seed or LIGHTLAG_SEED)")

    from lightlag_mcp.server import build_server  # late: --help works without the mcp package

    ticks = PROFILES[args.profile][4] if args.ticks is None else args.ticks
    service = DynamicEpisodeService(seed=args.seed, profile=args.profile,
                                    config=Config(delay_ticks=args.delay, max_ticks=ticks),
                                    artifact_dir=args.artifact_dir, noise_level=args.noise_level,
                                    bumpiness=args.bumpiness)
    token = os.environ.get("LIGHTLAG_EVALUATOR_TOKEN") or None
    if token is None and args.token_file and args.transport == "http":
        token = secrets.token_urlsafe(32)  # exists only inside this process's container
        os.makedirs(os.path.dirname(os.path.abspath(args.token_file)), exist_ok=True)
        descriptor = os.open(args.token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(token)
    server = build_server(service, evaluator_token=token)

    def finish():
        result = service.finish()
        print("lightlag dynamic episode finished: profile={} raw_score={raw_score} "
              "sampled={sampled_targets} alive={alive} at_base={at_base} "
              "tool_calls={tool_calls}".format(args.profile, **result), file=sys.stderr)

    def on_signal(signum, frame):
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
