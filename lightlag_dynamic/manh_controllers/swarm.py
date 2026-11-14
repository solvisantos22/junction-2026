"""Swarm testing: Manh controllers (and bounds and team references) x scenarios x delays x seeds.

From the repository root (needs numpy):

  python3 -m lightlag_dynamic.manh_controllers --list
  python3 -m lightlag_dynamic.manh_controllers --suite base  --seeds 0-19
  python3 -m lightlag_dynamic.manh_controllers --suite noise --seeds 0-19 --controllers 1 2 19
  python3 -m lightlag_dynamic.manh_controllers --suite partb --controllers manh --append
  python3 -m lightlag_dynamic.manh_controllers --report ~/lightlag-manh-results/noise   # rebuild the report only

--controllers takes names, numbers (19), or a kind (manh, bound, team); default all.
Writes <out>/rows.jsonl (one summary per episode, with failure labels), <out>/decisions.jsonl
(per-decision logs for seeds below --decision-seeds) and <out>/report.md. The default <out> is
~/lightlag-manh-results/<suite>, outside the repository: do not commit results rows.
"""

import argparse
import collections
import json
import os
import statistics as st
import time
from multiprocessing import Pool
from pathlib import Path

from .scenarios import DEFAULT_SENSING, make_env

DELAYS = (0, 3, 5)
ORACLE = "Oracle_exact_tight_MPC_manh_controller_16"
REFERENCE = "EKF_MPC_manh_controller_1"
TEAM = ("solvi_reference", "kristjan_reference", "blind")


def _sensing(**over):
    s = dict(DEFAULT_SENSING)
    s.update(over)
    return s


def suite_base():
    """The four main profiles as published."""
    return [{"name": "default", "profile": p} for p in ("static", "noisy", "rush", "rush_noisy")]


def suite_noise():
    """One sensing dial at a time, plus every dial scaled together (level)."""
    out = [{"name": "default", "group": "default", "sensing": _sensing()}]
    dials = {
        "pos": ("position_noise_m", (0.1, 0.6, 1.0)),
        "bias": ("heading_bias_deg", (0.0, 10.0, 20.0)),
        "walk": ("heading_bias_walk_deg", (0.0, 1.5, 3.0)),
        "head": ("heading_noise_deg", (0.0, 3.0, 6.0)),
        "vo": ("visual_odometry_noise", (0.01, 0.15, 0.3)),
    }
    for group, (key, values) in dials.items():
        for v in values:
            out.append({"name": f"{group}={v:g}", "group": group, "sensing": _sensing(**{key: v})})
    for level in (0.5, 2.0, 3.0):
        out.append({"name": f"level={level:g}", "group": "level",
                    "sensing": {k: v * level for k, v in DEFAULT_SENSING.items()}})
    return [dict(s, profile=p) for s in out for p in ("noisy", "rush_noisy")]


def suite_partb():
    """One candidate rule factor at a time."""
    out = [{"name": "default", "factors": {}},
           {"name": "drive_2m_per_tick", "factors": {"max_metres": 2.0}},
           {"name": "drive_1m_per_tick", "factors": {"max_metres": 1.0}},
           {"name": "vo_by_terrain", "factors": {"vo_by_terrain": {"bedrock": 0.03, "sand": 0.2}}},
           {"name": "windows_10_3", "factors": {"windows": (10, 3)}},
           {"name": "windows_16_4", "factors": {"windows": (16, 4)}},
           {"name": "hidden_sand_1", "factors": {"hidden_patches": 1}},
           {"name": "hidden_sand_2", "factors": {"hidden_patches": 2}},
           {"name": "slip_jump", "factors": {"slip_change": "auto"}},
           {"name": "turn_cost_0.01", "factors": {"turn_cost": 0.01}},
           {"name": "turn_cost_0.03", "factors": {"turn_cost": 0.03}}]
    return [dict(s, profile=p) for s in out for p in ("noisy", "rush_noisy")]


def suite_faults():
    """Things that go wrong on the link and the localiser: lost telemetry packets, outlier fixes."""
    out = [{"name": "default", "factors": {}},
           {"name": "packet_loss_10", "factors": {"packet_loss": {"p": 0.10}}},
           {"name": "packet_loss_25", "factors": {"packet_loss": {"p": 0.25}}},
           {"name": "packet_loss_50", "factors": {"packet_loss": {"p": 0.50}}},
           {"name": "outliers_5", "factors": {"fix_outliers": {"p": 0.05, "sigma": 3.0}}},
           {"name": "outliers_15", "factors": {"fix_outliers": {"p": 0.15, "sigma": 3.0}}},
           {"name": "loss_25_outliers_5", "factors": {"packet_loss": {"p": 0.25},
                                                      "fix_outliers": {"p": 0.05, "sigma": 3.0}}}]
    return [dict(s, profile=p) for s in out for p in ("rush", "rush_noisy")]


