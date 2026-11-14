"""Find discriminative seeds: our feedback controllers nearly solve them, every shortcut fails.

    python3 -m lightlag_dynamic.manh_controllers.seeds --seeds 1000-1499 --profiles rush rush_noisy --delay 3

Settings match Sölvi's Harbor experiments: the profile's default horizon (50 on rush), noise
level 1, bumpiness 0, the given delay. Each seed is played once per player (the noise is seeded
by the episode seed, so an episode is deterministic).

Why: on seed 500 the Harbor reference (kf_mpc) and Claude Opus 5.5 both score 1.000 on rush and
rush_noisy, so that seed cannot show a model-vs-reference gap. A useful seed is one a feedback
controller using only the five public tools nearly solves, while each shortcut an agent might
take falls well short.

Players
  selectors   Manh controllers 19, 20, 21 and 24 (feedback, delay-aware, rule-aware)
  shortcuts   blind           (POLICIES["open_loop"]: plans once from the briefing, never reads telemetry)
              cautious        (POLICIES["leg_and_wait"]: one leg, then waits for all its telemetry)
              stale_telemetry (feedback that plans from the last packet as if it were the present)
              window_blind    (feedback that ignores deadlines and never re-reads the map)
  reported    controller 1 (the repo's kf_mpc, the frozen Harbor reference) and bound 16
              (exact hidden information); scored and shown, never selected on, so the list does
              not favour seeds where the reference happened to get lucky.
              no_drift: kf_mpc that believes the heading bias is zero (bias variance at the
              floor, no bias walk). It re-plans from every fix like an agent that never models
              drift; added after the search as a report-only column, never selected on.

Criteria, declared before any seed in the search range was played (per profile, per seed):
  feedback    every selector alive and home at the horizon, and min(selectors) >= 0.90
  tier 1      feedback, and max(blind, cautious) <= 0.60            ("needs feedback")
  tier 2      tier 1, and max(stale_telemetry, window_blind) <= 0.60  ("needs delay-aware,
              rule-aware feedback": ignoring the delay or the new rules is not enough either)
  ranking     by gap = min(selectors) - max(shortcuts in the tier), then by seed
Seeds passing a tier on every requested profile are listed separately.

Selection uses scripted controllers only, never a model's outcome. A seed where every shortcut
fails still need not be hard for a model: it shows the seed needs the behaviour, not that a
model lacks it. Search seeds no one else uses (1000+); 0-19, 100-139, 200-209, 300-319, 400-419
and 500-504 are taken by development, held-out checks and Sölvi's Harbor comparisons.
"""

import argparse
import json
import os
import statistics as st
import sys
from multiprocessing import Pool
from pathlib import Path

SELECTORS = ("19", "20", "21", "24")
TIER1_SHORTCUTS = ("blind", "cautious")
TIER2_SHORTCUTS = ("stale_telemetry", "window_blind")
REPORTED = ("1", "16")
PROXIES = ("no_drift",)  # report-only stand-ins, never selected on
FEEDBACK_FLOOR = 0.90
SHORTCUT_CEILING = 0.60
# Policies of lightlag_dynamic.controllers that the Manh registry does not hold.
EXTRA_POLICIES = ("stale_telemetry", "window_blind")


def _names():
    from .swarm import resolve
    return ({key: resolve([key])[0] for key in SELECTORS + REPORTED}
            | {k: k for k in TIER1_SHORTCUTS + TIER2_SHORTCUTS + PROXIES})


def no_drift(tools):
    """kf_mpc that believes the heading bias is zero: an agent that re-plans but never models drift."""
    from lightlag_dynamic.kf_mpc import VAR_FLOOR, KalmanMPCController
    controller = KalmanMPCController(tools)
    controller.filter.cov[2][2] = VAR_FLOOR
    controller.filter.q_walk = 0.0
    controller.run()


def play(job):
    """One episode: (player key, registry name or policy, profile, delay, seed) -> result row."""
    key, name, profile, delay, seed = job
    if key in EXTRA_POLICIES + PROXIES:
        from lightlag_dynamic.controllers import POLICIES
        from lightlag_dynamic.tools import PublicTools

        from .scenarios import make_env
        from .superlog import summarize
        env = make_env(seed, delay, profile)
        crash = None
        try:
            (no_drift if key == "no_drift" else POLICIES[name])(PublicTools(env))
        except Exception as exc:  # a controller error is a result, not a harness failure
            crash = f"{type(exc).__name__}: {exc}"[:200]
        while not env.advance(5)["episode_complete"]:
            pass
        row = summarize(env.scenario_replay(), None, crash)
    else:
        from .swarm import run_one
        row, _ = run_one((name, {"name": "default", "profile": profile}, delay, seed, False))
    return {"player": key, "profile": profile, "delay": delay, "seed": seed, "share": row["share"],
            "alive": row["alive"], "at_base": row["at_base"], "crash": row["crash"], "labels": row["labels"]}


def mission_features(profile, seed, horizon=None):
    from lightlag_dynamic.missions import PROFILES, make_mission
    mission = make_mission(profile, seed, horizon or PROFILES[profile][4])
    plans = mission.plans
    return {"targets_at_launch": sum(p.appear_tick == 0 for p in plans),
            "discoveries": sum(p.appear_tick > 0 for p in plans),
            "deadlines": sum(p.deadline_tick is not None for p in plans),
            "total_value": sum(p.value for p in plans)}


