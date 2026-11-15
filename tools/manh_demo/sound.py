"""The sound track of manh_demo_1, synthesised from scratch: no samples, no library, no API.

Five layers, each written to `build/audio/` on its own so one can be listened to or left out
(`make assemble --mute rover,music`; `--mute voice` gives the film without its narration):

- voice   Kristján's narration (Kokoro, run locally), dry: no room and no echo. The first build gave it
          both, and Manh heard them as a reverb and as a whoosh after sentences (15 November). Two
          styles: `clean`, the voice as it was spoken, and `deep`, the same take two semitones lower
          with a little more chest. The final film will carry the team's own recorded voice instead;
- rover   under the chase-camera shots: gravel under the wheels, whose grain depends on the ground
          the rover is really on (regolith, sand, a rock field, bedrock), and a low electric motor
          whose pitch follows its real speed. Both come from what the recorder saw in every frame
          (`build/tele/`), so the sound stops when the rover stops and dies when its battery does;
- charts  one quiet, clean sound for everything that moves on a chart, at the moment the chart
          itself moves (`scenes.js`), plus the trackers locking on and the cards coming up;
- wind    a low wind, stronger over the ground than under the charts;
- music   one held note and its fifth, very low, that swells into the title and the last question.

Everything but the voice sits far under it and steps back further while it speaks. Nobody at a
keyboard can hear this file: the levels are set by measurement (see `build`'s notes and
`make check`), and they are the first thing to change by ear. They are all in `MIX`.
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf
from scipy import signal

RATE = 48000
FPS = 30

# Levels in dB relative to full scale; the narration is normalised to VOICE_LUFS and peaks near -6.
VOICE_LUFS = -16.0
MIX = {
    "gravel": -37.0,      # the gravel at full speed in the chase camera
    "roll": -47.0,        # the low noise of the wheels turning, under the gravel
    "motor": -33.5,       # mostly below 150 Hz: felt on headphones, nearly absent on a laptop
    "machinery": -37.0,   # the whine and the drive train's tick, 300 Hz to 2.6 kHz: quiet, but a laptop plays it
    "charts": -3.0,       # trim for every chart and interface sound (each has its own level below)
    "wind": -37.0,
    "music": -36.0,
    "thump": 0.0,         # trim for the two batteries running flat
    "duck": {"rover": -3.5, "charts": -1.5, "wind": -3.0, "music": -4.0},     # while the narrator speaks
}
LAYERS = ("voice", "rover", "charts", "music", "wind", "duck")     # what `mute` can leave out; "duck" is the stepping back under the voice
VOICE_STYLES = ("clean", "deep")
DEEP_SEMITONES = 2.0               # how much lower the `deep` voice is


def db(value: float) -> float:
    return float(10.0 ** (value / 20.0))


# ---------------------------------------------------------------- small tools
def butter(kind: str, freq: Any, order: int = 2) -> np.ndarray:
    return signal.butter(order, freq, kind, fs=RATE, output="sos")


def biquad(kind: str, freq: float, gain: float = 0.0, q: float = 0.707) -> np.ndarray:
    """One section of the Audio EQ Cookbook: 'peak', 'low' (shelf) or 'high' (shelf)."""
    a, w = 10.0 ** (gain / 40.0), 2.0 * math.pi * freq / RATE
    cos, sin = math.cos(w), math.sin(w)
    if kind == "peak":
        alpha = sin / (2.0 * q)
        b = [1 + alpha * a, -2 * cos, 1 - alpha * a]
        den = [1 + alpha / a, -2 * cos, 1 - alpha / a]
    else:
        alpha, root = sin / 2.0 * math.sqrt(2.0), 2.0 * math.sqrt(a)
        sign = 1.0 if kind == "low" else -1.0
        b = [a * ((a + 1) - sign * (a - 1) * cos + root * alpha), sign * 2 * a * ((a - 1) - sign * (a + 1) * cos), a * ((a + 1) - sign * (a - 1) * cos - root * alpha)]
        den = [(a + 1) + sign * (a - 1) * cos + root * alpha, -sign * 2 * ((a - 1) + sign * (a + 1) * cos), (a + 1) + sign * (a - 1) * cos - root * alpha]
    return np.array([[b[0] / den[0], b[1] / den[0], b[2] / den[0], 1.0, den[1] / den[0], den[2] / den[0]]])


def filt(sos: np.ndarray, x: np.ndarray) -> np.ndarray:
    return signal.sosfilt(sos, x, axis=0)


def pink(n: int, rng: np.random.Generator) -> np.ndarray:
    """Noise with equal power in every octave."""
    spectrum = np.fft.rfft(rng.standard_normal(n))
    spectrum[1:] /= np.sqrt(np.arange(1, len(spectrum)))
    spectrum[0] = 0.0
    out = np.fft.irfft(spectrum, n)
    return out / (np.sqrt(np.mean(out ** 2)) + 1e-12)


def band(n: int, low: float, high: float, rng: np.random.Generator, colour: str = "white") -> np.ndarray:
    source = pink(n, rng) if colour == "pink" else rng.standard_normal(n)
    out = filt(butter("bandpass", [low, high]), source)
    return out / (np.sqrt(np.mean(out ** 2)) + 1e-12)


def one_pole(x: np.ndarray, seconds: float) -> np.ndarray:
    """Smooth a control signal with one time constant."""
    k = 1.0 - math.exp(-1.0 / (max(seconds, 1e-4) * RATE))
    return signal.lfilter([k], [1.0, k - 1.0], x)


def hann_window(n: int, attack: float = 0.5) -> np.ndarray:
    """An envelope that rises over `attack` of its length and falls over the rest, both as half cosines."""
    up = max(1, int(n * attack))
    return np.concatenate([0.5 - 0.5 * np.cos(np.linspace(0, math.pi, up)), 0.5 + 0.5 * np.cos(np.linspace(0, math.pi, max(1, n - up)))])[:n]


def stereo(mono: np.ndarray, pan: Any = 0.0) -> np.ndarray:
    """Place a mono sound: pan -1 is left, +1 right, constant power; `pan` may move over the sound."""
    angle = (np.clip(np.asarray(pan, dtype=float), -1, 1) + 1.0) * math.pi / 4.0
    return np.stack([mono * np.cos(angle), mono * np.sin(angle)], axis=1) * math.sqrt(2.0)     # full level in both when centred


def place(track: np.ndarray, clip: np.ndarray, at: float, gain: float = 1.0) -> None:
    """Add a stereo clip into a track at a time in seconds; what falls outside the track is dropped."""
    start = int(round(at * RATE))
    if start < 0:
        clip, start = clip[-start:], 0
    end = min(len(track), start + len(clip))
    if end > start:
        track[start:end] += clip[: end - start] * gain


def tone(freq: Any, seconds: float, decay: float, attack: float = 0.002) -> np.ndarray:
    """A sine that starts at once and dies away; `freq` may be an array to glide."""
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    phase = 2 * math.pi * (np.cumsum(np.broadcast_to(np.asarray(freq, dtype=float), (n,))) / RATE)
    return np.sin(phase) * np.exp(-t / decay) * np.minimum(1.0, t / attack)


# ---------------------------------------------------------------- loudness (ITU-R BS.1770)
K_SHELF = np.array([[1.53512485958697, -2.69169618940638, 1.19839281085285, 1.0, -1.69065929318241, 0.73248077421585]])
K_HIGH = np.array([[1.0, -2.0, 1.0, 1.0, -1.99004745483398, 0.99007225036621]])


def loudness(x: np.ndarray) -> float:
    """Integrated loudness in LUFS of a mono or stereo track at 48 kHz, with the standard's two gates."""
    x = x[:, None] if x.ndim == 1 else x
    weighted = filt(K_HIGH, filt(K_SHELF, x))
    block, hop = int(0.4 * RATE), int(0.1 * RATE)
    count = max(1, (len(weighted) - block) // hop + 1)
    squares = np.cumsum(np.vstack([np.zeros((1, weighted.shape[1])), weighted ** 2]), axis=0)
    power = np.array([np.sum(squares[i * hop + block] - squares[i * hop]) / block for i in range(count)])
    level = -0.691 + 10 * np.log10(power + 1e-12)
    loud = power[level > -70.0]
    if not len(loud):
        return -70.0
    gate = -0.691 + 10 * math.log10(float(np.mean(loud))) - 10.0
    kept = power[level > gate]
    return -0.691 + 10 * math.log10(float(np.mean(kept)) + 1e-12)


# ---------------------------------------------------------------- the voice
def compress(x: np.ndarray, threshold: float = -25.0, ratio: float = 3.2, knee: float = 8.0, attack: float = 0.006, release: float = 0.14) -> np.ndarray:
    """A plain compressor on the level measured every millisecond."""
    hop = RATE // 1000
    count = len(x) // hop + 1
    padded = np.pad(x, (0, count * hop - len(x)))
    level = 20 * np.log10(np.sqrt(np.mean(padded.reshape(count, hop) ** 2, axis=1)) + 1e-9)
    over = level - threshold
    cut_db = np.where(over <= -knee / 2, 0.0, np.where(over >= knee / 2, (1 - 1 / ratio) * over, (1 - 1 / ratio) * (over + knee / 2) ** 2 / (2 * knee)))
    smoothed, state = np.empty(count), 0.0
    up, down = 1 - math.exp(-0.001 / attack), 1 - math.exp(-0.001 / release)
    for i, wanted in enumerate(cut_db):
        state += (wanted - state) * (up if wanted > state else down)
        smoothed[i] = state
    gain = np.interp(np.arange(len(x)), np.arange(count) * hop + hop / 2, smoothed)
    return x * 10 ** (-gain / 20)


def speaking_level(x: np.ndarray) -> float:
    """The level of a line in dB while its speaker is speaking: its 20 ms frames within 35 dB of the loudest."""
    hop = RATE // 50
    frames = x[: len(x) // hop * hop].reshape(-1, hop)
    power = np.mean(frames ** 2, axis=1)
    return 10 * math.log10(float(np.mean(power[power > power.max() * db(-35) ** 2])) + 1e-12)


def deepen(path: Path) -> np.ndarray:
    """A spoken line `DEEP_SEMITONES` lower, formants and all, so it sounds like a deeper voice and not like the
    same voice straining down (Rubber Band, through ffmpeg; the length does not change). Then a little more chest,
    a little more edge so it stays crisp, and a gentle compressor to hold its level even. No room, no echo."""
    lower = 2.0 ** (-DEEP_SEMITONES / 12.0)
    done = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-af", "rubberband=pitch={:.5f}:pitchq=quality:formant=shifted".format(lower),
                           "-ar", str(RATE), "-ac", "1", "-f", "f32le", "-"], capture_output=True)
    if done.returncode != 0:
        raise SystemExit("ffmpeg could not lower {}: {}".format(path.name, done.stderr.decode()[-400:]))
    x = np.frombuffer(done.stdout, dtype=np.float32).astype(np.float64)
    x = filt(butter("highpass", 55.0), x * db(-20.0 - speaking_level(x)))
    for section in (biquad("low", 150.0, 2.5), biquad("peak", 4200.0, 1.5, 0.8)):
        x = filt(section, x)
    return compress(x, threshold=-22.0, ratio=2.2, knee=10.0, attack=0.008, release=0.15)


