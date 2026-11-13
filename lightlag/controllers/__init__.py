"""Controllers that act exclusively through Lightlag's public tools."""

from .api import PublicTools
from .baselines import do_nothing, move_and_wait, nominal_open_loop, stale_telemetry, stop_early
from .reference import reference

POLICIES = {
    "reference": reference,
    "move_and_wait": move_and_wait,
    "nominal_open_loop": nominal_open_loop,
    "stale_telemetry": stale_telemetry,
    "do_nothing": do_nothing,
    "stop_early": stop_early,
}

__all__ = ["PublicTools", "POLICIES", *POLICIES]
