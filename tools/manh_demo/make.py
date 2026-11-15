#!/usr/bin/env python3
"""Build manh_demo_1: a more cinematic cut of Kristján's Lightlag Traverse demo video.

    python -m tools.manh_demo.make all          # voice, picture, sound, video (about ten minutes)
    ... make voice       # speak the narration (Kristján's script and voice container, no network)
    ... make capture     # record every shot frame by frame   [--only cold,energy]
    ... make fit         # stretch the last card so the film is exactly as long as it should be
    ... make assemble    # synthesise the sound track, join the shots, write the video and subtitles
    ... make split       # the film without its narration, and the narration alone (clean and deep), to build/out/
    ... make voices      # the opening line in four voices, to choose one by ear (Docker)
    ... make piece --name lineup,drivers   # record draft pieces as clips of their own, to build/out/
    ... make clip --shot ground            # one recorded shot as a clip of its own, without narration
    ... make check       # a speech recogniser writes down the finished sound track; compare with the script
    ... make frames --shot energy --at 2.5,9   # look at single frames of one shot without recording it
    ... make all --film 2                      # the second draft (manh_demo_2): script v2, nine models in the replay
    ... make kit --film 2                      # docs/manh-demo/narration-kit/: the film without its narrator, the lines with their times

`--film 2` goes with every step. The second draft has its own script, shots and build folder
(`build/film2/`), so the first cut and its recordings stay as they are.

Run it with the Python of `tools/manh_demo/build/venv` (playwright, numpy, scipy, soundfile). Needs
Docker with Kristján's narrator image (`docker build -t lightlag-narrator tools/demo_video/voice`),
Playwright's Chromium (`python -m playwright install chromium`) and ffmpeg. On a machine where the
shell is not in the docker group yet: `sg docker -c "<the command>"`.

Kristján's video (`docs/demo-video/`) is the team's main one and is not touched: this cut reads his
storyboard, his scenes and his numbers and writes to `docs/manh-demo/`. Intermediate files go to
`tools/manh_demo/build/` (not committed).
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.demo_video import data as film_data
from tools.demo_video import make as kmake

from . import cut, makers, pages

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = HERE / "build"                    # the venv, the fonts' cache and the draft clips (out/), whichever film is built
BUILD = ROOT                             # the film's own recordings, voice and sound; see `use`
OUT = REPO / "docs" / "manh-demo"
VIDEO = OUT / (cut.NAME + ".mp4")
FPS, SIZE = kmake.FPS, kmake.SIZE
FADE_IN, FADE_OUT = kmake.FADE_IN, kmake.FADE_OUT
CHROME_ARGS = ["--enable-gpu", "--ignore-gpu-blocklist", "--hide-scrollbars", "--force-color-profile=srgb",
               "--autoplay-policy=no-user-gesture-required"]

# Kristján's helpers (the voice, the subtitles, the listening check) read these when they are called.
kmake.BUILD, kmake.OUT, kmake.VIDEO = BUILD, OUT, VIDEO

run = kmake.run

# The films this tool builds. 1 is the cinematic cut of Kristján's film: his script, his shots. 2 is the next draft:
# the plain-words script, the pieces Manh has looked at one by one, and a replay with nine models in it (`makers.CAST`).
FILMS: Dict[int, Dict[str, Any]] = {
    1: {"name": cut.NAME, "folder": None, "lines": cut.LINES, "subtitles": cut.SUBTITLES, "voice": cut.VOICE, "shots": cut.shots,
        "poster": cut.POSTER, "extra": {}, "cast": None, "style": "clean", "said": {}},
    2: {"name": cut.NAME2, "folder": "film2", "lines": cut.LINES2, "subtitles": cut.SUBTITLES2, "voice": cut.VOICE2, "shots": cut.shots2,
        "poster": None, "extra": {"cards": "score", "tiers": makers.cast_tiers()}, "cast": makers.CAST, "style": "deep", "said": cut.SAID2},
    # 3 is the long film: the same story in about ten minutes (no fixed length: nothing is stretched to fit).
    3: {"name": cut.NAME3, "folder": "film3", "lines": cut.LINES3, "subtitles": cut.SUBTITLES3, "voice": cut.VOICE3, "shots": cut.shots3,
        "poster": None, "extra": {"cards": "score", "tiers": {**makers.cast_tiers(), makers.CAST3["Gemini 4 Carbon"]: "FLAGSHIP"}}, "cast": makers.CAST3,
        "style": "deep", "said": cut.SAID3, "limit": 660.0, "target": None, "crf": "26"},
}
FILM = FILMS[1]


def use(number: int) -> None:
    """Build film `number` from here on: its script, its shots, its own build folder."""
    global FILM, BUILD, VIDEO
    FILM = FILMS[number]
    BUILD = ROOT / FILM["folder"] if FILM["folder"] else ROOT
    VIDEO = OUT / (FILM["name"] + ".mp4")
    kmake.BUILD, kmake.VIDEO = BUILD, VIDEO
    kmake.storyboard.LINES, kmake.storyboard.SUBTITLES, kmake.storyboard.VOICE = FILM["lines"], FILM["subtitles"], FILM["voice"]


class SavedRuns(type(film_data.RUNS)):
    """The folder of saved runs as Kristján's numbers read it, without the runs that carry no `run.json`: the tier
    comparison's GPT and Gemini runs are saved another way, and his reader stops at the first folder without one."""

    def glob(self, pattern: str) -> Any:
        return (path for path in super().glob(pattern) if (path / "run.json").exists())


