# manh_demo_1: a more cinematic cut of the demo video

Sunday 15 November 2026, about 01:13 Helsinki (second build). Owner: Manh / Claude Code (demo cut chat).

**[`manh_demo_1.mp4`](manh_demo_1.mp4)**: 1 minute 59 seconds (119.1 s; the Junction guide allows two minutes), 1920×1080, 30 frames a second, narrated, 32 MB. Subtitles: [`manh_demo_1.srt`](manh_demo_1.srt). A still: [`poster.jpg`](poster.jpg).

**Kristján's video stays the main one.** [`docs/demo-video/lightlag-traverse-demo.mp4`](../demo-video/lightlag-traverse-demo.mp4) is the team's demo until the team approves this cut. This is iteration 1 of Manh's version, made to be changed. Nothing is uploaded.

**Manh has listened to the first build** and asked for one change, made in the second build below; he called every other sound perfect. Claude Code cannot hear: the levels were set by measurement. See [what was not checked](#what-was-checked-and-what-was-not).

## Builds

| Build | Change |
|---|---|
| 1 · Sunday about 01:00 | The first cut |
| 2 · Sunday about 01:13 | **Two echoes removed, at Manh's word after listening.** The first build also sent "zero." (0:10) and "saved it." (0:49) into the long echo. No chart or interface sound plays at those two moments, so the echo's tail was the loudest thing once the voice stopped and came across as a whoosh. Measured after each word, the second that follows is now 5 and 6.5 LU quieter (−32.7 and −33.7 LUFS). The picture is byte for byte the same, the two echoes that remain are unchanged, and everything else is within 0.05 dB of the first build |
| 3 · Sunday about 05:00, **tool and draft clips only** | Manh's notes after the second build: the film feels a little gimmicky, the narrator's room and echo have to go, the words are too technical, the opening should say what this is, and the final film will carry the team's own recorded voice. So nothing is stitched for now. The tool makes **separate draft clips** to pick from (`make piece`, `make clip`, `make split`, to `tools/manh_demo/build/out/`, not in the repository): the film without narration, the narration alone (dry: no room, no echo; also a deeper take), a lineup of the nine models in three tiers, a card for the reference and the trained RL agent, Modal's name in its green with its mark, sand that is softer and no longer hisses or clicks, and a quiet machinery sound. The script in plain words with a cliffhanger after every beat is [`script-v2.md`](script-v2.md). **The committed film is still the second build**, with the voice treatment Manh has since turned down |

## What is the same

The story, the script, the narrator's voice, every number and every replay are Kristján's second cut, read from his files each time this is built ([`tools/demo_video/storyboard.py`](../../tools/demo_video/storyboard.py), [`film.html`](../../tools/demo_video/film.html), [`data.py`](../../tools/demo_video/data.py)). For what is said, the source of each number and how the picture is recorded, read [his README](../demo-video/README.md). None of his files is edited.

## What is new

| Manh asked for | What the cut does |
|---|---|
| A logo tracker over the AI rovers in the top-down shots | In every top-down shot each rover gets a frame around it, a line and a badge with **the logo of the lab whose model drives it** and its name. The rover the story is about gets a large badge, the others a small one. The reference is a planner, not a model, so it gets a gold route tile instead of a logo. A lost rover's badge turns red and says LOST |
| The logo on the explanation of a failure | The card that explains a moment (BATTERY FLAT, THE REFERENCE PACES ITSELF) carries the tile and "CLAUDE · ANTHROPIC" beside the run's name |
| The same anywhere a model is named | Logo tiles in the standings, beside the rover's name label in the chase camera, in the top-left tag, and in front of every model on the results chart and the 300-world chart |
| Gravel under the rover | In the chase-camera shots: short grains of noise, more of them the faster the rover really drives. The grain changes with the ground it is really on: regolith, sand (a finer hiss), a rock field (lower, with clacks), bedrock |
| A small rumbling engine, subliminal | A low electric motor whose pitch follows the rover's real speed. Most of it is below 150 Hz: felt on headphones, nearly absent on a laptop. It idles when the rover stops and winds down when the battery dies |
| Quiet, clean, flowing sounds under the charts | One sound for each thing that moves on a chart, at the moment the chart moves it: air sliding up as a bar grows (further for a higher score), long moving air while a line draws itself, a soft note when a link lights or a number lands, a low note under a verdict |
| A cinematic voice effect on the narrator | The same voice, produced like a trailer voice: rumble out, more chest, a compressor that holds every syllable near one level, the hissing consonants held back, a short room around it, and **a long echo on the last word** of two lines: the verdict ("planning the day.") and the last question ("make it home?") |
| At most 2:00, ideally 1:59 | 119.1 s. The last card is held until the film is exactly that long, so a player shows 1:59 whether it rounds down or to the nearest second |

Other ideas put in, each easy to take out again:

- **The battery dies like a power cut.** Where a battery runs flat the picture drops dark for a moment, red closes in from the edges and the ground comes back with some of its colour drained. Behind a rover that is nearly empty, a low double warning pip comes faster as the battery drains, and stops with it.
- **The top-down moment is held longer.** In the opening of "This is Lightlag Traverse" the camera drops in half a second later than in Kristján's cut, so the trackers have about two seconds over the rovers as they leave the lander.
- **The title lands on its own**, a quarter of a second before the narrator names it, with a low note under it.
- **One held note under the film.** A low D and its fifth, very quiet, that swells into the title and into the last question. Every note of every chart sound is taken from the same scale, so nothing clashes with it.
- **The cameras and the cuts are heard.** A breath of air when the camera rises or drops in, at the one hard cut, and under each fade between shots. The trackers lock on with a run of quick pips; a card slides up with a low note; the way home draws itself in eleven rising pips.
- **A vignette** on the ground shots and behind the charts, and a warm light that drifts slowly behind the charts.

## How loud everything is

Measured on the finished track (K-weighted loudness, the scale broadcast uses; the voice is the reference):

| Layer | Loudness where it sounds | Under the voice by |
|---|---|---|
| Narration | −16.0 LUFS | |
| Rover (gravel, rolling, motor) | about −39 LUFS: the gravel leads, the motor is 7 LU under it | about 22 LU |
| Chart and interface sounds | about −45 LUFS in the middle, a few louder moments | about 29 LU |
| The two batteries running flat | −22 LUFS for a second each | 6 LU: the two loud moments of the film |
| Wind | about −44 LUFS | about 28 LU |
| The held note | about −40 LUFS | about 24 LU |

Everything but the voice also steps back while the narrator speaks (the rover by 3.5 dB, the note by 4, the wind by 3, the chart sounds by 1.5).

## What was checked, and what was not

- **Length:** 119.10 s by ffprobe, picture and sound. The build refuses anything over 119.4 s.
- **Words:** the same offline speech recogniser Kristján used (Whisper `base.en`, which has not seen the script) wrote down the finished sound track with every layer in: 304 of the script's 316 words came back as written, against 305 for his cut. The differences are the same spellings and near-homophones ("meters", "centimeters", "root", "two", "Clod").
- **Levels:** −16.0 LUFS integrated, loudness range 4.3 LU, true peak −3.6 dBFS (ffmpeg `ebur128`); Kristján's cut reads −16.2 LUFS.
- **Sounds sit on the picture:** every chart sound is checked against the moments the chart really used while it was recorded; the build stops if one has drifted. The rover's sound is made from what the recorder saw in each frame.
- **Picture:** frames from every shot were looked at for overlaps and cut-off text, at the tracker moments in particular.
- **Kristján's files:** unchanged; a test compares them before and after the build's copies are made. 14 tests (`python3 -m unittest discover -s tests/manh_demo -v`; the 4 sound tests need numpy, scipy and soundfile).
- **Checked by one pair of ears.** Manh listened to the first build and asked for the two echoes above to go; nobody else has heard it, and nobody has yet heard the second build. Whether the motor is subliminal or simply inaudible on a given pair of speakers, only a person there can say. Each layer is a file of its own in `tools/manh_demo/build/audio/` (`voice.wav`, `rover.wav`, `charts.wav`, `wind.wav`, `music.wav`), so one can be listened to alone.
- **A different typeface.** Kristján's pages ask for DIN Condensed, which only macOS has. This cut was built on Linux with Barlow Condensed (and Inter, JetBrains Mono) in its place, so letters are a little rounder than in his video. The layouts were checked to hold.
- **The marks** are the Simple Icons paths for Claude, OpenAI and DeepMind (CC0). The logos are trademarks of their owners and are used only to name the maker of a model on screen. Only Claude appears in this cut; OpenAI and Google DeepMind are registered for the demos to come ([`makers.py`](../../tools/manh_demo/makers.py)).

## Change it

```sh
python3.12 -m venv tools/manh_demo/build/venv
tools/manh_demo/build/venv/bin/pip install playwright numpy scipy soundfile
tools/manh_demo/build/venv/bin/python -m playwright install chromium
docker build -t lightlag-narrator tools/demo_video/voice             # once: Kristján's voice container
tools/manh_demo/build/venv/bin/python -m tools.manh_demo.make all    # about ten minutes
```

On a machine whose shell is not in the docker group yet, wrap the steps that speak or listen: `sg docker -c "… make voice"`.

| To change | Do this |
|---|---|
| A level | `MIX` at the top of [`tools/manh_demo/sound.py`](../../tools/manh_demo/sound.py), then `make assemble` (a minute; nothing is recorded again) |
| Leave a layer out | `make assemble --mute rover,music` (layers: `rover`, `charts`, `music`, `wind`, `echo`, `treat`; `--mute echo,treat` gives Kristján's plain voice) |
| Which words echo | `THROWS` in [`cut.py`](../../tools/manh_demo/cut.py) |
| The trackers, the card, the power cut | [`tracker.js`](../../tools/manh_demo/tracker.js), then `make capture --only cold,world,energy` and `make assemble` |
| The logos on the charts, the chart sounds' timing | [`scenes.js`](../../tools/manh_demo/scenes.js) |
| A new maker | one entry in [`makers.py`](../../tools/manh_demo/makers.py) and its mark in `tools/manh_demo/logos/` |
| What is said or shown | Kristján's `storyboard.py`: this cut follows it. Then `make all` |
| Look at one moment without recording | `make frames --shot energy --at 3.5,12` writes pictures to `tools/manh_demo/build/frames/` |
