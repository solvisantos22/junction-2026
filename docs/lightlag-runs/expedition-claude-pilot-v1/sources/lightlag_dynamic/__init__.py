"""Dynamic-rules pilot for Lightlag: sample deadlines, mid-mission discoveries, seeded maps.

Adds these rules on top of the team's `lightlag` simulator without changing it. Run from
the repository root; see lightlag_dynamic/README.md and docs/lightlag-dynamic-pilot.md.
Set LIGHTLAG_REPO only to run it against a different checkout of the simulator.
"""

import os
import sys

if os.environ.get("LIGHTLAG_REPO"):
    sys.path.insert(0, os.path.expanduser(os.environ["LIGHTLAG_REPO"]))

from .missions import PROFILES, Mission, TargetPlan, make_mission  # noqa: E402
from .environment import DynamicEnvironment  # noqa: E402
from .tools import PublicTools, run_episode  # noqa: E402
from .controllers import POLICIES  # noqa: E402

__all__ = ["DynamicEnvironment", "Mission", "POLICIES", "PROFILES", "PublicTools",
           "TargetPlan", "make_mission", "run_episode"]
