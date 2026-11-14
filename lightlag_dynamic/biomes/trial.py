"""Early test: which controller does best in each biome.

From the repository root (needs numpy, like the Manh controllers it plays):

  python3 -m lightlag_dynamic.biomes.trial --seeds 2000-2039                    # every biome
  python3 -m lightlag_dynamic.biomes.trial --biomes troy_crust --controllers 1 24 27 team --seeds 0-19
  python3 -m lightlag_dynamic.biomes.trial --set troy_crust.soft_rate=0.2 --biomes troy_crust
  python3 -m lightlag_dynamic.biomes.trial --report ~/lightlag-manh-results/biomes   # rebuild the report

Plays registered controllers (lightlag_dynamic/manh_controllers: Manh controllers, bounds and
the team's references and baselines, all unchanged) in every chosen biome, profile, delay and
seed. Writes <out>/rows.jsonl (one summary per episode), <out>/report.md and
<out>/summary.json. The default <out> is ~/lightlag-manh-results/biomes, outside the
repository: do not commit result rows.

--controllers takes names, numbers (24) or a kind (manh, bound, team); default: every Manh
and team controller plus bound 16. Scripted controllers only: no model is run.
"""

import argparse
import collections
import json
import os
import statistics as st
import time
from multiprocessing import Pool
from pathlib import Path

from .catalog import BIOME_IDS, CATALOG, MAIN, parse_biome

DELAYS = (0, 3, 5)
PROFILES = ("rush", "rush_noisy")
ORACLE = "Oracle_exact_tight_MPC_manh_controller_16"
FROZEN = "EKF_MPC_manh_controller_1"   # the repository's kf_mpc, the frozen Harbor reference
BASELINES = ("blind", "cautious")      # a fixed plan, and one leg at a time with a wait


def run_one(job):
    """Play one episode; returns its summary row."""
    from lightlag_dynamic.manh_controllers import controllers as zoo
    from lightlag_dynamic.manh_controllers.superlog import SuperLogger, summarize
    from lightlag_dynamic.tools import PublicTools

    from .environment import make_biome_env
    name, biome, profile, delay, seed, settings = job
    spec = zoo.REGISTRY[name]
    play_delay = spec["force_delay"] if spec["force_delay"] is not None else delay
    env = make_biome_env(biome, seed, play_delay, profile, settings=settings or None, **spec["env_kwargs"])
    tools = PublicTools(env)
    log = SuperLogger(env, keep_decisions=False) if spec["logged"] else None
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
    replay = env.scenario_replay()
    row = summarize(replay, log, crash)
    info = replay.get("biome") or {}
    row.update(controller=name, kind=spec["kind"], biome=biome, profile=profile, delay=delay, seed=seed,
               seconds=round(time.time() - t0, 3), wheel_wear=info.get("wheel_wear", 0),
               drives_limited=info.get("drives_limited", 0),
               slip_trips=replay["scenario"].get("slip_trips", 0), calls=tools.calls)
    return row


def default_controllers():
    from lightlag_dynamic.manh_controllers import controllers as zoo
    return [n for n, s in zoo.REGISTRY.items() if s["kind"] in ("manh", "team") or n == ORACLE]


def parse_settings(items):
    """['troy_crust.soft_rate=0.2', ...] -> {'troy_crust': {'soft_rate': 0.2}}"""
    out = {}
    for item in items or []:
        key, _, value = item.partition("=")
        biome, _, name = key.partition(".")
        if not (biome and name and value):
            raise SystemExit(f"--set expects biome.name=value, got {item!r}")
        out.setdefault(biome, {})[name] = json.loads(value)
    return out


def run_trial(biomes, profiles, delays, seeds, names, workers, out, settings=None, quiet=False):
    from lightlag_dynamic.manh_controllers import controllers as zoo
    settings = settings or {}
    jobs, seen = [], set()
    for biome in biomes:
        own = {k: v for k, v in settings.items() if k in parse_biome(biome)}
        for profile in profiles:
            for name in names:
                spec = zoo.REGISTRY[name]
                for delay in delays:
                    for seed in seeds:
                        if spec["force_delay"] is not None:  # played once, counted at every delay
                            key = (name, biome, profile, seed)
                            if key in seen:
                                continue
                            seen.add(key)
                        jobs.append((name, biome, profile, delay, seed, own))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not quiet:
        print(f"biome trial: {len(jobs)} episodes on {workers} workers -> {out}", flush=True)
    t0, rows = time.time(), []
    if workers > 1:
        with Pool(workers) as pool:
            for i, row in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
                rows.append(row)
                if not quiet and (i + 1) % 1000 == 0:
                    print(f"  {i + 1}/{len(jobs)} in {time.time() - t0:.0f}s", flush=True)
    else:
        rows = [run_one(job) for job in jobs]
    rows += [dict(row, delay=d) for row in list(rows)
             if zoo.REGISTRY[row["controller"]]["force_delay"] is not None for d in delays if d != row["delay"]]
    rows.sort(key=lambda r: (BIOME_IDS.index(r["biome"]) if r["biome"] in BIOME_IDS else 99, r["biome"],
                             r["profile"], r["controller"], r["delay"], r["seed"]))
    with open(out / "rows.jsonl", "w") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=float) + "\n")
    meta = {"biomes": list(biomes), "profiles": list(profiles), "delays": list(delays),
            "seeds": [min(seeds), max(seeds), len(seeds)], "settings_overrides": settings}
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    if not quiet:
        print(f"done in {time.time() - t0:.0f}s", flush=True)
    return rows