def voice_line(path: Path, style: str) -> np.ndarray:
    """One line of the narration at 48 kHz, in the chosen style."""
    raw, rate = sf.read(str(path), dtype="float64")
    raw = raw if raw.ndim == 1 else raw.mean(axis=1)
    plain = filt(butter("highpass", 60.0), signal.resample_poly(raw, RATE, rate))
    if style == "clean":
        return plain
    if style != "deep":
        raise SystemExit("no voice style called {}: choose from {}".format(style, ", ".join(VOICE_STYLES)))
    deep = deepen(path)[: len(plain)]
    return np.pad(deep, (0, len(plain) - len(deep)))


def impulse(rt60: float, predelay: float, low: float, high: float, seed: int, taps: bool, bloom: float = 0.02) -> np.ndarray:
    """A room as a stereo impulse response: a few early reflections, then noise dying away over `rt60` seconds.
    `bloom` is how long the tail takes to come up. Used for the ring of a battery running flat, never on the voice."""
    rng = np.random.default_rng(seed)
    n, lead = int(rt60 * 1.2 * RATE), int(predelay * RATE)
    t = np.arange(n) / RATE
    tail = rng.standard_normal((n, 2)) * np.exp(-6.91 * t / rt60)[:, None]
    tail = filt(butter("bandpass", [low, high]), tail)
    tail[: int(bloom * RATE)] *= np.linspace(0, 1, int(bloom * RATE))[:, None] ** 2
    out = np.zeros((n + lead, 2))
    out[lead:] = tail / (np.sqrt(np.sum(tail ** 2, axis=0)) + 1e-12)
    if taps:
        for ms, gain, side in ((11, 0.30, 0), (17, 0.26, 1), (23, 0.22, 0), (31, 0.17, 1), (43, 0.12, 0), (57, 0.09, 1)):
            out[int(ms / 1000 * RATE), side] += gain
    return out / (np.sqrt(np.mean(np.sum(out ** 2, axis=0))) + 1e-12)


