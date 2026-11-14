"""Run a delivered dynamic controller through the same five MCP tools as a model."""

import argparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--policy", choices=("kf_mpc", "open_loop", "leg_and_wait"), default="kf_mpc")
    args = parser.parse_args()
    from lightlag_dynamic.controllers import POLICIES
    from mcp_client import connect

    with connect(args.url) as tools:
        expected = {"rules", "map", "telemetry_log", "uplink", "advance"}
        if set(tools.tool_names()) != expected:
            raise RuntimeError("the experiment requires exactly the five public tools")
        POLICIES[args.policy](tools)
    print(args.policy + " finished through public MCP tools")


if __name__ == "__main__":
    main()
