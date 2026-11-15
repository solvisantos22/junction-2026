#!/usr/bin/env python3
"""Three labs, three tiers: GPT and Gemini agents on Kristján's Traverse tasks.

    python3 tools/tier_agents/run_tiers.py            # run everything not yet saved
    python3 tools/tier_agents/run_tiers.py --dry-run  # print the plan only

Each run is one Harbor trial exactly like Kristján's Claude agent runs: OpenCode
1.19.5 in Harbor 0.25.0, `--agent-setup-timeout-multiplier 3`, the unchanged task
folders `harbor/lightlag-traverse-campaign/` (worlds 2027, 2028, 2029) and
`harbor/lightlag-traverse/` (world 2026), the model's default settings. The Claude
column is Kristján's own runs in docs/lightlag-runs/ (not rerun here).

Order: cheapest tier first (bottom, middle, top), the two labs side by side, up to
--parallel trials at once. A run starts only if its lab's spend (priced from the
tokens each finished run reports) plus a worst case for every running trial stays
under --budget dollars.

Every finished trial is copied to docs/lightlag-runs/<name>/ by harbor/save_run.py
(local paths replaced, credentials refused) and gets one line in
docs/tier-comparison/runs.jsonl. A run whose folder already exists is skipped, so
the script can be stopped and started again. Keys come from .env:
OPENAI_API_KEY and GOOGLE_API_KEY (see tools/tier_agents/run.sh).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNS = REPO / "docs" / "lightlag-runs"
LEDGER = REPO / "docs" / "tier-comparison" / "runs.jsonl"
RUNNER = REPO / "tools" / "tier_agents" / "run.sh"

# Brand tiers, decided by Manh on 15 November 2026. Claude 5.5 is Kristján's runs.
LINEUP = [
    # tier, lab, model selector, short name used in folder names
    ("bottom", "openai", "openai/gpt-6-luna", "gpt-6-luna"),
    ("bottom", "google", "gemini/gemini-4-hydrogen", "gemini-4-hydrogen"),
    ("middle", "openai", "openai/gpt-6.1-terra", "gpt-6.1-terra"),
    ("middle", "google", "gemini/gemini-4-argon", "gemini-4-argon"),
    ("top", "openai", "openai/gpt-6.1-sol", "gpt-6.1-sol"),
    ("top", "google", "gemini/gemini-4-carbon", "gemini-4-carbon"),
]
TASKS = [
    # task folder, run-name prefix (Kristján's names: campaign-agent-opus-1, traverse-agent-opus-1)
    ("harbor/lightlag-traverse-campaign", "campaign-agent"),
    ("harbor/lightlag-traverse", "traverse-agent"),
]
REPEATS = 3

# US dollars per 1M tokens: input, cached input, output. From
# https://developers.openai.com/api/docs/pricing and https://aistudio.google.com/docs/pricing,
# read 15 November 2026 (Gemini 4 Argon and Carbon prices hold until 30 November 2026).
PRICES = {
    "gpt-6-luna": (0.10, 0.01, 0.50),
    "gpt-6.1-terra": (1.00, 0.05, 5.00),
    "gpt-6.1-sol": (2.00, 0.10, 10.00),
    "gemini-4-hydrogen": (1.50, 0.075, 7.50),
    "gemini-4-argon": (2.00, 0.10, 10.00),
    "gemini-4-carbon": (2.00, 0.10, 10.00),
}


def worst_case(short):
    """A run's cost if it read 0.8M tokens with no cache hits and wrote 40k: the reservation."""
    price_in, _, price_out = PRICES[short]
    return (800_000 * price_in + 40_000 * price_out) / 1e6


def plan():
    """Every run, in launch order: tier by tier, repeat by repeat, the labs alternating."""
    runs = []
    for tier in ("bottom", "middle", "top"):
        members = [row for row in LINEUP if row[0] == tier]
        for repeat in range(1, REPEATS + 1):
            for task, prefix in TASKS:
                for _, lab, selector, short in members:
                    runs.append({"tier": tier, "lab": lab, "model": selector, "short": short,
                                 "task": task, "name": f"{prefix}-{short}-{repeat}", "repeat": repeat})
    return runs


def cost_of(short, agent_result):
    price_in, price_cached, price_out = PRICES[short]
    total_in = agent_result.get("n_input_tokens") or 0
    cached = agent_result.get("n_cache_tokens") or 0
    out = agent_result.get("n_output_tokens") or 0
    return (max(total_in - cached, 0) * price_in + cached * price_cached + out * price_out) / 1e6


