"""Serve one ground-change mission over MCP: the same five tools, the same grading.

    python3 -m lightlag_shift.serve --seed 3100 --profile rush_noisy --delay 3
    python3 -m lightlag_shift.serve --transport http --host 0.0.0.0 --port 8000 --seed 3100

It takes the options of `python3 -m lightlag_dynamic.serve`, because it is that entry point
with one thing swapped: the episode behind the tools. The lock, the transcript, the
evaluator-only finish route and the artifacts are the team's, unchanged.

Which mission is chosen by the environment variable LIGHTLAG_SHIFT_MISSION, set where the
episode's other settings are (the simulator's container):

    ground   (default) the slip of every terrain changes once: `ShiftEnvironment`
    rule     one of four published changes happens once: `RuleChangeEnvironment`
"""

import os
import sys

import lightlag_dynamic.serve as dynamic_serve
from lightlag import Config
from lightlag_dynamic.missions import PROFILES

from .environment import ShiftEnvironment
from .rule_change import RuleChangeEnvironment

MISSIONS = {"ground": ShiftEnvironment, "rule": RuleChangeEnvironment}


class ShiftEpisodeService(dynamic_serve.DynamicEpisodeService):
    """The dynamic episode service, playing a mission whose ground changes once."""

    def __init__(self, seed, profile="rush_noisy", config=None, artifact_dir=None, noise_level=1.0,
                 bumpiness=0.0, mission=None):
        mission = mission or os.environ.get("LIGHTLAG_SHIFT_MISSION") or "ground"
        if mission not in MISSIONS:
            raise ValueError("unknown mission {!r}; use one of {}".format(mission, ", ".join(MISSIONS)))
        if bumpiness:
            raise ValueError("the ground-change mission does not combine with bumpy ground")
        if config is None:
            config = Config(max_ticks=PROFILES[profile][4])
        super().__init__(seed=seed, profile=profile, config=config, artifact_dir=artifact_dir,
                         noise_level=noise_level)
        # Swap the episode before any tool call, as the dynamic service does for its own.
        self._env = MISSIONS[mission](seed=seed, config=config, profile=profile, noise_level=noise_level)
        self.mission = mission
        rules = self._env.rules()
        self._max_ticks = rules["max_ticks"]
        self._max_advance = rules["max_advance_ticks"]


def main(argv=None):
    # The dynamic entry point builds whatever service class this name holds when it runs.
    dynamic_serve.DynamicEpisodeService = ShiftEpisodeService
    return dynamic_serve.main(argv)


if __name__ == "__main__":
    sys.exit(main())
