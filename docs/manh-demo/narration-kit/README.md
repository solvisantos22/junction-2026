# Narration kit: record the narrator for `manh_demo_2`

Sunday 15 November 2026, about 07:10 Helsinki. Manh / Claude Code (demo cut chat). For the teammate who records the narration, and for the coding agent helping him. Everything needed is in this folder.

`manh_demo_2` is the team's **draft** film (1:59), a trailer for Lightlag Traverse. Its picture, music and effects are finished; its narrator is a synthetic placeholder. This kit replaces the placeholder with a real voice **without touching the picture**. Kristján's film (`docs/demo-video/`) stays the main one until the team decides.

| File | What it is |
|---|---|
| [`manh_demo_2_no_narrator.mp4`](manh_demo_2_no_narrator.mp4) | **The film without its narrator**: picture, music and effects. 119.1 s, 1920×1080, 30 fps |
| [`narration.md`](narration.md) | **The draft narration**: the 15 lines in order, when each starts, when it must be over, what the picture does on which words, and a clean reading copy at the end |
| [`narration.srt`](narration.srt) | The same lines as subtitles with times, to rehearse against the film |
| [`guide_voice.m4a`](guide_voice.m4a) | The placeholder narrator alone, in sync with the film: listen for pace, do not use it in the film |
| [`timing.json`](timing.json) | The lines and times as data (what the tool reads) |
| [`lay_narration.py`](lay_narration.py) | Cuts a recording into the lines, fits each into its place, cleans the voice and writes the narrated film. Needs Python 3.8+ and ffmpeg, nothing else |

## The short way

1. **Rehearse.** Play the film with the lines on screen: `mpv --sub-file=narration.srt manh_demo_2_no_narrator.mp4` (or VLC: Subtitle › Add Subtitle File). Read along twice.
2. **Record one read-through** of the reading copy at the end of [`narration.md`](narration.md): all 15 lines, top to bottom, with **two full seconds of silence after every line**. No need to watch the film or a clock while recording.
3. **Lay it in:**

```bash
python3 lay_narration.py splice my_reading.m4a
```

It prints where it found each line, what it did to fit it, and writes `manh_demo_2_narrated.mp4` here. Watch that once with the sound on.

## How to narrate this film

It is a two-minute trailer with a cliffhanger after almost every line. What works:

- **One listener.** Talk to one person across a table, low and sure. Do not announce and do not act.
- **Pace: about three words a second**, the placeholder's pace: brisk, never rushed. Each line has a place it must fit ([`narration.md`](narration.md), "Must end by"). The long ones, `n11`, `n10` and `n8`, have to keep moving; the short ones, `n6b` and `n12`, can breathe.
- **The questions are the hooks.** "So who do you trust to drive?", "So what went wrong?", "So what is it?", "Lucky maps?", "Can a machine learn it instead?", "Can your agent make it home?" Lift a little, then stop dead. Leave the question open; the next picture answers it.
- **Short sentences are full stops.** "No points." "It will not make it." "Nothing broke." Let the voice fall on each, then a small beat.
- **Land the numbers.** Slow a touch on "three seconds", "thirteen metres … twenty-one samples", "Thirty times", "forty-eight percent", "ninety-five times in a hundred", "eight percent to thirty-six", "less than half a point". They are the evidence.
- **Tone by line.** `n3` ("Surely one of them makes it home?") is wry. `n6` and `n7` are sober: a rover dies in each. `n12` is the invitation: warm, direct.
- **Do not hurry the last word of a line.** The tool cuts on silence; a swallowed ending is the one thing it cannot give back.

Recording it well matters more than any processing afterwards:

- **Room:** small and soft. A bedroom, a wardrobe full of clothes, or a duvet over your head. Windows shut, laptop fan and fridge out of earshot, phone in flight mode.
- **Microphone:** a phone's voice-memo app is good enough (choose "lossless" if it offers it); a headset or USB microphone is fine too. Keep it **a hand's width (15 to 20 cm) from your mouth, a little to the side** so your breath does not hit it, and keep that distance for the whole reading.
- **Level:** the loudest words should peak around −12 to −6 dB. If the meter ever touches the top, record again further away: a clipped recording cannot be repaired.
- **Body:** sit upright or stand, take a sip of water, read each line silently once, then say it.
- **Pauses:** two full seconds after every line (count "one thousand one, one thousand two"). Keep pauses inside a line under a second.
- **A slip:** stop, wait two seconds, say the whole line again and carry on. Remember which line it was; the first take is thrown away afterwards with `--drop`.
- **Twice:** do two full read-throughs and keep the better one.

## Splicing: one read-through into the film

`splice` measures the recording's own room noise and voice level, finds the pauses, and takes the long ones as the borders between lines (a pause counts when it is at least half as long as your typical pause between lines). It then cuts out the 15 lines with a quarter of a second of room around each, throws the rest away, and puts each line's first word on its time in the film. A line that is too long for its place is **sped up by at most 12%, pitch unchanged**; if that is not enough the tool says which line, and the next line waits for it.