def activity(mono: np.ndarray, attack: float = 0.05, release: float = 0.35) -> np.ndarray:
    """0 to 1: whether the narrator is speaking, with a quick rise and a slow fall."""
    level = one_pole(np.abs(mono), 0.012)
    on = (level > db(-42)).astype(float)
    rise, fall = one_pole(on, attack), one_pole(on[::-1], release)[::-1]
    return np.clip(np.maximum(rise, fall), 0, 1)


def voice_bus(spoken: List[Dict[str, Any]], folder: Path, total: float, style: str = "clean") -> Tuple[np.ndarray, np.ndarray]:
    """The narration on the film's time line, dry: (the voice in both channels, the voice alone)."""
    n = int(round(total * RATE))
    dry = np.zeros(n)
    for item in spoken:
        line = voice_line(folder / "{}.wav".format(item["line"]), style)
        start = int(round(item["at"] * RATE))
        end = min(n, start + len(line))
        dry[start:end] += line[: end - start]
    out = np.repeat(dry[:, None], 2, axis=1)
    level = db(VOICE_LUFS - loudness(out))
    return out * level, dry * level


# ---------------------------------------------------------------- the rover
GROUND = ("regolith", "sand", "rocks", "bedrock")
# per kind of ground: grains a second at full speed, and bands of (low Hz, high Hz, decay ms, share of the grains, level)
GRAVEL = {
    "regolith": (150.0, [(650.0, 2100.0, 9.0, 0.5, 1.0), (2100.0, 6200.0, 5.0, 0.5, 0.8)]),
    # Sand was first a dense, bright hiss, and Manh heard it as static (15 November). Now it is few, soft, low grains
    # (the wheels pressing in), and the sifting on top comes in the rhythm of the wheels' treads: see `rover_shot`.
    # A sixth number is a soft start in milliseconds: on sand a grain swells in instead of snapping on, because the
    # snap is what Manh heard as clicking in the second try.
    "sand": (110.0, [(380.0, 1500.0, 36.0, 1.0, 0.3, 12.0)]),
    "rocks": (95.0, [(320.0, 1300.0, 15.0, 0.45, 1.35), (1300.0, 5200.0, 6.0, 0.55, 1.1)]),
    "bedrock": (75.0, [(900.0, 3600.0, 5.0, 1.0, 1.0)]),
}


SAND_SIFT = 1.4        # the sifting off the treads, against the gravel level: the soft rhythm that says "sand"


def control(values: np.ndarray, n: int, smooth: float) -> np.ndarray:
    """A per-frame value stretched to audio rate and smoothed."""
    frames = np.arange(len(values)) * (RATE / FPS)
    return one_pole(np.interp(np.arange(n), frames, values), smooth)


