"""Real-time Lightlag: the mission clock runs on the wall clock, so thinking costs ticks.

    python3 -m lightlag_dynamic.realtime --seconds-per-tick 5 --profile rush_noisy --seed 7 --delay 3
    python3 -m lightlag_dynamic.realtime --seconds-per-tick 5 --profile rush_noisy --transport http \\
        --port 8000 --seed 7 --delay 3 --artifact-dir /evaluator/run1

Every other flag and LIGHTLAG_* setting is the same as `python -m lightlag_dynamic.serve`.
The tick length also reads from LIGHTLAG_SECONDS_PER_TICK.

Why: in the turn-based episode only `advance` moves the clock, so an agent can think for as
long as it likes between ticks. Mission control has no such pause button. Here:

- One tick passes every `seconds_per_tick` seconds, starting at the agent's first tool call
  (not at server start, so container and harness start-up never cost ticks).
- Before any tool answers, the episode catches up to the wall clock. Commands are stamped
  with the tick at which they arrive; telemetry that arrived meanwhile is in `telemetry_log`.
- `advance(n)` no longer moves the clock: it waits until n more ticks have passed and returns
  every packet that arrived since the previous `advance`, including those that arrived while
  the agent was thinking, so an agent that reads only `advance` misses nothing. The other
  tools answer at once.
- `rules()` publishes the clock (tick length, current tick, seconds elapsed).
- Once the wall clock passes the horizon the episode is complete and graded as usual.
- A controller that answers instantly loses nothing: on the same seed it scores what it
  scores turn-based (tested).

Transcript: each catch-up is recorded as a `"tool": "clock"` record with the ticks it moved;
agent `advance` records move no ticks; every record carries `wall_seconds` since the first
call. Replays therefore step the clock by `clock` records (or by tick_before/tick_after),
not by `advance` arguments. replay.json is unchanged: commands keep their sent_tick.

This module changes no file of lightlag_mcp or lightlag_dynamic.serve (serve.py is copied
into Sölvi's frozen experiments). It subclasses DynamicEpisodeService and, in its own
process only, swaps the service class and the clock wording of the tool descriptions before
reusing serve.main. The swap fails loudly if that wording changes.
"""

import argparse
import math
import os
import sys
import threading
import time

from . import serve
from .serve import DynamicEpisodeService

try:  # the service is standard library only; the tool error type lives with lightlag_mcp
    from lightlag_mcp.service import ToolError
except ImportError:  # pragma: no cover
    ToolError = ValueError


class RealTimeEpisodeService(DynamicEpisodeService):
    """DynamicEpisodeService whose clock follows `clock()` instead of `advance` calls."""

    def __init__(self, seed, seconds_per_tick, clock=time.monotonic, sleep=time.sleep, **kwargs):
        if not (isinstance(seconds_per_tick, (int, float)) and math.isfinite(seconds_per_tick)
                and seconds_per_tick > 0):
            raise ValueError("seconds_per_tick must be a positive number")
        super().__init__(seed=seed, **kwargs)
        self._lock = threading.RLock()  # call() catches up under the lock, then re-enters it
        self._seconds_per_tick = float(seconds_per_tick)
        self._clock = clock
        self._sleep = sleep
        self._t0 = None
        self._reported_until = 0  # advance has returned every packet received up to this tick

    # -- clock -----------------------------------------------------------------------

    def elapsed(self):
        return 0.0 if self._t0 is None else self._clock() - self._t0

    def wall_tick(self):
        """The tick the wall clock has reached (0 before the first call), capped at the horizon."""
        if self._t0 is None:
            return 0
        return min(self._max_ticks, int(math.floor(self.elapsed() / self._seconds_per_tick + 1e-9)))

    def _catch_up(self):
        """Advance the episode to the wall clock, recording each step. Caller holds the lock."""
        if self._closed:
            return
        target = self.wall_tick()
        while self._tick < target:
            before = self._tick
            result = self._env.advance(min(self._max_advance, target - self._tick))
            self._tick = result["current_tick"]
            self._record({"n": None, "tool": "clock", "arguments": {"ticks": self._tick - before},
                          "ok": True, "tick_before": before, "tick_after": self._tick,
                          "summary": self._summarise("advance", result)})
        if self._tick >= self._max_ticks and self._result is None:
            self._grade()

    def _advance_ticks(self, arguments):
        """The tick count of a well-formed advance request, else None (the call then fails as usual)."""
        if not isinstance(arguments, dict) or set(arguments) - {"ticks"}:
            return None
        ticks = arguments.get("ticks", 1)
        return ticks if type(ticks) is int and 1 <= ticks <= self._max_advance else None

    # -- agent-facing ------------------------------------------------------------------

    def call(self, tool, arguments=None):
        arguments = dict(arguments or {})
        with self._lock:
            if self._t0 is None and not self._closed:
                self._t0 = self._clock()
            self._catch_up()
            start = self._tick
        ticks = self._advance_ticks(arguments) if tool == "advance" else None
        if ticks is not None:
            target = min(start + ticks, self._max_ticks)
            remaining = self._t0 + target * self._seconds_per_tick - self._clock()
            if remaining > 0:
                self._sleep(remaining)  # outside the lock: the evaluator can still finish
        with self._lock:
            self._catch_up()
            return super().call(tool, arguments)

    def _dispatch(self, tool, arguments):
        if self._closed or tool not in ("rules", "advance"):
            return super()._dispatch(tool, arguments)
        if tool == "rules":
            rules = super()._dispatch(tool, arguments)
            rules["clock"] = self.clock_rules()
            return rules
        if set(arguments) - {"ticks"}:
            raise ToolError("advance takes one optional argument: ticks (an integer from 1 to 5)")
        if self._advance_ticks(arguments) is None:
            raise ToolError("ticks must be an integer from 1 to {}".format(self._max_advance))
        packets = [packet for packet in self._env.telemetry_log()
                   if packet["received_tick"] > self._reported_until]
        self._reported_until = self._tick
        return {"current_tick": self._tick, "episode_complete": self._tick >= self._max_ticks,
                "packets": packets}

    def clock_rules(self):
        return {
            "mode": "real_time",
            "seconds_per_tick": self._seconds_per_tick,
            "started": "at your first tool call",
            "current_tick": self._tick,
            "seconds_elapsed": round(self.elapsed(), 3),
            "advance": ("waits until that many more ticks have passed and returns every packet "
                        "received since your previous advance; it does not stop the clock"),
        }

    def _record(self, record):
        if self._t0 is not None:
            record = dict(record, wall_seconds=round(self.elapsed(), 3))
        super()._record(record)


