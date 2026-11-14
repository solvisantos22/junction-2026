"""Five public MCP tools for the expedition; evaluator closure is token protected."""

import hmac
import json
from typing import Any, Dict, List

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as McpToolError
from pydantic import StrictInt
from starlette.requests import Request
from starlette.responses import JSONResponse

from .service import ToolError

INSTRUCTIONS = """Drive a rover to collect science and return to base within the fixed
simulated horizon. Read rules and map for all costs, terrain, target windows,
regional quality priors and sensor accuracy. Regional quality is shared by the
targets in that region: one observation can affect several route decisions.
There are two inspections total, at most one per region; each spends energy and
returns one imperfect rich/poor signal in delayed telemetry. Samples also provide
science evidence. Quality is fixed throughout the episode. Public visibility
episodes publish actual regional qualities in rules.
Commands execute FIFO, one per tick, no earlier than sent_tick + delay_ticks + 1.
Telemetry describes packet.tick and arrives delay_ticks later. Wheel slip is
unknown; compare wheel and visual odometry and obey the published sensing rules.
Only advance moves simulated time. Reading tools, thinking and scripting are
free. There is no reset or evaluator access. Score is credited sampled value
times the survival/base-return factor, normalized by max_available_value."""


def build_server(service, evaluator_token=None):
    server = MCPServer("expedition", instructions=INSTRUCTIONS)

    def call(name, arguments=None):
        try:
            return json.dumps(service.call(name, arguments), separators=(",", ":"), allow_nan=False)
        except ToolError as error:
            raise McpToolError(str(error)) from None

    @server.tool(name="rules", description="All public rules: delay, horizon, energy, slip ranges, sensing accuracy, target and base radii, command limits, sample windows, regional quality priors/multipliers and inspection budget/cost/accuracy. Free; does not advance time.", structured_output=False)
    def rules() -> str:
        return call("rules")

    @server.tool(name="map", description="Current public map: size in metres, base, available targets with position/value/region/deadline, hazards and sand rectangles. New targets follow the discovery rules. Unmapped ground is bedrock. Free; does not reveal hidden qualities.", structured_output=False)
    def map_() -> str:
        return call("map")

    @server.tool(name="telemetry_log", description="All delivered telemetry packets, oldest first: tick, received_tick, position, heading_deg, battery, terrain, wheel_odometry, visual_odometry, sampled_targets, alive and events. Packets are delay_ticks old; tick 0 is the launch briefing. Inspection events contain one fixed rich/poor signal; rereading is not new evidence. Free.", structured_output=False)
    def telemetry_log() -> str:
        return call("telemetry_log")

    @server.tool(name="uplink", description='Send 1–5 commands atomically. {"action":"drive","heading_deg":H,"metres":M}, with 0=east, 90=north and wheel distance 0<M<=5; {"action":"sample"} collects the nearest eligible target within target_radius and costs energy even on a miss; {"action":"inspect","region":"r1"} (also r2/r3) spends inspection energy and yields delayed regional evidence, at most two total and once per region; {"action":"wait"}. FIFO, one command per tick, first no earlier than current_tick+delay_ticks+1 or after existing reservations. Returns acknowledgements with execute_tick. Invalid batches change nothing. Does not move time.', structured_output=False)
    def uplink(commands: List[Dict[str, Any]]) -> str:
        return call("uplink", {"commands": commands})

    @server.tool(name="advance", description="Advance 1–5 simulated ticks (default 1), clipped at the horizon. Returns current_tick, episode_complete, and packets delivered during those ticks. This is the only public tool that moves time. If you stop early, accepted commands still execute through the horizon.", structured_output=False)
    def advance(ticks: StrictInt = 1) -> str:
        return call("advance", {"ticks": ticks})

    @server.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(request: Request):
        return JSONResponse({"status": "ok"})

    @server.custom_route("/evaluator/finish", methods=["POST"], include_in_schema=False)
    async def finish(request: Request):
        expected = "Bearer " + evaluator_token if evaluator_token else ""
        presented = request.headers.get("authorization", "")
        if not evaluator_token or not hmac.compare_digest(presented.encode(), expected.encode()):
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse(service.finish())

    return server
