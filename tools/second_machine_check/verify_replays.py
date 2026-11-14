#!/usr/bin/env python3
"""Re-simulate every saved Lightlag Traverse run from its command log and compare with what was saved.

    python3 tools/second_machine_check/verify_replays.py                      # every traverse-* and campaign-* run
    python3 tools/second_machine_check/verify_replays.py campaign-            # only the campaign runs
    python3 tools/second_machine_check/verify_replays.py --runs <folder> ...  # another folder of runs

A saved run holds the evaluator's replay: the world's seed and settings, every command with the
tick it was sent, every true state and every telemetry packet. For each mission of each run the
commands are sent again, at the same ticks, to a fresh `TraverseEnvironment` of that seed. The
acknowledgements, the whole replay, the result and the verifier's reward must come out the same.

So a score in `docs/lightlag-runs/` can be checked without Docker, Harbor or a model: a Claude run
cannot be repeated (the model answers differently every time), but what it sent is saved, and
the simulator is deterministic. Read-only. Standard library only, Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from lightlag_traverse.environment import TraverseEnvironment  # noqa: E402

RUNS = REPO / "docs" / "lightlag-runs"
PREFIXES = ("traverse-", "campaign-")


def normalized(value: Any) -> Any:
    """The value as it reads back from JSON, so a fresh replay compares with a saved one."""
    return json.loads(json.dumps(value, allow_nan=False))


def replay_mission(replay: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """Play one saved mission again. Returns what differs (empty when nothing does) and the new result."""
    env = TraverseEnvironment(replay["seed"], mission=replay["config"])
    by_tick: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for command in replay["commands"]:
        by_tick[command["sent_tick"]].append(command)
    problems: List[str] = []
    for tick in range(replay["config"]["max_ticks"]):
        for command in by_tick.pop(tick, []):
            if normalized(env.uplink([command["command"]])) != [command]:
                problems.append("the acknowledgement at tick {} differs".format(tick))
        env.advance(1)
    if by_tick:
        problems.append("commands sent after the last tick")
    again = normalized(env.replay())
    if again != replay:
        problems.append("the replay differs in {}".format(sorted(key for key in replay if again.get(key) != replay[key])))
    return problems, env.evaluate()


def check_run(run: Path) -> Dict[str, Any]:
    """One run folder: every mission played again, the results and the verifier's reward compared."""
    evaluator = run / "artifacts" / "evaluator"
    missions = sorted(path for path in (evaluator / "missions").iterdir() if path.is_dir()) \
        if (evaluator / "missions").exists() else [evaluator]
    problems: List[str] = []
    raw, most, rewards = 0.0, 0.0, []
    for folder in missions:
        if not (folder / "replay.json").exists():
            problems.append("{}: no replay.json".format(folder.name))
            continue
        replay = json.loads((folder / "replay.json").read_text(encoding="utf-8"))
        found, result = replay_mission(replay)
        problems += ["{}: {}".format(folder.name, problem) for problem in found]
        saved = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        for key in ("raw_score", "max_available_value", "alive", "at_base", "sampled_targets"):
            if result[key] != saved[key]:
                problems.append("{}: result {} is {}, saved {}".format(folder.name, key, result[key], saved[key]))
        raw += result["raw_score"]
        most += result["max_available_value"]
        rewards.append(result["raw_score"] / result["max_available_value"])
    reward = raw / most if most else float("nan")
    graded = run / "verifier" / "reward.txt"
    if graded.exists() and not math.isclose(float(graded.read_text()), reward, abs_tol=1e-6):
        problems.append("the verifier wrote {}, recomputed {:.6f}".format(graded.read_text().strip(), reward))
    return {"run": run.name, "missions": len(missions), "reward": reward, "mission_rewards": rewards,
            "verifier_file": graded.exists(), "problems": problems}


def find_runs(folder: Path = RUNS, prefixes: Sequence[str] = PREFIXES) -> List[Path]:
    return sorted(path for path in folder.iterdir()
                  if path.is_dir() and path.name.startswith(tuple(prefixes)) and (path / "artifacts" / "evaluator").exists())


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("prefixes", nargs="*", default=list(PREFIXES), help="run folder name prefixes")
    parser.add_argument("--runs", type=Path, default=RUNS, help="the folder holding the run folders")
    parser.add_argument("--json", type=Path, default=None, help="also write the rows here")
    args = parser.parse_args(argv)
    rows = []
    for run in find_runs(args.runs, args.prefixes):
        row = check_run(run)
        rows.append(row)
        print("{:<28} {} mission{}  reward {:.6f} [{}]  {}  {}".format(
            row["run"], row["missions"], " " if row["missions"] == 1 else "s", row["reward"],
            " ".join("{:.3f}".format(r) for r in row["mission_rewards"]),
            "verifier agrees" if row["verifier_file"] and not row["problems"] else
            "no verifier file" if not row["verifier_file"] else "",
            "REPRODUCED" if not row["problems"] else "MISMATCH: " + "; ".join(row["problems"][:4])), flush=True)
    bad = sum(bool(row["problems"]) for row in rows)
    print("{} runs, {} with a mismatch (Python {})".format(len(rows), bad, sys.version.split()[0]))
    if args.json:
        args.json.write_text(json.dumps({"python": sys.version.split()[0], "runs": rows}, indent=1) + "\n", encoding="utf-8")
    return 1 if bad or not rows else 0


if __name__ == "__main__":
    sys.exit(main())