SUITES = {"base": suite_base, "noise": suite_noise, "partb": suite_partb, "faults": suite_faults}


def _factors(scn, horizon):
    f = dict(scn.get("factors") or {})
    if f.get("slip_change") == "auto":
        f["slip_change"] = {"tick": int(horizon * 0.35), "delta": {"sand": 0.2, "bedrock": 0.1}}
    return f


def run_one(job):
    """Play one episode; returns (summary row, per-decision log or None)."""
    from lightlag_dynamic.missions import PROFILES
    from lightlag_dynamic.tools import PublicTools

    from . import controllers as zoo
    from .superlog import SuperLogger, summarize
    name, scn, delay, seed, keep = job
    spec = zoo.REGISTRY[name]
    play_delay = spec["force_delay"] if spec["force_delay"] is not None else delay
    horizon = PROFILES[scn["profile"]][4]
    env = make_env(seed, play_delay, scn["profile"], sensing=scn.get("sensing"),
                   factors=_factors(scn, horizon), **spec["env_kwargs"])
    tools = PublicTools(env)
    log = SuperLogger(env, keep_decisions=keep) if spec["logged"] else None
    zoo.Current.logger = log
    crash = None
    t0 = time.time()
    try:
        spec["play"](tools, env)
    except Exception as exc:  # a controller error is a result, not a harness failure
        crash = f"{type(exc).__name__}: {exc}"[:200]
    finally:
        zoo.Current.logger = None
    while not env.advance(5)["episode_complete"]:
        pass
    row = summarize(env.scenario_replay(), log, crash)
    row.update(controller=name, kind=spec["kind"], scenario=scn["name"], group=scn.get("group", ""),
               profile=scn["profile"], delay=delay, seed=seed, seconds=round(time.time() - t0, 3))
    return row, (log.decisions if (log is not None and keep) else None)


def parse_seeds(text):
    out = []
    for part in text.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def resolve(items):
    """Names, numbers or kinds -> registered names, in registry order."""
    from . import controllers as zoo
    if not items:
        return list(zoo.REGISTRY)
    wanted = set()
    for item in items:
        if item in zoo.REGISTRY:
            wanted.add(item)
        elif item.isdigit():
            hits = [n for n in zoo.REGISTRY if zoo.number(n) == int(item)]
            if not hits:
                raise SystemExit(f"no controller number {item}" +
                                 (f" (retired: {zoo.RETIRED[int(item)]})" if int(item) in zoo.RETIRED else ""))
            wanted.update(hits)
        elif item in {"manh", "bound", "team"}:
            wanted.update(n for n, s in zoo.REGISTRY.items() if s["kind"] == item)
        else:
            raise SystemExit(f"unknown controller {item!r}; see --list")
    return [n for n in zoo.REGISTRY if n in wanted]


def load(out):
    return [json.loads(line) for line in open(Path(out) / "rows.jsonl")]


def run_suite(suite, seeds, names, workers, out, decision_seeds=3, append=False, quiet=False):
    from . import controllers as zoo
    jobs, seen = [], set()
    for scn in SUITES[suite]():
        for name in names:
            spec = zoo.REGISTRY[name]
            for delay in DELAYS:
                for seed in seeds:
                    if spec["force_delay"] is not None:  # played once, counted at every delay
                        key = (name, scn["name"], scn["profile"], seed)
                        if key in seen:
                            continue
                        seen.add(key)
                    jobs.append((name, scn, delay, seed, seed < decision_seeds))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not quiet:
        print(f"{suite}: {len(jobs)} episodes on {workers} workers -> {out}", flush=True)
    t0 = time.time()
    rows, decisions = [], []

    def collect(results):
        for i, (row, dec) in enumerate(results):
            rows.append(row)
            if dec:
                entry = {k: row[k] for k in ("controller", "scenario", "profile", "delay", "seed")}
                entry["decisions"] = dec
                decisions.append(entry)
            if not quiet and (i + 1) % 500 == 0:
                print(f"  {i + 1}/{len(jobs)} in {time.time() - t0:.0f}s", flush=True)

    if workers > 1:
        with Pool(workers) as pool:
            collect(pool.imap_unordered(run_one, jobs, chunksize=4))
    else:
        collect(map(run_one, jobs))
    rows += [dict(row, delay=d) for row in list(rows) if zoo.REGISTRY[row["controller"]]["force_delay"] is not None
             for d in DELAYS if d != row["delay"]]
    if append and (out / "rows.jsonl").exists():
        ran = set(names)
        rows = [r for r in load(out) if r["controller"] not in ran] + rows
        if (out / "decisions.jsonl").exists():
            old = [json.loads(line) for line in open(out / "decisions.jsonl")]
            decisions = [d for d in old if d["controller"] not in ran] + decisions
    with open(out / "rows.jsonl", "w") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=float) + "\n")
    with open(out / "decisions.jsonl", "w") as fh:
        for d in decisions:
            fh.write(json.dumps(d, default=float) + "\n")
    if not quiet:
        print(f"done in {time.time() - t0:.0f}s", flush=True)
    return rows