def rover_shot(frames: List[Dict[str, Any]], seed: int) -> np.ndarray:
    """Gravel and motor for one ground shot, from what the followed rover did in every frame."""
    n = int(round(len(frames) * RATE / FPS))
    rng = np.random.default_rng(seed)
    count = len(frames)
    throttle, near, alive, ground = np.zeros(count), np.zeros(count), np.zeros(count), np.zeros(count, dtype=int)
    for i, now in enumerate(frames):
        before = frames[i - 1] if i else now
        ticks = now["t"] - before["t"]
        same = now["follow"] == before["follow"] and 0 < ticks < 1.5         # not a cut, not a jump in time
        metres = math.hypot(now["x"] - before["x"], now["y"] - before["y"]) if same else 0.0
        throttle[i] = min(1.15, metres / ticks / 5.0) if same and now["playing"] and now["alive"] else 0.0   # rovers drive up to 5 m a tick
        near[i] = now["chase"] ** 2 * (1.0 - now["weight"])                  # 1 behind the rover, 0 from above
        alive[i] = 1.0 if now["alive"] else 0.0
        ground[i] = now["ground"]
    drive, close, on = control(throttle, n, 0.09), control(near, n, 0.12), control(alive, n, 0.22)
    out = np.zeros((n, 2))
    # gravel: short bursts of band-limited noise, more of them the faster the rover goes
    for index, name in enumerate(GROUND):
        here = control((ground == index).astype(float), n, 0.06)
        if here.max() < 1e-3:
            continue
        rate, bands = GRAVEL[name]
        for low, high, decay, share, level, *soft in bands:
            steps = np.arange(int(decay * 5 / 1000 * RATE)) / RATE
            kernel = np.exp(-steps / (decay / 1000))
            if soft:
                kernel = kernel * (1.0 - np.exp(-steps / (soft[0] / 1000)))
                kernel /= kernel.max()
            for side in (0, 1):                                              # each side's wheels crunch on their own
                chance = drive * here * rate * share / RATE
                hits = (rng.random(n) < chance) * rng.lognormal(0.0, 0.45, n)
                grain = signal.fftconvolve(hits, kernel)[:n] * band(n, low, high, rng)
                out[:, side] += grain * level * 0.33 * db(MIX["gravel"]) * close
    # sand sifting off the treads: soft air that comes and goes as each tread bites, left and right in turn,
    # faster as the rover speeds up. A rhythm is what tells it from static.
    sandy = control((ground == GROUND.index("sand")).astype(float), n, 0.06)
    if sandy.max() > 1e-3:
        tread = np.cumsum(3.4 + 5.6 * drive) / RATE
        for side in (0, 1):
            bite = np.clip(np.cos(2 * math.pi * (tread + 0.5 * side)), 0, 1) ** 3
            sift = band(n, 1500.0, 4200.0, rng, "pink") * bite
            out[:, side] += sift * drive * sandy * SAND_SIFT * db(MIX["gravel"]) * close
    ceiling = db(MIX["gravel"] + 13.0)
    out = np.tanh(out / ceiling) * ceiling                                   # a rare loud grain is rounded off, so none pokes out
    # the wheels rolling: low noise that pulses with their turning
    turning = np.cumsum(2.2 + 3.2 * drive) / RATE
    roll = band(n, 110.0, 650.0, rng, "pink") * drive ** 0.8 * (1.0 + 0.22 * np.sin(2 * math.pi * turning))
    out += (roll * db(MIX["roll"]) * 2.4 * close * (1.0 - 0.45 * sandy))[:, None]          # sand swallows some of the rolling
    # the motor: a low hum with its overtones, and a faint whine, both rising with speed; it winds down when the battery dies
    pitch = (36.0 + 30.0 * drive) * (0.3 + 0.7 * on)
    phase = 2 * math.pi * np.cumsum(pitch * (1.0 + 0.012 * np.sin(2 * math.pi * 5.3 * np.arange(n) / RATE))) / RATE
    hum = sum(level * np.sin(k * phase + k) for k, level in ((1, 1.0), (2, 0.6), (3, 0.36), (4, 0.2), (5, 0.1)))
    whine = 0.07 * np.sin(2 * math.pi * np.cumsum((185.0 + 240.0 * drive) * (0.3 + 0.7 * on)) / RATE)
    flutter = 1.0 + 0.16 * filt(butter("lowpass", 11.0), rng.standard_normal(n)) * 6.0
    motor = filt(butter("lowpass", 900.0), (hum + whine) * flutter) * (0.2 + 0.8 * drive) * on
    out += (motor * 0.55 * db(MIX["motor"]) * (0.25 + 0.75 * close))[:, None]
    # the machinery, where a laptop can play it: an electric whine that climbs with speed, and the drive train's
    # soft tick, one side after the other. Quiet, but a pitch and a rhythm, so it reads as a machine.
    t = np.arange(n) / RATE
    climb = 2 * math.pi * np.cumsum((290.0 + 250.0 * drive) * (0.3 + 0.7 * on) * (1.0 + 0.007 * np.sin(2 * math.pi * 6.1 * t))) / RATE
    whirr = (np.sin(climb) + 0.4 * np.sin(2 * climb + 0.6) + 0.16 * np.sin(3 * climb + 1.1)) * drive ** 0.7 * on
    out += (filt(butter("lowpass", 2400.0), whirr) * 0.5 * db(MIX["machinery"]) * (0.3 + 0.7 * close))[:, None]
    teeth = np.cumsum((5.5 + 7.5 * drive) * (drive > 0.03)) / RATE
    click = np.exp(-np.arange(int(0.03 * RATE)) / (0.0055 * RATE))
    steps = np.arange(int(0.1 * RATE)) / RATE
    thud = np.exp(-steps / 0.02) * (1.0 - np.exp(-steps / 0.006))               # on sand the tick is a soft, low thud: no edge
    thud /= thud.max()
    for side in (0, 1):
        turned = (np.diff(np.floor(teeth + 0.5 * side), prepend=np.floor(0.5 * side)) > 0) * (0.65 + 0.35 * rng.random(n))
        tick = signal.fftconvolve(turned * (1.0 - sandy), click)[:n] * band(n, 900.0, 2600.0, rng)
        tick += signal.fftconvolve(turned * sandy, thud)[:n] * band(n, 300.0, 950.0, rng) * 0.55
        out[:, side] += tick * 1.5 * db(MIX["machinery"]) * on * (0.3 + 0.7 * close)
    return out


