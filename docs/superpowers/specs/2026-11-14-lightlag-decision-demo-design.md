# Lightlag decision demo design

The user approved building a decision-focused demo and explicitly delegated
routine decisions during an overnight work block. This records the bounded
design before implementation. Final project/rules choice remains open.

## Purpose and alternatives

Show a judge one concrete decision, the information available then, and the
verified consequence. The existing general replay viewer is useful context but
does not explain these dynamic-task failures. A new live simulator UI would
add unnecessary implementation and reproducibility risk. We choose a separate,
offline evidence page built from saved replays, preserving the existing viewer.

## Page and interaction

Create `viewer/decisions.html` with three selectable cases:

1. Rush 501: actual model versus a **post-hoc continuation** that sends no more
   commands after call 12. Actual reward 0; alternative 5.25/12, alive away from
   base. This demonstrates the remaining salvage before the homeward drive.
2. Noisy 502: actual model versus the **independent reference from the start**.
   Scores 8.25/13 and 10/13. Focus call 10, waiting from tick 12 to 17 while the
   command queue empties. Do not label this reference run a branch of the agent.
3. Noisy 504: actual model versus a **post-hoc continuation** that sends no more
   commands after call 20. Actual reward 0; alternative 6/10, alive at base.
   The queued return arrives at 27; call 21 adds an unaffordable excursion.

Use two replay panels on one tick slider, with play/pause, previous/next tick,
and buttons to jump to the decision or finish. Show true position, the last
delivered observation with its age, queued commands, battery and final reward.
Draw battery traces through the horizon and mark the decision/death ticks.
Support keyboard controls and a usable narrow-screen layout. No external
assets, server, network or build dependency is required to open the result.

## Explain what the data means

Truth is evaluator-side replay, never information given to the playing model.
Use the actual delivered/noisy telemetry, not truth states relabelled as an
observation. Do not invent a model belief or predicted position. Explicitly
label branches as post-hoc and the independent reference as a separate policy.

The energy panel must explain that every survivor pays **25 idle energy** over
the fixed 50-tick horizon, leaving 75 for movement and samples. Waiting changes
deadlines/opportunities; it does not increase that common full-horizon idle bill.
A tick-specific idle reserve is a lower bound excluding further actions. Any
forecast from true state/continuation must be marked evaluator-side, not an
estimate the model actually formed. Keep runtime plumbing out of the main story.

Display source artifact/audit links, exact agent/model and profile/seed, and a
link to the complete mixed eight-run comparison. Do not imply these selected
failure cases estimate overall failure frequency. The first version uses the
original exploratory traces; overnight repeat outcomes are a separate study.

## Implementation boundaries

- New `viewer/decision_build.py`: load saved evidence, replay the two declared
  continuations through existing `make_environment`, validate against saved
  counterfactual checks, and embed a small structured payload in the template.
- New `viewer/decision_template.html`: standalone SVG/HTML/CSS/JavaScript UI.
- New `viewer/decisions.html`: generated distributable, safe JSON embedding.
- New `tests/viewer/test_decision_build.py`: meaningful data/branch/timing checks.
- New `docs/lightlag-decision-demo.md`: build/open commands, case walkthrough,
  source provenance and limitations.

Do not modify simulator, controllers, audit implementation, existing viewer
files or run folders. Validate scores, branch equivalence, visible-packet timing,
safe embedding and original-file preservation; inspect the page in a browser.
Self-review: scope is a replay presentation only, no new rules or inference.
