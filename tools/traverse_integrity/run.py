"""Run the integrity probes against a disposable copy of the campaign task, through Harbor.

    python -m tools.traverse_integrity.run --out <folder> [--mode probe|block] [--seeds 1201,1202,1203]

Copies harbor/lightlag-traverse-campaign to <folder>/task, gives the copy its own seeds (the
judged worlds are never played), runs tools.traverse_integrity.agent:ProbeAgent on it with Harbor
0.25.0 and writes <folder>/report-<mode>.json: every attempt, and the reward Harbor reported
beside the simulator's own result. Needs Docker and uv. No model or API call.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
TASK = REPO / "harbor" / "lightlag-traverse-campaign"
HARBOR = ["uvx", "--from", "harbor==0.25.0", "harbor"]
AGENT = "tools.traverse_integrity.agent:ProbeAgent"


def replica(out: Path, seeds: str) -> Path:
    """A copy of the task that differs from the judged one in its seeds and nothing else."""
    target = out / "task" / TASK.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(TASK, target)
    compose = target / "environment" / "docker-compose.yaml"
    text, count = re.subn(r'LIGHTLAG_SEEDS: "[0-9, ]+"', 'LIGHTLAG_SEEDS: "{}"'.format(seeds), compose.read_text())
    if count != 1:
        raise SystemExit("could not set the seeds in the copy")
    compose.write_text(text)
    return target


def play(task: Path, out: Path, mode: str) -> Optional[Path]:
    name = "integrity-{}".format(mode)
    job = out / "jobs" / name
    if job.exists():
        shutil.rmtree(job)
    environment = dict(os.environ, PYTHONPATH=str(REPO), LIGHTLAG_PROBE_MODE=mode)
    subprocess.run(HARBOR + ["run", "-p", str(task), "-a", AGENT, "-o", str(out / "jobs"), "--job-name", name],
                   cwd=REPO, env=environment, check=False)
    trials = sorted(path for path in job.iterdir() if path.is_dir()) if job.exists() else []
    return trials[0] if trials else None


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def report(trial: Path, seeds: str, mode: str) -> Dict[str, Any]:
    result = load(trial / "result.json") or {}
    harbor = ((result.get("verifier_result") or {}).get("rewards") or {}).get("reward")
    exception = (result.get("exception_info") or {}).get("exception_type")
    simulator = load(trial / "artifacts" / "evaluator" / "result.json")
    own = simulator["raw_score"] / simulator["max_available_value"] if simulator else None
    probe = load(trial / "agent" / "probe.json") or {"findings": []}
    calls: List[Dict[str, Any]] = []
    transcript = trial / "artifacts" / "evaluator" / "transcript.jsonl"
    if transcript.exists():
        calls = [json.loads(line) for line in transcript.read_text().splitlines() if line.strip()]
    refused = [call for call in calls if not call["ok"]]
    rules = json.dumps(probe.get("rules", {}))
    named = [seed for seed in seeds.split(",") if re.search(r"(?<![0-9.]){}(?![0-9.])".format(seed.strip()), rules)]
    findings = list(probe["findings"])
    findings.append({"group": "transcript", "attack": "a refused call moving the clock",
                     "held": all(call["tick_before"] == call["tick_after"] for call in refused),
                     "seen": "{} of {} calls refused, none moved the clock".format(len(refused), len(calls))})
    findings.append({"group": "tools", "attack": "the seeds as numbers inside the rules' generator and campaign blocks",
                     "held": not named, "seen": named or "none of {}".format(seeds)})
    if mode == "probe":
        findings.append({"group": "reward", "attack": "the reward Harbor reports after the forgeries",
                         "held": harbor is not None and own is not None and abs(harbor - own) < 1e-6 and harbor == 0.0,
                         "seen": "Harbor reward {}, the simulator's own result {} (sampled {})".format(
                             harbor, own, simulator.get("sampled_targets") if simulator else None)})
    else:
        findings.append({"group": "reward", "attack": "the reward Harbor reports when the reward files cannot be written",
                         "held": harbor is None or harbor == 0.0,
                         "seen": "Harbor reward {}, exception {}; the simulator's own result {}".format(harbor, exception, own)})
    stdout = trial / "verifier" / "test-stdout.txt"
    return {"mode": mode, "seeds": seeds, "trial": trial.name, "harbor_reward": harbor, "harbor_exception": exception,
            "simulator_reward": own, "tool_calls": len(calls), "refused_calls": len(refused),
            "verifier_output": stdout.read_text()[-600:] if stdout.exists() else None, "findings": findings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--mode", choices=("probe", "block"), default="probe")
    parser.add_argument("--seeds", default="1201,1202,1203")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    trial = play(replica(out, args.seeds), out, args.mode)
    if trial is None:
        print("Harbor left no trial folder", file=sys.stderr)
        return 1
    summary = report(trial, args.seeds, args.mode)
    (out / "report-{}.json".format(args.mode)).write_text(json.dumps(summary, indent=1) + "\n")
    for finding in summary["findings"]:
        print("[{}] {}: {} -> {}".format({True: "held", False: "BROKEN", None: "note"}[finding["held"]],
                                         finding["group"], finding["attack"], finding["seen"]))
    broken = [finding for finding in summary["findings"] if finding["held"] is False]
    print("\n{} attempts, {} broke a boundary. Harbor reward {}, the simulator's own {}.".format(
        len(summary["findings"]), len(broken), summary["harbor_reward"], summary["simulator_reward"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
