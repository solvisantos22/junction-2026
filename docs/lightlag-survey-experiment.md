# Six regions, two inspections

**Free experiment complete; advancement gate failed.** No six-region model run
or canonical promotion. [Decision and handoff](lightlag-survey-handoff.md).

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

## Safety correction before the next comparison

The two deaths in the first scheduling revision followed departures near sand
boundaries. Their predicted travel costs were approximately 16 energy, while
executed travel cost 23–30. Inspection and idle charges were already included;
the weak point was estimating terrain from ideal waypoints despite uncertain
pose and slip.

The next revision propagates commanded drives through the public KF and prices
possible sand exposure in a covariance envelope using the existing 90% home
confidence level. Both outbound travel and return use guarded energy. This is
a conservative heuristic, not a safety guarantee, and applies identically to
every acquisition control. It does not change simulator physics, mission energy,
seeds, probe policy or the frozen first comparison.

Synthetic checks cover a public-world execution inside the pose envelope that
uses more sand than the nominal plan, variance-sensitive caching, correlated
pose, unchanged costs without sand, and outbound/home/idle reserve accounting.
Review also found that unobserved queued drives could release this extra reserve
when the inherited predictor used their mean cost. The correction retains
guarded-minus-mean cost until delivered battery telemetry reconciles it, excluding
canceled commands and avoiding duplicate sample, inspection or idle charges.
The entire 128-episode old-map comparison will be rerun in a new directory;
repair cases alone cannot establish improvement.

## Related teammate evidence

Kristján's [Lightlag Live research](lightlag-live.md), integrated in `d0da13b`,
reports a saved Opus autopilot approximately tied with the reference on 200 fresh
maps (.515 versus .518). Its selected campaign has a larger reference lead;
clock/harness incidents and reuse of fixed programs limit interpretation. This
is evidence against relying on a hand-played navigation gap when scripting is
allowed, not evidence for our new information bottleneck. The survey keeps
scripting available, a separate mechanism, and an unselected check split.
The Live report attributes about $9.15 to Kristján's key; that amount is separate
from this experiment's historical usage ledger and is not a verified balance.

The final correction passes 25 focused tests and independent safety review; the
combined reference/repair/study-runner suite passes 38 tests. Outcome improvements
remain to be measured on the full declared comparison.

## Second repair result: safer, still not a science improvement

The [second complete 128-episode repair comparison](lightlag-runs/survey-reference-repair-v2/summary.json)
uses the identical declared three-region development grid, frozen at `6192e8e`.
All cases complete without controller errors, all full replays reconstruct, and
source hashes remain unchanged.

| Policy | Mean raw science after survival | Deaths | Alive and home |
|---|---:|---:|---:|
| Frozen reference | 7.68594 | 1/32 | 30/32 |
| Guarded scheduling revision | 7.17031 | 0/32 | 32/32 |
| Frozen no-probe | 6.24375 | 2/32 | 30/32 |
| Guarded no-probe | 7.12344 | 0/32 | 32/32 |

The safety correction removes observed deaths and failed returns, but adaptive
mean raw science remains lower than the frozen reference. Within the revised
planner, inspections add only .046875 raw on these old maps. This is comparator
development, not independent validation or evidence of model difficulty. The
conservative guard trades some collection for survival; it is not universally
better. Both negative and positive outcomes remain published.

The next step is the predeclared six-region development matrix, with all controls
sharing the guarded navigation. Its structural gate and disjoint check still
determine whether a paid pilot is justified. A retained development-only timing
check ([artifact](lightlag-runs/survey-timing-v1/timing.json), map0/seed100) took
.517 seconds including transcript/replay reconstruction, within the declared
one-second target. No cases or settings were selected from that score.

## Six-region development and check freeze

The [576-episode development matrix](lightlag-runs/survey-development-v1/summary.json)
completes without errors; all replays reconstruct and source hashes are unchanged.
All six regions satisfy the competitive two-target/home criterion on maps 0, 1 and 3;
the adaptive reference physically samples every region across cases and uses
two different nonempty inspection sets (r2+r6, r4+r6). The structural gate passes.

| Development policy | Mean raw score | Alive and home |
|---|---:|---:|
| Adaptive | 8.88125 | 32/32 |
| No inspection | 8.18906 | 32/32 |
| Entropy | 8.26250 | 32/32 |
| Best fixed pair, r5+r6 | 9.15938 | 32/32 |