def summarise(run, trial):
    result = json.loads((trial / "result.json").read_text())
    agent = result.get("agent_result") or {}
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    log = trial / "agent" / "opencode.txt"
    text = log.read_text(errors="replace") if log.exists() else ""
    errors = sorted({name for name in ("ProviderAuthError", "APIError", "ProviderModelNotFoundError")
                     if f'"name":"{name}"' in text})
    return {
        **{k: run[k] for k in ("name", "tier", "lab", "model", "task", "repeat")},
        "reward": rewards.get("reward"),
        "input_tokens": agent.get("n_input_tokens"),
        "cached_tokens": agent.get("n_cache_tokens"),
        "output_tokens": agent.get("n_output_tokens"),
        "cost_usd_from_prices": round(cost_of(run["short"], agent), 4),
        "cost_usd_reported_by_opencode": agent.get("cost_usd"),
        "agent_errors": errors,
        "exception": (result.get("exception_info") or {}).get("exception_type"),
        "task_checksum": result.get("task_checksum"),
        "agent_info": result.get("agent_info"),
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--parallel", type=int, default=6, help="trials at once (each is two containers)")
    parser.add_argument("--budget", type=float, default=18.0, help="dollars per lab before it stops taking runs")
    parser.add_argument("--only", help="comma-separated short model names to run, e.g. gpt-6-luna")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resave", action="store_true",
                        help="save again every ledger run marked unsaved (save_run.py --check-env .env), then stop")
    args = parser.parse_args(argv)

    if args.resave:
        rows = [json.loads(line) for line in LEDGER.read_text().splitlines()]
        for row in rows:
            trials = sorted((REPO / "jobs" / row["name"]).glob("*__*"))
            if row.get("saved") or not trials:
                continue
            saved = subprocess.run([sys.executable, str(REPO / "harbor" / "save_run.py"), str(trials[0]), row["name"],
                                    "--check-env", str(REPO / ".env")], cwd=REPO, capture_output=True, text=True)
            row["saved"] = saved.returncode == 0
            print(row["name"], "saved" if row["saved"] else "NOT saved: " + saved.stderr.strip()[:200])
        LEDGER.write_text("".join(json.dumps(row) + "\n" for row in rows))
        return 0

    runs = [r for r in plan() if not (RUNS / r["name"]).exists()]
    if args.only:
        keep = set(args.only.split(","))
        runs = [r for r in runs if r["short"] in keep]
    if args.dry_run:
        for r in runs:
            print(f'{r["tier"]:6} {r["model"]:26} {r["task"]:34} {r["name"]}')
        return 0

    spent = {"openai": 0.0, "google": 0.0}
    reserved = {"openai": 0.0, "google": 0.0}
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            row = json.loads(line)
            spent[row["lab"]] = spent.get(row["lab"], 0.0) + (row.get("cost_usd_from_prices") or 0.0)
    lock = threading.Lock()
    LEDGER.parent.mkdir(parents=True, exist_ok=True)

    def one(run):
        hold = worst_case(run["short"])
        with lock:
            if spent[run["lab"]] + reserved[run["lab"]] + hold > args.budget:
                print(f'skip {run["name"]}: {run["lab"]} spent ${spent[run["lab"]]:.2f}, '
                      f'${reserved[run["lab"]]:.2f} held by running trials', flush=True)
                return
            reserved[run["lab"]] += hold
        try:
            _play(run)
        finally:
            with lock:
                reserved[run["lab"]] -= hold

    def _play(run):
        done = subprocess.run(["bash", str(RUNNER), run["task"], run["model"], run["name"]],
                              cwd=REPO, capture_output=True, text=True)
        print(done.stdout.strip() or done.stderr.strip(), flush=True)
        trials = sorted((REPO / "jobs" / run["name"]).glob("*__*"))
        if not trials or not (trials[0] / "result.json").exists():
            print(f'{run["name"]}: no trial result', flush=True)
            return
        row = summarise(run, trials[0])
        saved = subprocess.run([sys.executable, str(REPO / "harbor" / "save_run.py"), str(trials[0]), run["name"],
                                "--check-env", str(REPO / ".env")],
                               cwd=REPO, capture_output=True, text=True)
        row["saved"] = saved.returncode == 0
        with lock:
            spent[run["lab"]] += row["cost_usd_from_prices"]
            with LEDGER.open("a") as ledger:
                ledger.write(json.dumps(row) + "\n")
            print(f'{run["name"]}: reward {row["reward"]}, ${row["cost_usd_from_prices"]:.3f}, '
                  f'{run["lab"]} total ${spent[run["lab"]]:.2f}, errors {row["agent_errors"]}, '
                  f'saved {row["saved"]} {saved.stderr.strip()[:200]}', flush=True)

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        list(pool.map(one, runs))
    print(f'done; spent openai ${spent["openai"]:.2f}, google ${spent["google"]:.2f}', flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
