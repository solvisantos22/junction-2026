#!/usr/bin/env python3
"""One request per program on the MAX map: a frozen baseline of Claude models on superhard and fair MAX worlds.

    python3 -m lightlag_traverse_max.oneshot request <out.md>              # the exact text a model is sent
    python3 -m lightlag_traverse_max.oneshot freeze --scripted <play.json> # write the frozen protocol
    python3 -m lightlag_traverse_max.oneshot ask --budget-usd 15 --env-file <.env>   # PAID
    python3 -m lightlag_traverse_max.oneshot play                          # free: every program, every world
    python3 -m lightlag_traverse_max.oneshot report                        # the tables, into the README

The method is Kristján's one-request test (lightlag_traverse/oneshot.py): a model gets the task's
instruction, the published rules, the tool outputs of one example world (99991, never evaluated)
and the published ground model, and writes one program that plays a whole mission on its own.
Here the rules, the map and the example come from the MAX map, and one added section says what
the MAX map changes. Sending is lightlag_live.oneshot.ask, unchanged: adaptive thinking, the frozen
effort and token limit, no retries and no fallback model, so every reply comes from the model
named. A reply counts as it came; one without a program scores 0 on every world. A call that
brought no reply (an API error) may be sent again. Playing is lightlag_traverse_max.sandbox.

Everything frozen sits in docs/lightlag-runs/max-baseline/: freeze.json (the worlds and the rule
that chose them, models, effort, token limit, samples, the request's sha256 and the sha256 of the
files that make the mission), request.md, scripted.json (the four scripted players on the same
worlds), replies/<model>-<k>/, asks.jsonl and plays.json. Standard library only, except `ask`,
which needs the `anthropic` package and ANTHROPIC_API_KEY (read from --env-file, never printed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from lightlag_traverse import oneshot as kristjans

from . import heldout
from .environment import MAX_SETTINGS, make_env

REPO = Path(__file__).resolve().parent.parent
BASELINE = REPO / "docs" / "lightlag-runs" / "max-baseline"
NAME = "MAX-map model baseline"

# The protocol. Once a request has been sent, changing any of it means a new baseline under a new name.
HARD_WORLDS = heldout.SUPERHARD_WORLDS        # (505, 509, 515)
FAIR_WORLDS = heldout.FAIR_WORLDS             # (500, 510, 520)
TASK_WORLD = 2026
WORLDS = HARD_WORLDS + FAIR_WORLDS + (TASK_WORLD,)
RULES = {
    "pool": ("The 24 worlds 500-523 (Manh's claimed range), each played once on both maps by all four scripted "
             "players at full budgets and never used for tuning. Manh picked both groups from them by manh_max's "
             "score on the MAX map, after the first freeze and before any request was sent."),
    "superhard": ("manh_max scores 0.199, 0.180 and 0.094 on the MAX map (the hardest of the 24 "
                  "is 515; 509 is the only one of the 8 hardest where it still gets home). All 8 worlds under 0.2 "
                  "were 503 504 505 509 515 516 517 518; the 9th hardest scored 0.291."),
    "fair": ("manh_max scores 0.455, 0.481 and 0.529 on the MAX map and gets home, keeping 82%, "
             "99% and 99% of its normal-map score; the three highest MAX scores of the 24."),
    "task_world": "the task's world, as an anchor next to Kristján's normal-map baseline; in neither group.",
}
MODELS = (("haiku", "claude-haiku-5-5"), ("sonnet", "claude-sonnet-5-5"), ("opus", "claude-opus-5-5"))
EFFORT = "medium"
MAX_TOKENS = 128000
SAMPLES = 3
PLAYERS = ("manh_max", "pilot", "greedy", "straight")
# Kristján's one-request programs, written for the normal map, played here unchanged on the MAX map.
TRANSFER = (("normal-opus-1", "traverse-oneshot-opus-1"), ("normal-sonnet-1", "traverse-oneshot-sonnet-1"),
            ("normal-haiku-1", "traverse-oneshot-haiku-1"))
# The files that make the mission: the world, the physics, the MAX map, the tools inside the sandbox, grading.
MISSION_FILES = ("lightlag_traverse_max/environment.py", "lightlag_traverse/environment.py",
                 "lightlag_traverse/surface.py", "lightlag_traverse/terrain.py", "lightlag_traverse/planning.py",
                 "lightlag_traverse/sandbox_worker.py", "lightlag_mcp/service.py")
KEY = "ANTHROPIC_API_KEY"


def _once(text: str, marker: str, insert: str) -> str:
    if text.count(marker) != 1:
        raise RuntimeError("expected {!r} once in Kristján's request".format(marker))
    return text.replace(marker, insert + marker)


def max_section() -> str:
    s = MAX_SETTINGS
    relay, crust = s["relay_passes"], s["crust"]
    noise = s["visual_odometry_noise_by_terrain"]
    return """\
