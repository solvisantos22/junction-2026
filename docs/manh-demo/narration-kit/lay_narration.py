#!/usr/bin/env python3
"""Put your own narration on the film that has no narrator.

    python3 lay_narration.py splice reading.wav      # ONE read-through of the script, a clear pause after every line:
                                                     # it is cut into the lines and each line is laid where it belongs
    python3 lay_narration.py lines recordings/       # one recording per line: n1.wav, n2.wav, ... (ids in narration.md)
    python3 lay_narration.py one take.wav            # a take recorded while the film was playing, started on its first frame

Writes manh_demo_2_narrated.mp4 beside this file (or --out). The picture is copied untouched. The voice is cleaned
and given a broadcast sound (see README.md, "The radio voice"), brought to the film's loudness (-16 LUFS) and mixed
over the film's own sound. Needs ffmpeg and ffprobe on the PATH and nothing else. Recordings may be wav, m4a, mp3,
flac, aac or ogg.

  the voice
    --raw               leave the voice as it was recorded: no cleaning, no tone shaping (loudness is still matched)
    --deeper 1          lower the voice by this many semitones (0 to 2 stays natural; default 0)
    --voice-gain 2      make the voice this many dB louder (minus: quieter) after it is levelled

  splice
    --pause 1.0         the shortest silence, in seconds, that separates two lines (default: worked out from the reading)
    --drop 4,9          throw away these spoken blocks (numbered as the tool lists them): a line you said twice
    --remove 66.6-69.6  throw away these seconds of the reading first: a false start, a cough (repeatable with commas)
    --cuts 7.2,15.0     cut the reading at these seconds instead of looking for pauses (one fewer than there are lines)
    --keep folder/      also save the cut lines as n1.wav, n2.wav, ...: listen, re-record one, then use `lines`

  fitting (splice and lines)
    --breath 0.35       a line that is too long for its place first has the pauses inside it cut down to this many seconds
    --max-speed 1.12    ... and is then sped up by at most this much, pitch unchanged
    --shift n8=0.2      start a line this many seconds later than its time (repeatable)

  one
    --offset 0.35       your take starts this many seconds after the film's first frame (may be negative)

  --dry                 say what would be done and stop before writing the film
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from array import array
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
KINDS = (".wav", ".m4a", ".mp3", ".flac", ".aac", ".ogg")
STEREO = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
FRAME = 0.02                    # seconds: a recording's loudness is measured in steps of this
LEAD, TAIL = 0.30, 0.35         # seconds of the room kept before and after a line's speech, so a soft first word is not cut
GAP = 0.15                      # the least silence between the end of one line's speech and the start of the next
WORKING_LEVEL = -18.0           # dB: every recording is brought to this before it is cleaned, whatever level it was recorded at


def run(command: List[str]) -> subprocess.CompletedProcess:
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        sys.stderr.write(done.stderr[-3000:])
        raise SystemExit("this command failed: " + " ".join(command[:6]) + " ...")
    return done


def seconds_of(path: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)]).stdout.strip())


def filters() -> set:
    """The audio filters this ffmpeg has (an older or a minimal build lacks some of the cleaning ones)."""
    listing = run(["ffmpeg", "-hide_banner", "-filters"]).stdout
    return {parts[1] for parts in (line.split() for line in listing.splitlines()) if len(parts) > 2}


def voice_chain(have: set, raw: bool, deeper: float, gain: float) -> Tuple[str, List[str]]:
    """The filters the whole voice goes through once the lines are in place, and what had to be left out. The voice
    arrives at about WORKING_LEVEL, so the levels below mean the same for a quiet recording and a loud one."""
    skipped, chain = [], []

    def use(name: str, text: str) -> None:
        (chain if name in have else skipped).append(text if name in have else name)

    if deeper:
        ratio = 2.0 ** (-deeper / 12.0)
        if "rubberband" in have:
            chain.append("rubberband=pitch={:.5f}".format(ratio))
        else:                                 # the same without that library: slow the sound down, then put its speed back
            chain.append("asetrate=48000*{:.5f},aresample=48000,atempo={:.5f}".format(ratio, 1.0 / ratio))
    if not raw:
        chain.append("highpass=f=75")                                                    # rumble, desk bumps, pops
        use("afftdn", "afftdn=nr=10:nf=-50:tn=1")                                        # steady room noise: fan, hiss
        use("agate", "agate=threshold=0.004:ratio=2:range=0.25:attack=3:release=250")    # the room and the breaths between phrases, 12 dB down
        use("deesser", "deesser=i=0.35:m=0.5:f=0.5:s=o")                                 # hard S sounds
        chain += ["equalizer=f=110:t=q:w=0.9:g=3",                                       # chest: the "radio" depth
                  "equalizer=f=320:t=q:w=1.2:g=-2.5",                                    # the boxy sound of a small room
                  "equalizer=f=4200:t=q:w=1.0:g=3",                                      # presence: consonants come forward
                  "highshelf=f=9500:g=2"]                                                # air
        use("acompressor", "acompressor=threshold=0.09:ratio=3.5:attack=6:release=90:makeup=2.5")   # every word at one level
    chain.append("loudnorm=I=-16:TP=-2:LRA=9")
    if gain:
        chain.append("volume={}dB".format(gain))
    chain.append(STEREO)
    return ",".join(chain), skipped


def hear(path: Path, work: Path, sure: bool = True) -> Tuple[List[Tuple[float, float]], float, float, float]:
    """Every stretch of a recording without speech, as (start, end) in seconds; the room's level and the voice's
    (dB); and the recording's length. The line between room and voice is set from the recording itself, a third of
    the way from its quietest tenth to its loudest tenth, so a quiet voice or a room with a fan needs no setting.
    A bump shorter than an eighth of a second is not speech; a gap shorter than three tenths is not a pause."""
    raw = work / "levels.raw"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "8000", "-f", "s16le", str(raw)])
    samples = array("h")
    samples.frombytes(raw.read_bytes()[:(raw.stat().st_size // 2) * 2])
    if sys.byteorder == "big":
        samples.byteswap()
    step = int(8000 * FRAME)
    levels = [10.0 * math.log10(sum(v * v for v in samples[i:i + step]) / step / 32768.0 ** 2 + 1e-12) for i in range(0, len(samples) - step + 1, step)]
    length = len(samples) / 8000.0
    if len(levels) < 15:
        raise SystemExit("{} is shorter than a third of a second".format(path.name))
    ordered = sorted(levels)
    room, voice = ordered[len(ordered) // 10], ordered[len(ordered) * 9 // 10]
    if voice - room < 12.0:
        if sure:
            raise SystemExit("the voice is hardly louder than the room ({:.0f} dB against {:.0f} dB): record closer to the microphone, somewhere quieter".format(voice, room))
        return [], room, voice, length             # a clip cut tight to its words has no room in it to hear
    line = room + max(6.0, 0.35 * (voice - room))
    loud = [level > line for level in levels]

    def runs(flags: List[bool]) -> List[List[int]]:            # [is it loud, first frame, one past the last]
        out: List[List[int]] = []
        for number, flag in enumerate(flags):
            if out and out[-1][0] == flag:
                out[-1][2] = number + 1
            else:
                out.append([flag, number, number + 1])
        return out

    for flag, a, b in runs(loud):                               # a click or a bump in a pause is not speech
        if flag and (b - a) * FRAME < 0.125:
            loud[a:b] = [False] * (b - a)
    # a soft first syllable ("We", "A", "Its") or a fading last one sits under that line: speech already found is
    # grown outwards, by up to half a second, for as long as the level stays clearly above the room
    soft, reach = room + max(4.0, 0.15 * (voice - room)), int(0.5 / FRAME)
    for flag, a, b in runs(loud):
        if not flag:
            continue
        for step, edge in ((-1, a - 1), (1, b)):
            frame, grown = edge, 0
            while 0 <= frame < len(levels) and not loud[frame] and levels[frame] > soft and grown < reach:
                loud[frame] = True
                frame, grown = frame + step, grown + 1
    return [(a * FRAME, b * FRAME) for flag, a, b in runs(loud) if not flag and (b - a) * FRAME >= 0.3], room, voice, length


def spoken_blocks(quiet: List[Tuple[float, float]], length: float, wanted: int, pause: Optional[float]) -> Tuple[List[Tuple[float, float]], float]:
    """Where the lines are in a read-through: (start, end) of every block of speech between two long pauses, and
    how long a pause had to be. The pauses between lines are told from the short ones inside a line by their
    length: unless --pause says otherwise, a pause counts when it is at least half as long as the typical one of
    the `wanted - 1` longest."""
    inner = sorted((b - a for a, b in quiet if a > 0.05 and b < length - 0.05), reverse=True)
    if len(inner) < wanted - 1 and not pause:
        raise SystemExit("only {} pauses were found in the reading and the script has {} lines: leave about two seconds of silence "
                         "after every line, or give the cut times with --cuts".format(len(inner), wanted))
    top = sorted(inner[:wanted - 1])
    limit = pause if pause else max(0.45, 0.5 * top[len(top) // 2])
    cuts = [(a, b) for a, b in quiet if b - a >= limit or a <= 0.05 or b >= length - 0.05]
    edges = [0.0] + [t for pair in cuts for t in pair] + [length]
    return [(a, b) for a, b in zip(edges[0::2], edges[1::2]) if b - a > 0.25], limit


def inner_pauses(quiet: List[Tuple[float, float]], start: float, end: float) -> List[Tuple[float, float]]:
    """The pauses that lie inside a line's speech."""
    return [(a, b) for a, b in quiet if a > start + 0.05 and b < end - 0.05]


