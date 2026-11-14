"""Write down what is said in a sound file, with the time of each word, inside the container.

    python listen.py /work/sound.wav /work/heard.json

A check on the narration by something that was not told the script: `make check` compares
what this hears in the finished video with the lines of `storyboard.py`.
"""
import json
import sys
import wave

import numpy as np
from faster_whisper import WhisperModel


def main() -> int:
    sound, out = sys.argv[1], sys.argv[2]
    with wave.open(sound, "rb") as handle:              # 16 kHz, one channel, 16-bit: what `make check` writes
        if (handle.getframerate(), handle.getnchannels(), handle.getsampwidth()) != (16000, 1, 2):
            raise SystemExit("the sound must be 16 kHz mono 16-bit PCM")
        samples = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(samples, word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    words = [{"w": word.word.strip(), "t0": round(word.start, 2), "t1": round(word.end, 2)} for segment in segments for word in segment.words]
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"text": " ".join(word["w"] for word in words), "words": words}, handle, indent=1)
    print("{} words heard".format(len(words)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