# ---------------------------------------------------------------- chart and interface sounds
PENTATONIC = (0, 3, 5, 7, 10, 12, 15, 17)       # steps of D minor pentatonic, so nothing ever clashes with the held D


def note(step: int, octave: float = 1174.66) -> float:
    return octave * 2 ** (PENTATONIC[step % len(PENTATONIC)] / 12.0)


def sweep(seconds: float, low: float, high: float, rng: np.random.Generator, attack: float = 0.35, width: float = 0.9) -> np.ndarray:
    """Air moving: pink noise through a band that slides from `low` to `high` Hz. The clean 'flow' under the charts."""
    n = int(seconds * RATE)
    centre = np.geomspace(low, high, n)
    out = np.zeros((n, 2))
    for side in (0, 1):
        source = pink(n + 2048, rng)[:n]
        # a sliding band: the noise is shifted down by the moving centre, low-passed, and shifted back up
        phase = 2 * math.pi * np.cumsum(centre) / RATE
        low_pass = butter("lowpass", 260.0 * width, 2)
        i, q = filt(low_pass, source * np.cos(phase)), filt(low_pass, source * np.sin(phase))
        out[:, side] = i * np.cos(phase) + q * np.sin(phase)
    out /= np.sqrt(np.mean(out ** 2)) + 1e-12
    return out * hann_window(n, attack)[:, None]


