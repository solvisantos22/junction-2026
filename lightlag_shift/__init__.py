"""The ground changes: a Lightlag mission whose slip coefficients change once at a hidden time.

A proposal for the team, not a rules decision. See docs/lightlag-shift.md.
"""

from .environment import CHANGE_WINDOW, SLIP_AFTER, ShiftEnvironment, draw_change

__all__ = ["CHANGE_WINDOW", "SLIP_AFTER", "ShiftEnvironment", "draw_change"]
