"""Serve one traverse mission over MCP: the team's episode service, with wording for this ground.

    python -m lightlag_traverse.server --seed 7 --transport stdio
    python -m lightlag_traverse.server --transport http --host 0.0.0.0 --port 8000 --artifact-dir /evaluator

The lock, the transcript, the grading and the evaluator-only finish are `lightlag_mcp`'s
`EpisodeService`, unchanged; only the episode behind it and the tool descriptions differ. The
seed may come from LIGHTLAG_SEED, the artifact folder from LIGHTLAG_ARTIFACT_DIR, the token
file from LIGHTLAG_TOKEN_FILE. Serving needs the `mcp` package (2.x); the service does not.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import signal
import sys
from typing import Any, Dict, List, Optional, Sequence

from lightlag_mcp.service import EpisodeService, ToolError

from .environment import TraverseEnvironment


class TraverseEpisodeService(EpisodeService):
    """lightlag_mcp's EpisodeService, playing a traverse mission."""

    def __init__(self, seed: int, artifact_dir: Optional[str] = None) -> None:
        super().__init__(seed=seed, artifact_dir=artifact_dir)
        # Swap the episode before any tool call; the lock, transcript and grading are unchanged.
        self._env = TraverseEnvironment(seed)
        rules = self._env.rules()
        self._max_ticks = rules["max_ticks"]
        self._max_advance = rules["max_advance_ticks"]


INSTRUCTIONS = """\
Lightlag Traverse: you drive a rover across Mars-like ground for one long mission, through a \
signal delay.

Goal: sample science targets and end the mission at the lander. Score = credited sample value \
x 1.0 if the rover ends within base_radius of the lander, x 0.5 if it ends alive elsewhere, x 0 \
if the battery reached zero, divided by the value of every target of the mission. It is scored \
when max_ticks have passed.

Timing: a command you send at tick t executes at tick t + delay_ticks + 1 at the earliest, one \
command per tick, in order. A telemetry packet describes the rover at packet.tick and reaches \
you delay_ticks later. Only `advance` moves the clock; every other tool is free.

The ground: `map` gives a height grid and a terrain class per cell. Slip, sideways slide and \
energy depend on the slope and the terrain; ground steeper than max_tilt stops the rover and \
clears its queue. The battery is charged by a sun that climbs and sinks over the mission. \
`rules` gives every formula and number.

Start with `rules` and `map`. The map is large, so read it with a program. You may write and \
run code.\
"""

RULES_DESCRIPTION = (
    "Published rules for this mission: timing, the drive physics on sloping ground (slip, sideways slide, "
    "the tilt limit), energy and solar charging, sensing noise, sampling, deadlines, discoveries and the "
    "reward. Free: does not advance time."
)
MAP_DESCRIPTION = (
    "The public map: width, height and cell_m in metres; elevation_cm[j][i], the height in centimetres at "
    "x = i * cell_m, y = j * cell_m; terrain[j], one class code per grid cell (terrain_codes names them); the "
    "lander (base) and the targets known so far (id, x, y, value, deadline_tick, late_value, appear_tick). "
    "About 65 kB of JSON. `rules` defines how the ground acts on the rover. Free: does not advance time."
)
TELEMETRY_DESCRIPTION = (
    "Every telemetry packet received so far, oldest first. Each packet has tick (the moment it describes), "
    "received_tick, position [x, y], heading_deg (commanded heading), battery, charge (solar energy gained "
    "that tick), terrain, tilt (slope under the rover), wheel_odometry, visual_odometry, sampled_targets, "
    "alive and events. `rules` defines measurement accuracy. Packets are delay_ticks old when they arrive. "
    "Free: does not advance time."
)
UPLINK_DESCRIPTION = (
    "Send 1 to 5 commands. They execute in order, one per tick. The first executes at "
    "current_tick + delay_ticks + 1, or one tick after the last command already queued, whichever is later. "
    'Commands: {"action": "drive", "heading_deg": H, "metres": M} with heading 0 = east and 90 = north and '
    'M the wheel distance in (0, 5]; {"action": "sample"} collects the nearest unsampled target if the rover '
    'is within target_radius, and costs energy either way; {"action": "wait"}. Returns the execute_tick '
    "of each command. A request with any invalid command is rejected whole and changes nothing. "
    "Does not advance time."
)
ADVANCE_DESCRIPTION = (
    "Let 1 to 5 ticks pass (default 1). This is the only tool that moves the clock. Returns current_tick, "
    "episode_complete and the telemetry packets that arrived during those ticks."
)