## This is the MAX map

The mission is played on the MAX map: the same kind of world, targets, deadlines, sun and drive limit as above, with harder operations. `rules()["max_option"]` names the changes, and each has its own entry in `rules()` with the exact rule. Where they differ from what is said above, they hold. In short:

- **The link is open only during relay passes** (`relay_passes`): {open} ticks of every {period}, while `tick % {period} < {open}`. An uplink sent while the link is closed goes up when the next pass opens; its acknowledgement gives `transmit_tick` and `execute_tick`. A packet that would arrive while the link is closed arrives when the next pass opens, so telemetry comes in bursts.
- **Packets are lost** (`telemetry_packet_loss`): each telemetry packet is lost with probability {loss}.
- **Position fixes are worse** (`sensing`, `position_fix_outliers`): {fix} m of noise per axis, and {wild:.0%} of fixes are off by a further {wild_m} m per axis.
- **The rover stops itself when its wheels slip too much** (`onboard_slip_check`): a drive step that slips more than {slip} is the last of its drive and every queued command is discarded; telemetry reports a `safety_stop` with reason `slip_limit`.
- **Some ground is softer than the map says** (`crust`): `map()` lists `crust_regions`. Inside them the ground is mapped as bedrock, but each cell there whose steepest slope is at most {soft_slope} is soft sand underneath with probability {soft_rate}, not listed.
- **Dune slopes are hidden** (`sand_grade_gain`): how fast slip on sand grows with the slope is hidden in [{gain_low}, {gain_high}]; `physics` publishes 3.5.
- **The wheels' size is hidden** (`wheel_scale_error`): a drive of M metres turns the wheels M x scale, with scale hidden within 1 +- {wheel}, and wheel odometry still reads M for a drive that runs to the end.
- **Turning costs energy** (`turn_cost`): {turn} x the degrees turned x the drive cost per metre of the terrain underneath, paid before the drive.
- **Visual odometry noise depends on the terrain** (`visual_odometry_by_terrain`): from {vo_low} on bedrock to {vo_high} on sand.

