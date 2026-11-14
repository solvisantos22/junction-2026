"""Play a Lightlag MCP server from ordinary, synchronous Python.

`connect(target)` yields an object with the five public methods, each making a
real MCP tool call. Scripted controllers can therefore run through the same
service a model would use:

    from lightlag_controllers import REFERENCE, drive, make
    from lightlag_mcp.client import connect

    with connect("http://127.0.0.1:8000/mcp") as tools:
        drive(tools, make(REFERENCE))

`target` is a URL (Streamable HTTP), `StdioServerParameters`, or a server object
for in-process tests. Requires the `mcp` package, version 2.x.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import json
import threading
from typing import Any, Dict, Iterator, List

from mcp import Client


class RemoteToolError(ValueError):
    """The server rejected a call. A ValueError, like the simulator's own rejections."""


class McpTools:
    """The five public methods, each a blocking MCP tool call."""

    def __init__(self, client: Client, loop: asyncio.AbstractEventLoop) -> None:
        self._client = client
        self._loop = loop

    def _call(self, tool: str, arguments: Dict[str, Any]) -> Any:
        future = asyncio.run_coroutine_threadsafe(self._client.call_tool(tool, arguments), self._loop)
        result = future.result()
        text = "".join(getattr(block, "text", "") for block in result.content)
        if result.is_error:
            raise RemoteToolError(text)
        return json.loads(text)

    def rules(self) -> Dict[str, Any]:
        return self._call("rules", {})

    def map(self) -> Dict[str, Any]:
        return self._call("map", {})

    def telemetry_log(self) -> List[Dict[str, Any]]:
        return self._call("telemetry_log", {})

    def uplink(self, commands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._call("uplink", {"commands": commands})

    def advance(self, ticks: int = 1) -> Dict[str, Any]:
        return self._call("advance", {"ticks": ticks})

    def tool_names(self) -> List[str]:
        future = asyncio.run_coroutine_threadsafe(self._client.list_tools(), self._loop)
        return [tool.name for tool in future.result().tools]


@contextlib.contextmanager
def connect(target: Any) -> Iterator[McpTools]:
    """Open an MCP session on a background event loop and yield blocking tools."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, name="lightlag-mcp-client", daemon=True)
    thread.start()
    ready: "concurrent.futures.Future[Client]" = concurrent.futures.Future()
    stop_holder: List[asyncio.Event] = []

    async def session() -> None:
        # The session is opened and closed inside one task, as the SDK requires.
        stop = asyncio.Event()
        stop_holder.append(stop)
        try:
            async with Client(target) as client:
                ready.set_result(client)
                await stop.wait()
        except BaseException as failure:
            if not ready.done():
                ready.set_exception(failure)
                return
            raise

    running = asyncio.run_coroutine_threadsafe(session(), loop)
    try:
        client = ready.result(timeout=30)
        try:
            yield McpTools(client, loop)
        finally:
            loop.call_soon_threadsafe(stop_holder[0].set)
            running.result(timeout=30)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        loop.close()