# -- tool wording for the real-time server (this process only) ------------------------------

FREE = "Free: does not advance time."
ANSWERS_AT_ONCE = "Answers at once; the real-time clock keeps running."
TURN_BASED_TIMING = "Only `advance` moves the clock; every other tool is free."


def real_time_timing(seconds_per_tick):
    return ("The clock runs in real time: one tick every {:g} seconds from your first tool call, "
            "whether or not you call tools, so time spent thinking costs ticks. `advance(n)` waits "
            "until n more ticks have passed; `rules()` reports the current tick.").format(seconds_per_tick)


def real_time_advance(seconds_per_tick):
    return ("Wait until 1 to 5 more ticks have passed (default 1); one tick is {:g} seconds of real "
            "time. The clock runs whether or not you call this. Returns current_tick, "
            "episode_complete and every telemetry packet that arrived since your previous advance, "
            "including while you were thinking.").format(seconds_per_tick)


def _replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError("lightlag_mcp's tool wording changed; update lightlag_dynamic.realtime: "
                           + repr(old))
    return text.replace(old, new)


def patch_tool_wording(server_module, seconds_per_tick):
    """Make the MCP tool texts describe the real-time clock. Mutates `server_module` in place."""
    server_module.INSTRUCTIONS = _replace_once(server_module.INSTRUCTIONS, TURN_BASED_TIMING,
                                               real_time_timing(seconds_per_tick))
    for name in ("RULES_DESCRIPTION", "MAP_DESCRIPTION", "TELEMETRY_DESCRIPTION"):
        setattr(server_module, name, _replace_once(getattr(server_module, name), FREE, ANSWERS_AT_ONCE))
    server_module.ADVANCE_DESCRIPTION = real_time_advance(seconds_per_tick)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lightlag_dynamic.realtime", add_help=False)
    parser.add_argument("--seconds-per-tick", type=float,
                        default=float(os.environ.get("LIGHTLAG_SECONDS_PER_TICK") or 0) or None)
    args, rest = parser.parse_known_args(argv)
    if "-h" in rest or "--help" in rest:
        print(__doc__)
        return 0
    if args.seconds_per_tick is None or not args.seconds_per_tick > 0:
        parser.error("a positive --seconds-per-tick (or LIGHTLAG_SECONDS_PER_TICK) is required")
    seconds = args.seconds_per_tick

    def service(**kwargs):
        return RealTimeEpisodeService(seconds_per_tick=seconds, **kwargs)

    import lightlag_mcp.server as server_module  # late: needs the mcp package
    patch_tool_wording(server_module, seconds)
    serve.DynamicEpisodeService = service  # serve.main builds its service from this name
    print("lightlag real-time clock: {:g} s per tick, starting at the first tool call".format(seconds),
          file=sys.stderr)
    return serve.main(rest)


if __name__ == "__main__":
    sys.exit(main())