""".format(open=relay["open_ticks"], period=relay["period_ticks"], loss=s["packet_loss"],
           fix=s["position_noise_m"], wild=s["fix_outliers"]["probability"], wild_m=s["fix_outliers"]["sigma_m"],
           slip=s["slip_check_limit"], soft_slope=crust["max_soft_slope"], soft_rate=crust["soft_rate"],
           gain_low=s["sand_grade_gain_range"][0], gain_high=s["sand_grade_gain_range"][1],
           wheel=s["wheel_scale_error"], turn=s["turn_cost_per_degree"], vo_low=noise["bedrock"], vo_high=noise["sand"])


def build_request() -> str:
    """Kristján's request text, filled from the MAX map's example world, with the MAX section added."""
    env = make_env(kristjans.EXAMPLE_SEED, "max")
    rules, world = env.rules(), env.map()
    first = env.telemetry_log()[0]
    acks = env.uplink([{"action": "drive", "heading_deg": 90, "metres": 5}])
    outs = [env.advance(1) for _ in range(8)]
    arrived = {packet["tick"] for packet in outs[7]["packets"]}
    lost = [tick for tick in range(1, 6) if tick not in arrived]
    rows = world["elevation_cm"]
    shown = dict(world)
    shown["elevation_cm"] = "[{} rows of {} integers; row j is y = j * cell_m, column i is x = i * cell_m; first row begins {} ...]".format(
        len(rows), len(rows[0]), rows[0][:8])
    shown["terrain"] = "[{} strings of {} codes; string j covers y from j * cell_m to (j + 1) * cell_m; first string begins {!r} ...]".format(
        len(world["terrain"]), len(world["terrain"][0]), world["terrain"][0][:24])
    shown["targets"] = world["targets"][:3] + ["... {} targets in all at launch".format(len(world["targets"]))]
    eighth = ("On the MAX map the link was closed at tick 5, so nothing arrived. The eighth `tools.advance(1)`, "
              "when the next relay pass opened, returned the packets of ticks 1 to 5 together{}:\n\n"
              "```json\nADVANCE8_JSON\n```\n\n").format(
        "" if not lost else " (the packet of tick {} was lost)".format(" and ".join(map(str, lost))))
    text = _once(kristjans.REQUEST, "## What you write", max_section())
    text = _once(text, "## `lightlag_surface.py`", eighth)
    for token, value in (
        ("MAX_TICKS", str(rules["max_ticks"])), ("WIDTH", str(int(world["width"]))), ("HEIGHT", str(int(world["height"]))),
        ("TARGETS", str(len(world["targets"]))),
        ("RULES_JSON", json.dumps(rules, indent=1)),
        ("MAP_TEXT", json.dumps(shown, indent=1)),
        ("FIRST_PACKET", json.dumps(first)),
        ("ACK_JSON", json.dumps(acks)),
        ("ADVANCE_JSON", json.dumps(outs[4])),
        ("ADVANCE8_JSON", json.dumps(outs[7])),
        ("SURFACE_SOURCE", Path(kristjans.__file__).with_name("surface.py").read_text(encoding="utf-8").rstrip()),
    ):
        text = text.replace(token, value)
    return text


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mission_hashes() -> Dict[str, str]:
    return {name: sha256((REPO / name).read_bytes()) for name in MISSION_FILES}


def helsinki_now() -> str:
    return datetime.now(ZoneInfo("Europe/Helsinki")).strftime("%Y-%m-%d %H:%M Helsinki")


def requests_sent(out: Path = BASELINE) -> bool:
    replies = out / "replies"
    return (out / "asks.jsonl").exists() or (replies.exists() and any(replies.iterdir()))


def freeze(scripted: Sequence[Path], out: Path = BASELINE, refreeze: Optional[str] = None) -> Dict[str, Any]:
    """Write the frozen protocol: request.md, scripted.json and freeze.json. A frozen protocol can be
    changed only before any request is sent, by giving `refreeze` (why); the earlier freeze is kept in
    the history."""
    history: List[Dict[str, Any]] = []
    if (out / "freeze.json").exists():
        if not refreeze:
            raise SystemExit("{} is already frozen; to change it before any request is sent, say why with "
                             "--refreeze".format(out))
        if requests_sent(out):
            raise SystemExit("requests have been sent: a changed protocol is a new baseline under a new name")
        previous = json.loads((out / "freeze.json").read_text(encoding="utf-8"))
        history = previous.get("history", []) + [{
            "frozen": previous["frozen"], "on_commit": previous["on_commit"],
            "worlds": {key: previous[key] for key in ("hard_worlds", "fair_worlds", "task_world") if key in previous},
            "request_sha256": previous["request"]["sha256"], "replaced_because": refreeze}]
    found: Dict[Tuple[str, int, str], Dict[str, Any]] = {}
    for path in scripted:
        for row in json.loads(Path(path).read_text(encoding="utf-8")):
            if row["seed"] in WORLDS and row["policy"] in PLAYERS:
                found[(row["policy"], row["seed"], row["map"])] = row
    rows = list(found.values())
    missing = [(p, s, m) for p in PLAYERS for s in WORLDS for m in ("normal", "max") if (p, s, m) not in found]
    if missing:
        raise SystemExit("the scripted results lack {} runs, e.g. {}".format(len(missing), missing[0]))
    text = build_request()
    out.mkdir(parents=True, exist_ok=True)
    (out / "request.md").write_text(text, encoding="utf-8")
    kept = [{"player": r["policy"], "seed": r["seed"], "map": r["map"], "reward": r["reward"],
             "samples": len(r["result"]["sampled_targets"]), "alive": r["result"]["alive"],
             "at_base": r["result"]["at_base"], "slip_trips": r.get("trips", 0)}
            for r in sorted(rows, key=lambda r: (r["map"], r["policy"], r["seed"]))]
    (out / "scripted.json").write_text(json.dumps(kept, indent=1) + "\n", encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    frozen = {
        "name": NAME, "frozen": helsinki_now(), "on_commit": commit, "map": "max",
        "hard_worlds": list(HARD_WORLDS), "fair_worlds": list(FAIR_WORLDS), "task_world": TASK_WORLD,
        "rules": RULES,
        "models": dict(MODELS), "samples_per_model": SAMPLES, "effort": EFFORT, "thinking": "adaptive",
        "max_tokens": MAX_TOKENS, "fallback_model": None,
        "replies": "a reply counts as it came, one without a program scoring 0 on every world; a call that "
                   "brought no reply (an API error) may be sent again",
        "request": {"file": "request.md", "sha256": sha256(text.encode("utf-8")), "characters": len(text),
                    "example_world": kristjans.EXAMPLE_SEED},
        "mission_files_sha256": mission_hashes(),
        "scripted": {"file": "scripted.json", "players": list(PLAYERS),
                     "command": "python3 -m lightlag_traverse_max.play --seeds {} --maps normal,max --policies {} "
                                "--json <file>".format(",".join(map(str, WORLDS)), ",".join(PLAYERS))},
        "transfer": {name: "docs/lightlag-runs/{}/policy.py".format(folder) for name, folder in TRANSFER},
        "sandbox": "lightlag_traverse_max.sandbox: Kristján's worker under bubblewrap (no network, read-only "
                   "files, user nobody, 2 GB address space, Python 3.12), his timeouts and call cap",
        "score": "the mission's reward: credited value x (1 at the lander, 0.5 alive elsewhere, 0 lost) / all "
                 "the value there was; a program is summed up by its mean over the superhard worlds and over "
                 "the fair worlds",
        "history": history,
    }
    (out / "freeze.json").write_text(json.dumps(frozen, indent=1) + "\n", encoding="utf-8")
    return frozen


def load_frozen(out: Path = BASELINE) -> Dict[str, Any]:
    frozen = json.loads((out / "freeze.json").read_text(encoding="utf-8"))
    if sha256((out / "request.md").read_bytes()) != frozen["request"]["sha256"]:
        raise SystemExit("request.md is not the frozen request")
    return frozen


# ---- asking (paid) -----------------------------------------------------------------------------

def load_key(env_file: Path) -> None:
    """Put ANTHROPIC_API_KEY from a KEY=VALUE file into this process's environment. Never prints it."""
    if os.environ.get(KEY):
        return
    if not Path(env_file).is_file():
        raise SystemExit("no {}: put {}=... in it (.env is gitignored)".format(env_file, KEY))
    for line in Path(env_file).read_text(encoding="utf-8").splitlines():
        name, sep, value = line.strip().partition("=")
        if sep and name.replace("export ", "").strip() == KEY:
            os.environ[KEY] = value.strip().strip("'\"")
            return
    raise SystemExit("{} has no {} line".format(env_file, KEY))