def cut_out(source: Path, target: Path, piece: Dict[str, Any], breath: Optional[float]) -> Dict[str, Any]:
    """Write a line's speech as a file of its own, with up to LEAD and TAIL of the room around it, faded at both
    ends. With `breath`, every pause inside the line that is longer is cut down to that length, from its middle."""
    lead, tail = max(0.0, min(LEAD, piece["before"])), max(0.0, min(TAIL, piece["after"]))
    parts, clock_ = [], piece["start"] - lead
    for a, b in (piece["pauses"] if breath else []):
        if b - a > breath:
            parts.append((clock_, a + breath / 2.0))
            clock_ = b - breath / 2.0
    parts.append((clock_, piece["end"] + tail))
    steps = ["[0:a]atrim=start={:.3f}:end={:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.008,afade=t=out:st={:.3f}:d=0.008[p{}]".format(
        a, b, max(0.0, b - a - 0.008), number) for number, (a, b) in enumerate(parts)]
    length = sum(b - a for a, b in parts)
    steps.append("{}concat=n={}:v=0:a=1,afade=t=in:d=0.015,afade=t=out:st={:.3f}:d=0.05[line]".format(
        "".join("[p{}]".format(number) for number in range(len(parts))), len(parts), max(0.0, length - 0.05)))
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(source), "-filter_complex", ";".join(steps), "-map", "[line]", "-ac", "1", "-ar", "48000", str(target)])
    return {"path": target, "lead": lead, "speech": length - lead - tail, "tail": tail}


