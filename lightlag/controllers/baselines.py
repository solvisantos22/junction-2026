"""Scripted controls for interpreting controller evaluation results."""

from .api import PublicTools
from .reference import Mission


def move_and_wait(tools: PublicTools):
    """Wait for each action's execution packet before choosing another action."""
    Mission(tools, mode="move_and_wait").run()


def nominal_open_loop(tools: PublicTools):
    """Use midpoint slip and the launch briefing, with no later state correction."""
    Mission(tools, mode="nominal_open_loop").run()


def stale_telemetry(tools: PublicTools):
    """Treat the latest delivered position as current; ignore pending motion."""
    Mission(tools, mode="stale_telemetry").run()


def do_nothing(tools: PublicTools):
    """Issue no commands; the evaluator still consumes the full horizon."""
    return None


def stop_early(tools: PublicTools):
    """Plan for the full horizon, but return control at its first quarter."""
    Mission(tools, stop_fraction=4).run()
