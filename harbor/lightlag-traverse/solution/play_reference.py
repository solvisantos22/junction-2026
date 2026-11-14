"""Play the mission with the traverse pilot, through the public tools."""

import argparse
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    from lightlag_client import connect
    from lightlag_traverse.pilot import fly

    started = time.time()
    with connect(args.url) as tools:
        if set(tools.tool_names()) != {"rules", "map", "telemetry_log", "uplink", "advance"}:
            raise RuntimeError("the task offers exactly the five public tools")
        pilot = fly(tools)
    print("the traverse pilot finished the mission through public MCP tools in {:.0f}s; it believes it "
          "sampled {} targets".format(time.time() - started, len(pilot.sampled)))


if __name__ == "__main__":
    sys.exit(main())
