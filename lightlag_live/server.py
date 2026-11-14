"""MCP server for one Lightlag Live campaign. Requires the `mcp` package, version 2.x.

The tool descriptions below are everything an agent is told about how to act, so they state
the clock and the timing rules in full. They must stay consistent with `rules()`.

Every tool call runs in a worker thread: `advance` waits for real time to pass, and the
server must keep answering other calls (and the evaluator) while it does.
"""

from __future__ import annotations

import asyncio
import hmac
import json
from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as McpToolError
from starlette.requests import Request
from starlette.responses import JSONResponse

from .campaign import CampaignService, ToolError


def instructions(seconds_per_tick: float) -> str:
    return """\
Lightlag Live: you operate a rover through a signal delay, in real time, over several missions in a row.

Goal: in each mission, sample science targets and end the mission at base. A mission's score = \
total credited sample value under its sampling rules x 1.0 if the rover ends within base_radius \
of base, x 0.5 if it ends alive elsewhere, x 0 if the battery reached zero, divided by the total \
value generated for that mission. The campaign's score is the mean of the missions' scores.

Clock: one tick passes every {seconds:g} seconds of real time. The clock starts at your first \
`uplink` or `advance`; before that `rules`, `map` and `telemetry_log` are free, so prepare for as \
long as you like. Once started it never stops, whether or not you call a tool. Each mission lasts \
max_ticks ticks and the next one starts the moment it ends, on a new map with a recharged rover at \
base; `rules`, `map` and `telemetry_log` then describe the new mission.

Timing: a command you send at tick t executes at tick t + delay_ticks + 1 at the earliest, one \
command per tick, in order. A telemetry packet describes the rover at packet.tick and reaches you \
delay_ticks later, so what you read is the past.

Unknown: how much the wheels slip on each terrain, and, when `rules` lists sensing noise, the \
rover's true position and its heading bias. `rules` gives the ranges and the measurement accuracy.

Nobody can keep up with this clock by calling tools by hand. Write a program that drives, start it, \
and let it run; you may change it while it runs.\
""".format(seconds=seconds_per_tick)


RULES_DESCRIPTION = (
    "Published rules for the mission in progress: delay_ticks, max_ticks, battery and energy costs, slip range "
    "per terrain, sampling and base radius, command limits, sensing accuracy, plus `campaign` (how many "
    "missions, which one this is, whether the campaign is complete) and `clock` (tick length, whether it has "
    "started). Answers at once; never starts the clock."
)
MAP_DESCRIPTION = (
    "Currently available public map and target information for the mission in progress: size in metres, base "
    "position, targets (id, x, y, value, deadline_tick, late_value, appear_tick), hazard rectangles and sand "
    "rectangles (x1, y1, x2, y2), and `mission` (its number). Everything not sand is bedrock. `rules` defines "
    "target discoveries and their timing. Answers at once; never starts the clock."
)
TELEMETRY_DESCRIPTION = (
    "Every telemetry packet received so far in the mission in progress, oldest first. Each packet has tick "
    "(the moment it describes), received_tick, position [x, y], heading_deg (commanded heading), battery, "
    "terrain, wheel_odometry (wheel distance in metres during that tick), visual_odometry (reported movement "
    "in metres during that tick), sampled_targets, alive and events. `rules` defines measurement accuracy. "
    "Packets are delay_ticks old when they arrive. Answers at once; never starts the clock."
)
UPLINK_DESCRIPTION = (
    "Send 1 to 5 commands to the mission in progress. They execute in order, one per tick. The first executes "
    "at current_tick + delay_ticks + 1, or one tick after the last command already queued, whichever is later. "
    'Commands: {"action": "drive", "heading_deg": H, "metres": M} with heading 0 = east and 90 = north and '
    'M the wheel distance in (0, 5]; {"action": "sample"} collects the nearest unsampled target if the rover '
    'is within target_radius, and costs energy either way; {"action": "wait"}. Returns the execute_tick '
    "of each command. A request with any invalid command, or one that would execute after the mission's last "
    "tick, is rejected whole and changes nothing. Your first accepted uplink starts the real-time clock."
)


def advance_description(seconds_per_tick: float) -> str:
    return (
        "Wait until 1 to 5 more ticks have passed (default 1), never past the end of the mission; one tick is "
        "{:g} seconds of real time and the clock runs whether or not you call this. Returns current_tick, "
        "episode_complete (this mission has ended), campaign_complete, mission (its number) and every "
        "telemetry packet that arrived since your previous advance. After episode_complete the next call is "
        "answered by the next mission. Your first advance starts the real-time clock."
    ).format(seconds_per_tick)


def build_server(service: CampaignService, evaluator_token: Optional[str] = None,
                 seconds_per_tick: float = 1.0) -> MCPServer:
    """An MCP server exposing exactly the five public tools of `service`.

    With `evaluator_token`, an HTTP deployment also gets `POST /evaluator/finish`, which closes
    and grades the campaign for callers presenting that bearer token. Without a token the route
    answers 404, so it cannot be probed into existence.
    """
    server = MCPServer("lightlag", instructions=instructions(seconds_per_tick))

    async def call(tool: str, arguments: Optional[Dict[str, Any]] = None) -> str:
        """One JSON text result per call. A request the agent can fix comes back as a tool
        error carrying the reason, so interface mistakes are visible to it."""
        try:
            result = await asyncio.to_thread(service.call, tool, arguments)
        except ToolError as failure:
            raise McpToolError(str(failure)) from None
        return json.dumps(result, separators=(",", ":"))

    @server.tool(name="rules", description=RULES_DESCRIPTION, structured_output=False)
    async def rules() -> str:
        return await call("rules")

    @server.tool(name="map", description=MAP_DESCRIPTION, structured_output=False)
    async def map_() -> str:
        return await call("map")

    @server.tool(name="telemetry_log", description=TELEMETRY_DESCRIPTION, structured_output=False)
    async def telemetry_log() -> str:
        return await call("telemetry_log")

    @server.tool(name="uplink", description=UPLINK_DESCRIPTION, structured_output=False)
    async def uplink(commands: List[Dict[str, Any]]) -> str:
        return await call("uplink", {"commands": commands})

    @server.tool(name="advance", description=advance_description(seconds_per_tick), structured_output=False)
    async def advance(ticks: int = 1) -> str:
        return await call("advance", {"ticks": ticks})

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
        result = await asyncio.to_thread(service.finish)
        return JSONResponse(json.loads(json.dumps(result)))

    return server
