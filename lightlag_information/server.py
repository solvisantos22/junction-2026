"""MCP transport for the information-choice microenvironment (mcp 2.x)."""

import hmac
import json
from typing import Any, Dict, List

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as McpToolError
from pydantic import StrictInt
from starlette.requests import Request
from starlette.responses import JSONResponse

from .service import ToolError

INSTRUCTIONS = """Choose one route to maximize expected realized mission reward.
Read rules and map: they publish the terrain prior, signal accuracy, inspection
energy cost, route outcomes, command delay and completion-time penalty.
You may obtain one costly soil probe before committing. Its signal is delayed.
Accepted route commitments cannot be changed, even while waiting to execute.
Only advance moves simulated time; other public calls are free. Scripting and
calculation are allowed. No reset or evaluator access is available."""


def build_server(service, evaluator_token=None):
    server = MCPServer("information-choice", instructions=INSTRUCTIONS)

    def call(name, arguments=None):
        try:
            return json.dumps(service.call(name, arguments), separators=(",", ":"), allow_nan=False)
        except ToolError as error:
            raise McpToolError(str(error)) from None

    @server.tool(name="rules", description="All public probabilities, energy costs, timing, command schema and realized reward rules. Free; does not advance time.", structured_output=False)
    def rules() -> str:
        return call("rules")

    @server.tool(name="map", description="Public route/target alternatives and uncertain terrain prior. Does not reveal the sampled terrain or future probe signal. Free.", structured_output=False)
    def map_() -> str:
        return call("map")

    @server.tool(name="telemetry_log", description="Current tick and all delivered events. Events describe state_tick and arrive at delivery_tick. A probe event contains one fixed signal; rereading it gives no independent evidence. Free.", structured_output=False)
    def telemetry_log() -> str:
        return call("telemetry_log")

    @server.tool(name="uplink", description='Accept 1–5 commands atomically: {"action":"probe"}, {"action":"commit","route":"shortcut"} or route "detour", and {"action":"wait"}. At most one probe and one commitment; probe must precede commitment in accepted order. Commitment freezes the route immediately. Execution is FIFO, starting no earlier than current_tick + delay + 1. Does not move time. Returns sent_tick and accepted commands with execution_tick.', structured_output=False)
    def uplink(commands: List[Dict[str, Any]]) -> str:
        return call("uplink", {"commands": commands})

    @server.tool(name="advance", description="Advance 1–5 simulated ticks (default 1), clipped at the horizon. Returns current_tick and cumulative delivered entries. This is the only public tool that moves time. Accepted commands still execute if you stop early.", structured_output=False)
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
