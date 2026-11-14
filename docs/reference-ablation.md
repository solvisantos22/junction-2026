# Reference component ablations

Requested by Kristján on 14 November: modify each part of the reference a little
and collect evidence of possible improvements. This is an isolated normal-map
experiment, not a change to the frozen reference, simulator or submission task.
Sölvi's active learning and Manh's learned second opinion remain separate.

## Protocol, fixed before the first development result

- Use the exact full-budget reference from the pinned checkout as the baseline.
  All variants retain the same public five-tool interface, mission and score.
- Fifteen configurations: baseline; cubature heading propagation; double the
  position process noise; weaker slip prior weight; more pessimistic slip prior;
  half/double path energy price; 1.5x search steps/beam; replanning every six ticks;
  four-tick deadline margin; 5% longer predicted legs; battery floor 3.5;
  two-tick home margin; arrival threshold 1.3 m; midpoint initial solar prior.
  Exact controls live in `tools/reference_ablation/variants.py`.
- Development: all fifteen on worlds **450000–450011** (180 missions).
  Existing used worlds 1/2 are only for smoke/equivalence checks. None of the
  reserved submission, MAX, or teammate learning maps are used.
- Rank changes by paired mean reward improvement. Eligibility requires a positive
  mean, no increase in deaths or failures to return, no invalid requests/errors,
  and mean CPU time at most 1.75x baseline. Select the best two changes from
  different components; also combine up to the best three eligible components.
  No adaptive follow-up tuning within this study.
- Freeze selection and all source hashes before opening fresh worlds
  **451000–451031**. Evaluate baseline, the two selected individual changes and
  the combination (at most 128 confirmation missions). If only one component
  qualifies, compare it with baseline; if none qualify, report that and stop.
- Primary candidate: the combination if it has at least two members; otherwise
  the best individual. A useful confirmed gain requires mean improvement at least
  **0.01 official reward**, a positive lower end of its paired 95% bootstrap
  interval, no worse home/alive counts, no invalid calls/errors and CPU <=1.75x.
  Other fresh comparisons are secondary; report multiplicity-adjusted intervals
  as well as ordinary intervals. No automatic canonical promotion.
- Retain every mission, including exceptions; do not replace seeds, discard
  failures or rerun for better outcomes. Per-mission archives contain commands,
  true trajectory, received telemetry, grade and passive filter/prediction logs.
  Hidden truth is used only by the evaluator after the episode, never by a pilot.
- Report score, sample value/count, late samples, alive/home, invalid requests,
  safety stops, pose RMSE at the telemetry timestamp, queued-prediction RMSE,
  minimum battery and CPU/wall time. Compare paired by world; bootstrap 20,000
  resamples with fixed seed. Development intervals are descriptive after search.
- Verify that the unmodified wrapper produces exactly the original pilot's
  replay on a used smoke world. Audit every completed saved physics replay and
  score; separately repeat a small declared set of full controller runs.

The cubature filter rotates the nominal displacement according to the heading
bias distribution, using six sigma points and the same process/measurement
noise. It does **not** evaluate the terrain model separately at each point;
this is a small estimator ablation, not a complete redesign.

All computation is local, with no API calls or cloud jobs. Six worker processes
leave capacity for teammates; elapsed runtime will be measured rather than
estimated as a result. Source hashes make later core changes fail visibly.