Adaptive gains .69219 over no inspection and .61875 over entropy, but loses
.278125 to the development-selected fixed pair. These are development outcomes,
not a passed check. The unchanged predeclared protocol permits the separate
check after structural passage; it will test all four policies on the full
128-case disjoint grid without tuning or choosing favorable cases.

[Check protocol](lightlag-runs/survey-check-v1/protocol.json) and its checksum
freeze the selected r5+r6 pair, source hashes and settings before any check
rollout. Preparation executes zero check policies. This freeze is pushed before
running the check. No model API calls have been made.

## Held-out result and decision

The [128-episode held-out check](lightlag-runs/survey-check-v1/summary.json) ran
only after seal commit `6760d3c` was pushed. All cases complete, replay/grade
reconstruction passes, source hashes are unchanged, and every policy returns
home alive in all 32 cases. These inputs are now used; they cannot validate a
tuned revision.

| Check policy | Mean raw score | Adaptive minus policy | Required gain |
|---|---:|---:|---:|
| Adaptive | 9.96250 | — | — |
| No inspection | 9.79219 | +0.17031 | +1.0 |
| Entropy | 10.09687 | −0.13437 | +0.5 |
| Development-selected fixed r5+r6 | 9.80156 | +0.16094 | +0.5 |

**The check fails every aggregate gain threshold.** Adaptive also beats or ties
no inspection on only two of four maps, below the required three. Against entropy
and the fixed pair it has nonnegative means on three maps but a larger loss on
map 4. Its raw map gains over no inspection are −.8125, −.20625, +1.5, +.2.
Safety passes; information-allocation gains do not. No paid call follows this
protocol. No stronger-model failure is claimed: no model played this survey.

Across all check cases the adaptive reference chooses the same inspection pair,
r2+r6; entropy chooses r3+r6 and the fixed control r5+r6. The larger map stops
the old opening from observing every region, but does not itself make adaptive
acquisition demonstrably necessary. All six areas being competitive is a useful
structural property, not sufficient evidence of a reasoning challenge.

This does not prove an optimal adaptive policy cannot win: the public comparator
has explicit planning approximations, and the check crosses only four maps with
eight quality/noise draws. It does show that this implementation has not earned
scarce model credits or replacement of the team's task. The next design should
test consequential, context-dependent information choices before adding regions.
[Handoff](lightlag-survey-handoff.md) records preserved inputs, limits and next work.

### Saved-trace diagnosis (no reruns)

Every adaptive launch in both matrices sends two inspections with no productive
sample prefix, despite the planner supporting overlap candidates. In the check,
no-probe physically samples 4.0 distinct regions per episode on average versus
3.71875 for adaptive. Physical samples reveal quality while earning science.
Adaptive has 9 failed samples and 9 late samples across 32 cases, versus 3 and 3
for no-probe; entropy has 5 and 4. These are realized trace counts, not a causal
ablation: choices, travel and outcomes all differ. They identify navigation,
scheduling and planning approximations as confounds in the weak acquisition gain.

Thus the result is not proof that information is useless or that an optimal
policy cannot benefit. A stronger public decision oracle could improve this
comparison. Future work should isolate the acquisition/commitment tradeoff and
require a material advantage over matched simple policies before model testing.

The saved decision logs make the reference issue more specific: adaptive's first
physical sample averages tick 13.25, versus 5.75 for no-probe and 7.25 for entropy
and the fixed control. On maps 4–6 the initial heuristic favors waiting over its
best overlap by only .049–.056 raw. Prefix samples have hit/miss branches while
continuation samples assume planned success, so these close modeled choices
should not be treated as reliable value estimates.

Initial standalone region values are identical across all check cases: r1=3.68,
r2=2.88, r3=2.4, r4=2.4, r5=3.04, r6=3.36. Initial direct value is 7.04 from r1+r6.
The geometry variation preserved feasibility without changing these rankings.
Varying the public decision context and making exploration compete with a
consequential commitment is a better next hypothesis than increasing choice count.

Independent artifact audits confirm all 704 survey cases, their paired worlds,
full source/artifact hashes, sample-credit/safety arithmetic, fixed-pair selection,
structural plans and check margins. The check seal matches its published pre-run
commit exactly. Additive `independent-audit.json` reports sit with the original
evidence; no outcomes or frozen protocols were rewritten.