# ---- report -----------------------------------------------------------------------------------
def load(out):
    with open(Path(out) / "rows.jsonl") as fh:
        return [json.loads(line) for line in fh]


def label(name):
    """'24' for a Manh controller or bound, the plain name for a team controller."""
    head, sep, tail = name.rpartition("_manh_controller_")
    return tail if sep else name


def _mean(rows):
    return st.mean(r["share"] for r in rows) if rows else None


def _home(rows):
    return sum(r["alive"] and r["at_base"] for r in rows) / len(rows) if rows else None


def _pct(x, digits=1):
    return "-" if x is None else f"{100 * x:.{digits}f}%"


def summarise(rows):
    """Per biome: every controller's mean share and home rate, and the best real controller.

    A biome's score for a controller is the mean over its profiles, delays and seeds. "Overall"
    weighs every biome equally. Bounds use privileged information and are never ranked.
    """
    kinds = {r["controller"]: r["kind"] for r in rows}
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["biome"], r["controller"])].append(r)
    biomes = [b for b in dict.fromkeys(r["biome"] for r in rows)]
    names = list(dict.fromkeys(r["controller"] for r in rows))
    real = [n for n in names if kinds[n] != "bound"]
    table = {}
    for biome in biomes:
        scores = {n: {"share": _mean(by[(biome, n)]), "home": _home(by[(biome, n)]),
                      "dead": sum(not r["alive"] for r in by[(biome, n)]) / len(by[(biome, n)]),
                      "episodes": len(by[(biome, n)])}
                  for n in names if by[(biome, n)]}
        ranked = sorted((n for n in real if n in scores), key=lambda n: -scores[n]["share"])
        table[biome] = {"scores": scores, "ranked": ranked, "best": ranked[0] if ranked else None}
    complete = [n for n in real if all(n in table[b]["scores"] for b in biomes)]
    overall = {n: st.mean(table[b]["scores"][n]["share"] for b in biomes) for n in complete}
    others = [b for b in biomes if b != MAIN]
    new_only = {n: st.mean(table[b]["scores"][n]["share"] for b in others) for n in complete} if others else {}
    return {"biomes": biomes, "controllers": names, "kinds": kinds, "table": table,
            "overall": dict(sorted(overall.items(), key=lambda kv: -kv[1])),
            "new_biomes_only": dict(sorted(new_only.items(), key=lambda kv: -kv[1]))}


