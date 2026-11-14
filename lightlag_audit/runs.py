"""Load a saved Lightlag run folder and line up the agent's tool calls with the simulator's record.

A run folder is what `harbor/save_run.py` and Sölvi's experiment tooling write under
`docs/lightlag-runs/<name>/`:

    artifacts/evaluator/transcript.jsonl   every call that reached the simulator (MCP service)
    artifacts/evaluator/replay.json        evaluator-only truth: states, commands, telemetry
    artifacts/evaluator/result.json        the evaluator's score
    agent/trajectory.json                  the model's messages and tool calls (model runs only)
    result.json                            Harbor's trial record, including exception_info
    verifier/reward.txt                    the 0-1 reward the judges see

Only the transcript and replay are required. Everything here is read-only.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

STATE_TOOLS = ("uplink", "advance")
TOOLS = ("rules", "map", "telemetry_log", "uplink", "advance")


@dataclass
class AgentCall:
    """One tool call as the agent made it, with its own words from the same step."""
    tool: str
    arguments: Dict[str, Any]
    step_id: Any
    message: str
    result_text: str
    transcript_n: Optional[int] = None  # None: the call never reached the simulator


@dataclass
class Run:
    name: str
    path: Path
    transcript: List[Dict[str, Any]]
    replay: Dict[str, Any]
    evaluator_result: Dict[str, Any]
    reward: Optional[float]
    trial: Dict[str, Any]
    has_transcript: bool = True
    agent_calls: List[AgentCall] = field(default_factory=list)
    unmatched_agent_calls: List[AgentCall] = field(default_factory=list)
    model: Optional[str] = None

    @property
    def is_model_run(self):
        return bool(self.agent_calls)

    def agent_call_for(self, n):
        for call in self.agent_calls:
            if call.transcript_n == n:
                return call
        return None


def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_run(path) -> Run:
    path = Path(path)
    evaluator = path / "artifacts" / "evaluator"
    if not (evaluator / "replay.json").exists():
        raise FileNotFoundError(f"{path}: no artifacts/evaluator/replay.json")
    transcript = []
    transcript_path = evaluator / "transcript.jsonl"
    if transcript_path.exists():
        with open(transcript_path, encoding="utf-8") as handle:
            transcript = [json.loads(line) for line in handle if line.strip()]
    replay = _read_json(evaluator / "replay.json")
    result_path = evaluator / "result.json"
    evaluator_result = _read_json(result_path) if result_path.exists() else replay.get("result", {})
    reward = None
    reward_path = path / "verifier" / "reward.txt"
    if reward_path.exists():
        try:
            reward = float(reward_path.read_text().strip())
        except ValueError:
            reward = None
    trial = _read_json(path / "result.json") if (path / "result.json").exists() else {}
    run = Run(path.name, path, transcript, replay, evaluator_result, reward, trial,
              has_transcript=transcript_path.exists())
    trajectory_path = path / "agent" / "trajectory.json"
    if trajectory_path.exists():
        _attach_trajectory(run, _read_json(trajectory_path))
    return run


def _tool_name(function_name):
    """`lightlag_uplink` (OpenCode's MCP naming) or `uplink` -> `uplink`; others -> None."""
    name = function_name.split("__")[-1]
    if name.startswith("lightlag_"):
        name = name[len("lightlag_"):]
    return name if name in TOOLS else None


def _attach_trajectory(run, trajectory):
    steps = trajectory.get("steps", []) if isinstance(trajectory, dict) else trajectory
    agent = trajectory.get("agent", {}) if isinstance(trajectory, dict) else {}
    calls = []
    for step in steps:
        if step.get("source") != "agent":
            continue
        run.model = run.model or step.get("model_name") or agent.get("model_name")
        words = " ".join(str(step.get(key) or "") for key in ("reasoning_content", "message")).strip()
        results = {}
        for item in (step.get("observation") or {}).get("results", []) or []:
            results[item.get("source_call_id")] = str(item.get("content", ""))
        for tool_call in step.get("tool_calls") or []:
            tool = _tool_name(tool_call.get("function_name", ""))
            if tool is None:
                continue
            calls.append(AgentCall(tool, tool_call.get("arguments") or {}, step.get("step_id"), words,
                                   results.get(tool_call.get("tool_call_id"), "")))
    # Pair in order: the simulator records calls in the order it received them.
    index = 0
    for call in calls:
        if index < len(run.transcript) and run.transcript[index]["tool"] == call.tool:
            call.transcript_n = run.transcript[index]["n"]
            index += 1
            run.agent_calls.append(call)
        else:
            run.unmatched_agent_calls.append(call)