def build_server(service: EpisodeService, evaluator_token: Optional[str] = None):
    """An MCP server exposing exactly the five public tools of `service`.

    With `evaluator_token`, an HTTP deployment also gets `POST /evaluator/finish`, which closes and
    grades the mission for callers presenting that bearer token. Without one the route answers 404.
    """
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError as McpToolError
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    server = MCPServer("lightlag", instructions=INSTRUCTIONS)

    def call(tool: str, arguments: Optional[Dict[str, Any]] = None) -> str:
        try:
            return json.dumps(service.call(tool, arguments), separators=(",", ":"))
        except ToolError as failure:
            raise McpToolError(str(failure)) from None

    @server.tool(name="rules", description=RULES_DESCRIPTION, structured_output=False)
    def rules() -> str:
        return call("rules")

    @server.tool(name="map", description=MAP_DESCRIPTION, structured_output=False)
    def map_() -> str:
        return call("map")

    @server.tool(name="telemetry_log", description=TELEMETRY_DESCRIPTION, structured_output=False)
    def telemetry_log() -> str:
        return call("telemetry_log")

    @server.tool(name="uplink", description=UPLINK_DESCRIPTION, structured_output=False)
    def uplink(commands: List[Dict[str, Any]]) -> str:
        return call("uplink", {"commands": commands})

    @server.tool(name="advance", description=ADVANCE_DESCRIPTION, structured_output=False)
    def advance(ticks: int = 1) -> str:
        return call("advance", {"ticks": ticks})

    @server.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @server.custom_route("/evaluator/finish", methods=["POST"], include_in_schema=False)
    async def evaluator_finish(request: Request) -> JSONResponse:
        if not evaluator_token:
            return JSONResponse({"error": "not found"}, status_code=404)
        presented = request.headers.get("authorization", "")
        expected = "Bearer {}".format(evaluator_token)
        if not hmac.compare_digest(presented.encode(), expected.encode()):
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse(json.loads(json.dumps(service.finish())))

    return server


def main(argv: Optional[Sequence[str]] = None) -> int:
    env = os.environ.get
    parser = argparse.ArgumentParser(prog="lightlag_traverse.server",
                                     description="Serve one Lightlag Traverse mission over MCP.")
    parser.add_argument("--seed", type=int, default=int(env("LIGHTLAG_SEED")) if env("LIGHTLAG_SEED") else None)
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--artifact-dir", default=env("LIGHTLAG_ARTIFACT_DIR"),
                        help="evaluator-only directory for result.json, replay.json and transcript.jsonl")
    parser.add_argument("--token-file", default=env("LIGHTLAG_TOKEN_FILE"),
                        help="HTTP only: write a freshly generated evaluator token here when "
                             "LIGHTLAG_EVALUATOR_TOKEN is not set")
    args = parser.parse_args(argv)
    if args.seed is None:
        parser.error("a seed is required (--seed or LIGHTLAG_SEED)")

    service = TraverseEpisodeService(seed=args.seed, artifact_dir=args.artifact_dir)
    token = env("LIGHTLAG_EVALUATOR_TOKEN") or None
    if token is None and args.token_file and args.transport == "http":
        token = secrets.token_urlsafe(32)          # exists only inside this process's container
        os.makedirs(os.path.dirname(os.path.abspath(args.token_file)), exist_ok=True)
        descriptor = os.open(args.token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(token)
    server = build_server(service, evaluator_token=token)

    def finish() -> None:
        result = service.finish()
        print("lightlag traverse mission finished: raw_score={raw_score} of {max_available_value} "
              "sampled={sampled_targets} alive={alive} at_base={at_base} tool_calls={tool_calls}".format(**result),
              file=sys.stderr)

    def on_signal(signum: int, frame: object) -> None:
        finish()
        sys.exit(0)

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    try:
        if args.transport == "stdio":
            server.run("stdio")
        else:
            server.run("streamable-http", host=args.host, port=args.port)
    finally:
        finish()
    return 0


if __name__ == "__main__":
    sys.exit(main())