# ---- report ---------------------------------------------------------------------------------
def _pct(x):
    return "-" if x is None else f"{x:.0%}"


def _home(rs):
    return sum(r["alive"] and r["at_base"] for r in rs) / len(rs)


def report(out):
    """Leaderboard, per-scenario table, failure atlas, estimation quality, and where the
    reference and the best real controller fail and prevail. Writes <out>/report.md."""
    out = Path(out)
    rows = load(out)
    order = {}
    for r in rows:
        order.setdefault(r["controller"], len(order))
    names = sorted(order, key=lambda n: (n.rpartition("_manh_controller_")[2].isdigit() is False,
                                         int(n.rpartition("_")[2]) if "_manh_controller_" in n else 0, n))
    kinds = {r["controller"]: r["kind"] for r in rows}
    cells = collections.defaultdict(list)
    for r in rows:
        cells[(r["scenario"], r["profile"], r["delay"], r["controller"])].append(r)
    best_real, oracle = {}, {}
    for r in rows:
        k = (r["scenario"], r["profile"], r["delay"], r["seed"])
        if r["kind"] != "bound":
            best_real[k] = max(best_real.get(k, 0.0), r["share"])
        if r["controller"] == ORACLE:
            oracle[k] = r["share"]
    lines = [f"# Swarm report: {out.name}", "",
             f"{len(rows)} episode rows. Share = score / maximum available. Home = alive at base.",
             "Bounds use privileged information and are yardsticks, not entries.", "",
             "## Leaderboard (all cells)", "",
             "| Controller | Kind | Mean share | Home | Dead | Crash | Best real on seed | Share of bound 16 |",
             "|---|---|---|---|---|---|---|---|"]
    board = []
    for n in names:
        rs = [r for r in rows if r["controller"] == n]
        wins = sum(1 for r in rs if r["share"] >= best_real[(r["scenario"], r["profile"], r["delay"], r["seed"])] - 1e-9)
        ratio = [r["share"] / oracle[k] for r in rs
                 for k in [(r["scenario"], r["profile"], r["delay"], r["seed"])] if oracle.get(k)]
        board.append((st.mean(r["share"] for r in rs), n, rs, wins, ratio))
    board.sort(key=lambda b: -b[0])
    for mean, n, rs, wins, ratio in board:
        kind = kinds[n]
        lines.append(f"| {n} | {kind} | {mean:.1%} | {_home(rs):.0%} | {sum(not r['alive'] for r in rs) / len(rs):.0%} "
                     f"| {sum(bool(r['crash']) for r in rs) / len(rs):.0%} "
                     f"| {'-' if kind == 'bound' else format(wins / len(rs), '.0%')} "
                     f"| {_pct(st.mean(ratio)) if ratio else '-'} |")
    scen = []
    for r in rows:
        if (r["scenario"], r["profile"]) not in scen:
            scen.append((r["scenario"], r["profile"]))
    lines += ["", "## By scenario: share of maximum (home and alive out of N)", ""]
    for s, p in scen:
        lines += [f"### {s} / {p}", "", "| Controller | Delay 0 | Delay 3 | Delay 5 |", "|---|---|---|---|"]
        for n in names:
            cs = []
            for d in DELAYS:
                g = cells.get((s, p, d, n))
                cs.append(f"{st.mean(r['share'] for r in g):.0%} ({sum(r['alive'] and r['at_base'] for r in g)}/{len(g)})"
                          if g else "-")
            if any(c != "-" for c in cs):
                lines.append(f"| {n} | " + " | ".join(cs) + " |")
        lines.append("")
    labels = sorted({label for r in rows for label in r["labels"]})
    lines += ["## Failure atlas: share of episodes with each label", "",
              "| Controller | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for n in names:
        rs = [r for r in rows if r["controller"] == n]
        cnt = collections.Counter(label for r in rs for label in r["labels"])
        lines.append(f"| {n} | " + " | ".join(f"{cnt[x] / len(rs):.0%}" if cnt[x] else "" for x in labels) + " |")
    lines += ["", "## Estimation quality (logged controllers)", "",
              "| Controller | Position RMSE (m) | Predicted-at-execution error (m) | Mean NEES (2 = consistent) "
              "| Final bias error (deg) | Early sand slip error | Final sand slip error |",
              "|---|---|---|---|---|---|---|"]
    for n in names:
        rs = [r for r in rows if r["controller"] == n and r.get("pos_rmse") is not None]
        if not rs:
            continue

        def m(key, sub=None):
            vals = [(r[key][sub] if sub else r[key]) for r in rs if r.get(key) is not None]
            vals = [v for v in vals if v == v]
            return st.mean(vals) if vals else float("nan")
        lines.append(f"| {n} | {m('pos_rmse'):.2f} | {m('pred_err_mean'):.2f} | {m('nees_mean'):.2f} "
                     f"| {m('bias_err_final'):.2f} | {m('slip_err_early', 'sand'):.3f} | {m('slip_err_final', 'sand'):.3f} |")
    real = [b[1] for b in board if kinds[b[1]] == "manh"]
    focus = [n for n in dict.fromkeys(([REFERENCE] if REFERENCE in names else []) + real[:1])]
    for target in focus:
        gaps = []
        for (s, p, d, n), g in cells.items():
            if n != target:
                continue
            o = [oracle[(s, p, d, r["seed"])] for r in g if (s, p, d, r["seed"]) in oracle]
            team = [st.mean(x["share"] for x in cells[(s, p, d, t)]) for t in TEAM if cells.get((s, p, d, t))]
            share = st.mean(r["share"] for r in g)
            gaps.append((st.mean(o) - share if o else 0.0, share - (max(team) if team else 0.0), s, p, d, g))
        lines += ["", f"## Where {target} fails (largest gap to bound 16)", "",
                  "| Scenario | Profile | Delay | Share | Gap to bound | Top labels | Worst seeds |",
                  "|---|---|---|---|---|---|---|"]
        for gap, lead, s, p, d, g in sorted(gaps, key=lambda x: -x[0])[:8]:
            cnt = collections.Counter(x for r in g for x in r["labels"] if x not in ("PERFECT", "RETRIED_OK"))
            worst = sorted(g, key=lambda r: r["share"])[:3]
            lines.append(f"| {s} | {p} | {d} | {st.mean(r['share'] for r in g):.0%} | {gap:+.0%} "
                         f"| {', '.join(f'{k} {v}' for k, v in cnt.most_common(3))} "
                         f"| {', '.join(str(r['seed']) for r in worst)} |")
        lines += ["", f"## Where {target} prevails (largest lead over the best team controller)", "",
                  "| Scenario | Profile | Delay | Share | Lead over best team controller |", "|---|---|---|---|---|"]
        for gap, lead, s, p, d, g in sorted(gaps, key=lambda x: -x[1])[:8]:
            lines.append(f"| {s} | {p} | {d} | {st.mean(r['share'] for r in g):.0%} | {lead:+.0%} |")
    text = "\n".join(lines) + "\n"
    (out / "report.md").write_text(text)
    return text


def list_controllers():
    from . import controllers as zoo
    lines = ["| N | Name | Kind | What it is | Why it was built, and what it showed | Built |", "|---|---|---|---|---|---|"]
    for name, spec in zoo.REGISTRY.items():
        n = zoo.number(name)
        lines.append(f"| {'' if n is None else n} | `{name}` | {spec['kind']} | {spec['note']} | {spec['why']} | {spec['built']} |")
    lines += ["", "Retired numbers (never reused):"] + [f"- {n}: {why}" for n, why in sorted(zoo.RETIRED.items())]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m lightlag_dynamic.manh_controllers", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", choices=list(SUITES))
    ap.add_argument("--seeds", default="0-19")
    ap.add_argument("--controllers", nargs="*", help="names, numbers or kinds (manh, bound, team); default all")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--decision-seeds", type=int, default=3)
    ap.add_argument("--out", help="results directory (default ~/lightlag-manh-results/<suite>)")
    ap.add_argument("--append", action="store_true",
                    help="merge into existing results, replacing only the controllers run now")
    ap.add_argument("--report", help="rebuild the report of an existing results directory")
    ap.add_argument("--list", action="store_true", help="list the registered controllers")
    a = ap.parse_args(argv)
    if a.list:
        print(list_controllers())
        return
    if a.report:
        print(report(a.report))
        return
    if not a.suite:
        ap.error("--suite, --report or --list is required")
    out = Path(a.out).expanduser() if a.out else Path.home() / "lightlag-manh-results" / a.suite
    run_suite(a.suite, parse_seeds(a.seeds), resolve(a.controllers), a.workers, out,
              a.decision_seeds, a.append)
    print(report(out)[:4000])
