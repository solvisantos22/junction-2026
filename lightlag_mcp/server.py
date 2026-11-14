"""MCP server for one Lightlag episode. Requires the `mcp` package, version 2.x.

The tool descriptions below are everything an agent is told about how to act, so
they state the timing rules in full. They must stay consistent with `rules()`.
"""

from __future__ import annotations

import hmac
import json
from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as McpToolError
from starlette.requests import Request
from starlette.responses import JSONResponse

from .service import EpisodeService, ToolError

INSTRUCTIONS = """\
Lightlag: you drive a rover through a signal delay.

Goal: sample science targets and end the episode at base. Score = total credited \
sample value under the episode's sampling rules x 1.0 if the rover ends within \
base_radius of base, x 0.5 if it ends alive elsewhere, x 0 if the battery reached \
zero. It is scored when the episode's fixed number of ticks has passed.

Timing: a command you send at tick t executes at tick t + delay_ticks + 1 at the \
earliest, one command per tick, in order. A telemetry packet describes the rover at \
packet.tick and reaches you delay_ticks later, so what you read is the past. Only \
`advance` moves the clock; every other tool is free.

Unknown: how much the wheels slip on each terrain. `rules` gives the range. Compare \
wheel_odometry with visual_odometry in telemetry to estimate slip. `rules` defines \
measurement accuracy.

Start with `rules` and `map`. You may write and run code to plan.\
"""

RULES_DESCRIPTION = (
    "Published rules for this episode: delay_ticks, max_ticks, battery and energy costs, slip range "
    "per terrain, sampling and base radius, and command limits. Free: does not advance time."
)
MAP_DESCRIPTION = (
    "Currently available public map and target information: size in metres, base position, targets "
    "(id, x, y, value), hazard rectangles and sand rectangles (x1, y1, x2, y2). Everything not sand is "
    "bedrock. `rules` defines target discoveries and their timing. Free: does not advance time."
)
TELEMETRY_DESCRIPTION = (
    "Every telemetry packet received so far, oldest first. Each packet has tick (the moment it describes), "
    "received_tick, position [x, y], heading_deg (commanded heading), battery, terrain, wheel_odometry "
    "(wheel distance in metres during that tick), visual_odometry (reported movement in metres during "
    "that tick), sampled_targets, alive and events. `rules` defines measurement accuracy. "
    "Packets are delay_ticks old when they arrive. Free: does not advance time."
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


def build_server(service: EpisodeService, evaluator_token: Optional[str] = None) -> MCPServer:
    """An MCP server exposing exactly the five public tools of `service`.

    With `evaluator_token`, an HTTP deployment also gets `POST /evaluator/finish`,
    which closes and grades the episode for callers presenting that bearer token.
    Without a token the route answers 404, so it cannot be probed into existence.
    """
    server = MCPServer("lightlag", instructions=INSTRUCTIONS)

    def call(tool: str, arguments: Optional[Dict[str, Any]] = None) -> str:
        """One JSON text result per call, in exactly the simulator's own shape.

        A request the agent can fix comes back as a tool error carrying the reason,
        so interface mistakes are visible to it and not mistaken for a hard task.
        """
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