film_data.RUNS = SavedRuns(film_data.RUNS)


def plan(stretch: Optional[float] = None) -> List[Dict[str, Any]]:
    if stretch is None:
        saved = BUILD / "fit.json"
        stretch = json.loads(saved.read_text(encoding="utf-8"))["stretch"] if saved.exists() else 0.0
    return FILM["shots"](kmake.durations(), kmake.spoken_words(), stretch)


# ---------------------------------------------------------------- picture
def open_page(context: Any, shot: Dict[str, Any], sources: Dict[str, Any], problems: List[str]) -> Any:
    """The page of a shot, loaded, dressed and ready for its first frame. Its errors are collected in `problems`."""
    page = context.new_page()
    page.on("pageerror", lambda error: problems.append(str(error)[:300]))
    tiles = makers.for_page()
    if shot["page"] == "film":
        page.add_init_script("window.FILM_DATA = {}; window.__MANH = {};".format(
            sources["facts"], json.dumps({"tiles": tiles, "lineup": makers.lineup(), **sources["numbers"]})))
        page.goto(sources["film"].as_uri() + "?scene=" + shot["scene"])
        page.wait_for_function("window.__scene !== undefined && document.fonts.status === 'loaded'", polling=50)
        page.evaluate(sources["scenes.js"])
    else:
        page.goto(sources["campaign"].as_uri() + "?site={}".format(shot["site"]))
        page.wait_for_function("window.LIGHTLAG_TRAVERSE_APP !== undefined", polling=50, timeout=60000)
        page.evaluate(sources["overlay.js"])
        page.evaluate("window.__overlay.chapter({})".format(json.dumps(shot.get("chapter"))))
        runs = page.evaluate("() => window.LIGHTLAG_TRAVERSE_APP.RUNS.map(run => [run.id, run.kind, run.label, run.model || ''])")
        whose = {run: "rl" if label.startswith("RL agent") else makers.maker_of(label + " " + model) for run, kind, label, model in runs if kind != "reference"}
        icons = makers.scene_icon_settings()                                                            # the floating marks over the rovers
        tiers = dict(sources.get("extra", {}).get("tiers", {}))
        for run, key in whose.items():
            if key == "rl":                                                                             # the team's own trained agent: its lime network, and whose it is
                from . import learned
                icons["marks"]["rl"] = learned.icon_mark()
                tiers[run] = "OUR BEST SEED"                                                           # one rover, so one seed: the best, and it says so
        page.evaluate("m => { window.__MANH = m; }", {"tiles": tiles, "makers": {run: key for run, key in whose.items() if key}, "icons": icons,
                                                         **sources.get("extra", {}), "tiers": tiers})   # a draft's own settings, say cards: "score"
        page.evaluate(sources["tracker.js"])
        if shot.get("addon"):                 # a piece that draws frames of its own on top of the page (the opening in space)
            given = shot.get("addon_settings", {})
            settings = {**(makers.icon_settings(company=bool(given.get("company"))) if shot["addon"] == "icons.js" else {}),
                        **({**makers.scene_icon_settings(), "makers": {run: key for run, key in whose.items() if key}} if shot["addon"] == "icons_scene.js" else {}), **given}
            page.evaluate("p => { window.__PIECE = p; }", settings)
            page.evaluate((HERE / shot["addon"]).read_text(encoding="utf-8"))
    page.evaluate("() => window.__manh.ready")
    return page


