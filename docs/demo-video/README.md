# Lightlag Traverse: the demo video

Sunday 15 November 2026, about 06:15 Helsinki. Owner: Kristján / Claude Code (Traverse session). This is the **third cut**: the second cut's story (Saturday 23:50, made after Kristján watched the first) with Sunday morning's results in it. At Kristján's word it is the fallback for the submission if the team's recorded-voice film is not ready.

**What changed from the second cut.** The four driving shots, Claude's own words and the reference slide are the same frames and the same narration. Three slides and their lines are new. The results show all 25 campaign runs by nine models from three labs, with Google's top model 0.003 below the reference. The 300-world slide is one sentence shorter and adds the other labs' programs. The learning slide shows Sölvi's final controllers on held-out worlds and the Extra Trees model that picks the planner's strategy, in place of the pilot's development curve. The end card says eight rovers. The second cut is commit `beb0dfb`, and `storyboard.py` still builds it.

**[`lightlag-traverse-demo.mp4`](lightlag-traverse-demo.mp4)**: 1 minute 59 seconds (118.5 s; the Junction guide allows two minutes), 1920×1080, 30 frames a second, narrated, 36 MB. Subtitles: [`lightlag-traverse-demo.srt`](lightlag-traverse-demo.srt). A still for the submission page: [`poster.jpg`](poster.jpg).

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
| 1:13 | Results | The campaign through Harbor: the reference, then nine models from three labs, each with a bar to its best run and a mark for every run (25 in all); stop after one site; do nothing. Gemini 4 Carbon is marked 0.003 below the reference |
| 1:25 | 300 fresh worlds on Modal | Every world of six saved Claude programs against the reference; the pooled count; who won the few worlds the reference did not; the other labs' five one-request programs |
| 1:35 | Models that learn | Sölvi's final controllers on 40 held-out worlds (8% to 36%), then on the campaign, then the Extra Trees model that picks the planner's strategy and scores 0.48 points above the planner alone, under the 1-point bar for replacing it |
| 1:50 | End card | The command that reruns the reference, the live demo on Modal with its eight rovers, the question |

## What the narrator says

| At | Line |
|---|---|
| 0:00 | Thirteen metres from home, carrying 21 samples, this rover's battery runs flat. Its autopilot was written by Claude Opus. Score for this site: zero. |
| 0:11 | This is Lightlag Traverse: one day of driving on Mars-like ground. Every command lands three ticks late, and every position fix is three ticks old. |
| 0:21 | The ground fights back. Wheels slip on sand and slopes, so a rover is rarely where its program thinks. 3 cm too far from a target is a miss; ground too steep trips a safety stop that wipes every queued command. |
| 0:35 | And the only fuel is the sun. At 9% battery, our reference stops and waits for it. Four ticks later, Claude's rover drives its battery to zero, and the site scores nothing. Six ticks of waiting would have saved it. |
| 0:50 | In its own report, Claude says its planner only counted time, and that all three sites were played before it checked one result. Claude doesn't fail at coding. It fails at planning the day. |
| 1:02 | The reference is a planner, not a model. It tracks the rover through the delay, learns how each surface slips, and prices every leg of its route against the sun. |
| 1:13 | The reference scores 0.48. Twenty-five runs by nine models all finish below it. Only Google's top model comes close, at 0.47. Doing nothing scores zero. |
| 1:25 | On Modal, six of Claude's programs replayed 300 fresh worlds each. The reference scored higher 99 times in 100 and never lost a rover. |
| 1:36 | A small policy trained from scratch learns too: from 8% to 36% on unseen worlds, and past every Claude run on the campaign. And a model that picks our planner's strategy edged past the planner, by under half a point. |
| 1:50 | One command reruns it all, and a live demo on Modal plays any world you pick. Can your agent make it home? |

## The worlds Claude's programs won

Kristján asked whether another 300 worlds would give more than 288 wins, and whether the wins are battery luck. Neither, on the evidence:

- **Another 300 worlds would give about the same.** 288 of 300 is the worst of six programs (Sonnet agent 1); at that rate a fresh draw lands between about 281 and 295. Drawing again until the number improves would be choosing the worlds, and the judges can rerun it.
- **The video gives the pooled count from the same rows:** the reference is higher in 1,780 of 1,800 program-and-world pairs (98.9%). Of the other 20, 5 are exact ties and 15 are wins for a Claude program, none by more than 0.041. 13 of the 15 belong to Sonnet agent 1 and Opus agent 3, the two programs that also ran a battery flat on 91 and 157 of the 300 worlds.
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
| Reference 0.476; 25 agent runs by nine models, every one below it; Gemini 4 Carbon 0.473, 0.449 and 0.000 (its session ran out); Claude's best 0.293; stop after site 1 0.149; do nothing 0.000 | Each run's `artifacts/evaluator/result.json` under [`docs/lightlag-runs/campaign-*`](../lightlag-runs/); which model made which run from Manh's ledger, [`docs/tier-comparison/runs.jsonl`](../tier-comparison/runs.jsonl); write-ups: [Claude](../lightlag-traverse-campaign.md), [GPT and Gemini](../tier-comparison.md) |
| The battery chart | The same replays, site 3: the reference, Opus agent 2 (flat at tick 351) and Opus agent 4 (flat at tick 97) |
| 300 fresh worlds: 1,780 of 1,800 pairs to the reference; per program 288 to 300; no reference rover lost; 15 Claude wins, 5 ties, widest win 0.041; 87% (257 of 294) of Claude's lost rovers still had a way home; up to 100 containers, about 6,000 missions in all | `docs/traverse-farm/programs-1/rows.jsonl` and `docs/traverse-farm.md` (the farm session's, on `main`) |
| GPT and Gemini's five one-request programs: the reference higher in 1,485 of 1,500 | [`docs/traverse-farm/programs-tiers/evaluation.json`](../traverse-farm/programs-tiers/evaluation.json) (Manh, on Modal, the same 300 worlds) |
| 40 held-out worlds: before training 0.083, PPO 0.359, replay learner 0.363 (three seeds each), greedy rule 0.380, reference 0.508; PPO home on 117 of 120 missions. The campaign: PPO 0.366, every trained seed above every Claude run (best 0.293), reference 0.476. 47,840 training missions | [`docs/learning-final-results/README.md`](../learning-final-results/README.md) (Sölvi's final report). The controllers choose the next goal above hand-written navigation; they are not fine-tuned language models, and neither beats the greedy rule |
| Extra Trees picking the planner's strategy mid-mission: the planner with it scored 0.48 points above the planner alone on 96 fresh worlds (50.46% against 49.98%; 95% interval +0.27 to +0.72), and 0.28 above on 192 more (−0.07 to +0.52); the bar for replacing the reference was 1 point | [`docs/learned-portfolio-results/final/summary.json`](../learned-portfolio-results/final/summary.json) and [`docs/planner-lab-results/final/summary.json`](../planner-lab-results/final/summary.json) (Kristján's Codex sessions, on Modal). The second figure is the same frozen model as the control of a later round; that round's own Random Forest gained 0.20 and its best fixed strategy 0.35 |
| `harbor run -p harbor/lightlag-traverse-campaign -a oracle`, reward 0.476, about two minutes, the same score on a laptop, on Modal and through Harbor | [`campaign-reference`](../lightlag-runs/campaign-reference/) (0.476257, 94 s); `docs/traverse-farm.md`: the farm repeats it mission for mission |
| The live demo's address | `docs/modal-playbook.md`, `docs/submission-checklist.md` (the farm session's, on `main`) |

