# Lightlag Traverse: the demo video

Saturday 14 November 2026, about 23:00 Helsinki. Owner: Kristján / Claude Code (Traverse session).

**[`lightlag-traverse-demo.mp4`](lightlag-traverse-demo.mp4)**: 1 minute 58 seconds (118.4 s; the Junction guide allows two minutes), 1920×1080, 30 frames a second, narrated, 39 MB. Subtitles: [`lightlag-traverse-demo.srt`](lightlag-traverse-demo.srt). A still for the submission page: [`poster.jpg`](poster.jpg).

**Still to do, by a person:** listen to it once, upload it somewhere public (the guide asks for a public video), and put that link in the README and the platform entry. Nothing has been uploaded.

## What is in it

| From | Shot | On screen |
|---|---|---|
| 0:00 | Cold open | The judged campaign, site 1, from behind the rover whose autopilot Claude Opus wrote (agent run 2). Its battery runs out at tick 409, 13 m from the lander; the camera rises and the demo's story card shows the way home that was still open |
| 0:11 | The task | Site 1 from its first tick: the title, then one caption per rule; a ride behind a rover while the delay and the battery are explained |
| 0:30 | Why Claude struggles | Site 3 in story mode: the reference waits for the sun at 9% battery (tick 93); four ticks later Opus agent 4 runs flat 152 m from the lander |
| 0:51 | In Claude's own words | Two sentences from that Opus run's closing report, and how its three sites ended |
| 1:00 | The reference | What the planner does, beside the battery over the day at site 3 for the reference and two Opus runs |
| 1:13 | Results | The campaign through Harbor: the reference, seven Claude agent runs, stop after one site, do nothing |
| 1:27 | 300 fresh worlds on Modal | Every world of six saved Claude programs against the reference |
| 1:38 | A policy that learns | The PPO pilot trained on Modal, against a greedy controller and the reference |
| 1:50 | End card | The command that reruns the reference, the live demo on Modal, the question |

## What the narrator says

| At | Line |
|---|---|
| 0:00 | Thirteen metres from home, carrying 21 samples, this rover's battery runs flat. Its autopilot was written by Claude Opus. Score for this site: zero. |
| 0:11 | This is Lightlag Traverse, a reinforcement learning environment. An agent drives a rover across Mars-like ground, and every command lands three ticks late. The sun charges the battery; driving drains it. More targets than a day allows, three sites in a row, no reset. Every rule is public. |
| 0:30 | Claude doesn't fail at coding. Within minutes, it writes a real autopilot. It fails at planning a whole day: the route, the battery, the way home. |
| 0:39 | Here, at 9% battery, our reference waits for the sun. |
| 0:44 | Four ticks later, Claude's rover drives its battery to zero. Waiting six ticks would have brought it home. |
| 0:51 | Claude's own report: the planner only counted time. Its program played all three sites in under a minute, before Claude checked a single result. |
| 1:01 | The reference is a planner, not a model. It tracks the rover through the delay, learns how each terrain slips, and prices every leg of its route against the sun. It is always home before the day ends. |
| 1:13 | Through Harbor and OpenCode, the reference scores 0.48. Seven Claude runs, across Opus, Sonnet and Haiku, all score below 0.3. Three lost a rover. Doing nothing scores zero. |
| 1:27 | Was that luck? On Modal, we replayed six of Claude's programs on 300 fresh worlds. The reference won at least 288 times, and never lost a rover. |
| 1:38 | Also on Modal, a small policy trained from scratch improves from 0.09 to 0.38 in development, still short of a greedy controller and the reference. |
| 1:50 | One command reruns it all, and a live demo on Modal plays any world you pick. Can your agent make it home? |

## Where each number comes from

