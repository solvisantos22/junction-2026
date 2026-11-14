# Lightlag Traverse: the demo video

Saturday 14 November 2026, about 23:50 Helsinki. Owner: Kristján / Claude Code (Traverse session). This is the second cut, made after Kristján watched the first.

**[`lightlag-traverse-demo.mp4`](lightlag-traverse-demo.mp4)**: 1 minute 57 seconds (117.5 s; the Junction guide allows two minutes), 1920×1080, 30 frames a second, narrated, 35 MB. Subtitles: [`lightlag-traverse-demo.srt`](lightlag-traverse-demo.srt). A still for the submission page: [`poster.jpg`](poster.jpg).

**Not uploaded, at Kristján's word.** The guide asks for a public video: when he uploads it, the link goes in the README and the platform entry.

## What is in it

| From | Shot | On screen |
|---|---|---|
| 0:00 | Cold open | The judged campaign, site 1, from behind the rover whose autopilot Claude Opus wrote (agent run 2). Its battery runs out at tick 409, 13 m from the lander; the camera rises and the demo's story card shows the way home that was still open |
| 0:11 | The world | Site 1 under the title, then a ride behind a rover while the delay is explained; the ring it trails is its last position fix |
| 0:21 | The ground | Site 3, two rovers of the judged run. Opus agent 2 samples 2.53 m from a target that wants 2.5 m: a miss. Sonnet agent 1 is stopped on the lip of the scarp for ground too steep, one of its 30 safety stops at this site |
| 0:35 | Energy | Site 3 in story mode: the reference stops and waits for the sun at 9% battery (tick 93); four ticks later Opus agent 4 runs flat 152 m from the lander |
| 0:50 | In Claude's own words | Two sentences from Opus agent 2's closing report, how its three sites ended, and the verdict |
| 1:02 | The reference | What the planner does, as a chain that lights up link by link, over the battery through the day at site 3 for the reference and two Opus runs |
| 1:13 | Results | The campaign through Harbor: the reference, seven Claude agent runs, stop after one site, do nothing |
| 1:25 | 300 fresh worlds on Modal | Every world of six saved Claude programs against the reference; the pooled count; who won the few worlds the reference did not |
| 1:41 | A policy that learns | The PPO pilot trained on Modal, against a greedy controller and the reference |
| 1:49 | End card | The command that reruns the reference, the live demo on Modal, the question |

## What the narrator says

| At | Line |
|---|---|
| 0:00 | Thirteen metres from home, carrying 21 samples, this rover's battery runs flat. Its autopilot was written by Claude Opus. Score for this site: zero. |
| 0:11 | This is Lightlag Traverse: one day of driving on Mars-like ground. Every command lands three ticks late, and every position fix is three ticks old. |
| 0:21 | The ground fights back. Wheels slip on sand and slopes, so a rover is rarely where its program thinks. 3 cm too far from a target is a miss; ground too steep trips a safety stop that wipes every queued command. |
| 0:35 | And the only fuel is the sun. At 9% battery, our reference stops and waits for it. Four ticks later, Claude's rover drives its battery to zero, and the site scores nothing. Six ticks of waiting would have saved it. |
| 0:50 | In its own report, Claude says its planner only counted time, and that all three sites were played before it checked one result. Claude doesn't fail at coding. It fails at planning the day. |
| 1:02 | The reference is a planner, not a model. It tracks the rover through the delay, learns how each surface slips, and prices every leg of its route against the sun. |
| 1:13 | Through Harbor, the reference scores 0.48. Seven Claude runs, from Haiku to Opus, all finish below 0.3, and three lost a rover. Doing nothing scores zero. |
| 1:25 | On Modal, six of Claude's programs replayed 300 fresh worlds each. The reference scored higher 99 times in 100 and never lost a rover. Claude's few wins were narrow, mostly from programs that ran flat on up to half their worlds. |
| 1:41 | A policy trained there from scratch learns too: in development it reaches 0.38, still short of the reference. |
| 1:50 | One command reruns it all, and a live demo on Modal plays any world you pick. Can your agent make it home? |

## The worlds Claude's programs won

