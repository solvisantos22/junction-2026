"""Search the reference pilot's options with many missions, then check the winner on unseen worlds.

Backend-agnostic: every function takes `run_many(jobs) -> rows`, which can be a local process pool
(`jobs.local_map`) or Modal (`modal_app.py`). Standard library only.

The method, fixed before any run:
  1. Cross-entropy search over the options in SPACE, in a unit cube (log scale where marked).
     Each generation plays every candidate, the published defaults and the current centre on the
     same block of worlds, so candidates are compared paired, on identical ground. Generations
     use different blocks, so no candidate is tuned to one set of worlds.
  2. Selection: the best few candidates by paired gain are replayed with the defaults on a fresh
     block, and the best of those is chosen. This guards against the winner's curse.
  3. Confirmation: the chosen options and the defaults on confirmation worlds nobody searched.
     A gain is claimed only if its 95% paired bootstrap interval excludes zero.
A candidate slower than `max_slowdown` times the defaults is disqualified: the reference has to
run in the judges' container in reasonable time.
"""

from __future__ import annotations

import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

RunMany = Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]]

# name: (scale, low, high). "log" options are searched on a log scale; "*int" are rounded.
# The ablation switches "route" and "terrain", and "stop_ticks" (the sample's own tick), stay fixed.
SPACE: Dict[str, Tuple[str, float, float]] = {
    "plan_steps": ("log_int", 150000, 600000),
    "replan_steps": ("log_int", 10000, 60000),
    "beam": ("log_int", 300, 1200),
    "rebeam": ("log_int", 60, 240),
    "slip_prior": ("float", 0.25, 1.0),
    "replan_every": ("int", 6, 24),
    "arrive_m": ("float", 0.5, 2.0),
    "floor": ("float", 2.0, 12.0),
    "home_margin": ("float", 1.0, 10.0),
    "home_slack": ("float", 1.0, 1.25),
    "deadline_margin": ("int", 0, 5),
    "leg_slack": ("float", 0.9, 1.3),
    "energy_weight": ("log", 0.05, 1.0),
    "rebuild_shift": ("log", 0.01, 0.1),
}


# ---- the unit cube ------------------------------------------------------------------------
def encode(options: Dict[str, Any], space: Dict[str, Tuple[str, float, float]] = SPACE) -> List[float]:
    point = []
    for name, (scale, low, high) in space.items():
        value = float(options[name])
        if scale.startswith("log"):
            u = (math.log(value) - math.log(low)) / (math.log(high) - math.log(low))
        else:
            u = (value - low) / (high - low)
        point.append(min(1.0, max(0.0, u)))
    return point


def decode(point: Sequence[float], space: Dict[str, Tuple[str, float, float]] = SPACE) -> Dict[str, Any]:
    options: Dict[str, Any] = {}
    for u, (name, (scale, low, high)) in zip(point, space.items()):
        u = min(1.0, max(0.0, u))
        if scale.startswith("log"):
            value = math.exp(math.log(low) + u * (math.log(high) - math.log(low)))
        else:
            value = low + u * (high - low)
        options[name] = int(round(value)) if scale.endswith("int") else round(value, 4)
    return options


def check_space(defaults: Dict[str, Any], space: Dict[str, Tuple[str, float, float]] = SPACE) -> None:
    missing = sorted(set(space) - set(defaults))
    if missing:
        raise ValueError("the pilot has no option(s) {}: update SPACE or play the Traverse version that has them".format(", ".join(missing)))
    for name, (_, low, high) in space.items():
        if not low <= float(defaults[name]) <= high:
            raise ValueError("the pilot's default {}={} lies outside the searched range".format(name, defaults[name]))


def key(options: Dict[str, Any]) -> str:
    return json.dumps(options, sort_keys=True)


def _mission_key(item: Dict[str, Any]) -> str:
    from .jobs import job_key
    return job_key(item)


# ---- statistics ---------------------------------------------------------------------------
def paired(rows: List[Dict[str, Any]], a: str, b: str) -> List[float]:
    """Per-world reward of candidate a minus candidate b, on the worlds both played."""
    by = {}
    for row in rows:
        if "reward" in row:
            by[(row["candidate"], row["seed"])] = row["reward"]
    seeds = sorted({seed for (cand, seed) in by if cand == a} & {seed for (cand, seed) in by if cand == b})
    return [by[(a, seed)] - by[(b, seed)] for seed in seeds]


