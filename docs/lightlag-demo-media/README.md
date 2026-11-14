# Lightlag evidence recording

[Play or download the silent first cut](first-cut-v1/lightlag-selected-case.webm):
**62 seconds, 1920×1080, 16:9, 12 fps, WebM/VP9, 1,479,361 bytes** (1.48 MB).
This is a recorded replay of one selected case, with a checked post-hoc
continuation. It is not a live model rollout or a fresh successful model trial.
No external upload or submission has been made.

The clip records the existing [offline decision page](../../viewer/decisions.html),
without changing its source or embedded evidence. Side captions guide the
recording; both saved trajectories advance together through the page's existing
tick control. Camera timing is editorial, not wall-clock mission timing.
The original eight-run context remains visible: **3 model wins, 2 ties and
3 deficits** against the frozen original reference. This selected example does
not estimate failure prevalence.

## Story

| Video time | Evidence shown |
|---|---|
| 0–6 s | Selected noisy seed 504; delay 3, horizon 50, starting energy 100; full mixed-results context. |
| 6–16 s | Tick 25: the return is still queued for ticks 26–27. Call 21 adds 8.1 m of driving plus sampling, committing 11.1 action energy. |
| 16–22 s | The accepted return completes at tick 27. Both are home; only the actual run has the extra excursion queued for ticks 29–31. |
| 22–34 s | Synchronized saved replays advance through the excursion and subsequent idle drain. |
| 34–38 s | Actual energy exhaustion at tick 47, then the final ticks. The post-hoc branch remains alive at home. |
| 38–43 s | Tick 50: actual 0/10; checked continuation 6/10, alive at home, battery 9.33. |
| 43–54 s | Battery curves and fixed contract: every 50-tick survivor pays 25 idle energy. Returning home neither recharges nor stops the clock. |
| 54–62 s | Source links and limits: selected case, post-hoc branch, no fresh successful model attempt. |

The [plain narration script](first-cut-v1/narration.md) is supplied for a future
voiceover; the video itself has **no audio stream**. The branch includes all
public calls through call 20, followed by no new commands. Already accepted
commands still execute. The complete [original comparison](../lightlag-fixed-seed-comparison.md)
and [checked branch](../lightlag-audits/fixed-seeds501-504/rush-noisy-seed504-delay3-opus-5-5/stop-check.json)
remain the scientific evidence; the clip is a presentation of them.

## Verification

The [automated verification](first-cut-v1/verification.json) records source,
payload, script, encoder and video hashes; software versions; the storyboard;
decoded checkpoints; and evidence assertions. The
[visual review](first-cut-v1/visual-review.json) records inspection of seven
decoded frames: opening, queued return, home at 27, death at 47, final tick 50,
idle contract and closing limits. Maps, queues, scores and captions are visible
without overlap at the recorded resolution. Full-resolution intermediate
frames and encoder logs remain in temporary storage, not the repository.

Chrome loaded the final WebM, reported **62.000 seconds and 1920×1080**, sought
to each checkpoint, advanced in real playback, and reached the end without a
media error. A separate encoder inspection confirmed one VP9 video stream at
12 fps and no audio stream. The final repository copy matches the verified
temporary output byte for byte. There were **zero page JavaScript errors and
zero remote asset requests**; a fresh isolated Chrome context used no user
browser profile, account or network assets. No inference was called.

Evidence assertions check that the rover is away from base at tick 25 and home
at 27, the two existing return commands are still queued at 25, the added
commands execute at 29–31, actual death is at 47, and the checked branch ends
with 6/10 and 9.33 battery. The viewer payload and all input files match the
published design revision before and after recording. No viewer, simulator,
controller, reference-study or task-evidence file was modified.

The output is a silent **WebM first cut**, tested in local Chrome. MP4 export
and external submission-platform playback were not tested. Rendering bytes can
depend on browser, fonts and encoder versions; the script fixes evidence,
captions, frame rate, duration and tick/scroll timing, and records the actual
software versions used. The team still chooses the final story and submission.

## Reproduce

The [recording script](../../tools/lightlag_experiments/overnight_demo_video.py)
implements the [approved design](../superpowers/specs/2026-11-14-lightlag-demo-recording.md)
published at `b115cfcbce6106c0bfb7a0ac75357e0516c9d102`. It refuses existing output
or work directories and changed frozen input bytes. It injects only two caption
panels; it does not alter existing page styles, values, trajectories or labels.

The successful recording used CPython **3.12.16**, Playwright **1.65.2**, local
Chrome **157.0.8103.52**, and the free Playwright FFmpeg build **1013** (VP9).
Only the encoder was downloaded, into an isolated temporary runtime. From the
repository root, the exact encoder-install and recording commands were:

```sh
PLAYWRIGHT_BROWSERS_PATH=/tmp/lightlag-6974-demo-video-runtime PYTHONDONTWRITEBYTECODE=1 /tmp/lightlag-6974-overnight-analysis/bin/python -m playwright install ffmpeg
PYTHONDONTWRITEBYTECODE=1 /tmp/lightlag-6974-overnight-analysis/bin/python tools/lightlag_experiments/overnight_demo_video.py --chrome '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' --ffmpeg /tmp/lightlag-6974-demo-video-runtime/ffmpeg-1013/ffmpeg-mac --output /tmp/lightlag-6974-demo-video-cut02 --work-dir /tmp/lightlag-6974-demo-video-qa02
```

Choose new `--output` and `--work-dir` names for another recording. The script
streams JPEG browser frames to the isolated encoder and writes only the final
video, automated verification and narration into its output directory. It
decodes and tests that final video in a second isolated page; seven PNG
checkpoints stay in the work directory for inspection. The approved output was
then copied to `docs/lightlag-demo-media/first-cut-v1/`, with the separate visual
review added after inspection. Earlier temporary outputs were preserved.

Files in this first cut:

| Artifact | Bytes |
|---|---:|
| `lightlag-selected-case.webm` | 1,479,361 |
| `verification.json` | 6,389 |
| `narration.md` | 1,666 |
| `visual-review.json` | 1,402 |

The coordinator owns independent review, Git integration and shared
status/prize-document updates.