def record(context: Any, shot: Dict[str, Any], lengths: Dict[str, float], sources: Dict[str, Any],
           stills: Optional[List[float]] = None) -> Dict[str, Any]:
    """Record one shot, beat by beat as Kristján's recorder does. Returns its length, when each line and
    sound starts inside it, and (for the ground shots) what the followed rover did in every frame.
    With `stills`, nothing is encoded: those moments of the shot are saved as pictures instead."""
    problems: List[str] = []
    page = open_page(context, shot, sources, problems)
    film = shot["page"] == "film"

    def act(code: str) -> Any:               # run a storyboard snippet in the page, with A as the demo's controls
        return page.evaluate("() => { const A = window.LIGHTLAG_TRAVERSE_APP; " + code + " }")

    encoder = None if stills is not None else kmake.Encoder(BUILD / "shots" / "{}.mp4".format(shot["name"]))
    wanted = sorted(stills or [])
    fade_in, fade_out = shot.get("fade_in", FADE_IN), shot.get("fade_out", FADE_OUT)
    frame, events, thumps, sounds, talking = 0, [], [], [], 0.0
    telemetry: List[Dict[str, Any]] = []
    last_thump: Optional[float] = None
    beats = shot["beats"]
    for number, beat in enumerate(beats):
        last, start = number == len(beats) - 1, frame
        spoken = lengths[beat["vo"]] if beat.get("vo") else 0.0
        said = beat.get("vo_at", 0.0) + spoken                   # when the beat's last line ends: its own, or a later one laid in the same beat
        for extra in beat.get("more", []):
            said = max(said, extra["at"] + lengths[extra["vo"]])
        if beat.get("vo"):
            talking = max(talking, start / FPS + said)
        held = (said + beat.get("pad", 0.0)) if beat.get("vo") and not beat.get("over") else 0.0
        if last:
            held = max(held, talking - start / FPS + beat.get("pad", 0.0))
        need = math.ceil(max(beat.get("min", 0.0), held) * FPS)
        if last and beat.get("until"):
            raise SystemExit("{}: the last beat of a shot needs a fixed length".format(shot["name"]))
        if film:
            page.evaluate("([d, cues]) => { window.__scene.duration = d; window.__scene.cues = cues; }", [need / FPS, beat.get("cues", [])])
            for cue in page.evaluate("([name, d, cues]) => window.__manh.sfx(name, d, cues)", [shot["scene"], need / FPS, beat.get("cues", [])]):
                if cue["at"] < need / FPS - 0.05:
                    sounds.append({**cue, "at": round(start / FPS + cue["at"], 3), "scene_at": cue["at"]})
        else:
            page.evaluate("cues => { window.__overlay.cues = cues; }", beat.get("overlay", []))
            if beat.get("js"):
                act(beat["js"])
        if beat.get("vo"):
            events.append({"line": beat["vo"], "at": round(frame / FPS + beat.get("vo_at", 0.0), 3)})
        for extra in beat.get("more", []):
            events.append({"line": extra["vo"], "at": round(frame / FPS + extra["at"], 3)})
        if "thump" in beat:
            thumps.append(round(frame / FPS + beat["thump"], 3))
            last_thump = frame / FPS + beat["thump"]
        for cue in beat.get("sfx", []):
            sounds.append({**{key: value for key, value in cue.items() if key != "t"}, "at": round(frame / FPS + cue["t"], 3)})
        pending = sorted(beat.get("at", []), key=lambda item: item["t"])
        while True:
            local = (frame - start) / FPS
            while pending and pending[0]["t"] <= local:
                act(pending.pop(0)["js"])
            black = max(0.0, 1.0 - frame / (fade_in * FPS)) if fade_in else 0.0
            if last:
                black = max(black, 1.0 - (start + need - 1 - frame) / (fade_out * FPS))
            if film:
                page.evaluate("black => { window.__scene.fade = black; window.__film.step(1000 / %d); }" % FPS, black)
            else:
                since = None if last_thump is None or frame / FPS < last_thump else frame / FPS - last_thump
                seen = page.evaluate(
                    "([ts, black, shot, fx]) => { window.__film.step(1000 / %d); window.__overlay.draw(ts, black, shot); const seen = window.__manh.draw(fx); "
                    "if (window.__piece) window.__piece.draw(shot); return seen; }" % FPS,
                    [local, black, frame / FPS, {"dt": 1.0 / FPS, "since": since, "shot": frame / FPS, "trackers": beat.get("trackers")}])
                telemetry.append(seen)
            if encoder:
                encoder.add(page.screenshot(type="jpeg", quality=95))
            while wanted and frame / FPS >= wanted[0] - 1e-9:
                target = BUILD / "frames" / "{}_{:06.2f}.jpg".format(shot["name"], wanted.pop(0))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(page.screenshot(type="jpeg", quality=90))
                print("  " + str(target.relative_to(REPO)), flush=True)
            frame += 1
            if stills is not None and not wanted:
                page.close()
                return {"name": shot["name"], "frames": frame}
            if frame - start >= need and (not beat.get("until") or act("return " + beat["until"] + ";")):
                break
            if frame - start > need + 40 * FPS:
                raise SystemExit("{}: beat {} never ended".format(shot["name"], number + 1))
        if beat.get("then"):
            act(beat["then"])
    if film:                                 # every sound under a chart must sit on a moment the chart really used
        used = page.evaluate("() => window.__manh.onsets()")
        for cue in sounds:
            if cue.get("check") and not any(abs(cue["scene_at"] * 1000 - onset) <= 2 for onset in used):
                raise SystemExit("{}: the sound {!r} at {:.3f}s is not a moment of the scene any more: look at tools/manh_demo/scenes.js".format(
                    shot["name"], cue["kind"], cue["scene_at"]))
    if encoder:
        encoder.close()
    page.close()
    if problems:
        raise SystemExit("{}: the page reported errors: {}".format(shot["name"], problems[:3]))
    if telemetry:
        (BUILD / "tele").mkdir(parents=True, exist_ok=True)
        (BUILD / "tele" / "{}.json".format(shot["name"])).write_text(json.dumps(telemetry, separators=(",", ":")), encoding="utf-8")
    made = {"name": shot["name"], "page": shot["page"], "frames": frame, "seconds": round(frame / FPS, 3), "lines": events, "thumps": thumps, "sfx": sounds}
    if shot.get("vacuum"):
        made["vacuum"] = shot["vacuum"]       # seconds of the shot spent in space: no wind there
    return made


