"""Run an expedition reference through the same public MCP tools as the model."""

import argparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--policy", choices=("reference", "no_probe", "value_blind", "leader_probe", "entropy_probe", "forced_leader_probe", "nop"), default="reference")
    args = parser.parse_args()
    if args.policy == "nop":
        print("No-op: no commands; trusted evaluator completes the horizon.")
        return
    from lightlag_expedition.reference import run_policy
    from mcp_client import connect

    with connect(args.url) as tools:
        if set(tools.tool_names()) != {"rules", "map", "telemetry_log", "uplink", "advance"}:
            raise RuntimeError("expected exactly the five public expedition tools")
        result = run_policy(tools, args.policy)
    print("Policy finished through public MCP tools:", result)


if __name__ == "__main__":
    main()
