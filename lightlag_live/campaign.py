"""Several Lightlag missions in a row on a real-time clock, behind one lock.

Standard library only, on top of the team's `lightlag` and `lightlag_dynamic` packages, which
are imported and not changed. No MCP dependency: this module decides what an agent can and
cannot do, and it is tested on its own with a fake clock.

What is new compared with one turn-based episode:

- **A campaign.** `missions` is a list of (seed, profile) pairs. Each one is an unchanged
  `DynamicEnvironment` episode: same physics, same tools, same scoring. They are played back to
  back; the campaign's reward is the mean of the missions' scores.
- **A real-time clock.** One tick passes every `seconds_per_tick` seconds of wall time, whether
  or not anyone calls a tool. The clock starts at the agent's first `uplink` or `advance`;
  `rules`, `map` and `telemetry_log` are free before that, so an agent can read the first
  mission and prepare for as long as it likes. Once started the clock never stops: mission
  k + 1 begins the moment mission k ends.
- **`advance(n)` waits** until n more ticks have passed (never past the end of the mission) and
  returns every packet that arrived since the previous `advance`.

A controller that answers instantly loses nothing to the clock: with a fake clock it scores
exactly what it scores turn-based on the same seeds (tests/lightlag_live/test_campaign.py).

Agent-facing surface: `call(tool, arguments)` with exactly `rules`, `map`, `telemetry_log`,
`uplink`, `advance`. There is no reset, no seed, no score and no way to pause.

Evaluator-facing surface: `finish()`. It closes the campaign to the agent, lets every remaining
tick of every remaining mission pass at once (queued commands still execute, the battery keeps
draining), grades and writes the artifacts. Call it from trusted code only.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from lightlag import Config
from lightlag_dynamic.environment import DynamicEnvironment
from lightlag_dynamic.missions import PROFILES

PUBLIC_TOOLS = ("rules", "map", "telemetry_log", "uplink", "advance")
VERSION = "lightlag-live-v1"
MAX_ADVANCE = 5


class ToolError(ValueError):
    """A request the agent can fix: unknown tool, bad arguments, campaign over."""


class CampaignService:
    def __init__(
        self,
        missions: Sequence[Mapping[str, Any]],
        delay: int = 3,
        ticks: int = 50,
        seconds_per_tick: float = 1.0,
        noise_level: float = 1.0,
        artifact_dir: Optional[str] = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not missions:
            raise ValueError("a campaign needs at least one mission")
        self._missions: List[Dict[str, Any]] = []
        for mission in missions:
            seed, profile = mission["seed"], mission["profile"]
            if type(seed) is not int or profile not in PROFILES:
                raise ValueError("each mission needs an integer seed and a known profile")
            self._missions.append({"seed": seed, "profile": profile})
        if not (isinstance(seconds_per_tick, (int, float)) and math.isfinite(seconds_per_tick)
                and seconds_per_tick > 0):
            raise ValueError("seconds_per_tick must be a positive number")
        self._config = Config(delay_ticks=delay, max_ticks=ticks)
        self._ticks = ticks
        self._seconds_per_tick = float(seconds_per_tick)
        self._noise_level = float(noise_level)
        self._artifact_dir = artifact_dir
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.RLock()
        self._t0: Optional[float] = None
        self._closed = False
        self._done = False
        self._calls = 0
        self._transcript: List[Dict[str, Any]] = []
        self._results: List[Dict[str, Any]] = []
        self._leftover: Dict[int, List[Dict[str, Any]]] = {}
        self._result: Optional[Dict[str, Any]] = None
        self._finished_by: Optional[str] = None
        if artifact_dir:
            os.makedirs(artifact_dir, exist_ok=True)
            with open(os.path.join(artifact_dir, "transcript.jsonl"), "w", encoding="utf-8"):
                pass  # a fresh trace, so a crashed run still leaves something readable
        self._open(0)

    # -- agent-facing --------------------------------------------------------------------

    def call(self, tool: str, arguments: Optional[Mapping[str, Any]] = None) -> Any:
        """Run one public tool. Every call is recorded with the mission, tick and wall time."""
        arguments = dict(arguments or {})
        if tool == "advance":
            return self._advance(arguments)
        with self._lock:
            record = self._begin(tool, arguments)
            try:
                result = self._serve(tool, arguments)
            except (ToolError, ValueError, TypeError) as failure:
                self._fail(record, failure)
            return self._end(record, tool, result)

    # The same five tools as plain methods, for scripted controllers in the same process.

    def rules(self) -> Dict[str, Any]:
        return self.call("rules")

    def map(self) -> Dict[str, Any]:
        return self.call("map")

    def telemetry_log(self) -> List[Dict[str, Any]]:
        return self.call("telemetry_log")

    def uplink(self, commands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.call("uplink", {"commands": commands})

    def advance(self, ticks: int = 1) -> Dict[str, Any]:
        return self.call("advance", {"ticks": ticks})

    def _serve(self, tool: str, arguments: Dict[str, Any]) -> Any:
        if tool not in PUBLIC_TOOLS:
            raise ToolError("unknown tool {!r}; available: {}".format(tool, ", ".join(PUBLIC_TOOLS)))
        if self._closed:
            raise ToolError("the campaign is closed")
        if tool == "uplink":
            if set(arguments) != {"commands"}:
                raise ToolError("uplink takes exactly one argument: commands (a list of 1 to 5 commands)")
            if self._t0 is None:
                # A rejected request changes nothing, so it must not start the clock either.
                acknowledgements = self._env.uplink(arguments["commands"])
                self._start_clock()
                return acknowledgements
            self._sync()
            if self._done:
                raise ToolError("the campaign is over")
            return self._env.uplink(arguments["commands"])
        if arguments:
            raise ToolError("{} takes no arguments".format(tool))
        self._sync()
        result = getattr(self._env, tool)()
        if tool == "rules":
            result = dict(result, campaign=self._campaign_rules(), clock=self._clock_rules())
        elif tool == "map":
            result = dict(result, mission=self._index + 1)
        return result

    def _advance(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            record = self._begin("advance", arguments)
            try:
                if set(arguments) - {"ticks"}:
                    raise ToolError("advance takes one optional argument: ticks (an integer from 1 to 5)")
                ticks = arguments.get("ticks", 1)
                if type(ticks) is not int or not 1 <= ticks <= MAX_ADVANCE:
                    raise ToolError("ticks must be an integer from 1 to {}".format(MAX_ADVANCE))
                if self._closed:
                    raise ToolError("the campaign is closed")
            except ToolError as failure:
                self._fail(record, failure)
            if not self._done:
                self._start_clock()
                self._sync()
            if self._done:  # nothing left to wait for: answer at once so loops can end
                return self._end(record, "advance", self._advance_reply(len(self._missions) - 1, []))
            index = self._index
            target = min(self._tick + ticks, self._ticks)
            assert self._t0 is not None
            wake = self._t0 + (index * self._ticks + target) * self._seconds_per_tick
        remaining = wake - self._clock()
        if remaining > 0:
            self._sleep(remaining)  # outside the lock: other calls and the evaluator are not blocked
        with self._lock:
            if self._closed:
                self._fail(record, ToolError("the campaign is closed"))
            if self._index == index:
                self._step_to(target)  # this mission only; the next call moves on to the next one
                reply = self._advance_reply(index, self._unreported())
            else:  # another call already moved the campaign past this mission
                reply = self._advance_reply(index, self._leftover.pop(index, []))
            return self._end(record, "advance", reply)

    def _advance_reply(self, index: int, packets: List[Dict[str, Any]]) -> Dict[str, Any]:
        current = self._tick if index == self._index else self._ticks
        return {"current_tick": current, "episode_complete": current >= self._ticks,
                "campaign_complete": self._done, "mission": index + 1, "packets": packets}

    def _unreported(self) -> List[Dict[str, Any]]:
        packets = [packet for packet in self._env.telemetry_log()
                   if packet["received_tick"] > self._reported_until]
        self._reported_until = self._tick
        return packets

    def _campaign_rules(self) -> Dict[str, Any]:
        return {
            "missions": len(self._missions),
            "mission": self._index + 1,
            "ticks_per_mission": self._ticks,
            "complete": self._done,
            "next_mission": ("starts the moment this one ends, on a new map with a recharged rover at base; "
                             "rules(), map() and telemetry_log() then describe the new mission"),
            "scoring": "the campaign's score is the mean of the missions' scores; each mission is scored as its rules say",
        }

    def _clock_rules(self) -> Dict[str, Any]:
        return {
            "mode": "real_time",
            "seconds_per_tick": self._seconds_per_tick,
            "started": self._t0 is not None,
            "starts": "at your first uplink or advance; rules, map and telemetry_log are free before that",
            "stops": "never: ticks pass whether or not you call a tool, and each mission follows the last",
            "seconds_elapsed": round(self._elapsed(), 3),
            "advance": ("waits until that many more ticks have passed, never past the end of the mission, and "
                        "returns every packet received since your previous advance"),
        }

    # -- evaluator-facing ----------------------------------------------------------------

    def finish(self) -> Dict[str, Any]:
        """Close the campaign, run every remaining tick at once, grade, write artifacts.

        Safe to call more than once; later calls return the same result.
        """
        with self._lock:
            self._closed = True
            if not self._done:
                self._finished_by = "evaluator"
                self._step_to(self._ticks)
                while not self._done:
                    self._roll()
                    self._step_to(self._ticks)
            assert self._result is not None
            return json.loads(json.dumps(self._result))

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def result(self) -> Optional[Dict[str, Any]]:
        """The campaign's grade once every mission has ended. Evaluator use only."""
        with self._lock:
            return None if self._result is None else json.loads(json.dumps(self._result))

    def transcript(self) -> List[Dict[str, Any]]:
        with self._lock:
            return json.loads(json.dumps(self._transcript))

    # -- clock ---------------------------------------------------------------------------

    def _elapsed(self) -> float:
        return 0.0 if self._t0 is None else self._clock() - self._t0

    def _start_clock(self) -> None:
        if self._t0 is None:
            self._t0 = self._clock()

    def _wall_tick(self) -> int:
        """Ticks since the start of the campaign according to the wall clock, capped at its end."""
        total = len(self._missions) * self._ticks
        return min(total, int(math.floor(self._elapsed() / self._seconds_per_tick + 1e-9)))

    def _sync(self) -> None:
        """Bring the campaign up to the wall clock, moving into later missions as they start."""
        if self._t0 is None or self._done:
            return
        now = self._wall_tick()
        while True:
            end = (self._index + 1) * self._ticks
            self._step_to(min(now, end) - self._index * self._ticks)
            if self._done or self._tick < self._ticks or now < end:
                return
            self._roll()

    def _step_to(self, local_tick: int) -> None:
        """Advance the current mission to `local_tick`; grade it when it reaches its horizon."""
        before = self._tick
        while self._tick < local_tick:
            self._tick = self._env.advance(min(MAX_ADVANCE, local_tick - self._tick))["current_tick"]
        if self._tick > before:
            self._record({"n": None, "tool": "clock", "arguments": {"ticks": self._tick - before},
                          "ok": True, "mission": self._index + 1, "tick_before": before,
                          "tick_after": self._tick})
        if self._tick >= self._ticks and len(self._results) == self._index:
            self._grade_mission()

    def _roll(self) -> None:
        """Move on to the next mission. Its clock started when the previous one ended."""
        self._leftover[self._index] = self._unreported()
        self._open(self._index + 1)

    def _open(self, index: int) -> None:
        mission = self._missions[index]
        self._index = index
        self._env = DynamicEnvironment(seed=mission["seed"], config=self._config,
                                       profile=mission["profile"], noise_level=self._noise_level)
        self._tick = 0
        self._reported_until = 0
        if self._artifact_dir:
            os.makedirs(self._mission_dir(index), exist_ok=True)
            with open(os.path.join(self._mission_dir(index), "transcript.jsonl"), "w", encoding="utf-8"):
                pass

    # -- grading and artifacts -----------------------------------------------------------

    def _grade_mission(self) -> None:
        evaluation = self._env.evaluate()
        available = evaluation["max_available_value"]
        reward = evaluation["raw_score"] / available if available > 0 else 0.0
        mission = self._missions[self._index]
        self._results.append(dict(evaluation, mission=self._index + 1, profile=mission["profile"],
                                  seed=mission["seed"], reward=reward))
        if self._artifact_dir:
            self._write(os.path.join(self._mission_dir(self._index), "result.json"), self._results[-1])
            self._write(os.path.join(self._mission_dir(self._index), "replay.json"), self._env.replay())
        if self._index == len(self._missions) - 1:
            self._done = True
            rewards = [result["reward"] for result in self._results]
            self._result = {
                "version": VERSION,
                "reward": sum(rewards) / len(rewards),
                "missions": self._results,
                "clock_started": self._t0 is not None,
                "finished_by": self._finished_by or "clock",
                "seconds_per_tick": self._seconds_per_tick,
                "ticks_per_mission": self._ticks,
                "delay_ticks": self._config.delay_ticks,
                "tool_calls": self._calls,
            }
            if self._artifact_dir:
                self._write(os.path.join(self._artifact_dir, "result.json"), self._result)

    def _mission_dir(self, index: int) -> str:
        assert self._artifact_dir is not None
        return os.path.join(self._artifact_dir, "missions", "{:02d}".format(index + 1))

    @staticmethod
    def _write(path: str, payload: Any) -> None:
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)

    # -- transcript ----------------------------------------------------------------------

    def _begin(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        self._calls += 1
        return {"n": self._calls, "tool": tool, "arguments": arguments,
                "mission": self._index + 1, "tick_before": self._tick}

    def _fail(self, record: Dict[str, Any], failure: Exception) -> None:
        record.update(ok=False, error=str(failure), tick_after=self._tick)
        self._record(record)
        if isinstance(failure, ToolError):
            raise failure
        raise ToolError(str(failure)) from None

    def _end(self, record: Dict[str, Any], tool: str, result: Any) -> Any:
        record.update(ok=True, summary=self._summarise(tool, result))
        if tool == "advance":  # an advance belongs to the mission it waited in
            record.update(mission=result["mission"], tick_after=result["current_tick"])
        else:
            record.update(mission=self._index + 1, tick_after=self._tick)
        self._record(record)
        return result

    def _record(self, record: Dict[str, Any]) -> None:
        if self._t0 is not None:
            record = dict(record, wall_seconds=round(self._elapsed(), 3))
        self._transcript.append(record)
        if not self._artifact_dir:
            return
        line = json.dumps(record, sort_keys=True) + "\n"
        with open(os.path.join(self._artifact_dir, "transcript.jsonl"), "a", encoding="utf-8") as stream:
            stream.write(line)
        mission_dir = self._mission_dir(record["mission"] - 1)
        if os.path.isdir(mission_dir):
            with open(os.path.join(mission_dir, "transcript.jsonl"), "a", encoding="utf-8") as stream:
                stream.write(line)

    @staticmethod
    def _summarise(tool: str, result: Any) -> Dict[str, Any]:
        """A compact note per call; the replays hold the full state."""
        if tool == "uplink":
            return {"execute_ticks": [ack["execute_tick"] for ack in result]}
        if tool == "advance":
            return {"current_tick": result["current_tick"], "episode_complete": result["episode_complete"],
                    "campaign_complete": result["campaign_complete"],
                    "packet_ticks": [packet["tick"] for packet in result["packets"]]}
        if tool == "telemetry_log":
            return {"packets": len(result)}
        return {}