def chart_numbers(data: Dict[str, Any]) -> Dict[str, Any]:
    """What this cut's own charts show: the trained agent beside the planner, and every campaign run of all nine models."""
    facts, claude = makers.facts(), {}
    for item in data["campaign"]["claude"]:
        claude.setdefault(item["model"].upper(), []).append(item["score"])
    tiers = makers.tier_table(claude, data["campaign"]["reference"]["score"], facts["rl"])
    fresh, gain = data["final"]["fresh"], data["planner"]["first"]["gain"]
    worlds, outcomes, game = makers.worlds_table(), makers.outcomes_table(), makers.game_facts()
    sol = next(row for row in outcomes["rows"] if row["name"] == "GPT-6.1 SOL")
    long = {"ticks": game["ticks"], "targets_at_launch": game["targets_at_launch"], "width": game["width"], "runs": tiers["count"],
            "reference_percent": tiers["reference_percent"], "best_run_per_mille": round(tiers["best_run"]["score"] * 1000),
            "best_mean_percent": tiers["best_mean_percent"], "best_mean_model": tiers["best_mean"]["name"],
            "google_runs": outcomes["labs"]["google"]["runs"], "google_never_started": outcomes["labs"]["google"]["never_started"],
            "anthropic_lost": outcomes["labs"]["anthropic"]["lost"], "sol_away_on_site_one": sum(run["sites"][0] == "away" for run in sol["runs"]),
            "sol_lost_or_idle": sol["count"]["lost"] + sol["count"]["idle"],
            "cheapest_cents": round(min(outcomes["costs"][row["name"]] for row in outcomes["rows"] if row["maker"] != "anthropic") * 100),
            "dearest_cents": round(max(outcomes["costs"].values()) * 100), "best_mean_cents": round(outcomes["costs"][tiers["best_mean"]["name"]] * 100),
            "reference_lines_hundreds": game["reference_lines"] // 100, "worlds": worlds["worlds"], "pairs": worlds["pairs"], "worlds_percent": worlds["percent"],
            "reference_lost": worlds["reference_lost"], "programs_lost": worlds["lost"], "initial_percent": round(fresh["initial"] * 100),
            "ppo_percent": round(fresh["ppo"] * 100), "gain_under_half_a_point": 0 < gain < 0.5,
            "training_missions_thousands": data["final"]["training_missions"] // 1000}
    return {"long": long, "outcomes": outcomes, "game": game, "facts": {**facts, "models": len(tiers["rows"]), "below_rl": tiers["below_learned"], "best_model": tiers["best_mean"]}, "tiers": tiers,
            "worlds": worlds,
            "final": {"initial_percent": round(fresh["initial"] * 100), "ppo_percent": round(fresh["ppo"] * 100), "gain_under_half_a_point": 0 < gain < 0.5}}


def browser_sources() -> Dict[str, Any]:
    data = {**film_data.build(), **film_data.extras()}        # extras: what the slides of Kristján's third cut read (the learning slide)
    numbers = chart_numbers(data)
    for table, claims in FILM["said"].items():            # the narration states these in words
        for key, said in claims.items():
            if numbers[table][key] != said:
                raise SystemExit("{}: the narration says {} = {}, the runs now say {}: change the line in tools/manh_demo/cut.py".format(
                    FILM["name"], key, said, numbers[table][key]))
    return {
        "campaign": pages.cast_page(BUILD, FILM["cast"]) if FILM["cast"] else pages.campaign_page(BUILD),
        "film": pages.film_page(BUILD), "overlay.js": pages.overlay_script(),
        "tracker.js": (HERE / "tracker.js").read_text(encoding="utf-8"), "scenes.js": (HERE / "scenes.js").read_text(encoding="utf-8"),
        "facts": json.dumps({**data, "live_url": cut.LIVE_URL}, separators=(",", ":")),
        "numbers": numbers, "extra": dict(FILM["extra"]),
    }


def with_browser(work: Any) -> Any:
    from playwright.sync_api import sync_playwright

    sources = browser_sources()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=CHROME_ARGS, env=pages.font_environment(ROOT))
        context = browser.new_context(viewport={"width": SIZE[0], "height": SIZE[1]}, device_scale_factor=1)
        context.add_init_script((REPO / "tools" / "demo_video" / "clock.js").read_text(encoding="utf-8"))
        try:
            return work(context, sources)
        finally:
            browser.close()


def capture(only: Optional[List[str]] = None, stretch: Optional[float] = None) -> List[Dict[str, Any]]:
    lengths, shots = kmake.durations(), plan(stretch)
    (BUILD / "shots").mkdir(parents=True, exist_ok=True)
    timeline_path = BUILD / "timeline.json"
    known = {item["name"]: item for item in json.loads(timeline_path.read_text())} if timeline_path.exists() else {}

    def work(context: Any, sources: Dict[str, Any]) -> None:
        for shot in shots:
            if only and shot["name"] not in only:
                continue
            known[shot["name"]] = record(context, shot, lengths, sources)
            print("  {:10s} {:6.2f}s  lines at {}  {} sounds".format(
                shot["name"], known[shot["name"]]["seconds"], [(e["line"], e["at"]) for e in known[shot["name"]]["lines"]],
                len(known[shot["name"]]["sfx"])), flush=True)

    with_browser(work)
    timeline = [known[shot["name"]] for shot in shots if shot["name"] in known]
    timeline_path.write_text(json.dumps(timeline, indent=1), encoding="utf-8")
    print("  {:.2f}s in {} shots".format(sum(item["seconds"] for item in timeline), len(timeline)))
    return timeline