The slides read these files when the video is built ([`tools/demo_video/data.py`](../../tools/demo_video/data.py)). The only numbers typed in by hand are four of the farm's totals (257 of 294, 100 containers, 6,000 missions, 105 core-hours), copied from `docs/traverse-farm.md` into named constants there, and the eight rovers of the live site.

## How it was made

- **Picture.** The 3D shots are the real demo page, [`viewer/traverse-campaign.html`](../../viewer/traverse-campaign.html), replaying the saved campaign runs: the rovers move as the replays say, the red MISS and STOPPED labels and the three cards are the page's own. A script drives the page through its own controls and records it frame by frame in headless Chrome on a clock it steps itself ([`tools/demo_video/clock.js`](../../tools/demo_video/clock.js)), so every frame is exact however long it takes to draw. The film adds a title, a chapter label, a few short captions and fades ([`overlay.js`](../../tools/demo_video/overlay.js)). The slides are one canvas page ([`film.html`](../../tools/demo_video/film.html)).
- **Voice.** Kokoro-82M (open weights, Apache-2.0), voice `af_heart` at 1.12 times its normal pace, run in a Docker container with no network ([`voice/`](../../tools/demo_video/voice/)). It is a synthetic voice. No API was called and nothing was paid for.
- **Timing.** The voice model reports when it says each word. Captions, slide build-ups, the missed sample, the two batteries running flat (on the words "flat" and "zero") and the subtitles are placed by those times ([`storyboard.py`](../../tools/demo_video/storyboard.py), and [`storyboard3.py`](../../tools/demo_video/storyboard3.py) for what the third cut changes).
- **Sound.** The narration at −16 LUFS, a quiet wind under it, and a low thud where each battery runs flat. No music.

## What was checked, and what was not

- **Length:** 118.5 s; the build refuses to write a video over 119 s.
- **Words:** a speech recogniser that had not seen the script (Whisper `base.en`, offline) wrote down the finished sound track: 310 of the script's 321 words came back as written. The rest are spellings and near-homophones ("meters", "centimeters", "root" for "route", "two" for "too", "Claudopus" for "Claude Opus", "cloud" for "Claude", "passed" for "past", "one hundred"). It hears every line begin within 0.75 s of where the line was laid, always on the early side, as its word times tend to be. `make check` repeats this.
- **Levels:** −16.2 LUFS integrated, loudness range 4.6 LU, true peak −1.5 dBFS (ffmpeg `ebur128`).
- **Picture:** frames from the three new slides and the end card were looked at for overlaps, cut-off text and timing; the other six shots are the second cut's recordings, unchanged.
- **Not checked by ear.** Claude Code cannot listen. Kristján watched the first cut; nobody has yet watched the third from start to finish. `make assemble --no-bed` gives narration only.

## Rebuild or change it

```sh
docker build -t lightlag-narrator tools/demo_video/voice                                               # once: the voice
docker build -t lightlag-listener -f tools/demo_video/voice/Dockerfile.listen tools/demo_video/voice   # once: only for `check`
export LIGHTLAG_STORYBOARD=storyboard3                                                                 # the third cut; leave unset for the second
uv run --no-project --python 3.12 --with playwright python -m tools.demo_video.make all                # under ten minutes
uv run --no-project --python 3.12 --with playwright python -m tools.demo_video.make check
```

Needs Docker, Google Chrome and ffmpeg. `make voice`, `make capture --only ground,quote` and `make assemble` run one step. To change what is said or shown, edit `storyboard.py` (or `storyboard3.py` for the three slides the third cut replaces): a changed line is spoken again and every cue moves with it. Another voice: `VOICE` there (`am_michael` and `bm_george` are also in the image). Intermediate files go to `tools/demo_video/build/`, which is not committed.

`storyboard.py`, the scenes it uses in `film.html` and `data.build()` are left as they were, because Manh's cut (`tools/manh_demo/`) is built on top of them; the third cut's slides are new scenes (`results3`, `learning3`) and its numbers come from `data.extras()`.
