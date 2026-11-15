# The submission video

**[`lightlag-traverse-submission.mp4`](lightlag-traverse-submission.mp4) is the film to upload for the Junction submission** (1:59, 1920×1080, 33.7 MB; the limit is 2:00). Manh named it the final submission video on Sunday 15 November 2026, about 07:45 Helsinki. Whoever uploads: this file, not `docs/demo-video/` and not `docs/manh-demo/manh_demo_2.mp4`.

```bash
git pull
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 docs/submission-video/lightlag-traverse-submission.mp4   # 119.100000
```

| File | What it is |
|---|---|
| [`lightlag-traverse-submission.mp4`](lightlag-traverse-submission.mp4) | The film: the picture of `manh_demo_2` with the team's own narration laid in |
| [`lightlag-traverse-submission.srt`](lightlag-traverse-submission.srt) | Subtitles with the words as spoken, for the upload |

## What it is

The second draft film of [`docs/manh-demo/`](../manh-demo/README.md#the-second-draft-manh_demo_2) (twelve shots: Mars from orbit, nine models of three labs, one failure per tier, the model's own report, the sun, every run against the planner, the planner's four methods, 300 fresh worlds, the models that learn, the end card), with the placeholder voice replaced by a teammate's recording. The recording was cut into its 15 lines, each line put on its picture, one false start removed, and the voice cleaned and levelled by [`narration-kit/lay_narration.py`](../manh-demo/narration-kit/README.md); the exact command is in that README ("The first real take"). The picture is byte for byte the draft's. The same file is also at `docs/manh-demo/narration-kit/manh_demo_2_narrated.mp4`.

## Before uploading: what is checked and what is not

- **Length 119.1 s, sound −16.0 LUFS, peak −4.3 dBFS** (measured). A speech recogniser hears all 15 lines at their times, each with its first word.
- **Every number said or shown is counted from the saved runs**, and the build of the picture stops if one changes: see ["What the film says, and what holds"](../manh-demo/README.md#the-second-draft-manh_demo_2). "None beat our driver" is about the three-site campaign and the line says so.
- **Line 11 ends on "gained less".** The script's last words there, "than half a point", are not in the recording. The slide behind it shows the number (+0.48 points). To fix it, record that line again as the kit's README describes.
- **Line 12** is spoken as "It can't plan the day" (the script has "can't yet").
- **Nobody but Manh has watched it, and the voice treatment was set by measurement, not by ear**: listen once on headphones and once on laptop speakers before it goes up.
- Kristján's film, [`docs/demo-video/lightlag-traverse-demo.mp4`](../demo-video/lightlag-traverse-demo.mp4), is unchanged and remains the fallback, with the source of every number in his README.

If the team decides otherwise, change this page, the "Video" line of the front page and the video rows of `docs/submission-entry.md` and `docs/submission-checklist.md`.