def frames(shot_name: str, moments: List[float], extra: Optional[Dict[str, Any]] = None) -> None:
    """Save single frames of one shot (seconds into the shot) to build/frames/, without recording it."""
    lengths = kmake.durations()
    shot = next((item for item in plan() if item["name"] == shot_name), None)
    if shot is None and shot_name in cut.PIECES:
        shot = {"name": "piece_" + shot_name, **cut.PIECES[shot_name]}
    if shot is None:
        raise SystemExit("no shot or piece called {}".format(shot_name))
    with_browser(lambda context, sources: record(context, shot, lengths, {**sources, "extra": {**sources["extra"], **(extra or {})}}, stills=moments))


def fit() -> float:
    """Stretch the last card so the whole film lasts `cut.TARGET_SECONDS`, and record that card again."""
    timeline = json.loads((BUILD / "timeline.json").read_text(encoding="utf-8"))
    saved = BUILD / "fit.json"
    before = json.loads(saved.read_text(encoding="utf-8"))["stretch"] if saved.exists() else 0.0
    total = sum(item["seconds"] for item in timeline)
    if "target" in FILM and FILM["target"] is None:
        print("  the film is {:.2f}s ({}:{:04.1f}); this film has no fixed length, nothing is stretched".format(total, int(total // 60), total % 60))
        return 0.0
    stretch = round(max(0.0, before + cut.TARGET_SECONDS - total), 3)
    saved.write_text(json.dumps({"stretch": stretch}), encoding="utf-8")
    print("  the film is {:.2f}s; the last card is held {:.2f}s longer to make it {:.1f}s".format(total, stretch, cut.TARGET_SECONDS))
    if abs(stretch - before) > 1e-6:
        capture(only=[timeline[-1]["name"]], stretch=stretch)
    return stretch


# ---------------------------------------------------------------- putting it together
def spoken_lines(timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """When each line of the narration starts, in seconds from the start of the film."""
    spoken, offset = [], 0.0
    for item in timeline:
        spoken += [{"line": event["line"], "at": round(offset + event["at"], 3)} for event in item["lines"]]
        offset += item["seconds"]
    return spoken


def assemble(mute: Optional[List[str]] = None, voice: Optional[str] = None, variant: Optional[str] = None) -> Path:
    """Join the shots, synthesise the sound and write the film. A `variant` (say "no_voice") is a side copy for
    looking or listening: it goes to the build folder and leaves the film, its subtitles and its poster alone."""
    from . import sound

    lengths, words = kmake.durations(), kmake.spoken_words()
    timeline = json.loads((BUILD / "timeline.json").read_text(encoding="utf-8"))
    names = [shot["name"] for shot in plan()]
    if [item["name"] for item in timeline] != names:
        raise SystemExit("not every shot is recorded yet: run `make capture`")
    total = sum(item["seconds"] for item in timeline)
    if total > FILM.get("limit", cut.LIMIT_SECONDS):
        raise SystemExit("the video would be {:.1f}s, over the {:.1f}s this cut allows: shorten the script".format(total, FILM.get("limit", cut.LIMIT_SECONDS)))
    OUT.mkdir(parents=True, exist_ok=True)
    listing = BUILD / "shots.txt"
    listing.write_text("".join("file '{}'\n".format(BUILD / "shots" / "{}.mp4".format(name)) for name in names), encoding="utf-8")
    joined, silent = BUILD / "picture.mp4", BUILD / "picture-lean.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)])
    # The shots are recorded at a generous quality. The film is encoded once more, a little leaner: about a
    # quarter smaller in the repository, and not to be told apart (SSIM 0.995 against the joined shots).
    newest = max((BUILD / "shots" / "{}.mp4".format(name)).stat().st_mtime for name in names)
    if not silent.exists() or silent.stat().st_mtime < newest:
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined), "-an", "-c:v", "libx264", "-preset", "slow", "-crf", FILM.get("crf", "21.5"), "-pix_fmt", "yuv420p",
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", str(silent)])

    spoken = spoken_lines(timeline)
    report = sound.build(timeline, spoken, BUILD, mute=mute or [], voice_style=voice or FILM["style"])
    target = VIDEO if variant is None else ROOT / "out" / "{}_{}.mp4".format(FILM["name"], variant)
    target.parent.mkdir(parents=True, exist_ok=True)
    # the limiter's ceiling leaves room for what AAC adds between samples, as in Kristján's cut
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(report["mix"]), "-map", "0:v", "-map", "1:a",
         "-af", "alimiter=limit=0.8:level=disabled,apad,atrim=0:{:.3f}".format(total),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(target)])
    if variant is None:
        VIDEO.with_suffix(".srt").write_text(kmake.subtitles(spoken, lengths, words), encoding="utf-8")
        if FILM["poster"]:
            shot, into = FILM["poster"]
            title_at = sum(item["seconds"] for item in timeline[:names.index(shot)]) + into + cut.TITLE_LEAD
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "{:.2f}".format(title_at), "-i", str(VIDEO), "-frames:v", "1", "-q:v", "2", str(OUT / "poster.jpg")])
        (BUILD / "spoken.json").write_text(json.dumps({"total": round(total, 2), "lines": spoken, "thumps": report["thumps"]}, indent=1), encoding="utf-8")
    probe = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(target)]).stdout.strip()
    print("  {} {:.2f}s (the file says {}s), {:.1f} MB".format(target.relative_to(REPO), total, probe, target.stat().st_size / 1e6))
    for line in report["notes"]:
        print("    " + line)
    if variant is None:
        for item in spoken:
            print("    {:>6.1f}s  {}  {}".format(item["at"], item["line"], FILM["subtitles"][item["line"]][:80]))
    return target


