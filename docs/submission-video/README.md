# The submission video

**[`lightlag-traverse-submission.mp4`](lightlag-traverse-submission.mp4) is the film of the Junction submission** (1:59, 1920×1080, 33.7 MB; the limit is 2:00). It is public at **<https://youtu.be/NYYjwijLLm4>** and that link is in the entry's Video field ([upload notes](../video-upload.md)). Manh named the film the final submission video on Sunday 15 November 2026, about 07:45 Helsinki. At about 08:10 its line 11 was recorded again and laid in, at Kristján's word; everything else is the 07:45 film.

```bash
git pull
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 docs/submission-video/lightlag-traverse-submission.mp4   # 119.104000
shasum -a 256 docs/submission-video/lightlag-traverse-submission.mp4   # e5705857a9bfd91873c9f9a1e644cb5eda9583716951216c52b83716e02ff348
```

| File | What it is |
|---|---|
| [`lightlag-traverse-submission.mp4`](lightlag-traverse-submission.mp4) | The film: the picture of `manh_demo_2` with the team's own narration laid in |
| [`lightlag-traverse-submission.srt`](lightlag-traverse-submission.srt) | Subtitles with the words as spoken |

## What it is

The second draft film of [`docs/manh-demo/`](../manh-demo/README.md#the-second-draft-manh_demo_2) (twelve shots: Mars from orbit, nine models of three labs, one failure per tier, the model's own report, the sun, every run against the planner, the planner's four methods, 300 fresh worlds, the models that learn, the end card), with the placeholder voice replaced by a teammate's recording. The recording was cut into its 15 lines, each line put on its picture, one false start removed, and the voice cleaned and levelled by [`narration-kit/lay_narration.py`](../manh-demo/narration-kit/README.md); the exact command is in that README ("The first real take"). The picture is byte for byte the draft's. The kit's `docs/manh-demo/narration-kit/manh_demo_2_narrated.mp4` is the 07:45 film with the first take of line 11; since 08:10 it is no longer the same file as this one.

## Line 11, recorded again

In the 07:45 film line 11 ended: "Even a model trained to pick the planner's strategy gained less." The script's last words, "than half a point", were not in the recording, and Kristján heard the sentence as the learned model falling short of the planner. It is the other way round. The model (Extra Trees, picking one of the planner's strategies mid-mission) plays on top of the planner, and the pair scores higher than the planner alone: 50.46% against 49.98% on 96 fresh worlds ([`docs/learned-portfolio-results/README.md`](../learned-portfolio-results/README.md)). The narrator recorded the line again as:

> We trained a small one from scratch: from 8% to 36% on unseen worlds, still short of the planner. A model that picks the planner's strategy did beat it, by under half a point.

"Still short of the planner" is about the small model trained from scratch. "Under half a point" is the 0.48 points of the first test (95% interval 0.27 to 0.72); on 192 more worlds the lead was 0.28 points (−0.07 to 0.52). The slide behind the line shows +0.48.

How it was laid in (Kristján / Claude Code, Traverse session):

```bash
# the new recording alone, cleaned, levelled and put on its time by the kit, over the film without a narrator
mkdir lines && cp new-take.m4a lines/n11.m4a
python3 docs/manh-demo/narration-kit/lay_narration.py lines lines --out n11_only.mp4     # n11 1:40.2 to 1:50.7, as recorded

# that line's stretch, 1:39.5 to 1:51.8, cross-faded into the 07:45 film in the silence on either side; the picture is copied
ffmpeg -i lightlag-traverse-submission.mp4 -i n11_only.mp4 -filter_complex "\
[0:a]volume='1-clip((t-99.50)/0.08,0,1)*clip((111.78-t)/0.08,0,1)':eval=frame[a0];\
[1:a]volume='clip((t-99.50)/0.08,0,1)*clip((111.78-t)/0.08,0,1)':eval=frame[a1];\
[a0][a1]amix=inputs=2:normalize=0:dropout_transition=0[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -movflags +faststart corrected.mp4
```

## What is checked and what is not

- **Length 119.1 s, sound −16.1 LUFS, peak −2.7 dBFS** (measured). The new line measures −15.9 LUFS, between its neighbours (−15.4 and −16.3). The picture stream is the 07:45 film's, copied without re-encoding.
- **A speech recogniser hears the ending as:** "Can a machine learn it instead? We trained a small one from scratch, from 8% to 36% on unseen worlds. Still short of the planner, a model that picks the planner strategy did beat it by under half a point. AI can write the code. It can't plan the day. Can your agent make it home?" The punctuation is the recogniser's. In the recording the longest pause of the line (0.6 s) comes after "planner" and a shorter one (0.5 s) before "still", so the break falls where the script has it; whether it also sounds that way is for a listener to say.
- **"A model that picks…" begins at 1:46.9**, where the picture brings up the planner's panel (1:47.0).
- **Who has heard it:** the corrected film was opened for Kristján, who then asked for it to be published. Claude Code cannot listen; the levels and the cut were set by measurement. The 07:45 film was watched by Manh.
- **Every number said or shown is counted from the saved runs**, and the build of the picture stops if one changes: see ["What the film says, and what holds"](../manh-demo/README.md#the-second-draft-manh_demo_2). "None beat our driver" is about the three-site campaign and the line says so.
- **Line 12** is spoken as "It can't plan the day" (the script has "can't yet").
- **Not changed:** the kit's script and timings (`docs/manh-demo/narration-kit/narration.md`, `timing.json`, `narration.srt`), `docs/manh-demo/script-v2.md` and the drafts `manh_demo_2.mp4` and `manh_demo_long.mp4` still carry the old wording of this line. They are Manh's; the submission is this file.
- Kristján's film, [`docs/demo-video/lightlag-traverse-demo.mp4`](../demo-video/lightlag-traverse-demo.mp4), remains the fallback, with the source of every number in his README.

If the team decides otherwise, change this page, the "Video" line of the front page and the video rows of `docs/submission-entry.md` and `docs/submission-checklist.md`.
