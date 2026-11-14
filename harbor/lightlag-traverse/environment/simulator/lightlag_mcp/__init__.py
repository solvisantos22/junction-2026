"""The Lightlag simulator as an MCP service.

`service` needs only the standard library. `server` and `client` need the `mcp`
package (2.x, Python 3.10+) and are imported on demand.
"""

from .service import PUBLIC_TOOLS, EpisodeService, ToolError

__all__ = ["PUBLIC_TOOLS", "EpisodeService", "ToolError"]
