"""Speak the narration: one WAV per line, inside the container.

    python speak.py /work/lines.json /work/out [--voice af_heart] [--speed 1.0]

`lines.json` is a list of {"id": ..., "say": ...}. Writes out/<id>.wav (24 kHz mono),
out/<id>.words.json (when each word starts and ends, in seconds, as the voice model reports
it) and out/durations.json. A line is only spoken again when its text, voice or speed changed.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

RATE = 24000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("lines", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--voice", default="af_heart")
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    pipeline = KPipeline(lang_code=args.voice[0])
    durations = {}
    for line in json.loads(args.lines.read_text(encoding="utf-8")):
        key = hashlib.sha256("{}|{}|{}".format(line["say"], args.voice, args.speed).encode()).hexdigest()[:16]
        wav, stamp = args.out / "{}.wav".format(line["id"]), args.out / "{}.key".format(line["id"])
        timing = args.out / "{}.words.json".format(line["id"])
        if not (wav.exists() and timing.exists() and stamp.exists() and stamp.read_text() == key):
            parts, spoken, words, offset = [], [], [], 0.0
            for result in pipeline(line["say"], voice=args.voice, speed=args.speed, split_pattern=r"\n+"):
                audio = np.asarray(result.audio, dtype=np.float32)
                for token in (getattr(result, "tokens", None) or []):          # times count from the start of this piece
                    start, end = getattr(token, "start_ts", None), getattr(token, "end_ts", None)
                    words.append({"w": token.text, "space": bool(getattr(token, "whitespace", "")),
                                  "t0": None if start is None else round(offset + start, 3),
                                  "t1": None if end is None else round(offset + end, 3)})
                offset += len(audio) / RATE
                parts.append(audio)
                spoken.append(result.phonemes)
            sf.write(str(wav), np.concatenate(parts), RATE, subtype="PCM_16")
            (args.out / "{}.phonemes.txt".format(line["id"])).write_text(" | ".join(spoken) + "\n", encoding="utf-8")
            timing.write_text(json.dumps(words) + "\n", encoding="utf-8")
            stamp.write_text(key)
        durations[line["id"]] = round(sf.info(str(wav)).duration, 3)
        print("{:12s} {:6.2f}s  {}".format(line["id"], durations[line["id"]], line["say"][:70]), flush=True)
    (args.out / "durations.json").write_text(json.dumps(durations, indent=1) + "\n", encoding="utf-8")
    print("total {:.1f}s".format(sum(durations.values())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
