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
| 3 · Sunday about 04:15, **tool and draft clips only** | Manh's notes after the second build: the film feels a little gimmicky, the narrator's room and echo have to go, the words are too technical, the opening should say what this is, and the final film will carry the team's own recorded voice. So nothing is stitched for now. The tool makes **separate draft clips** to pick from (`make piece`, `make clip`, `make split`, to `tools/manh_demo/build/out/`, not in the repository): the film without narration, the narration alone (dry: no room, no echo; also a deeper take), a lineup of the nine models in three tiers, a card for the reference and the trained RL agent, Modal's name in its green with its mark, sand that is softer and no longer hisses or clicks, and a quiet machinery sound. The script in plain words with a cliffhanger after every beat is [`script-v2.md`](script-v2.md). **The committed film is still the second build**, with the voice treatment Manh has since turned down |
| 4 · Sunday about 04:50, **two more draft pieces** | **An opening** (`make piece --name intro`, 21.6 s): a flat-shaded Mars made from noise turns under a low sun with "MARS" and the signal delay beside it; the camera dives through streaks and dust, comes straight down onto the spot where the rovers start (beside the lander, the reference rover under it), then rises to the page's usual overview, where the title comes up. Silent in space: the wind and the rover sound are cut while the shot is in vacuum (`vacuum` in [`cut.py`](../../tools/manh_demo/cut.py)). **Floating 3D icons** (`make piece --name icons_labs`, 20 s): three of the film's rovers, each with a lab's own logo (Anthropic, Google DeepMind, OpenAI; `lab` and `logo` in [`makers.py`](../../tools/manh_demo/makers.py)) floating over it, in four kinds for Manh to pick from, five seconds each: A a turning coin, B a tile that faces the viewer with one to three pips for the tier, C the bare mark, D the tile on a hairline with a ring on the ground. The marks are cut from their SVG paths by three.js's own SVG loader (`tools/manh_demo/vendor/`, MIT, r187). Both are drafts outside the film; neither is in the committed video |
| 5 · Sunday about 05:00, **the icons over the real environment, and Manh's pick so far** | Three icon pieces now. `make piece --name icons` is the studio with the model families' marks (Claude, Gemini, GPT), the set Manh saw first; `icons_labs` is the same studio with the labs' own logos; **`make piece --name icons_scene`** (25.6 s, [`icons_scene.js`](../../tools/manh_demo/icons_scene.js)) plays the same two moments of the real demo page once for each kind, so they can be compared fairly: three seconds behind a driving rover, then three and a half from overhead with every rover on the map. An icon is life-size beside the rover up close and never smaller than 44 pixels on screen; the reference carries a gold route instead of a lab's mark; the page's name labels and the first cut's framed trackers are off. **Manh's notes:** he likes all four and C, the bare mark, best; from overhead it was a little too big and wanted a hint of contrast, so C is now 35 pixels at its smallest and has a hair-thin dark outline. **Also from his listening:** sand is softer and has lost first its hiss, then its clicks (soft grains that swell in, a rhythm from the treads, a low thud in place of the tick), and the rover has a quiet machinery sound of its own (a whine that climbs with speed, the drive train's tick). For about twenty minutes two sessions worked on the pieces in the same folder; the clips are now kept apart by name (`intro_v2` and `icons_labs` are the side chat's renders) |
| 6 · Sunday about 05:20, **icon C on the film's rovers** | At Manh's word ("Yes, use C"), [`tracker.js`](../../tools/manh_demo/tracker.js) no longer draws the frame, the line and the badge of the first cut: every rover carries its lab's mark as a small solid object just above it, in the chase camera and from overhead, with the hair-thin outline. It is life-size beside the rover up close and, after his third note on size, 29 pixels at its smallest from overhead (44, then 35 before). The reference carries a gold route. A rover whose battery runs out loses its mark at that moment and the page's own red LOST label takes its place; the page's MISS, STOPPED and points notes sit on top of the mark; the rovers standing at the lander stay bare. The page's new "Skip" button on a story card is hidden while recording. The four ground shots were recorded again and cut as clips without narration (`make capture --only cold,world,ground,energy`, then `make clip --shot cold --tag film_cold_icon_c`, and so on). The marks arriving over the rovers are still heard in the two shots that open from overhead; in the cold open they are already there when the camera rises, so those four pips are gone. **The committed film is still the second build**, with the framed trackers |
| 7 · Sunday about 06:05, **the second draft film** | At Manh's word ("compile it onto a next draft demo", and: the replay should carry all the different agents, as a story from the light models to the heavy ones): [`manh_demo_2.mp4`](manh_demo_2.mp4), 119.1 s, built with `make all --film 2`. The plain-words script, the opening from orbit, the lineup, icon C, the score-cards and the card for the planner and the trained agent, compiled; new in it, **a replay with one rover per model** (nine models of three labs and the team's own RL agent) and **a chart of every run of all nine**. See [The second draft](#the-second-draft-manh_demo_2) below. `manh_demo_1.mp4` is still the second build |
| 8 · Sunday about 06:25, **the second draft, second build** | Manh's two notes after watching, and two things the frames showed. **The long text that flashed at 1:04 is gone:** as the first score-card closed, the page's own two paragraphs showed through for three frames while the card faded; the card now keeps its dress while it leaves, and at that hard cut it goes with its picture. **"Was it luck? 300 fresh worlds" now holds all nine models** ("it's only Claude? … such that it includes all the models"): a chart of this cut's own in the look of Kristján's, a row per model with its best program, world by world against the planner; the line says "every model's best program … ninety-five times in a hundred" (2,556 of 2,700). Also: "Ours saw its battery fall" is "Our driver saw …" (a listener hears "hours"), the trained agent's row reads OUR BEST SEED so its sample count is no longer cut off, and each tier sits under its model's name instead of being cut short beside it. Same length, 119.1 s |
| 9 · Sunday about 06:50, **the second draft, third build** | Manh's next notes: keep the 300-world chart as it is but lighter ("perhaps it was too thick"), speed up the first seconds, the nine-models part is "a little bit too long as well, just some jargon", and pull two slides of Kristján's film in: "In Claude's own words" and "And models that learn". So: the opening line is one sentence shorter and the orbit 3.7 s shorter; the lineup rolls out faster with plain words only (6.6 s, was 9.3); Kristján's **quote slide** follows the flagship's rover, since it is that same run's closing report (without his verdict line, which this film says at its end); his **learning slide** of the third cut (Sölvi's final controllers, then the model that picks the planner's strategy) takes the place of this cut's own card for the trained agent; the 300-world strips are thinner. To make room, the results line no longer states the best average, "We wondered too" is gone and several pauses are shorter. Same length, 119.1 s, now twelve shots |
| 10 · Sunday about 07:10, **a narration kit** | Manh: the build without the narrator should have a name that says so and come "in like a package with the draft of the narration which my teammate can read from, and then narrate himself", with a small README his agent can read. [`narration-kit/`](narration-kit/README.md): `manh_demo_2_no_narrator.mp4`, the 15 lines with their times and what the picture does on which words, the lines as subtitles, the placeholder alone as a guide, and `lay_narration.py`, which cuts one read-through into the lines at its pauses, fits each into its place (a line too long is sped up by at most 12%), cleans the voice the way a radio voice is treated and writes the narrated film. The data files are written by `make kit --film 2`. Tried on stand-in readings made from the placeholder (one line said twice, a slow reader, room noise): the recogniser heard all 15 lines in order. Not yet tried with a human voice |
| 11 · Sunday about 07:25, **the planner slide names its methods** | Manh: the film never said what the reference is; "each block diagram should have the name of the method + the text explaining what it is". Above each of the four links of Kristján's planner scene (1:22) there is now a tab with the method behind it, lit with the link: EKF · EXTENDED KALMAN FILTER (three states: position and heading bias), ONLINE SLIP ESTIMATE, DIJKSTRA FIELDS · SUN MODEL, BEAM + ITERATED LOCAL SEARCH. The names are what `lightlag_traverse/pilot.py` and `planning.py` do, and a test looks for each in the code. His scene is drawn untouched underneath. Narration and timing unchanged; the kit's film was written again |

## The second draft: `manh_demo_2`

[`manh_demo_2.mp4`](manh_demo_2.mp4) · [subtitles](manh_demo_2.srt) · 119.1 s · 33.6 MB. **A draft for the team's notes, not the submission video.** Kristján's film stays the main one and `manh_demo_1.mp4` is untouched; this film has its own script, shots and build folder (`tools/manh_demo/build/film2/`). The narrator is a placeholder (the same synthetic voice, two semitones lower, dry) until the team records its own; to record it, start at [`narration-kit/`](narration-kit/README.md): the film without its narrator, the lines with their times, and a tool that lays a recording in.

| From | Shot | What is on screen | Line |
|---|---|---|---|
| 0:00 | `v2_intro` | Mars from orbit, the dive, the landing on our map, the title | n1, n2 |
| 0:16 | `v2_lineup` | Three labs, three tiers, nine models | n3 |
| 0:23 | `v2_fast` | FAST: behind GPT-6 Luna at site 3 as it samples 3 cm too far from a rock | n4 |
| 0:32 | `v2_mid` | BALANCED: Claude Sonnet 5.5 stopped on the scarp of site 3 | n5 |
| 0:39 | `v2_flagship` | FLAGSHIP: behind Claude Opus 5.5 at site 1 until its battery is flat, then its score-card | n6, n6b |
| 0:49 | `v2_quote` | In Claude's own words: two sentences of that run's closing report, and how its three sites ended (Kristján's scene) | n6c |
| 0:58 | `v2_energy` | The sun: Gemini 4 Argon runs flat at site 3; a cut to the planner waiting for light | n7, n7b |
| 1:11 | `v2_tiers` | Every campaign run of all nine models against the planner's score | n8 |
| 1:22 | `v2_reference` | What the planner is (Kristján's scene), with the method behind each of its four links named above it | n9 |
| 1:29 | `v2_farm` | 300 fresh worlds on Modal: every model's best program against the planner, world by world (this cut's chart, in the look of Kristján's) | n10 |
| 1:40 | `v2_learning` | And models that learn: Sölvi's final controllers on held-out worlds and on the campaign, then the model that picks the planner's strategy (Kristján's scene of his third cut) | n11 |
| 1:52 | `v2_end` | The end card (Kristján's scene) | n12 |

The words are `LINES2` in [`cut.py`](../../tools/manh_demo/cut.py) and, as a table, in [`script-v2.md`](script-v2.md).

**Score-cards.** The card that explains a moment is a score-card in this film (`cards: "score"`, in [`tracker.js`](../../tools/manh_demo/tracker.js)): the headline, the lab's mark and the tier, three large numbers with a small label each, and a second later one line with what would have saved the rover or why the planner's way works. Manh found the page's two paragraphs too long and said "Yes, build it" to this version; he has seen it as two clips and has not yet said whether it stays. The numbers are read out of the page's own sentences, so they are the evaluator's.

**Nine models in one replay.** Kristján's page shows his seven Claude runs. For this film the page is built again from a cast of saved runs, one per model, plus the team's trained agent: a folder of links in the build folder, read by his own builder (`viewer/build_traverse.py`, which checks as always that every run played the reference's three worlds). None of his files and none of the runs is changed ([`pages.cast_page`](../../tools/manh_demo/pages.py), `CAST` in [`makers.py`](../../tools/manh_demo/makers.py)). The standings carry each model's mark and its tier.

| Model | Tier | Run that drives | Its campaign score | Why this run |
|---|---|---|---|---|
| Claude Opus 5.5 | flagship | `campaign-agent-opus-2` | 0.120 | the story: flat 13 m from the lander at site 1. Its lowest of four (0.267, 0.247, 0.244, 0.120) |
| Claude Sonnet 5.5 | balanced | `campaign-agent-sonnet-1` | 0.213 | the story: 30 safety stops on the scarp of site 3. The lower of two (0.293, 0.213) |
| Claude Haiku 5.5 | fast | `campaign-agent-haiku-1` | 0.000 | its only run |
| GPT-6.1 Sol | flagship | `campaign-agent-gpt-6.1-sol-1` | 0.353 | the middle of three |
| GPT-6.1 Terra | balanced | `campaign-agent-gpt-6.1-terra-3` | 0.229 | the middle of three |
| GPT-6 Luna | fast | `campaign-agent-gpt-6-luna-1` | 0.110 | the middle of three, and the story: 8 missed samples at site 3, one by 3 cm |
| Gemini 4 Carbon | flagship | `campaign-agent-gemini-4-carbon-1` | 0.449 | the middle of three |
| Gemini 4 Argon | balanced | `campaign-agent-gemini-4-argon-1` | 0.297 | the story: flat at site 3. The only one of its three runs that left the lander (the others scored 0) |
| Gemini 4 Hydrogen | fast | `campaign-agent-gemini-4-hydrogen-1` | 0.404 | the middle of three |
| RL agent · PPO | ours | Sölvi's final policy, seed 43 ([`learned.py`](../../tools/manh_demo/learned.py)) | 0.395 | the best of three seeds, and the standings say so; the slide at 1:40 shows the mean, 0.366 |

**What the film says, and what holds.**

- Three of the nine rovers were picked for what they show, as the table says, and two of those are that model's lowest run. The chart at 1:11 shows all 25 runs, whichever drives in the replay.
- "None beat our driver" is about the three-site campaign, which is what the film shows: the best run scored 0.473 (Gemini 4 Carbon) against the planner's 0.476. On the separate one-site task one Gemini 4 Carbon run scored 0.567 against the planner's 0.565, so the line keeps its "on three maps in a row".
- "Ours brought home forty-eight percent" is the planner's 0.476 on the campaign. "From eight percent to thirty-six on unseen worlds" is Sölvi's PPO before and after training, the mean of three seeds on 40 held-out worlds (0.083 and 0.359); "less than half a point" is the Extra Trees model that picks the planner's strategy, +0.48 points on 96 fresh worlds under the team's 1-point bar. Both are Kristján's numbers for his slide (`tools/demo_video/data.py`, `extras`). That no run reaches the planner and every number the narration states are counted from the runs at every build, and the build stops if one changes (`SAID2` in `cut.py`).
- "Its own report says why" quotes the closing message of the Opus run whose rover has just run flat (`campaign-agent-opus-2`); the two sentences on screen are its words, the narrator's are a paraphrase.
- "The planner won ninety-five times in a hundred" is 2,556 of 2,700 match-ups (94.7%): each model's best program on 300 worlds none of them had seen (seeds 600 to 899, replayed on Modal), against the planner on the same world. Best means the highest mean score there among the programs that model left, which favours the models; counting all 22 programs, the planner is ahead in 6,390 of 6,600, and the chart says so. The programs are from the one-site task and from single requests, not the campaign runs of the replay: Gemini 4 Hydrogen agent run 2 (of 2 programs), GPT-6.1 Sol agent run 3 (of 4), Gemini 4 Carbon agent run 2 (its only one: its single-request reply was cut off before any program), GPT-6.1 Terra agent run 2 (of 4), Claude Opus 5.5 one request (of 3), Gemini 4 Argon one request (its only one), Claude Sonnet 5.5 agent run 1 (of 2), GPT-6 Luna agent run 3 (of 4), Claude Haiku 5.5 one request (its only one). Claude's are Kristján's farm run (`docs/traverse-farm/programs-1`), the others the tier comparison's (`programs-tiers`, `programs-agents-tiers`, `programs-agents-tiers-2`); each program is compared with the reference of its own farm run (the two reference runs differ on one world of 300; neither lost a rover) (`worlds_table` in `makers.py`).
- The quote slide, the planner scene, the learning slide and the end card are Kristján's, with his numbers, read from his page at build time; the learning slide's line about the campaign names Claude's runs only, as in his film.

**Checked.** 119.10 s by ffprobe. The offline recogniser heard 307 of the script's 313 words as written with every layer in; the rest are spellings ("meters"), "ours" heard as "hours", "in a hundred" heard as "and one hundred" and one "what" heard as "it". −16.1 LUFS, loudness range 4.0 LU, true peak −1.9 dBFS. Every chart sound is checked against the chart's own timing, as before, Kristján's two slides included. 25 tests: among them the four moments of the ladder read from the replays (the 3 cm, the 8 misses and 1 sample, the 30 stops from tick 302, the 13 m and 21 samples at tick 409, tick 62), the narration's numbers from the runs and from the 300-world rows, that his scenes are where the shots expect them, and that the nine-model page builds with his files byte for byte unchanged. A contact sheet of sixteen moments and frames of every new shot were looked at after each build, and the frames around the cut where the long text had flashed (clean). **Not checked:** only Manh has watched it, and nobody has listened critically; the pacing was set by measurement, not by eye and ear, and it is tighter now: most pauses between lines are about half a second.

**Change it.** The words and shots: `LINES2` and `shots2` in [`cut.py`](../../tools/manh_demo/cut.py). Which run drives for a model: `CAST` in [`makers.py`](../../tools/manh_demo/makers.py). The chart of all nine and the 300-world chart: `SCENES.tiers` and `SCENES.worlds` in [`scenes.js`](../../tools/manh_demo/scenes.js); which numbers the narration states: `SAID2` in `cut.py`. Then `make all --film 2` (ten minutes; `sg docker -c "… make voice --film 2"` where the shell is not in the docker group), or only a step: `make capture --film 2 --only v2_fast`, `make fit --film 2`, `make assemble --film 2 [--voice clean]`, `make check --film 2`.

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
| The opening's timing (orbit, dive, land, rise) | `addon_settings` and the beats of `intro` in [`cut.py`](../../tools/manh_demo/cut.py); the picture in [`intro.js`](../../tools/manh_demo/intro.js); then `make piece --name intro` |
| The floating icons | [`icons.js`](../../tools/manh_demo/icons.js) (the four kinds are in `BUILD`), the logos and colours in [`makers.py`](../../tools/manh_demo/makers.py); then `make piece --name icons` |
| Look at one moment without recording | `make frames --shot energy --at 3.5,12` (a piece works too: `--shot intro`) writes pictures to `tools/manh_demo/build/frames/` |