def render(cue: Dict[str, Any], rng: np.random.Generator) -> Tuple[np.ndarray, float]:
    """One sound as a stereo clip, and how long before its moment it begins."""
    kind = cue["kind"]
    if kind == "tick":                       # something small arrives: a clean high blip
        clip = tone(note(cue.get("step", 0)), 0.3, 0.05) + 0.4 * tone(note(cue.get("step", 0)) * 2.0, 0.3, 0.03)
        return stereo(clip * db(-37), cue.get("pan", 0.15 * ((cue.get("step", 0) % 3) - 1))), 0.0
    if kind == "tock":                       # something ends: lower and duller
        clip = tone(196.0, 0.4, 0.08) + 0.5 * tone(98.0, 0.4, 0.1) + 0.25 * band(int(0.4 * RATE), 200, 900, rng) * np.exp(-np.arange(int(0.4 * RATE)) / (0.03 * RATE))
        return stereo(clip * db(-31)), 0.0
    if kind in ("chime", "chime_soft"):      # a link lights up, a number lands
        f = note(cue.get("step", 3), 587.33)
        clip = tone(f, 1.6, 0.42) + 0.45 * tone(f * 2.005, 1.6, 0.3) + 0.2 * tone(f * 3.0, 1.6, 0.18)
        return stereo(clip * db(-33 if kind == "chime" else -37), -0.25 + 0.17 * cue.get("step", 1)), 0.0
    if kind == "bar":                        # a bar grows: air sliding up, further the higher the score
        score = float(cue.get("score", 0.2))
        length = 0.55 + 0.9 * min(0.5, score)
        clip = sweep(length, 420.0, 520.0 + 5200.0 * min(0.5, score), rng, attack=0.3)
        pan = np.linspace(-0.55, -0.35 + 1.7 * min(0.5, score), len(clip))
        mono = clip.mean(axis=1) * db(-31 if cue.get("gold") else -34)
        return 0.5 * stereo(mono, pan) + 0.5 * clip * db(-31 if cue.get("gold") else -34), 0.05
    if kind == "flow":                       # a line draws itself: long, even, moving air
        rise = float(cue.get("rise", 0.0))
        length = float(cue.get("len", 1.0)) + 0.5
        clip = sweep(length, 700.0, 700.0 * 2 ** (1.7 * rise), rng, attack=min(0.3, 0.5 / length), width=0.7)
        return clip * db(-34), 0.12
    if kind == "swell":                      # a block of text comes up: a soft push of air
        clip = sweep(0.8, 300.0, 900.0, rng, attack=0.45, width=0.8)
        return clip * db(-34), 0.2
    if kind == "riser":                      # into the last question
        length = max(0.3, float(cue.get("len", 1.0)))
        clip = sweep(length, 320.0, 4200.0, rng, attack=0.97, width=1.2) * (np.linspace(0, 1, int(length * RATE)) ** 2.2)[:, None]
        return clip * db(-30), 0.0
    if kind in ("hit", "hit_soft"):          # a verdict lands: a low note, the octave small speakers can play, air after it
        big = kind == "hit"
        n = int(1.6 * RATE)
        t = np.arange(n) / RATE
        glide = 1.0 + 0.5 * np.exp(-t / 0.035)
        low = tone(55.0 * glide, 1.6, 0.45 if big else 0.22, 0.004) + 0.55 * tone(110.0 * glide, 1.6, 0.3 if big else 0.16, 0.004)
        air = sweep(1.6, 2400.0, 900.0, rng, attack=0.02, width=1.6).mean(axis=1) * np.exp(-t / 0.4)
        shine = (tone(1174.66, 1.6, 0.6) + 0.7 * tone(1760.0, 1.6, 0.5)) * db(-22)
        clip = stereo((low + 0.1 * air) * db(-22 if big else -27)) + stereo(shine * db(-22 if big else -30), 0.3)
        if big:                              # and a breath in before it
            lead = sweep(0.4, 500.0, 2200.0, rng, attack=0.96, width=1.0) * db(-33)
            both = np.zeros((len(lead) + n, 2))
            both[: len(lead)] += lead
            both[len(lead):] += clip
            return both, 0.4
        return clip, 0.0
    if kind == "typing":                     # the command typing itself out
        length = float(cue.get("len", 1.3))
        clip = np.zeros((int((length + 0.1) * RATE), 2))
        for i in range(int(length * 15)):
            at = i / 15.0 + rng.uniform(-0.012, 0.012)
            key = band(int(0.02 * RATE), 1800.0, 5200.0, rng) * np.exp(-np.arange(int(0.02 * RATE)) / (0.004 * RATE)) * rng.uniform(0.6, 1.0)
            place(clip, stereo(key * db(-38), rng.uniform(-0.3, 0.3)), max(0.0, at))
        return clip, 0.0
    if kind in ("whoosh", "cut", "transition"):       # the camera moves, the film cuts
        length = float(cue.get("len", {"whoosh": 1.2, "cut": 0.45, "transition": 0.7}[kind]))
        n = int(length * RATE)
        up = sweep(length, 180.0, 1500.0 if kind == "whoosh" else 900.0, rng, attack=0.5, width=1.0)
        back = sweep(length, 1500.0 if kind == "whoosh" else 900.0, 180.0, rng, attack=0.5, width=1.0)
        fade = np.linspace(0, 1, n)[:, None]
        clip = up * (1 - fade) + back * fade
        return clip * db({"whoosh": -31, "cut": -33, "transition": -36}[kind]), length * (0.5 if kind != "whoosh" else 0.1)
    if kind == "lock":                       # a tracker closes on a rover: two quick pips, or one for the small ones
        hero = cue.get("who") == "hero"
        clip = tone(1760.0, 0.09, 0.022) * (1.0 if hero else 0.0)
        second = tone(2349.3 if hero else 2093.0, 0.14, 0.03)
        both = np.zeros(int(0.22 * RATE))
        both[: len(clip)] += clip
        both[int((0.065 if hero else 0.0) * RATE):][: len(second)] += second
        return stereo(both * db(-35 if hero else -41), cue.get("pan", 0.0)), 0.0
    if kind == "card":                       # the card that explains a moment slides up
        slide = sweep(0.42, 900.0, 320.0, rng, attack=0.3, width=1.0) * db(-33)
        bad = cue.get("tone") != "gold"
        low = (tone(110.0, 1.3, 0.45) + 0.8 * tone(116.5 if bad else 165.0, 1.3, 0.4)) * db(-31)
        clip = np.zeros((int(1.4 * RATE), 2))
        clip[: len(slide)] += slide
        place(clip, stereo(low), 0.12)
        return clip, 0.1
    if kind == "way":                        # the way home draws itself, dot by dot
        clip = np.zeros((int(2.1 * RATE), 2))
        for i in range(11):
            pip = tone(note(i % 6 if cue.get("open", True) else 5 - i % 6, 587.33), 0.25, 0.045)
            place(clip, stereo(pip * db(-39), -0.5 + 0.1 * i), 0.15 * i)
        return clip, 0.0
    if kind in ("sample", "late"):           # a sample is taken: two rising notes; late, one
        clip = np.zeros(int(0.5 * RATE))
        first = tone(880.0, 0.3, 0.07)
        clip[: len(first)] += first
        if kind == "sample":
            second = tone(1174.66, 0.4, 0.1)
            clip[int(0.075 * RATE):][: len(second)] += second
        return stereo(clip * db(-36 if cue.get("who") == "on" else -41)), 0.0
    if kind == "miss":                       # a sample missed: two falling notes that do not resolve
        clip = np.zeros(int(0.6 * RATE))
        for at, f in ((0.0, 659.25), (0.11, 466.16)):
            piece = tone(f, 0.4, 0.09) + 0.3 * tone(f * 2, 0.4, 0.05)
            clip[int(at * RATE):][: len(piece)] += piece
        return stereo(clip * db(-31)), 0.0
    if kind == "stop":                       # a safety stop: the brakes, then two low warnings
        n = int(0.7 * RATE)
        clip = np.zeros(n)
        brake = band(int(0.09 * RATE), 300.0, 2200.0, rng) * np.exp(-np.arange(int(0.09 * RATE)) / (0.022 * RATE))
        clip[: len(brake)] += brake * 1.4
        for at in (0.1, 0.26):
            beep = tone(392.0, 0.12, 0.05) + 0.4 * tone(784.0, 0.12, 0.04)
            clip[int(at * RATE):][: len(beep)] += beep
        return stereo(clip * db(-31)), 0.0
    if kind == "warn":                       # the battery warning: two short low pips, a little louder as it empties
        clip = np.zeros(int(0.3 * RATE))
        for at in (0.0, 0.1):
            pip = tone(523.25, 0.12, 0.028) + 0.35 * tone(1046.5, 0.12, 0.02)
            clip[int(at * RATE):][: len(pip)] += pip
        return stereo(clip * db(-37 - 60 * float(cue.get("charge", 0.03)))), 0.0
    if kind == "thump":                      # a battery runs flat: the power winds down into a low thud that rings
        n = int(2.6 * RATE)
        t = np.arange(n) / RATE
        wind_down = tone(np.geomspace(230.0, 38.0, int(1.0 * RATE)), 1.0, 0.5, 0.01) * db(-25)
        thud = tone(55.0, 1.4, 0.4, 0.003) * db(-11) + tone(110.0, 1.4, 0.2, 0.003) * db(-17)
        knock = filt(butter("lowpass", 420.0), rng.standard_normal(int(0.3 * RATE))) * np.exp(-np.arange(int(0.3 * RATE)) / (0.05 * RATE)) * db(-17)
        clip = np.zeros(n)
        clip[: len(wind_down)] += wind_down
        clip[: len(thud)] += thud
        clip[: len(knock)] += knock
        tail = signal.fftconvolve(clip, impulse(2.2, 0.03, 90.0, 1800.0, 21, False)[:, 0])[:n] * db(-17)
        return stereo(clip) + np.stack([tail, np.roll(tail, 331)], axis=1), 0.0
    raise ValueError("no sound called {!r}".format(kind))


