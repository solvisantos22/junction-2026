#!/usr/bin/env python3
"""Play one Lightlag episode with the reference controller, over MCP.

    python3 play_reference.py --url http://lightlag:8000/mcp
    python3 play_reference.py --url http://lightlag:8000/mcp --strategy open_loop_nominal

`lightlag_controllers/` and `mcp_client.py` beside this file are copies made by
harbor/sync_task.py. The controller sees only what the five tools return.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from lightlag_controllers import ALL_STRATEGIES, drive, make
from mcp_client import connect


def main(argv: Optional[Sequence[str]] = None) -> int:
    strategies = {strategy.name: strategy for strategy in ALL_STRATEGIES}
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="the lightlag MCP endpoint")
    parser.add_argument("--strategy", choices=sorted(strategies), default="reference")
    args = parser.parse_args(argv)
    controller = make(strategies[args.strategy])
    with connect(args.url) as tools:
        usage = drive(tools, controller)
    print("{} finished: {} commands in {} uplinks, {} advances".format(
        args.strategy, usage["commands_sent"], usage["uplinks"], usage["advances"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
