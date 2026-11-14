#!/usr/bin/env python3
"""Build Traverse demo pages for the normal and MAX map option: one world, both maps, four players.

    python3 viewer/build_traverse_max.py                  # world 2026: viewer/traverse-players-normal.html and -max.html
    python3 viewer/build_traverse_max.py --seed 500       # another world
    python3 viewer/build_traverse_max.py --maps max       # only the MAX page
    python3 viewer/build_traverse_max.py --evaluation     # the six held-out worlds: viewer/traverse-evaluation-max.html

Each page is Kristján's Traverse demo (viewer/traverse/, unchanged) fed with four runs on one map:
the reference pilot in gold, then Manh's best (`manh_max`), greedy and straight. The missions are
played here with lightlag_traverse_max (a seed always gives the same runs), saved the way real runs
are, and gathered by build_traverse.gather, so its checks apply. Nothing of Kristján's is written:
not viewer/traverse/data.json, not viewer/traverse-demo.html.

Two things the page shows differently on the MAX map, because it was drawn for the normal one:
  * lost packets leave gaps in the telemetry, and the page draws the operator's fix tick by tick,
    so a lost tick repeats the last fix received (what the operator still had);
  * a stop by the onboard slip check is listed like a stop on ground too steep: the slope made the
    wheels slip past the limit.
Standard library only.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "viewer"))

import build_traverse  # noqa: E402
from lightlag_traverse.play import PublicTools, save_run  # noqa: E402
from lightlag_traverse_max.environment import OPTIONS, make_env  # noqa: E402
from lightlag_traverse_max.heldout import EVALUATION_WORLDS, FAIR_WORLDS, SUPERHARD_WORLDS  # noqa: E402
from lightlag_traverse_max.play import policy  # noqa: E402

# (player, kind on the page, label, what it is)
PLAYERS: List[Tuple[str, str, str, str]] = [
    ("pilot", "reference", "Reference pilot", "Kristján's reference pilot, unchanged"),
    ("manh_max", "scripted", "Manh's best", "manh_max: Kristján's pilot with the max-env layers"),
    ("greedy", "scripted", "Greedy", "the pilot without route optimisation"),
    ("straight", "scripted", "Straight line", "drives straight at the next target and ignores the ground"),
]

NOTES = {
    "normal": (" <b>Normal map.</b> Manh's best sends exactly the reference's commands here, so the two "
               "tracks lie on top of each other."),
    "max": (" <b>MAX map:</b> the link is open 4 ticks in 8; a wheel slip over 0.45 ends the drive and clears "
            "the queue (listed as <i>ground too steep</i>); crust regions hide soft sand; the dune slope gain "
            "and the wheel size are hidden; the position fix is 2 m off; turning costs energy; 10% of packets "
            "are lost (the fix then stays where it was) and 5% of fixes are wild."),
}
TITLES = {"normal": ("Lightlag Traverse · normal map", "TRAVERSE"),
          "max": ("Lightlag Traverse · MAX map", "TRAVERSE · MAX")}


def play(job: Tuple[str, int, str, Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    """One whole mission: the player gets the five public tools, then the remaining ticks pass."""
    name, seed, option, mission = job
    env = make_env(seed, option, mission=mission) if mission else make_env(seed, option)
    started = time.time()
    policy(name)(PublicTools(env))
    seconds = time.time() - started
    while not env.advance(5)["episode_complete"]:
        pass
    return {"player": name, "map": option, "result": env.evaluate(), "replay": env.replay(),
            "seconds": round(seconds, 1)}


def filled(replay: Dict[str, Any]) -> Dict[str, Any]:
    """The replay with one telemetry packet per tick, from tick 0 to the last one received: a lost
    packet's tick repeats the last packet received, marked `lost`."""
    received = {packet["tick"]: packet for packet in replay["received_telemetry"]}
    log, last = [], None
    for tick in range(max(received) + 1):
        packet = received.get(tick)
        if packet is None:
            packet = dict(last, tick=tick, lost=True)
        log.append(packet)
        last = packet
    return dict(replay, received_telemetry=log)


def page_data(option: str, runs: Sequence[Dict[str, Any]], players: Sequence[Tuple[str, str, str, str]],
              seed: int) -> Dict[str, Any]:
    """Kristján's page data for these runs, gathered and checked by his builder."""
    with tempfile.TemporaryDirectory(prefix="traverse-players-") as root:
        for (name, kind, label, how), run in zip(players, runs):
            replay = filled(run["replay"]) if option == "max" else run["replay"]
            save_run(Path(root) / "traverse-{}".format(name), {"result": run["result"], "replay": replay},
                     {"kind": kind, "label": label, "model": "", "how": how,
                      "source": "python3 viewer/build_traverse_max.py --seed {} --maps {}".format(seed, option)})
        data = build_traverse.gather(build_traverse.run_folders(Path(root)))
    data["title"], data["brand"] = TITLES[option]
    data["pitch"] += NOTES[option]
    return data


