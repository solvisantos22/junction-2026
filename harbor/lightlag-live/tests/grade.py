#!/usr/bin/env python3
"""Write the Harbor reward for one Lightlag Live campaign.

Reward = the mean over the campaign's missions of raw_score / max_available_value, in [0, 1]:

    raw_score = credited value of sampled targets x 1.0 at base, x 0.5 alive elsewhere, x 0 if dead

Only the simulator's result file is read. It comes from the simulator's container, which the
agent can reach through the five tools and nothing else. The mean is recomputed here from
the per-mission numbers and must agree with the simulator's. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, Optional, Sequence


class BadResult(ValueError):
    """The result file is absent or not what the simulator writes."""


def mission_reward(mission: Dict[str, Any]) -> float:
    try:
        raw = mission["raw_score"]
        available = mission["max_available_value"]
    except (KeyError, TypeError):
        raise BadResult("a mission lacks raw_score or max_available_value") from None
    for name, value in (("raw_score", raw), ("max_available_value", available)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise BadResult("{} is not a finite number".format(name))
    if available <= 0:
        raise BadResult("max_available_value must be positive")
    if raw < 0 or raw > available + 1e-9:
        raise BadResult("raw_score {} is outside 0..{}".format(raw, available))
    return min(1.0, max(0.0, raw / available))


def reward_from(result: Dict[str, Any]) -> float:
    try:
        missions = result["missions"]
        claimed = result["reward"]
    except (KeyError, TypeError):
        raise BadResult("result lacks missions or reward") from None
    if not isinstance(missions, list) or not missions:
        raise BadResult("missions must be a non-empty list")
    reward = sum(mission_reward(mission) for mission in missions) / len(missions)
    if isinstance(claimed, bool) or not isinstance(claimed, (int, float)) or abs(claimed - reward) > 1e-9:
        raise BadResult("the campaign reward does not match its missions")
    return reward


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--result", required=True, help="result.json written by the simulator")
    parser.add_argument("--reward", required=True, help="where to write the single reward number")
    parser.add_argument("--details", default=None, help="optional copy of the result plus the reward")
    args = parser.parse_args(argv)
    try:
        with open(args.result, encoding="utf-8") as stream:
            result = json.load(stream)
        reward = reward_from(result)
    except (OSError, ValueError) as failure:
        print("cannot grade: {}".format(failure), file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(os.path.abspath(args.reward)), exist_ok=True)
    with open(args.reward, "w", encoding="utf-8") as stream:
        stream.write("{:.6f}\n".format(reward))
    if args.details:
        with open(args.details, "w", encoding="utf-8") as stream:
            json.dump(dict(result, reward=reward), stream, indent=2, sort_keys=True)
            stream.write("\n")
    print("reward {:.6f} over {} missions: {}".format(
        reward, len(result["missions"]),
        ", ".join("{:.3f}{}".format(mission_reward(m), "" if m.get("alive") else " (rover lost)")
                  for m in result["missions"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
