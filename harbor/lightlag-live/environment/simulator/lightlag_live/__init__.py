"""Lightlag Live: several unchanged Lightlag missions in a row on a real-time clock.

A proposal, not a rules decision (see docs/lightlag-live.md). It adds a way to *serve* the
team's missions; it changes no file of `lightlag`, `lightlag_dynamic` or `lightlag_mcp`.

    python3 -m unittest discover -s tests/lightlag_live -v      # standard library only
    python3 -m lightlag_live --help                              # the MCP server (needs `mcp`)

`campaign` needs only the standard library. `server` needs the `mcp` package (2.x).
"""

from .campaign import PUBLIC_TOOLS, CampaignService, ToolError
from .reference import play_campaign

__all__ = ["PUBLIC_TOOLS", "CampaignService", "ToolError", "play_campaign"]