def bootstrap(differences: Sequence[float], draws: int = 10000, seed: int = 0) -> Tuple[float, float]:
    rng, n = random.Random(seed), len(differences)
    means = sorted(sum(differences[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return means[int(0.025 * draws)], means[int(0.975 * draws) - 1]


def summarise(rows: List[Dict[str, Any]], candidate: str) -> Dict[str, Any]:
    mine = [row for row in rows if row.get("candidate") == candidate]
    played = [row for row in mine if "reward" in row]
    return {
        "worlds": len(played), "crashed": len(mine) - len(played),
        "mean": statistics.mean(r["reward"] for r in played) if played else None,
        "lost": sum(not r["alive"] for r in played), "away": sum(r["alive"] and not r["at_base"] for r in played),
        "seconds": statistics.mean(r["seconds"] for r in played) if played else None,
    }


# ---- bookkeeping --------------------------------------------------------------------------
class Ledger:
    """Every row on disk as it arrives, so an interrupted search resumes without replaying worlds."""

    def __init__(self, folder: Optional[Path]):
        self.folder, self.rows, self.done = folder, [], {}
        if folder:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / "rows.jsonl"
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        row = json.loads(line)
                        self.rows.append(row)
                        if "reward" in row:
                            self.done[_mission_key(row)] = row

    def play(self, run_many: RunMany, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        todo, queued = [], set()
        for job in jobs:   # each mission is played once, however many candidates share it
            k = _mission_key(job)
            if k not in self.done and k not in queued:
                queued.add(k)
                todo.append(job)
        fresh = run_many(todo) if todo else []
        if self.folder and fresh:
            with (self.folder / "rows.jsonl").open("a", encoding="utf-8") as stream:
                for row in fresh:
                    stream.write(json.dumps(row, sort_keys=True) + "\n")
        for row in fresh:
            self.rows.append(row)
            if "reward" in row:
                self.done[_mission_key(row)] = row
        out = []
        for job in jobs:   # relabel cached rows with this job's candidate/generation tags
            cached = self.done.get(_mission_key(job))
            if cached is not None:
                out.append(dict(cached, **{k: job[k] for k in ("candidate", "generation", "block") if k in job}))
            else:   # a crashed job: report its crash under this job's tags
                crash = next((r for r in fresh if _mission_key(r) == _mission_key(job)), None)
                if crash is not None:
                    out.append(dict(crash, **{k: job[k] for k in ("candidate", "generation", "block") if k in job}))
        return out

    def write(self, name: str, payload: Any) -> None:
        if self.folder:
            (self.folder / name).write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _jobs(candidates: Dict[str, Dict[str, Any]], seeds: Iterable[int], tags: Dict[str, Any]) -> List[Dict[str, Any]]:
    seeds = list(seeds)
    return [dict(tags, policy="pilot", options=options, candidate=name, seed=seed)
            for name, options in candidates.items() for seed in seeds]


def _gain(rows: List[Dict[str, Any]], name: str, defaults_name: str, seconds_cap: Optional[float]) -> float:
    diffs = paired(rows, name, defaults_name)
    stats = summarise(rows, name)
    if not diffs or stats["crashed"]:
        return -math.inf
    if seconds_cap is not None and stats["seconds"] is not None and stats["seconds"] > seconds_cap:
        return -math.inf
    return statistics.mean(diffs)


# ---- the search ---------------------------------------------------------------------------
def search(run_many: RunMany, defaults: Dict[str, Any], *, search_seeds: Sequence[int], select_seeds: Sequence[int],
           confirm_seeds: Sequence[int], generations: int = 6, population: int = 24, block: int = 40, elites: int = 6,
           finalists: int = 3, smoothing: float = 0.7, sigma0: float = 0.25, sigma_min: float = 0.05,
           max_slowdown: float = 2.0, rng_seed: int = 2026, out: Optional[Path] = None,
           log: Callable[[str], None] = print) -> Dict[str, Any]:
    check_space(defaults)
    if len(search_seeds) < generations * block:
        raise ValueError("need {} search worlds, got {}".format(generations * block, len(search_seeds)))
    ledger, rng = Ledger(out), random.Random(rng_seed)
    base = {name: defaults[name] for name in SPACE}
    mean, sigma = encode(base), [sigma0] * len(SPACE)
    history, tried = [], {}
    ledger.write("plan.json", {"space": SPACE, "defaults": base, "generations": generations, "population": population,
                               "block": block, "elites": elites, "finalists": finalists, "max_slowdown": max_slowdown,
                               "search_seeds": [search_seeds[0], search_seeds[-1]], "select_seeds": list(select_seeds),
                               "confirm_seeds": [confirm_seeds[0], confirm_seeds[-1]], "rng_seed": rng_seed})
    for g in range(generations):
        seeds = search_seeds[g * block:(g + 1) * block]
        candidates = {"defaults": base}
        if key(decode(mean)) != key(base):
            candidates["g{}-centre".format(g)] = decode(mean)
        for i in range(population):
            point = [min(1.0, max(0.0, rng.gauss(m, s))) for m, s in zip(mean, sigma)]
            candidates["g{}-c{}".format(g, i)] = decode(point)
        rows = ledger.play(run_many, _jobs(candidates, seeds, {"generation": g}))
        default_seconds = summarise(rows, "defaults")["seconds"]
        cap = max_slowdown * default_seconds if default_seconds else None
        gains = {name: _gain(rows, name, "defaults", cap) for name in candidates if name != "defaults"}
        ranked = sorted(gains, key=gains.get, reverse=True)
        for name in ranked:
            tried[name] = {"options": candidates[name], "gain": gains[name], "generation": g, **summarise(rows, name)}
        top = [encode(candidates[name]) for name in ranked[:elites] if gains[name] > -math.inf]
        if top:
            centre = [statistics.mean(column) for column in zip(*top)]
            spread = [statistics.pstdev(column) for column in zip(*top)]
            mean = [(1 - smoothing) * m + smoothing * c for m, c in zip(mean, centre)]
            sigma = [max(sigma_min, (1 - smoothing) * s + smoothing * d) for s, d in zip(sigma, spread)]
        record = {"generation": g, "seeds": [seeds[0], seeds[-1]], "defaults": summarise(rows, "defaults"),
                  "best": ranked[0], "best_gain": gains[ranked[0]], "best_options": candidates[ranked[0]],
                  "mean_sigma": statistics.mean(sigma)}
        history.append(record)
        ledger.write("history.json", history)
        log("generation {}: defaults {:.3f}, best {} {:+.3f}, sigma {:.3f}".format(
            g, record["defaults"]["mean"], ranked[0], gains[ranked[0]], record["mean_sigma"]))

    # selection on a fresh block, against the winner's curse
    pool = sorted((n for n in tried if tried[n]["gain"] > -math.inf), key=lambda n: tried[n]["gain"], reverse=True)
    picks = {"defaults": base, **{name: tried[name]["options"] for name in pool[:finalists]}}
    rows = ledger.play(run_many, _jobs(picks, select_seeds, {"block": "select"}))
    default_seconds = summarise(rows, "defaults")["seconds"]
    cap = max_slowdown * default_seconds if default_seconds else None
    selection = {name: {"gain": _gain(rows, name, "defaults", cap), **summarise(rows, name)} for name in picks}
    chosen = max((n for n in picks if n != "defaults"), key=lambda n: selection[n]["gain"], default=None)
    ledger.write("selection.json", {"picks": picks, "results": selection, "chosen": chosen})
    log("selection: " + ", ".join("{} {:+.3f}".format(n, selection[n]["gain"]) for n in picks if n != "defaults"))

    confirmation: Dict[str, Any] = {"chosen": chosen}
    if chosen is not None and selection[chosen]["gain"] > 0:
        final = {"defaults": base, "chosen": picks[chosen]}
        rows = ledger.play(run_many, _jobs(final, confirm_seeds, {"block": "confirm"}))
        diffs = paired(rows, "chosen", "defaults")
        low, high = bootstrap(diffs)
        confirmation.update({
            "options": picks[chosen], "defaults": summarise(rows, "defaults"), "candidate": summarise(rows, "chosen"),
            "gain": statistics.mean(diffs), "interval_95": [low, high], "worlds": len(diffs),
            "higher": sum(d > 1e-9 for d in diffs), "equal": sum(abs(d) <= 1e-9 for d in diffs),
            "lower": sum(d < -1e-9 for d in diffs), "confirmed": low > 0,
        })
        log("confirmation on {} worlds: {:+.3f} (95% {:+.3f} to {:+.3f}){}".format(
            len(diffs), confirmation["gain"], low, high, ", confirmed" if low > 0 else ", NOT confirmed"))
    else:
        confirmation["confirmed"] = False
        log("selection found nothing better than the defaults; confirmation skipped")
    ledger.write("confirmation.json", confirmation)
    return {"history": history, "selection": selection, "confirmation": confirmation}


def evaluate(run_many: RunMany, policies: Dict[str, Dict[str, Any]], seeds: Sequence[int],
             out: Optional[Path] = None) -> Dict[str, Any]:
    """Several policies on the same worlds. `policies`: name -> job fields (policy, options, program...)."""
    ledger = Ledger(out)
    jobs = [dict(spec, candidate=name, seed=seed) for name, spec in policies.items() for seed in seeds]
    rows = run_many(jobs) if out is None else ledger.play(run_many, jobs)
    table = {name: summarise(rows, name) for name in policies}
    ledger.write("evaluation.json", {"seeds": [seeds[0], seeds[-1]], "worlds": len(seeds), "table": table})
    return {"rows": rows, "table": table}
