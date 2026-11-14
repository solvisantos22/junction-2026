"""One Lightlag episode behind a lock, with an evaluator-only way to finish it.

Standard library only, Python 3.9+. This module has no MCP dependency: it is the
piece that decides what an agent can and cannot do, and it is tested on its own.

Agent-facing surface: exactly `rules`, `map`, `telemetry_log`, `uplink`, `advance`,
reached through `EpisodeService.call`. There is no reset, no seed choice, no score.

Evaluator-facing surface: `finish()`, which closes the episode to the agent, lets
the remaining ticks pass, grades it and writes the artifacts. Call it from trusted
code only.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Mapping, Optional

from lightlag import Config, Environment, World

PUBLIC_TOOLS = ("rules", "map", "telemetry_log", "uplink", "advance")


class ToolError(ValueError):
    """A request the agent can fix: unknown tool, bad arguments, closed episode."""


class EpisodeService:
    def __init__(
        self,
        seed: int,
        config: Optional[Config] = None,
        world: Optional[World] = None,
        artifact_dir: Optional[str] = None,
    ) -> None:
        self._env = Environment(seed=seed, config=config, world=world)
        self._max_ticks = self._env.rules()["max_ticks"]
        self._max_advance = self._env.rules()["max_advance_ticks"]
        self._lock = threading.Lock()
        self._tick = 0
        self._closed = False
        self._result: Optional[Dict[str, Any]] = None
        self._calls = 0
        self._artifact_dir = artifact_dir
        self._transcript: List[Dict[str, Any]] = []
        if artifact_dir:
            os.makedirs(artifact_dir, exist_ok=True)
            # Start a fresh transcript so a crashed run still leaves a readable trace.
            with open(os.path.join(artifact_dir, "transcript.jsonl"), "w", encoding="utf-8"):
                pass

    # -- agent-facing --------------------------------------------------------------

    def call(self, tool: str, arguments: Optional[Mapping[str, Any]] = None) -> Any:
        """Run one public tool. Calls are serialized; every call is recorded."""
        arguments = dict(arguments or {})
        with self._lock:
            self._calls += 1
            record: Dict[str, Any] = {
                "n": self._calls, "tool": tool, "arguments": arguments, "tick_before": self._tick,
            }
            try:
                result = self._dispatch(tool, arguments)
            except (ToolError, ValueError, TypeError) as failure:
                record.update(ok=False, error=str(failure), tick_after=self._tick)
                self._record(record)
                if isinstance(failure, ToolError):
                    raise
                raise ToolError(str(failure)) from None
            record.update(ok=True, tick_after=self._tick, summary=self._summarise(tool, result))
            self._record(record)
            if self._tick >= self._max_ticks and self._result is None:
                self._grade()
            return result

    # The same five tools as plain methods, for scripted policies in the same process.

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

    def _dispatch(self, tool: str, arguments: Dict[str, Any]) -> Any:
        if tool not in PUBLIC_TOOLS:
            raise ToolError("unknown tool {!r}; available: {}".format(tool, ", ".join(PUBLIC_TOOLS)))
        if self._closed:
            raise ToolError("the episode is closed")
        if tool in ("rules", "map", "telemetry_log"):
            if arguments:
                raise ToolError("{} takes no arguments".format(tool))
            return getattr(self._env, tool)()
        if tool == "uplink":
            if set(arguments) != {"commands"}:
                raise ToolError("uplink takes exactly one argument: commands (a list of 1 to 5 commands)")
            return self._env.uplink(arguments["commands"])
        if set(arguments) - {"ticks"}:
            raise ToolError("advance takes one optional argument: ticks (an integer from 1 to 5)")
        result = self._env.advance(arguments.get("ticks", 1))
        self._tick = result["current_tick"]
        return result

    # -- evaluator-facing ----------------------------------------------------------

    def finish(self) -> Dict[str, Any]:
        """Close the episode to the agent, run out the clock, grade, write artifacts.

        Safe to call more than once; later calls return the same result.
        """
        with self._lock:
            self._closed = True
            while self._tick < self._max_ticks:
                step = min(self._max_advance, self._max_ticks - self._tick)
                self._tick = self._env.advance(step)["current_tick"]
            if self._result is None:
                self._grade()
            assert self._result is not None
            return dict(self._result)

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def result(self) -> Optional[Dict[str, Any]]:
        """The grade, once the horizon has been reached. Evaluator use only."""
        return None if self._result is None else dict(self._result)

    def transcript(self) -> List[Dict[str, Any]]:
        with self._lock:
            return json.loads(json.dumps(self._transcript))

    # -- internals -----------------------------------------------------------------

    def _grade(self) -> None:
        evaluation = self._env.evaluate()
        self._result = dict(evaluation, tool_calls=self._calls)
        if not self._artifact_dir:
            return
        self._write("result.json", self._result)
        self._write("replay.json", self._env.replay())

    def _write(self, name: str, payload: Any) -> None:
        assert self._artifact_dir is not None
        path = os.path.join(self._artifact_dir, name)
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)

    def _record(self, record: Dict[str, Any]) -> None:
        self._transcript.append(record)
        if self._artifact_dir:
            with open(os.path.join(self._artifact_dir, "transcript.jsonl"), "a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, sort_keys=True) + "\n")

    @staticmethod
    def _summarise(tool: str, result: Any) -> Dict[str, Any]:
        """A compact note per call; the replay holds the full state."""
        if tool == "uplink":
            return {"execute_ticks": [ack["execute_tick"] for ack in result]}
        if tool == "advance":
            return {
                "current_tick": result["current_tick"],
                "episode_complete": result["episode_complete"],
                "packet_ticks": [packet["tick"] for packet in result["packets"]],
            }
        if tool == "telemetry_log":
            return {"packets": len(result)}
        return {}
