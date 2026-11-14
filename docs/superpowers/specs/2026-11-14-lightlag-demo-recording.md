# Lightlag evidence recording design and plan

The user authorized autonomous overnight development and a morning handoff.
This reversible presentation increment prepares a silent first cut for review;
it does not submit a video, select final rules or claim a new model result.

## Chosen approach

Record the already verified offline `viewer/decisions.html` in an isolated local
Chrome session. Use one legible landscape clip, roughly 45–70 seconds, focused
on the most direct comparison: noisy seed 504, actual run versus no new commands
after call 20. Preserve the page's actual data and comparison labels. A short
caption overlay is allowed solely to guide the recording; do not alter the
saved trajectories, values or app source. Also provide a plain narration script
and recording commands so the team can revise it after choosing the final task.

A static montage would conceal the evolving queue and battery. A long recording
of all three cases would overload a first cut. The selected single case provides
one clear decision, while the full-results banner and ending acknowledge the
three wins, two ties and three deficits in the original eight-run comparison.
The clip is explicitly a recorded replay with a post-hoc continuation, not a
live model rollout or an estimate of failure prevalence.

## Story and acceptance

1. Establish the selected-case context and fixed mission contract.
2. Show case 504 at tick 25: the accepted return is still in flight; a further
   drive/sample excursion commits 11.1 action energy. The existing queue reaches
   home at tick 27. Never imply it was already home at tick 25.
3. Play the two replays together through tick 50. Actual battery exhausts at
   tick 47; the checked no-new-command continuation ends alive at home with
   9.33 battery and 6/10 reward, versus actual 0/10.
4. Show the battery chart and decision explanation. Explain that every survivor
   pays 25 idle energy; getting home earlier does not reduce that fixed bill.
5. End with mixed-results context, source locations and the limitation that a
   post-hoc continuation is not a fresh successful model attempt.

Keep map, queue, score and captions readable at the recorded resolution. Inspect
representative extracted frames, verify duration/dimensions and playback, and
check the final outcome against the frozen page payload. No external assets,
accounts, user browser profile, API calls or uploads. Browser/encoder dependencies
stay in an isolated temporary environment. Publish a modest-size video artifact
plus README/narration, not redundant full-resolution intermediate frames.

## Implementation sequence

- Check local capture/encoding support; use the established isolated Playwright
  and installed Chrome, downloading only its free local encoder if necessary.
- Write the narrow deterministic recording script under the claimed tool path.
- Capture to a new temporary output, encode a broadly playable result, and save
  only the final clip plus a compact verification record under the claimed docs
  directory. Preserve any earlier outputs until verification succeeds.
- Inspect the start, queued return, death and final frames; test offline video
  loading and confirm all text/values/timings.
- Independent review then root verification/integration; add accurate prize
  evidence and link from the morning brief. No change to the existing viewer.
