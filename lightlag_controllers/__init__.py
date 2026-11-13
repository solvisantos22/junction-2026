"""Reference controller and scripted baselines for Lightlag.

Everything here uses only the simulator's five public methods. See
docs/lightlag-pilot.md for what each controller does and how to run the comparison.
"""

from .controllers import (
    ALL_STRATEGIES,
    MOVE_AND_WAIT,
    NO_OP,
    OPEN_LOOP_NOMINAL,
    REFERENCE,
    STALE_TELEMETRY,
    STOP_EARLY,
    Controller,
    Strategy,
    Tuning,
    make,
)
from .runner import run_episode

__all__ = [
    "ALL_STRATEGIES", "MOVE_AND_WAIT", "NO_OP", "OPEN_LOOP_NOMINAL", "REFERENCE",
    "STALE_TELEMETRY", "STOP_EARLY", "Controller", "Strategy", "Tuning", "make", "run_episode",
]