def worst_case_usd(model: str, request_characters: int, max_tokens: int = MAX_TOKENS) -> float:
    """The most one call can cost: every allowed output token, and at least one input token per 2 characters."""
    from lightlag_live.oneshot import PRICES
    price_in, price_out = PRICES[model]
    return (request_characters / 2 * price_in + max_tokens * price_out) / 1e6


class Budget:
    """A spending cap shared by the threads: a call reserves its worst case first and settles after."""

    def __init__(self, cap: float, spent: float) -> None:
        self.cap, self.spent, self.held = cap, spent, 0.0
        self._lock = threading.Lock()

    def reserve(self, amount: float) -> bool:
        with self._lock:
            if self.spent + self.held + amount > self.cap:
                return False
            self.held += amount
            return True

    def settle(self, reserved: float, cost: float) -> None:
        with self._lock:
            self.held -= reserved
            self.spent += cost


def _meta(folder: Path) -> Optional[Dict[str, Any]]:
    path = folder / "meta.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def ask(budget_usd: float, out: Path = BASELINE, send: Optional[Callable[[Path, Path, str], int]] = None,
        models: Sequence[Tuple[str, str]] = MODELS, samples: int = SAMPLES) -> int:
    """Send the frozen request for every reply not yet received: one thread per model, its samples in
    order. Stops a model before a call whose worst case would take the total past `budget_usd`."""
    frozen = load_frozen(out)
    request = out / "request.md"
    if send is None:
        from lightlag_live.oneshot import ask as live_ask

        def send(request: Path, folder: Path, model: str) -> int:
            return live_ask(request, folder, model, frozen["effort"], frozen["max_tokens"])
    replies = out / "replies"
    replies.mkdir(parents=True, exist_ok=True)
    spent = sum((_meta(f) or {}).get("cost_usd") or 0.0 for f in replies.iterdir() if f.is_dir())
    budget = Budget(budget_usd, spent)
    log_lock = threading.Lock()

    def log(entry: Dict[str, Any]) -> None:
        with log_lock, (out / "asks.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def one_model(short: str, model: str) -> None:
        for k in range(1, samples + 1):
            folder = replies / "{}-{}".format(short, k)
            meta = _meta(folder)
            if meta is not None and "error" not in meta:
                continue
            if folder.exists():  # no reply came back: keep the attempt aside and ask again
                n = 1
                while folder.with_name("{}.no-reply-{}".format(folder.name, n)).exists():
                    n += 1
                folder.rename(folder.with_name("{}.no-reply-{}".format(folder.name, n)))
            worst = worst_case_usd(model, frozen["request"]["characters"], frozen["max_tokens"])
            if not budget.reserve(worst):
                print("{}: not sent; its worst case ${:.2f} would pass the ${:.2f} budget".format(
                    folder.name, worst, budget_usd), flush=True)
                log({"reply": folder.name, "model": model, "sent": False, "budget_usd": budget_usd,
                     "at": helsinki_now()})
                return
            send(request, folder, model)
            meta = _meta(folder) or {"error": "no meta.json"}
            cost = worst if "error" in meta else meta["cost_usd"]  # an error's cost is unknown: count the worst
            budget.settle(worst, cost)
            log({"reply": folder.name, "model": model, "sent": True, "budget_usd": budget_usd, "at": helsinki_now(),
                 "cost_usd": meta.get("cost_usd"), "stop_reason": meta.get("stop_reason"),
                 "error": meta.get("error"), "has_play": meta.get("has_play"), "seconds": meta.get("seconds")})

    threads = [threading.Thread(target=one_model, args=pair) for pair in models]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    done = sum(1 for short, _ in models for k in range(1, samples + 1)
               if "error" not in (_meta(replies / "{}-{}".format(short, k)) or {"error": 1}))
    print("{} of {} replies in hand; ${:.4f} spent in all (budget ${:.2f})".format(
        done, len(models) * samples, budget.spent, budget_usd))
    return 0 if done == len(models) * samples else 1


# ---- playing (free) ----------------------------------------------------------------------------

def programs(out: Path = BASELINE) -> List[Tuple[str, Optional[Path]]]:
    """(name, policy file or None for a reply without a program): the replies, then Kristján's programs."""
    found: List[Tuple[str, Optional[Path]]] = []
    replies = out / "replies"
    for short, _ in MODELS:
        for k in range(1, SAMPLES + 1):
            meta = _meta(replies / "{}-{}".format(short, k))
            if meta is None or "error" in meta:
                continue
            policy = replies / "{}-{}".format(short, k) / "policy.py"
            found.append(("{}-{}".format(short, k), policy if meta.get("has_play") and policy.stat().st_size else None))
    for name, folder in TRANSFER:
        found.append((name, REPO / "docs" / "lightlag-runs" / folder / "policy.py"))
    return found


def _play(job: Tuple[str, Optional[str], int]) -> Dict[str, Any]:
    from .sandbox import run
    name, policy, seed = job
    if policy is None:
        return {"program": name, "seed": seed, "status": "no program", "errors": [], "calls": 0, "reward": 0.0,
                "samples": 0, "alive": True, "at_base": True, "seconds": 0.0}
    with tempfile.TemporaryDirectory(prefix="max-baseline-") as folder:
        summary = run(Path(policy), Path(folder), seed, "max")
    keep = ("status", "errors", "calls", "reward", "samples", "alive", "at_base", "seconds", "think_max_seconds")
    return dict({"program": name, "seed": seed}, **{key: summary[key] for key in keep})


def play(out: Path = BASELINE, workers: int = 4) -> List[Dict[str, Any]]:
    """Play every program on every frozen world, on the MAX map; adds to plays.json, never replays a done pair."""
    load_frozen(out)
    path = out / "plays.json"
    rows: List[Dict[str, Any]] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    done = {(row["program"], row["seed"]) for row in rows}
    jobs = [(name, None if policy is None else str(policy), seed) for name, policy in programs(out)
            for seed in WORLDS if (name, seed) not in done]
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        for row in pool.map(_play, jobs):
            rows.append(row)
            print("{:<16} world {:>4}: {:.3f}  {}{}".format(
                row["program"], row["seed"], row["reward"], row["status"],
                "" if row["at_base"] else (" away" if row["alive"] else " LOST")), flush=True)
            path.write_text(json.dumps(sorted(rows, key=lambda r: (r["program"], r["seed"])), indent=1) + "\n",
                            encoding="utf-8")
    return rows


# ---- report ------------------------------------------------------------------------------------

def _fate(alive: Any, at_base: Any) -> str:
    return "home" if at_base else ("away" if alive else "lost")


def _mean(runs: Dict[int, Dict[str, Any]], worlds: Sequence[int]) -> Optional[float]:
    return statistics.mean(runs[s]["reward"] for s in worlds) if all(s in runs for s in worlds) else None


def _line(label: str, runs: Dict[int, Dict[str, Any]], extra: str = "") -> str:
    cells = ["{:.3f}{}".format(runs[s]["reward"], {"home": "", "away": "*", "lost": "†"}[
        _fate(runs[s]["alive"], runs[s]["at_base"])]) if s in runs else "–" for s in WORLDS]
    means = ["**{:.3f}**".format(m) if m is not None else "–"
             for m in (_mean(runs, HARD_WORLDS), _mean(runs, FAIR_WORLDS))]
    return "| {} | {} | {} |{}".format(label, " | ".join(means), " | ".join(cells), extra)


def report(out: Path = BASELINE) -> str:
    """The baseline's README: the protocol and every result so far."""
    frozen = load_frozen(out)
    scripted = json.loads((out / "scripted.json").read_text(encoding="utf-8"))
    plays = json.loads((out / "plays.json").read_text(encoding="utf-8")) if (out / "plays.json").exists() else []
    head = "| Player | Superhard mean | Fair mean | {} |\n|---|---|---|{}\n".format(
        " | ".join("{} ({})".format(s, "hard" if s in HARD_WORLDS else "fair" if s in FAIR_WORLDS else "task")
                   for s in WORLDS), "---|" * len(WORLDS))
    lines = []
    for option in ("max", "normal"):
        lines.append("\n**Scripted players, {} map** (`scripted.json`):\n\n{}".format(
            "MAX" if option == "max" else "normal", head) + "\n".join(
            _line(player, {r["seed"]: r for r in scripted if r["player"] == player and r["map"] == option})
            for player in PLAYERS))
    by_program: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for row in plays:
        by_program.setdefault(row["program"], {})[row["seed"]] = row
    replies = [name for name in by_program if not name.startswith("normal-")]
    transfer = [(name, by_program[name]) for name, _ in TRANSFER if name in by_program]
    if replies:
        rows, means = [], []
        for short, model in MODELS:
            names = [n for n in ("{}-{}".format(short, k) for k in range(1, SAMPLES + 1)) if n in by_program]
            for name in names:
                meta = _meta(out / "replies" / name) or {}
                rows.append(_line("{} ({})".format(name, model), by_program[name],
                                  " ${:.2f}, {} output tokens".format(meta.get("cost_usd") or 0.0,
                                                                      meta.get("output_tokens", "?"))))
            hard = [m for m in (_mean(by_program[n], HARD_WORLDS) for n in names) if m is not None]
            fair = [m for m in (_mean(by_program[n], FAIR_WORLDS) for n in names) if m is not None]
            if hard and fair:
                means.append("| {} | **{:.3f}** | **{:.3f}** | {} |".format(
                    model, statistics.mean(hard), statistics.mean(fair),
                    ", ".join("{:.3f} / {:.3f}".format(h, f) for h, f in zip(hard, fair))))
        lines.append("\n**Programs written for the MAX map** (one reply each, `replies/`; cost after the row):\n\n"
                     + head + "\n".join(rows))
        lines.append("\n**By model**, mean of its programs:\n\n| Model | Superhard | Fair | Each program "
                     "(superhard / fair) |\n|---|---|---|---|\n" + "\n".join(means))
    if transfer:
        lines.append("\n**Kristján's one-request programs, written for the normal map**, played unchanged on the "
                     "MAX map:\n\n" + head + "\n".join(_line(name, runs) for name, runs in transfer))
    text = """# {name}

A freeze point for the MAX map: Claude models write one program each, from one request, and it plays
superhard and fair MAX worlds. Frozen {frozen}. Generated by `python3 -m lightlag_traverse_max.oneshot
report`; the method and every command are in [`lightlag_traverse_max/oneshot.py`](../../../lightlag_traverse_max/oneshot.py).

## What is frozen

- **Superhard worlds:** {hard}. {rule_hard}
- **Fair worlds:** {fair}. {rule_fair}
- **Anchor:** {task}, {rule_task}
- **Where they come from:** {rule_pool}
- **Request:** [`request.md`](request.md), sha256 `{sha}`: Kristján's one-request text with the MAX map's rules, map
  and example world ({example}), plus a section on what the MAX map changes.
- **Models:** {models}; {samples} replies each, effort `{effort}`, adaptive thinking, at most {tokens} output tokens,
  no retries, no fallback model. A reply counts as it came; one without a program scores 0 everywhere.
- **Playing:** every program plays every world once on the MAX map in `lightlag_traverse_max.sandbox`
  (Kristján's worker under bubblewrap; it reproduces his Docker run of the normal-map Opus program byte for byte).
- **The mission's code** is pinned by sha256 in [`freeze.json`](freeze.json).

## Results

Score per world; `*` ended away from the lander (half score), `†` lost (battery empty). Means are over the 3 superhard
and the 3 fair worlds; world {task} stands apart.
{tables}
""".format(name=NAME, frozen=frozen["frozen"], hard=", ".join(map(str, HARD_WORLDS)), fair=", ".join(map(str, FAIR_WORLDS)), task=TASK_WORLD,
           rule_hard=RULES["superhard"], rule_fair=RULES["fair"], rule_task=RULES["task_world"],
           rule_pool=RULES["pool"],
           sha=frozen["request"]["sha256"], example=frozen["request"]["example_world"],
           models=", ".join("`{}`".format(m) for _, m in MODELS), samples=frozen["samples_per_model"],
           effort=frozen["effort"], tokens=frozen["max_tokens"], tables="\n".join(lines))
    (out / "README.md").write_text(text, encoding="utf-8")
    return text


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    requesting = commands.add_parser("request", help="write the request text")
    requesting.add_argument("out", type=Path)
    freezing = commands.add_parser("freeze", help="write the frozen protocol")
    freezing.add_argument("--scripted", type=Path, nargs="+", required=True,
                          help="lightlag_traverse_max.play --json output, one or more files")
    freezing.add_argument("--refreeze", help="change a frozen protocol before any request is sent: why")
    asking = commands.add_parser("ask", help="PAID: send the frozen request for every reply not yet received")
    asking.add_argument("--budget-usd", type=float, required=True)
    asking.add_argument("--env-file", type=Path, default=REPO / ".env")
    playing = commands.add_parser("play", help="play every program on every frozen world")
    playing.add_argument("--workers", type=int, default=4)
    commands.add_parser("report", help="write the README with every result so far")
    args = parser.parse_args(argv)
    if args.command == "request":
        text = build_request()
        args.out.write_text(text, encoding="utf-8")
        print("wrote {} ({} characters)".format(args.out, len(text)))
        return 0
    if args.command == "freeze":
        frozen = freeze(args.scripted, refreeze=args.refreeze)
        print("froze {}: request sha256 {}".format(BASELINE, frozen["request"]["sha256"]))
        return 0
    if args.command == "ask":
        load_key(args.env_file)
        return ask(args.budget_usd)
    if args.command == "play":
        play(workers=args.workers)
        return 0
    report()
    print("wrote {}".format(BASELINE / "README.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