# ---------------------------------------------------------------- the film and its voice apart
OPTIONS = [("af_heart", "clean", "the voice as it is, nothing added"), ("af_heart", "deep", "the same take, two semitones lower with more chest"),
           ("am_michael", "clean", "Michael, a lower American voice"), ("bm_george", "clean", "George, a lower British voice")]


def voices() -> Path:
    """The opening line in four voices, one after another, each saying its own number first: for choosing by ear.
    Needs Docker (Kristján's narrator image holds all three voices)."""
    import numpy as np
    import soundfile as sf

    from . import sound

    pieces = []
    for number, (name, style, what) in enumerate(OPTIONS, 1):
        folder = BUILD / "voice_options" / "{}_{}".format(number, name)
        folder.mkdir(parents=True, exist_ok=True)
        said = "Option {}. {}".format(number, cut.LINES["a1"])
        (folder / "lines.json").write_text(json.dumps([{"id": "opt", "say": said}]), encoding="utf-8")
        run(["docker", "run", "--rm", "--network", "none", "-v", "{}:/work".format(folder),
             "-v", "{}:/opt/speak.py:ro".format(REPO / "tools" / "demo_video" / "voice" / "speak.py"), kmake.IMAGE,
             "/work/lines.json", "/work", "--voice", name, "--speed", str(cut.VOICE["speed"])])
        line = sound.voice_line(folder / "opt.wav", style)
        line = line * sound.db(sound.VOICE_LUFS + 3.0 - sound.loudness(line))        # one channel at the film's loudness
        line *= min(1.0, 0.89 / float(np.max(np.abs(line))))
        pieces += [line, np.zeros(int(0.9 * sound.RATE))]
        print("  option {}: {} ({:.1f}s)".format(number, what, len(line) / sound.RATE))
    target = ROOT / "out" / "voice_options.wav"
    target.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(target), np.clip(np.concatenate(pieces), -1.0, 1.0), sound.RATE, subtype="PCM_16")
    print("  " + str(target.relative_to(REPO)))
    return target


def clip(name: str, tag: Optional[str] = None, item: Optional[Dict[str, Any]] = None) -> Path:
    """One recorded shot as a small film of its own: its picture, its sounds, no narration."""
    from . import sound

    if item is None:
        item = next((found for found in json.loads((BUILD / "timeline.json").read_text(encoding="utf-8")) if found["name"] == name), None)
    if item is None:
        raise SystemExit("no recorded shot called {}".format(name))
    report = sound.build([item], [], BUILD, mute=["voice"], into="audio-clip-" + (tag or name), whole=False)     # a folder of its own: two clips may be cut at once
    target = ROOT / "out" / "{}.mp4".format(tag or name)
    target.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(BUILD / "shots" / "{}.mp4".format(name)), "-i", str(report["mix"]), "-map", "0:v", "-map", "1:a",
         "-af", "alimiter=limit=0.8:level=disabled,apad,atrim=0:{:.3f}".format(item["seconds"]),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(target)])
    print("  {} {:.2f}s, {:.1f} MB".format(target.relative_to(REPO), item["seconds"], target.stat().st_size / 1e6))
    return target


def alt(shot_name: str, tag: str, extra: Dict[str, Any]) -> Path:
    """One shot of the film recorded again with a draft setting (say the cards as score-cards), as a clip of its own.
    The film's own recording of that shot is left alone."""
    shot = next((dict(item) for item in plan() if item["name"] == shot_name), None)
    if shot is None:
        raise SystemExit("no shot called {}".format(shot_name))
    shot["name"] = "alt_" + tag
    item = with_browser(lambda context, sources: record(context, shot, kmake.durations(), {**sources, "extra": {**sources["extra"], **extra}}))
    return clip(shot["name"], tag=tag, item=item)