# ---------------------------------------------------------------- wind and music
def wind(total: float, ground: np.ndarray, seed: int) -> np.ndarray:
    """A low wind that comes and goes; `ground` is 1 over the ground shots and 0 under the charts."""
    n = int(round(total * RATE))
    rng = np.random.default_rng(seed)
    out = np.zeros((n, 2))
    gust = 1.0 + 0.45 * np.clip(filt(butter("lowpass", 0.18), rng.standard_normal(n)) * 60.0, -1, 1)
    for side in (0, 1):
        brown = np.cumsum(rng.standard_normal(n))
        brown = filt(butter("bandpass", [40.0, 240.0]), brown)
        brown /= np.sqrt(np.mean(brown ** 2)) + 1e-12
        air = band(n, 500.0, 2400.0, rng, "pink") * 0.11
        out[:, side] = (brown + air * ground) * gust * (0.5 + 0.5 * ground)
    return out * db(MIX["wind"])


def music(total: float, swell: np.ndarray, seed: int) -> np.ndarray:
    """One held D and its fifth, slowly breathing, with a faint high shimmer; `swell` is its loudness over the film."""
    n = int(round(total * RATE))
    rng = np.random.default_rng(seed)
    t = np.arange(n) / RATE
    out = np.zeros((n, 2))
    voices = ((73.42, 1.0, 0.07), (110.0, 0.8, 0.05), (146.83, 0.6, 0.09), (220.0, 0.22, 0.06), (293.66, 0.12, 0.11))
    for freq, level, rate in voices:
        for side, detune in ((0, 0.9985), (1, 1.0015)):
            breath = 0.72 + 0.28 * np.sin(2 * math.pi * rate * t + rng.uniform(0, 6.28))
            wave = np.sin(2 * math.pi * freq * detune * t) + 0.22 * np.sin(2 * math.pi * 2 * freq * detune * t + 1.0) + 0.08 * np.sin(2 * math.pi * 3 * freq * detune * t)
            out[:, side] += wave * level * breath
    for freq, level, rate in ((587.33, 0.05, 0.13), (880.0, 0.035, 0.17), (1174.66, 0.02, 0.21)):
        for side in (0, 1):
            out[:, side] += np.sin(2 * math.pi * freq * t + rng.uniform(0, 6.28)) * level * (0.5 + 0.5 * np.sin(2 * math.pi * rate * t + rng.uniform(0, 6.28)))
    out /= np.sqrt(np.mean(out ** 2)) + 1e-12
    return out * swell[:, None] * db(MIX["music"])


def ramps(total: float, points: List[Tuple[float, float]]) -> np.ndarray:
    """A level over the film from (seconds, value) points, joined by straight lines and then smoothed."""
    n = int(round(total * RATE))
    xs, ys = zip(*sorted(points))
    return one_pole(np.interp(np.arange(n) / RATE, xs, ys), 0.25)