```bash
python3 lay_narration.py splice my_reading.m4a --dry          # only say what it found; write nothing
python3 lay_narration.py splice my_reading.m4a --drop 4       # block 4 was a slip: throw it away
python3 lay_narration.py splice my_reading.m4a --keep lines/  # also save n1.wav, n2.wav, ... to listen to
python3 lay_narration.py lines lines/                         # after re-recording one of them into that folder
```

| It says | Do this |
|---|---|
| "16 blocks, but the script has 15 lines" | A line was said twice: find it in the list (two blocks of about the same length in a row) and add `--drop` with the number of the bad take. Or a pause inside a line was too long: add `--pause` with a value above it |
| "14 blocks, but the script has 15 lines" | Two lines ran together: add `--pause` with a value below the gap between them, or give the 14 cut times yourself: `--cuts 7.4,16.9,…` (seconds into the reading) |
| "STILL 0.8 s TOO LONG" | Say that line faster or drop a word, record just that line and use `--keep` and `lines`; or allow more speed with `--max-speed 1.18` (above about 15% it starts to sound hurried) |
| "the voice is hardly louder than the room" | Too far from the microphone or too noisy a room: record again, closer |
| A line starts a touch early or late for the picture | `--shift n8=0.2` starts line `n8` 0.2 s later |

Two other ways in, if he prefers: `lines folder/` takes one recording per line (`n1.wav`, `n2.wav`, … with the ids of `narration.md`), and `one take.wav` takes a single take recorded while the film was playing (`--offset` if it did not start on the first frame).

## The radio voice

Unless `--raw` is given, the voice goes through what a radio or trailer voice goes through, in this order:

1. **Level:** brought to one working level, whatever it was recorded at.
2. **High-pass at 75 Hz:** rumble, desk bumps and pops out.
3. **Noise reduction:** steady room noise (fan, hiss) down by about 10 dB.
4. **A soft gate:** the room and the breaths between phrases 12 dB quieter. The pauses between lines and anything said outside the 15 lines are already cut away by `splice`.
5. **De-esser:** hard S sounds tamed.
6. **Tone:** +3 dB around 110 Hz for chest (the depth of a radio voice), −2.5 dB around 320 Hz against the boxy sound of a small room, +3 dB around 4 kHz so consonants come forward, +2 dB of air above 9.5 kHz.
7. **Compressor, 3.5 to 1:** every word at about the same level, which is most of what "professional" sounds like.
8. **Loudness and limiter:** −16 LUFS, the film's level, with nothing above −2 dB.

| To | Add |
|---|---|
| Make the voice a little deeper | `--deeper 1` lowers it one semitone. Try 0.5 to 1.5; above 2 it stops sounding like its owner. The default is 0: the chest in step 6 is the natural kind of deep |
| Hear it untouched, to compare | `--raw` |
| Make the voice louder or quieter against the music | `--voice-gain 2` or `--voice-gain -2` (dB) |

What processing cannot do: remove the echo of a hard, empty room, or repair clipping. A close microphone in a soft room is where the sound comes from.

**Not yet judged by ear.** These settings are common broadcast practice, and were checked by measurement and by a speech recogniser on a synthetic voice (it heard every line, in order). They were written by an AI that cannot listen, and nobody has tuned them on a human voice. Compare with `--raw` and trust your ears. The chain is `voice_chain()` in [`lay_narration.py`](lay_narration.py), one line per step.

## Before it goes anywhere

- The tool prints the film's length, loudness and peak. Expect **119.1 s**, about **−16 LUFS**, a peak below −1 dBFS. The submission allows 2:00 at most; the picture is never lengthened.
- Watch it once with sound: every line over before the next begins, and the moments in [`narration.md`](narration.md) ("What the picture does on which words") roughly on their words.
- [`narration.srt`](narration.srt) holds the draft's words. If the words change, change the subtitles too.

## If the words change

The wording is a draft and may change; the facts may not. Every number in the lines is counted from saved runs, and a build of the film stops if one stops being true. Before changing a claim, read "What the film says, and what holds" in [`../README.md`](../README.md). The lines that carry claims: `n4` (3 centimetres; 9 tries, 1 rock), `n5` (30 times), `n6` (13 metres, 21 samples), `n8` (none beat the planner **on three maps in a row**: keep those words, it is not true of the one-site task; 48 percent; never lost a rover), `n10` (300 worlds; 95 times in 100), `n11` (8 to 36 percent; less than half a point).

## For the agent helping him

- This folder is self-contained: work in it, with paths relative to it. `python3 lay_narration.py --help` lists every option.
- A good session: `--dry` first, read the block list with him, fix the count with `--drop` or `--pause`, then run for real, then listen together. Offer `--deeper 1` and `--raw` as comparisons instead of guessing what he will like.
- Never re-encode or lengthen the picture; fit the voice to it. If a line cannot fit, shorten the line (keeping its facts) before asking for more speed.
- The files here except this README and the script are generated: `python -m tools.manh_demo.make kit --film 2` from the repository root rewrites them from the film as last built (that needs the build set-up in [`../README.md`](../README.md)). Do not edit `timing.json` by hand.
- When he is happy, the narrated film is `manh_demo_2_narrated.mp4` in this folder. Committing it, and whether it becomes the submission video, is the team's decision: say so in `TEAM_STATUS.md` rather than replacing `docs/demo-video/`.