def piece(name: str) -> Path:
    """Record one of this cut's draft pieces (`cut.PIECES`) and write it as a clip of its own. Pieces are not
    part of the film: each is looked at alone, and joined only once the team has picked."""
    if name not in cut.PIECES:
        raise SystemExit("no piece called {}: there are {}".format(name, ", ".join(sorted(cut.PIECES))))
    shot = {"name": "piece_" + name, **cut.PIECES[name]}
    (BUILD / "shots").mkdir(parents=True, exist_ok=True)
    item = with_browser(lambda context, sources: record(context, shot, {}, sources))
    (BUILD / "pieces").mkdir(parents=True, exist_ok=True)
    (BUILD / "pieces" / "{}.json".format(name)).write_text(json.dumps(item, indent=1), encoding="utf-8")
    return clip(shot["name"], tag=name, item=item)


def split() -> List[Path]:
    """The film without its narration, and the narration without the film, so each can be judged alone."""
    import numpy as np
    import soundfile as sf

    from . import sound

    made = [assemble(mute=["voice"], variant="no_voice")]
    timeline = json.loads((BUILD / "timeline.json").read_text(encoding="utf-8"))
    total = sum(item["seconds"] for item in timeline)
    for style in sound.VOICE_STYLES:
        _, alone = sound.voice_bus(spoken_lines(timeline), BUILD / "voice", total, style)
        alone = alone * math.sqrt(2.0)                                               # one channel as loud as the film's two
        alone *= min(1.0, 0.89 / float(np.max(np.abs(alone))))                       # and never clipped: the film has a limiter, this file has none
        target = ROOT / "out" / "{}_voice_{}.wav".format(FILM["name"], style)
        sf.write(str(target), np.clip(alone, -1.0, 1.0), sound.RATE, subtype="PCM_16")
        print("  {} {:.1f}s, {:.1f} LUFS, peak {:.1f} dBFS".format(target.relative_to(REPO), total, sound.loudness(alone),
                                                                    20 * math.log10(float(np.max(np.abs(alone))) + 1e-12)))
        made.append(target)
    return made