def tightened(piece: Dict[str, Any], breath: float) -> float:
    """How long a line's speech is once the pauses inside it are cut down to `breath`."""
    return piece["end"] - piece["start"] - sum(max(0.0, b - a - breath) for a, b in piece["pauses"])


def clock(seconds: float) -> str:
    return "{}:{:04.1f}".format(int(seconds // 60), seconds % 60)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("\n", 2)[2])
    parser.add_argument("how", choices=["splice", "lines", "one"])
    parser.add_argument("source", type=Path)
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--deeper", type=float, default=0.0)
    parser.add_argument("--voice-gain", type=float, default=0.0)
    parser.add_argument("--pause", type=float, default=None)
    parser.add_argument("--drop", default="")
    parser.add_argument("--remove", default="")
    parser.add_argument("--cuts", default="")
    parser.add_argument("--keep", type=Path, default=None)
    parser.add_argument("--breath", type=float, default=0.35)
    parser.add_argument("--max-speed", type=float, default=1.12)
    parser.add_argument("--shift", action="append", default=[], metavar="LINE=SECONDS")
    parser.add_argument("--offset", type=float, default=0.0)
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit("{} is needed and was not found (macOS: brew install ffmpeg)".format(tool))
    if not 0.0 <= args.deeper <= 4.0:
        raise SystemExit("--deeper takes 0 to 4 semitones; above 2 a voice stops sounding like its owner")

    timing = json.loads((HERE / "timing.json").read_text(encoding="utf-8"))
    film, total, lines = HERE / timing["film"], float(timing["seconds"]), timing["lines"]
    if not film.exists():
        raise SystemExit("{} is not beside this script".format(timing["film"]))
    out = args.out or HERE / timing["film"].replace("_no_narrator", "_narrated")
    shifts = {key: float(value) for key, value in (item.split("=", 1) for item in args.shift)}
    if set(shifts) - {line["id"] for line in lines}:
        raise SystemExit("no line called {}".format(", ".join(sorted(set(shifts) - {line["id"] for line in lines}))))
    work = Path(tempfile.mkdtemp(prefix="narration-"))
    pieces: Dict[str, Dict[str, Any]] = {}       # line id -> its recording cut to its speech, and what is known about it
    placed: List[Tuple[Path, float, float, float]] = []     # (file, seconds into the film, speed, gain in dB)

    if args.how == "one":
        if not args.source.is_file():
            raise SystemExit("no such recording: {}".format(args.source))
        _, room, voice, length = hear(args.source, work, sure=False)
        print("one take of {:.1f} s, starting {:+.2f} s from the film's first frame (the film is {:.1f} s)".format(length, args.offset, total))
        placed.append((args.source, args.offset, 1.0, WORKING_LEVEL - voice))
    elif args.how == "lines":
        if not args.source.is_dir():
            raise SystemExit("`lines` takes the folder that holds n1.wav, n2.wav, ...")
        for line in lines:
            found = next((args.source / (line["id"] + kind) for kind in KINDS if (args.source / (line["id"] + kind)).exists()), None)
            if not found:
                continue
            quiet, room, voice, length = hear(found, work, sure=False)       # where the words are in the file: silence before and after is left out
            start = quiet[0][1] if quiet and quiet[0][0] <= 0.05 else 0.0
            end = quiet[-1][0] if quiet and quiet[-1][1] >= length - 0.05 else length
            pieces[line["id"]] = {"source": found, "start": start, "end": end, "before": start, "after": length - end,
                                  "pauses": inner_pauses(quiet, start, end), "gain": WORKING_LEVEL - voice}
        missing = [line["id"] for line in lines if line["id"] not in pieces]
        if not pieces:
            raise SystemExit("no recordings found in {}: name them n1.wav, n2.wav, ... as in narration.md".format(args.source))
        if missing:
            print("not recorded yet, left silent: {}".format(", ".join(missing)))
    else:
        if not args.source.is_file():
            raise SystemExit("no such recording: {}".format(args.source))
        reading = work / "reading.wav"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(args.source), "-ac", "1", "-ar", "48000", str(reading)])
        removed = sorted(tuple(float(value) for value in item.split("-", 1)) for item in args.remove.split(",") if item.strip())
        if removed:                                  # a false start or a cough goes first; every time given afterwards is still a time of the recording as it was
            whole, keep, clock_ = reading, [], 0.0
            for a, b in removed:
                keep.append((clock_, a))
                clock_ = b
            keep.append((clock_, seconds_of(whole)))
            reading = work / "reading-kept.wav"
            steps = ["[0:a]atrim=start={:.3f}:end={:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.01,afade=t=out:st={:.3f}:d=0.01[k{}]".format(
                a, b, max(0.0, b - a - 0.01), number) for number, (a, b) in enumerate(keep)]
            steps.append("{}concat=n={}:v=0:a=1[kept]".format("".join("[k{}]".format(number) for number in range(len(keep))), len(keep)))
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(whole), "-filter_complex", ";".join(steps), "-map", "[kept]", "-ac", "1", "-ar", "48000", str(reading)])
            print("removed from the reading: {}".format(", ".join("{} to {}".format(clock(a), clock(b)) for a, b in removed)))
        moved = lambda t: t - sum(min(t, b) - a for a, b in removed if t > a)             # noqa: E731  a time of the recording, in the reading that is left
        quiet, room, voice, length = hear(reading, work)
        if args.cuts:
            marks, blocks, limit = [0.0] + sorted(moved(float(value)) for value in args.cuts.split(",")) + [length], [], None
            if len(marks) - 1 != len(lines):
                raise SystemExit("--cuts needs {} times for {} lines, got {}".format(len(lines) - 1, len(lines), len(marks) - 2))
            for a, b in zip(marks, marks[1:]):              # each part, trimmed to its speech
                inside = [(max(a, s), min(b, e)) for s, e in quiet if e > a and s < b]
                start = next((e for s, e in inside if s <= a + 0.01), a)
                end = next((s for s, e in reversed(inside) if e >= b - 0.01), b)
                blocks.append((start, max(end, start + 0.2)))
        else:
            blocks, limit = spoken_blocks(quiet, length, len(lines), args.pause)
        dropped = sorted({int(value) for value in args.drop.split(",") if value.strip()})
        kept = [number for number in range(1, len(blocks) + 1) if number not in dropped]
        fits = len(kept) == len(lines)
        print("the reading is {:.1f} s (the room at {:.0f} dB, the voice at {:.0f} dB); {} spoken blocks found{}:".format(
            length, room, voice, len(blocks), "" if limit is None else " (a pause of {:.1f} s or more separates two lines)".format(limit)))
        for number, (a, b) in enumerate(blocks, 1):
            line = lines[kept.index(number)] if fits and number in kept else None
            print("  block {:>2}  {} to {}  {:5.1f} s{}".format(number, clock(a), clock(b), b - a, "   dropped" if number in dropped else
                                                            "   -> {:<4} (placeholder {:.1f} s)  {}".format(line["id"], line["placeholder_seconds"], line["text"][:44]) if line else ""))
        if not fits:
            more = len(kept) > len(lines)
            raise SystemExit(
                "\n{} blocks, but the script has {} lines, which take the placeholder {} s.\n".format(
                    len(kept), len(lines), ", ".join("{:.1f}".format(line["placeholder_seconds"]) for line in lines))
                + ("A line was said twice, or a pause inside a line was as long as the pauses between lines.\n"
                   "  said twice:    add --drop with the numbers of the blocks to throw away, for example --drop 4\n"
                   "  a long pause:  set --pause above it, for example --pause {:.1f}\n".format((limit or 0.6) + 0.4) if more else
                   "Two lines ran together, or the room is too noisy to hear the pauses.\n"
                   "  ran together:  set --pause below the gap between them, for example --pause {:.1f}, or give the cut times with --cuts\n".format(max(0.3, (limit or 0.6) - 0.3)))
                + "Compare the blocks' lengths with the placeholder's to see where it went wrong.")
        for line, number in zip(lines, kept):
            a, b = blocks[number - 1]
            before = a - (blocks[number - 2][1] if number > 1 else 0.0)                    # the pause on either side, shared with the neighbour
            after = (blocks[number][0] if number < len(blocks) else length) - b
            pieces[line["id"]] = {"source": reading, "start": a, "end": b, "before": 0.45 * before, "after": 0.45 * after,
                                  "pauses": inner_pauses(quiet, a, b), "gain": WORKING_LEVEL - voice}
        if args.keep:
            args.keep.mkdir(parents=True, exist_ok=True)
            for key, piece in pieces.items():
                cut_out(piece["source"], args.keep / "{}.wav".format(key), piece, None)
            print("the cut lines are in {} (n1.wav, ...): re-record one there and run `lines` on that folder".format(args.keep))

    if pieces:
        # every line with its first word at its time; one that is too long is sped up a little, and if that is not
        # enough the next one waits for it
        free, late = 0.0, 0
        print("placing:")
        for number, line in enumerate(lines):
            piece = pieces.get(line["id"])
            if not piece:
                continue
            begins = max(line["start"] + shifts.get(line["id"], 0.0), free)
            until = lines[number + 1]["start"] - GAP if number + 1 < len(lines) else total - 0.25
            room_, said, breath = max(0.5, until - begins), piece["end"] - piece["start"], None
            if said > room_ + 0.02 and tightened(piece, args.breath) < said - 0.05:      # too long as it is: first the pauses inside it
                breath = args.breath
            piece = {**piece, **cut_out(piece["source"], work / "{}.wav".format(line["id"]), piece, breath)}
            speed = min(args.max_speed, max(1.0, piece["speech"] / room_))
            ends = begins + piece["speech"] / speed
            note = " and ".join(part for part in ("pauses inside it cut to {:.2f} s ({:.1f} s saved)".format(breath, said - piece["speech"]) if breath else "",
                                                  "sped up {:.0f}%".format((speed - 1) * 100) if speed > 1.001 else "") if part) or "as recorded"
            if ends - until > 0.05:
                late += 1
                note += "; STILL {:.1f} s TOO LONG: the next line starts late. Say it faster, cut words, or record it again".format(ends - until)
            if begins > line["start"] + 0.4:
                note += "; starts {:.1f} s late".format(begins - line["start"])
            print("  {:<4} {} to {}  {:5.1f} s of speech, {:5.1f} s for the placeholder: {}".format(line["id"], clock(begins), clock(ends), said, line["placeholder_seconds"], note))
            placed.append((piece["path"], begins - piece["lead"] / speed, speed, piece["gain"]))
            free = ends + GAP
        if free - GAP > total:
            raise SystemExit("the narration runs {:.1f} s past the end of the film: it has to be shorter".format(free - GAP - total))
        if late:
            print("{} line(s) are too long for their place even sped up; the film is still written so you can hear it".format(late))

    have = filters()
    chain, skipped = voice_chain(have, args.raw, args.deeper, args.voice_gain)
    print("the voice: {}{}".format("as recorded, loudness matched" if args.raw else "cleaned and shaped (README.md, \"The radio voice\")",
                                   ", {:g} semitone(s) lower".format(args.deeper) if args.deeper else ""))
    if skipped:
        print("  this ffmpeg lacks {}: those steps are left out (a full build has them: brew install ffmpeg)".format(", ".join(skipped)))
    if args.dry:
        print("--dry: nothing written")
        return 0

    command, parts = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(film)], []
    for number, (path, start, speed, gain) in enumerate(placed, 1):
        command += ["-i", str(path)]
        steps = ["aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=mono", "volume={:.2f}dB".format(max(-30.0, min(30.0, gain)))]
        if start < 0:
            steps.append("atrim=start={:.3f},asetpts=PTS-STARTPTS".format(-start))
        if speed > 1.001:
            steps.append("atempo={:.4f}".format(speed))
        steps.append("adelay={}".format(int(round(max(0.0, start) * 1000))))
        parts.append("[{}:a]{},apad[v{}]".format(number, ",".join(steps), number))
    mixed = "".join("[v{}]".format(number) for number in range(1, len(placed) + 1))
    parts.append("{}amix=inputs={}:normalize=0:duration=longest,atrim=0:{:.3f},{}[voice]".format(mixed, len(placed), total, chain))
    parts.append("[0:a]{}[bed]".format(STEREO))
    parts.append("[bed][voice]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.8:level=disabled,atrim=0:{:.3f}[sound]".format(total))
    command += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[sound]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", str(out)]
    run(command)
    shutil.rmtree(work, ignore_errors=True)
    length = seconds_of(out)
    measured = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(out), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    summary = measured[measured.rfind("Summary:"):]
    loud, peak = re.search(r"I:\s+(-?[\d.]+) LUFS", summary), re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    print("wrote {} ({:.1f} s, {:.1f} MB{})".format(out, length, out.stat().st_size / 1e6,
                                                   ", {} LUFS, peak {} dBFS".format(loud.group(1), peak.group(1)) if loud and peak else ""))
    if length > 120.0:
        print("  LONGER THAN TWO MINUTES: the submission allows 2:00 at most")
    return 0


if __name__ == "__main__":
    sys.exit(main())
