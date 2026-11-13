"""Connect the dynamic pilot to the team's code and compare everything on one table.

  python3 -m lightlag_dynamic.crosscheck                 # profiles static + rush, delays 0 3 5, seeds 0-19
  python3 -m lightlag_dynamic.crosscheck --hard          # also with the team pilot's tougher physics

Runs, on the same seeds:
  * this pilot's controllers (reference, leg_and_wait, open_loop, stale_telemetry, window_blind)
  * the team's controllers from lightlag_controllers/ (team_reference, team_move_and_wait,
    team_open_loop, team_stale), unchanged, through their own drive() loop
and checks that the team's evaluator, lightlag.evaluation.run_episode, gives the same score
for a dynamic episode as this pilot's runner.

"--hard" applies the rule variant the team pilot recommends (docs/lightlag-pilot.md):
sampling radius 0.4 m, slip noise +-0.08, sand slip 0.15-0.60, via the team's own
physics_overrides() helper. Nothing in the team repository is modified on disk.
"""

import argparse
import contextlib
import statistics
import sys

from lightlag import Config
import lightlag.evaluation as team_evaluation
from lightlag_controllers import (MOVE_AND_WAIT, OPEN_LOOP_NOMINAL, REFERENCE, STALE_TELEMETRY,
                                  as_policy)
from lightlag_controllers.pilot import physics_overrides

from .controllers import POLICIES
from .environment import DynamicEnvironment
from .missions import PROFILES
from .tools import run_episode

TEAM_POLICIES = {"team_reference": as_policy(REFERENCE),
                 "team_move_and_wait": as_policy(MOVE_AND_WAIT),
                 "team_open_loop": as_policy(OPEN_LOOP_NOMINAL),
                 "team_stale": as_policy(STALE_TELEMETRY)}
OURS = ["reference", "leg_and_wait", "open_loop", "stale_telemetry", "window_blind"]
HARD = {"radius": 0.4, "noise": 0.08, "sand_slip": (0.15, 0.60)}


@contextlib.contextmanager
def team_evaluator_with(profile):
    """Let lightlag.evaluation.run_episode build a DynamicEnvironment for one block."""
    original = team_evaluation.Environment

    def build(seed=0, config=None, world=None):
        return DynamicEnvironment(seed=seed, config=config, profile=profile)

    team_evaluation.Environment = build
    try:
        yield
    finally:
        team_evaluation.Environment = original


def evaluator_agreement(profile, seeds, delay, overrides):
    """Same policy, same seed: this pilot's runner and the team evaluator must agree."""
    horizon = PROFILES[profile][4]
    mismatches = []
    with team_evaluator_with(profile):
        for seed in seeds:
            ours = run_episode(POLICIES["reference"], seed, delay, profile, config_overrides=overrides)
            theirs = team_evaluation.run_episode(
                POLICIES["reference"], seed=seed,
                config=Config(delay_ticks=delay, max_ticks=horizon, **overrides))
            if abs(ours["result"]["raw_score"] - theirs["result"]["raw_score"]) > 1e-9:
                mismatches.append(seed)
    return mismatches


def run(profiles, delays, seeds, hard):
    overrides = {"target_radius": HARD["radius"]} if hard else {}
    physics = physics_overrides(HARD["noise"], HARD["sand_slip"]) if hard else contextlib.nullcontext()
    policies = {name: POLICIES[name] for name in OURS}
    policies.update(TEAM_POLICIES)
    table = []
    with physics:
        for profile in profiles:
            mismatches = evaluator_agreement(profile, seeds[:5], 3, overrides)
            print(f"[{profile}{' hard' if hard else ''}] team evaluator agrees with pilot runner on "
                  f"{5 - len(mismatches)}/5 seeds" + (f" (mismatch: {mismatches})" if mismatches else ""),
                  file=sys.stderr)
            for delay in delays:
                scores = {name: [] for name in policies}
                homes = {name: 0 for name in policies}
                for seed in seeds:
                    for name, policy in policies.items():
                        r = run_episode(policy, seed, delay, profile, policy_name=name,
                                        config_overrides=overrides)["result"]
                        scores[name].append(r["raw_score"])
                        homes[name] += r["at_base"] and r["alive"]
                ref = scores["reference"]
                for name in policies:
                    ratios = [s / q for s, q in zip(scores[name], ref) if q > 0]
                    table.append({"profile": profile + (" + hard physics" if hard else ""),
                                  "delay": delay, "policy": name,
                                  "mean": statistics.mean(scores[name]),
                                  "vs_ref": statistics.mean(ratios) if ratios else None,
                                  "home": homes[name] / len(seeds)})
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cross-check the dynamic pilot with the team's code")
    parser.add_argument("--profiles", nargs="+", default=["static", "rush"], choices=list(PROFILES))
    parser.add_argument("--delays", nargs="+", type=int, default=[0, 3, 5])
    parser.add_argument("--seeds", type=int, nargs=2, default=[0, 19], metavar=("FIRST", "LAST"))
    parser.add_argument("--hard", action="store_true", help="also run with the team pilot's tougher physics")
    args = parser.parse_args(argv)
    seeds = list(range(args.seeds[0], args.seeds[1] + 1))
    table = run(args.profiles, args.delays, seeds, hard=False)
    if args.hard:
        table += run(args.profiles, args.delays, seeds, hard=True)
    names = OURS + list(TEAM_POLICIES)
    print("| profile | delay | " + " | ".join(names) + " |")
    print("|---|---|" + "---|" * len(names))
    keyed = {(r["profile"], r["delay"], r["policy"]): r for r in table}
    for profile, delay in dict.fromkeys((r["profile"], r["delay"]) for r in table):
        cells = []
        for name in names:
            r = keyed[(profile, delay, name)]
            share = "" if r["vs_ref"] is None or name == "reference" else f" ({r['vs_ref']:.0%})"
            home = "" if r["home"] == 1 else f" h{r['home']:.0%}"
            cells.append(f"{r['mean']:.2f}{share}{home}")
        print(f"| {profile} | {delay} | " + " | ".join(cells) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