def kit() -> Path:
    """The narration kit, for a teammate who records the narration himself: the film without its narrator under a
    name that says so, every line with when it starts and how long it may be, what the picture does on which words,
    the lines as subtitles, and the placeholder narrator alone as a guide for pace. The folder's README and its
    helper (`lay_narration.py`) are kept by hand; this writes the rest from the film as it was last built."""
    import soundfile as sf

    from . import sound

    folder = OUT / "narration-kit"
    folder.mkdir(parents=True, exist_ok=True)
    timeline, lengths = json.loads((BUILD / "timeline.json").read_text(encoding="utf-8")), kmake.durations()
    shots = {shot["name"]: shot for shot in plan()}
    if [item["name"] for item in timeline] != list(shots):
        raise SystemExit("not every shot is recorded yet: run `make capture`")
    starts, total = {}, 0.0
    for item in timeline:
        starts[item["name"]], total = total, total + item["seconds"]
    spoken = spoken_lines(timeline)

    # what the picture does, and when, in seconds from the start of the film
    moments: List[Dict[str, Any]] = []
    for name, sync in getattr(cut, "SYNC2", {}).items():
        shot, begin = shots[name], starts[name]
        if "parts" in sync:
            given = shot["addon_settings"]
            moments.append({"at": begin + given["orbit"], "what": sync["parts"]["dive"]})
            moments.append({"at": begin + given["orbit"] + given["dive"] + given["land"] + given["rise"] + 0.1, "what": sync["parts"]["title"]})
        if "cues" in sync:
            at, frames_before = None, 0.0
            for beat in shot["beats"]:
                if beat.get("cues"):
                    for cue, what in zip(beat["cues"], sync["cues"]):
                        if what:
                            moments.append({"at": begin + frames_before + cue, "what": what})
        if "events" in sync:
            seen = json.loads((BUILD / "tele" / "{}.json".format(name)).read_text(encoding="utf-8"))
            for kind, what in sync["events"].items():
                frame = next((number for number, state in enumerate(seen) for event in state["events"]
                              if (event["k"] == kind and event.get("who", "on") == "on") or (kind == "gold" and event["k"] == "card" and event.get("tone") == "gold")
                              or (kind == "card" and event["k"] == "card")), None)
                if frame is None:
                    raise SystemExit("{}: the picture no longer shows {!r}: look at SYNC2 in tools/manh_demo/cut.py".format(name, kind))
                moments.append({"at": begin + frame / FPS, "what": what})
    moments.sort(key=lambda moment: moment["at"])

    lines = []
    for number, item in enumerate(spoken):
        following = spoken[number + 1]["at"] if number + 1 < len(spoken) else total - 0.3
        shot = next(name for name in reversed(list(starts)) if starts[name] <= item["at"] + 1e-6)
        lines.append({"id": item["line"], "start": round(item["at"], 2), "placeholder_seconds": round(lengths[item["line"]], 2),
                      "must_end_by": round(following - 0.2, 2), "shot": shot, "text": FILM["subtitles"][item["line"]],
                      "sync": [{"at": round(moment["at"], 2), "what": moment["what"]} for moment in moments if item["at"] - 0.3 <= moment["at"] < following - 0.3]})
    film = "{}_no_narrator.mp4".format(FILM["name"])
    (folder / "timing.json").write_text(json.dumps({"film": film, "seconds": round(total, 2), "fps": FPS, "lines": lines}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    clock = lambda seconds: "{}:{:04.1f}".format(int(seconds // 60), seconds % 60)                      # noqa: E731
    text = ["# The narration, line by line", "",
            "The draft narration of `{}` ({:.1f} s), written from the film as it was last built (`make kit --film {}`). ".format(film, total, [n for n, f in FILMS.items() if f is FILM][0])
            + "Times are minutes:seconds from the first frame. A line may start a little later than its time, never earlier than the line before it ends; "
              "it has to be over by **must end by**, where the next line starts. The placeholder's length is what the synthetic voice needed at a brisk, clear pace.", "",
            "| Line | Starts | Must end by | Placeholder | Say |", "|---|---|---|---|---|"]
    for line in lines:
        text.append("| `{}` | {} | {} | {:.1f} s | {} |".format(line["id"], clock(line["start"]), clock(line["must_end_by"]), line["placeholder_seconds"], line["text"]))
    text += ["", "## What the picture does on which words", "",
             "The picture was recorded to the placeholder's timing. These are the moments worth landing; half a second early or late is fine, and nothing breaks if one is missed.", "",
             "| At | During | The picture |", "|---|---|---|"]
    for line in lines:
        for moment in line["sync"]:
            text.append("| {} | `{}` | {} |".format(clock(moment["at"]), line["id"], moment["what"]))
    text += ["", "## Reading copy", ""] + ["{}".format(line["text"]) + "\n" for line in lines]
    (folder / "narration.md").write_text("\n".join(text).rstrip("\n") + "\n", encoding="utf-8")

    shutil.copyfile(assemble(mute=["voice"], variant="no_voice"), folder / film)
    shutil.copyfile(VIDEO.with_suffix(".srt"), folder / "narration.srt")
    _, alone = sound.voice_bus(spoken, BUILD / "voice", total, FILM["style"])
    guide = BUILD / "guide_voice.wav"
    sf.write(str(guide), alone * min(1.0, 0.7 / float(abs(alone).max())), sound.RATE, subtype="PCM_16")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(guide), "-ac", "1", "-c:a", "aac", "-b:a", "96k", str(folder / "guide_voice.m4a")])
    for path in sorted(folder.iterdir()):
        print("  {} ({:.1f} MB)".format(path.relative_to(REPO), path.stat().st_size / 1e6))
    return folder


def levels() -> None:
    """The finished sound track's loudness, as ffmpeg's EBU R128 meter reads it."""
    done = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(VIDEO), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                          capture_output=True, text=True)
    tail = done.stderr[done.stderr.rfind("Summary:"):]
    print("  " + " · ".join(line.strip() for line in tail.splitlines() if any(key in line for key in ("I:", "LRA:", "Peak:"))))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=["voice", "capture", "fit", "assemble", "all", "check", "frames", "levels", "split", "voices", "clip", "piece", "alt", "kit"])
    parser.add_argument("--only", default=None, help="capture: comma-separated shot names")
    parser.add_argument("--shot", default=None, help="frames, clip: the shot")
    parser.add_argument("--tag", default=None, help="clip: the name of the file written to build/out/")
    parser.add_argument("--name", default=None, help="piece: which draft piece to record (see cut.PIECES)")
    parser.add_argument("--cards", default=None, help="alt, frames: 'score' draws the story cards as score-cards")
    parser.add_argument("--at", default="1", help="frames: comma-separated seconds into the shot")
    parser.add_argument("--mute", default="", help="assemble: comma-separated layers to leave out: voice, rover, charts, music, wind, duck")
    parser.add_argument("--voice", default=None, help="assemble: the narrator's style, clean or deep (default: the film's own)")
    parser.add_argument("--film", type=int, default=1, choices=sorted(FILMS), help="which film: 1 the cinematic cut, 2 the second draft")
    args = parser.parse_args(argv)
    use(args.film)
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is needed and was not found")
    if args.step in ("voice", "all"):
        print("narration:")
        lengths = kmake.voice()
        print("  {:.1f}s of speech in {} lines".format(sum(lengths[key] for key in FILM["lines"]), len(FILM["lines"])))
    if args.step == "frames":
        frames(args.shot, [float(value) for value in args.at.split(",")], {"cards": args.cards} if args.cards else {})
    if args.step in ("capture", "all"):
        print("picture:")
        capture(args.only.split(",") if args.only else None)
    if args.step in ("fit", "all"):
        print("length:")
        fit()
    if args.step in ("assemble", "all"):
        print("video:")
        assemble([name for name in args.mute.split(",") if name], voice=args.voice)
        levels()
    if args.step == "alt":
        print("draft of a shot:")
        alt(args.shot, args.tag or args.shot + "_alt", {"cards": args.cards} if args.cards else {})
    if args.step == "piece":
        print("piece:")
        for name in args.name.split(","):
            piece(name)
    if args.step == "clip":
        print("clip:")
        clip(args.shot, args.tag)
    if args.step == "split":
        print("apart:")
        split()
    if args.step == "kit":
        print("narration kit:")
        kit()
    if args.step == "voices":
        print("voices:")
        voices()
    if args.step == "levels":
        levels()
    if args.step == "check":
        print("by ear:")
        kmake.check()
    return 0


if __name__ == "__main__":
    sys.exit(main())
