# Lightlag decision demo

The [offline decision page](../viewer/decisions.html) follows three selected
decisions from the fixed seed comparison. It shows saved evaluator truth beside
the latest delivered telemetry, including measurement noise. Two cases compare
an actual model run with a checked post-hoc continuation. The queue case uses an
independent recorded reference run from tick 0.

These are exploratory failure cases selected after outcomes. The
[complete comparison](lightlag-fixed-seed-comparison.md) retains all eight
attempts: **3 model wins, 2 ties and 3 deficits** against the frozen original
KF + MPC reference. This selection is not a population failure estimate.

## Build and open

From the repository root, with Python 3 and no extra dependencies:

```sh
python3 viewer/decision_build.py --out viewer/decisions.html
python3 -m unittest discover -s tests/viewer -v
open viewer/decisions.html
```

The generated file opens directly with `file://`; a server and network access
are unnecessary. It embeds all six complete replays and the page code. Source
links are relative to `viewer/`, so keep the repository's directory structure
to use those links. Copying only the HTML preserves playback, but not the
linked source artifacts. The existing `viewer/demo.html` remains a separate
four-run viewer and is not rebuilt by this command.

## Walkthrough

Each tab opens at its selected decision. Both maps share one tick slider.
Use Play/Pause, the previous/next buttons, Decision and Finish. Away from a
focused form control, Space toggles playback, Left/Right step one tick, Home
goes to tick 0, End goes to tick 50, and D returns to the decision. Arrow keys
on the case tabs switch cases; the slider also supports its native keyboard
controls. At narrow widths the two maps stack vertically.

The solid position marker and path show evaluator truth. The marker has no
orientation: a stored commanded heading is not the noisy drive's true heading.
The purple dashed ring shows
the latest packet whose recorded `received_tick` is no later than the selected
tick. Battery, packet timestamp, arrival time and observation age are separate
readouts. No true state is substituted for an observation, and no model belief
or internal estimate is inferred. Discovered targets appear on the evaluator
map at their appearance tick; an asterisk marks a discovery whose packet has
not yet arrived. Target labels show their full on-time value, not the reduced
late credit. Collected targets are filled using evaluator truth.

Pending commands are commands already sent by that tick but scheduled for a
later tick. Commands sent at the selected tick are included. The view does not
split multiple calls at the same simulator tick into separate frames. The
model cannot intervene during an `advance(5)` call; packets that arrive during
it are returned with that call. The decision notes identify those intervals.

1. **Rush, seed 501 — home is not the finish line.** At tick 20, call 13 adds
   two return drives totaling 7.02 action energy. The actual run reaches home
   at tick 25 with 11.521 battery, exhausts it at tick 49, and earns **0/12**.
   The right panel replays the public transcript through call 12, then sends
   no new commands. Existing commands still execute. It survives away from
   base with 6.041 battery and **5.25/12** after the 0.5 survival multiplier.
   The audit's main reference-relative loss is the earlier call 11; this
   separate salvage check does not redefine that audit attribution.
2. **Rush noisy, seed 502 — a queue runs dry.** Call 10 advances from tick 12
   to 17, while the queue ends at tick 14. New commands then cannot execute
   before tick 21. The audit's reference takeover could queue a sample at
   tick 12 to execute at 16. It attributes 2.25 raw points to the wait, with
   0.5 recovered by call 11. The displayed actual run earns **8.25/13**, and
   the **independent original KF + MPC run from tick 0** earns **10/13**.
   The right panel is not the audit's takeover branch and does not establish
   that every score difference was caused by this one wait.
3. **Rush noisy, seed 504 — the return was already queued.** Call 21 at tick
   25 adds 8.1 m of driving plus a sample, costing 11.1 energy. The existing
   queue brings the rover home at tick 27; the new excursion then leaves base.
   The sample succeeds on time, but the actual rover dies at tick 47 and earns
   **0/10**. The continuation through call 20 with no further commands stays
   at base, survives with 9.33 battery and earns **6/10**.

The battery plot always shows the full horizon. Its curves and final rewards
are evaluator-side outcomes, not predictions made by the model. Every survivor
pays the same **50 × 0.5 = 25** idle energy from its initial 100. It must spend
**strictly less than 75** on actions to remain alive at tick 50. Waiting affects
deadlines and opportunities, not this fixed bill; returning home does not
recharge. The selected-tick idle cost is only a lower bound on future energy
use and explicitly excludes actions. This is a delayed-command simulation
with toy rules, not a faithful Mars operations model.

## Provenance and verification

The saved actual runs identify `anthropic/claude-opus-5-5` in **OpenCode 1.19.5**.
Their frozen source commit is `02e4f7062ec3feaca14d9cc2eeb953af870ba769`.
The page links each actual replay, public tool transcript, audit, run identity
and source/task hashes. The queue case also links its independent reference.

The builder loads model/reference replay JSON without changing it. For each
post-hoc continuation, it creates the existing audit environment from the
saved replay, repeats every public tool call through the inclusive cutoff,
then calls `advance(5)` until the horizon. It stores the resulting replay only
inside the page payload. It refuses to build if the result or final battery
differs from the published
[seed-501 salvage check](lightlag-audits/fixed-seeds501-504/rush-seed501-delay3-opus-5-5/salvage-check.json)
or [seed-504 stop check](lightlag-audits/fixed-seeds501-504/rush-noisy-seed504-delay3-opus-5-5/stop-check.json).
It also requires the existing audits to report exact replay matches and no
infrastructure findings. No simulator, reference, auditor or evidence folder
is changed.

The new tests cover the exact scores and comparison labels, unmodified source
replays, the checked continuations and their shared prefixes, packet arrival
boundaries, preserved noisy observations, the full 51-state horizon, recorded
death ticks, JSON roundtrip and safe script embedding. The four original
viewer tests remain in the same verification command. Browser layout and
interaction checks are separate from these data tests.

Browser verification on 14 November: installed Chrome loaded the standalone
`file://` page, switched all cases, played/paused, stepped and scrubbed ticks,
jumped to decision/end, and exercised keyboard shortcuts. Layouts at 390, 768
and 1440 pixels had no horizontal overflow; desktop and mobile screenshots
were inspected. No JavaScript errors. The unavailable browser automation host
was replaced by an isolated local Playwright/Chrome session; no user browser
profile or external service was used. Independent spec and quality reviews
completed; all 13 viewer tests passed. A browser regression check also confirms
that embedded `<!--<script>` text cannot swallow the following page script.

## Privacy and limits

No paid inference, accounts, external fonts, assets or network calls are
needed. Only saved simulation evidence and selected provenance fields are
embedded: no API keys, local runtime files, account information, model
trajectory text or inferred private reasoning. Full replays include hidden
truth and slip/sensing information; this page is evaluator/demo material and
must not be supplied to the task's acting agent as an observation source.

The two continuations are post-hoc interpretation checks, not fresh model
trials. The reference is a feasible frozen controller, not an optimal policy.
No broad reliability, causal noise-effect or faithful physical-rover claim
follows from these examples. Preserve the complete mixed results when sharing
the demo, and use fresh predeclared trials for confirmation claims.
