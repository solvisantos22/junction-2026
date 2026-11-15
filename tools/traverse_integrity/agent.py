"""A Harbor agent that attacks the task instead of playing it.

    harbor run -p <copy of the task> -a tools.traverse_integrity.agent:ProbeAgent

It does what a model's agent can do and nothing more: it puts one file, probe.py, into the agent's
container and runs it there. Unlike Harbor's `oracle` agent it brings no solution folder, so the
container is the one a model sees. `LIGHTLAG_PROBE_MODE` (probe, or block) picks what probe.py does.
Start it through `python -m tools.traverse_integrity.run`, which also makes the copy.
"""

from __future__ import annotations

import os
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.agents.capabilities import AgentCapabilities
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

PROBE = Path(__file__).with_name("probe.py")
OUTPUTS = ("probe.json", "probe.txt")


class ProbeAgent(BaseAgent):
    # The task declares an MCP server; the probe reaches it by its address, as a program would.
    capabilities = AgentCapabilities(mcp_servers=True)

    @staticmethod
    def name() -> str:
        return "lightlag-integrity-probe"

    def version(self) -> str:
        return "1"

    async def setup(self, environment: BaseEnvironment) -> None:
        return

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        mode = os.environ.get("LIGHTLAG_PROBE_MODE", "probe")
        await environment.upload_file(source_path=PROBE, target_path="/tmp/probe.py")
        await environment.exec(
            command="python3 /tmp/probe.py --mode {} --out /logs/agent/probe.json > /logs/agent/probe.txt 2>&1".format(mode),
            timeout_sec=900,
        )
        for name in OUTPUTS:                     # already there when Harbor mounts the log folder
            target = self.logs_dir / name
            if not target.exists():
                try:
                    await environment.download_file(source_path="/logs/agent/{}".format(name), target_path=target)
                except Exception as failure:     # the report says so if the file is missing
                    self.logger.error("could not fetch {}: {}".format(name, failure))