Kristján asked whether another 300 worlds would give more than 288 wins, and whether the wins are battery luck. Neither, on the evidence:

- **Another 300 worlds would give about the same.** 288 of 300 is the worst of six programs (Sonnet agent 1); at that rate a fresh draw lands between about 281 and 295. Drawing again until the number improves would be choosing the worlds, and the judges can rerun it.
- **The video now gives the pooled count from the same rows:** the reference is higher in 1,780 of 1,800 program-and-world pairs (98.9%). Of the other 20, 5 are exact ties and 15 are wins for a Claude program, none by more than 0.041. 13 of the 15 belong to Sonnet agent 1 and Opus agent 3, the two programs that also ran a battery flat on 91 and 157 of the 300 worlds.
- **It does not call them luck.** The farm session recorded the 15 missions again on Modal (`docs/traverse-farm/claude-wins-battery.json`, `docs/traverse-farm.md`, on `main`): in 5 the rover had dipped below 5% battery before winning, in 10 it never went below 8%. So a third were near misses and two thirds were narrow wins outright.

## Where each number comes from

| In the video | Source |
|---|---|
| Site 1: battery flat at tick 409, 13 m from the lander, 21 samples worth 0.40 of the site; waiting 7 ticks would have reached it | The replay of [`campaign-agent-opus-2`](../lightlag-runs/campaign-agent-opus-2/); the card's text is the demo page's own ([`viewer/traverse_story.py`](../../viewer/traverse_story.py)) |
| 600 m × 400 m, commands 3 ticks late and fixes 3 ticks old, the 36% tilt limit, a sample within 2.5 m, three sites, five tools | Rules 0.1.0 and the campaign task ([`harbor/lightlag-traverse-campaign/`](../../harbor/lightlag-traverse-campaign/)) |
| Site 3, tick 46: Opus agent 2 samples 2.53 m from the nearest target (7 missed samples at that site; the reference missed none) | The replay of `campaign-agent-opus-2`, through `viewer/traverse_story.py` |
| Site 3, tick 302: Sonnet agent 1 stopped for ground too steep (30 safety stops at that site; the reference none) | The replay of [`campaign-agent-sonnet-1`](../lightlag-runs/campaign-agent-sonnet-1/), through `viewer/traverse_story.py` |
| Site 3: the reference waits at 9.1% (tick 93) and is never below 7% that day; Opus agent 4 flat at tick 97, 152 m out; 6 ticks of waiting would have reached the lander | The replays of [`campaign-reference`](../lightlag-runs/campaign-reference/) and [`campaign-agent-opus-4`](../lightlag-runs/campaign-agent-opus-4/), through `viewer/traverse_story.py` |
| The two quoted sentences | [`campaign-agent-opus-2/agent/opencode.txt`](../lightlag-runs/campaign-agent-opus-2/agent/opencode.txt), word for word; "…" marks the file name left out |
| Reference 0.476; Claude 0.293, 0.267, 0.247, 0.244, 0.213, 0.120, 0.000; three runs lost a rover; stop after site 1 0.149; do nothing 0.000 | Each run's `artifacts/evaluator/result.json` under [`docs/lightlag-runs/campaign-*`](../lightlag-runs/); [write-up](../lightlag-traverse-campaign.md) |
| The battery chart | The same replays, site 3: the reference, Opus agent 2 (flat at tick 351) and Opus agent 4 (flat at tick 97) |
| 300 fresh worlds: 1,780 of 1,800 pairs to the reference; per program 288 to 300; no reference rover lost; 15 Claude wins, 5 ties, widest win 0.041; 87% (257 of 294) of Claude's lost rovers still had a way home; up to 100 containers, about 6,000 missions in all | `docs/traverse-farm/programs-1/rows.jsonl` and `docs/traverse-farm.md` (the farm session's, on `main`) |
| PPO from scratch 0.087 → 0.377 (three seeds), greedy controller 0.381, reference 0.514 | [`docs/learning-campaign-results/pilot/README.md`](../learning-campaign-results/pilot/README.md) (Sölvi's pilot). **A development result**: its 32 validation worlds were looked at repeatedly and are not held out; the untouched final worlds stay closed until the weights are frozen |
| `harbor run -p harbor/lightlag-traverse-campaign -a oracle`, reward 0.476, about two minutes, the same score on a laptop, on Modal and through Harbor | [`campaign-reference`](../lightlag-runs/campaign-reference/) (0.476257, 94 s); `docs/traverse-farm.md`: the farm repeats it mission for mission |
| The live demo's address | `docs/modal-playbook.md`, `docs/submission-checklist.md` (the farm session's, on `main`) |