# ---------------------------------------------------------------- the mix
def build(timeline: List[Dict[str, Any]], spoken: List[Dict[str, Any]], folder: Path, mute: Optional[List[str]] = None,
          voice_style: str = "clean", into: str = "audio", whole: bool = True) -> Dict[str, Any]:
    """Write build/audio/mix.wav and one file per layer; return where, and notes on the levels. With "voice" in
    `mute` the narration is left out of the mix and nothing steps back for it: the film alone, for looking at.
    A clip that is not the whole film (`whole` false) goes to its own folder `into` and gets an even bed under it
    instead of the film's swells into the title and the last question."""
    mute = list(mute or [])
    unknown = sorted(set(mute) - set(LAYERS))
    if unknown:
        raise SystemExit("no layer called {}: choose from {}".format(", ".join(unknown), ", ".join(LAYERS)))
    total = sum(item["seconds"] for item in timeline)
    n = int(round(total * RATE))
    out_folder = folder / into
    out_folder.mkdir(parents=True, exist_ok=True)
    voice, dry = voice_bus(spoken, folder / "voice", total, voice_style)

    starts, offset = {}, 0.0
    for item in timeline:
        starts[item["name"]] = offset
        offset += item["seconds"]
    rover, charts = np.zeros((n, 2)), np.zeros((n, 2))
    on_ground, air, thumps, cues = np.zeros(n), np.ones(n), [], []
    for number, item in enumerate(timeline):
        begin = starts[item["name"]]
        a, b = int(begin * RATE), int((begin + item["seconds"]) * RATE)
        if item.get("vacuum"):                                                # a stretch in space: no wind there, no rover
            air[int((begin + item["vacuum"][0]) * RATE): int((begin + item["vacuum"][1]) * RATE)] = 0.0
        tele = folder / "tele" / "{}.json".format(item["name"])
        if item.get("page") != "film" and tele.exists():
            frames = json.loads(tele.read_text(encoding="utf-8"))
            on_ground[a:b] = 1.0
            clip = rover_shot(frames, 100 + number)
            edge = np.ones(len(clip))                                         # in and out with the picture's fades
            edge[: int(0.3 * RATE)] = np.linspace(0, 1, int(0.3 * RATE))
            edge[-int(0.25 * RATE):] = np.linspace(1, 0, int(0.25 * RATE))
            place(rover, clip * edge[:, None], begin)
            warn_at = 0.0
            for index, frame in enumerate(frames):                            # what happened in the picture
                at = begin + index / FPS
                # behind a rover whose battery is nearly empty, a low warning that comes faster as it drains
                charge = frame.get("battery", 1.0)
                if frame["alive"] and frame["playing"] and frame["chase"] > 0.6 and charge < 0.06 and at >= warn_at:
                    cues.append({"at": at, "kind": "warn", "charge": charge})
                    warn_at = at + 0.4 + 9.0 * charge
                for who in frame.get("locks", []):
                    cues.append({"at": at, "kind": "lock", "who": who})
                for event in frame.get("events", []):
                    if event["k"] in ("sample", "late", "miss", "stop", "card", "way"):
                        cues.append({**event, "at": at, "kind": event["k"]})
        for cue in item.get("sfx", []):
            cues.append({**cue, "at": begin + cue["at"]})
        thumps += [round(begin + at, 3) for at in item.get("thumps", [])]
        if number:
            cues.append({"at": begin, "kind": "transition"})
    # trackers that lock on together are heard as a quick run of pips, not as one loud one
    locks = sorted((cue for cue in cues if cue["kind"] == "lock"), key=lambda cue: cue["at"])
    for index, cue in enumerate(locks):
        cue["pan"] = -0.5 + (index % 5) * 0.25
    rng = np.random.default_rng(2026)
    for cue in sorted(cues, key=lambda cue: (cue["at"], cue["kind"])):
        clip, lead = render(cue, rng)
        place(charts, clip, cue["at"] - lead, db(MIX["charts"]))
    for at in thumps:
        clip, lead = render({"kind": "thump"}, rng)
        place(charts, clip, at - lead, db(MIX["thump"]))

    ground, air = one_pole(on_ground, 0.4), one_pole(air, 0.5)
    blow = wind(total, ground, 7) * air[:, None]
    rover *= air[:, None]
    title = next((starts[item["name"]] for item in timeline if item["name"] == "world"), 11.0)
    end = starts[timeline[-1]["name"]]
    swell = ramps(total, [(0.0, 0.0), (2.5, 0.85), (title - 0.5, 0.9), (title + 0.6, 1.5), (title + 5.0, 0.9), (end - 6.0, 0.8), (end + 1.0, 1.0),
                          (total - 2.6, 1.6), (total - 0.2, 0.0)] if whole else [(0.0, 0.0), (0.8, 0.9), (total - 0.8, 0.9), (total - 0.1, 0.0)])
    score = music(total, swell, 3)

    speaking = activity(dry)
    layers = {"rover": rover, "charts": charts, "wind": blow, "music": score}
    silent = "voice" in mute
    mix = np.zeros_like(voice) if silent else voice.copy()
    for name, layer in layers.items():
        if name in mute:
            layer *= 0.0
            continue
        if not silent and "duck" not in mute:
            layer *= (1.0 - speaking * (1.0 - db(MIX["duck"][name])))[:, None]
        mix += layer
    close = np.ones(n)                                                        # out with the picture
    tail = int(min(1.3 if whole else 0.5, total / 3) * RATE)
    close[-tail:] = np.linspace(1, 0, tail) ** 1.5
    close[: int(0.25 * RATE)] = np.linspace(0, 1, int(0.25 * RATE))
    mix *= close[:, None]
    path = out_folder / "mix.wav"
    sf.write(str(path), np.clip(mix, -1.0, 1.0), RATE, subtype="PCM_24")
    for name, layer in {"voice": voice, **layers}.items():
        sf.write(str(out_folder / "{}.wav".format(name)), np.clip(layer * close[:, None], -1.0, 1.0), RATE, subtype="PCM_24")

    def rms(x: np.ndarray, where: Optional[np.ndarray] = None) -> float:
        x = x if where is None else x[where]
        return 20 * math.log10(float(np.sqrt(np.mean(x ** 2))) + 1e-12) if len(x) else -120.0

    talk, quiet = speaking > 0.6, speaking < 0.05
    rest = mix if silent else mix - voice
    notes = ["sound: {:.1f} LUFS overall, voice {} ({}), sample peak {:.1f} dBFS".format(
                 loudness(mix), "left out" if silent else "{:.1f} LUFS".format(loudness(voice)), voice_style, 20 * math.log10(float(np.max(np.abs(mix))) + 1e-12)),
             "while the narrator speaks: voice {:.1f} dB, everything else {:.1f} dB ({:.1f} dB under it)".format(
                 rms(voice, talk), rms(rest, talk), rms(voice, talk) - rms(rest, talk)),
             "in the pauses: everything else {:.1f} dB".format(rms(rest, quiet))]
    for name, layer in layers.items():
        if name not in mute:
            loud = np.abs(layer).max(axis=1) > db(-70)
            notes.append("  {:7s} {:6.1f} dB where it sounds ({:4.1f}s of the film), peak {:6.1f} dBFS".format(
                name, rms(layer, loud), loud.sum() / RATE, 20 * math.log10(float(np.max(np.abs(layer))) + 1e-12)))
    notes.append("{} chart and interface sounds, {} thumps".format(len(cues), len(thumps)))
    (out_folder / "cues.json").write_text(json.dumps(sorted(({key: (round(value, 3) if isinstance(value, float) else value) for key, value in cue.items()} for cue in cues),
                                                             key=lambda cue: cue["at"]), indent=1), encoding="utf-8")
    return {"mix": path, "notes": notes, "thumps": thumps}
