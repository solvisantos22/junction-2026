"""Serve one episode in a chosen biome over MCP, through Kristján's lightlag_mcp server.

    python3 -m lightlag_dynamic.biomes.serve --biome relay_pass --profile rush --seed 7 --delay 3
    python3 -m lightlag_dynamic.biomes.serve --biome troy_crust --profile rush_noisy --transport http \\
        --port 8000 --seed 7 --delay 3 --artifact-dir /evaluator/run1

The same five tools, evaluator-only finish, artifacts and settings as
`python3 -m lightlag_dynamic.serve` (LIGHTLAG_SEED, LIGHTLAG_DELAY, LIGHTLAG_TICKS,
LIGHTLAG_PROFILE, LIGHTLAG_NOISE_LEVEL, LIGHTLAG_ARTIFACT_DIR, LIGHTLAG_EVALUATOR_TOKEN,
LIGHTLAG_TOKEN_FILE), plus --biome / LIGHTLAG_BIOME and, for the no-GPS prototype, --no-gps /
LIGHTLAG_NO_GPS=1, --weak-gps / LIGHTLAG_WEAK_GPS=1 or --many-sensors / LIGHTLAG_MANY_SENSORS=1.
With the default biome, main_mars, and today's position fix, the episode is the one
`lightlag_dynamic.serve` plays.

The tool descriptions are made true for the episode (wording.py): with --no-gps or --weak-gps
they say what telemetry reports instead of a trustworthy position, and in a biome they point
at rules()["biome"] and the map's extra layers. With main_mars and today's fix they are
lightlag_mcp's own, unchanged.

A separate module, so `lightlag_dynamic/serve.py`, which the Harbor experiments copy and hash,
stays unchanged; nothing under harbor/ uses this (tools/biome_experiments/prepare.py packs it
as an isolated Harbor task outside the checkout). Like that module it swaps the episode inside
lightlag_mcp's EpisodeService (`_env`, `_max_ticks`, `_max_advance`). Serving needs the `mcp`
package (2.x, Python 3.10+); BiomeEpisodeService itself is standard library only.
"""

import argparse
import os
import secrets
import signal
import sys

from lightlag import Config
from lightlag_dynamic.missions import PROFILES
from lightlag_mcp.service import EpisodeService

from .catalog import BIOME_IDS, MAIN, parse_biome
from .environment import BiomeEnvironment


class BiomeEpisodeService(EpisodeService):
    """lightlag_mcp's EpisodeService, playing a dynamic profile in a chosen biome."""

    def __init__(self, seed, biome=MAIN, profile="rush", config=None, artifact_dir=None, noise_level=1.0,
                 no_gps=False, gps_noise=None, weak_gps=False, many_sensors=False):
        parse_biome(biome)
        if profile not in PROFILES:
            raise ValueError(f"unknown profile {profile!r}; use one of {', '.join(PROFILES)}")
        if config is None:
            config = Config(max_ticks=PROFILES[profile][4])
        super().__init__(seed=seed, config=config, artifact_dir=artifact_dir)
        # Swap the episode before any tool call; the lock, transcript and grading are unchanged.
        if no_gps or weak_gps or many_sensors or gps_noise is not None:  # prototype: no fix, or weak sensors
            from .nogps import MANY_SENSORS, WEAK_GPS, NoGpsEnvironment
            navigation = dict(MANY_SENSORS) if many_sensors else dict(WEAK_GPS) if weak_gps else {}
            if gps_noise is not None:
                navigation["position_noise_m"] = gps_noise
            self._env = NoGpsEnvironment(seed=seed, config=config, profile=profile, biome=biome,
                                         noise_level=noise_level, navigation=navigation)
        else:
            self._env = BiomeEnvironment(seed=seed, config=config, profile=profile, biome=biome,
                                         noise_level=noise_level)
        rules = self._env.rules()
        self._max_ticks = rules["max_ticks"]
        self._max_advance = rules["max_advance_ticks"]
        self.profile, self.biome = profile, biome
        self.no_gps = bool(no_gps or weak_gps or many_sensors or gps_noise is not None)


def build_biome_server(service, evaluator_token=None):
    """lightlag_mcp's server for `service`, with tool texts that are true for its episode.

    The stock texts promise a position in every packet and know nothing of biomes. They are
    swapped (wording.py) only while this server is built, so nothing else in the process
    changes and no file of lightlag_mcp is edited.
    """
    import lightlag_mcp.server as server_module  # late: needs the mcp package

    from .wording import patched
    with patched(server_module, service._env.rules()):
        return server_module.build_server(service, evaluator_token=evaluator_token)


def _env_int(name, default):
    value = os.environ.get(name)
    return default if value in (None, "") else int(value)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lightlag_dynamic.biomes.serve",
                                     description="Serve one Lightlag episode in a chosen biome over MCP.")
    parser.add_argument("--biome", default=os.environ.get("LIGHTLAG_BIOME") or MAIN,
                        help="one of: " + ", ".join(BIOME_IDS) + "; mix with +")
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
    parser.add_argument("--no-gps", action="store_true", default=os.environ.get("LIGHTLAG_NO_GPS") in ("1", "true", "yes"),
                        help="prototype: no position fix; a beacon range and a sun compass instead")
    parser.add_argument("--weak-gps", action="store_true", default=os.environ.get("LIGHTLAG_WEAK_GPS") in ("1", "true", "yes"),
                        help="prototype: as --no-gps, but keep a very noisy position fix (nogps.WEAK_GPS)")
    parser.add_argument("--many-sensors", action="store_true",
                        default=os.environ.get("LIGHTLAG_MANY_SENSORS") in ("1", "true", "yes"),
                        help="prototype: many weak sensors to fuse (nogps.MANY_SENSORS)")
    parser.add_argument("--gps-noise", type=float,
                        default=float(os.environ["LIGHTLAG_GPS_NOISE"]) if os.environ.get("LIGHTLAG_GPS_NOISE") else None,
                        help="prototype: as --no-gps, but keep a position fix with this much noise per axis (metres)")
    args = parser.parse_args(argv)
    if args.seed is None:
        parser.error("a seed is required (--seed or LIGHTLAG_SEED)")
    try:
        parse_biome(args.biome)
    except ValueError as error:
        parser.error(str(error))

    ticks = PROFILES[args.profile][4] if args.ticks is None else args.ticks
    service = BiomeEpisodeService(seed=args.seed, biome=args.biome, profile=args.profile,
                                  config=Config(delay_ticks=args.delay, max_ticks=ticks),
                                  artifact_dir=args.artifact_dir, noise_level=args.noise_level,
                                  no_gps=args.no_gps, gps_noise=args.gps_noise, weak_gps=args.weak_gps,
                                  many_sensors=args.many_sensors)
    token = os.environ.get("LIGHTLAG_EVALUATOR_TOKEN") or None
    if token is None and args.token_file and args.transport == "http":
        token = secrets.token_urlsafe(32)  # exists only inside this process's container
        os.makedirs(os.path.dirname(os.path.abspath(args.token_file)), exist_ok=True)
        descriptor = os.open(args.token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(token)
    server = build_biome_server(service, evaluator_token=token)  # late import: --help works without mcp

    def finish():
        result = service.finish()
        print("lightlag biome episode finished: biome={} profile={} raw_score={raw_score} "
              "sampled={sampled_targets} alive={alive} at_base={at_base} "
              "tool_calls={tool_calls}".format(args.biome, args.profile, **result), file=sys.stderr)

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