| In the video | Source |
|---|---|
| Site 1: battery flat at tick 409, 13 m from the lander, 21 samples worth 0.40 of the site; waiting 7 ticks would have reached it | The replay of [`campaign-agent-opus-2`](../lightlag-runs/campaign-agent-opus-2/); the card's text is the demo page's own ([`viewer/traverse_story.py`](../../viewer/traverse_story.py)) |
| 600 m × 400 m, commands 3 ticks late, 46 targets, three sites, five tools | Rules 0.1.0 and the campaign task ([`harbor/lightlag-traverse-campaign/`](../../harbor/lightlag-traverse-campaign/)) |
| Site 3: the reference waits at 9.1% (tick 93); Opus agent 4 flat at tick 97, 152 m out; 6 ticks of waiting would have reached the lander | The replays of [`campaign-reference`](../lightlag-runs/campaign-reference/) and [`campaign-agent-opus-4`](../lightlag-runs/campaign-agent-opus-4/), through `viewer/traverse_story.py` |
| The two quoted sentences | [`campaign-agent-opus-2/agent/opencode.txt`](../lightlag-runs/campaign-agent-opus-2/agent/opencode.txt), word for word; "…" marks the file name left out |
| Reference 0.476; Claude 0.293, 0.267, 0.247, 0.244, 0.213, 0.120, 0.000; three runs lost a rover; stop after site 1 0.149; do nothing 0.000 | Each run's `artifacts/evaluator/result.json` under [`docs/lightlag-runs/campaign-*`](../lightlag-runs/); [write-up](../lightlag-traverse-campaign.md) |
| The battery chart | The same replays, site 3: the reference, Opus agent 2 (flat at tick 351) and Opus agent 4 (flat at tick 97) |
| 300 fresh worlds: the reference higher on 288 to 300 for each of six programs; no reference rover lost; 87% (257 of 294) of Claude's lost rovers still had a way home; about 6,000 missions and 105 core-hours, up to 100 containers | `docs/traverse-farm/programs-1/rows.jsonl` and `docs/traverse-farm.md` (the farm session's, on `main`) |
| PPO from scratch 0.087 → 0.377 (three seeds), greedy controller 0.381, reference 0.514 | [`docs/learning-campaign-results/pilot/README.md`](../learning-campaign-results/pilot/README.md) (Sölvi's pilot). **A development result**: its 32 validation worlds were looked at repeatedly and are not held out; the untouched final worlds stay closed until the weights are frozen |
| `harbor run -p harbor/lightlag-traverse-campaign -a oracle`, reward 0.476, about two minutes, the same score on a laptop, on Modal and through Harbor | [`campaign-reference`](../lightlag-runs/campaign-reference/) (0.476257, 94 s); `docs/traverse-farm.md`: the farm repeats it mission for mission |
| The live demo's address | `docs/modal-playbook.md`, `docs/submission-checklist.md` (the farm session's, on `main`) |

The slides read these files when the video is built ([`tools/demo_video/data.py`](../../tools/demo_video/data.py)). The only numbers typed in by hand are four of the farm's totals (257 of 294, 100 containers, 6,000 missions, 105 core-hours), copied from `docs/traverse-farm.md` into named constants there.

## How it was made

- **Picture.** The 3D shots are the real demo page, [`viewer/traverse-campaign.html`](../../viewer/traverse-campaign.html), replaying the saved campaign runs: the rovers move as the replays say, and the two cards are the page's own story mode. A script drives the page through its own controls and records it frame by frame in headless Chrome on a clock it steps itself ([`tools/demo_video/clock.js`](../../tools/demo_video/clock.js)), so every frame is exact however long it takes to draw. The film adds a title, a chapter label, short captions and fades ([`overlay.js`](../../tools/demo_video/overlay.js)). The slides are one canvas page ([`film.html`](../../tools/demo_video/film.html)).
- **Voice.** Kokoro-82M (open weights, Apache-2.0), voice `af_heart` at 1.12 times its normal pace, run in a Docker container with no network ([`voice/`](../../tools/demo_video/voice/)). It is a synthetic voice. No API was called and nothing was paid for.
- **Timing.** The voice model reports when it says each word. Captions, slide build-ups, the two batteries running flat (on the words "flat" and "zero") and the subtitles are placed by those times ([`storyboard.py`](../../tools/demo_video/storyboard.py)).
- **Sound.** The narration at −16 LUFS, a quiet wind under it, and a low thud where each battery runs flat. No music.

## What was checked, and what was not

- **Length:** 118.4 s; the build refuses to write a video over 119 s.
- **Words:** a speech recogniser that had not seen the script (Whisper `base.en`, offline) wrote down the finished sound track: 304 of the script's 310 words came back as written. The other six are spellings and near-homophones ("meters", "root" for "route", "Clodopus" for "Claude Opus", "the" for "this", "train" for "trained") and one stray "set". It hears every line begin within 0.75 s of where the line was laid, always on the early side, as its word times tend to be. `make check` repeats this.
- **Levels:** −16.1 LUFS integrated, loudness range 4 LU, true peak −1.5 dBFS (ffmpeg `ebur128`).
- **Picture:** frames from every shot and every cut were looked at for overlaps, cut-off text and timing. No one has watched it in motion from start to finish.
- **Not checked by ear.** Claude Code cannot listen. Whether the voice sounds right, and whether the wind and the thuds sit well under it, needs a person. `make assemble --no-bed` gives narration only.

## Rebuild or change it

```sh
docker build -t lightlag-narrator tools/demo_video/voice                                               # once: the voice
docker build -t lightlag-listener -f tools/demo_video/voice/Dockerfile.listen tools/demo_video/voice   # once: only for `check`
uv run --no-project --python 3.12 --with playwright python -m tools.demo_video.make all                # under ten minutes
uv run --no-project --python 3.12 --with playwright python -m tools.demo_video.make check
```

Needs Docker, Google Chrome and ffmpeg. `make voice`, `make capture --only why,learning` and `make assemble` run one step. To change what is said or shown, edit `storyboard.py`: a changed line is spoken again and every cue moves with it. Another voice: `VOICE` there (`am_michael` and `bm_george` are also in the image). Intermediate files go to `tools/demo_video/build/`, which is not committed.

If the final learning run reports a later checkpoint, `data.py` reads the pilot's README: point `learning()` at the new table, change line `m2`, and rebuild `learning`.