def build(seed: int = 2026, maps: Sequence[str] = OPTIONS, out_dir: Path = REPO / "viewer",
          players: Sequence[Tuple[str, str, str, str]] = PLAYERS, mission: Optional[Dict[str, Any]] = None,
          workers: int = 8) -> List[Path]:
    """Play every player on every map, then write one page per map. Returns the pages written."""
    jobs = [(name, seed, option, mission) for option in maps for name, _, _, _ in players]
    if workers <= 1:
        played = [play(job) for job in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            played = list(pool.map(play, jobs))
    pages = []
    for option in maps:
        runs = [run for run in played if run["map"] == option]
        data = page_data(option, runs, players, seed)
        out = Path(out_dir) / "traverse-players-{}.html".format(option)
        page = build_traverse.standalone(data)
        out.write_text(page, encoding="utf-8")
        pages.append(out)
        print("wrote {} ({:.1f} MB): world {}, {} map".format(out.name, len(page) / 1e6, seed, option))
        for run, shown in zip(runs, [next(r for r in data["runs"] if r["id"] == "traverse-" + run["player"])
                                     for run in runs]):
            print("  {:<16} reward {:.3f}  samples {:>2}  {:<22} {:>6.1f} s".format(
                shown["label"], shown["reward"], len(shown["samples"]),
                "lost" if not shown["alive"] else "home" if shown["home"] else "away from the lander", run["seconds"]))
    return pages


def evaluation(out: Path = REPO / "viewer" / "traverse-evaluation-max.html", worlds: Sequence[int] = EVALUATION_WORLDS,
               players: Sequence[Tuple[str, str, str, str]] = PLAYERS, mission: Optional[Dict[str, Any]] = None,
               workers: int = 8) -> Path:
    """The held-out evaluation worlds on the MAX map, one site each, all in one page (keys 1-6 switch)."""
    jobs = [(name, seed, "max", mission) for seed in worlds for name, _, _, _ in players]
    if workers <= 1:
        played = [play(job) for job in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            played = list(pool.map(play, jobs))
    per_world = [played[i * len(players):(i + 1) * len(players)] for i in range(len(worlds))]
    pages = [page_data("max", runs, players, seed) for seed, runs in zip(worlds, per_world)]
    group = {seed: "fair" for seed in FAIR_WORLDS}
    group.update({seed: "superhard" for seed in SUPERHARD_WORLDS})
    # Kristján's campaign page as it is (his headings, his text, his site buttons); only the worlds differ.
    reference = {seed: page["runs"][0]["reward"] for seed, page in zip(worlds, pages)}
    for number, (seed, page) in enumerate(zip(worlds, pages), 1):
        page["site"] = number
        page["brand"] = "SITE {} / {}".format(number, len(worlds))
        page["title"] = "Lightlag Traverse · site {}".format(number)
        page["pitch"] = page["pitch"].replace(NOTES["max"], "")
        page["sites"] = [{"n": n, "label": "SITE {}".format(n), "note": "reference {:.2f} here".format(reference[s])}
                         for n, s in enumerate(worlds, 1)]
    html = build_traverse.standalone(pages)
    Path(out).write_text(html, encoding="utf-8")
    print("wrote {} ({:.1f} MB): {} held-out worlds, MAX map".format(Path(out).name, len(html) / 1e6, len(worlds)))
    for seed, page in zip(worlds, pages):
        print("  world {:>4} {:<9} ".format(seed, group.get(seed, "")) + "  ".join(
            "{} {:.3f}".format(run["label"], run["reward"]) for run in page["runs"]))
    return Path(out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--evaluation", action="store_true",
                        help="the six held-out evaluation worlds, MAX map, one page: viewer/traverse-evaluation-max.html")
    parser.add_argument("--seed", type=int, default=2026, help="the world (default 2026, the task's world)")
    parser.add_argument("--maps", default="normal,max", help="normal, max, or both")
    parser.add_argument("--out-dir", type=Path, default=REPO / "viewer")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    if args.evaluation:
        evaluation(workers=args.workers)
        return 0
    maps = args.maps.split(",")
    for option in maps:
        if option not in OPTIONS:
            parser.error("unknown map {!r}: choose from {}".format(option, ", ".join(OPTIONS)))
    build(args.seed, maps, args.out_dir, workers=args.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