The slides read these files when the video is built ([`tools/demo_video/data.py`](../../tools/demo_video/data.py)); what they drew from is saved as [`tools/demo_video/data/film_data.json`](../../tools/demo_video/data/film_data.json). The only numbers typed in by hand are four of the farm's totals (257 of 294, 100 containers, 6,000 missions, 105 core-hours), copied from `docs/traverse-farm.md` into named constants there.

## How it was made

- **Picture.** The 3D shots are the real demo page, [`viewer/traverse-campaign.html`](../../viewer/traverse-campaign.html), replaying the saved campaign runs: the rovers move as the replays say, the red MISS and STOPPED labels and the three cards are the page's own. A script drives the page through its own controls and records it frame by frame in headless Chrome on a clock it steps itself ([`tools/demo_video/clock.js`](../../tools/demo_video/clock.js)), so every frame is exact however long it takes to draw. The film adds a title, a chapter label, a few short captions and fades ([`overlay.js`](../../tools/demo_video/overlay.js)). The slides are one canvas page ([`film.html`](../../tools/demo_video/film.html)).
- **Voice.** Kokoro-82M (open weights, Apache-2.0), voice `af_heart` at 1.12 times its normal pace, run in a Docker container with no network ([`voice/`](../../tools/demo_video/voice/)). It is a synthetic voice. No API was called and nothing was paid for.
- **Timing.** The voice model reports when it says each word. Captions, slide build-ups, the missed sample, the two batteries running flat (on the words "flat" and "zero") and the subtitles are placed by those times ([`storyboard.py`](../../tools/demo_video/storyboard.py)).
- **Sound.** The narration at −16 LUFS, a quiet wind under it, and a low thud where each battery runs flat. No music.

## What was checked, and what was not

- **Length:** 117.5 s; the build refuses to write a video over 119 s.
- **Words:** a speech recogniser that had not seen the script (Whisper `base.en`, offline) wrote down the finished sound track: 305 of the script's 316 words came back as written. The rest are spellings and near-homophones ("meters", "centimeters", "root" for "route", "two" for "too", "Clodopus" for "Claude Opus", "the sight" for "this site", "finished", "one hundred", "train"). It hears every line begin within 0.75 s of where the line was laid, always on the early side, as its word times tend to be. `make check` repeats this.
- **Levels:** −16.2 LUFS integrated, loudness range 4.9 LU, true peak −1.5 dBFS (ffmpeg `ebur128`).
- **Picture:** frames from every shot and every cut were looked at for overlaps, cut-off text and timing.
- **Not checked by ear.** Claude Code cannot listen. Kristján watched the first cut; nobody has yet watched this one from start to finish. `make assemble --no-bed` gives narration only.

## Rebuild or change it

```sh
docker build -t lightlag-narrator tools/demo_video/voice                                               # once: the voice
docker build -t lightlag-listener -f tools/demo_video/voice/Dockerfile.listen tools/demo_video/voice   # once: only for `check`
uv run --no-project --python 3.12 --with playwright python -m tools.demo_video.make all                # under ten minutes
uv run --no-project --python 3.12 --with playwright python -m tools.demo_video.make check
```

Needs Docker, Google Chrome and ffmpeg. `make voice`, `make capture --only ground,quote` and `make assemble` run one step. To change what is said or shown, edit `storyboard.py`: a changed line is spoken again and every cue moves with it. Another voice: `VOICE` there (`am_michael` and `bm_george` are also in the image). Intermediate files go to `tools/demo_video/build/`, which is not committed.

If the final learning run reports a later checkpoint, `data.py` reads the pilot's README: point `learning()` at the new table, change line `m2`, and rebuild `learning`.
