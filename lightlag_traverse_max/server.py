#!/usr/bin/env python3
"""Serve the Traverse MAX map over MCP: one mission, or a campaign of missions in a row.

    python -m lightlag_traverse_max.server --seeds 500,510,520 --transport http --port 8000
    LIGHTLAG_SEEDS=505,509,515 python -m lightlag_traverse_max.server --transport http

Kristján's server (lightlag_traverse/server.py) and campaign (lightlag_traverse/campaign.py),
unchanged, with the MAX map's mission behind them: the same five tools, the same transcript, lock,
grading, evaluator token and finish route. Only the episode is swapped, before any tool call. The
seeds come from the evaluator (LIGHTLAG_SEED / LIGHTLAG_SEEDS) and stay in this process.
"""

from __future__ import annotations

import argparse
import os
import secrets
import signal
import sys
from typing import Any, Dict, Optional, Sequence

from lightlag_mcp.service import EpisodeService
from lightlag_traverse.campaign import TEXTS as CAMPAIGN_TEXTS, TraverseCampaign, TraverseCampaignService
from lightlag_traverse.server import TEXTS, TraverseEpisodeService, build_server

from .environment import make_env

MAX_NOTE = """

This is the MAX map: the link is open only during relay passes, telemetry packets can be lost, \
position fixes are worse and sometimes wild, the rover stops itself when its wheels slip too much, \
some mapped bedrock is soft sand underneath, the dune slope gain and the wheel size are hidden, \
turning costs energy, and visual odometry noise depends on the terrain. `rules()["max_option"]` \
names each change and `rules()` gives its exact rule.\
"""


class MaxEpisodeService(TraverseEpisodeService):
    """The team's episode service (lock, transcript, grading), with a mission of either map behind it."""

    def __init__(self, seed: int, artifact_dir: Optional[str] = None, option: str = "max") -> None:
        super().__init__(seed, artifact_dir=artifact_dir)
        self._env = make_env(seed, option)          # swapped before any tool call
        rules = self._env.rules()
        self._max_ticks = rules["max_ticks"]
        self._max_advance = rules["max_advance_ticks"]


class MaxTraverseCampaign(TraverseCampaign):
    """Kristján's campaign, with every mission on the MAX map."""

    def _open(self, index: int) -> None:
        self._index = index
        self._env = make_env(self.seeds[index], "max", mission=self._overrides or None)
        self._tick = 0


class MaxCampaignService(TraverseCampaignService):
    """Kristján's campaign service, playing a MAX-map campaign."""

    def __init__(self, seeds: Sequence[int], artifact_dir: Optional[str] = None,
                 mission: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(seeds, artifact_dir=artifact_dir, mission=mission)
        self._campaign = MaxTraverseCampaign(seeds, mission)   # swapped before any tool call
        self._env = self._campaign
        rules = self._campaign.rules()
        self._max_ticks = len(self._campaign.seeds) * rules["max_ticks"]
        self._max_advance = rules["max_advance_ticks"]


def texts(campaign: bool) -> Dict[str, str]:
    """Kristján's server texts with one paragraph on the MAX map added to the instructions."""
    chosen = dict(CAMPAIGN_TEXTS if campaign else TEXTS)
    chosen["instructions"] = chosen["instructions"] + MAX_NOTE
    return chosen


def main(argv: Optional[Sequence[str]] = None) -> int:
    env = os.environ.get
    parser = argparse.ArgumentParser(prog="lightlag_traverse_max.server",
                                     description="Serve one Lightlag Traverse MAX-map mission, or a campaign, over MCP.")
    parser.add_argument("--seed", type=int, default=int(env("LIGHTLAG_SEED")) if env("LIGHTLAG_SEED") else None)
    parser.add_argument("--seeds", default=env("LIGHTLAG_SEEDS"),
                        help="a campaign instead of one mission: comma-separated seeds, played in that order")
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--artifact-dir", default=env("LIGHTLAG_ARTIFACT_DIR"),
                        help="evaluator-only directory for result.json, replay.json and transcript.jsonl")
    parser.add_argument("--token-file", default=env("LIGHTLAG_TOKEN_FILE"),
                        help="HTTP only: write a freshly generated evaluator token here when "
                             "LIGHTLAG_EVALUATOR_TOKEN is not set")
    args = parser.parse_args(argv)
    if args.seeds:
        try:
            seeds = [int(part) for part in args.seeds.split(",") if part.strip()]
        except ValueError:
            parser.error("--seeds must be comma-separated integers")
        service: EpisodeService = MaxCampaignService(seeds, artifact_dir=args.artifact_dir)
    elif args.seed is None:
        parser.error("a seed is required (--seed or LIGHTLAG_SEED), or seeds for a campaign (--seeds or LIGHTLAG_SEEDS)")
    else:
        service = MaxEpisodeService(args.seed, artifact_dir=args.artifact_dir)
    token = env("LIGHTLAG_EVALUATOR_TOKEN") or None
    if token is None and args.token_file and args.transport == "http":
        token = secrets.token_urlsafe(32)          # exists only inside this process's container
        os.makedirs(os.path.dirname(os.path.abspath(args.token_file)), exist_ok=True)
        descriptor = os.open(args.token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(token)
    server = build_server(service, evaluator_token=token, texts=texts(bool(args.seeds)))

    def finish() -> None:
        result = service.finish()
        print("lightlag traverse MAX mission finished: raw_score={raw_score} of {max_available_value} "
              "sampled={sampled_targets} alive={alive} at_base={at_base} tool_calls={tool_calls}".format(**result),
              file=sys.stderr)

    def on_signal(signum: int, frame: object) -> None:
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