def judge(cell):
    """Apply the declared criteria to one (profile, seed) cell: {player key: row}."""
    sel = [cell[k] for k in SELECTORS]
    floor = min(r["share"] for r in sel)
    feedback = floor >= FEEDBACK_FLOOR and all(r["alive"] and r["at_base"] and not r["crash"] for r in sel)
    ceil1 = max(cell[k]["share"] for k in TIER1_SHORTCUTS)
    ceil2 = max(cell[k]["share"] for k in TIER1_SHORTCUTS + TIER2_SHORTCUTS)
    tier1 = feedback and ceil1 <= SHORTCUT_CEILING
    tier2 = tier1 and ceil2 <= SHORTCUT_CEILING
    return {"floor": floor, "feedback": feedback, "tier1": tier1, "tier2": tier2,
            "gap1": floor - ceil1, "gap2": floor - ceil2}


def score(seeds, profiles, delay, workers=1):
    """Play every player on every (profile, seed); returns {(profile, seed): cell} with verdicts."""
    names = _names()
    jobs = [(key, name, p, delay, s) for p in profiles for s in seeds for key, name in names.items()]
    if workers > 1:
        with Pool(workers) as pool:
            rows = list(pool.imap_unordered(play, jobs, chunksize=8))
    else:
        rows = [play(job) for job in jobs]
    cells = {}
    for row in rows:
        cells.setdefault((row["profile"], row["seed"]), {})[row["player"]] = row
    for (profile, seed), cell in cells.items():
        cell["features"] = mission_features(profile, seed)
        cell["verdict"] = judge(cell)
    return cells


def _row(seed, cell, gap_key):
    v, f = cell["verdict"], cell["features"]
    shares = " | ".join(f"{cell[k]['share']:.2f}" for k in COLUMNS)
    return (f"| {seed} | {v[gap_key]:+.2f} | {shares} | {f['targets_at_launch']}+{f['discoveries']} "
            f"| {f['deadlines']} | {f['total_value']:g} |")


COLUMNS = SELECTORS + REPORTED + PROXIES + TIER1_SHORTCUTS + TIER2_SHORTCUTS
LABELS = {"1": "kf_mpc", "16": "bound 16", "no_drift": "no-drift"}
HEADER = ("| Seed | Gap | 19 | 20 | 21 | 24 | kf_mpc (1) | bound 16 | no-drift | blind | cautious | stale | window-blind "
          "| Targets (launch+found) | Deadlines | Value |\n|---|" + "---|" * 15)


def report(cells, profiles, delay, top=10):
    seeds = sorted({s for _, s in cells})
    lines = [f"# Discriminative seeds: {', '.join(profiles)}, delay {delay}, seeds {seeds[0]}-{seeds[-1]}", "",
             "Criteria and players: `lightlag_dynamic/manh_controllers/seeds.py`. Shares are of the maximum.", ""]
    for profile in profiles:
        mine = {s: c for (p, s), c in cells.items() if p == profile}
        n = len(mine)
        count = lambda key: sum(c["verdict"][key] for c in mine.values())
        mean = lambda key: st.mean(c[key]["share"] for c in mine.values())
        lines += [f"## {profile}", "",
                  f"{n} seeds. Feedback floor met: {count('feedback')}. Tier 1: {count('tier1')}. "
                  f"Tier 2: {count('tier2')}.", "",
                  "Mean share: " + ", ".join(f"{LABELS.get(k, k)} {mean(k):.0%}" for k in COLUMNS), ""]
        for tier, gap in (("tier2", "gap2"), ("tier1", "gap1")):
            picked = sorted((s for s, c in mine.items() if c["verdict"][tier]),
                            key=lambda s: (-mine[s]["verdict"][gap], s))[:top]
            lines += [f"### {'Tier 2' if tier == 'tier2' else 'Tier 1'}: top {len(picked)} by gap", ""]
            lines += [HEADER] + [_row(s, mine[s], gap) for s in picked] if picked else ["None."]
            lines.append("")
    if len(profiles) > 1:
        lines += ["## Passing on every profile", ""]
        for tier in ("tier2", "tier1"):
            both = [s for s in seeds if all(cells[(p, s)]["verdict"][tier] for p in profiles)]
            lines.append(f"- {'Tier 2' if tier == 'tier2' else 'Tier 1'}: {', '.join(map(str, both)) or 'none'}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    from .swarm import parse_seeds
    ap = argparse.ArgumentParser(prog="python3 -m lightlag_dynamic.manh_controllers.seeds",
                                 description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="1000-1499")
    ap.add_argument("--profiles", nargs="+", default=["rush", "rush_noisy"])
    ap.add_argument("--delay", type=int, default=3)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", help="directory for cells.jsonl and report.md (default ~/lightlag-manh-results/seeds)")
    args = ap.parse_args(argv)
    seeds = parse_seeds(args.seeds)
    cells = score(seeds, args.profiles, args.delay, args.workers)
    text = report(cells, args.profiles, args.delay, args.top)
    out = Path(args.out or Path.home() / "lightlag-manh-results" / "seeds")
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "cells.jsonl", "w", encoding="utf-8") as stream:
        for (profile, seed), cell in sorted(cells.items()):
            stream.write(json.dumps({"profile": profile, "seed": seed, **cell}, sort_keys=True) + "\n")
    (out / "report.md").write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\nwritten: {out / 'report.md'}", file=sys.stderr)


if __name__ == "__main__":
    main()