def report(out):
    """Best controller per biome, the overall ranking, and a table per biome. Writes report.md."""
    from lightlag_dynamic.manh_controllers import controllers as zoo
    out = Path(out)
    rows = load(out)
    meta = json.loads((out / "meta.json").read_text()) if (out / "meta.json").exists() else {}
    s = summarise(rows)
    table, kinds = s["table"], s["kinds"]

    def title(biome):
        return " + ".join(CATALOG[b]["name"] for b in parse_biome(biome))

    def what(name):
        if kinds.get(name) == "team":
            return f"`{name}`"
        note = (zoo.REGISTRY.get(name) or {}).get("note", "")
        return f"{label(name)} ({note if len(note) <= 72 else note[:70].rstrip() + '…'})"

    seeds = meta.get("seeds")
    lines = ["# Biome trial", "",
             f"{len(rows)} episode rows; profiles {', '.join(meta.get('profiles', []))}; delays "
             f"{', '.join(map(str, meta.get('delays', [])))}"
             + (f"; seeds {seeds[0]}-{seeds[1]} ({seeds[2]})." if seeds else "."),
             "Share = score / maximum available. Home = alive at base at the horizon. Scripted "
             "controllers only; bounds use privileged information and are not ranked.", ""]
    if meta.get("settings_overrides"):
        lines += [f"Settings overridden for this run: `{json.dumps(meta['settings_overrides'])}`", ""]
    lines += ["## Best controller in each biome", "",
              "| Biome | Best controller | Share | Home | `kf_mpc` (1) | 24 | `blind` | `cautious` | Bound 16 |",
              "|---|---|---|---|---|---|---|---|---|"]
    c24 = next((n for n in s["controllers"] if label(n) == "24"), None)
    for biome in s["biomes"]:
        t = table[biome]
        sc = t["scores"]

        def cell(name):
            return _pct(sc[name]["share"]) if name in sc else "-"
        best = t["best"]
        lines.append(f"| {title(biome)} | {what(best)} | {_pct(sc[best]['share'])} | {_pct(sc[best]['home'], 0)} "
                     f"| {cell(FROZEN)} | {cell(c24)} | {cell('blind')} | {cell('cautious')} | {cell(ORACLE)} |")
    lines += ["", "## Overall: mean share with every biome weighted equally", "",
              "| Rank | Controller | All biomes | New biomes only | " + " | ".join(title(b) for b in s["biomes"]) + " |",
              "|---|---|---|---|" + "---|" * len(s["biomes"])]
    for rank, (name, mean) in enumerate(s["overall"].items(), 1):
        lines.append(f"| {rank} | {what(name)} | {_pct(mean)} | {_pct(s['new_biomes_only'].get(name))} | "
                     + " | ".join(_pct(table[b]["scores"][name]["share"]) for b in s["biomes"]) + " |")
    cells = collections.defaultdict(list)
    for r in rows:
        cells[(r["biome"], r["profile"], r["delay"], r["controller"])].append(r)
    delays = sorted({r["delay"] for r in rows})
    profiles = list(dict.fromkeys(r["profile"] for r in rows))
    lines += ["", "## By biome and profile: share of maximum (home and alive out of N)", ""]
    for biome in s["biomes"]:
        for profile in profiles:
            lines += [f"### {title(biome)} / {profile}", "",
                      "| Controller | " + " | ".join(f"Delay {d}" for d in delays) + " |",
                      "|---|" + "---|" * len(delays)]
            order = table[biome]["ranked"] + [n for n in s["controllers"] if kinds[n] == "bound"]
            for name in order:
                cs = []
                for d in delays:
                    g = cells.get((biome, profile, d, name))
                    cs.append(f"{_pct(_mean(g), 0)} ({sum(r['alive'] and r['at_base'] for r in g)}/{len(g)})" if g else "-")
                if any(c != "-" for c in cs):
                    lines.append(f"| {what(name)} | " + " | ".join(cs) + " |")
            lines.append("")
    text = "\n".join(lines) + "\n"
    (out / "report.md").write_text(text)
    compact = {"meta": meta, "overall": s["overall"], "new_biomes_only": s["new_biomes_only"],
               "best": {b: {"controller": table[b]["best"], **table[b]["scores"][table[b]["best"]]} for b in s["biomes"]},
               "scores": {b: table[b]["scores"] for b in s["biomes"]}}
    (out / "summary.json").write_text(json.dumps(compact, indent=2) + "\n")
    return text


def main(argv=None):
    from lightlag_dynamic.manh_controllers.swarm import parse_seeds, resolve
    ap = argparse.ArgumentParser(prog="python3 -m lightlag_dynamic.biomes.trial", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--biomes", nargs="*", default=list(BIOME_IDS), help="biome ids; mix with +")
    ap.add_argument("--profiles", nargs="*", default=list(PROFILES))
    ap.add_argument("--delays", nargs="*", type=int, default=list(DELAYS))
    ap.add_argument("--seeds", default="2000-2039")
    ap.add_argument("--controllers", nargs="*", help="names, numbers or kinds (manh, bound, team)")
    ap.add_argument("--set", action="append", metavar="BIOME.NAME=VALUE", help="override a biome setting")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--out", help="results directory (default ~/lightlag-manh-results/biomes)")
    ap.add_argument("--report", help="rebuild the report of an existing results directory")
    a = ap.parse_args(argv)
    if a.report:
        print(report(Path(a.report).expanduser()))
        return
    for biome in a.biomes:
        parse_biome(biome)
    names = resolve(a.controllers) if a.controllers else default_controllers()
    out = Path(a.out).expanduser() if a.out else Path.home() / "lightlag-manh-results" / "biomes"
    run_trial(a.biomes, a.profiles, a.delays, parse_seeds(a.seeds), names, a.workers, out, parse_settings(a.set))
    print(report(out)[:6000])


if __name__ == "__main__":
    main()
