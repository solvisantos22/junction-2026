"""Serve one ground-change mission over MCP: the same five tools, the same grading.

    python3 -m lightlag_shift.serve --seed 3100 --profile rush_noisy --delay 3
    python3 -m lightlag_shift.serve --transport http --host 0.0.0.0 --port 8000 --seed 3100

It takes the options of `python3 -m lightlag_dynamic.serve`, because it is that entry point
with one thing swapped: the episode behind the tools is a `ShiftEnvironment`. The lock, the
transcript, the evaluator-only finish route and the artifacts are the team's, unchanged.
"""

import sys

import lightlag_dynamic.serve as dynamic_serve
from lightlag import Config
from lightlag_dynamic.missions import PROFILES

from .environment import ShiftEnvironment


class ShiftEpisodeService(dynamic_serve.DynamicEpisodeService):
    """The dynamic episode service, playing a mission whose ground changes once."""

    def __init__(self, seed, profile="rush_noisy", config=None, artifact_dir=None, noise_level=1.0,
                 bumpiness=0.0):
        if bumpiness:
            raise ValueError("the ground-change mission does not combine with bumpy ground")
        if config is None:
            config = Config(max_ticks=PROFILES[profile][4])
        super().__init__(seed=seed, profile=profile, config=config, artifact_dir=artifact_dir,
                         noise_level=noise_level)
        # Swap the episode before any tool call, as the dynamic service does for its own.
        self._env = ShiftEnvironment(seed=seed, config=config, profile=profile, noise_level=noise_level)
        rules = self._env.rules()
        self._max_ticks = rules["max_ticks"]
        self._max_advance = rules["max_advance_ticks"]


def main(argv=None):
    # The dynamic entry point builds whatever service class this name holds when it runs.
    dynamic_serve.DynamicEpisodeService = ShiftEpisodeService
    return dynamic_serve.main(argv)


if __name__ == "__main__":
    sys.exit(main())
