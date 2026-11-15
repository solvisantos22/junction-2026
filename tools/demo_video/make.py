#!/usr/bin/env python3
"""Build the Lightlag Traverse demo video: narration, picture, and the two put together.

    uv run --no-project --python 3.12 --with playwright python -m tools.demo_video.make all
    ... make voice       # speak the lines of storyboard.py (Docker, no network)
    ... make capture     # record every shot frame by frame   [--only cold,task]
    ... make assemble    # join the shots, lay the narration under them, write the subtitles
    ... make check       # a speech recogniser writes down the finished sound track; compare with the script

Needs Docker with the narrator image (`docker build -t lightlag-narrator tools/demo_video/voice`),
Google Chrome and ffmpeg; `check` needs the listener image (see `voice/Dockerfile.listen`).
The picture is the real demo page (`viewer/traverse-campaign.html`,
the saved campaign runs) and the scenes of `film.html`, both drawn on a virtual clock
(`clock.js`) so every frame is exact however long it takes to draw. Intermediate files go to
`tools/demo_video/build/` (not committed); the video and its subtitles to `docs/demo-video/`.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import data as film_data

# The script to build: storyboard.py (the second cut) unless LIGHTLAG_STORYBOARD names another module
# of this package, for example storyboard3 (the third cut).
storyboard = importlib.import_module("{}.{}".format(__package__, os.environ.get("LIGHTLAG_STORYBOARD", "storyboard")))

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BUILD = HERE / "build"
OUT = REPO / "docs" / "demo-video"
VIDEO = OUT / "lightlag-traverse-demo.mp4"
FPS = 30
SIZE = (1920, 1080)
FADE_IN, FADE_OUT = 0.3, 0.22           # seconds of fade from and to black around every shot
IMAGE = "lightlag-narrator"
LISTENER = "lightlag-listener"
CHROME_ARGS = ["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=metal", "--hide-scrollbars",
               "--force-color-profile=srgb", "--autoplay-policy=no-user-gesture-required"]


def run(command: List[str], **more: Any) -> subprocess.CompletedProcess:
    done = subprocess.run(command, capture_output=True, text=True, **more)
    if done.returncode != 0:
        raise SystemExit("{} failed:\n{}".format(command[0], (done.stderr or done.stdout)[-2500:]))
    return done


# ---------------------------------------------------------------- narration
def voice() -> Dict[str, float]:
    folder = BUILD / "voice"
    folder.mkdir(parents=True, exist_ok=True)
    lines = [{"id": key, "say": text} for key, text in storyboard.LINES.items()]
    (folder / "lines.json").write_text(json.dumps(lines, indent=1), encoding="utf-8")
    done = run(["docker", "run", "--rm", "--network", "none", "-v", "{}:/work".format(folder),
                "-v", "{}:/opt/speak.py:ro".format(HERE / "voice" / "speak.py"), IMAGE,
                "/work/lines.json", "/work", "--voice", storyboard.VOICE["voice"], "--speed", str(storyboard.VOICE["speed"])])
    for line in done.stdout.splitlines():
        if line[:3].strip() and not line.lstrip().startswith(("super()", "WeightNorm")):
            print("  " + line)
    return durations()


def durations() -> Dict[str, float]:
    path = BUILD / "voice" / "durations.json"
    if not path.exists():
        raise SystemExit("no narration yet: run `make voice` first")
    found = json.loads(path.read_text(encoding="utf-8"))
    missing = sorted(set(storyboard.LINES) - set(found))
    if missing:
        raise SystemExit("lines not spoken yet: {}".format(", ".join(missing)))
    return found


def spoken_words() -> Dict[str, List[Dict[str, Any]]]:
    """When each word of each line is spoken (the voice model's own timing), for cues and subtitles."""
    found = {}
    for key, text in storyboard.LINES.items():
        path = BUILD / "voice" / "{}.words.json".format(key)
        if not path.exists():
            raise SystemExit("no word timing for line {}: run `make voice` again".format(key))
        found[key] = json.loads(path.read_text(encoding="utf-8"))
        if "".join(word["w"] + (" " if word["space"] else "") for word in found[key]).strip() != text:
            raise SystemExit("the word timing of line {} is for another text: run `make voice` again".format(key))
    return found


# ---------------------------------------------------------------- picture
class Encoder:
    """One shot's frames, piped to ffmpeg as JPEGs."""

    def __init__(self, path: Path) -> None:
        self.process = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
             "-an", "-vf", "scale=in_color_matrix=bt601:in_range=pc:out_color_matrix=bt709:out_range=tv,format=yuv420p",
             "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-r", str(FPS),
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", str(path)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def add(self, jpeg: bytes) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(jpeg)

    def close(self) -> None:
        assert self.process.stdin is not None
        self.process.stdin.close()
        error = self.process.stderr.read().decode() if self.process.stderr else ""
        if self.process.wait() != 0:
            raise SystemExit("ffmpeg could not encode a shot:\n" + error[-2000:])


def record(context: Any, shot: Dict[str, Any], lengths: Dict[str, float], facts: str) -> Dict[str, Any]:
    """Record one shot. Returns its length and when, inside it, each line and sound starts."""
    page = context.new_page()
    problems: List[str] = []
    page.on("pageerror", lambda error: problems.append(str(error)[:300]))
    film = shot["page"] == "film"
    if film:
        page.add_init_script("window.FILM_DATA = {};".format(facts))
        page.goto((HERE / "film.html").as_uri() + "?scene=" + shot["scene"])
        page.wait_for_function("window.__scene !== undefined && document.fonts.status === 'loaded'", polling=50)
    else:
        page.goto((REPO / "viewer" / "traverse-campaign.html").as_uri() + "?site={}".format(shot["site"]))
        page.wait_for_function("window.LIGHTLAG_TRAVERSE_APP !== undefined", polling=50, timeout=60000)
        page.evaluate((HERE / "overlay.js").read_text(encoding="utf-8"))
        page.evaluate("window.__overlay.chapter({})".format(json.dumps(shot.get("chapter"))))
    def act(code: str) -> Any:               # run a storyboard snippet in the page, with A as the demo's controls
        return page.evaluate("() => { const A = window.LIGHTLAG_TRAVERSE_APP; " + code + " }")

    encoder = Encoder(BUILD / "shots" / "{}.mp4".format(shot["name"]))
    fade_in, fade_out = shot.get("fade_in", FADE_IN), shot.get("fade_out", FADE_OUT)
    frame, events, sounds, talking = 0, [], [], 0.0     # talking: when, in the shot, the last line so far ends
    beats = shot["beats"]
    for number, beat in enumerate(beats):
        last, start = number == len(beats) - 1, frame
        spoken = lengths[beat["vo"]] if beat.get("vo") else 0.0
        if beat.get("vo"):
            talking = max(talking, start / FPS + beat.get("vo_at", 0.0) + spoken)
        # a beat lasts its minimum and, unless its line runs on over later beats, its line and the pause after;
        # the last beat also waits for every line still being spoken
        held = (beat.get("vo_at", 0.0) + spoken + beat.get("pad", 0.0)) if beat.get("vo") and not beat.get("over") else 0.0
        if last:
            held = max(held, talking - start / FPS + beat.get("pad", 0.0))
        need = math.ceil(max(beat.get("min", 0.0), held) * FPS)
        if last and beat.get("until"):
            raise SystemExit("{}: the last beat of a shot needs a fixed length".format(shot["name"]))
        if film:
            page.evaluate("([d, cues]) => { window.__scene.duration = d; window.__scene.cues = cues; }",
                          [need / FPS, beat.get("cues", [])])
        else:
            page.evaluate("cues => { window.__overlay.cues = cues; }", beat.get("overlay", []))
            if beat.get("js"):
                act(beat["js"])
        if beat.get("vo"):
            events.append({"line": beat["vo"], "at": round(frame / FPS + beat.get("vo_at", 0.0), 3)})
        if "thump" in beat:
            sounds.append(round(frame / FPS + beat["thump"], 3))
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
                page.evaluate("([ts, black, shot]) => { window.__film.step(1000 / %d); window.__overlay.draw(ts, black, shot); }" % FPS,
                              [local, black, frame / FPS])
            encoder.add(page.screenshot(type="jpeg", quality=95))
            frame += 1
            if frame - start >= need and (not beat.get("until") or act("return " + beat["until"] + ";")):
                break
            if frame - start > need + 40 * FPS:
                raise SystemExit("{}: beat {} never ended".format(shot["name"], number + 1))
        if beat.get("then"):
            act(beat["then"])
    encoder.close()
    page.close()
    if problems:
        raise SystemExit("{}: the page reported errors: {}".format(shot["name"], problems[:3]))
    return {"name": shot["name"], "frames": frame, "seconds": round(frame / FPS, 3), "lines": events, "thumps": sounds}


def capture(only: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    from playwright.sync_api import sync_playwright

    lengths = durations()
    plan = storyboard.shots(lengths, spoken_words())
    (BUILD / "shots").mkdir(parents=True, exist_ok=True)
    more = storyboard.facts() if hasattr(storyboard, "facts") else {}          # what a later cut's slides add
    facts = json.dumps({**film_data.build(), **more, "live_url": storyboard.LIVE_URL}, separators=(",", ":"))
    timeline_path = BUILD / "timeline.json"
    known = {item["name"]: item for item in json.loads(timeline_path.read_text())} if timeline_path.exists() else {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=CHROME_ARGS)
        context = browser.new_context(viewport={"width": SIZE[0], "height": SIZE[1]}, device_scale_factor=1)
        context.add_init_script((HERE / "clock.js").read_text(encoding="utf-8"))
        for shot in plan:
            if only and shot["name"] not in only:
                continue
            known[shot["name"]] = record(context, shot, lengths, facts)
            print("  {:10s} {:6.2f}s  lines at {}".format(shot["name"], known[shot["name"]]["seconds"],
                                                       [(e["line"], e["at"]) for e in known[shot["name"]]["lines"]]), flush=True)
        browser.close()
    timeline = [known[shot["name"]] for shot in plan if shot["name"] in known]
    timeline_path.write_text(json.dumps(timeline, indent=1), encoding="utf-8")
    return timeline


# ---------------------------------------------------------------- putting it together
def stamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    return "{:02d}:{:02d}:{:02d},{:03d}".format(ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


CLAUSE_END = ".?!:;,"


def clause_times(words: List[Dict[str, Any]]) -> List[List[float]]:
    """[start, end] of each clause of a spoken line: the words up to each comma or full stop."""
    found: List[List[float]] = []
    open_clause: Optional[List[float]] = None
    for word in words:
        if word["w"] in CLAUSE_END:
            if open_clause:
                found.append(open_clause)
            open_clause = None
        elif word["t0"] is not None:
            open_clause = [open_clause[0] if open_clause else word["t0"], word["t1"] if word["t1"] is not None else word["t0"]]
    if open_clause:
        found.append(open_clause)
    return found


def subtitles(spoken: List[Dict[str, Any]], lengths: Dict[str, float], words: Dict[str, List[Dict[str, Any]]]) -> str:
    """SubRip subtitles. A line is cut at its sentence ends, a long sentence at a comma; each piece is
    shown from its first word to its last, as the voice model timed them."""
    import re

    blocks = []
    for item in spoken:
        text, start = storyboard.SUBTITLES[item["line"]], item["at"]
        clauses = re.split(r"(?<=[.?!:;,])\s+", text)
        times = clause_times(words[item["line"]])
        if len(times) != len(clauses):              # the subtitle text is punctuated differently: share the time out by length
            total, done, times = sum(len(clause) for clause in clauses), 0, []
            for clause in clauses:
                times.append([lengths[item["line"]] * done / total, lengths[item["line"]] * (done + len(clause)) / total])
                done += len(clause)
        piece, begun, ended = "", 0.0, 0.0
        for clause, (a, b) in zip(clauses, times):
            # the next clause would make the piece too long to read; a few words alone are not left as a piece
            if piece and len(piece) + 1 + len(clause) > (96 if min(len(piece), len(clause)) < 20 else 64):
                blocks.append([start + begun, start + ended, piece])
                piece = ""
            if not piece:
                begun = a
            piece, ended = (piece + " " + clause).strip(), b
            if clause[-1] in ".?!":                           # a sentence ends here
                blocks.append([start + begun, start + ended, piece])
                piece = ""
        if piece:
            blocks.append([start + begun, start + ended, piece])
    for block, following in zip(blocks, blocks[1:] + [None]):       # stay up a moment after the last word, never into the next piece
        block[1] = min(block[1] + 0.35, following[0] - 0.04) if following else block[1] + 0.35
    return "".join("{}\n{} --> {}\n{}\n\n".format(i, stamp(a), stamp(b), text) for i, (a, b, text) in enumerate(blocks, 1))


def assemble(bed: bool = True) -> Path:
    lengths, words = durations(), spoken_words()
    timeline = json.loads((BUILD / "timeline.json").read_text(encoding="utf-8"))
    names = [shot["name"] for shot in storyboard.shots(lengths, words)]
    if [item["name"] for item in timeline] != names:
        raise SystemExit("not every shot is recorded yet: run `make capture`")
    OUT.mkdir(parents=True, exist_ok=True)
    listing = BUILD / "shots.txt"
    listing.write_text("".join("file '{}'\n".format(BUILD / "shots" / "{}.mp4".format(name)) for name in names), encoding="utf-8")
    silent = BUILD / "picture.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(silent)])
    spoken, thumps, offset = [], [], 0.0
    for item in timeline:
        spoken += [{"line": event["line"], "at": round(offset + event["at"], 3)} for event in item["lines"]]
        thumps += [round(offset + at, 3) for at in item["thumps"]]
        offset += item["seconds"]
    total = offset
    if total > storyboard.LIMIT_SECONDS:
        raise SystemExit("the video would be {:.1f}s, over the {:.0f}s limit: shorten the script".format(total, storyboard.LIMIT_SECONDS))
    inputs, graph, voices = ["-i", str(silent)], [], []
    for index, item in enumerate(spoken, 1):
        inputs += ["-i", str(BUILD / "voice" / "{}.wav".format(item["line"]))]
        graph.append("[{}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={}:all=1[v{}]".format(index, int(item["at"] * 1000), index))
        voices.append("[v{}]".format(index))
    graph.append("{}amix=inputs={}:normalize=0:dropout_transition=0,highpass=f=65,"
                 "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[voice]".format("".join(voices), len(voices)))
    layers = ["[voice]"]
    if bed:
        # a low wind under everything, and a soft thud where a battery runs flat
        graph.append("anoisesrc=d={:.2f}:c=brown:r=48000:a=0.5:seed=2027,lowpass=f=240,highpass=f=40,volume=-30dB,"
                     "aformat=channel_layouts=stereo,afade=t=in:d=1.2,afade=t=out:st={:.2f}:d=1.6[bed]".format(total, total - 1.7))
        layers.append("[bed]")
        for number, at in enumerate(thumps, 1):
            # a low note that small speakers cannot play, its octave, which they can, and a short dull knock
            graph.append("sine=f=55:d=0.9:r=48000,afade=t=out:st=0.02:d=0.85,volume=-9dB[ta{0}];"
                         "sine=f=110:d=0.5:r=48000,afade=t=out:st=0.01:d=0.45,volume=-15dB[tb{0}];"
                         "anoisesrc=d=0.25:c=brown:r=48000:a=0.6:seed=409,lowpass=f=420,afade=t=out:st=0:d=0.22,volume=-13dB[tc{0}];"
                         "[ta{0}][tb{0}][tc{0}]amix=inputs=3:normalize=0:dropout_transition=0,aformat=channel_layouts=stereo,"
                         "adelay={1}:all=1[t{0}]".format(number, int(at * 1000)))
            layers.append("[t{}]".format(number))
    # the limiter's ceiling leaves room for what AAC adds between samples: the finished track peaks near -1.5 dBTP
    graph.append("{}amix=inputs={}:normalize=0:dropout_transition=0,alimiter=limit=0.8:level=disabled,apad,atrim=0:{:.3f}[out]".format(
        "".join(layers), len(layers), total))
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(graph), "-map", "0:v", "-map", "[out]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(VIDEO)])
    VIDEO.with_suffix(".srt").write_text(subtitles(spoken, lengths, words), encoding="utf-8")
    # a still for the submission page: the title over the map, just after that shot fades in
    shot, into = storyboard.POSTER
    title_at = sum(item["seconds"] for item in timeline[:names.index(shot)]) + into
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "{:.2f}".format(title_at), "-i", str(VIDEO), "-frames:v", "1", "-q:v", "2", str(OUT / "poster.jpg")])
    (BUILD / "spoken.json").write_text(json.dumps({"total": round(total, 2), "lines": spoken, "thumps": thumps}, indent=1), encoding="utf-8")
    print("  {} {:.1f}s, {:.1f} MB".format(VIDEO.relative_to(REPO), total, VIDEO.stat().st_size / 1e6))
    for item in spoken:
        print("    {:>6.1f}s  {}  {}".format(item["at"], item["line"], storyboard.SUBTITLES[item["line"]][:80]))
    return VIDEO


# ---------------------------------------------------------------- checking the sound by ear, as far as a script can
SMALL = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()


def number_words(n: int) -> List[str]:
    if n < 20:
        return [SMALL[n]]
    if n < 100:
        return [TENS[n // 10 - 2]] + ([SMALL[n % 10]] if n % 10 else [])
    if n < 1000:
        return [SMALL[n // 100], "hundred"] + (number_words(n % 100) if n % 100 else [])
    return [word for digit in str(n) for word in number_words(int(digit))]


def plain_words(text: str) -> List[str]:
    """A sentence as bare lower-case words, figures spelled the way the narrator says them."""
    import re

    words: List[str] = []
    for token in re.findall(r"\d+(?:\.\d+)?%?|[a-z']+", text.lower().replace("’", "'")):
        if token[0].isdigit():
            percent, token = token.endswith("%"), token.rstrip("%")
            whole, _, fraction = token.partition(".")
            words += number_words(int(whole))
            if fraction:
                words += ["point"] + [SMALL[int(digit)] for digit in fraction]
            if percent:
                words.append("percent")
        else:
            words.append(token.strip("'"))
    return [word for word in words if word]


def check() -> None:
    """Have a speech recogniser, which has not seen the script, write down the finished video's sound track,
    and compare: which words it heard differently, and how far each line starts from where it was laid."""
    import difflib

    if not VIDEO.exists() or not (BUILD / "spoken.json").exists():
        raise SystemExit("no finished video yet: run `make assemble` first")
    folder = BUILD / "check"
    folder.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(VIDEO), "-vn", "-ac", "1", "-ar", "16000", str(folder / "sound.wav")])
    run(["docker", "run", "--rm", "--network", "none", "-v", "{}:/work".format(folder),
         "-v", "{}:/opt/listen.py:ro".format(HERE / "voice" / "listen.py"), LISTENER, "/work/sound.wav", "/work/heard.json"])
    heard = json.loads((folder / "heard.json").read_text(encoding="utf-8"))
    spoken = json.loads((BUILD / "spoken.json").read_text(encoding="utf-8"))
    said, starts = [], []                               # the script as bare words, and where each line's first word is
    for item in spoken["lines"]:
        starts.append((len(said), item))
        said += plain_words(storyboard.LINES[item["line"]])
    tokens: List[List[Any]] = []                        # the recogniser writes 0.48 as "0" and ".48", 9% as "9" and "%"
    for word in heard["words"]:
        if tokens and word["w"][:1] in ".%" and tokens[-1][0][-1:].isdigit():
            tokens[-1][0] += word["w"]
        else:
            tokens.append([word["w"], word["t0"]])
    got, when = [], []
    for token, t0 in tokens:
        for piece in plain_words(token):
            got.append(piece)
            when.append(t0)
    matcher = difflib.SequenceMatcher(a=said, b=got, autojunk=False)
    same = sum(block.size for block in matcher.get_matching_blocks())
    print("  heard {} of the script's {} words as written ({:.1f}%)".format(same, len(said), 100.0 * same / len(said)))
    for tag, a0, a1, b0, b1 in matcher.get_opcodes():
        if tag != "equal":
            print("    script: {!r:40}  heard: {!r}".format(" ".join(said[a0:a1]), " ".join(got[b0:b1])))
    lookup = {}
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            lookup[block.a + k] = when[block.b + k]
    words = spoken_words()
    for index, item in starts:
        first = next((word["t0"] for word in words[item["line"]] if word["t0"] is not None and word["w"] not in CLAUSE_END), 0.0)
        if index in lookup:
            print("    {}  laid at {:6.2f}s, heard at {:6.2f}s".format(item["line"], item["at"] + first, lookup[index]))
        else:
            print("    {}  laid at {:6.2f}s, its first word was not recognised".format(item["line"], item["at"] + first))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=["voice", "capture", "assemble", "all", "check"])
    parser.add_argument("--only", default=None, help="capture: comma-separated shot names")
    parser.add_argument("--no-bed", action="store_true", help="assemble: narration only, no wind and no thuds")
    args = parser.parse_args(argv)
    for tool in ("ffmpeg", "docker"):
        if not shutil.which(tool):
            raise SystemExit(tool + " is needed and was not found")
    if args.step in ("voice", "all"):
        print("narration:")
        lengths = voice()
        print("  {:.1f}s of speech in {} lines".format(sum(lengths[key] for key in storyboard.LINES), len(storyboard.LINES)))
    if args.step in ("capture", "all"):
        print("picture:")
        capture(args.only.split(",") if args.only else None)
    if args.step in ("assemble", "all"):
        print("video:")
        assemble(bed=not args.no_bed)
    if args.step == "check":
        print("by ear:")
        check()
    return 0


if __name__ == "__main__":
    sys.exit(main())
