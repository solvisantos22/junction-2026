"""Play the whole campaign with the team's frozen KF + MPC controller, through the public tools."""

import argparse
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    from campaign_reference import play_campaign
    from lightlag_client import connect
    from lightlag_dynamic.controllers import POLICIES

    started = time.time()
    with connect(args.url) as tools:
        if set(tools.tool_names()) != {"rules", "map", "telemetry_log", "uplink", "advance"}:
            raise RuntimeError("the task offers exactly the five public tools")
        play_campaign(tools, POLICIES["kf_mpc"],
                      on_mission=lambda number: print("mission {} at {:.0f}s".format(number, time.time() - started),
                                                      flush=True))
    print("kf_mpc finished the campaign through public MCP tools in {:.0f}s".format(time.time() - started))


if __name__ == "__main__":
    sys.exit(main())
