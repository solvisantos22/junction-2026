"""Play the campaign with the traverse pilot, mission after mission, through the public tools."""

import argparse
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    from lightlag_client import connect
    from lightlag_traverse.pilot import fly_campaign

    started = time.time()
    with connect(args.url) as tools:
        if set(tools.tool_names()) != {"rules", "map", "telemetry_log", "uplink", "advance"}:
            raise RuntimeError("the task offers exactly the five public tools")
        pilots = fly_campaign(tools)
    print("the traverse pilot finished {} missions through public MCP tools in {:.0f}s; it believes it "
          "sampled {} targets".format(len(pilots), time.time() - started,
                                      " + ".join(str(len(pilot.sampled)) for pilot in pilots)))


if __name__ == "__main__":
    sys.exit(main())
