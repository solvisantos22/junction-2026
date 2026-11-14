"""One protected rover expedition; public tools and durable evaluator evidence."""

from copy import deepcopy
import json
import math
from pathlib import Path
import threading

from .environment import ExpeditionEnvironment

PUBLIC_TOOLS = ("rules", "map", "telemetry_log", "uplink", "advance")


class ToolError(ValueError):
    """A rejected public request."""


def _json_safe_record(value):
    """Retain invalid numeric inputs as explicit evidence, never executable inputs."""
    if isinstance(value, float) and not math.isfinite(value):
        label = "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
        return {"__nonfinite_float__": label}
    if isinstance(value, dict):
        return {key: _json_safe_record(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_record(item) for item in value]
    return deepcopy(value)


class ExpeditionService:
    def __init__(self, seed, mission_seed=0, visibility="hidden", artifact_dir=None):
        self._env = ExpeditionEnvironment(seed=seed, mission_seed=mission_seed, visibility=visibility)
        rules = self._env.rules()
        self._horizon = rules["max_ticks"]
        self._max_advance = rules["max_advance_ticks"]
        self._tick = 0
        self._closed = False
        self._result = None
        self._lock = threading.Lock()
        self._transcript = []
        self._artifact_dir = Path(artifact_dir) if artifact_dir else None
        if self._artifact_dir:
            self._artifact_dir.mkdir(parents=True, exist_ok=True)
            # A restart must not replace any existing episode's evidence.
            for name in ("result.json", "replay.json", "result.json.tmp", "replay.json.tmp"):
                if (self._artifact_dir / name).exists():
                    raise FileExistsError("episode artifact already exists: " + name)
            (self._artifact_dir / "transcript.jsonl").open("x").close()

    def call(self, tool, arguments=None):
        with self._lock:
            record = {"n": len(self._transcript) + 1, "tool": tool,
                      "arguments": deepcopy(arguments), "tick_before": self._tick}
            try:
                if self._closed:
                    raise ToolError("episode is closed")
                if not isinstance(tool, str) or tool not in PUBLIC_TOOLS:
                    raise ToolError("unknown public tool")
                if arguments is None:
                    arguments = {}
                if not isinstance(arguments, dict):
                    raise ToolError("arguments must be an object")
                if tool in ("rules", "map", "telemetry_log"):
                    if arguments:
                        raise ToolError(tool + " takes no arguments")
                elif tool == "uplink":
                    if set(arguments) != {"commands"}:
                        raise ToolError("uplink takes exactly commands")
                elif set(arguments) - {"ticks"}:
                    raise ToolError("advance accepts only optional ticks")
                result = getattr(self._env, tool)(**arguments)
                if tool == "advance":
                    self._tick = result["current_tick"]
            except (ValueError, TypeError) as error:
                record.update(ok=False, error=str(error), tick_after=self._tick)
                self._record(record)
                raise ToolError(str(error)) from None
            record.update(ok=True, result=deepcopy(result), tick_after=self._tick)
            self._record(record)
            if self._tick == self._horizon:
                self._grade()
            return deepcopy(result)

    def rules(self):
        return self.call("rules")

    def map(self):
        return self.call("map")

    def telemetry_log(self):
        return self.call("telemetry_log")

    def uplink(self, commands):
        return self.call("uplink", {"commands": commands})

    def advance(self, ticks=1):
        return self.call("advance", {"ticks": ticks})

    def finish(self):
        """Evaluator only: close public interaction and execute accepted commands."""
        with self._lock:
            if self._closed:
                return deepcopy(self._result)
            self._closed = True
            while self._tick < self._horizon:
                self._tick = self._env.advance(min(self._max_advance, self._horizon - self._tick))["current_tick"]
            self._grade()
            return deepcopy(self._result)

    def transcript(self):
        with self._lock:
            return deepcopy(self._transcript)

    def _record(self, record):
        record = _json_safe_record(record)
        serialized = json.dumps(record, sort_keys=True, allow_nan=False) + "\n"
        if self._artifact_dir:
            with (self._artifact_dir / "transcript.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(serialized)
        self._transcript.append(record)

    def _grade(self):
        evaluation = self._env.evaluate()
        self._result = dict(evaluation,
                            reward=evaluation["raw_score"] / evaluation["max_available_value"],
                            tool_calls=len(self._transcript))
        if self._artifact_dir:
            for name, value in (("result.json", self._result), ("replay.json", self._env.replay())):
                target = self._artifact_dir / name
                temporary = target.with_suffix(".json.tmp")
                temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
                temporary.replace(target)
