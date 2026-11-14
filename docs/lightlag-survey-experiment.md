# Six regions, two inspections

Sölvi approved the next experiment after the three-region pilot failed to show a
convincing strong-model gap. This is a new experimental package, not a final
project/rules decision. The frozen expedition, shared physics and teammate work
remain unchanged.

The intended bottleneck is choosing what to learn before committing to an
itinerary. An opening sample and two inspections can give evidence about every
region in the old version. Here that opening leaves three regions without new
evidence. Imperfect inspection signals remain imperfect; observation does not
mean the true quality is known with certainty.

## Published mission contract

The new `SurveyEnvironment` retains the existing continuous driving, slip,
heading drift, noisy fixes, terrain costs, hazards, FIFO command queues, sampling
radius and return-home grading. Horizon 60, command/telemetry delay 3, battery
100, idle cost .5, sample cost 3, inspection cost 2 and inspection accuracy .9
remain unchanged. The global inspection budget is two, at most one per region,
reserved atomically on acceptance even if later canceled. Physical samples reveal
exact regional quality through delayed telemetry. Scripting remains allowed.

| Region | Rich prior | Two initial values | Radius from base | Initial deadline range |
|---|---:|---|---|---|
| r1 | .90 | 2, 2 | 4–7 m | 18–32 |
| r2 | .35 | 3, 3 | 6–10 m | 26–44 |
| r3 | .50 | 2, 2 | 5–9 m | 22–40 |
| r4 | .25 | 3, 3 | 6–10 m | 26–44 |
| r5 | .70 | 2, 2 | 4–8 m | 20–36 |
| r6 | .45 | 3, 3 | 5–9 m | 24–42 |

The map is 40×40 with base (20,20). Region bearings are 60 degrees apart with a
uniform whole-map rotation and ±20-degree target jitter. Published spacing,
clearance and bounded rejection rules apply to all fourteen targets, two sand
patches and two hazards. The two discoveries are value 3 each: r4 at tick 10,
deadline 26, and r6 at tick 22, deadline 44. Positions stay hidden until discovery.

Regional qualities are independent and fixed for the episode; poor/rich value
multipliers are .2/1. All targets in a region share quality. Normalization uses
the public **all-rich total 36**, never the realized hidden total. More targets
and a larger denominator may lower normalized scores; that alone is not harder
reasoning. Hidden/public-quality controls share seeds, physics and grading.

## Comparator and gate

The separate reference revision uses the existing public KF/MPC estimator and a
bounded planning horizon. It must compare acting, waiting for a physical sample,
and overlapping inspections with useful movement. Actual beliefs update only
when evidence is delivered; missed samples and canceled probes cannot produce
imaginary knowledge. Branches charge queue time, all action costs, future idle
drain and a safe return. It is a heuristic, not a globally optimal solver.

[The predeclared free gate](lightlag-survey-gate.md) compares adaptive acquisition
with no inspection, entropy and the best fixed pair selected on development
maps. All use the same movement, planning and admission logic. Development uses
576 episodes, followed—only if structural checks pass—by 128 checks on disjoint
map/episode seeds. All outcomes and regressions stay in the repository.

The environment increment has 22 passing tests, including 100 geometry seeds,
six-region hidden-state isolation, delayed learning, atomic inspection limits,
constant-denominator scoring, and all-rich/no-inspection equivalence to the
existing physical simulator on the same generated mission. No policy result or
model gap is claimed by these mechanics tests.

## Reference revision

`lightlag_expedition/reference_v2.py` is separate from the frozen reference. It
compares ordinary motion, waiting for a physical sample's revelation, waiting
for remote inspections, and driving/sampling while inspections share the queue.
Six-region development timing is approximately .28–.50 seconds per episode.
Sixteen focused tests and independent review pass; the three-test repair-study
runner retains controller errors separately from scores and reconstructs public
transcripts and full replays.

The planner caches feasible routes as regional value coefficients, evaluates at
most four targets and one first-target candidate per region, and chooses at most
two probes as a batch. All controls share its navigation and admission logic.
Only the proposed first physical sample branches on estimated hit/miss; direct
and continuation route samples use the frozen MPC's planned-success assumption.
Hypothetical sample outcomes change quality beliefs but do not condition pose
uncertainty, and future fixes/undiscovered positions are not forecast. Actual
delivered failures still update the KF. Diagnostic values and return checks are
heuristic predictions, not calibrated expectations or guarantees. These limits
apply equally to the adaptive and simpler acquisition policies.

## First comparator-repair result: retain the regression

The first [128-episode repair comparison](lightlag-runs/survey-reference-repair-v1/summary.json)
uses 32 previously declared development cases (old three-region maps 0–3,
episode seeds 100–107), each played by both references and both no-probe variants.
All public transcripts/replays reconstruct, all sources match `584809a`, and no
controller/harness errors occurred.

| Policy | Mean raw science after survival | Deaths | Alive and home |
|---|---:|---:|---:|
| Frozen reference | 7.68594 | 1/32 | 30/32 |
| First scheduling revision | 7.22500 | 2/32 | 29/32 |
| Frozen no-probe | 6.24375 | 2/32 | 30/32 |
| Revised no-probe | 6.78750 | 1/32 | 31/32 |

The revised adaptive reference is worse overall, despite supporting useful
inspection overlap. This result is not replaced or relabeled as an improvement.
A rover can be at base but dead after terminal idle drain; alive-and-home above
requires both. Physical return/battery regressions are being diagnosed before
launching the six-region development matrix. Any revised code and rerun will
use a new output directory and keep this source version and all outcomes.
No additional Claude API calls have been made.
